# Guiones para Dataset Sintético de Prueba — Subagente de Seriedad

**Total:** 23 guiones · 4 categorías · Español mexicano  
**Voces TTS:** `es-MX-JorgeNeural` (M) · `es-MX-DaliaNeural` (F)

---

## Nota metodológica

Para llamadas no-emergencia sin términos de broma, el sistema responde
`pedir_mas_informacion` (no `posible_improcedente`). Esto es comportamiento
correcto: la política conservadora requiere marcadores explícitos de broma
O anomalías acústicas para clasificar como improcedente.

---

## Categorías

| Cat | Recomendación esperada | IDs |
|---|---|---|
| A — Emergencia completa | `continuar` | G-01 a G-04 |
| B — Alto riesgo | `escalar_humano` | G-05 a G-12 |
| C — Info incompleta | `pedir_mas_informacion` | G-13 a G-19 |
| D — Broma explícita | `posible_improcedente` | G-20 a G-23 |

---

## CAT A — `continuar`

**Req:** incident_keyword + location_hint + coherence ≥ 0.55 + SIN high-risk terms

### G-01 · Robo a negocio | Voz: M

> Buenas noches, quiero reportar un robo en la tienda de abarrotes ubicada en la calle Benito Juárez número cuatro, colonia Centro, Apizaco. Unos sujetos entraron, rompieron la cerradura y se llevaron mercancía. Ya se fueron, no hay personas lastimadas hasta donde sé.

Keywords: `robo` (incident+emergency) · `calle`, `numero`, `colonia` (location) · `personas` (victim)  
Recomendación: **continuar**

---

### G-02 · Choque sin lesionados | Voz: F

> Quiero reportar un choque entre dos automóviles en la avenida Independencia, esquina con la calle Hidalgo, en Tlaxcala. Los conductores ya bajaron de sus autos, están alterados pero no hay lesionados. Necesito que vengan a regular el tráfico.

Keywords: `choque` · `avenida`, `esquina`, `calle` · `conductores`  
Recomendación: **continuar** — "lesionados" ≠ "herido", no activa high-risk

---

### G-03 · Asalto a transeúnte | Voz: M

> Me acaban de asaltar en el estacionamiento del mercado municipal, sobre la carretera número ciento diecisiete en Huamantla. Le quitaron la bolsa a una señora que estaba ahí. Los asaltantes corrieron hacia el norte hace unos dos minutos.

Keywords: `asalto` · `carretera`, `numero` · `señora`  
Recomendación: **continuar**

---

### G-04 · Pelea callejera activa | Voz: F

> Buenas tardes, hay una pelea en la calle Zaragoza número doce, colonia San Diego, Tlaxcala. Son como cinco personas peleando afuera de un negocio. Se ven muy alterados, alguien podría salir lastimado. Manden una patrulla por favor.

Keywords: `pelea` · `calle`, `numero`, `colonia` · `alguien`  
Recomendación: **continuar** — "lastimado" no es high-risk

---

## CAT B — `escalar_humano`

**High-risk list:** `arma` · `balazo` · `disparo` · `herido` · `sangre` · `incendio` · `secuestro` · `infarto` · `ambulancia` · `violencia`

### G-05 · Incendio | Voz: F

> Auxilio, hay un incendio en la casa de mis vecinos en la calle Morelos número treinta y cuatro, colonia La Loma, Tlaxcala. Las llamas ya salen por la ventana. Creemos que hay personas adentro. Manden bomberos urgente.

High-risk: **`incendio`** — Recomendación: **escalar_humano**

---

### G-06 · Accidente con herido | Voz: M

> Hay un accidente grave en la carretera Tlaxcala-Apizaco, kilómetro doce. Un automóvil volcó y hay un señor herido que está en el piso. Está consciente pero no puede moverse. Necesito que manden ayuda de inmediato.

High-risk: **`herido`** — Recomendación: **escalar_humano**

---

### G-07 · Disparo activo | Voz: F

> Oiga, se escuchó un disparo aquí en la colonia Xicohténcatl, por la calle Guerrero. La gente está corriendo y todos tienen mucho miedo. No sé si hay alguien afectado pero fue muy cerca de donde estamos.

High-risk: **`disparo`** (singular — "disparos" plural NO matchea)  
Recomendación: **escalar_humano**

---

### G-08 · Persona con arma | Voz: M

> Estoy en el centro comercial de Tlaxcala y hay un señor con un arma en la planta baja, cerca de la entrada principal. Hay muchas personas aquí adentro y todos estamos muy asustados. Vengan rápido por favor.

High-risk: **`arma`** — Recomendación: **escalar_humano**

---

### G-09 · Infarto + ambulancia | Voz: F

> Por favor manden ayuda urgente, mi papá se desmayó y creemos que tuvo un infarto. Estamos en la avenida Juárez número doscientos, colonia Buenavista, Apizaco. Tiene los labios morados y no responde bien. Necesitamos una ambulancia ya.

High-risk: **`infarto`**, **`ambulancia`** — Recomendación: **escalar_humano**

---

### G-10 · Secuestro | Voz: M

> Urgente, creo que están secuestrando a mi hijo. Recibí una llamada de un número desconocido exigiendo dinero y amenazando con hacerle daño. Estoy en mi casa en la calle Lerdo número ochenta, colonia Centro, Tlaxcala. Tengo mucho miedo.

High-risk: **`secuestro`** — Recomendación: **escalar_humano**

---

### G-11 · Sangre visible | Voz: F

> Hay una señora en la banqueta de la calle Xicoténcatl, frente al número cuarenta y cinco, colonia Centro. Está tirada y tiene sangre en la cabeza. No sabemos qué le pasó, llegamos y ya estaba así.

High-risk: **`sangre`** — Recomendación: **escalar_humano**

---

### G-12 · Violencia doméstica | Voz: M

> Llamo porque mi vecina está siendo agredida adentro de su casa. Se escuchan gritos y golpes fuertes. Hay mucha violencia, me preocupa que le hagan daño grave. La dirección es calle Revolución número doce, colonia San Miguel, Tlaxcala.

High-risk: **`violencia`** — Recomendación: **escalar_humano**

---

## CAT C — `pedir_mas_informacion`

**Req:** emergencia presente pero falta incident/location para `continuar`,
o completeness < 0.75, o llamada sin emergencia (sin bromas)

### G-13 · Choque sin ubicación | Voz: M

> Hay un choque aquí cerca pero no sé exactamente en qué calle estoy. Son dos autos que chocaron, los conductores ya bajaron y están discutiendo pero no hay lesionados que yo vea. Necesito que vengan pero no sé cómo decirles dónde estoy exactamente.

has_incident=T · has_location=**F** → no cumple condición de `continuar`  
Recomendación: **pedir_mas_informacion**

---

### G-14 · Desmayo sin ubicación | Voz: F

> Mi mamá se desmayó. Está en el piso y no la puedo levantar. No sé en qué parte de la ciudad estamos, salimos a caminar. Por favor ayúdenos.

`desmayo` (incident, NO high-risk) · `mi mama` (victim) · sin location  
Recomendación: **pedir_mas_informacion**

---

### G-15 · Robo vago | Voz: M

> Oiga, creo que me robaron algo del carro pero no estoy seguro. Llegué y noté que falta algo de adentro. No vi quién lo hizo, no sé cuándo pasó exactamente. No sé qué hacer.

`robo` · sin location · sin victim explícito · completeness = 2/4 = 0.5  
Recomendación: **pedir_mas_informacion**

---

### G-16 · Sospechoso, sin emergencia | Voz: F

> Oiga, hay un señor parado afuera de mi casa desde hace mucho tiempo y me parece muy sospechoso. No sé si está haciendo algo malo. Estoy en la colonia El Olivo pero no sé si es un problema real.

`señor` (victim) · `colonia` (location) · sin incident_keyword  
has_incident=F → no puede ser `continuar`  
Recomendación: **pedir_mas_informacion**

---

### G-17 · Llamada mínima | Voz: M

> Ayuda, algo pasó aquí en mi calle.

word_count=7 < 12 · completeness=1/4=0.25  
Recomendación: **pedir_mas_informacion**

---

### G-18 · Queja de ruido | Voz: F

> Buenas tardes, llamo para quejarme porque los vecinos ponen música muy fuerte todas las noches y no me dejan dormir. Ya les pedí que pararan pero no hacen caso. No sé si ustedes pueden hacer algo al respecto.

Sin emergency, sin incident · completeness=1/4  
Sistema conservador: sin anomalías acústicas TTS → no puede inferir improcedencia  
Recomendación: **pedir_mas_informacion**

---

### G-19 · Número equivocado | Voz: M

> Disculpe, creo que me equivoqué de número. Quería llamar a otra parte y no sé cómo terminé aquí. No era para esto, perdone la molestia.

Sin emergency, sin incident · completeness=1/4  
Recomendación: **pedir_mas_informacion**

---

## CAT D — `posible_improcedente`

**Req:** improcedence ≥ 0.7 AND has_joke AND completeness < 0.5 AND coherence < 0.6

Cada guión combina:
- Joke tokens: `jaja`, `jeje`, `jajaja`, `era broma`, `broma`, `molestar`, `xd`, `mentira`, `jugando`
- Evasivos: `no es cierto`, `da igual`, `quien sabe`, `no quiero decir`, `no se`
- Topic shifts: `musica`, `otra cosa`, `videojuego`
- Contradicción: par (`era broma`, `ayuda`) cuando ambos están presentes

---

### G-20 · Broma + contradicción | Voz: M

> Jajaja, era broma. Quería pedir ayuda a mis amigos para gastar una broma pero no es cierto nada de esto. Da igual, quien sabe para qué llamé. Olvidalo.

Coherencia: contradicción(era broma+ayuda)=-0.25 · evasivos×3=-0.35 → **coherence≈0.40**  
Improcedencia: joke+0.35 · completeness<0.5+0.20 · coherence<0.55+0.20 → **≈0.85**  
Recomendación: **posible_improcedente**

---

### G-21 · Broma + distracción | Voz: F

> Jeje, mentira, era una broma nomás. Estaba jugando. No quiero decir nada. Da igual. Mejor hablemos de musica o de otra cosa. No sé por qué llamé.

⚠️ Escribir "musica" SIN acento para que el token normalizado haga match.

Coherencia: evasivos×3=-0.35 · topic_shifts×2=-0.40 → **coherence≈0.25**  
Improcedencia: joke+0.35 · sin_emergency+0.10 · completeness+0.20 · coherence+0.20 → **≈0.95**  
Recomendación: **posible_improcedente**

---

### G-22 · XD + contradicción + videojuego | Voz: M

> Xd perdón, era broma. Quería pedir ayuda para molestar a alguien. No es cierto. Da igual, mejor hablemos de videojuegos. No quiero decir más.

Coherencia: contradicción=-0.25 · evasivos×3=-0.35 · topic_shift=-0.20 → **coherence≈0.20**  
Improcedencia: joke+0.35 · completeness+0.20 · coherence+0.20 → **≈0.85**  
Recomendación: **posible_improcedente**

---

### G-23 · Múltiples marcadores | Voz: F

> Jajaja, era broma. Quería molestar a alguien, fue un juego. No es cierto nada de esto. Da igual, quien sabe. Mejor de musica o de otra cosa.

⚠️ Escribir "musica" SIN acento.

Coherencia: evasivos×3=-0.35 · topic_shifts×2=-0.40 → **coherence≈0.25**  
Improcedencia: joke+0.35 · sin_emergency+0.10 · completeness+0.20 · coherence+0.20 → **≈0.95**  
Recomendación: **posible_improcedente**

---

## Ground Truth

| ID | Descripción | Voz | Esperado | high_risk | joke |
|---|---|---|---|---|---|
| G-01 | Robo tienda | M | `continuar` | No | No |
| G-02 | Choque autos | F | `continuar` | No | No |
| G-03 | Asalto transeúnte | M | `continuar` | No | No |
| G-04 | Pelea callejera | F | `continuar` | No | No |
| G-05 | Incendio | F | `escalar_humano` | incendio | No |
| G-06 | Herido en accidente | M | `escalar_humano` | herido | No |
| G-07 | Disparo | F | `escalar_humano` | disparo | No |
| G-08 | Arma en centro comercial | M | `escalar_humano` | arma | No |
| G-09 | Infarto + ambulancia | F | `escalar_humano` | infarto, ambulancia | No |
| G-10 | Secuestro | M | `escalar_humano` | secuestro | No |
| G-11 | Sangre en banqueta | F | `escalar_humano` | sangre | No |
| G-12 | Violencia doméstica | M | `escalar_humano` | violencia | No |
| G-13 | Choque sin ubicación | M | `pedir_mas_informacion` | No | No |
| G-14 | Desmayo sin ubicación | F | `pedir_mas_informacion` | No | No |
| G-15 | Robo vago | M | `pedir_mas_informacion` | No | No |
| G-16 | Sospechoso | F | `pedir_mas_informacion` | No | No |
| G-17 | Info mínima | M | `pedir_mas_informacion` | No | No |
| G-18 | Queja ruido | F | `pedir_mas_informacion` | No | No |
| G-19 | Número equivocado | M | `pedir_mas_informacion` | No | No |
| G-20 | Broma + contradicción | M | `posible_improcedente` | No | Sí |
| G-21 | Broma + tema ajeno | F | `posible_improcedente` | No | Sí |
| G-22 | XD + videojuego | M | `posible_improcedente` | No | Sí |
| G-23 | Múltiples marcadores | F | `posible_improcedente` | No | Sí |

---

## Script: generar_dataset.py

```python
"""
Genera 23 audios MP3 del dataset sintético con edge-tts.
Instalar: pip install edge-tts --break-system-packages
"""
import asyncio, csv
from pathlib import Path
import edge_tts

OUTPUT_DIR = Path("dataset_prueba")
OUTPUT_DIR.mkdir(exist_ok=True)
VOCES = {"M": "es-MX-JorgeNeural", "F": "es-MX-DaliaNeural"}

GUIONES = [
    ("G-01","M","continuar","Buenas noches, quiero reportar un robo en la tienda de abarrotes ubicada en la calle Benito Juárez número cuatro, colonia Centro, Apizaco. Unos sujetos entraron, rompieron la cerradura y se llevaron mercancía. Ya se fueron, no hay personas lastimadas hasta donde sé."),
    ("G-02","F","continuar","Quiero reportar un choque entre dos automóviles en la avenida Independencia, esquina con la calle Hidalgo, en Tlaxcala. Los conductores ya bajaron de sus autos, están alterados pero no hay lesionados. Necesito que vengan a regular el tráfico."),
    ("G-03","M","continuar","Me acaban de asaltar en el estacionamiento del mercado municipal, sobre la carretera número ciento diecisiete en Huamantla. Le quitaron la bolsa a una señora que estaba ahí. Los asaltantes corrieron hacia el norte hace unos dos minutos."),
    ("G-04","F","continuar","Buenas tardes, hay una pelea en la calle Zaragoza número doce, colonia San Diego, Tlaxcala. Son como cinco personas peleando afuera de un negocio. Se ven muy alterados, alguien podría salir lastimado. Manden una patrulla por favor."),
    ("G-05","F","escalar_humano","Auxilio, hay un incendio en la casa de mis vecinos en la calle Morelos número treinta y cuatro, colonia La Loma, Tlaxcala. Las llamas ya salen por la ventana. Creemos que hay personas adentro. Manden bomberos urgente."),
    ("G-06","M","escalar_humano","Hay un accidente grave en la carretera Tlaxcala-Apizaco, kilómetro doce. Un automóvil volcó y hay un señor herido que está en el piso. Está consciente pero no puede moverse. Necesito que manden ayuda de inmediato."),
    ("G-07","F","escalar_humano","Oiga, se escuchó un disparo aquí en la colonia Xicohténcatl, por la calle Guerrero. La gente está corriendo y todos tienen mucho miedo. No sé si hay alguien afectado pero fue muy cerca de donde estamos."),
    ("G-08","M","escalar_humano","Estoy en el centro comercial de Tlaxcala y hay un señor con un arma en la planta baja, cerca de la entrada principal. Hay muchas personas aquí adentro y todos estamos muy asustados. Vengan rápido por favor."),
    ("G-09","F","escalar_humano","Por favor manden ayuda urgente, mi papá se desmayó y creemos que tuvo un infarto. Estamos en la avenida Juárez número doscientos, colonia Buenavista, Apizaco. Tiene los labios morados y no responde bien. Necesitamos una ambulancia ya."),
    ("G-10","M","escalar_humano","Urgente, creo que están secuestrando a mi hijo. Recibí una llamada de un número desconocido exigiendo dinero y amenazando con hacerle daño. Estoy en mi casa en la calle Lerdo número ochenta, colonia Centro, Tlaxcala. Tengo mucho miedo."),
    ("G-11","F","escalar_humano","Hay una señora en la banqueta de la calle Xicoténcatl, frente al número cuarenta y cinco, colonia Centro. Está tirada y tiene sangre en la cabeza. No sabemos qué le pasó, llegamos y ya estaba así."),
    ("G-12","M","escalar_humano","Llamo porque mi vecina está siendo agredida adentro de su casa. Se escuchan gritos y golpes fuertes. Hay mucha violencia, me preocupa que le hagan daño grave. La dirección es calle Revolución número doce, colonia San Miguel, Tlaxcala."),
    ("G-13","M","pedir_mas_informacion","Hay un choque aquí cerca pero no sé exactamente en qué calle estoy. Son dos autos que chocaron, los conductores ya bajaron y están discutiendo pero no hay lesionados que yo vea. Necesito que vengan pero no sé cómo decirles dónde estoy exactamente."),
    ("G-14","F","pedir_mas_informacion","Mi mamá se desmayó. Está en el piso y no la puedo levantar. No sé en qué parte de la ciudad estamos, salimos a caminar. Por favor ayúdenos."),
    ("G-15","M","pedir_mas_informacion","Oiga, creo que me robaron algo del carro pero no estoy seguro. Llegué y noté que falta algo de adentro. No vi quién lo hizo, no sé cuándo pasó exactamente. No sé qué hacer."),
    ("G-16","F","pedir_mas_informacion","Oiga, hay un señor parado afuera de mi casa desde hace mucho tiempo y me parece muy sospechoso. No sé si está haciendo algo malo. Estoy en la colonia El Olivo pero no sé si es un problema real."),
    ("G-17","M","pedir_mas_informacion","Ayuda, algo pasó aquí en mi calle."),
    ("G-18","F","pedir_mas_informacion","Buenas tardes, llamo para quejarme porque los vecinos ponen música muy fuerte todas las noches y no me dejan dormir. Ya les pedí que pararan pero no hacen caso. No sé si ustedes pueden hacer algo al respecto."),
    ("G-19","M","pedir_mas_informacion","Disculpe, creo que me equivoqué de número. Quería llamar a otra parte y no sé cómo terminé aquí. No era para esto, perdone la molestia."),
    ("G-20","M","posible_improcedente","Jajaja, era broma. Quería pedir ayuda a mis amigos para gastar una broma pero no es cierto nada de esto. Da igual, quien sabe para qué llamé. Olvidalo."),
    ("G-21","F","posible_improcedente","Jeje, mentira, era una broma nomás. Estaba jugando. No quiero decir nada. Da igual. Mejor hablemos de musica o de otra cosa. No sé por qué llamé."),
    ("G-22","M","posible_improcedente","Xd perdón, era broma. Quería pedir ayuda para molestar a alguien. No es cierto. Da igual, mejor hablemos de videojuegos. No quiero decir más."),
    ("G-23","F","posible_improcedente","Jajaja, era broma. Quería molestar a alguien, fue un juego. No es cierto nada de esto. Da igual, quien sabe. Mejor de musica o de otra cosa."),
]

async def generar(gid, texto, voz_key):
    archivo = OUTPUT_DIR / f"{gid}.mp3"
    await edge_tts.Communicate(texto, VOCES[voz_key]).save(str(archivo))
    print(f"  OK {archivo.name}")
    return str(archivo)

async def main():
    print(f"Generando {len(GUIONES)} audios...\n")
    rutas = await asyncio.gather(*[generar(g,t,v) for g,v,_,t in GUIONES])
    csv_path = OUTPUT_DIR / "ground_truth.csv"
    with open(csv_path,"w",newline="",encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id","archivo","recomendacion_esperada","texto"])
        for (gid,_,rec,texto), ruta in zip(GUIONES,rutas):
            w.writerow([gid, Path(ruta).name, rec, texto])
    print(f"\nGround truth: {csv_path}")

asyncio.run(main())
```

---

## Script: evaluar_dataset.py

```python
"""
Evalúa el pipeline contra el dataset. Ejecutar desde subagente_seriedad/
"""
import csv, json, subprocess
from pathlib import Path

DATASET_DIR = Path("dataset_prueba")

def evaluar(audio):
    r = subprocess.run(["python","main.py","--audio",audio,"--model","tiny"],
                       capture_output=True, text=True)
    try: return json.loads(r.stdout)
    except: return {"recommendation":"ERROR"}

def main():
    guiones = list(csv.DictReader(open(DATASET_DIR/"ground_truth.csv", encoding="utf-8")))
    resultados, ok = [], 0
    print(f"{'ID':<6} {'Esperado':<25} {'Obtenido':<25} Resultado")
    print("-"*72)
    for g in guiones:
        salida = evaluar(str(DATASET_DIR/g["archivo"]))
        obtenido = salida.get("recommendation","ERROR")
        correcto = obtenido == g["recomendacion_esperada"]
        if correcto: ok += 1
        print(f"{g['id']:<6} {g['recomendacion_esperada']:<25} {obtenido:<25} {'OK' if correcto else 'FAIL'}")
        resultados.append({"id":g["id"],"esperado":g["recomendacion_esperada"],
                           "obtenido":obtenido,"correcto":correcto,
                           "seriousness":salida.get("seriousness_score",""),
                           "improcedence":salida.get("improcedence_score",""),
                           "confidence":salida.get("confidence","")})
    print(f"\nAccuracy: {ok}/{len(guiones)} = {ok/len(guiones)*100:.1f}%")
    out = DATASET_DIR/"resultados_evaluacion.csv"
    with open(out,"w",newline="",encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=resultados[0].keys())
        w.writeheader(); w.writerows(resultados)
    print(f"Resultados guardados: {out}")

main()
```

---

## Uso rápido

```bash
# Instalar
pip install edge-tts --break-system-packages

# Generar audios (desde cualquier directorio)
python generar_dataset.py
# → dataset_prueba/G-01.mp3 ... G-23.mp3 + ground_truth.csv

# Evaluar (desde subagente_seriedad/)
python evaluar_dataset.py
# → tabla de resultados + dataset_prueba/resultados_evaluacion.csv
```

---

## Limitación documentada

Audio TTS = sin ruido, sin clipping, sin silencios largos → acoustic_anomaly_flags vacío.
La ruta `posible_improcedente` vía anomalías acústicas no se ejercita con este dataset.
Este dataset prueba principalmente la **rama semántica**.
Para prueba de la rama acústica: usar Kaggle "911 Recordings" o grabaciones del C5i.
