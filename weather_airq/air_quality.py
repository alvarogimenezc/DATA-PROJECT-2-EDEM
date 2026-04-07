import requests
import time
import os
import logging

#Coordenadas de Valencia
LAT = "39.47391"
LON = "-0.37966"

#Configurar logging para ver mensajes en la consola
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

#API Key desde variable de entorno (NO hardcodeada, es decir, sin escribir valores fijos directamente en el codigo)
#Debemos meter la api key en el contenedor para que sea accesible 
API_KEY = "311e34f13899f30c02c390854ae76b32"
if not API_KEY:
    logger.error("ERROR: Debes configurar la variable API_KEY")
    exit(1)

#URL de la API OpenWeatherMap para tiempo real
URL_realtime = f"http://api.openweathermap.org/data/2.5/air_pollution?lat={LAT}&lon={LON}&appid={API_KEY}"

#Función para obtener datos en tiempo real de la API
def realtime_data():
    response = requests.get(URL_realtime, timeout=10)
    response.raise_for_status()
    data = response.json()
    item = data["list"][0]

    return {
        "timestamp": item["dt"],
        "ciudad": "Valencia",
        "aqi": item["main"]["aqi"],
        "co": item["components"]["co"],
        "no2": item["components"]["no2"],
        "o3": item["components"]["o3"],
        "pm2_5": item["components"]["pm2_5"],
        "pm10": item["components"]["pm10"],
    }    

#Función principal, bucle infinito para obtener datos de calidad de aire en tiempo real
while True: 
    try: 
        data = realtime_data()

        #Definimos ahora la lógica de negocio para enviar a pub/sub
        #Solo usaremos el AQUI para determinar la calidad, ya que incluye una combinación del resto de contaminantes
        indice_multiplicador_aire= 1.5 - (data["aqi"] - 1)*(0.9/4)
        logger.info(f"Índice multiplicador de puntos por calidad del aire: {indice_multiplicador_aire}")

    except Exception as e: 
        logger.error(f"Error al obtener datos: {e}")
