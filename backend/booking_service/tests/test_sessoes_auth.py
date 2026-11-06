import json
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from redis.exceptions import RedisError

from app.deps import utilizador_atual


class RedisSessaoFalsa:
    def __init__(self, valor: str | None) -> None:
        self.valor = valor
        self.ttl: int | None = None

    def get(self, chave: str) -> str | None:
        assert chave == "sessao:token-opaco"
        return self.valor

    def expire(self, chave: str, segundos: int) -> bool:
        assert chave == "sessao:token-opaco"
        self.ttl = segundos
        return True

    def delete(self, chave: str) -> int:
        assert chave == "sessao:token-opaco"
        self.valor = None
        return 1


def _valor_sessao(expira_em: datetime) -> str:
    return json.dumps({
        "utilizador_id": 42,
        "perfil": "estudante",
        "email": "teste@example.com",
        "expira_em": expira_em.isoformat(),
    })


def test_sessao_bearer_valida_e_renova_inatividade() -> None:
    redis = RedisSessaoFalsa(
        _valor_sessao(datetime.now(timezone.utc) + timedelta(hours=1))
    )

    utilizador_id = utilizador_atual(
        redis=redis,
        authorization="Bearer token-opaco",
    )

    assert utilizador_id == 42
    assert redis.ttl == 30 * 60


def test_sessao_expirada_devolve_401() -> None:
    redis = RedisSessaoFalsa(
        _valor_sessao(datetime.now(timezone.utc) - timedelta(seconds=1))
    )

    with pytest.raises(HTTPException) as erro:
        utilizador_atual(redis=redis, authorization="Bearer token-opaco")

    assert erro.value.status_code == 401
    assert redis.valor is None


def test_sessao_sem_bearer_devolve_401() -> None:
    with pytest.raises(HTTPException) as erro:
        utilizador_atual(redis=RedisSessaoFalsa(None), authorization=None)

    assert erro.value.status_code == 401


def test_falha_redis_devolve_503() -> None:
    class RedisIndisponivel(RedisSessaoFalsa):
        def get(self, chave: str) -> str | None:
            raise RedisError("falha simulada")

    with pytest.raises(HTTPException) as erro:
        utilizador_atual(
            redis=RedisIndisponivel(None),
            authorization="Bearer token-opaco",
        )

    assert erro.value.status_code == 503
