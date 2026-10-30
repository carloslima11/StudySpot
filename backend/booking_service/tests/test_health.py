from fastapi.testclient import TestClient
from app.main import app
from collections.abc import Generator
from unittest.mock import Mock
from fastapi.testclient import TestClient
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import StaticPool
from app.cache import get_redis
from app.db import get_engine
from app.main import app
from app.routes.health import MENSAGEM_INDISPONIVEL
import pytest


def test_live_responde_com_estado_vivo() -> None:
    client = TestClient(app)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"estado": "vivo"}


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    app.dependency_overrides.clear()
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def criar_engine_sqlite() -> Engine:
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_ready_responde_quando_dependencias_estao_disponiveis(
    client: TestClient,
) -> None:
    engine = criar_engine_sqlite()
    redis = Mock(spec=Redis)
    redis.ping.return_value = True
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_redis] = lambda: redis

    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"estado": "pronto"}
    redis.ping.assert_called_once()


def test_ready_devolve_503_se_postgres_falhar(client: TestClient) -> None:
    engine = Mock(spec=Engine)
    engine.connect.side_effect = SQLAlchemyError("falha simulada")
    redis = Mock(spec=Redis)
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_redis] = lambda: redis

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": MENSAGEM_INDISPONIVEL}


def test_ready_devolve_503_se_redis_falhar(client: TestClient) -> None:
    engine = criar_engine_sqlite()
    redis = Mock(spec=Redis)
    redis.ping.side_effect = RedisError("falha simulada")
    app.dependency_overrides[get_engine] = lambda: engine
    app.dependency_overrides[get_redis] = lambda: redis

    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"detail": MENSAGEM_INDISPONIVEL}
