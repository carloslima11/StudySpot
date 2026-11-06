from collections.abc import Generator
from hmac import compare_digest
from unittest.mock import Mock
from urllib.parse import parse_qs, urlparse
import pytest
from fastapi.testclient import TestClient
from redis import Redis
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from app.cache import get_redis
from app.core.config import Settings, get_settings
from app.core.security import decifrar_segredo_totp, verificar_palavra_passe
from app.db import get_db
from app.main import app
from app.models import Base, SegredoTOTP, Utilizador
from redis.exceptions import RedisError


@pytest.fixture
def contexto() -> Generator[tuple[TestClient, sessionmaker[Session], Mock], None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    fabrica_sessoes = sessionmaker(bind=engine, expire_on_commit=False)

    def obter_db() -> Generator[Session, None, None]:
        with fabrica_sessoes() as sessao:
            yield sessao

    redis = Mock(spec=Redis)
    redis.ping.return_value = True
    settings = Settings(
        database_url="sqlite://",
        redis_url="redis://localhost",
        totp_encryption_key="11" * 32,
    )

    app.dependency_overrides[get_db] = obter_db
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_settings] = lambda: settings

    try:
        with TestClient(app) as client:
            yield client, fabrica_sessoes, redis
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def test_registo_guarda_password_e_totp_cifrado(
    contexto: tuple[TestClient, sessionmaker[Session], Mock],
) -> None:
    client, fabrica_sessoes, redis = contexto
    response = client.post(
        "/api/auth/registo",
        json={
            "nome": "Utilizador de teste",
            "email": "teste@example.com",
            "palavra_passe": "Palavra-passe-de-teste",
        },
    )

    assert response.status_code == 201
    dados = response.json()
    assert dados["utilizador_id"] > 0
    assert dados["uri_configuracao_totp"].startswith("otpauth://totp/")
    redis.ping.assert_called_once()

    segredo_uri = parse_qs(urlparse(dados["uri_configuracao_totp"]).query)[
        "secret"
    ][0]
    with fabrica_sessoes() as sessao:
        utilizador = sessao.scalar(
            select(Utilizador).where(
                Utilizador.email == "teste@example.com")
        )
        assert utilizador is not None
        assert verificar_palavra_passe(
            "Palavra-passe-de-teste",
            utilizador.palavra_passe_hash,
        )

        segredo_guardado = sessao.get(SegredoTOTP, utilizador.id)
        assert segredo_guardado is not None
        assert segredo_guardado.confirmado is False
        segredo_decifrado = decifrar_segredo_totp(
            segredo_guardado.segredo_cifrado,
            segredo_guardado.nonce,
            "11" * 32,
        )
        assert compare_digest(segredo_decifrado, segredo_uri)


def test_registo_rejeita_email_duplicado(contexto) -> None:
    client, fabrica_sessoes, _ = contexto
    pedido = {
        "nome": "Utilizador de teste",
        "email": "teste@example.com",
        "palavra_passe": "Palavra-passe-de-teste",
    }

    primeira_resposta = client.post("/api/auth/registo", json=pedido)
    segunda_resposta = client.post("/api/auth/registo", json=pedido)

    assert primeira_resposta.status_code == 201
    assert segunda_resposta.status_code == 409

    with fabrica_sessoes() as sessao:
        utilizadores = sessao.scalars(select(Utilizador)).all()
        assert len(utilizadores) == 1


def test_registo_devolve_503_se_redis_falhar(contexto) -> None:
    client, fabrica_sessoes, redis = contexto
    redis.ping.side_effect = RedisError("falha simulada")

    response = client.post(
        "/api/auth/registo",
        json={
            "nome": "Utilizador de teste",
            "email": "teste@example.com",
            "palavra_passe": "Palavra-passe-de-teste",
        },
    )

    assert response.status_code == 503
    with fabrica_sessoes() as sessao:
        assert sessao.scalar(select(Utilizador.id)) is None
