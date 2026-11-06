import os
from dotenv import load_dotenv
from redis import Redis

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("WEB_SECRET_KEY") or os.getenv("SECRET_KEY")
    SESSION_TYPE = "redis"
    SESSION_REDIS = Redis.from_url(os.getenv("SESSION_REDIS_URL", "redis://localhost:6379/1"))
    SESSION_KEY_PREFIX = "studyspot:web:"
    SESSION_PERMANENT = True
    PERMANENT_SESSION_LIFETIME = 1800
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").lower() == "true"
    AUTH_API_URL = os.getenv("AUTH_API_URL", "http://localhost:8080/api/auth")
    BOOKING_API_URL = os.getenv("BOOKING_API_URL", "http://localhost:8080")