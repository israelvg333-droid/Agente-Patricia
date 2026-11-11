# Metodología para implementar en Python un subagente de estimación de seriedad de llamadas

> Documento metodológico basado en la propuesta inicial del subagente conversacional multimodal, adaptado para una implementación progresiva en Python.  
> El objetivo no es detectar bromas con certeza absoluta, sino estimar probabilísticamente la seriedad de una llamada y apoyar al agente principal en la toma de decisiones.

---

## 1. Nombre tentativo del módulo

**Subagente de Estimación de Seriedad de Llamadas en Tiempo Real**  
También puede nombrarse como:

- Módulo Inteligente de Evaluación de Seriedad de Llamadas.
- Subagente de Validación Conversacional.
- Módulo de Detección de Llamadas Improcedentes.
- Evaluador Multimodal de Seriedad.

---

## 2. Objetivo general

Diseñar e implementar en Python un subagente conversacional capaz de analizar señales acústicas y semánticas de una llamada para estimar su nivel de seriedad, detectar posibles llamadas improcedentes o de broma y entregar una señal estructurada al agente principal de atención o clasificación de incidentes.

El sistema debe funcionar inicialmente como **herramienta de apoyo**, no como mecanismo automático para cerrar llamadas.

---

## 3. Enfoque metodológico

La metodología se basa en un enfoque **multimodal**, porque la seriedad de una llamada no puede evaluarse de forma confiable usando únicamente el audio o únicamente el texto.

Se proponen dos ramas principales:

1. **Rama acústica**  
   Analiza cómo habla la persona.

2. **Rama semántica**  
   Analiza qué dice la persona.

Ambas ramas se fusionan para generar un **score de seriedad** y una recomendación operativa.

---

## 4. Planteamiento del problema

En sistemas de atención ciudadana, emergencias o reportes de incidentes pueden existir llamadas de broma, llamadas improcedentes, llamadas incompletas o reportes falsos. Estas llamadas pueden consumir recursos, saturar operadores y retrasar la atención de incidentes reales.

Sin embargo, detectar una broma automáticamente es una tarea delicada porque existen casos reales donde la persona puede sonar nerviosa, confundida, incoherente o poco clara. Por ello, el problema debe formularse como:

> **Estimación probabilística de seriedad bajo incertidumbre.**

No se recomienda plantearlo como:

> “Detector definitivo de bromas”.

---

## 5. Hipótesis de trabajo

**Hipótesis principal:**

> Un sistema multimodal que combine señales acústicas como prosodia, energía, pausas, ritmo y F0, junto con señales semánticas obtenidas mediante ASR, análisis de intención, coherencia conversacional y reglas del dominio, permitirá estimar la seriedad de una llamada con mayor robustez que un sistema basado solamente en audio o solamente en texto.

**Hipótesis secundarias:**

1. La rama acústica permite obtener señales tempranas antes de contar con suficiente contenido textual.
2. La rama semántica ayuda a reducir falsos positivos generados por nerviosismo, confusión o expresividad emocional legítima.
3. Los modelos simples pueden servir como línea base antes de implementar redes profundas.
4. La supervisión humana seguirá siendo necesaria en llamadas críticas, ambiguas o de baja confianza.

---

## 6. Evaluación de costos

La implementación puede hacerse con distintos niveles de costo. Para iniciar, se recomienda una versión **local y gratuita** en Python.

### 6.1 Componentes que pueden ser gratuitos

| Componente | Puede ser gratis | Herramientas sugeridas |
|---|---:|---|
| Lenguaje base | Sí | Python |
| Procesamiento de audio | Sí | librosa, torchaudio, scipy, pydub |
| Extracción de características | Sí | librosa, openSMILE, pyAudioAnalysis |
| Modelos clásicos | Sí | scikit-learn |
| Deep Learning | Sí | PyTorch o TensorFlow |
| ASR local | Sí | Whisper local, faster-whisper |
| Pruebas offline | Sí | Audios `.wav` o grabaciones internas |
| Visualización de resultados | Sí | Streamlit, Gradio, matplotlib, pandas |

### 6.2 Componentes que pueden generar costo

| Componente | Puede costar | Motivo |
|---|---:|---|
| ASR por API | Sí | Se cobra por minuto o por uso |
| OpenAI para análisis semántico | Sí | Se cobra por tokens |
| Text-to-Speech comercial | Sí | ElevenLabs, OpenAI TTS u otros proveedores pueden cobrar |
| Telefonía real | Sí | Twilio, SIP, WebRTC o proveedores telefónicos |
| GPU en la nube | Sí | Entrenamiento o inferencia acelerada |
| Dataset etiquetado | Sí | Recolección, anonimización y etiquetado humano |
| Almacenamiento en nube | Sí | Grabaciones, logs y auditoría |
| Despliegue en servidor | Sí | VPS, Docker, monitoreo, dominios, seguridad |

### 6.3 Conclusión de costos

Para una primera versión en Python, el proyecto **no necesita iniciar con gasto económico fuerte** si se trabaja con:

- audios grabados;
- Whisper local;
- extracción de features acústicos;
- modelos clásicos;
- dashboard local.

El costo aparecerá principalmente cuando se quiera:

- trabajar en tiempo real;
- usar telefonía real;
- usar APIs externas;
- entrenar modelos grandes;
- almacenar llamadas;
- desplegar en producción.

---

## 7. Cambios recomendados respecto a la propuesta completa

La propuesta original es sólida como arquitectura final, pero para implementarla en Python se recomienda simplificarla.

### 7.1 Cambios sugeridos

| Elemento de la propuesta completa | Recomendación para Python | Motivo |
|---|---|---|
| Telefonía en tiempo real desde el inicio | Cambiar por audios `.wav` o micrófono local | Reduce costo y complejidad |
| CNN-LSTM-MLP desde el inicio | Empezar con modelos clásicos | Se necesita dataset grande para deep learning |
| ASR en la nube | Usar Whisper local primero | Evita costo inicial |
| Retrieval avanzado | Usar reglas y catálogo simple al inicio | Más fácil de validar |
| Agente completamente autónomo | Usarlo como recomendador | Evita riesgos operativos |
| Cierre automático de llamadas | No implementarlo al inicio | Riesgo alto de falsos positivos |
| Detección binaria broma/no broma | Usar niveles de seriedad | Más realista y defendible |

---

## 8. Arquitectura propuesta para implementación en Python

### 8.1 Arquitectura MVP

```text
Audio de entrada
    |
    v
Preprocesamiento
    - Conversión a WAV
    - Normalización
    - Reducción básica de ruido
    - Segmentación
    |
    +----------------------------+
    |                            |
    v                            v
Rama acústica               Rama semántica
- energía                   - Whisper local
- F0                        - transcripción
- pausas                    - intención
- ritmo                     - coherencia
- duración                  - palabras clave
- features SER              - reglas del dominio
    |                            |
    +-------------+--------------+
                  |
                  v
        Fusión de características
                  |
                  v
          Clasificador inicial
                  |
                  v
        Score de seriedad
                  |
                  v
Recomendación al agente principal
- continuar
- pedir más información
- escalar a humano
- posible improcedente
```

---

## 9. Stack técnico recomendado

### 9.1 Librerías base

```bash
pip install numpy pandas scikit-learn matplotlib librosa soundfile pydub
```

### 9.2 Para ASR local

Opción 1: Whisper original

```bash
pip install openai-whisper
```

Opción 2: faster-whisper, recomendada si se busca mejor rendimiento

```bash
pip install faster-whisper
```

### 9.3 Para audio en tiempo real desde micrófono

```bash
pip install sounddevice soundfile
```

### 9.4 Para interfaz local

```bash
pip install streamlit
```

### 9.5 Para deep learning en fases posteriores

```bash
pip install torch torchaudio
```

---

## 10. Estructura sugerida del proyecto

```text
subagente_seriedad/
│
├── data/
│   ├── raw/
│   ├── processed/
│   └── labels.csv
│
├── notebooks/
│   ├── 01_exploracion_audio.ipynb
│   ├── 02_extraccion_features.ipynb
│   └── 03_entrenamiento_baseline.ipynb
│
├── src/
│   ├── audio_preprocessing.py
│   ├── acoustic_features.py
│   ├── asr_transcription.py
│   ├── semantic_features.py
│   ├── fusion.py
│   ├── train_model.py
│   ├── inference.py
│   └── policy.py
│
├── models/
│   ├── baseline_svm.pkl
│   ├── baseline_random_forest.pkl
│   └── mlp_model.pt
│
├── app/
│   └── streamlit_app.py
│
├── reports/
│   ├── metricas.md
│   └── matriz_confusion.png
│
├── requirements.txt
└── README.md
```

---

## 11. Fases de implementación

## Fase 0: Definición del alcance

### Objetivo

Definir qué se entenderá por llamada seria, dudosa, improcedente o posible broma.

### Actividades

- Definir etiquetas.
- Definir reglas de seguridad.
- Definir si se trabajará con audios reales, simulados o sintéticos.
- Definir qué datos pueden almacenarse legalmente.
- Establecer que el sistema no cerrará llamadas automáticamente.

### Salida esperada

Documento de criterios de clasificación.

Ejemplo de etiquetas:

```text
0 = improcedente o posible broma
1 = dudosa
2 = seria
```

O bien:

```text
score_seriedad = 0.0 a 1.0
```

---

## Fase 1: Recolección y preparación de datos

### Objetivo

Crear un dataset inicial para pruebas.

### Actividades

- Reunir audios en formato `.wav`.
- Separar audios por categoría.
- Anonimizar datos sensibles.
- Crear un archivo `labels.csv` con metadatos.

### Ejemplo de `labels.csv`

```csv
file,label_seriedad,urgencia,emocion,calidad_audio,observaciones
call_001.wav,seria,alta,estres,buena,reporte coherente
call_002.wav,dudosa,media,neutral,regular,respuestas vagas
call_003.wav,improcedente,baja,risa,buena,posible broma
```

### Salida esperada

Dataset organizado y listo para extracción de características.

---

## Fase 2: Preprocesamiento de audio

### Objetivo

Preparar el audio para análisis acústico y transcripción.

### Actividades

- Convertir audio a formato estándar.
- Normalizar volumen.
- Reducir ruido básico.
- Dividir en segmentos.
- Detectar silencios y pausas.

### Formato recomendado

```text
WAV
16 kHz
mono
PCM
```

### Salida esperada

Audios limpios y segmentados.

---

## Fase 3: Rama acústica

### Objetivo

Extraer variables acústicas relacionadas con prosodia, emoción y dinámica vocal.

### Features sugeridas

| Feature | Qué puede aportar |
|---|---|
| Energía RMS | Intensidad de la voz |
| F0 / pitch | Tono y variación tonal |
| Duración de pausas | Vacilaciones o cortes |
| Velocidad de habla | Urgencia o nerviosismo |
| MFCCs | Timbre y características espectrales |
| Zero Crossing Rate | Cambios rápidos en señal |
| Spectral centroid | Brillo o distribución espectral |
| Jitter / shimmer | Estabilidad vocal, si se calcula |

### Herramientas sugeridas

- `librosa`
- `torchaudio`
- `openSMILE`
- `pyAudioAnalysis`

### Salida esperada

Vector acústico por llamada o por segmento.

Ejemplo:

```text
[mean_energy, std_energy, mean_f0, std_f0, pause_ratio, speech_rate, mfcc_1, ..., mfcc_n]
```

---

## Fase 4: Rama semántica

### Objetivo

Transcribir y analizar el contenido textual de la llamada.

### Actividades

1. Transcribir audio con Whisper local.
2. Limpiar la transcripción.
3. Extraer palabras clave.
4. Detectar intención.
5. Evaluar coherencia conversacional.
6. Verificar si el reporte contiene información mínima.

### Variables semánticas sugeridas

| Variable | Descripción |
|---|---|
| Tipo de incidente detectado | incendio, robo, agresión, accidente, etc. |
| Dirección o ubicación mencionada | Presencia de lugar específico |
| Existencia de afectados | persona herida, víctima, testigo |
| Nivel de detalle | Bajo, medio, alto |
| Coherencia narrativa | Si mantiene el mismo relato |
| Respuestas evasivas | Si evita contestar preguntas básicas |
| Cambio de tema | Si rompe la dinámica conversacional |
| Palabras de burla | Risas, insultos, bromas explícitas |

### Salida esperada

Vector semántico por llamada.

Ejemplo:

```text
[has_location, has_incident_type, has_victim, contradiction_score, topic_shift_score, detail_score]
```

---

## Fase 5: Fusión de características

### Objetivo

Combinar la información acústica y semántica para generar una representación única de la llamada.

### Método inicial recomendado

Concatenación simple:

```text
features_finales = features_acusticas + features_semanticas
```

### Ejemplo

```text
[energía, F0, pausas, ritmo, MFCCs, ubicación, tipo_incidente, coherencia, evasión]
```

### Salida esperada

Dataset tabular listo para entrenamiento.

---

## Fase 6: Modelos iniciales

### Objetivo

Entrenar modelos base antes de implementar deep learning complejo.

### Modelos recomendados para empezar

| Modelo | Uso recomendado |
|---|---|
| Logistic Regression | Baseline simple e interpretable |
| Random Forest | Maneja relaciones no lineales |
| SVM | Útil con pocos datos y features bien diseñadas |
| MLP pequeño | Primer acercamiento neuronal |

### Modelos no recomendados al inicio

| Modelo | Motivo |
|---|---|
| CNN-LSTM desde cero | Requiere muchos datos etiquetados |
| Transformer propio | Alto costo y complejidad |
| Sistema 100% en tiempo real | Requiere infraestructura avanzada |

### Salida esperada

Primer clasificador con métricas básicas.

---

## Fase 7: Política de decisión

### Objetivo

Traducir el score del modelo en una acción útil para el agente principal.

### Salidas sugeridas

| Score de seriedad | Estado | Acción sugerida |
|---:|---|---|
| 0.80 - 1.00 | Alta seriedad | Continuar atención o escalar |
| 0.50 - 0.79 | Dudosa | Pedir más información |
| 0.30 - 0.49 | Baja seriedad | Validar con preguntas específicas |
| 0.00 - 0.29 | Posible improcedente | Marcar alerta, pero no cerrar automáticamente |

### Regla de seguridad

```text
Si hay señales de riesgo alto, lesión, violencia, fuego, arma, accidente, menor de edad o emergencia médica:
    escalar o continuar atención aunque el score de seriedad sea bajo.
```

---

## Fase 8: Evaluación

### Objetivo

Medir si el subagente realmente ayuda a estimar seriedad.

### Métricas recomendadas

| Métrica | Uso |
|---|---|
| Accuracy | Medida general, no suficiente por sí sola |
| Precision | Qué tan confiables son las alertas de improcedencia |
| Recall para llamadas serias | Evitar descartar llamadas reales |
| F1-score | Balance entre precision y recall |
| Matriz de confusión | Ver errores por clase |
| AUROC | Evaluar separación entre clases |
| AUPRC | Útil si hay clases desbalanceadas |
| Brier Score | Calibración de probabilidades |

### Métrica prioritaria

Para este proyecto debe priorizarse:

```text
Recall alto para llamadas serias
```

Porque es más grave marcar una emergencia real como broma que dejar pasar una llamada improcedente.

---

## Fase 9: Interfaz de prueba

### Objetivo

Crear una interfaz sencilla para probar el sistema.

### Herramienta recomendada

```text
Streamlit
```

### Funciones de la interfaz

- Subir archivo de audio.
- Ver transcripción.
- Ver features acústicos principales.
- Ver score de seriedad.
- Ver explicación del resultado.
- Ver acción sugerida.

### Ejemplo de salida

```json
{
  "score_seriedad": 0.72,
  "estado": "dudosa",
  "accion_sugerida": "pedir más información",
  "evidencias": {
    "ubicacion_detectada": false,
    "tipo_incidente_detectado": true,
    "pausas_largas": true,
    "cambio_de_tema": false,
    "calidad_audio": "regular"
  }
}
```

---

## Fase 10: Evolución hacia modelo CNN-LSTM-MLP

### Objetivo

Cuando exista suficiente dataset, pasar de modelos clásicos a un modelo E2E.

### Arquitectura propuesta

```text
Audio / Mel-Spectrogram
    |
    v
CNN bloque 1
    |
CNN bloque 2
    |
CNN bloque 3
    |
LSTM 256
    |
LSTM 256
    |
MLP 3 capas
    |
Salidas:
- P(seriedad)
- estrés
- urgencia
- activación emocional
- confianza
```

### Funciones de pérdida

```text
L_total = w1 * BCE(seriedad)
        + w2 * CCC(estrés)
        + w3 * CCC(urgencia)
        + w4 * CCC(activación_emocional)
        + w5 * pérdida_calibración
```

### Recomendación

No implementar esta fase hasta tener:

- suficientes audios etiquetados;
- variedad de hablantes;
- llamadas serias, dudosas e improcedentes;
- criterios de anotación claros;
- métricas comparables contra modelos baseline.

---

## 12. Integración futura con el agente principal

El subagente debe comunicarse con el agente principal mediante una salida estructurada.

### Ejemplo de respuesta del subagente

```json
{
  "call_id": "abc123",
  "seriedad_score": 0.68,
  "improcedencia_score": 0.32,
  "urgencia_score": 0.74,
  "confianza": 0.61,
  "estado": "dudosa",
  "accion_recomendada": "pedir_mas_informacion",
  "evidencias": [
    "No se detectó ubicación clara",
    "Se detectó posible tipo de incidente",
    "La narración tiene bajo nivel de detalle",
    "No hay señales acústicas suficientes para marcar improcedencia"
  ]
}
```

### Acciones posibles

```text
continuar_atencion
pedir_mas_informacion
escalar_humano
marcar_posible_improcedente
```

---

## 13. Consideraciones éticas y de seguridad

### Riesgos

- Marcar una llamada real como broma.
- Sesgo por acento, edad, discapacidad del habla o nerviosismo.
- Errores de transcripción.
- Mala calidad de audio.
- Uso indebido de grabaciones.
- Sobreconfianza en el modelo.

### Mitigaciones

- No cerrar llamadas automáticamente.
- Usar supervisión humana en casos críticos.
- Guardar explicaciones del resultado.
- Evaluar sesgos por subgrupos si los datos lo permiten.
- Anonimizar información sensible.
- Priorizar seguridad sobre eficiencia.

---

## 14. Entregables por etapa

| Fase | Entregable |
|---|---|
| 0 | Documento de alcance y criterios de etiquetas |
| 1 | Dataset inicial organizado |
| 2 | Script de preprocesamiento de audio |
| 3 | Script de extracción de features acústicas |
| 4 | Script de transcripción y análisis semántico |
| 5 | Dataset fusionado |
| 6 | Modelo baseline entrenado |
| 7 | Política de decisión |
| 8 | Reporte de métricas |
| 9 | Demo en Streamlit |
| 10 | Propuesta para CNN-LSTM-MLP |
| 11 | API de integración con agente principal |

---

## 15. Ruta de implementación recomendada

### Semana 1

- Definir etiquetas.
- Preparar estructura del proyecto.
- Recolectar o simular audios.
- Crear `labels.csv`.

### Semana 2

- Implementar preprocesamiento.
- Extraer features acústicos.
- Probar Whisper local.

### Semana 3

- Generar features semánticos.
- Construir dataset fusionado.
- Entrenar modelos baseline.

### Semana 4

- Evaluar métricas.
- Crear política de decisión.
- Implementar demo en Streamlit.

### Semana 5 o posterior

- Integrar con agente principal.
- Mejorar modelo.
- Evaluar tiempo real.
- Considerar CNN-LSTM-MLP.

---

## 16. Conclusión

La propuesta puede implementarse en Python, pero debe hacerse de forma progresiva. La arquitectura completa con telefonía en tiempo real, ASR, SER, retrieval, CNN-LSTM-MLP y agente principal es viable como visión final, pero demasiado compleja para iniciar.

La mejor ruta es comenzar con un MVP offline basado en audios grabados, Whisper local, extracción de características acústicas, análisis semántico simple y modelos clásicos. Esta versión puede construirse con herramientas gratuitas y permitirá validar si las señales acústicas y semánticas realmente aportan valor para estimar la seriedad de una llamada.

El sistema debe mantenerse como apoyo al agente principal y no como mecanismo automático de cierre o descarte de llamadas. La prioridad metodológica debe ser reducir falsos positivos en llamadas reales, mantener trazabilidad y escalar a supervisión humana cuando exista incertidumbre o riesgo.
