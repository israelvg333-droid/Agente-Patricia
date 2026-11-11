# Anexos de evidencias técnicas

**Criterio de elaboración.** Este documento se generó mediante inspección del árbol de trabajo, código fuente, documentación, artefactos persistidos y repositorio Git presentes en el proyecto. Las cifras se identifican con su archivo de evidencia. No se ejecutaron procesos durante la auditoría; por tanto, los resultados de ejecución y pruebas que se consignan son los artefactos históricos disponibles.

# Anexo 1. Evidencias del desarrollo e implementación del prototipo

Este anexo presenta las evidencias técnicas del desarrollo del subagente conversacional de estimación de seriedad de llamadas, incluyendo la estructura del proyecto, las pruebas realizadas y ejemplos de la salida generada por el sistema durante su evaluación.

## 1. Árbol completo del proyecto

Árbol generado a partir del contenido actual. Se excluyeron `.git`, entornos virtuales, cachés, `__pycache__`, `node_modules` y directorios temporales. Para conservar una lectura útil del anexo, las colecciones masivas de archivos se representan por su patrón y cantidad, no por cada nombre individual; sus inventarios completos están en el sistema de archivos.

```text
subagente_seriedad/
├── .env.example
├── .gitignore
├── README.md
├── requirements.txt
├── pyproject.toml
├── main.py
├── procesar_dataset.py
├── eval_english_dataset.py
├── guiones_dataset_prueba.md
├── MEJORAS_PROYECTO.md
├── MEJORAS_SUBAGENTE_CONVERSACIONAL.md
├── RESUMEN_DATASET.md
├── clasificacion_dataset.csv
├── clasificacion_dataset.json
├── clasificacion_dataset.partial.jsonl
├── features_dataset.csv
├── errores_procesamiento.log
├── test_20.json
├── data/
│   ├── audios/
│   │   ├── ejemplo.txt
│   │   ├── test_broma.txt
│   │   ├── test_emergencia.txt
│   │   ├── Prueba llamada.mp3
│   │   ├── 911_recordings/
│   │   │   ├── 911_metadata.csv
│   │   │   ├── call_*.mp3 (315 archivos conservados)
│   │   │   ├── filtrar_audios_por_duracion.py
│   │   │   └── link de las llamadas.txt
│   │   └── outputs/
│   │       ├── resultado_*.json (23 resultados individuales)
│   │       ├── english_eval/resultado_*.json (20 resultados)
│   │       └── run5/ (checkpoint y reporte de una ejecución batch)
├── docs/
│   ├── METODOLOGIA_BASE.md
│   ├── IMPLEMENTACION_INICIAL.md
│   ├── Implementacion_20260629.md
│   └── CAMBIOS_MULTIMODAL.md
├── reportes/
│   ├── reporte_filtrado_duracion.md
│   ├── reporte_filtrado_duracion.csv
│   └── muestra_etiquetado.csv
├── scripts/
│   └── evaluate.py
├── src/
│   ├── audio/
│   │   ├── preprocessing.py
│   │   ├── acoustic_features.py
│   │   ├── emergency_indicators.py
│   │   └── vad.py
│   ├── asr/
│   │   ├── transcriber.py
│   │   └── transcript_quality.py
│   ├── semantic/
│   │   ├── text_analyzer.py
│   │   ├── intent_analyzer.py
│   │   └── coherence_analyzer.py
│   ├── scoring/
│   │   ├── seriousness_scorer.py
│   │   ├── decision_policy.py
│   │   └── category_mapper.py
│   ├── evaluation/
│   │   ├── metrics.py
│   │   └── sampling.py
│   ├── report/
│   │   └── implementation_report.py
│   └── utils/
│       ├── config.py
│       ├── helpers.py
│       └── logger.py
└── tests/
    ├── conftest.py
    ├── test_acoustic_features.py
    ├── test_category_mapper.py
    ├── test_coherence_analyzer.py
    ├── test_decision_policy.py
    ├── test_emergency_indicators.py
    ├── test_evaluation.py
    ├── test_integration.py
    ├── test_preprocessing.py
    ├── test_procesar_dataset.py
    ├── test_scoring.py
    ├── test_text_analyzer.py
    ├── test_transcript_quality.py
    └── test_vad.py
```

## 2. Descripción de la estructura del proyecto

El proyecto es un MVP local en Python que estima probabilísticamente la seriedad de una llamada a partir de audio y/o de una transcripción. `main.py` es el punto de entrada de inferencia individual. Admite `--audio` para transcribir con Whisper local o `--transcript` para una transcripción manual; después guarda un JSON de resultado.

El flujo general implementado es:

```text
Audio o transcripción manual
        ↓
ASR local / lectura de texto + validación y carga de audio
        ↓
Extracción acústica y detección de silencios
        ↓
Análisis semántico, de intención y coherencia
        ↓
Puntaje de seriedad e improcedencia + política de decisión
        ↓
Payload JSON y recomendación operativa
```

Las responsabilidades técnicas son las siguientes:

| Ubicación | Finalidad comprobable |
|---|---|
| `src/audio/` | Validación, carga y normalización del audio; extracción de energía, F0, jitter/shimmer aproximados, MFCC, forma espectral, pausas, SNR y anomalías; derivación de indicadores acústicos de emergencia y VAD basado en silencios. |
| `src/asr/` | Transcripción local con Whisper o lectura de archivos de texto; evaluación de la calidad de transcripción. |
| `src/semantic/` | Análisis por reglas de términos, completitud e indicios de ubicación; clasificación de intención y detección de evasivas, contradicciones o cambios de tema. |
| `src/scoring/` | Fusión de evidencia acústica y semántica, cálculo de scores, confianza, categoría (`SERIA`, `DUDOSA`, `IMPROCEDENTE`) y política de recomendación. |
| `src/evaluation/` | Muestreo estratificado para etiquetado manual y métricas: matriz de confusión, precisión, recall, F1, exactitud, macro-F1, AUROC y Brier score. |
| `src/report/` | Construcción y persistencia del payload JSON final. |
| `src/utils/` | Configuración de aplicación/audio, funciones auxiliares y logger. |
| `tests/` | Pruebas unitarias e integración de los módulos de audio, texto, puntaje, evaluación y procesamiento batch. |
| `data/` | Entradas de texto/audio, corpus 911 y resultados JSON persistidos. |
| `reportes/` | Evidencia de filtrado por duración y hoja de etiquetado manual. |
| `docs/` y archivos Markdown de raíz | Metodología, implementación inicial, cambios multimodales, mejoras y bitácora técnica. |

El README establece que el resultado es apoyo operativo y que no debe emplearse para cerrar llamadas automáticamente. También documenta que el sistema actual usa heurísticas auditables y no un modelo supervisado entrenado.

## 3. Scripts importantes

| Nombre y ubicación | Propósito |
|---|---|
| `main.py` | Ejecuta inferencia individual en modo audio o transcripción manual, imprime el score y guarda el resultado JSON. |
| `procesar_dataset.py` | Clasifica en lote grabaciones 911, mantiene checkpoint, genera CSV/JSON de clasificación y de features; admite reprocesamiento selectivo y backfill acústico. |
| `eval_english_dataset.py` | Evalúa en lote un directorio de audios en inglés y genera un JSON por llamada más un resumen estadístico. |
| `scripts/evaluate.py` | Genera una muestra estratificada para etiquetado ciego (`sample`) y calcula métricas contra etiquetas manuales (`evaluate`). |
| `data/audios/911_recordings/filtrar_audios_por_duracion.py` | Filtra el corpus por duración. El reporte persistido indica que separó audios mayores a cinco minutos. |

No se detectó un script de entrenamiento de modelo. El README confirma que no hay entrenamiento supervisado implementado; `features_dataset.csv` se describe como entrada para futuros modelos baseline.

## 4. Evidencias de ejecución

| Evidencia localizada | Descripción |
|---|---|
| `data/outputs/resultado_*.json` | Existen 23 resultados individuales en la raíz de salidas. El más reciente localizado es `resultado_20260730_140731.json`, generado el 2026-07-30 14:07:31 con `test_emergencia.txt`. |
| `data/outputs/english_eval/` | Contiene 20 JSON de resultados individuales de una evaluación en inglés. |
| `test_20.json` | Resultado batch de 20 archivos: 20 procesados correctamente, 0 errores, seriedad media 0.955, improcedencia media 0.041, confianza media 0.881 y 1575.2 s de tiempo total. |
| `RESUMEN_DATASET.md` | Resumen de clasificación batch del conjunto 911: 315 hallados/procesados, 315 correctos y 0 errores en la generación registrada el 2026-07-15. |
| `clasificacion_dataset.csv` y `.json` | Persisten 315 registros de clasificación con archivo, duración, transcripción, categoría, confianza, justificación, scores y recomendación. |
| `features_dataset.csv` | Persisten 315 filas y 73 columnas: resultados de clasificación y vector de características acústicas. |
| `errores_procesamiento.log` | Contiene un error histórico para `call_506.mp3` por imposibilidad de carga/decodificación. Esto no coincide con el resumen posterior, que informa 0 errores; ambos artefactos se conservan y corresponden a ejecuciones distintas. |

**Captura sugerida:** terminal con `python main.py --transcript data\audios\test_emergencia.txt`, mostrando el score y la ruta del JSON generado.

**Captura sugerida:** explorador o VS Code abierto en `data/outputs/` y en `RESUMEN_DATASET.md`, mostrando que las ejecuciones conservaron resultados.

## 5. Evidencias de pruebas automatizadas

La herramienta de pruebas configurada es **pytest** (`pyproject.toml` define `testpaths = ["tests"]` y desactiva el proveedor de caché). Se localizaron 13 módulos de pruebas actuales que cubren análisis acústico, VAD, preprocesamiento, texto, coherencia, decisión, scoring, mapeo de categoría, indicadores de emergencia, calidad de transcripción, integración, evaluación y procesamiento del dataset.

La inspección estática de los archivos actuales identifica **221 funciones nombradas `test_*`**. Esta cifra no equivale necesariamente al número que reportará pytest, pues pueden existir pruebas parametrizadas; no se ejecutó pytest como parte de esta auditoría.

Sí existe evidencia histórica explícita de **109 pruebas exitosas**: `docs/Implementacion_20260629.md` registra literalmente `109 passed in 3.57s` el 29-jun-2026, distribuidas entonces en siete módulos. Además, `MEJORAS_SUBAGENTE_CONVERSACIONAL.md` conserva un registro de `114 passed, 1 warning`, y `MEJORAS_PROYECTO.md` registra una suite posterior de 169 pruebas pasando. Estas cifras son históricas y no deben presentarse como resultado de una ejecución actual sin volver a ejecutar la suite.

No se localizó un reporte de cobertura ni configuración de `pytest-cov`; por ello la cobertura porcentual no está disponible. Para generarla habría que instalar/configurar `pytest-cov` y conservar el reporte resultante.

### Capturas sugeridas

```powershell
python -m pytest tests/ -v
python -m pytest tests/ -q
```

Para evidenciar específicamente el antecedente de 109 pruebas, capturar en VS Code el fragmento de `docs/Implementacion_20260629.md` que contiene `109 passed in 3.57s`. No atribuir ese número a una ejecución nueva si la terminal muestra otro total.

## 6. Ejemplo de salida JSON

Fragmento real y resumido de `data/outputs/resultado_20260730_140731.json`:

```json
{
  "generated_at": "2026-07-30T14:07:31",
  "input": {
    "audio": null,
    "transcript": "data\\audios\\test_emergencia.txt",
    "mode": "transcript_only"
  },
  "score": {
    "seriousness_score": 0.9,
    "improcedence_score": 0.0,
    "confidence": 0.75,
    "recommendation": "escalar_humano"
  }
}
```

## 7. Evidencias del repositorio Git

El repositorio contiene **8 commits** accesibles desde todas las referencias locales/remotas observadas. Existen las ramas locales `main` (activa) y `claude/emergency-call-auditor-20ac57`; también se observa `origin/main` y `origin/HEAD -> origin/main`.

Hitos relevantes del historial:

| Commit | Fecha | Hito resumido |
|---|---:|---|
| `dc8c2fa` | 2026-06-18 | Creación inicial del repositorio. |
| `50cc307` | 2026-07-02 | Actualización integral: ejemplos de audio/salidas, cambios multimodales y mejoras de componentes acústicos, scoring y documentación. |
| `1ef1212` | 2026-07-07 | Incorporación del filtrado de audios por duración y mejoras al scoring. |
| `7d48a48` | 2026-07-15 | Procesamiento del dataset 911, infraestructura de evaluación, estabilidad vocal, backfill acústico, CSV de features y pruebas asociadas. |
| `3afa17c` | 2026-07-15 | Actualización menor de la bitácora de deuda técnica DT-16. |

El estado de trabajo observado antes de crear este anexo ya tenía cambios no relacionados en `MEJORAS_PROYECTO.md` y el directorio no versionado `.claude/`; no son producto de esta auditoría. Este anexo es el único archivo creado por ella.

### Capturas sugeridas

```powershell
git log --oneline --decorate -8
git branch -a
git show --stat 7d48a48
```

Capturar el log, la vista de ramas y el resumen estadístico del commit `7d48a48`, por ser el hito que incorpora dataset, evaluación y features persistidas.

# Anexo 2. Casos de prueba y resultados experimentales

Este anexo reúne los casos funcionales, resultados batch y artefactos de evaluación que sí están conservados en el proyecto. Los resultados representan salidas del sistema heurístico; no se localizaron etiquetas manuales completadas ni métricas experimentales contra ground truth humano.

## A2.1 Casos de prueba utilizados

| Caso | Archivo | Descripción | Resultado esperado | Resultado observado |
|---|---|---|---|---|
| Emergencia textual | `data/audios/test_emergencia.txt` | Texto en español con accidente, ubicación, persona herida y ambulancia. | No disponible como aserción formal independiente; los términos de riesgo activan la política de seguridad. | En `resultado_20260730_140731.json`: seriedad 0.900, confianza 0.750 y `escalar_humano`. |
| Broma textual | `data/audios/test_broma.txt` | Texto: “jaja era una broma no paso nada me estaba riendo”. | No disponible en el archivo de entrada. | En `resultado_20260629_113943.json`: seriedad 0.100, confianza 0.650 y `pedir_mas_informacion`. |
| Audio de ejemplo | `data/audios/Prueba llamada.mp3` | Audio local usado en inferencias individuales. | No disponible. | Dos artefactos conservados: `resultado_20260702_112946.json` (0.655, 0.787, `pedir_mas_informacion`) y `resultado_20260702_113627.json` (0.389, 0.787, misma recomendación). |
| Corpus 911 filtrado | `data/audios/911_recordings/call_*.mp3` | 315 grabaciones en inglés procesadas tras el filtrado por duración. | Clasificación batch y generación de reportes. | `RESUMEN_DATASET.md` informa 315 procesadas correctamente; `clasificacion_dataset.csv` conserva un registro por audio. |
| Muestra para evaluación humana | `reportes/muestra_etiquetado.csv` | Muestra estratificada ciega de llamadas para capturar `etiqueta_manual`. | Completar etiquetas `SERIA`, `DUDOSA` o `IMPROCEDENTE` y ejecutar la evaluación. | 49 filas; las 49 tienen `etiqueta_manual` vacía. No hay métricas contra juicio humano. |
| Guiones sintéticos documentados | `guiones_dataset_prueba.md` | 23 guiones G-01 a G-23, distribuidos entre continuar, escalar, pedir información e improcedencia. | La documentación describe las categorías esperadas por guion. | No se localizaron los audios sintéticos `G-01` a `G-23` ni un archivo de resultados de esa evaluación en el árbol actual. |

## A2.2 Resultados obtenidos

### Clasificación del dataset 911

Datos extraídos de `RESUMEN_DATASET.md` y verificados contra `clasificacion_dataset.csv` (315 filas):

| Indicador | Resultado |
|---|---:|
| Audios encontrados/procesados | 315 / 315 |
| Procesados con éxito | 315 |
| Errores reportados en el resumen | 0 |
| Duración promedio | 170.3 s |
| Duración mínima / máxima | 9.8 s / 299.5 s |
| Duración total | 53,642 s (14:54:02) |
| Tiempo de procesamiento registrado | 00:02:00 |
| Confianza media de clasificación | 0.91 |
| Seriedad media global (recalculada desde CSV) | 0.891 |
| Confianza de categoría media (recalculada desde CSV) | 0.907 |
| Calidad media de transcripción (recalculada desde CSV) | 0.993 |
| Transcripciones marcadas como sospechosas | 6 |

| Categoría | Casos | Porcentaje | Confianza media | Seriedad media |
|---|---:|---:|---:|---:|
| `SERIA` | 281 | 89.2% | 0.91 | 0.95 |
| `DUDOSA` | 34 | 10.8% | 0.88 | 0.43 |
| `IMPROCEDENTE` | 0 | 0.0% | No disponible | No disponible |

| Recomendación observada en `clasificacion_dataset.csv` | Casos |
|---|---:|
| `escalar_humano` | 202 |
| `pedir_mas_informacion` | 107 |
| `continuar` | 6 |
| `posible_improcedente` | 0 |

### Corrida batch de 20 audios

`test_20.json` conserva el siguiente resumen:

| Indicador | Resultado |
|---|---:|
| Archivos totales / procesados correctamente | 20 / 20 |
| Errores | 0 |
| Seriedad promedio | 0.955 |
| Improcedencia promedio | 0.041 |
| Confianza promedio | 0.881 |
| `escalar_humano` | 16 |
| `pedir_mas_informacion` | 4 |
| Tiempo total | 1575.2 s |

No existe `reportes/reporte_evaluacion.md`, porque la muestra manual no contiene etiquetas. Por tanto, precisión, recall, F1, exactitud, AUROC y Brier score contra referencia humana **no están disponibles**. Se generan al completar `etiqueta_manual` en `reportes/muestra_etiquetado.csv` y ejecutar `python scripts/evaluate.py evaluate`.

## A2.3 Ejemplo representativo de salida JSON

Fragmento real de `test_20.json` para `call_10.mp3`:

```json
{
  "file": "call_10.mp3",
  "status": "ok",
  "score": {
    "seriousness_score": 0.926,
    "improcedence_score": 0.1,
    "confidence": 1.0,
    "recommendation": "pedir_mas_informacion",
    "audio_priority": {
      "used": true,
      "seriousness_audio_score": 0.488,
      "audio_reliability": 1.0,
      "stress_vocal_score": 0.581,
      "urgency_score": 0.479,
      "nervousness_score": 0.592
    }
  }
}
```

## A2.4 Resultados del dataset en inglés

Sí existe evaluación del dataset en inglés. `RESUMEN_DATASET.md` identifica ASR `openai-whisper-local-tiny` con idioma forzado `en`; el script `procesar_dataset.py` describe el origen como grabaciones reales de despacho 911 en inglés y el uso de diccionarios bilingües en el analizador semántico.

| Métrica solicitada | Evidencia |
|---|---|
| Número de audios | 315 procesados. |
| Promedio de seriedad | 0.891 global recalculado desde `clasificacion_dataset.csv`; el resumen por clase informa 0.95 para SERIA y 0.43 para DUDOSA. |
| Promedio de confianza | 0.907 recalculado en la columna `confianza`; el resumen redondea a 0.91. |
| Distribución de recomendaciones | 202 `escalar_humano`, 107 `pedir_mas_informacion`, 6 `continuar`, 0 `posible_improcedente`. |
| Distribución de categorías | 281 SERIA, 34 DUDOSA, 0 IMPROCEDENTE. |
| Métricas contra etiquetas humanas | No disponibles: `muestra_etiquetado.csv` tiene 49 etiquetas pendientes. |
| Calidad de transcripción | 6 transcripciones sospechosas, listadas en `RESUMEN_DATASET.md`; la calidad media de la columna es 0.993. |

# Lista de capturas recomendadas

- [ ] VS Code o explorador mostrando el árbol de `src/`, `tests/`, `data/`, `docs/`, `scripts/` y `reportes/`.
- [ ] Terminal ejecutando `python main.py --transcript data\audios\test_emergencia.txt` y mostrando la recomendación.
- [ ] Archivo JSON recién generado abierto, con `input`, `score`, `recommendation` y `evidence` visibles.
- [ ] Terminal ejecutando `python -m pytest tests/ -v` y mostrando el total real de pruebas de esa ejecución.
- [ ] `docs/Implementacion_20260629.md` abierto en la línea que registra `109 passed in 3.57s` como evidencia histórica.
- [ ] `RESUMEN_DATASET.md` abierto en las tablas de totales, categorías y transcripciones sospechosas.
- [ ] `clasificacion_dataset.csv` abierto mostrando columnas de archivo, categoría, confianza, score y recomendación.
- [ ] `features_dataset.csv` abierto mostrando la persistencia de características acústicas.
- [ ] `test_20.json` abierto en su objeto `summary`.
- [ ] Terminal con `git log --oneline --decorate -8`.
- [ ] Terminal con `git show --stat 7d48a48` para el hito de dataset/evaluación/features.
- [ ] `reportes/muestra_etiquetado.csv` abierto mostrando la muestra ciega y el estado pendiente de etiquetas.

# Comandos para obtener evidencias

Los comandos siguientes corresponden a interfaces definidas en el proyecto. Los que reprocesan el dataset o sobrescriben resultados deben ejecutarse únicamente si se desea generar evidencia nueva y se acepta alterar esos artefactos.

```powershell
# Inferencia reproducible con texto manual y generación de JSON en data/outputs/
python main.py --transcript data\audios\test_emergencia.txt
python main.py --transcript data\audios\test_broma.txt

# Inferencia con audio (requiere Whisper local y soporte de decodificación)
python main.py --audio "data\audios\Prueba llamada.mp3" --model tiny

# Pruebas
python -m pytest tests/ -v
python -m pytest tests/ -q

# Generar muestra de etiquetado; no usar --force si se quieren conservar etiquetas existentes
python scripts/evaluate.py sample

# Tras completar etiqueta_manual en reportes/muestra_etiquetado.csv
python scripts/evaluate.py evaluate

# Generar solamente los reportes a partir del checkpoint existente
python procesar_dataset.py --report-only

# Backfill de features acústicas del checkpoint existente; actualiza artefactos batch
python procesar_dataset.py --redo-acustico

# Evaluación batch genérica para un directorio de audios en inglés
python eval_english_dataset.py --audio-dir data\audios\911_recordings --model tiny --output results_english.json
```

El proyecto no declara un comando de cobertura. Para obtener esa evidencia debe agregarse/configurarse una herramienta de cobertura antes de ejecutar un comando con `--cov`.
