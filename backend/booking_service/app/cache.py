import os
from functools import lru_cache
from redis import Redis


@lru_cache
def get_redis() -> Redis:
    redis_url = os.environ.get("REDIS_URL")
    if not redis_url:
        raise RuntimeError("A variável REDIS_URL não está configurada.")

    return Redis.from_url(redis_url, decode_responses=True)
