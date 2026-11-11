# Cambios multimodales recientes

## Cambios de codigo

- `main.py`
  - Agrega `--model tiny|base|small`.
  - Pasa el modelo seleccionado a Whisper local.

- `src/asr/transcriber.py`
  - Permite seleccionar modelo de Whisper.
  - Reporta el modelo usado en la transcripcion.

- `src/audio/preprocessing.py`
  - Mantiene compatibilidad con `.wav`, `.mp3` y `.m4a`.
  - Agrega manejo de error cuando `librosa` no puede decodificar el audio.
  - Conserva la amplitud relativa para que energia, clipping y calidad sean mas utiles.

- `src/audio/acoustic_features.py`
  - Extrae duracion, RMS, energia promedio, energia maxima, desviacion de energia, pico, ZCR, tempo, silencios, pausas, F0, clipping, SNR y calidad aproximada.
  - Agrega `acoustic_anomaly_flags` para alimentar la fusion multimodal.

- `src/scoring/seriousness_scorer.py`
  - Combina senales semanticas, completitud, coherencia y rasgos acusticos.
  - Agrega evidencia acustica explicable.
  - Ajusta confianza cuando hay mala calidad o anomalias acusticas.

- `src/scoring/decision_policy.py`
  - Si la confianza es baja, recomienda `pedir_mas_informacion`.
  - Si hay baja completitud, baja coherencia y anomalias acusticas, puede recomendar `posible_improcedente`.
  - Mantiene prioridad de seguridad para terminos criticos con `escalar_humano`.

## Resultado esperado

Cada ejecucion con audio genera un JSON en `data/outputs/` con:

- `transcription`
- `acoustic_features`
- `semantic_analysis`
- `intent_analysis`
- `coherence_analysis`
- `score`
- `recommendation`
- `evidence`

## Limites

Las nuevas features son heuristicas acusticas, no un modelo entrenado. Deben calibrarse con datos etiquetados antes de usarse en decisiones reales.
