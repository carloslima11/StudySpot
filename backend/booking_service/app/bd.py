import os
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine


@lru_cache
def get_engine() -> Engine:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("A variável DATABASE_URL não está configurada.")

    return create_engine(database_url, pool_pre_ping=True)
