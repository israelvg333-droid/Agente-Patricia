from __future__ import annotations

import argparse
import csv
import os
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".aac", ".wma"}
MAX_DURATION_SECONDS = 300.0
os.environ.setdefault("NUMBA_CACHE_DIR", str(Path.cwd() / ".numba_cache"))


@dataclass
class AudioResult:
    archivo: str
    ruta_original: Path
    duracion_segundos: float | None
    duracion_mmss: str
    accion: str
    error: str | None = None


def find_project_root(script_path: Path) -> Path:
    """Resolve project root from data/audios/911_recordings/script.py."""
    return script_path.resolve().parents[3]


def iter_audio_files(audio_root: Path) -> list[Path]:
    return sorted(
        path
        for path in audio_root.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    )


def get_audio_duration(path: Path) -> float:
    errors: list[str] = []
    try:
        import soundfile as sf

        info = sf.info(str(path))
        if info.duration and info.duration > 0:
            return float(info.duration)
    except Exception as exc:
        errors.append(f"soundfile: {exc!r}")

    try:
        import librosa

        duration = librosa.get_duration(path=str(path))
        if duration and duration > 0:
            return float(duration)
    except Exception as exc:
        errors.append(f"librosa: {exc!r}")
        details = "; ".join(errors) if errors else repr(exc)
        raise RuntimeError(f"No se pudo obtener duracion: {details}") from exc

    details = "; ".join(errors) if errors else "sin detalles del decodificador"
    raise RuntimeError(f"No se pudo obtener una duracion valida: {details}")


def format_mmss(seconds: float | None) -> str:
    if seconds is None:
        return ""
    rounded = int(round(seconds))
    minutes, secs = divmod(rounded, 60)
    return f"{minutes:02d}:{secs:02d}"


def unique_destination(destination_dir: Path, filename: str) -> Path:
    candidate = destination_dir / filename
    if not candidate.exists():
        return candidate

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        candidate = destination_dir / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def process_audio_file(path: Path, destination_dir: Path) -> AudioResult:
    try:
        duration = get_audio_duration(path)
    except Exception as exc:
        return AudioResult(
            archivo=path.name,
            ruta_original=path,
            duracion_segundos=None,
            duracion_mmss="",
            accion="Conservado",
            error=str(exc),
        )

    if duration > MAX_DURATION_SECONDS:
        destination = unique_destination(destination_dir, path.name)
        shutil.move(str(path), str(destination))
        action = "Movido (>5 minutos)"
    else:
        action = "Conservado"

    return AudioResult(
        archivo=path.name,
        ruta_original=path,
        duracion_segundos=duration,
        duracion_mmss=format_mmss(duration),
        accion=action,
    )


def write_csv(results: list[AudioResult], csv_path: Path) -> None:
    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=[
                "archivo",
                "ruta_original",
                "duracion_segundos",
                "duracion_mmss",
                "accion",
            ],
        )
        writer.writeheader()
        for result in results:
            writer.writerow(
                {
                    "archivo": result.archivo,
                    "ruta_original": str(result.ruta_original),
                    "duracion_segundos": (
                        f"{result.duracion_segundos:.3f}"
                        if result.duracion_segundos is not None
                        else ""
                    ),
                    "duracion_mmss": result.duracion_mmss,
                    "accion": result.accion,
                }
            )


def write_markdown(
    results: list[AudioResult],
    markdown_path: Path,
    executed_at: datetime,
    total_duration: float,
) -> None:
    moved = [result for result in results if result.accion == "Movido (>5 minutos)"]
    kept = [result for result in results if result.accion == "Conservado"]
    errors = [result for result in results if result.error]

    lines = [
        "# Reporte de filtrado por duracion",
        "",
        f"Fecha y hora de ejecucion: {executed_at.strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"Total de audios encontrados: {len(results)}",
        f"Total de audios conservados: {len(kept)}",
        f"Total de audios movidos: {len(moved)}",
        f"Duracion total procesada: {format_mmss(total_duration)} ({total_duration:.3f} segundos)",
        "",
        "## Archivos movidos",
        "",
    ]

    if moved:
        lines.extend(["| nombre | duracion | ruta original |", "|---|---:|---|"])
        for result in moved:
            lines.append(
                f"| {result.archivo} | {result.duracion_mmss} | {result.ruta_original} |"
            )
    else:
        lines.append("No se movieron archivos.")

    if errors:
        lines.extend(["", "## Errores", ""])
        lines.extend(["| archivo | ruta original | error |", "|---|---|---|"])
        for result in errors:
            lines.append(f"| {result.archivo} | {result.ruta_original} | {result.error} |")

    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(audio_root: Path, destination_dir: Path, reports_dir: Path) -> tuple[list[AudioResult], float]:
    destination_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    audio_files = iter_audio_files(audio_root)
    results = [process_audio_file(path, destination_dir) for path in audio_files]
    total_duration = sum(
        result.duracion_segundos or 0.0 for result in results
    )

    executed_at = datetime.now()
    write_markdown(
        results,
        reports_dir / "reporte_filtrado_duracion.md",
        executed_at,
        total_duration,
    )
    write_csv(results, reports_dir / "reporte_filtrado_duracion.csv")
    return results, total_duration


def parse_args() -> argparse.Namespace:
    script_path = Path(__file__)
    project_root = find_project_root(script_path)
    parser = argparse.ArgumentParser(
        description="Filtra audios con duracion mayor a 5 minutos."
    )
    parser.add_argument(
        "--audio-root",
        type=Path,
        default=project_root / "data" / "audios" / "911_recordings",
    )
    parser.add_argument(
        "--destination-dir",
        type=Path,
        default=project_root / "data" / "audios_descartados",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=project_root / "reportes",
    )
    return parser.parse_args()


def main() -> None:
    os.environ.setdefault("NUMBA_CACHE_DIR", str(Path.cwd() / ".numba_cache"))
    args = parse_args()
    results, _ = run(args.audio_root, args.destination_dir, args.reports_dir)
    moved = sum(result.accion == "Movido (>5 minutos)" for result in results)
    kept = sum(result.accion == "Conservado" for result in results)

    print(f"Audios encontrados: {len(results)}")
    print()
    print(f"Conservados: {kept}")
    print()
    print(f"Movidos (>5 min): {moved}")
    print()
    print("Carpeta destino:")
    print("data/audios_descartados/")
    print()
    print("Reporte generado:")
    print("reportes/reporte_filtrado_duracion.md")
    print("reportes/reporte_filtrado_duracion.csv")


if __name__ == "__main__":
    main()
