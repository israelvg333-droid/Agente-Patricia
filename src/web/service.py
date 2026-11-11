"""Ejecucion en segundo plano del pipeline real para la interfaz grafica.

Cada analisis se encola como un trabajo y lo procesa un unico hilo worker
(Whisper y librosa son costosos; procesarlos en serie evita saturar el equipo).
El worker invoca `main.analyze_call`, la misma funcion que usa la CLI, y
reporta las etapas reales del pipeline para mostrar el progreso.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import main as pipeline
from src.utils.logger import get_logger

logger = get_logger("subagente_seriedad.web.service")

# Orden de etapas tal como las emite `analyze_call`.
PIPELINE_STAGES = [
    pipeline.STAGE_TRANSCRIPTION,
    pipeline.STAGE_ACOUSTIC,
    pipeline.STAGE_SEMANTIC,
    pipeline.STAGE_SCORING,
    pipeline.STAGE_SAVING,
]
WHISPER_MODELS = ("tiny", "base", "small")
LANGUAGES = ("es", "en")
_MAX_FINISHED_JOBS = 200


@dataclass
class Job:
    id: str
    mode: str  # "audio" | "transcript_only"
    source_name: str
    input_path: str
    language: str
    model: str
    status: str = "en_cola"  # en_cola | procesando | completado | error
    stage: str | None = None
    completed_stages: list[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: _now())
    started_at: str | None = None
    finished_at: str | None = None
    result_id: str | None = None
    error: str | None = None
    error_type: str | None = None

    def public(self, queue_position: int | None = None) -> dict[str, Any]:
        data = asdict(self)
        data.pop("input_path", None)
        data["stages"] = PIPELINE_STAGES
        data["queue_position"] = queue_position
        return data


class AnalysisService:
    """Cola de analisis con un worker dedicado."""

    def __init__(self, output_dir: Path) -> None:
        self.output_dir = Path(output_dir)
        self._jobs: dict[str, Job] = {}
        self._order: list[str] = []
        self._queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self._current: str | None = None
        self._worker = threading.Thread(
            target=self._run, name="analisis-worker", daemon=True
        )
        self._worker.start()

    # -- API publica -----------------------------------------------------
    def submit(
        self,
        *,
        mode: str,
        input_path: Path,
        source_name: str,
        language: str = "es",
        model: str = "tiny",
    ) -> Job:
        job = Job(
            id=uuid.uuid4().hex[:12],
            mode=mode,
            source_name=source_name,
            input_path=str(input_path),
            language=language,
            model=model,
        )
        with self._lock:
            self._jobs[job.id] = job
            self._order.append(job.id)
            self._trim_finished()
        self._queue.put(job.id)
        return job

    def get(self, job_id: str) -> dict[str, Any] | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return job.public(self._queue_position(job_id))

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            ids = self._order[-limit:][::-1]
            return [self._jobs[i].public(self._queue_position(i)) for i in ids]

    def worker_state(self) -> dict[str, Any]:
        with self._lock:
            pending = sum(1 for j in self._jobs.values() if j.status == "en_cola")
            current = self._jobs.get(self._current) if self._current else None
            return {
                "alive": self._worker.is_alive(),
                "busy": current is not None,
                "current_job": current.public() if current else None,
                "queued": pending,
            }

    # -- worker ----------------------------------------------------------
    def _run(self) -> None:
        while True:
            job_id = self._queue.get()
            try:
                self._process(job_id)
            except Exception:  # defensa final: el worker nunca debe morir
                logger.exception("Fallo inesperado procesando el trabajo %s", job_id)
            finally:
                self._queue.task_done()

    def _process(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = "procesando"
            job.started_at = _now()
            self._current = job_id

        def on_stage(stage: str) -> None:
            with self._lock:
                if job.stage and job.stage not in job.completed_stages:
                    job.completed_stages.append(job.stage)
                job.stage = stage

        args = argparse.Namespace(
            audio=job.input_path if job.mode == "audio" else None,
            transcript=job.input_path if job.mode == "transcript_only" else None,
            output_dir=str(self.output_dir),
            language=job.language,
            model=job.model,
        )
        try:
            _payload, output_path = pipeline.analyze_call(args, on_stage=on_stage)
        except Exception as exc:
            logger.warning("Analisis %s fallido: %s", job_id, exc)
            with self._lock:
                job.status = "error"
                job.error = str(exc) or type(exc).__name__
                job.error_type = type(exc).__name__
                job.finished_at = _now()
                self._current = None
            return

        with self._lock:
            if job.stage and job.stage not in job.completed_stages:
                job.completed_stages.append(job.stage)
            job.stage = None
            job.status = "completado"
            job.result_id = Path(output_path).stem
            job.finished_at = _now()
            self._current = None

    # -- utilidades internas (llamar con el lock tomado) -------------------
    def _queue_position(self, job_id: str) -> int | None:
        queued = [i for i in self._order if self._jobs[i].status == "en_cola"]
        return queued.index(job_id) + 1 if job_id in queued else None

    def _trim_finished(self) -> None:
        finished = [i for i in self._order if self._jobs[i].status in ("completado", "error")]
        for job_id in finished[: max(0, len(finished) - _MAX_FINISHED_JOBS)]:
            self._order.remove(job_id)
            del self._jobs[job_id]


class ImportProbe:
    """Comprueba en segundo plano si un modulo se puede IMPORTAR de verdad.

    `find_spec` solo dice que el paquete existe; Whisper (torch, numba,
    tiktoken) puede estar instalado y aun asi fallar al importarse. La prueba
    se hace en un subproceso con el mismo interprete del servidor para no
    cargar torch en este proceso. Un exito se conserva; un fallo se vuelve a
    comprobar tras `retry_seconds` (por ejemplo, despues de instalar).
    """

    def __init__(self, modules: tuple[str, ...], retry_seconds: float = 60.0) -> None:
        self.modules = modules
        self.retry_seconds = retry_seconds
        self._results: dict[str, dict[str, Any]] = {}
        self._running: set[str] = set()
        self._lock = threading.Lock()

    def result(self, module: str) -> dict[str, Any]:
        """{"ok": True|False|None, "detalle": str|None}; None = verificando."""
        with self._lock:
            current = self._results.get(module)
            stale = (
                current is not None
                and current["ok"] is False
                and time.monotonic() - current["checked"] > self.retry_seconds
            )
            if (current is None or stale) and module not in self._running:
                self._running.add(module)
                threading.Thread(
                    target=self._probe, args=(module,), name=f"probe-{module}", daemon=True
                ).start()
            if current is None:
                return {"ok": None, "detalle": None}
            return {"ok": current["ok"], "detalle": current["detalle"]}

    def start_all(self) -> None:
        for module in self.modules:
            self.result(module)

    def _probe(self, module: str) -> None:
        ok, detail = probe_import(module)
        with self._lock:
            self._results[module] = {"ok": ok, "detalle": detail, "checked": time.monotonic()}
            self._running.discard(module)


def probe_import(module: str, timeout: float = 180.0) -> tuple[bool, str | None]:
    """Importa `module` en un subproceso del mismo interprete."""
    if importlib.util.find_spec(module) is None:
        return False, f"El paquete '{module}' no está instalado en {sys.executable}."
    try:
        completed = subprocess.run(
            [sys.executable, "-c", f"import {module}"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, f"La importación de '{module}' superó {int(timeout)} s."
    except OSError as exc:
        return False, f"No se pudo verificar '{module}': {exc}"
    if completed.returncode == 0:
        return True, None
    lines = [line for line in (completed.stderr or "").splitlines() if line.strip()]
    return False, lines[-1] if lines else f"La importación de '{module}' falló."


IMPORT_PROBE = ImportProbe(("librosa", "soundfile", "whisper"))


def python_runtime() -> dict[str, Any]:
    return {
        "ejecutable": sys.executable,
        "version": sys.version.split()[0],
        "entorno_virtual": sys.prefix != sys.base_prefix,
    }


def system_dependencies(
    output_dir: Path, probe: ImportProbe | None = None
) -> dict[str, Any]:
    """Disponibilidad real de las dependencias que el pipeline necesita."""
    probe = probe or IMPORT_PROBE

    output_dir = Path(output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        writable = os.access(output_dir, os.W_OK)
    except OSError:
        writable = False

    def module_component(module_id: str, **info: Any) -> dict[str, Any]:
        state = probe.result(module_id)
        return {"id": module_id, "ok": state["ok"], "detalle": state["detalle"], **info}

    components = [
        module_component(
            "librosa",
            nombre="Análisis acústico (librosa)",
            requerido_para="features acústicas e indicadores de voz",
            solucion="pip install -r requirements.txt",
        ),
        module_component(
            "soundfile",
            nombre="Lectura de audio (soundfile)",
            requerido_para="decodificar .wav/.flac/.ogg",
            solucion="pip install -r requirements.txt",
        ),
        module_component(
            "whisper",
            nombre="Transcripción local (Whisper)",
            requerido_para="transcribir audio automáticamente",
            solucion="pip install openai-whisper",
        ),
        {
            "id": "ffmpeg",
            "nombre": "FFmpeg",
            "ok": shutil.which("ffmpeg") is not None,
            "detalle": None,
            "requerido_para": "decodificar .mp3/.m4a y transcribir con Whisper",
            "solucion": "Instale FFmpeg y agréguelo al PATH",
        },
        {
            "id": "output_dir",
            "nombre": "Directorio de resultados",
            "ok": writable,
            "detalle": None,
            "requerido_para": "guardar resultado_<fecha>.json",
            "solucion": f"Verifique los permisos de escritura en {output_dir}",
        },
    ]
    by_id = {c["id"]: c["ok"] for c in components}
    verifying = any(ok is None for ok in by_id.values())
    audio_ready = bool(by_id["librosa"] and by_id["whisper"] and by_id["ffmpeg"])
    if not by_id["output_dir"]:
        overall = "fuera_de_servicio"
    elif verifying:
        overall = "verificando"
    elif audio_ready:
        overall = "operativo"
    else:
        overall = "degradado"
    return {
        "estado": overall,
        "analisis_audio_completo": audio_ready,
        "analisis_texto": by_id["output_dir"],
        "componentes": components,
        "python": python_runtime(),
    }


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
