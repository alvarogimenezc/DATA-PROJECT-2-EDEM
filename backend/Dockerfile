FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY ./cloudrisk_api ./cloudrisk_api

ENV PORT=8080

# Start FastAPI
CMD ["uvicorn", "cloudrisk_api.main:app", "--host", "0.0.0.0", "--port", "8080"]
