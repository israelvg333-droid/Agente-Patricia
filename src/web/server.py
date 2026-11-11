"""Servidor Flask: API REST + archivos estaticos de la interfaz EVA."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.utils import secure_filename

from src.audio.preprocessing import SUPPORTED_AUDIO_EXTENSIONS
from src.utils.config import DATA_DIR, OUTPUT_DIR, ensure_directories
from src.web.history import ResultHistory
from src.web.service import (
    IMPORT_PROBE,
    LANGUAGES,
    WHISPER_MODELS,
    AnalysisService,
    system_dependencies,
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
UPLOAD_DIR = DATA_DIR / "uploads"
MAX_UPLOAD_MB = 200
MAX_TEXT_CHARS = 20000
TEXT_EXTENSIONS = {".txt"}


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400, code: str = "solicitud_invalida"):
        super().__init__(message)
        self.message = message
        self.status = status
        self.code = code


def create_app(
    output_dir: Path | None = None,
    upload_dir: Path | None = None,
    service: AnalysisService | None = None,
) -> Flask:
    ensure_directories()
    output_dir = Path(output_dir or OUTPUT_DIR)
    upload_dir = Path(upload_dir or UPLOAD_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)

    app = Flask(__name__, static_folder=None)
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_MB * 1024 * 1024
    app.json.ensure_ascii = False
    app.json.sort_keys = False

    history = ResultHistory(output_dir)
    IMPORT_PROBE.start_all()
    analysis = service or AnalysisService(output_dir)
    started_at = datetime.now().isoformat(timespec="seconds")

    # -- interfaz ---------------------------------------------------------
    @app.get("/")
    def index() -> Any:
        return send_from_directory(STATIC_DIR, "index.html")

    @app.get("/static/<path:filename>")
    def static_files(filename: str) -> Any:
        return send_from_directory(STATIC_DIR, filename)

    # -- API --------------------------------------------------------------
    @app.get("/api/status")
    def status() -> Any:
        deps = system_dependencies(output_dir)
        return jsonify(
            {
                **deps,
                "worker": analysis.worker_state(),
                "servidor_iniciado": started_at,
                "directorio_resultados": str(output_dir),
                "formatos_audio": sorted(SUPPORTED_AUDIO_EXTENSIONS),
                "formatos_texto": sorted(TEXT_EXTENSIONS),
                "modelos_whisper": list(WHISPER_MODELS),
                "idiomas": list(LANGUAGES),
                "max_upload_mb": MAX_UPLOAD_MB,
            }
        )

    @app.get("/api/stats")
    def stats() -> Any:
        return jsonify(history.stats())

    @app.get("/api/analyses")
    def list_analyses() -> Any:
        return jsonify({"items": history.list()})

    @app.get("/api/analyses/<result_id>")
    def get_analysis(result_id: str) -> Any:
        try:
            detail = history.get(result_id)
        except (OSError, ValueError) as exc:
            raise ApiError(
                f"El resultado {result_id} no se pudo leer: {exc}", 500, "resultado_ilegible"
            ) from exc
        if detail is None:
            raise ApiError(f"No existe el resultado {result_id}.", 404, "no_encontrado")
        return jsonify(detail)

    @app.post("/api/analyze")
    def analyze() -> Any:
        language = request.form.get("language", "es")
        model = request.form.get("model", "tiny")
        if language not in LANGUAGES:
            raise ApiError(f"Idioma no soportado: {language}.")
        if model not in WHISPER_MODELS:
            raise ApiError(f"Modelo de Whisper no soportado: {model}.")

        job_dir = upload_dir / (
            datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + _short_token()
        )
        upload = request.files.get("file")
        text = (request.form.get("text") or "").strip()

        if upload and upload.filename:
            original = upload.filename
            suffix = Path(original).suffix.lower()
            if suffix not in SUPPORTED_AUDIO_EXTENSIONS | TEXT_EXTENSIONS:
                allowed = ", ".join(sorted(SUPPORTED_AUDIO_EXTENSIONS | TEXT_EXTENSIONS))
                shown = suffix or "(sin extensión)"
                raise ApiError(f"Formato no soportado: {shown}. Use {allowed}.")
            stem = secure_filename(Path(original).stem) or "llamada"
            job_dir.mkdir(parents=True, exist_ok=True)
            target = job_dir / f"{stem}{suffix}"
            upload.save(target)
            if target.stat().st_size == 0:
                raise ApiError("El archivo está vacío.")
            if suffix in TEXT_EXTENSIONS:
                _validate_text_file(target)
                mode = "transcript_only"
            else:
                mode = "audio"
            source = original
        elif text:
            if len(text) > MAX_TEXT_CHARS:
                raise ApiError(f"La transcripción supera {MAX_TEXT_CHARS} caracteres.")
            job_dir.mkdir(parents=True, exist_ok=True)
            target = job_dir / "transcripcion_capturada.txt"
            target.write_text(text, encoding="utf-8")
            mode = "transcript_only"
            source = target.name
        else:
            raise ApiError("Adjunte un archivo de audio o .txt, o escriba la transcripción.")

        job = analysis.submit(
            mode=mode, input_path=target, source_name=source, language=language, model=model
        )
        return jsonify(analysis.get(job.id)), 202

    @app.get("/api/jobs")
    def list_jobs() -> Any:
        return jsonify({"items": analysis.recent()})

    @app.get("/api/jobs/<job_id>")
    def get_job(job_id: str) -> Any:
        job = analysis.get(job_id)
        if job is None:
            raise ApiError(
                "El trabajo no existe (es posible que el servidor se haya reiniciado).",
                404,
                "no_encontrado",
            )
        return jsonify(job)

    # -- errores ----------------------------------------------------------
    @app.errorhandler(ApiError)
    def handle_api_error(exc: ApiError) -> Any:
        return jsonify({"error": exc.message, "code": exc.code}), exc.status

    @app.errorhandler(RequestEntityTooLarge)
    def handle_too_large(_exc: RequestEntityTooLarge) -> Any:
        return (
            jsonify(
                {
                    "error": f"El archivo supera el límite de {MAX_UPLOAD_MB} MB.",
                    "code": "archivo_demasiado_grande",
                }
            ),
            413,
        )

    @app.errorhandler(HTTPException)
    def handle_http(exc: HTTPException) -> Any:
        if request.path.startswith("/api/"):
            return jsonify({"error": exc.description, "code": exc.name}), exc.code
        return exc

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception) -> Any:
        app.logger.exception("Error no controlado")
        return (
            jsonify({"error": f"Error interno del servidor: {exc}", "code": "error_interno"}),
            500,
        )

    return app


def _validate_text_file(path: Path) -> None:
    try:
        content = path.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ApiError("La transcripción .txt debe estar codificada en UTF-8.") from exc
    if not content:
        raise ApiError("La transcripción .txt no contiene texto.")


def _short_token() -> str:
    import uuid

    return uuid.uuid4().hex[:6]
