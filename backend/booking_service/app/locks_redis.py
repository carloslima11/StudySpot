from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator
from uuid import uuid4

from redis import Redis
from redis.exceptions import RedisError

from app.servico_reservas import LockIndisponivel

_LIBERTAR = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    return redis.call('del', KEYS[1])
end
return 0
"""


class RedisIndisponivel(LockIndisponivel):
    pass


class LocksRedis:
    def __init__(self, cliente: Redis, ttl_ms: int = 5000) -> None:
        self._redis = cliente
        self._ttl_ms = ttl_ms

    @contextmanager
    def adquirir(self, chaves: list[str]) -> Iterator[None]:
        token = uuid4().hex
        obtidas: list[str] = []
        try:
            for chave in sorted(chaves):
                if not self._redis.set(chave, token, nx=True, px=self._ttl_ms):
                    raise LockIndisponivel(f"slot ocupado por outro pedido: {chave}")
                obtidas.append(chave)
        except RedisError as exc:
            self._libertar(obtidas, token)
            raise RedisIndisponivel("Redis indisponível") from exc
        except LockIndisponivel:
            self._libertar(obtidas, token)
            raise
        try:
            yield
        finally:
            self._libertar(obtidas, token)

    def _libertar(self, chaves: list[str], token: str) -> None:
        for chave in chaves:
            try:
                self._redis.eval(_LIBERTAR, 1, chave, token)
            except RedisError:
                pass
