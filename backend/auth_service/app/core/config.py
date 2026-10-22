# permite validar a TOTP(password temporária de uso único) usando uma expressão regular
import re
from functools import lru_cache  # guarda em memória o resultado de "get_settings"
# permite validar um campo da configuração
from pydantic import SecretStr, field_validator
# obrigam o Pydantic a carregar e valida configurações
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # o "SecretStr" serve para guardar info sensível
    database_url: SecretStr
    redis_url: SecretStr
    totp_encryption_key: SecretStr

    @field_validator("totp_encryption_key")
    @classmethod
    def validar_chave_totp(cls, value: SecretStr) -> SecretStr:
        chave = value.get_secret_value()
        if not re.fullmatch(r"[0-9a-fA-F]{64}", chave):
            raise ValueError(
                "A chave TOTP deve conter exatamente 64 caracteres hexadecimais.")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
