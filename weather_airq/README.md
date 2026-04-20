# ⛅ CloudRISK — Ingestores Ambientales (Clima y Calidad del Aire)

Esta carpeta contiene dos "reporteros" automáticos (`calidad_aire.py` y `clima.py`). Su misión es asomarse a la ventana cada 30 segundos para ver cómo está Valencia y avisar al juego de CloudRISK.

Dependiendo del tiempo y la contaminación, calculan un **Multiplicador de Ejércitos**.
* Si hace un día estupendo y el aire es puro = **1.5** (¡Tus ejércitos crecen un 50%!).
* Si hay tormenta y el aire es tóxico = **0.6** (¡Cuidado, pierdes casi la mitad de tus refuerzos!).

---

## 🛠️ Los dos reporteros

### 1. `calidad_aire.py`
Mide el Índice de Calidad del Aire (AQI).
* **Fórmula:** Penaliza progresivamente a medida que la contaminación sube del nivel 1 al 5.
* **Mensaje:** Lo envía con la etiqueta `"type": "air_quality"`.

### 2. `clima.py`
Mide el estado del cielo (Sol, Lluvia, Nieve) y la Temperatura.
* **Fórmula:** Da puntos base según el cielo (Despejado suma, Tormenta resta). Además, aplica una penalización extra de `-0.2` si hace calor extremo (>35ºC) o mucho frío (<5ºC) porque a las tropas les cuesta marchar.
* **Mensaje:** Lo envía con la etiqueta `"type": "weather"`.

---

## 🧪 Cómo probarlos en el portátil 

Nuestros scripts son a prueba de fallos. Si los ejecutas tal cual, entrarán en **"Modo Simulacro" (MOCK)**: se inventarán datos de clima realistas y los imprimirán en tu pantalla, sin necesidad de conectarse a Google Cloud ni gastar en APIs de pago.

Abre tu terminal, entra en esta carpeta y ejecuta:

```bash
# 1. Instala las librerías necesarias
pip install -r requirements.txt

# 2. Enciende el reportero de calidad del aire (pulsa Ctrl+C para apagarlo)
python calidad_aire.py

# 3. O enciende el reportero del clima (pulsa Ctrl+C para apagarlo)
python clima.py
```

[calidad_aire.py] y [clima.py] 
       ↓ 
 Envían un JSON cada 30 segundos
       ↓
[Google Pub/Sub] (Nuestras antenas)
       ↓
[Apache Beam / Dataflow] (El código que transforma los datos)
       ↓
[BigQuery] (Donde se guarda el historial)