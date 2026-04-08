"""
Configuración del backend CloudRISK.
Lee variables de entorno con tipado fuerte usando pydantic_settings.
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_ID: str = "cloudrisk-492619"
    BQ_DATASET: str = "cloudrisk"
    BQ_USER_ACTIONS_TABLE: str = "user_actions"

    # Colecciones Firestore (contrato compartido con el pipeline de Noelia)
    COL_USER_BALANCE: str = "user_balance"
    COL_LOCATION_BALANCE: str = "location_balance"


settings = Settings()
