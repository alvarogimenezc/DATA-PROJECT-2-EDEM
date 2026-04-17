"""
CloudRISK Backend API.
Punto de entrada FastAPI: monta los endpoints y expone Swagger en /api/v1/docs.
"""
from fastapi import FastAPI, APIRouter

from cloudrisk_api.endpoints import estado, acciones


base_path = "/api/v1"
router = APIRouter(prefix=base_path)

app = FastAPI(
    title="CloudRISK Backend",
    docs_url=f"{base_path}/docs",
    swagger_ui_parameters={"displayRequestDuration": True},
    version="1.0.0",
)


@app.get("/health", tags=["health"], summary="Liveness probe")
def health():
    return {"status": "ok"}


app.include_router(prefix=router.prefix, router=estado.router)
app.include_router(prefix=router.prefix, router=acciones.router)
