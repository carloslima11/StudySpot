from collections.abc import Generator
from datetime import datetime, timezone

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.cache import get_redis
from app.core.config import Settings, get_settings
from app.core.security import decifrar_segredo_totp
from app.db import get_db
from app.main import app
from app.models import Base, SegredoTOTP, Utilizador


class RedisFalso:
    def __init__(self) -> None:
        self.valores: dict[str, str] = {}
        self.expiracoes: dict[str, int] = {}

    def ping(self) -> bool:
        return True

    def set(self, chave: str, valor: str, ex: int | None = None) -> bool:
        self.valores[chave] = valor
        if ex is not None:
            self.expiracoes[chave] = ex
        return True

    def get(self, chave: str) -> str | None:
        return self.valores.get(chave)

    def delete(self, *chaves: str) -> int:
        removidas = 0
        for chave in chaves:
            removidas += int(self.valores.pop(chave, None) is not None)
            self.expiracoes.pop(chave, None)
        return removidas

    def expire(self, chave: str, segundos: int) -> bool:
        if chave not in self.valores:
            return False
        self.expiracoes[chave] = segundos
        return True

    def incr(self, chave: str) -> int:
        valor = int(self.valores.get(chave, "0")) + 1
        self.valores[chave] = str(valor)
        return valor

    def ttl(self, chave: str) -> int:
        return self.expiracoes.get(chave, -1)


@pytest.fixture
def contexto() -> Generator[
    tuple[TestClient, sessionmaker[Session], RedisFalso],
    None,
    None,
]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    fabrica_sessoes = sessionmaker(bind=engine, expire_on_commit=False)
    redis = RedisFalso()
    settings = Settings(
        database_url="sqlite://",
        redis_url="redis://localhost",
        totp_encryption_key="11" * 32,
    )

    def obter_db() -> Generator[Session, None, None]:
        with fabrica_sessoes() as sessao:
            yield sessao

    app.dependency_overrides[get_db] = obter_db
    app.dependency_overrides[get_redis] = lambda: redis
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        with TestClient(app) as client:
            yield client, fabrica_sessoes, redis
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def _criar_utilizador_confirmado(
    fabrica_sessoes: sessionmaker[Session],
) -> tuple[Utilizador, str]:
    segredo = pyotp.random_base32()
    utilizador = Utilizador(
        nome="Utilizador de teste",
        email="teste@example.com",
        palavra_passe_hash="",
        perfil="estudante",
    )
    from app.core.security import cifrar_segredo_totp, gerar_hash_palavra_passe

    utilizador.palavra_passe_hash = gerar_hash_palavra_passe("Palavra-passe-de-teste")
    cifrado, nonce = cifrar_segredo_totp(segredo, "11" * 32)
    with fabrica_sessoes() as sessao:
        sessao.add(utilizador)
        sessao.flush()
        sessao.add(
            SegredoTOTP(
                utilizador_id=utilizador.id,
                segredo_cifrado=cifrado,
                nonce=nonce,
                confirmado=True,
            )
        )
        sessao.commit()
        return utilizador, segredo


def test_registo_confirma_totp_e_login_emite_sessao(contexto) -> None:
    client, fabrica_sessoes, redis = contexto
    resposta_registo = client.post(
        "/api/auth/registo",
        json={
            "nome": "Utilizador de teste",
            "email": "teste@example.com",
            "palavra_passe": "Palavra-passe-de-teste",
        },
    )
    assert resposta_registo.status_code == 201
    registo = resposta_registo.json()
    segredo = pyotp.parse_uri(registo["uri_configuracao_totp"]).secret
    codigo_confirmacao = pyotp.TOTP(segredo).generate_otp(
        pyotp.TOTP(segredo).timecode(datetime.now(timezone.utc)) - 1
    )

    confirmacao = client.post(
        "/api/auth/totp/confirmar",
        json={
            "token_confirmacao": registo["token_confirmacao"],
            "codigo": codigo_confirmacao,
        },
    )
    assert confirmacao.status_code == 200
    assert confirmacao.json() == {"estado": "confirmado"}

    with fabrica_sessoes() as sessao:
        utilizador = sessao.scalar(select(Utilizador))
        segredo_guardado = sessao.get(SegredoTOTP, utilizador.id)
        assert segredo_guardado.confirmado is True
        assert decifrar_segredo_totp(
            segredo_guardado.segredo_cifrado,
            segredo_guardado.nonce,
            "11" * 32,
        ) == segredo

    desafio = client.post(
        "/api/auth/login",
        json={
            "email": "teste@example.com",
            "palavra_passe": "Palavra-passe-de-teste",
        },
    )
    assert desafio.status_code == 202
    token_desafio = desafio.json()["token_desafio"]
    sessao = client.post(
        "/api/auth/login/totp",
        json={
            "token_desafio": token_desafio,
            "codigo": pyotp.TOTP(segredo).now(),
        },
    )
    assert sessao.status_code == 200
    dados_sessao = sessao.json()
    assert dados_sessao["utilizador_id"] > 0

    eu = client.get(
        "/api/auth/eu",
        headers={"Authorization": f"Bearer {dados_sessao['token']}"},
    )
    assert eu.status_code == 200
    assert eu.json()["email"] == "teste@example.com"
    assert redis.get(f"sessao:{dados_sessao['token']}") is not None

    logout = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {dados_sessao['token']}"},
    )
    assert logout.status_code == 204
    assert redis.get(f"sessao:{dados_sessao['token']}") is None


def test_login_tem_mensagem_generica_e_limita_tentativas(contexto) -> None:
    client, fabrica_sessoes, _ = contexto
    _criar_utilizador_confirmado(fabrica_sessoes)

    for _ in range(5):
        response = client.post(
            "/api/auth/login",
            json={
                "email": "teste@example.com",
                "palavra_passe": "palavra-passe-errada",
            },
        )
        assert response.status_code == 401
        assert response.json()["detail"] == "E-mail, palavra-passe ou código inválido."

    bloqueado = client.post(
        "/api/auth/login",
        json={
            "email": "teste@example.com",
            "palavra_passe": "Palavra-passe-de-teste",
        },
    )
    assert bloqueado.status_code == 429
    assert "Retry-After" in bloqueado.headers


def test_totp_reutilizado_nao_emite_outra_sessao(contexto) -> None:
    client, fabrica_sessoes, redis = contexto
    utilizador, segredo = _criar_utilizador_confirmado(fabrica_sessoes)
    passo_atual = pyotp.TOTP(segredo).timecode(
        datetime.now(timezone.utc)
    )
    utilizador.ultimo_passo_totp = passo_atual
    with fabrica_sessoes() as sessao:
        registado = sessao.get(Utilizador, utilizador.id)
        registado.ultimo_passo_totp = passo_atual
        sessao.commit()

    desafio = client.post(
        "/api/auth/login",
        json={
            "email": utilizador.email,
            "palavra_passe": "Palavra-passe-de-teste",
        },
    )
    resposta = client.post(
        "/api/auth/login/totp",
        json={
            "token_desafio": desafio.json()["token_desafio"],
            "codigo": pyotp.TOTP(segredo).now(),
        },
    )
    assert resposta.status_code == 401
    assert not any(chave.startswith("sessao:") for chave in redis.valores)
