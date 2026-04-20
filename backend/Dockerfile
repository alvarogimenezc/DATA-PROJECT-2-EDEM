#Imagen base: Python 3.12 
FROM python:3.12-slim

#Carpeta de trabajo dentro del contenedor
WORKDIR /app

#Instalar dependencias del sistema necesarias para Shapely (geometría)
RUN apt-get update && apt-get install -y \
    gcc \
    libgeos-dev \
    && rm -rf /var/lib/apt/lists/*

#Copiar e instalar dependencias Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

#Copiar todo el código del backend al contenedor
COPY . .

#Puerto en el que escucha la API
ENV PORT=8080
EXPOSE 8080

#Arrancar el servidor FastAPI con Uvicorn
CMD ["sh", "-c", "uvicorn cloudrisk_api.main:app --host 0.0.0.0 --port ${PORT}"]
