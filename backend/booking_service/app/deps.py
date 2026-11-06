import json
from collections.abc import Iterator
from datetime import datetime, timezone
from functools import lru_cache
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.csp import ConfigCSP
from app.locks_redis import LocksRedis
from app.repo_sql import RepositorioSQL, get_session
from app.schemas import LISBOA

_TTL_SESSAO_SEGUNDOS = 30 * 60


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
        redis: Annotated[Redis, Depends(_cliente_redis)],
        authorization: Annotated[Optional[str], Header()] = None) -> int:
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Sessão inválida ou em falta.")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        valor = redis.get(f"sessao:{token}")
        if valor is None:
            raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
        if isinstance(valor, bytes):
            valor = valor.decode("utf-8")
        dados = json.loads(valor)
        expira_em = datetime.fromisoformat(dados["expira_em"])
        if expira_em.tzinfo is None or expira_em <= datetime.now(timezone.utc):
            redis.delete(f"sessao:{token}")
            raise HTTPException(status_code=401, detail="Sessão inválida ou expirada.")
        restante = int((expira_em - datetime.now(timezone.utc)).total_seconds())
        redis.expire(f"sessao:{token}", min(_TTL_SESSAO_SEGUNDOS, restante))
        return int(dados["utilizador_id"])
    except HTTPException:
        raise
    except (RedisError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise HTTPException(
            status_code=503,
            detail="O serviço está temporariamente indisponível. "
                   "Tenta novamente dentro de instantes.",
        ) from None
