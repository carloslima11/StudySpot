import os
from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.engine import Engine


@lru_cache
def get_engine() -> Engine:
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("A variável DATABASE_URL não está configurada.")

    connect_args = {}
    if make_url(database_url).get_backend_name() == "postgresql":
        connect_args = {
            "connect_timeout": 3,
            "options": "-c statement_timeout=5000",
        }
    return create_engine(
        database_url,
        pool_pre_ping=True,
        connect_args=connect_args,
    )
