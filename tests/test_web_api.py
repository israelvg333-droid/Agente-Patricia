"""Pruebas de la interfaz grafica: API Flask + cola de analisis.

Ejecutan el pipeline real (`main.analyze_call`). En modo audio se sustituye
solo Whisper y la decodificacion del archivo (dependencias externas pesadas);
features, indicadores, scoring, politica y guardado se ejecutan sin dobles.
"""
from __future__ import annotations

import argparse
import io
import json
import time

import numpy as np
import pytest

flask = pytest.importorskip("flask")

import main as main_module  # noqa: E402
from src.report.implementation_report import save_result  # noqa: E402
from src.scoring.category_mapper import VALID_CATEGORIES  # noqa: E402
from src.web.server import create_app  # noqa: E402
from src.web.service import ImportProbe, probe_import  # noqa: E402

EMERGENCY_TEXT = (
    "Necesito una ambulancia, mi esposo se desmayo y no respira, "
    "estamos en la calle Hidalgo 123."
)


@pytest.fixture()
def client(tmp_path):
    app = create_app(output_dir=tmp_path / "out", upload_dir=tmp_path / "up")
    app.config["TESTING"] = True
    return app.test_client()


def _wait(client, job_id, timeout=20.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = client.get(f"/api/jobs/{job_id}").get_json()
        if job["status"] in ("completado", "error"):
            return job
        time.sleep(0.05)
    raise AssertionError("El trabajo no termino a tiempo")


class TestAnalyze:
    def test_text_input_runs_full_pipeline(self, client):
        resp = client.post("/api/analyze", data={"text": EMERGENCY_TEXT})
        assert resp.status_code == 202
        job = _wait(client, resp.get_json()["id"])

        assert job["status"] == "completado"
        assert job["completed_stages"] == job["stages"]
        detail = client.get(f"/api/analyses/{job['result_id']}").get_json()
        assert detail["category"]["categoria"] in VALID_CATEGORIES
        assert detail["payload"]["input"]["mode"] == "transcript_only"
        assert detail["payload"]["transcription"]["text"] == EMERGENCY_TEXT
        assert detail["payload"]["score"]["recommendation"]

    def test_txt_upload(self, client):
        data = {"file": (io.BytesIO(EMERGENCY_TEXT.encode("utf-8")), "llamada.txt")}
        resp = client.post("/api/analyze", data=data, content_type="multipart/form-data")
        assert resp.status_code == 202
        job = _wait(client, resp.get_json()["id"])
        assert job["status"] == "completado"
        assert job["source_name"] == "llamada.txt"

    def test_audio_upload_uses_acoustic_pipeline(self, client, monkeypatch):
        sample_rate = 16000
        t = np.linspace(0, 2.0, sample_rate * 2, endpoint=False)
        audio = (0.4 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
        monkeypatch.setattr(main_module, "load_audio", lambda *_a, **_k: (audio, sample_rate))
        monkeypatch.setattr(
            main_module,
            "transcribe_audio",
            lambda *_a, **_k: {"text": EMERGENCY_TEXT, "engine": "stub", "status": "ok"},
        )
        data = {"file": (io.BytesIO(b"RIFF0000WAVE"), "llamada.wav"), "model": "base"}
        resp = client.post("/api/analyze", data=data, content_type="multipart/form-data")
        job = _wait(client, resp.get_json()["id"])

        assert job["status"] == "completado", job["error"]
        payload = client.get(f"/api/analyses/{job['result_id']}").get_json()["payload"]
        assert payload["input"]["mode"] == "audio"
        assert payload["acoustic_features"]["duration_seconds"] == pytest.approx(2.0)
        assert payload["acoustic_features"]["emergency_audio_indicators"]

    def test_pipeline_failure_reported_as_job_error(self, client, monkeypatch):
        def boom(*_args, **_kwargs):
            raise RuntimeError("fallo simulado del scoring")

        monkeypatch.setattr(main_module, "score_call", boom)
        resp = client.post("/api/analyze", data={"text": EMERGENCY_TEXT})
        job = _wait(client, resp.get_json()["id"])
        assert job["status"] == "error"
        assert "fallo simulado" in job["error"]
        assert job["stage"] == "puntuacion"
        # El worker sigue vivo para el siguiente analisis.
        monkeypatch.undo()
        resp = client.post("/api/analyze", data={"text": EMERGENCY_TEXT})
        assert _wait(client, resp.get_json()["id"])["status"] == "completado"

    @pytest.mark.parametrize(
        ("data", "fragment"),
        [
            ({}, "Adjunte un archivo"),
            ({"file": (io.BytesIO(b"x"), "virus.exe")}, "Formato no soportado"),
            ({"file": (io.BytesIO(b""), "vacio.wav")}, "vac"),
            ({"file": (io.BytesIO(b"   "), "vacio.txt")}, "no contiene texto"),
            ({"file": (io.BytesIO(b"\xff\xfe\x00a"), "latin.txt")}, "UTF-8"),
            ({"text": "hola", "model": "large"}, "Modelo de Whisper"),
            ({"text": "hola", "language": "fr"}, "Idioma"),
        ],
    )
    def test_invalid_requests(self, client, data, fragment):
        resp = client.post("/api/analyze", data=data, content_type="multipart/form-data")
        assert resp.status_code == 400
        assert fragment in resp.get_json()["error"]

    def test_unknown_job(self, client):
        assert client.get("/api/jobs/noexiste").status_code == 404


class TestHistory:
    def test_history_and_stats_reflect_saved_results(self, client):
        for text in (EMERGENCY_TEXT, "jaja era broma xd"):
            job_id = client.post("/api/analyze", data={"text": text}).get_json()["id"]
            assert _wait(client, job_id)["status"] == "completado"

        items = client.get("/api/analyses").get_json()["items"]
        assert len(items) == 2
        stats = client.get("/api/stats").get_json()
        assert stats["total"] == 2
        assert sum(stats["categorias"].values()) == 2
        assert sum(stats["recomendaciones"].values()) == 2
        assert sum(sum(d[c] for c in VALID_CATEGORIES) for d in stats["tendencia"]) == 2

    def test_cli_results_appear_in_history(self, client, tmp_path):
        transcript = tmp_path / "cli.txt"
        transcript.write_text(EMERGENCY_TEXT, encoding="utf-8")
        args = argparse.Namespace(
            audio=None,
            transcript=str(transcript),
            output_dir=str(tmp_path / "out"),
            language="es",
            model="tiny",
        )
        main_module.run_pipeline(args)
        items = client.get("/api/analyses").get_json()["items"]
        assert [i["source"] for i in items] == ["cli.txt"]

    @pytest.mark.parametrize("bad_id", ["resultado_999", "..%2Fetc", "otro_archivo"])
    def test_missing_or_invalid_ids(self, client, bad_id):
        assert client.get(f"/api/analyses/{bad_id}").status_code == 404

    def test_status_reports_components(self, client):
        status = client.get("/api/status").get_json()
        assert status["estado"] in {"operativo", "degradado", "verificando", "fuera_de_servicio"}
        assert status["python"]["ejecutable"]
        ids = {c["id"] for c in status["componentes"]}
        assert {"librosa", "whisper", "ffmpeg", "output_dir"} <= ids
        assert status["worker"]["alive"] is True

    def test_index_served(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"EVA" in resp.data


def test_save_result_does_not_overwrite_same_second(tmp_path):
    first = save_result({"n": 1}, tmp_path)
    second = save_result({"n": 2}, tmp_path)
    assert first != second
    assert json.loads(first.read_text(encoding="utf-8"))["n"] == 1
    assert json.loads(second.read_text(encoding="utf-8"))["n"] == 2


class TestDependencyProbe:
    def test_importable_module(self):
        assert probe_import("json") == (True, None)

    def test_missing_module_reports_reason(self):
        ok, detail = probe_import("modulo_que_no_existe_eva")
        assert ok is False
        assert "no está instalado" in detail

    def test_broken_module_reports_import_error(self, tmp_path, monkeypatch):
        (tmp_path / "paquete_roto_eva.py").write_text("import dependencia_ausente_eva\n")
        monkeypatch.syspath_prepend(str(tmp_path))
        monkeypatch.setenv("PYTHONPATH", str(tmp_path))
        ok, detail = probe_import("paquete_roto_eva")
        assert ok is False
        assert "dependencia_ausente_eva" in detail

    def test_probe_runs_in_background(self):
        probe = ImportProbe(("json",))
        assert probe.result("json")["ok"] in (None, True)
        deadline = time.time() + 10
        while probe.result("json")["ok"] is None and time.time() < deadline:
            time.sleep(0.05)
        assert probe.result("json") == {"ok": True, "detalle": None}
