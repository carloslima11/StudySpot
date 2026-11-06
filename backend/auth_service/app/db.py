from functools import lru_cache
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from app.core.config import get_settings
from collections.abc import Generator
from sqlalchemy.orm import Session, sessionmaker


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    with get_sessionmaker()() as sessao:
        yield sessao


@lru_cache
def get_engine() -> Engine:
    database_url = get_settings().database_url.get_secret_value()
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
