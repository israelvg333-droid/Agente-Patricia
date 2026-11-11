from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any


def build_result_payload(
    transcript: dict[str, Any],
    acoustic_features: dict[str, Any],
    semantic_analysis: dict[str, Any],
    intent_analysis: dict[str, Any],
    coherence_analysis: dict[str, Any],
    score: dict[str, Any],
    input_metadata: dict[str, Any],
) -> dict[str, Any]:
    return {
        # 1.0 = esquema original sin versionar; 1.1 agrega jitter/shimmer, forma
        # espectral, voice_tremor_score y este mismo campo (cambios aditivos).
        "schema_version": "1.1",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input": input_metadata,
        "transcription": transcript,
        "acoustic_features": acoustic_features,
        "semantic_analysis": semantic_analysis,
        "intent_analysis": intent_analysis,
        "coherence_analysis": coherence_analysis,
        "score": score,
        "recommendation": score.get("recommendation"),
        "evidence": score.get("evidence", []),
    }


def save_result(payload: dict[str, Any], output_dir: str | Path) -> Path:
    path = Path(output_dir)
    path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = path / f"resultado_{timestamp}.json"
    # Dos analisis dentro del mismo segundo generaban el mismo nombre y el
    # segundo sobrescribia al primero; se agrega un sufijo incremental.
    suffix = 2
    while output_path.exists():
        output_path = path / f"resultado_{timestamp}_{suffix}.json"
        suffix += 1
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return output_path
