import hashlib

from redis import Redis

MAX_TENTATIVAS = 5
JANELA_SEGUNDOS = 15 * 60


def _hash(valor: str) -> str:
    return hashlib.sha256(valor.encode("utf-8")).hexdigest()


def chaves_tentativas(email: str, ip: str) -> tuple[str, str]:
    return (
        f"auth:falhas:email:{_hash(email)}",
        f"auth:falhas:ip:{_hash(ip)}",
    )


def bloqueado(redis: Redis, email: str, ip: str) -> int:
    restantes = []
    for chave in chaves_tentativas(email, ip):
        quantidade = int(redis.get(chave) or 0)
        if quantidade >= MAX_TENTATIVAS:
            restantes.append(max(int(redis.ttl(chave)), 1))
    return max(restantes, default=0)


def registar_falha(redis: Redis, email: str, ip: str) -> int:
    ttls = []
    for chave in chaves_tentativas(email, ip):
        quantidade = redis.incr(chave)
        if quantidade == 1:
            redis.expire(chave, JANELA_SEGUNDOS)
        if quantidade >= MAX_TENTATIVAS:
            ttls.append(max(int(redis.ttl(chave)), 1))
    return max(ttls, default=0)


def limpar_tentativas(redis: Redis, email: str, ip: str) -> None:
    redis.delete(*chaves_tentativas(email, ip))
