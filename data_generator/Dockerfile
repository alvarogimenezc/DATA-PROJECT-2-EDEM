FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV CLOUDRISK_LOCAL_METRICS_DIR=/metrics

# Non-root user
RUN useradd --system --create-home --shell /bin/false app \
    && mkdir -p /metrics \
    && chown -R app:app /app /metrics
USER app

CMD ["python", "-u", "recolector_metricas_local.py"]
