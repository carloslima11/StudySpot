from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICO = Path(__file__).resolve().parents[2]
BACKEND = SERVICO.parent
RAIZ = BACKEND.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(RAIZ / ".env", BACKEND / ".env", SERVICO / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: SecretStr = SecretStr("redis://localhost:16379/0")

    mqtt_ativo: bool = False
    mqtt_host: str = "localhost"
    mqtt_port: int = 11883
    mqtt_topico_checkin: str = "studyspot/salas/+/checkin"
    checkin_segredo: Optional[SecretStr] = None
    qr_validade_segundos: int = 120

    slot_minutos: int = 30
    limite_diario_horas: float = 4.0
    tolerancia_checkin_minutos: int = 15
    antecedencia_checkin_minutos: int = 15
    lock_ttl_ms: int = 5000

    tarefa_periodica_ativa: bool = False
    tarefa_periodica_segundos: int = 60

    auth_modo_dev: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
