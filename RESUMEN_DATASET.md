# Resumen de clasificacion del dataset 911

Fecha de generacion: 2026-07-15 14:02:01
Ruta analizada: `C:\Users\dotis\Documents\Detecciones de comportamientos en agentes\Investigaciones\Metodologia\subagente_seriedad\data\audios\911_recordings`
ASR: openai-whisper-local-tiny (idioma forzado: en)

## Totales

- Total de audios encontrados: **315**
- Total de audios procesados: **315**
- Procesados con exito: **315**
- Con error: **0**

## Distribucion por categoria

| Categoria | Total | Porcentaje | Confianza media | Seriedad media |
|---|---:|---:|---:|---:|
| SERIA | 281 | 89.2% | 0.91 | 0.95 |
| DUDOSA | 34 | 10.8% | 0.88 | 0.43 |
| IMPROCEDENTE | 0 | 0.0% | - | - |

## Duraciones

- Duracion promedio: 170.3 s
- Duracion minima: 9.8 s
- Duracion maxima: 299.5 s
- Duracion total de audio procesado: 14:54:02 (53642 s)
- Tiempo total de procesamiento (wall clock): 00:02:00

## Clasificaciones de baja confianza (< 0.60)

No se detectaron clasificaciones por debajo del umbral.

## Transcripciones sospechosas

Se detectaron **6** transcripciones con senales de baja calidad (muy cortas, repetitivas o con caracteres inesperados). Su evidencia semantica es poco confiable y conviene revisarlas manualmente:

| archivo | categoria | confianza | calidad | alertas |
|---|---|---:|---:|---|
| call_160.mp3 | SERIA | 0.71 | 0.60 | transcripcion_repetitiva |
| call_361.mp3 | SERIA | 0.72 | 0.60 | transcripcion_repetitiva |
| call_59.mp3 | SERIA | 0.70 | 0.60 | transcripcion_muy_corta |
| call_507.mp3 | SERIA | 0.81 | 0.65 | transcripcion_repetitiva |
| call_521.mp3 | SERIA | 0.81 | 0.71 | transcripcion_repetitiva |
| call_494.mp3 | DUDOSA | 0.73 | 0.75 | transcripcion_repetitiva |

## Errores

No se registraron errores de procesamiento.

## Observaciones

- El dataset proviene de grabaciones reales de despacho 911 en ingles; el pipeline uso los diccionarios bilingues (es/en) del analizador semantico.
- El dataset fue previamente filtrado por duracion (solo audios <= 5 min, ver `reportes/reporte_filtrado_duracion.md`).
- Los audios se COPIARON a `dataset_clasificado/` para conservar el dataset original intacto.
- 6 transcripciones fueron marcadas como sospechosas; su confianza fue reducida automaticamente y la alerta quedo registrada en la justificacion.
- Confianza promedio de clasificacion: 0.91.
- La clasificacion es heuristica y auditable, no un modelo entrenado; no debe usarse para cerrar llamadas automaticamente.
