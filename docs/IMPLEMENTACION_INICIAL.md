# Implementacion inicial del subagente de seriedad de llamadas

## Resumen

Se implemento un MVP offline/local en Python para procesar una transcripcion manual o un archivo de audio, extraer senales acusticas, analizar contenido semantico y generar un score probabilistico con recomendacion operativa.

El sistema mantiene la restriccion de seguridad principal: no cuelga, no cierra llamadas y no afirma que una llamada sea falsa. Solo entrega una estimacion bajo incertidumbre.

## Que se mejoro

- La rama acustica dejo de depender solo de duracion, energia basica y silencio.
- `main.py` acepta `--model tiny|base|small` para seleccionar Whisper local.
- El JSON de salida incluye una seccion `acoustic_features` mas completa.
- El score final ahora combina senales semanticas, completitud, coherencia y caracteristicas acusticas.
- La evidencia incluye mensajes de la rama acustica, por ejemplo:
  - Alta proporcion de silencio.
  - Energia vocal baja.
  - Audio con posible mala calidad.
  - Variabilidad acustica detectada.
  - Pausas prolongadas detectadas.
- La politica de decision incorpora baja confianza y anomalias acusticas sin recomendar cierre automatico.

## Componentes multimodales actuales

### Rama acustica

Implementada en `src/audio/acoustic_features.py` y `src/audio/vad.py`.

Extrae:

- Duracion.
- RMS y energia promedio.
- Energia maxima.
- Desviacion de energia.
- Amplitud pico.
- Zero crossing rate.
- Tempo aproximado cuando aplica.
- Proporcion de silencio.
- Numero aproximado de pausas.
- Duracion promedio y maxima de pausas.
- F0 promedio, minimo, maximo y desviacion cuando `librosa.pyin` puede estimarlo.
- Calidad aproximada de audio.
- Clipping aproximado.
- SNR aproximado.
- Banderas de anomalia acustica.

### Rama semantica

Implementada en `src/semantic/`.

Extrae:

- Palabras de emergencia.
- Palabras asociadas a broma o burla.
- Ubicacion aproximada.
- Personas afectadas.
- Tipo de incidente.
- Completitud de informacion.
- Intencion estimada.
- Coherencia, evasivas, contradicciones simples y cambios de tema.

### Fusion y decision

Implementada en `src/scoring/`.

Combina:

- Seriedad semantica.
- Completitud.
- Coherencia.
- Riesgo alto.
- Senales acusticas anomalas.
- Calidad del audio.
- Confianza estimada.

## Como ejecutar

Con audio y Whisper `tiny`:

```powershell
python main.py --audio data\audios\1757078926.92210.mp3 --model tiny
```

Con transcripcion manual:

```powershell
python main.py --transcript data\audios\ejemplo.txt
```

Los resultados se guardan en `data/outputs/`.

## Limitaciones de Whisper en CPU

- `tiny` suele ser viable para pruebas rapidas, pero puede transcribir peor.
- `base` mejora precision, con mas tiempo de ejecucion.
- `small` puede ser lento en CPU y consumir mas memoria.
- Audios largos o con ruido pueden tardar bastante.
- Whisper puede cometer errores con acentos, ruido, multiples voces, baja calidad o palabras locales.
- El sistema no asume GPU.

## Pendiente

- Validar umbrales acusticos con audios etiquetados.
- Agregar pruebas unitarias para scoring y politica de decision.
- Medir precision, recall, F1 y matriz de confusion.
- Calibrar probabilidades con datos reales.
- Separar voz de ruido o multiples hablantes.
- Anonimizar datos sensibles.
- Implementar un dataset tabular de features para modelos baseline.
- Evaluar `faster-whisper` como alternativa local mas eficiente.

## Recomendaciones para fase 2

- Crear un conjunto de llamadas simuladas y anonimizadas con etiquetas: seria, dudosa, posible improcedente.
- Priorizar recall alto para llamadas serias.
- Entrenar modelos baseline clasicos antes de considerar CNN-LSTM.
- Registrar version de reglas, features y dependencias en cada JSON.
- Agregar pruebas de regresion con audios cortos `.wav`, `.mp3` y `.m4a`.
- Agregar un reporte de auditoria por llamada con razones separadas por rama acustica y semantica.
- Mantener supervision humana para llamadas criticas o de baja confianza.

## Fuera de alcance actual

- APIs de pago.
- Telefonia real.
- Twilio, SIP, WebRTC o streaming.
- Entrenamiento CNN-LSTM.
- Uso obligatorio de GPU.
- Cierre automatico o descarte automatico de llamadas.
