from functools import lru_cache
from redis import Redis
from app.core.config import get_settings


@lru_cache
def get_redis() -> Redis:
    redis_url = get_settings().redis_url.get_secret_value()
    return Redis.from_url(redis_url, decode_responses=True)
