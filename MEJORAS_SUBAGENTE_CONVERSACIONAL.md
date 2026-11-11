# MEJORAS_SUBAGENTE_CONVERSACIONAL

> Documento vivo. Primera version: 2026-07-02 (reorientacion audio-first). Ultima actualizacion: 2026-07-14. El historial detallado por sesion esta en `MEJORAS_PROYECTO.md`.

## Resumen ejecutivo

Se reoriento el proyecto hacia un enfoque audio-first para estimar la seriedad de llamadas de emergencia. La transcripcion sigue disponible, pero ahora opera como fuente complementaria. La mejora principal fue agregar una capa explicable de indicadores acusticos de emergencia sobre las features ya existentes: stress vocal, urgencia, nerviosismo, desesperacion, calma, agresividad acustica, inestabilidad vocal, confiabilidad del audio y un `seriousness_audio_score`.

Tambien se centralizaron parametros acusticos, se conecto la nueva inferencia al scoring, se ajusto la politica de decision para priorizar casos con audio compatible con crisis y se agregaron pruebas unitarias.

Desde entonces el sistema se ha validado y evolucionado con datos reales:

- **2026-07-07**: helpers compartidos (`clamp01`, `optional_float`), eliminacion de duplicacion en 3 modulos.
- **2026-07-08**: procesamiento batch del dataset 911 real (316 audios: 280 SERIA / 35 DUDOSA / 0 IMPROCEDENTE), deteccion automatica de transcripciones alucinadas por Whisper (`transcript_quality.py`) con recalibracion de confianza, parametros anti-alucinacion en el ASR y conexion completa de `AudioAnalysisConfig` al pipeline.
- **2026-07-14**: nuevas features de estabilidad vocal (jitter y shimmer aproximados — temblor de la voz), forma espectral (rolloff, ancho de banda, flatness), indicador `voice_tremor_score` calibrado contra la distribucion real del dataset 911, tests de integracion end-to-end, linter `ruff` configurado y JSON de salida versionado (`schema_version: "1.1"`).

Estado actual: **187 tests pasando, `ruff check` limpio, pipeline verificado end-to-end con audio sintetico y llamadas 911 reales.**

## Actualizacion 2026-07-14 — Estabilidad vocal, integracion y calidad de software

### Nuevas caracteristicas acusticas

- `estimated_jitter_ratio`: perturbacion relativa media de F0 entre tramas vocales consecutivas (serie de `librosa.yin` con mascara 70-600 Hz). Aproximacion al jitter clasico; proxy del temblor de la voz (item 13 de las prioridades del proyecto).
- `estimated_shimmer_ratio`: perturbacion relativa media de amplitud RMS entre tramas activas consecutivas (excluye transiciones habla-pausa).
- `spectral_rolloff_hz`, `spectral_bandwidth_hz`, `spectral_flatness`: forma espectral con una unica STFT compartida. Rolloff y ancho de banda complementan al centroide para caracterizar gritos y voz tensa; la flatness detecta espectro tipo ruido (calidad vocal degradada o canal ruidoso).

### Nuevo indicador: `voice_tremor_score`

- Combina jitter, shimmer y desviacion de F0; expone el flag `temblor_vocal_probable` (>= 0.65).
- **Calibrado con datos reales**: los umbrales de laboratorio saturaban en audio telefonico (jitter aproximado observado 0.12-0.45 en 10 llamadas 911, un orden de magnitud mayor que el jitter ciclo a ciclo clasico). Con los umbrales recalibrados el indicador discrimina (0.22-0.84 en la muestra).
- **Decision de diseno**: es informativo y NO participa aun en `seriousness_audio_score`, para preservar la comparabilidad con las 315 llamadas ya clasificadas; se integrara con pesos derivados del etiquetado manual. Un test de regresion protege esta propiedad.

### Calidad de software

- `tests/test_integration.py`: primera cobertura end-to-end de `run_pipeline` (modo transcript-only sin mocks; modo audio con `.wav` sintetico de 220 Hz con vibrato y pausa, solo el ASR simulado). Suite total: 187 tests.
- `pyproject.toml` con `ruff` (reglas E, F, W, I, UP, B): 27 hallazgos auto-corregidos y 9 lineas largas reescritas; el linter queda limpio.
- `schema_version: "1.1"` en el JSON de salida: los cambios aditivos quedan versionados; la limpieza de claves duplicadas del nivel raiz se hara como esquema 2.0.

### Validacion de esta actualizacion

- 187 tests pasando (169 previos + 18 nuevos, 0 regresiones).
- `ruff check .` sin hallazgos.
- Smoke test CLI (`--transcript`) identico al historico: `escalar_humano`, score 0.9.
- Features nuevas verificadas sobre 10 llamadas reales del dataset 911 sin errores y con valores en rangos plausibles.

## Problemas encontrados

- El enfoque seguia siendo parcialmente ASR-first: el texto y sus reglas semanticas tenian mas peso conceptual que la evidencia acustica.
- Las features acusticas existian, pero no habia una capa de inferencia que tradujera prosodia, energia, pausas y F0 a indicadores utiles para emergencia.
- La politica de decision podia penalizar llamadas incompletas o poco coherentes aun cuando el audio sugiriera alta activacion o urgencia.
- La configuracion de umbrales acusticos estaba dispersa en funciones y constantes.
- La transcripcion manual enriquecia WPM, pero no existia una representacion explicita de confiabilidad del audio.
- No habia pruebas para indicadores de stress/urgencia/nerviosismo.
- El proyecto contiene artefactos generados (`__pycache__`, outputs, caches) y cambios previos sin commit. No se eliminaron para evitar tocar trabajo ajeno.
- Las probabilidades siguen siendo heuristicas sin calibracion estadistica ni validacion con dataset real.

## Cambios implementados

- Se agrego `src/audio/emergency_indicators.py`.
  - Calcula `stress_vocal_score`, `urgency_score`, `nervousness_score`, `desperation_score`, `calm_score`, `aggression_score`, `voice_instability_score`, `audio_reliability` y `seriousness_audio_score`.
  - Produce `indicator_flags` explicables como `stress_vocal_alto`, `urgencia_acustica_alta`, `desesperacion_probable`, `voz_inestable` y `baja_confiabilidad_audio`.

- Se actualizo `src/audio/acoustic_features.py`.
  - Integra `emergency_audio_indicators` dentro de `acoustic_features`.
  - Recalcula indicadores tras estimar `approx_speech_rate` desde transcripcion, porque la velocidad de habla aporta al score acustico.
  - Mantiene compatibilidad con los campos existentes.

- Se actualizo `src/utils/config.py`.
  - Agrega `AudioAnalysisConfig` para concentrar umbrales de F0, habla rapida/lenta, silencio, pausas, SNR y clipping.

- Se actualizo `src/scoring/seriousness_scorer.py`.
  - Da peso explicito al `seriousness_audio_score`.
  - Agrega `audio_priority` al resultado final.
  - Incorpora evidencia acustica explicable al arreglo `evidence`.
  - Ajusta confianza usando `audio_reliability`.

- Se actualizo `src/scoring/decision_policy.py`.
  - Escala a humano si el audio muestra crisis fuerte con confiabilidad suficiente.
  - Evita clasificar como improcedente una llamada incompleta cuando el audio tiene evidencia clara de stress/urgencia.

- Se actualizo `main.py`.
  - Pasa la configuracion acustica al extractor.

- Se agregaron pruebas.
  - `tests/test_emergency_indicators.py`
  - Nuevos casos en `tests/test_decision_policy.py`
  - Actualizacion de `tests/test_acoustic_features.py`

- Se actualizo `README.md`.
  - Documenta el enfoque audio-first y los nuevos indicadores.

## Justificacion

La investigacion en Speech Emotion Recognition y paralinguistica muestra que las senales acusticas no verbales aportan informacion distinta a la transcripcion: prosodia, energia, F0, pausas, ritmo y calidad vocal. Por eso el proyecto necesitaba una capa intermedia que no solo extraiga features, sino que las convierta en indicadores de emergencia.

Se evaluaron alternativas modernas:

- openSMILE/eGeMAPS: es una opcion fuerte para SER porque ofrece feature sets estandarizados. La documentacion oficial de openSMILE Python reporta soporte para ComParE 2016, GeMAPS y eGeMAPS, incluyendo eGeMAPSv02 con 88 functionals. No se agrego como dependencia inmediata porque el proyecto ya usa `librosa`, busca mantenerse liviano y openSMILE tiene consideraciones de licencia para uso comercial. Referencia: https://audeering.github.io/opensmile-python/
- wav2vec 2.0, HuBERT y WavLM: son buenos candidatos para embeddings acusticos aprendidos. Trabajos como benchmarks con wav2vec 2.0/HuBERT en SER reportan buen rendimiento en IEMOCAP, pero requieren dataset etiquetado, mas memoria y una estrategia de fine-tuning o extraccion de embeddings. Referencia: https://arxiv.org/abs/2111.02735
- SpeechBrain: es una opcion viable para modelos preentrenados y fine-tuning, pero incorporarla ahora aumentaria dependencias y complejidad sin dataset local calibrado. Referencia: https://speechbrain.readthedocs.io/
- Whisper: se conserva solo como apoyo textual. No es el eje del sistema porque ASR pierde informacion prosodica y puede fallar con ruido, multiples hablantes o alta carga emocional.

La implementacion actual prioriza mantenibilidad: features acusticas interpretables, indicadores auditables, pruebas unitarias y una ruta clara hacia modelos supervisados cuando exista dataset.

## Nueva arquitectura

```text
Audio opcional / transcripcion opcional
    |
    v
Preprocesamiento de audio
    - validacion de formato
    - carga mono 16 kHz
    - normalizacion numerica
    |
    v
Extraccion acustica
    - energia RMS y energia por trama
    - F0, rango y variabilidad
    - MFCCs
    - centroide espectral
    - ZCR
    - pausas y proporcion de silencio
    - SNR, clipping y calidad
    |
    v
Indicadores acusticos de emergencia
    - stress vocal
    - urgencia
    - nerviosismo
    - desesperacion
    - calma
    - agresividad acustica
    - inestabilidad vocal
    - confiabilidad del audio
    |
    +-----------------------------+
    |                             |
    v                             v
Scoring audio-first          Analisis textual de apoyo
                              - palabras clave
                              - intencion
                              - coherencia
                              - completitud
    |                             |
    +-------------+---------------+
                  |
                  v
          Politica de decision
                  |
                  v
  continuar / pedir_mas_informacion / escalar_humano / posible_improcedente
```

## Mejoras enfocadas en el analisis de audio

Caracteristicas utilizadas:

- Energia RMS global y por trama.
- Variabilidad de energia.
- Pico de amplitud.
- Zero Crossing Rate.
- F0 medio, minimo, maximo y desviacion.
- Rango de pitch.
- MFCCs.
- Centroide espectral.
- Rolloff, ancho de banda y flatness espectrales (2026-07-14).
- Jitter y shimmer aproximados (2026-07-14).
- Proporcion de silencio.
- Conteo y duracion de pausas.
- Velocidad aproximada de habla.
- SNR aproximado.
- Clipping.
- Calidad de audio.

Nuevos indicadores:

- `stress_vocal_score`: variabilidad de energia, F0, rango tonal, habla rapida e intensidad.
- `urgency_score`: habla rapida, energia alta y baja proporcion de silencio.
- `nervousness_score`: F0 variable, energia variable, pausas y ZCR.
- `desperation_score`: combinacion de stress, urgencia y F0 elevado/variable.
- `calm_score`: baja activacion, habla moderada y silencios no extremos.
- `aggression_score`: intensidad, centroide espectral y ZCR elevados.
- `voice_instability_score`: variacion de F0 y energia.
- `voice_tremor_score` (2026-07-14): temblor vocal desde jitter/shimmer aproximados; informativo, pendiente de integrarse al score primario tras calibracion con etiquetas.
- `audio_reliability`: penaliza mala calidad, SNR bajo, clipping y silencio excesivo.
- `seriousness_audio_score`: score acustico primario para fusion.

Cambios en inferencia:

- El score final ahora incorpora primero `seriousness_audio_score` cuando existe audio.
- Si el audio muestra indicadores fuertes de crisis y confiabilidad suficiente, la politica recomienda `escalar_humano`.
- Si el texto es incompleto pero el audio sugiere urgencia, la politica prefiere `pedir_mas_informacion` antes que marcar improcedencia.
- La evidencia incluye explicaciones acusticas legibles.

## Fortalezas actuales

- Arquitectura modular por dominio: audio, ASR, semantica, scoring, reportes y utils.
- Dependencias ligeras y ejecutables localmente.
- Politica conservadora: no recomienda colgar ni cerrar automaticamente.
- Tests existentes para VAD, preprocesamiento, scoring, coherencia, texto y features.
- Salida JSON estructurada para integracion con agente principal.
- Manejo razonable de errores cuando Whisper o decodificacion de audio fallan.

## Debilidades actuales

- No existe dataset etiquetado de llamadas reales o simuladas con criterios consistentes.
- No hay calibracion probabilistica.
- No hay modelo supervisado entrenado para seriedad, stress o urgencia.
- La estimacion de F0 puede fallar en ruido, musica, multiples voces o audio telefonico degradado.
- La velocidad de habla depende de transcripcion si no hay segmentacion fonetica o VAD mas fino.
- No hay evaluacion objetiva con precision, recall, F1, AUROC, AUPRC o Brier Score.
- No hay separacion por segmentos temporales; el sistema resume toda la llamada.
- No hay explicabilidad cuantitativa tipo SHAP/LIME ni analisis de error por subgrupos.

## Mejoras futuras priorizadas

> Actualizado 2026-07-14. Los items ya completados se marcaron; el detalle vivo esta en el Roadmap de `MEJORAS_PROYECTO.md`.

1. **Etiquetado manual estratificado del dataset 911** (35 DUDOSAS + 15 SERIAS como minimo) — es el desbloqueador de todo lo demas: metricas reales, calibracion de umbrales y pesos, e integracion de `voice_tremor_score` al score primario. *(El dataset ya esta procesado: 315 llamadas clasificadas con scores y features.)*
2. Definir protocolo de anotacion y acuerdo interanotador.
3. Agregar evaluacion objetiva: recall para llamadas serias como metrica principal, matriz de confusion, F1 macro, AUROC, AUPRC y calibracion.
4. Reprocesar los 11 audios con transcripcion sospechosa usando Whisper `base` + parametros anti-alucinacion; hacer backfill acustico del checkpoint para incorporar las features de 2026-07-14 (jitter, shimmer, forma espectral, temblor).
5. Corregir el sesgo del token "911"/digitos sueltos en `text_analyzer.py` (DT-11; requiere decision de negocio porque cambia el scoring del historico).
6. Entrenar baseline supervisado interpretable con Logistic Regression, Random Forest o XGBoost sobre features acusticas.
7. Incorporar openSMILE/eGeMAPS como extractor opcional para comparar contra features `librosa`; `parselmouth` para jitter/shimmer ciclo a ciclo exactos.
8. Agregar segmentacion temporal para estimar curvas de stress/urgencia por ventana.
9. Probar embeddings wav2vec 2.0, HuBERT o WavLM como features congeladas.
10. Evaluar SpeechBrain o modelos SER preentrenados cuando haya datos y hardware adecuados.
11. Implementar fusion multimodal calibrada: audio como rama primaria y texto como rama auxiliar.
12. Agregar explainability: contribucion por indicador, importancias de variables y reportes de error.
13. Agregar interfaz de inspeccion (Streamlit) con graficas de energia, F0, pausas y score temporal.
14. Evaluar robustez por ruido, acento, edad, genero, discapacidad del habla y canal telefonico.
15. Preparar API estable para integracion con el sistema multiagente; versionar esquema 2.0 del JSON (eliminar claves duplicadas del nivel raiz).
16. Agregar type checker (`mypy`/`pyright`) como siguiente paso de tooling. *(Linter `ruff` ya configurado; tests de integracion ya agregados; `schema_version` ya versionado.)*

## Riesgos

- Los scores actuales son heuristicas, no probabilidades calibradas.
- La activacion vocal no equivale automaticamente a emergencia: una persona puede sonar calmada en una emergencia real o alterada en una llamada no urgente.
- Los umbrales pueden sesgarse por acento, genero, edad, microfono, codec o ruido.
- El ASR puede introducir errores semanticos, especialmente con ruido o habla emocional.
- El audio telefonico real puede tener ancho de banda limitado y distorsiones que afecten F0, MFCCs y SNR.
- Existe riesgo operativo si se usa el sistema para descartar llamadas. Debe mantenerse como apoyo, no como decisor final.

## Recomendaciones

- Mantener la regla de seguridad: nunca cerrar llamadas automaticamente.
- Validar umbrales con audios reales anonimizados o simulaciones controladas antes de ajustar pesos.
- Priorizar recall de llamadas serias sobre precision de improcedencia.
- Registrar evidencia acustica y textual para auditoria.
- Separar pronto el dataset de pruebas de los outputs generados por ejecuciones locales.
- Convertir los indicadores actuales en baseline contra el cual comparar modelos supervisados.
- Adoptar openSMILE/eGeMAPS como extractor opcional en una rama experimental, no como dependencia obligatoria inmediata.
- Usar Whisper solo para enriquecer texto, no para reemplazar prosodia.

## Verificacion (historica, 2026-07-02)

> Estado actual (2026-07-14): 187 tests pasando. Ver "Actualizacion 2026-07-14" arriba.

Se ejecuto:

```powershell
python -m pytest tests/ -q --basetemp .tmp_pytest_run
```

Resultado:

```text
114 passed, 1 warning
```

La advertencia corresponde a permisos de `.pytest_cache`; por eso se uso `--basetemp` dentro del workspace. La ejecucion funcional de tests fue correcta.

## Prueba funcional con audio real

Archivo utilizado:

```text
C:\Users\dotis\Documents\Detecciones de comportamientos en agentes\Investigaciones\Metodologia\subagente_seriedad\data\audios\Prueba llamada.mp3
```

Fecha de la prueba: 2026-07-02.

Flujo ejecutado:

1. Localizacion automatica del archivo `Prueba llamada.*`.
2. Validacion de dependencias acusticas en `.venv`.
3. Compilacion con `py_compile`.
4. Ejecucion de tests unitarios.
5. Ejecucion completa del pipeline con `main.py --audio`.
6. Revision del JSON generado.
7. Ajuste de scoring por incoherencia detectada.
8. Reejecucion de tests y pipeline completo.

Resultado obtenido inicialmente:

- Archivo de salida: `data\outputs\resultado_20260702_112946.json`.
- `seriousness_score`: `0.655`.
- `improcedence_score`: `0.25`.
- `confidence`: `0.787`.
- Recomendacion: `pedir_mas_informacion`.
- Indicadores acusticos principales: `seriousness_audio_score=0.453`, `audio_reliability=0.6`, `stress_vocal_score=0.583`, `urgency_score=0.219`, `nervousness_score=0.738`.

Problemas encontrados:

- La transcripcion automatica con Whisper fue ruidosa y mezclo frases de una conversacion transaccional, sin terminos claros de emergencia.
- El scoring elevaba demasiado la seriedad porque aceptaba falsos positivos semanticos de ubicacion/personas y completitud aunque no hubiera incidente ni emergencia textual.
- Se observaron advertencias esperadas de Whisper en CPU: `FP16 is not supported on CPU; using FP32 instead`.
- Pytest reporto una advertencia de permisos al intentar escribir cache en `.pytest_cache`; no afecto la ejecucion de pruebas.

Soluciones aplicadas:

- Se ajusto `src/scoring/seriousness_scorer.py` para que ubicacion, completitud y coherencia solo eleven la seriedad cuando exista incidente/emergencia textual o urgencia acustica confiable (`seriousness_audio_score >= 0.55` y `audio_reliability >= 0.45`).
- Se agrego una prueba de regresion en `tests/test_scoring.py` para evitar que texto largo no emergente infle el score de seriedad.
- Se mantuvo la politica conservadora: el sistema no cierra ni descarta automaticamente la llamada.

Resultado final:

- Archivo de salida final: `data\outputs\resultado_20260702_113627.json`.
- `seriousness_score`: `0.389`.
- `improcedence_score`: `0.25`.
- `confidence`: `0.787`.
- Recomendacion: `pedir_mas_informacion`.
- Transcripcion: `status=ok`, usada solo como apoyo.
- Audio: cargado y procesado correctamente.
- Duracion: `670.752` segundos.
- Calidad de audio: `posible_saturacion`.
- SNR estimado: `57.452 dB`.
- Proporcion de silencio: `0.641473`.
- Pausas detectadas: `300`.
- Pausa mas larga: `68.064` segundos.
- F0 medio estimado: `191.016 Hz`.
- Desviacion F0: `92.146 Hz`.
- Indicadores: `nerviosismo_alto`, `voz_inestable`.

Observaciones:

- El resultado final es mas coherente con el contenido detectado: no aparecen palabras de emergencia, incidente ni alto riesgo, y la conversacion parece transaccional o administrativa.
- El nivel de seriedad queda bajo-medio (`0.389`) por nerviosismo e inestabilidad vocal, pero no escala a emergencia porque la urgencia acustica es baja (`0.219`) y el texto no aporta incidente.
- La confianza es relativamente alta (`0.787`) porque hay audio largo, transcripcion disponible y features acusticas calculadas, aunque la calidad se marco como `posible_saturacion`.
- Limitaciones: Whisper genero texto ruidoso; la inferencia acustica sigue siendo heuristica; una llamada real puede ser seria aunque no contenga terminos de emergencia o aunque el hablante suene calmado.

Verificacion final realizada:

- Compilacion correcta con `py_compile`.
- Sin errores de sintaxis en los modulos principales.
- Sin importaciones rotas detectadas durante tests y ejecucion.
- Dependencias acusticas resueltas: `numpy`, `scipy`, `soundfile`, `librosa`.
- Whisper disponible y funcional en CPU, con advertencia esperada de FP16.
- Audio `Prueba llamada.mp3` procesado correctamente.
- Salida consistente con el enfoque audio-first: la transcripcion no domina la decision y solo complementa la inferencia acustica.

## Comandos para ejecutar manualmente

Desde PowerShell:

```powershell
cd "C:\Users\dotis\Documents\Detecciones de comportamientos en agentes\Investigaciones\Metodologia\subagente_seriedad"
```

Activar entorno virtual:

```powershell
.\.venv\Scripts\Activate.ps1
```

Instalar dependencias si fuera necesario:

```powershell
python -m pip install -r requirements.txt
python -m pip install openai-whisper
```

Variables de entorno recomendadas para consola Windows:

```powershell
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONWARNINGS = "default"
```

Localizar automaticamente el audio `Prueba llamada.*`:

```powershell
$AUDIO = (Get-ChildItem -Path "C:\Users\dotis\Documents\Detecciones de comportamientos en agentes\Investigaciones\Metodologia\subagente_seriedad\data\audios" -Filter "Prueba llamada.*" -File | Select-Object -First 1).FullName
$AUDIO
```

Comando para iniciar/ver ayuda del proyecto:

```powershell
python main.py --help
```

Comando para ejecutar el analisis completo del audio:

```powershell
python main.py --audio "$AUDIO" --model tiny --language es
```

Comando para ejecutar el analisis completo guardando log de consola:

```powershell
python main.py --audio "$AUDIO" --model tiny --language es 2>&1 | Tee-Object -FilePath "C:\Users\dotis\Documents\Detecciones de comportamientos en agentes\Investigaciones\Metodologia\subagente_seriedad\data\outputs\prueba_funcional_20260702.log"
```

Comando para ejecutar unicamente la inferencia desde un JSON ya generado:

```powershell
$env:RESULT_JSON = "C:\Users\dotis\Documents\Detecciones de comportamientos en agentes\Investigaciones\Metodologia\subagente_seriedad\data\outputs\resultado_20260702_113627.json"
python -c "import json, os; from pathlib import Path; from src.scoring.seriousness_scorer import score_call; d=json.loads(Path(os.environ['RESULT_JSON']).read_text(encoding='utf-8')); print(json.dumps(score_call(d['acoustic_features'], d['semantic_analysis'], d['intent_analysis'], d['coherence_analysis']), ensure_ascii=False, indent=2))"
```

Comando para visualizar resultados:

```powershell
$env:RESULT_JSON = "C:\Users\dotis\Documents\Detecciones de comportamientos en agentes\Investigaciones\Metodologia\subagente_seriedad\data\outputs\resultado_20260702_113627.json"
python -m json.tool "$env:RESULT_JSON"
```

Comando para ejecutar pruebas:

```powershell
python -m pytest tests/ -q --basetemp .tmp_pytest_run
```

Comando para revisar logs capturados:

```powershell
Get-Content -Path "C:\Users\dotis\Documents\Detecciones de comportamientos en agentes\Investigaciones\Metodologia\subagente_seriedad\data\outputs\prueba_funcional_20260702.log" -Encoding UTF8
```

Comando de depuracion:

```powershell
$env:PYTHONFAULTHANDLER = "1"
$env:PYTHONWARNINGS = "default"
python main.py --audio "$AUDIO" --model tiny --language es
```

Comando para verificar sintaxis/importaciones principales:

```powershell
python -m py_compile main.py src\audio\preprocessing.py src\audio\acoustic_features.py src\audio\emergency_indicators.py src\audio\vad.py src\asr\transcriber.py src\semantic\text_analyzer.py src\semantic\intent_analyzer.py src\semantic\coherence_analyzer.py src\scoring\seriousness_scorer.py src\scoring\decision_policy.py src\report\implementation_report.py src\utils\config.py src\utils\logger.py
```
