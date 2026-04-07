import requests
import time
import os
import logging

# Coordenadas de Valencia
LAT = "39.47391"
LON = "-0.37966"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_KEY = os.environ.get("CLAVE_API")
if not API_KEY:
    logger.error("ERROR: Debes configurar la variable API_KEY")
    exit(1)

# CAMBIO: Usamos la API de "weather" en lugar de "air_pollution"
URL_weather = f"https://api.openweathermap.org/data/2.5/weather?lat={LAT}&lon={LON}&appid={API_KEY}&units=metric"

def realtime_weather_data():
    response = requests.get(URL_weather, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    return {
        "timestamp": data.get("dt"),
        "temp": data["main"]["temp"],
        "lluvia": data.get("rain", {}).get("1h", 0), # mm en la última hora
        "nubes": data["clouds"]["all"],             # % de nubosidad
        "clima_principal": data["weather"][0]["main"] # 'Rain', 'Clear', 'Clouds', etc.
    }

while True: 
    try: 
        weather = realtime_weather_data()

        #Multiplicador de clima
        #Queremos: Buen tiempo (Sol/Despejado) -> 1.5 | Mal tiempo (Tormenta/Lluvia) -> 0.6
        
        #Base por tipo de clima
        if weather["clima_principal"] == "Clear":
            indice = 1.5
        elif weather["clima_principal"] in ["Clouds", "Drizzle"]:
            indice = 1.2
        elif weather["clima_principal"] == "Rain":
            indice = 0.8
        elif weather["clima_principal"] in ["Thunderstorm", "Snow"]:
            indice = 0.6
        else:
            indice = 1.0  #Valor neutral para otros estados

        #Ajuste opcional por temperatura extrema (Penalizamos si hace más de 35°C o menos de 5°C)
        if weather["temp"] > 30 or weather["temp"] < 5:
            indice -= 0.2

        # Aseguramos que no se salga de tus límites (0.6 a 1.5)
        indice_multiplicador_tiempo = max(0.6, min(1.5, indice))

        message = {
            "type": "weather_condition",
            "ts": weather["timestamp"],
            "temp": weather["temp"],
            "condicion": weather["clima_principal"],
            "indice_multiplicador_tiempo": round(indice_multiplicador_tiempo, 2)
        }

        logger.info(f"Datos meteorológicos procesados: {message}")

    except Exception as e: 
        logger.error(f"Error al obtener datos: {e}")
        time.sleep(60)