import pytest

pytest.importorskip("redis")

from redis.exceptions import ConnectionError as RedisConnectionError

from app.locks_redis import LocksRedis, RedisIndisponivel
from app.servico_reservas import LockIndisponivel


class RedisFalso:
    def __init__(self, falha=False):
        self.dados, self.falha = {}, falha

    def set(self, chave, valor, nx=False, px=None):
        if self.falha:
            raise RedisConnectionError("redis em baixo")
        if nx and chave in self.dados:
            return None
        self.dados[chave] = valor
        return True

    def eval(self, _script, _n, chave, token):
        if self.dados.get(chave) == token:
            del self.dados[chave]
            return 1
        return 0


def test_adquire_e_liberta_todas_as_chaves():
    r = RedisFalso()
    with LocksRedis(r).adquirir(["b", "a"]):
        assert set(r.dados) == {"a", "b"}
    assert r.dados == {}


def test_chave_ocupada_nao_fica_com_locks_parciais():
    r = RedisFalso()
    r.dados["b"] = "de-outro"
    with pytest.raises(LockIndisponivel):
        with LocksRedis(r).adquirir(["a", "b"]):
            pass
    assert r.dados == {"b": "de-outro"}


def test_redis_em_baixo_levanta_redis_indisponivel():
    with pytest.raises(RedisIndisponivel):
        with LocksRedis(RedisFalso(falha=True)).adquirir(["a"]):
            pass


def test_liberta_mesmo_se_o_corpo_falhar():
    r = RedisFalso()
    with pytest.raises(ValueError):
        with LocksRedis(r).adquirir(["a"]):
            raise ValueError("erro")
    assert r.dados == {}
