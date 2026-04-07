# ============================================================
# Consumer mínimo - recibe mensajes push de Pub/Sub
# Fase 3 del Data Project 2 (Flujo Datos 1)
# ============================================================

import os                                           # Variables de entorno (lo usaremos en Fase 4)
import json                                         # Convertir entre dict Python y string JSON
import base64                                       # Pub/Sub envía el payload codificado en base64
from fastapi import FastAPI, Request, HTTPException # Framework web async + tipos auxiliares

# Crea la aplicación FastAPI. Uvicorn buscará esta variable `app` al arrancar.
app = FastAPI()


# ------------------------------------------------------------
# Health check: Cloud Run hace ping aquí para saber si el
# servicio está sano. Si devuelve 200 -> sigue recibiendo tráfico.
# ------------------------------------------------------------
@app.get("/health")
def health():
    return {"status": "ok"}


# ------------------------------------------------------------
# Liveness probe: "¿estás vivo?". Si falla, el orquestador
# reinicia el contenedor (en Kubernetes/Cloud Run).
# ------------------------------------------------------------
@app.get("/live")
def live():
    return "alive"


# ------------------------------------------------------------
# Endpoint principal: recibe los mensajes que Pub/Sub
# nos manda en modo PUSH.
#
# Pub/Sub no envía directamente nuestro JSON, lo "envuelve":
# {
#   "message": {
#     "data": "<JSON original codificado en base64>",
#     "messageId": "id único del mensaje",
#     "publishTime": "..."
#   },
#   "subscription": "..."
# }
# ------------------------------------------------------------
@app.post("/process")
async def process(request: Request):

    # 1) Leer y parsear el body como JSON.
    #    Si no es JSON válido -> 400 Bad Request.
    try:
        envelope = await request.json()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid json: {e}")

    # 2) Extraer el campo "message" del envelope.
    #    Si no existe, no es una petición de Pub/Sub válida.
    msg = envelope.get("message")
    if not msg:
        raise HTTPException(status_code=400, detail="missing 'message' field")

    # 3) Sacar el messageId (lo usaremos en Fase 4 para idempotencia)
    #    y el campo data, que viene en base64.
    message_id = msg.get("messageId", "unknown")
    data_b64 = msg.get("data")
    if not data_b64:
        raise HTTPException(status_code=400, detail="missing 'data' field")

    # 4) Decodificar base64 -> bytes -> string -> dict Python.
    #    Después de esto, `event` contiene el JSON original que
    #    publicó el walker (type, user_id, ts, pasos, lat, lon, ...).
    try:
        decoded = base64.b64decode(data_b64).decode("utf-8")
        event = json.loads(decoded)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"invalid payload: {e}")

    # 5) De momento solo lo logueamos. En las próximas fases
    #    aquí irá: validación, guardado en Firestore, insert en BigQuery, etc.
    #    flush=True fuerza que se vea ya en `docker logs` sin buffering.
    print(f"[consumer] msg_id={message_id} event={event}", flush=True)

    # 6) Devolver 200 = mensaje aceptado.
    #    Pub/Sub considera el mensaje "ack" y no lo reintentará.
    #    Si devolviéramos 5xx, Pub/Sub lo reintentaría con backoff.
    return {"status": "ok", "messageId": message_id}
