import logging
from fastapi import APIRouter, Depends, HTTPException
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from app.cache import get_redis
from app.db import get_engine


router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)

MENSAGEM_INDISPONIVEL = (
    "O serviço está temporariamente indisponível. "
    "Tenta novamente dentro de instantes."
)


@router.get("/live")
def live() -> dict[str, str]:
    return {"estado": "vivo"}


@router.get("/ready")
def ready(
    engine: Engine = Depends(get_engine),
    redis: Redis = Depends(get_redis),
) -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("Health check do PostgreSQL falhou.")
        raise HTTPException(
            status_code=503,
            detail=MENSAGEM_INDISPONIVEL,
        ) from None

    try:
        if not redis.ping():
            raise RedisError("O Redis não confirmou o ping.")
    except RedisError:
        logger.warning("Health check do Redis falhou.")
        raise HTTPException(
            status_code=503,
            detail=MENSAGEM_INDISPONIVEL,
        ) from None

    return {"estado": "pronto"}
