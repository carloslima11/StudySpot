from collections.abc import Iterator
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException
from redis import Redis
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.csp import ConfigCSP
from app.locks_redis import LocksRedis
from app.repo_sql import RepositorioSQL, get_session
from app.schemas import LISBOA


def agora() -> datetime:
    return datetime.now(LISBOA).replace(tzinfo=None)


@lru_cache
def _cliente_redis() -> Redis:
    return Redis.from_url(get_settings().redis_url.get_secret_value())


def get_locks(settings: Annotated[Settings, Depends(get_settings)]) -> LocksRedis:
    return LocksRedis(_cliente_redis(), ttl_ms=settings.lock_ttl_ms)


def get_repo(sessao: Annotated[Session, Depends(get_session)]) -> Iterator[RepositorioSQL]:
    yield RepositorioSQL(sessao)


def get_cfg(settings: Annotated[Settings, Depends(get_settings)]) -> ConfigCSP:
    return ConfigCSP(slot_minutos=settings.slot_minutos,
                     limite_diario_horas=settings.limite_diario_horas)


def utilizador_atual(
        settings: Annotated[Settings, Depends(get_settings)],
        x_utilizador_id: Annotated[Optional[int], Header()] = None) -> int:
    if settings.auth_modo_dev and x_utilizador_id is not None:
        return x_utilizador_id
    raise HTTPException(status_code=401, detail="Sessão inválida ou em falta.")
