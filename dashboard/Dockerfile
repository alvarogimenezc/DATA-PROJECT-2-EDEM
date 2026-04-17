FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV STREAMLIT_SERVER_PORT=8080
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLECORS=false

# Non-root user for defense in depth
RUN useradd --system --create-home --shell /bin/false app \
    && chown -R app:app /app
USER app

EXPOSE 8080

CMD ["streamlit", "run", "main.py"]
