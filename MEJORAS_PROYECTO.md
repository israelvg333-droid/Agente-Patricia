# MEJORAS_PROYECTO.md

Historial técnico del subagente de seriedad de llamadas. Cada sesión de trabajo agrega una entrada con fecha. Las secciones **Roadmap Técnico** y **Deuda Técnica** al final del documento son las versiones vivas y se actualizan en cada sesión.

---

# Sesión 2026-07-06 — Revisión técnica completa

---

## 1. Resumen Ejecutivo

### Estado general

El proyecto es un MVP Python funcional para estimar la seriedad de llamadas de emergencia. Combina análisis acústico (librosa), ASR opcional (Whisper local), análisis semántico por reglas y una política de decisión conservadora. El pipeline es lineal y comprensible, el código está razonablemente organizado por capas, y existe una suite de 114 tests unitarios que pasan al 100%.

### Nivel de calidad del código

**Bueno para un MVP académico.** El código es legible, tiene manejo de errores defensivo en los puntos críticos, utiliza dataclasses para la configuración, evita dependencias externas de pago y respeta la restricción ética principal (nunca recomendar colgar llamadas).

### Fortalezas

- Arquitectura clara separada en capas: audio, ASR, semántica, scoring, reporte, utils.
- Pipeline de ejecución lineal y fácil de seguir en `main.py`.
- Configuración centralizada con `AudioAnalysisConfig` y `AppConfig`.
- 114 tests unitarios cubriendo todos los módulos críticos.
- Manejo de modos: con audio, solo transcripción, y fallback si librosa/Whisper fallan.
- Política de decisión conservadora que prioriza la seguridad sobre la eficiencia.
- Documentación metodológica detallada en `docs/`.

### Debilidades

- Funciones privadas duplicadas entre módulos (`_clamp`, `_optional_float`).
- Campos de configuración definidos pero nunca utilizados (`f0_min_hz`, `f0_max_hz`).
- La ventana de análisis acústico se calcula cuatro veces por llamada en lugar de una.
- Cobertura de tests muy baja para `emergency_indicators.py` (solo 3 tests para el módulo heurístico más complejo).
- No existen tests de integración end-to-end.
- `2do avance.md` en la raíz es un documento obsoleto que duplica contenido del README.

---

## 2. Mejoras implementadas

### Mejora 1 — Configuración del logger al nivel de módulo

**Archivos modificados:**
- `src/utils/logger.py`

**Problema detectado:**
`logging.basicConfig(...)` se llamaba dentro de `get_logger()`, es decir, en cada invocación de esa función. Aunque `basicConfig` es idempotente (no-op después de la primera llamada), la llamada repetida es innecesaria, dificulta la lectura de la intención del código y puede enmascarar problemas si alguien intentara personalizar la configuración de logging antes de llamar a `get_logger`.

**Solución implementada:**
Se movió la llamada a `basicConfig` al nivel de módulo, fuera de la función. `get_logger` ahora solo devuelve el logger por nombre.

**Beneficios:**
- La configuración del logger ocurre exactamente una vez al importar el módulo.
- La función `get_logger` tiene una única responsabilidad clara.
- Facilita sobreescribir la configuración de logging desde el exterior antes de importar el módulo.

---

### Mejora 2 — Eliminación de import `Tuple` obsoleto en preprocessing

**Archivos modificados:**
- `src/audio/preprocessing.py`

**Problema detectado:**
El módulo importaba `Tuple` del módulo `typing` (`from typing import Any, Tuple`) pero el proyecto ya utiliza `from __future__ import annotations`, que permite usar la sintaxis de anotaciones nativa de Python 3.9+ sin activarla en runtime. El tipo `Tuple[Any, int]` del módulo `typing` es el equivalente legado de `tuple[Any, int]`.

**Solución implementada:**
- Se eliminó `Tuple` del import de `typing`.
- Se actualizó la firma de `load_audio` de `Tuple[Any, int]` a `tuple[Any, int]`.

**Beneficios:**
- Elimina un import sin uso.
- Consistencia con el estilo moderno de Python 3.9+ que usa el resto del proyecto.
- Reduce la dependencia innecesaria en `typing` para tipos básicos.

---

### Mejora 3 — Renombrado de `_weighted_mean` a `_mean_valid` en emergency_indicators

**Archivos modificados:**
- `src/audio/emergency_indicators.py`

**Problema detectado:**
La función `_weighted_mean` computaba una media aritmética simple de los valores no-None de un tuple, sin ningún peso diferencial. El nombre "weighted mean" (media ponderada) es incorrecto y engañoso: implicaría que cada valor tiene un peso asignado, lo cual no ocurre. Un desarrollador que lea el nombre esperaría una lógica de ponderación que no existe.

**Solución implementada:**
Se renombró la función a `_mean_valid` (media de los valores válidos), que describe con precisión su comportamiento: calcula la media aritmética de los elementos no-None del tuple de entrada, retorna 0.0 si no hay valores válidos, y aplica `_clamp` al resultado.

**Beneficios:**
- El nombre refleja exactamente lo que hace la función.
- Elimina la confusión con algoritmos de media ponderada (weighted average).
- Todos los usos internos del módulo fueron actualizados correctamente.
- Los 114 tests siguen pasando sin cambios.

---

### Mejora 4 — Fixture `acoustic_with_anomalies` sin clave `emergency_audio_indicators`

**Archivos modificados:**
- `tests/conftest.py`

**Problema detectado:**
La fixture `acoustic_with_anomalies` definía un diccionario de features acústicas con anomalías simuladas, pero omitía la clave `emergency_audio_indicators`. Esta clave es accedida por `score_call` en `seriousness_scorer.py` mediante `acoustic.get("emergency_audio_indicators")`. La ausencia de la clave no causaba un error (`.get()` retorna `None` y el código lo maneja), pero producía un comportamiento inconsistente: al usar esta fixture, los indicadores de emergencia nunca serían evaluados aunque el fixture represente un audio con características.

**Solución implementada:**
Se agregó la clave `emergency_audio_indicators` a la fixture, usando los valores que devuelve `empty_emergency_audio_indicators` con todos los scores en `None` y `audio_reliability: 0.0`. Esto representa correctamente un audio cuyos indicadores de emergencia no pudieron derivarse (coherente con las anomalías acústicas severas que simula el fixture).

**Beneficios:**
- La fixture es más representativa de la estructura real del diccionario de features.
- Cualquier test futuro que use `acoustic_with_anomalies` accederá a la clave sin sorpresas.
- Mantiene la semántica original: audio con anomalías pero sin indicadores acústicos de emergencia derivados.

---

## 3. Problemas encontrados sin modificar

### Problema 1 — `_clamp` duplicado en `seriousness_scorer.py` y `emergency_indicators.py`

Ambos módulos definen de forma idéntica:
```python
def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
```

**Razón para no modificar:** Extraer esta función a `src/utils/helpers.py` requeriría actualizar imports en múltiples archivos y podría generar problemas de importaciones circulares si no se hace con cuidado. El riesgo de romper algo supera el beneficio para un MVP. Se recomienda como mejora futura junto con `_optional_float`.

---

### Problema 2 — `_optional_float` duplicado en `seriousness_scorer.py` y `decision_policy.py`

Mismo patrón que el Problema 1. Ambas definiciones son idénticas:
```python
def _optional_float(value: Any) -> float | None:
    return float(value) if value is not None else None
```

**Razón para no modificar:** Misma razón que el Problema 1. Ver recomendaciones futuras (Prioridad Media).

---

### Problema 3 — `AudioAnalysisConfig.f0_min_hz` y `f0_max_hz` son campos muertos

`AudioAnalysisConfig` define `f0_min_hz: float = 70.0` y `f0_max_hz: float = 600.0`, pero ningún módulo del pipeline los usa. El filtro de rango de F0 en `_estimate_f0_stats` usa las constantes de módulo `_SPEECH_F0_MIN_HZ = 70.0` y `_SPEECH_F0_MAX_HZ = 600.0` hardcodeadas directamente.

**Razón para no modificar:** Conectar el config a la función privada requiere cambiar la firma de `_estimate_f0_stats`, lo cual tiene bajo riesgo pero medio esfuerzo. Los valores son iguales en ambos lugares, por lo que no hay divergencia de comportamiento actual.

---

### Problema 4 — `_analysis_window` se invoca 4 veces por llamada

En `extract_acoustic_features`, las funciones `_estimate_tempo`, `_estimate_f0_stats`, `_extract_mfcc_stats` y `_extract_spectral_centroid` llaman cada una a `_analysis_window` internamente. Esto produce hasta 4 truncaciones del mismo audio de hasta 20 segundos.

**Razón para no modificar:** El impacto de rendimiento es bajo (para audios menores a 20 segundos, `_analysis_window` retorna el array original sin copia). Resolver esto requiere cambiar las firmas de las cuatro funciones privadas para aceptar audio pre-truncado, lo cual es una refactorización más extensa. Se recomienda como mejora futura (Prioridad Baja).

---

### Problema 5 — `_analysis_window` ignora `AudioAnalysisConfig.analysis_window_seconds`

`AudioAnalysisConfig` define `analysis_window_seconds: float = 20.0`, pero `_analysis_window` usa el valor hardcodeado `max_seconds=20.0` en sus defaults. Si alguien cambiara el config, el pipeline no lo respetaría.

**Razón para no modificar:** Está relacionado con el Problema 4. Resolver ambos juntos como parte de una refactorización del pipeline de extracción es más seguro que hacerlo de forma parcial.

---

### Problema 6 — Claves redundantes en el JSON de salida

`build_result_payload` en `implementation_report.py` incluye `recommendation` y `evidence` tanto dentro de `score` (como `score.recommendation`, `score.evidence`) como en el nivel raíz del JSON. Esto es redundancia estructural.

**Razón para no modificar:** Cambiar el esquema del JSON rompería la compatibilidad con cualquier consumidor existente (scripts, hojas de cálculo, visualizaciones) que dependan de las claves del nivel raíz. Además, los resultados en `data/outputs/` ya existentes seguirían teniendo el esquema antiguo. Si se desea corregir esto, debe hacerse con una versión del esquema explícita (campo `schema_version`).

---

### Problema 7 — `2do avance.md` en la raíz está desactualizado

El archivo `2do avance.md` en la raíz del proyecto es una versión anterior del README que no menciona MFCCs, indicadores de emergencia acústicos, `emergency_audio_indicators`, ni la suite de tests. El README actual (`README.md`) lo reemplaza completamente.

**Razón para no modificar:** Eliminar archivos de documentación requiere confirmar con el autor que no tiene valor de referencia histórica. Se recomienda eliminarlo o moverlo a `docs/archivo/`.

---

### Problema 8 — Cobertura delgada de `test_emergency_indicators.py`

El módulo `emergency_indicators.py` contiene la heurística más compleja del sistema (8 indicadores compuestos, 9 funciones de scoring, pesos implícitos) y solo tiene 3 tests. Los tests actuales verifican el signo general del score (stress alto → seriousness alta, calma → seriousness baja), pero no cubren:
- Indicadores individuales (`nervousness_score`, `urgency_score`, `aggression_score`, etc.)
- `indicator_flags` de cada indicador
- `_audio_reliability` en distintas condiciones
- El efecto de `audio_reliability < 0.45` sobre `seriousness_audio_score`

**Razón para no modificar:** Agregar tests es trabajo de escritura, no de refactoring. No rompe nada pero es deuda de calidad prioritaria.

---

## 4. Recomendaciones futuras

### Prioridad Alta

**4.1 Ampliar tests de `emergency_indicators.py`**
El módulo es el más complejo y heurístico del sistema. Necesita al menos 15-20 tests adicionales que cubran cada indicador compuesto (urgency, nervousness, aggression, desperation, calm, voice_instability), los umbrales de `indicator_flags`, y el comportamiento de `audio_reliability` en baja calidad. Sin estos tests, los cambios en umbrales no pueden validarse de forma segura.

**4.2 Agregar tests de integración end-to-end**
Actualmente no existe ningún test que ejecute `run_pipeline` completo con un archivo `.wav` sintético generado en memoria (por ejemplo, con `soundfile.write`). Estos tests detectarían regresiones en la integración entre módulos que los tests unitarios no pueden capturar.

**4.3 Extraer `_clamp` y `_optional_float` a `src/utils/helpers.py`**
Eliminar la duplicación de estas funciones privadas en tres módulos distintos. Una vez extraídas, pueden mejorarse con type hints más precisos y documentación centralizada. La implementación requiere:
1. Crear `src/utils/helpers.py` con ambas funciones.
2. Actualizar imports en `seriousness_scorer.py`, `decision_policy.py` y `emergency_indicators.py`.
3. Verificar que no existan ciclos de importación.

**4.4 Conectar `AudioAnalysisConfig.f0_min_hz`/`f0_max_hz` al pipeline**
Los campos existen en el config pero `_estimate_f0_stats` usa constantes hardcodeadas. Conectar el config permite ajustar el rango de F0 sin tocar el código. La solución más limpia es precomputar la ventana de análisis una sola vez en `extract_acoustic_features` y pasarla como parámetro a las cuatro funciones privadas, lo que también resuelve el Problema 4 (llamadas redundantes a `_analysis_window`).

---

### Prioridad Media

**4.5 Versionar el esquema JSON de salida**
Agregar un campo `schema_version: "1.0"` al JSON de salida. Una vez versionado, se puede eliminar la duplicación de `recommendation`/`evidence` en el nivel raíz (Problema 6) de forma controlada pasando a `schema_version: "2.0"`.

**4.6 Eliminar o archivar `2do avance.md`**
Mover el archivo a `docs/archivo/2do_avance_historico.md` para preservar el historial sin contaminar la raíz del proyecto.

**4.7 Configurar `flake8` o `ruff` como linter en CI**
El código es limpio pero sin un linter configurado es fácil introducir imports sin uso, espacios inconsistentes o nombres que no siguen la convención. Ruff es especialmente rápido y reemplaza flake8 + isort + pyupgrade.

---

### Prioridad Baja

**4.8 Agregar `pyproject.toml` con configuración del proyecto**
Centraliza la configuración de herramientas (pytest, ruff, mypy) y facilita futuras integraciones con CI/CD.

**4.9 Agregar type checking estático con `mypy` o `pyright`**
El proyecto usa anotaciones de tipo consistentemente. Agregar un paso de `mypy --strict` detectaría errores de tipo en tiempo de desarrollo.

**4.10 Marcar `2do avance.md` como obsoleto**
Hasta que se pueda eliminar, agregar una nota al inicio del archivo: `> NOTA: Este documento está desactualizado. Ver README.md para la versión actual.`

---

## 5. Posibles nuevas funcionalidades

### 5.1 Interfaz Streamlit para visualización interactiva

**Justificación:** El sistema genera un JSON rico con scores, evidencias, features acústicas e indicadores. Una interfaz en Streamlit permitiría cargar un audio, ver la transcripción, ver los valores acústicos como gráficos (F0 a lo largo del tiempo, energía por tramas, ratio de silencios) y el resultado final con justificación visual. Sería útil para validar el sistema con usuarios operativos antes de integrarlo en producción.

**Herramienta:** `streamlit` (gratuito, local).

---

### 5.2 faster-whisper como motor de ASR

**Justificación:** `faster-whisper` (basado en CTranslate2) es entre 2x y 4x más rápido que `openai-whisper` en CPU con la misma precisión, y consume menos memoria. El módulo `transcriber.py` puede adaptarse con un bloque `try/except` que intente `faster_whisper` primero y caiga al `openai-whisper` como fallback. Esto no requiere cambiar la interfaz pública del módulo ASR.

**Herramienta:** `pip install faster-whisper`.

---

### 5.3 Jitter y shimmer como features de estabilidad vocal

**Justificación:** La metodología base (`METODOLOGIA_BASE.md`, Fase 3) los menciona explícitamente. Jitter mide la variabilidad ciclo-a-ciclo de F0 y shimmer mide la variabilidad de amplitud. Ambos son indicadores clásicos de estrés vocal y nerviosismo. Pueden calcularse sobre el audio con `parselmouth` (interfaz Python de Praat) sin dependencias de pago. Son especialmente útiles como features para los modelos supervisados de la siguiente fase.

**Herramienta:** `pip install praat-parselmouth`.

---

### 5.4 Evaluación automática con métricas (F1, AUROC, Brier Score)

**Justificación:** El sistema actualmente no tiene métricas de evaluación. Una vez que exista un dataset etiquetado (aunque sea pequeño, de 30-50 llamadas simuladas), un script `scripts/evaluate.py` podría ejecutar el pipeline sobre cada audio, comparar la recomendación con la etiqueta real y calcular recall para llamadas serias, precision para improcedentes, F1 y AUROC. El recall alto en llamadas serias es la métrica prioritaria.

---

### 5.5 Exportación de vector de features para entrenamiento de modelos baseline

**Justificación:** Actualmente todas las features se calculan pero no se persisten en formato tabular. Un script `scripts/extract_features.py` que genere un CSV con una fila por llamada y columnas para cada feature acústica y semántica permitiría entrenar modelos clásicos (regresión logística, random forest, SVM) sin modificar el pipeline principal. Esto es el prerequisito de la Fase 6 de la metodología.

---

### 5.6 Detección de múltiples hablantes

**Justificación:** El sistema asume un solo hablante. En llamadas reales puede haber operador + ciudadano, o interferencias. La diarización básica con `pyannote.audio` (gratuita para uso no comercial) permitiría segmentar el audio por hablante y analizar únicamente la voz del ciudadano, mejorando la calidad de los features acústicos.

---

### 5.7 Modo de análisis de segmentos (chunking)

**Justificación:** Para llamadas largas (> 20 segundos), el pipeline actual analiza solo los primeros 20 segundos para los features espectrales. Un modo de análisis por segmentos procesaría el audio en ventanas de 10-20 segundos y agregaría los resultados (percentiles, evolución temporal). Esto es especialmente útil para detectar cambios de comportamiento a lo largo de la llamada (por ejemplo, inicio tranquilo que se vuelve urgente).

---

## 6. Deuda técnica

| # | Componente | Descripción | Impacto |
|---|---|---|---|
| DT-1 | `emergency_indicators.py` | Solo 3 tests para la heurística más compleja del sistema | Alto |
| DT-2 | Helpers duplicados | `_clamp` y `_optional_float` en 3 módulos distintos | Medio |
| DT-3 | Config fields muertos | `f0_min_hz`, `f0_max_hz` en `AudioAnalysisConfig` nunca se usan | Medio |
| DT-4 | `_analysis_window` × 4 | La ventana de análisis se recalcula 4 veces por llamada | Bajo |
| DT-5 | Config no controla ventana | `analysis_window_seconds` definido en config pero ignorado | Bajo |
| DT-6 | JSON redundante | `recommendation` y `evidence` duplicados en nivel raíz | Bajo |
| DT-7 | Sin versión de esquema | No hay campo `schema_version` en el JSON de salida | Bajo |
| DT-8 | `2do avance.md` obsoleto | Documento en raíz desactualizado respecto al README | Bajo |
| DT-9 | Sin tests de integración | Ningún test ejecuta el pipeline completo con audio real o sintético | Alto |
| DT-10 | Sin linter configurado | No hay `ruff`/`flake8` ni `mypy` en el proyecto | Medio |

---

## 7. Riesgos

### R1 — Calibración de umbrales heurísticos sin datos etiquetados (Riesgo Alto)

Los umbrales de energía, silencio, F0, SNR y los pesos de los indicadores acústicos de emergencia son completamente heurísticos. Sin un dataset etiquetado con llamadas reales (seria, dudosa, improcedente) no es posible saber si los umbrales actuales producen recall alto para llamadas serias o generan muchos falsos positivos. Este es el riesgo más importante antes de cualquier uso operativo.

### R2 — Errores de transcripción con modelo tiny de Whisper (Riesgo Alto)

El modelo `tiny` de Whisper es rápido pero comete errores frecuentes con acentos regionales, múltiples voces, bajo SNR o vocabulario especializado. Un error de transcripción puede hacer que `analyze_text` no detecte palabras clave críticas (por ejemplo, "disparo" transcrito como "desparo" o "chispero"), reduciendo el seriousness score de una llamada grave.

### R3 — Sesgo por variante regional del español (Riesgo Medio)

Los vocabularios de palabras clave en `text_analyzer.py` usan términos del español latinoamericano (colonia, delegación, baldazo). Pueden fallar con variantes regionales de México, España, Argentina u otros países según el contexto de despliegue.

### R4 — Dependencia de FFmpeg para audio comprimido (Riesgo Medio)

Para `.mp3` y `.m4a`, `librosa` delega la decodificación a FFmpeg. Si FFmpeg no está instalado o el PATH no lo incluye, la carga de audio fallará con un error descriptivo pero el pipeline continuará en modo solo-texto, degradando silenciosamente la calidad del análisis acústico.

### R5 — Ausencia de anonimización de datos (Riesgo Alto para producción)

El pipeline guarda el JSON de salida con el path completo del archivo de audio como metadato (`input.audio`). Si los audios contienen datos personales o sensibles y los JSONs se almacenan en un sistema compartido, puede haber riesgos de privacidad. El sistema no anonimiza ni cifra los datos de salida.

### R6 — Sobreconfianza operativa (Riesgo Alto)

El score y la recomendación pueden interpretarse erróneamente como definitivos. La nota de seguridad en el JSON (`"safety_note": "Estimacion probabilistica..."`) es el único mecanismo actual de advertencia. Sin una interfaz de usuario que enfatice el carácter probabilístico del resultado, existe riesgo de que operadores usen el score como criterio de cierre.

---

## 8. Próximos pasos recomendados

### Corto plazo (1-2 semanas)

1. **Ampliar tests de `emergency_indicators.py`**: Agregar mínimo 15 tests para cada indicador y para los `indicator_flags`. Prioridad: esta es la heurística más importante y la menos cubierta.

2. **Agregar tests de integración**: Crear `tests/test_integration.py` con un test que genere un `.wav` sintético en memoria con `soundfile`, lo guarde en un directorio temporal y ejecute `run_pipeline` completo, verificando que el JSON de salida tiene la estructura esperada.

3. **Configurar `ruff` como linter**: Agregar `pyproject.toml` con configuración mínima de `ruff` (o `flake8`). Ejecutar una vez para limpiar imports sin uso residuales o inconsistencias de estilo.

4. **Archivar `2do avance.md`**: Mover a `docs/archivo/` y actualizar `.gitignore` si es necesario.

### Mediano plazo (2-6 semanas)

5. **Dataset etiquetado de llamadas simuladas**: Crear al menos 30-50 llamadas simuladas (.txt o .wav) con etiquetas manuales (seria/dudosa/improcedente). Incluso un dataset pequeño permite validar si los umbrales actuales tienen recall aceptable.

6. **Script de evaluación con métricas**: Implementar `scripts/evaluate.py` que ejecute el pipeline sobre el dataset etiquetado y calcule recall, precision, F1 y AUROC.

7. **Conectar `AudioAnalysisConfig` al pipeline de features**: Precomputar la ventana de análisis una sola vez en `extract_acoustic_features` usando `cfg.analysis_window_seconds`, y pasarla a `_estimate_tempo`, `_estimate_f0_stats`, `_extract_mfcc_stats` y `_extract_spectral_centroid`. Esto también conecta `f0_min_hz`/`f0_max_hz` del config al filtro de `_estimate_f0_stats`.

8. **Evaluar faster-whisper**: Medir velocidad y precisión de `faster-whisper` vs `openai-whisper tiny` en el conjunto de audios de prueba. Si el resultado es superior, actualizar `transcriber.py` con soporte para ambos.

### Largo plazo (6+ semanas)

9. **Modelos baseline supervisados**: Con dataset etiquetado disponible, exportar el vector de features acústicas + semánticas a CSV y entrenar regresión logística, random forest y SVM. Comparar métricas contra el sistema heurístico actual. El objetivo es superar el recall del sistema de reglas en llamadas serias.

10. **Interfaz Streamlit**: Implementar una demo visual que permita subir un audio o texto, ver la transcripción, visualizar los features acústicos (energía, F0, silencios como gráfico temporal) y el resultado con justificación. Útil para demostraciones y validación con usuarios operativos.

11. **Versionar esquema JSON y limpiar redundancias**: Agregar `schema_version: "2.0"` y eliminar las claves duplicadas `recommendation`/`evidence` del nivel raíz. Documentar la migración para consumidores existentes.

12. **Jitter y shimmer con parselmouth**: Agregar features de estabilidad vocal como preparación para la fase CNN-LSTM una vez que exista dataset etiquetado suficiente.

---

# Sesión 2026-07-07 — Adopción del modo de mantenimiento evolutivo y resolución de DT-2

## Fecha

2026-07-07

## Objetivo de la sesión

Establecer el modo de trabajo permanente de mantenimiento evolutivo, verificar el estado actual del proyecto, reestructurar este documento como historial técnico con secciones vivas de Roadmap y Deuda Técnica, y resolver la deuda técnica DT-2 (helpers duplicados).

## Archivos modificados

- `src/utils/helpers.py` (nuevo)
- `src/scoring/seriousness_scorer.py`
- `src/scoring/decision_policy.py`
- `src/audio/emergency_indicators.py`
- `tests/test_scoring.py`
- `MEJORAS_PROYECTO.md`

## Cambios implementados

1. **Creación de `src/utils/helpers.py`** con dos funciones compartidas: `clamp01(value)` (restringe al rango [0, 1]) y `optional_float(value)` (convierte a float preservando None).
2. **Eliminación de las copias duplicadas**: `_clamp` y `_optional_float` en `seriousness_scorer.py`, `_optional_float` en `decision_policy.py`, y `_clamp` y `_value` en `emergency_indicators.py` (esta última era una tercera copia de `optional_float` con otro nombre, no detectada en la auditoría anterior).
3. **Actualización de todos los usos** en los tres módulos a los nombres públicos `clamp01` y `optional_float`.
4. **Actualización de `tests/test_scoring.py`** para importar los helpers desde `src.utils.helpers` en lugar de los nombres privados de `seriousness_scorer`.
5. **Reestructuración de este documento** al formato de historial: entradas por sesión con fecha, más las secciones vivas Roadmap Técnico y Deuda Técnica al final.

## Justificación técnica

La auditoría del 2026-07-06 identificó la duplicación como recomendación 4.3 (Prioridad Alta). Existían cinco definiciones para dos funciones en tres módulos, lo que obligaba a mantener sincronizadas copias idénticas y ocultaba que `_value` en `emergency_indicators.py` era la misma función con otro nombre. `src/utils` no importa nada de `scoring` ni `audio`, por lo que la extracción no introduce ciclos de importación.

## Beneficios obtenidos

- Una única fuente de verdad para el clamping y la conversión opcional a float.
- Nombres públicos y descriptivos (`clamp01` deja explícito el rango) en lugar de tres nombres privados distintos para la misma lógica.
- Se elimina la deuda DT-2 del inventario.

## Riesgos detectados

- Riesgo bajo: el cambio es un refactor mecánico sin cambio de comportamiento. Los `replace_all` fueron verificados con grep para descartar corrupción de identificadores similares.

## Validaciones realizadas

- Suite completa: **114 tests pasando** antes y después del cambio.
- Verificación de imports: `import main` y uso directo de `clamp01`/`optional_float` sin errores.
- Smoke test end-to-end: `python main.py --transcript <archivo>` ejecuta el pipeline completo y genera el JSON con la estructura esperada (`escalar_humano` para un guion con términos de alto riesgo).
- `git status` limpio antes de la sesión; directorios temporales de pytest ya cubiertos por `.gitignore`.

## Recomendaciones futuras

- La siguiente prioridad del roadmap es ampliar los tests de `emergency_indicators.py` (DT-1) y agregar tests de integración end-to-end (DT-9), ambas de impacto Alto.
- Al conectar `AudioAnalysisConfig` al pipeline de features (recomendación 4.4 de la sesión anterior), aprovechar para mover el filtro de F0 a los campos del config.

---

# Sesión 2026-07-08 — Revisión integral tras el procesamiento del dataset 911 (316 audios)

## Fecha

2026-07-08

## Objetivo de la sesión

Revisión integral del proyecto usando los resultados del procesamiento batch del dataset 911 real (316 audios, `procesar_dataset.py`): análisis estadístico de la clasificación, auditoría de calidad del código y del pipeline, e implementación de mejoras derivadas directamente de lo observado en los datos.

## Estado del dataset y métricas

- 316 audios encontrados; 315 procesados con éxito, 1 con error (`call_506.mp3`).
- Distribución: **SERIA 280 (88.9%)**, **DUDOSA 35 (11.1%)**, **IMPROCEDENTE 0 (0%)**. Coherente con un dataset de grabaciones reales de despacho 911 (no contiene bromas), pero implica que la rama IMPROCEDENTE sigue sin validación con datos reales.
- Confianza media 0.91 (mediana 0.90); seriousness media 0.888 con 181 llamadas en ~1.0; improcedence máxima 0.50.
- Recomendaciones del pipeline: `escalar_humano` 200 (63%), `pedir_mas_informacion` 108, `continuar` 7.
- Tiempo de proceso: mediana 59.6 s/audio (RTF mediano 0.36x con Whisper tiny); wall clock total 01:19:39 con 3 workers × 2 hilos torch (~5x de paralelismo efectivo).
- Sin transcripciones vacías, pero 3 con < 10 palabras y 8 con patrones repetitivos típicos de alucinación de Whisper tiny (una con caracteres cirílicos/coreanos clasificada SERIA con confianza 1.0).

## Problemas encontrados

1. **Sobreconfianza con transcripciones degradadas (crítico para calibración)**: `call_288.mp3` (texto alucinado multilingüe) obtuvo confianza 1.0; `call_59.mp3` (transcripción de 2 palabras "Title 4") obtuvo DUDOSA con 0.85; `call_569.mp3` (1 palabra) SERIA con 0.54. El pipeline no distinguía entre evidencia semántica confiable y basura del ASR.
2. **Alucinaciones de Whisper tiny sin mitigar**: `transcribe()` se llamaba sin `condition_on_previous_text=False` ni `temperature=0.0`, los dos parámetros estándar para reducir bucles repetitivos en audios largos.
3. **`call_506.mp3` no es un audio**: es un documento HTML de 5 KB (descarga fallida guardada como .mp3). El error de carga era inevitable y está bien manejado; el archivo debe reemplazarse o descartarse del dataset.
4. **Deuda DT-3/DT-4/DT-5 vigentes**: `f0_min_hz`/`f0_max_hz` y `analysis_window_seconds` del config ignorados; `_analysis_window` recalculada 4 veces por llamada.
5. **Duplicación en `procesar_dataset.py`**: `write_csv` y `write_json` repetían la misma lista de columnas.
6. **Sesgo estructural detectado (no corregido, ver propuestas)**: `_has_address_like_text` acepta cualquier número de 2-5 dígitos y "911" está en `EMERGENCY_TERMS`, por lo que prácticamente toda transcripción de una llamada 911 real (que incluye el saludo del operador) activa `has_location` y keywords de emergencia. Esto explica en parte la concentración de seriousness en ~1.0 y limita el poder discriminante del scoring en este dataset.
7. Artefactos generados (`.numba_cache/`, `dataset_clasificado/`) sin ignorar en git.

## Archivos modificados

- `src/asr/transcript_quality.py` (nuevo)
- `src/scoring/category_mapper.py`
- `src/audio/acoustic_features.py`
- `procesar_dataset.py`
- `tests/test_transcript_quality.py` (nuevo)
- `tests/test_category_mapper.py`
- `tests/test_emergency_indicators.py`
- `.gitignore`
- `clasificacion_dataset.csv`, `clasificacion_dataset.json`, `RESUMEN_DATASET.md` (regenerados con `--report-only`)

## Cambios implementados

1. **Nuevo módulo `src/asr/transcript_quality.py`**: `assess_transcript_quality(text)` detecta tres señales de baja calidad con umbrales derivados del dataset: transcripción muy corta (< 10 palabras), patrón repetitivo (4-grama más frecuente > 5% — firma de alucinación de Whisper) y caracteres fuera del alfabeto latino (> 2% de las letras). Devuelve `quality_score` (0-1), `flags` e `is_suspect`.
2. **Calibración de confianza en `category_mapper.py`**: `map_score_to_category` acepta `transcript_quality` opcional; cuando la transcripción es sospechosa, la confianza se multiplica por un factor lineal en [0.5, 1.0] según `quality_score` y la alerta queda registrada en la justificación. **La categoría nunca cambia por calidad de transcripción** (se preserva la política conservadora). El helper público `apply_transcript_quality_adjustment` permite aplicar la misma regla a registros históricos.
3. **Mitigación de alucinaciones en `procesar_dataset.py`**: `transcribe(..., temperature=0.0, condition_on_previous_text=False)`.
4. **Retro-relleno desde checkpoint**: `ensure_transcript_quality(record)` calcula la calidad para registros de checkpoints previos (idempotente), lo que permitió regenerar los reportes del dataset completo con `--report-only` sin reprocesar 15 horas de audio.
5. **Conexión de `AudioAnalysisConfig` al pipeline de features** (resuelve DT-3, DT-4, DT-5): la ventana de análisis se calcula una sola vez con `cfg.analysis_window_seconds` y se pasa a los cuatro estimadores espectrales; `_estimate_f0_stats` ahora usa `cfg.f0_min_hz`/`cfg.f0_max_hz`. Sin cambio de comportamiento (los defaults coinciden).
6. **Exportes enriquecidos**: columnas nuevas en CSV/JSON (`alertas_transcripcion`, `calidad_transcripcion`, `seriousness_score`, `pipeline_confidence`, `recommendation`) con lista única `EXPORT_FIELDS` compartida (elimina la duplicación).
7. **`RESUMEN_DATASET.md` ampliado**: tabla de distribución con confianza y seriedad medias por categoría, nueva sección "Transcripciones sospechosas", observación automática sobre alertas y nota de wall clock correcta en modo `--report-only`.
8. **Tests**: 40 nuevos (169 en total): 16 para `transcript_quality`, 5 para el ajuste de confianza en el mapper y 19 para `emergency_indicators` (resuelve DT-1: helpers `_score_above`, `_score_between`, `_mean_valid`, `_range`, `_invert`, `_audio_reliability`, flags y rangos).
9. **`.gitignore`**: se ignoran `.numba_cache/` y `dataset_clasificado/`.

## Justificación técnica

El análisis del dataset real mostró que la principal fuente de error de calibración no era el scoring acústico sino la confianza ciega en la salida del ASR: el 3.5% de las transcripciones (11/315) eran basura parcial o total y el sistema las trataba como evidencia semántica válida. La solución es una capa de diagnóstico auditable que degrada la confianza — nunca la categoría — y deja rastro en la justificación, alineada con el principio del proyecto de nunca descartar una posible emergencia automáticamente.

## Beneficios obtenidos

- Tras regenerar reportes: 11 transcripciones sospechosas identificadas y recalibradas. `call_288` bajó de 1.00 → 0.75, `call_569` de 0.54 → 0.43 y `call_73` de 0.74 → 0.59; la lista de revisión manual (< 0.60) pasó de 1 a 2 llamadas, ambas justificadas.
- Las futuras corridas del batch producirán menos alucinaciones desde la fuente (parámetros de Whisper) y las que ocurran quedarán marcadas.
- Tres deudas técnicas resueltas (DT-3, DT-4, DT-5) y DT-1 cerrada con 19 tests nuevos.
- El CSV/JSON exportado ahora contiene los scores necesarios para el futuro entrenamiento supervisado y la matriz de confusión, sin releer el checkpoint.

## Riesgos detectados

- Riesgo bajo: el ajuste de confianza solo reduce (nunca aumenta) y no altera categorías; los umbrales de calidad podrían necesitar afinación con más datos (falsos positivos de `transcripcion_repetitiva` en llamadas con frases genuinamente repetidas por pánico).
- `temperature=0.0` y `condition_on_previous_text=False` solo aplican a corridas nuevas; el checkpoint actual conserva las transcripciones de la corrida original.

## Validaciones realizadas

- Suite completa: **169 tests pasando** (129 previos + 40 nuevos, 0 regresiones).
- Regeneración end-to-end de reportes con `--report-only` sobre el checkpoint real de 316 audios: categorías idénticas, solo confianzas ajustadas donde corresponde.
- Smoke test `python main.py --transcript data/audios/test_emergencia.txt`: pipeline completo OK (`escalar_humano`, score 0.9).
- Verificación del CSV regenerado: cabecera con las 12 columnas esperadas y BOM UTF-8 conservado para Excel.

## Recomendaciones futuras

1. **Reprocesar el dataset con `--fresh` y modelo `base`** (o al menos los 11 audios sospechosos): las alucinaciones de tiny son la mayor fuente de ruido semántico; `base` + los nuevos parámetros anti-alucinación deberían reducirlas de forma notable. No es urgente: el retro-relleno ya marca los casos afectados.
2. **Corregir el sesgo del token "911" y dígitos sueltos** (problema 6): requiere decisión de negocio porque cambia el scoring de todo el histórico; propuesta: excluir "911" de `EMERGENCY_TERMS` cuando aparece solo en el saludo inicial, y exigir contexto (nombre de vía o preposición) para `_has_address_like_text`.
3. **Etiquetado manual de una muestra estratificada** (p. ej. 50 llamadas: todas las DUDOSAS + 15 SERIAS aleatorias) para calcular recall/precision reales y calibrar los umbrales de confianza con evidencia.
4. Reemplazar o eliminar `data/audios/911_recordings/call_506.mp3` (es HTML, no audio).
5. Extracción de features a CSV para modelos supervisados baseline (ya existe la infraestructura de exportación).
6. Matriz de confusión y validación cruzada una vez exista el etiquetado manual; explicabilidad ya cubierta parcialmente por `justificacion`/`evidence`.

---

# Sesión 2026-07-14 — Tests de integración, linter, versionado de esquema y features de estabilidad vocal

## Fecha

2026-07-14

## Objetivo de la sesión

Continuar la evolución audio-first del proyecto ejecutando los pendientes de impacto Alto del roadmap: tests de integración end-to-end (DT-9), linter `ruff` con `pyproject.toml` (DT-10), versionado del esquema JSON (DT-7) y nuevas características acústicas de estabilidad vocal (jitter/shimmer aproximados, forma espectral y el indicador `voice_tremor_score`, ítem 13 de la lista de prioridades del proyecto: temblor de la voz).

## Estado verificado al inicio

- Working tree con los cambios de la sesión 2026-07-08 sin commitear (consistentes con el historial).
- Suite base: 169 tests pasando. Los 7 errores iniciales al usar `--basetemp .tmp_pytest_run` provienen de directorios `.tmp_pytest*` residuales con permisos dañados en Windows (no es un problema del código; usar el basetemp por defecto de pytest o `%TEMP%`).

## Archivos modificados

- `src/audio/acoustic_features.py` — jitter, shimmer y forma espectral
- `src/audio/emergency_indicators.py` — `voice_tremor_score` + flag `temblor_vocal_probable`
- `src/report/implementation_report.py` — `schema_version: "1.1"`
- `src/scoring/seriousness_scorer.py`, `src/scoring/decision_policy.py`, `src/semantic/text_analyzer.py`, `procesar_dataset.py`, `eval_english_dataset.py` — solo formato (líneas largas) e imports ordenados por `ruff --fix` (sin cambio de comportamiento)
- `pyproject.toml` (nuevo) — configuración de `ruff` y `pytest`
- `tests/test_integration.py` (nuevo) — 6 tests end-to-end
- `tests/test_acoustic_features.py` — 6 tests nuevos de estabilidad vocal/forma espectral
- `tests/test_emergency_indicators.py` — 6 tests nuevos de temblor vocal
- `README.md`, `requirements.txt` — documentación de features nuevas y dependencia de desarrollo

## Cambios implementados

1. **Jitter aproximado (`estimated_jitter_ratio`)**: perturbación relativa media de F0 entre tramas vocales consecutivas, calculada desde la serie de `librosa.yin` con máscara de validez (70–600 Hz). Aproximación al jitter clásico; proxy directo de temblor/inestabilidad de la voz.
2. **Shimmer aproximado (`estimated_shimmer_ratio`)**: perturbación relativa media de amplitud RMS entre tramas activas consecutivas (solo tramas por encima del umbral de silencio, para no medir transiciones habla-pausa).
3. **Forma espectral**: `spectral_rolloff_hz` (85%), `spectral_bandwidth_hz` y `spectral_flatness` con una única STFT compartida. Rolloff/ancho de banda complementan al centroide para gritos y voz tensa; la flatness es señal de audio ruidoso/calidad vocal degradada.
4. **`voice_tremor_score`** en `emergency_audio_indicators` con flag `temblor_vocal_probable` (≥ 0.65). **Decisión de diseño**: es aditivo/informativo y NO participa aún en `seriousness_audio_score`, para preservar la comparabilidad con el dataset 911 ya clasificado; se integrará al score tras el etiquetado manual (test de regresión `test_tremor_does_not_change_seriousness_audio_score` protege esta propiedad).
5. **Calibración empírica del temblor**: los umbrales de laboratorio (jitter 0.02–0.12) saturaban en audio telefónico real — muestreo de 10 llamadas 911 mostró jitter aproximado en rango 0.12–0.45 (la aproximación trama a trama de YIN es un orden de magnitud mayor que el jitter ciclo a ciclo). Umbrales ajustados a (0.12, 0.45) jitter y (0.12, 0.32) shimmer; el indicador ahora discrimina (0.22–0.84 en la muestra) en lugar de saturar.
6. **Tests de integración end-to-end (resuelve DT-9)**: `tests/test_integration.py` ejecuta `run_pipeline` real — modo transcript-only sin mocks, y modo audio con `.wav` sintético (tono 220 Hz con vibrato y pausa central) donde solo el ASR está simulado. Verifican estructura del JSON, rango de scores, F0 detectada en rango, pausas, enriquecimiento de WPM desde transcripción (192 wpm exactas) y errores de entrada (sin argumentos, audio inexistente).
7. **`ruff` configurado (resuelve DT-10)**: `pyproject.toml` con reglas E, F, W, I, UP, B y line-length 100. 27 hallazgos auto-corregidos (imports sin uso, orden de imports, f-string sin placeholders) y 9 líneas largas reescritas a mano. `ruff check .` queda limpio. Excepciones documentadas: E501 en tests y E402 en `procesar_dataset.py` (bootstrap de `sys.path`).
8. **`schema_version: "1.1"` en el JSON de salida (resuelve DT-7)**: 1.0 se define como el esquema original sin versionar; 1.1 agrega las features nuevas y el propio campo (cambios aditivos, sin ruptura). La limpieza de claves duplicadas del nivel raíz (DT-6) queda para una futura versión 2.0.

## Justificación técnica

El temblor de la voz es el ítem 13 de la lista de señales objetivo del proyecto y no existía ninguna feature que lo capturara; jitter y shimmer son sus correlatos clásicos en fonética forense y SER, y pueden aproximarse sin dependencias nuevas (se evaluó `parselmouth`/Praat para las versiones ciclo a ciclo exactas; queda en roadmap porque agrega una dependencia binaria y su beneficio real solo podrá medirse contra etiquetas). La forma espectral (rolloff, bandwidth, flatness) completa el eje 16 (características espectrales relevantes) reutilizando una sola STFT, con costo marginal. Los tests de integración eran la deuda Alta más antigua: los 169 tests unitarios no ejercitaban la integración `main.run_pipeline` → módulos, que es exactamente donde ocurrieron los problemas históricos (fixtures inconsistentes, claves faltantes).

## Beneficios obtenidos

- Tres deudas técnicas cerradas (DT-7, DT-9, DT-10) en una sesión.
- 18 tests nuevos (187 en total, 0 regresiones) incluyendo la primera cobertura end-to-end del pipeline.
- Cinco features acústicas nuevas listas para el futuro CSV de entrenamiento supervisado.
- Primer indicador calibrado contra la distribución real del dataset 911 (metodología replicable para recalibrar los demás).
- Base de código con linter limpio; los futuros diffs serán más pequeños y consistentes.

## Riesgos detectados

- Los umbrales del temblor se calibraron con una muestra de 10 llamadas del mismo dataset (mismo canal telefónico); pueden requerir ajuste con audios de otros canales o micrófonos.
- El jitter aproximado trama a trama mezcla temblor real con ruido de tracking de YIN; la separación limpia requiere `parselmouth` o F0 con `pyin` probabilístico.
- `ruff --fix` tocó módulos de scoring/semántica (solo imports y formato); la suite completa y el smoke test confirman que no hubo cambio de comportamiento.

## Validaciones realizadas

- `ruff check .` sin hallazgos.
- Suite completa: **187 tests pasando** (169 previos + 18 nuevos).
- Smoke test CLI: `python main.py --transcript data/audios/test_emergencia.txt` → `escalar_humano`, score 0.9, idéntico al histórico.
- Extracción real: features nuevas verificadas sobre `call_10.mp3` y muestreo de 10 llamadas del dataset 911 (valores en rangos plausibles, sin excepciones).
- El JSON de salida incluye `schema_version: "1.1"` y todas las claves previas (cambio aditivo verificado por los tests de integración).

## Recomendaciones futuras

1. Persistir las features nuevas en el CSV del dataset al reprocesar (`procesar_dataset.py` las incluirá automáticamente vía `extract_acoustic_features`, pero el checkpoint actual no las tiene: se necesitará `--fresh` o un backfill acústico sin re-transcribir).
2. Tras el etiquetado manual estratificado, decidir con datos el peso de `voice_tremor_score` dentro de `seriousness_audio_score`.
3. Evaluar `parselmouth` para jitter/shimmer ciclo a ciclo reales y comparar poder discriminante contra las aproximaciones.
4. Eliminar los directorios `.tmp_pytest*` bloqueados (requiere desbloqueo manual de permisos en Windows o reinicio) y dejar de usar `--basetemp` dentro del workspace.

---

# Sesión 2026-07-14 (2) — Infraestructura de evaluación con etiquetas manuales

## Fecha

2026-07-14 (segunda sesión del día)

## Objetivo de la sesión

Implementar la infraestructura de evaluación del roadmap de mediano plazo (`scripts/evaluate.py` con matriz de confusión, precision/recall/F1, AUROC y Brier) y desbloquear la recomendación #3 de la sesión 2026-07-08 (etiquetado manual de muestra estratificada), generando la hoja de etiquetado ciego lista para capturar.

## Estado verificado al inicio

- Working tree con los cambios de las sesiones 2026-07-08 y 2026-07-14 sin commitear, consistentes con la bitácora.
- Suite base: **187 tests pasando**; `ruff check .` limpio.
- Nota operativa: esta sesión se lanzó en un worktree de git (`.claude/worktrees/emergency-call-auditor-20ac57`) basado en el HEAD commiteado, que **no contiene** las dos sesiones sin commitear. Para no duplicar trabajo ni generar conflictos, la auditoría se realizó directamente sobre el checkout principal (donde vive el estado real) con cambios exclusivamente aditivos. El worktree quedó intacto y puede descartarse. **Recordatorio: commitear las sesiones pendientes reduciría este riesgo en el futuro.**

## Archivos creados

- `src/evaluation/__init__.py`, `src/evaluation/metrics.py` — métricas puras sin dependencia de sklearn: matriz de confusión, precision/recall/F1 por clase (con `None` para casos no evaluables en lugar de ceros engañosos), exactitud, macro-F1, AUROC por rangos (Mann-Whitney con corrección de empates) y Brier score.
- `src/evaluation/sampling.py` — `stratified_labeling_sample` (todas las DUDOSAS/IMPROCEDENTES + N SERIAS con semilla reproducible, excluye registros sin categoría válida como `call_506`) y `normalize_label` (tolera mayúsculas/minúsculas, espacios y acentos en la captura manual).
- `scripts/evaluate.py` — CLI con dos subcomandos: `sample` genera `reportes/muestra_etiquetado.csv` (protegido contra sobrescritura accidental de etiquetas ya capturadas; `--force` para regenerar) y `evaluate` cruza las etiquetas con `clasificacion_dataset.csv` y escribe `reportes/reporte_evaluacion.md`.
- `tests/test_evaluation.py` — 23 tests (matriz, métricas por clase, AUROC con separación perfecta/invertida/empates/una sola clase, Brier, normalización de etiquetas, estratificación reproducible).
- `reportes/muestra_etiquetado.csv` — hoja de etiquetado generada: **50 llamadas (35 DUDOSAS + 15 SERIAS, semilla 20260714), pendiente de captura manual**.

## Archivos modificados

- `pyproject.toml` — per-file-ignore E402 para `scripts/*` (mismo bootstrap de `sys.path` que `procesar_dataset.py`).
- `README.md` — sección "Evaluacion contra etiquetas manuales" y mención de `test_evaluation.py`.

## Decisiones de diseño

1. **Etiquetado ciego**: la hoja de etiquetado NO incluye la categoría, confianza ni scores del sistema — solo archivo, ruta, duración y transcripción. Mostrar la predicción sesgaría al etiquetador (anclaje); el cruce con el sistema lo hace `evaluate` por nombre de archivo. Además la muestra se ordena por archivo para no agrupar por categoría.
2. **Sin sklearn**: con decenas de llamadas etiquetadas las fórmulas cerradas son suficientes, auditables línea por línea y no agregan dependencia. Si en la fase de modelos supervisados se incorpora scikit-learn, estas métricas servirán de verificación cruzada.
3. **`None` en lugar de 0 para métricas no evaluables** (clase sin predicciones o sin ejemplos): distingue "no medible con esta muestra" de un cero real; macro-F1 excluye clases sin soporte.
4. **Evaluación incremental**: `evaluate` acepta hojas parcialmente etiquetadas (evalúa lo capturado, reporta pendientes) para permitir iterar sin esperar las 50 llamadas; etiquetas no reconocidas abortan con lista explícita en vez de descartarse en silencio.

## Justificación técnica

R1 (calibración de umbrales sin datos etiquetados) sigue siendo el riesgo más alto del proyecto y todas las decisiones de calibración pendientes (peso de `voice_tremor_score`, corrección del sesgo "911"/DT-11, umbrales de confianza) están bloqueadas por la falta de métricas reales. Esta sesión elimina el único impedimento de ingeniería: ya existe la muestra a etiquetar y el cálculo automático de métricas; lo restante (escuchar 50 audios y capturar etiquetas) es trabajo de dominio, no de código.

## Validaciones realizadas

- `ruff check .` sin hallazgos; suite completa: **210 tests pasando** (187 previos + 23 nuevos, 0 regresiones).
- `sample` ejecutado sobre el dataset real: 50 filas, columnas correctas, `etiqueta_manual` vacía, excluye el registro fallido `call_506`.
- Protección de sobrescritura verificada (segundo `sample` aborta con mensaje) y ruta de error de `evaluate` sin etiquetas verificada.
- `evaluate` end-to-end con 12 etiquetas sintéticas en directorio temporal: matriz, métricas por clase, AUROC y Brier correctos; reporte Markdown válido. El archivo temporal se eliminó; `muestra_etiquetado.csv` quedó sin contaminar.

## Problemas detectados

- El límite MAX_PATH de Windows (260 caracteres) impide escribir en rutas muy profundas (afectó al scratchpad del worktree durante las pruebas). No afecta al proyecto, pero conviene tenerlo presente para rutas de salida configurables.

## Riesgos detectados

- Riesgo bajo: todo el cambio es aditivo; ningún módulo del pipeline fue tocado.
- Las métricas con 50 llamadas tendrán intervalos de confianza amplios (especialmente IMPROCEDENTE, con 0 casos en el dataset); el reporte lo documenta en las notas metodológicas.

## Recomendaciones para la siguiente auditoría

1. **Capturar las etiquetas manuales** de `reportes/muestra_etiquetado.csv` (trabajo de dominio del autor) y ejecutar `python scripts/evaluate.py evaluate` — desbloquea la calibración basada en evidencia.
2. Reprocesar los 11 audios con transcripción sospechosa usando modelo `base` (pendiente de 2026-07-08; sigue siendo la prioridad de datos).
3. Con las métricas reales disponibles, decidir la corrección del sesgo DT-11 ("911"/dígitos) midiendo su impacto en recall/precision en lugar de a ciegas.
4. **Commitear el trabajo acumulado**: tres sesiones sin commitear elevan el riesgo de pérdida y complican los worktrees.

---

# Sesión 2026-07-14 (3) — Reprocesamiento selectivo y retranscripción de audios sospechosos

## Fecha

2026-07-14 (tercera sesión del día, continuación solicitada por el autor)

## Objetivo de la sesión

Ejecutar la prioridad marcada del roadmap: retranscribir los 11 audios con alertas de calidad usando el modelo `base` de Whisper y los parámetros anti-alucinación (resuelve DT-12). Requería una capacidad nueva: reprocesamiento selectivo del checkpoint sin tocar los otros 304 registros.

## Archivos modificados

- `procesar_dataset.py` — nuevos flags `--redo-sospechosos` (reprocesa registros con alertas de calidad) y `--redo-archivo NOMBRE` (repetible, admite registros con error); función `select_redo_paths` (retro-rellena calidad en checkpoints antiguos antes de filtrar, ignora archivos ya inexistentes) y `remove_category_copies` (borra copias huérfanas en `dataset_clasificado/` cuando la categoría cambia); comparación antes→después impresa al final; exclusión mutua con `--report-only`; docstring actualizado.
- `tests/test_procesar_dataset.py` (nuevo) — 6 tests de la selección y la limpieza de copias.
- `reportes/muestra_etiquetado.csv` — regenerada tras el reprocesamiento (49 llamadas: 34 DUDOSAS + 15 SERIAS); era seguro porque aún no había etiquetas capturadas y así la hoja refleja la estratificación y transcripciones vigentes.
- `clasificacion_dataset.{csv,json}`, `RESUMEN_DATASET.md`, `clasificacion_dataset.partial.jsonl`, `dataset_clasificado/` — regenerados por el batch.

## Decisiones de diseño

1. **El checkpoint no se reescribe**: los registros reprocesados se anexan al JSONL y superseden a los antiguos porque `load_checkpoint` conserva la última línea por ruta. Las versiones anteriores quedan en el archivo como rastro auditable (y respaldo adicional en `%TEMP%\backup_dataset_zdu55k8d`).
2. **Limpieza de copias por categoría**: al reprocesar se borran las copias del audio en todas las carpetas de `dataset_clasificado/` antes de copiar a la nueva categoría; sin esto, un cambio de categoría dejaba la copia vieja huérfana.

## Resultados del reprocesamiento (11 audios, modelo base, 3 workers, 3m03s)

| Audio | Antes | Después | Cambio relevante |
|---|---|---|---|
| call_288 | SERIA (0.75) repetitiva+caracteres | SERIA (1.00) sin alertas | Alucinación multilingüe eliminada |
| call_569 | SERIA (0.43) muy corta | SERIA (0.85) sin alertas | Transcripción completa recuperada |
| call_73 | SERIA (0.59) muy corta | SERIA (0.88) sin alertas | Transcripción completa recuperada |
| call_716 | SERIA (0.72) repetitiva | SERIA (0.83) sin alertas | Limpia |
| call_607 | DUDOSA (0.70) repetitiva | DUDOSA (0.82) sin alertas | Limpia |
| call_361 | DUDOSA (0.69) repetitiva | SERIA (0.72) | **Cambio de categoría** |
| call_59 | DUDOSA (0.68) muy corta | SERIA (0.70) | **Cambio de categoría** |
| call_494 | SERIA (0.67) repetitiva | DUDOSA (0.73) | **Cambio de categoría** |
| call_160, call_507, call_521 | SERIA repetitiva | SERIA, siguen con alerta | Repetición persiste con `base` |

- Transcripciones sospechosas: **11 → 6**. Distribución: SERIA 281 / DUDOSA 34 (antes 280/35).
- Los 11 registros reprocesados ya incluyen las features acústicas nuevas de 2026-07-14 (jitter, shimmer, forma espectral); DT-13 sigue vigente para los otros 304.
- `call_506.mp3` (HTML corrupto) ya no está en el dataset (315 audios encontrados, 0 errores): el pendiente de descartarlo queda cerrado.
- Las 6 alertas persistentes pueden ser repetición genuina (pánico) y no alucinación: son candidatas naturales a revisión durante el etiquetado manual (4 de ellas están en la muestra por diseño).

## Validaciones realizadas

- Suite completa: **216 tests pasando** (210 previos + 6 nuevos, 0 regresiones); `ruff check .` limpio.
- Consistencia post-batch verificada: conteos por categoría, migración de copias (`call_494` de `seria/` a `dudosa/`, `call_361` de `dudosa/` a `seria/`), checkpoint con líneas duplicadas resueltas por última-línea-gana, hoja de etiquetado sin etiquetas perdidas (tenía 0 capturadas antes de regenerar).
- Respaldo previo de `clasificacion_dataset.{csv,json}`, checkpoint y `RESUMEN_DATASET.md` en `%TEMP%\backup_dataset_zdu55k8d`.

## Riesgos detectados

- Riesgo bajo: el reprocesamiento solo tocó los 11 registros seleccionados; el resto del checkpoint quedó bit a bit intacto.
- Los 3 cambios de categoría muestran que la clasificación de llamadas con ASR degradado es sensible al motor de transcripción: refuerza la necesidad del etiquetado manual como árbitro (las etiquetas se hacen escuchando el audio, no leyendo la transcripción).

## Recomendaciones para la siguiente auditoría

1. **Capturar las etiquetas manuales** de `reportes/muestra_etiquetado.csv` (49 llamadas) y correr `python scripts/evaluate.py evaluate` — sigue siendo el desbloqueador principal.
2. Evaluar si conviene reprocesar TODO el dataset con `base` (los 3 cambios de categoría en 11 audios sugieren que `tiny` introduce ruido de clasificación medible); decidir tras ver las métricas del etiquetado.
3. Backfill acústico de los 304 registros restantes sin features nuevas (DT-13) — puede implementarse como `--redo-acustico` reutilizando la infraestructura de esta sesión, sin retranscribir.
4. Commitear el trabajo acumulado (DT-16, ahora cuatro sesiones sin commitear).

---

# Sesión 2026-07-15 — Backfill acústico y dataset de features para entrenamiento supervisado

## Fecha

2026-07-15

## Objetivo de la sesión

Cerrar DT-13 (registros del checkpoint sin features acústicas) y desbloquear el prerequisito de la fase de modelos supervisados: persistir el vector completo de features acústicas por llamada y exportarlo en formato tabular de entrenamiento.

## Estado verificado al inicio

- Working tree consistente con la bitácora (cinco sesiones sin commitear, incluida esta).
- Suite base: **216 tests pasando**; `ruff check .` limpio.
- Hoja de etiquetado `reportes/muestra_etiquetado.csv`: 49 filas, **0 etiquetas capturadas** — la evaluación con métricas sigue bloqueada por trabajo de dominio, no de ingeniería.
- **Hallazgo clave**: el checkpoint no persistía *ninguna* feature acústica — los registros solo guardan transcripción y scores finales. DT-13 (304 registros sin las features de 2026-07-14) era en realidad más profundo: los 315 registros carecían de vector de features, lo que bloqueaba por completo la exportación para entrenamiento supervisado (recomendación 5.5 de la primera auditoría).

## Archivos modificados

- `procesar_dataset.py` — persistencia de features, modo `--redo-acustico` y CSV de entrenamiento
- `tests/test_procesar_dataset.py` — 5 tests nuevos
- `README.md` — sección "Dataset de features para entrenamiento supervisado"
- `clasificacion_dataset.{csv,json}`, `RESUMEN_DATASET.md`, `clasificacion_dataset.partial.jsonl`, `features_dataset.csv` (nuevo) — regenerados/creados por el backfill

## Cambios implementados

1. **Vector de features persistido en el checkpoint**: `_analyze_audio` ahora incluye `features_acusticas` en cada registro — un dict aplanado con orden canónico (`ACOUSTIC_FEATURE_FIELDS`, 63 campos): 25 escalares (energía, F0, jitter, shimmer, forma espectral, silencios, tempo, SNR, clipping), 26 columnas MFCC (media y desviación de 13 coeficientes expandidos con `flatten_acoustic_features`), 10 indicadores acústicos de emergencia, calidad de audio y flags de anomalías serializados como texto.
2. **Modo `--redo-acustico`**: recalcula features y re-puntúa los registros ok del checkpoint que no tienen `features_acusticas`, **reutilizando la transcripción guardada** — los workers no cargan Whisper (`_init_worker(load_model=False)`), lo que reduce el costo de ~60 s/audio a ~1-2 s/audio. Preserva `modelo_asr`, idioma y status de transcripción del registro original; los registros con error se excluyen (no tienen transcripción que reutilizar; para esos existe `--redo-archivo`). Incompatible con `--fresh`, `--report-only` y los otros `--redo-*` (pools con y sin Whisper no se mezclan). Los audios sin registro previo se omiten con aviso.
3. **`features_dataset.csv` (nuevo export)**: una fila por llamada con 8 columnas de contexto/objetivo (archivo, categoría, confianza, scores, recomendación, calidad de transcripción) + las 63 de features. Es la tabla de entrada para los modelos baseline (regresión logística, random forest, SVM). Solo se genera si hay registros con features (no crea archivos vacíos engañosos).
4. **Backfill ejecutado sobre el dataset real**: 315/315 registros en **2 minutos** (4 workers, sin ASR), 0 errores. Verificación de regresión contra respaldo previo: **0 cambios de categoría, 0 cambios de confianza, 0 cambios de scores** — esperado, porque las features de 2026-07-14 son informativas y no participan del scoring. El checkpoint conserva las 642 líneas (viejas + nuevas) como rastro auditable; respaldo adicional en el scratchpad de la sesión.
5. **Tests**: 5 nuevos (221 en total) — aplanado con claves canónicas exactas, aplanado de `empty_acoustic_features`, selección de backfill (excluye registros con features, con error y archivos borrados), CSV de features solo con filas válidas, y no-creación del CSV sin features.

## Justificación técnica

La fase de modelos supervisados del roadmap requiere dos insumos: etiquetas manuales (trabajo de dominio, pendiente) y el vector de features por llamada (trabajo de ingeniería, resuelto aquí). Persistir las features en el checkpoint además elimina la asimetría que causó DT-13: hasta ahora cada mejora del extractor acústico dejaba obsoletos los registros históricos sin forma barata de actualizarlos; con `--redo-acustico` cualquier feature futura se retro-propaga al dataset completo en minutos y sin retranscribir. El diseño reutiliza la infraestructura de reprocesamiento selectivo de 2026-07-14 (3) (checkpoint append-only, limpieza de copias por categoría, comparación antes→después).

## Impacto esperado

- **Precisión**: sin cambio inmediato (verificado: 0 diferencias); habilita la mejora futura basada en modelos entrenados.
- **Mantenibilidad**: las features dejan de ser efímeras; recalibrar o añadir features ya no exige reprocesar el ASR (~80 min) sino solo el análisis acústico (~2 min).
- **Escalabilidad**: `features_dataset.csv` con 71 columnas listo para pandas/scikit-learn sin tocar el pipeline.

## Problemas detectados

- DT-14 (`.tmp_pytest*` bloqueados) **no pudo resolverse desde esta sesión**: `takeown`/`icacls`/`Remove-Item` devuelven acceso denegado incluso con reset de ACLs. Requiere una consola con privilegios de administrador (o reinicio) por parte del autor: `takeown /f .tmp_pytest /r /d s && icacls .tmp_pytest /reset /t && rmdir /s /q .tmp_pytest` (repetir para `_cache` y `_run`).
- La hoja de etiquetado sigue sin etiquetas capturadas: todas las decisiones de calibración (peso del temblor, sesgo DT-11, umbrales de confianza) siguen bloqueadas por este paso de dominio.

## Riesgos detectados

- Riesgo bajo: el backfill re-puntuó con el pipeline actual usando transcripciones intactas; la verificación contra respaldo confirmó cero desviaciones.
- El tamaño del checkpoint crece con cada redo (642 líneas para 315 audios); es intencional (auditabilidad), pero si algún día se compacta debe conservarse la semántica última-línea-gana.

## Validaciones realizadas

- `ruff check .` sin hallazgos; suite completa: **221 tests pasando** (216 previos + 5 nuevos, 0 regresiones).
- Smoke test aislado de `--redo-acustico` con 3 audios en directorio de salida temporal antes de tocar los reportes reales.
- Backfill completo: 315 registros, 0 errores, comparación antes→después impresa sin ningún cambio.
- Diff programático del `clasificacion_dataset.csv` regenerado contra el respaldo pre-backfill: 0 diferencias en categoría/confianza/scores/recomendación.
- `features_dataset.csv`: 316 líneas (cabecera + 315), 71 columnas, valores en rangos plausibles.
- Smoke test CLI: `python main.py --transcript data/audios/test_emergencia.txt` → `escalar_humano`, score 0.9, idéntico al histórico.
- `reportes/muestra_etiquetado.csv` intacta (el backfill no la toca).

## Recomendaciones para la siguiente auditoría

1. **Capturar las etiquetas manuales** de `reportes/muestra_etiquetado.csv` (49 llamadas) y correr `python scripts/evaluate.py evaluate` — sigue siendo el único desbloqueador de la calibración; ya no queda ingeniería pendiente para ese flujo.
2. Con etiquetas + `features_dataset.csv` disponibles, entrenar los **modelos baseline** (regresión logística, random forest) y comparar recall de SERIA contra el sistema heurístico.
3. Commitear el trabajo acumulado (DT-16, ya cinco sesiones sin commitear).
4. Resolver DT-14 desde una consola de administrador (comando documentado arriba).
5. Evaluar análisis exploratorio del `features_dataset.csv` (distribuciones, correlaciones feature↔categoría) como insumo para elegir features del modelo baseline; puede hacerse antes del etiquetado.

## Deuda técnica

- Se cierra DT-13. DT-14 y DT-16 permanecen (ver sección viva).

## Observaciones

- Decisión de diseño: las features se persisten *aplanadas* (no el dict anidado de `extract_acoustic_features`) para que el checkpoint y el CSV compartan el mismo esquema estable y el CSV no dependa de la estructura interna del extractor.
- El nombre de cada columna coincide con el de la feature original (MFCCs como `mfcc_mean_01..13`/`mfcc_std_01..13`), de modo que la literatura y el código usan el mismo vocabulario.

---

## Roadmap Técnico

> Sección viva. Actualizada por última vez: 2026-07-15.

### Corto plazo

- [x] Extraer `_clamp` y `_optional_float` a `src/utils/helpers.py` — **completado 2026-07-07**
- [x] Ampliar tests de `emergency_indicators.py` (indicadores individuales, `indicator_flags`, `audio_reliability`) — **completado 2026-07-08 (19 tests nuevos)**
- [x] Conectar `AudioAnalysisConfig` al pipeline de features (ventana de análisis precomputada + `f0_min_hz`/`f0_max_hz`) — **completado 2026-07-08**
- [x] Agregar tests de integración end-to-end (`run_pipeline` con `.wav` sintético generado con `soundfile`) — **completado 2026-07-14 (6 tests)**
- [x] Configurar `ruff` como linter con `pyproject.toml` — **completado 2026-07-14**
- [x] Jitter y shimmer (aproximados con librosa) + `voice_tremor_score` + rolloff/bandwidth/flatness espectrales — **completado 2026-07-14**
- [x] Reprocesar los 11 audios con transcripción sospechosa usando modelo `base` y los nuevos parámetros anti-alucinación — **completado 2026-07-14 (3): sospechosos 11 → 6, tres cambios de categoría**
- [ ] Etiquetado manual de muestra estratificada (34 DUDOSAS + 15 SERIAS) para métricas reales — **siguiente prioridad; hoja de etiquetado ciego regenerada el 2026-07-14 (3) en `reportes/muestra_etiquetado.csv` (49 llamadas); falta capturar etiquetas y correr `scripts/evaluate.py evaluate`**
- [ ] Archivar `2do avance.md` en `docs/archivo/` (requiere confirmación del autor)
- [x] Reemplazar o descartar `call_506.mp3` — **cerrado 2026-07-14 (3): el archivo ya no está en el dataset (315 audios, 0 errores)**
- [x] Backfill acústico de los registros sin features persistidas — **completado 2026-07-15: `--redo-acustico` implementado y ejecutado sobre los 315 registros (2 min, 0 errores, 0 cambios de clasificación); `features_dataset.csv` generado**

### Mediano plazo

- [ ] Dataset etiquetado de 30-50 llamadas simuladas (seria/dudosa/improcedente)
- [x] Script `scripts/evaluate.py` con recall, precision, F1 y AUROC (matriz de confusión) — **completado 2026-07-14 (2); la validación cruzada queda para la fase de modelos supervisados**
- [ ] Corregir sesgo del token "911"/dígitos sueltos en `EMERGENCY_TERMS` y `_has_address_like_text` (DT-11; requiere decisión de negocio)
- [ ] Evaluar `faster-whisper` como motor ASR alternativo

### Largo plazo

- [ ] Modelos baseline supervisados (regresión logística, random forest, SVM) sobre CSV de features — **el insumo de features ya existe (`features_dataset.csv`, 2026-07-15); solo falta el etiquetado manual**
- [ ] Interfaz Streamlit para visualización interactiva
- [ ] Esquema JSON `2.0`: eliminar claves duplicadas del nivel raíz (la versión 1.1 con `schema_version` ya existe desde 2026-07-14)
- [ ] Jitter y shimmer ciclo a ciclo exactos con `parselmouth` (comparar contra las aproximaciones de 2026-07-14)
- [ ] Integrar `voice_tremor_score` a `seriousness_audio_score` con pesos derivados del etiquetado manual
- [ ] Diarización de hablantes y análisis por segmentos (chunking)

---

## Deuda Técnica

> Sección viva. Actualizada por última vez: 2026-07-15.

### Alta

| ID | Componente | Descripción |
|---|---|---|
| DT-11 | `text_analyzer.py` | Sesgo: "911" en `EMERGENCY_TERMS` y `\b\d{2,5}\b` en `_has_address_like_text` hacen que casi toda llamada 911 real active keywords y `has_location` (detectado con el dataset 2026-07-08) |

### Media

| ID | Componente | Descripción |
|---|---|---|
| DT-14 | Tooling | Directorios `.tmp_pytest*` en la raíz con permisos dañados (Windows); irrecuperables sin consola de administrador (intento con `takeown`/`icacls` falló el 2026-07-15; comando documentado en esa sesión). Usar el basetemp por defecto de pytest |

### Baja

| ID | Componente | Descripción |
|---|---|---|
| DT-6 | JSON de salida | `recommendation` y `evidence` duplicados en nivel raíz (limpieza planificada para esquema 2.0) |
| DT-8 | Documentación | `2do avance.md` obsoleto en la raíz |
| DT-15 | Tooling | Sin type checker (`mypy`/`pyright`) configurado (el linter `ruff` ya quedó configurado en 2026-07-14) |

### Resueltas

| ID | Descripción | Resuelta en |
|---|---|---|
| DT-16 | Cinco sesiones de trabajo (2026-07-08 a 2026-07-15) sin commitear | 2026-07-15 (commit `7d48a48`; incluye limpieza de `.pyc` del índice y retiro de `docs/2do avance.md`) |
| DT-13 | Registros del checkpoint sin features acústicas persistidas (bloqueaba la exportación para entrenamiento supervisado) | 2026-07-15 |
| DT-12 | Checkpoint transcrito con Whisper tiny sin parámetros anti-alucinación; 11 transcripciones sospechosas | 2026-07-14 (3) |
| DT-7 | Sin campo `schema_version` en el JSON de salida | 2026-07-14 |
| DT-9 | Ningún test ejecutaba el pipeline completo end-to-end | 2026-07-14 |
| DT-10 | Sin linter configurado | 2026-07-14 |
| DT-1 | Solo 3 tests para `emergency_indicators.py`, la heurística más compleja | 2026-07-08 |
| DT-2 | `_clamp` y `_optional_float` duplicados en 3 módulos (5 definiciones) | 2026-07-07 |
| DT-3 | `f0_min_hz`, `f0_max_hz` definidos pero nunca usados | 2026-07-08 |
| DT-4 | `_analysis_window` se recalculaba 4 veces por llamada | 2026-07-08 |
| DT-5 | `analysis_window_seconds` definido en config pero ignorado | 2026-07-08 |
