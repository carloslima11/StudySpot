import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret")
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "sqlite:///studyspot.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    BOOKING_API_URL = os.getenv("BOOKING_API_URL", "http://localhost:8080")