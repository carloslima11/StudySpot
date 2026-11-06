import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from redis import Redis

TEMPO_INATIVIDADE_SEGUNDOS = 30 * 60
TEMPO_ABSOLUTO = timedelta(hours=8)


def _chave_sessao(token: str) -> str:
    return f"sessao:{token}"


def criar_sessao(redis: Redis, utilizador_id: int, perfil: str, email: str) -> str:
    token = secrets.token_urlsafe(32)
    expira_em = datetime.now(timezone.utc) + TEMPO_ABSOLUTO
    dados = {
        "utilizador_id": utilizador_id,
        "perfil": perfil,
        "email": email,
        "expira_em": expira_em.isoformat(),
    }
    redis.set(
        _chave_sessao(token),
        json.dumps(dados),
        ex=TEMPO_INATIVIDADE_SEGUNDOS,
    )
    return token


def obter_sessao(redis: Redis, token: str, *, renovar: bool = True) -> dict[str, Any] | None:
    chave = _chave_sessao(token)
    valor = redis.get(chave)
    if valor is None:
        return None

    if isinstance(valor, bytes):
        valor = valor.decode("utf-8")
    try:
        dados = json.loads(valor)
        expira_em = datetime.fromisoformat(dados["expira_em"])
        if expira_em.tzinfo is None:
            return None
    except (AttributeError, KeyError, TypeError, ValueError, json.JSONDecodeError):
        redis.delete(chave)
        return None

    agora = datetime.now(timezone.utc)
    restante = int((expira_em - agora).total_seconds())
    if restante <= 0:
        redis.delete(chave)
        return None
    if renovar:
        redis.expire(chave, min(TEMPO_INATIVIDADE_SEGUNDOS, restante))
    return dados
