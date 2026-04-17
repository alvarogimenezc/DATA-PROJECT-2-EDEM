# steps_ingestor — Cloud Run Job que corre el fetcher diario.
# El scoring horario fue eliminado al absorber su lógica en el pipeline
# Dataflow unificado (pipelines/cloudrisk_unified.py).

FROM python:3.12-slim

WORKDIR /app

# Deps primero para aprovechar cache de Docker
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Entrypoint por defecto del Job diario.
CMD ["python", "recolector_pasos_diario.py"]
