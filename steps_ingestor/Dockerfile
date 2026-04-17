# steps_ingestor — imagen que sirve tanto el fetcher (job) como el scorer (service).
# Mismo artefacto, entrypoint distinto según el servicio Cloud Run que apunte aquí.

FROM python:3.12-slim

WORKDIR /app

# Deps primero para aprovechar cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Por defecto levanta el scorer (Cloud Run Service). El Job fetcher sobreescribe
# el command con "python recolector_pasos_diario.py".
ENV PORT=8080
CMD ["sh", "-c", "uvicorn puntuador_horario:app --host 0.0.0.0 --port ${PORT}"]
