import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


class Config:
    # Production must provide a strong random SECRET_KEY via the host environment.
    IS_PRODUCTION = os.environ.get("APP_ENV", "").lower() == "production" or os.environ.get("RENDER", "").lower() in {"1", "true", "yes"}
    SECRET_KEY = os.environ.get("SECRET_KEY") or (
        None if IS_PRODUCTION else "local-only-development-key-not-for-deployment"
    )
    DATABASE_URL = os.environ.get("DATABASE_URL")
    if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
    elif DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
    SQLALCHEMY_DATABASE_URI = DATABASE_URL or f"sqlite:///{BASE_DIR / 'instance' / 'farm.db'}"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get(
        "SESSION_COOKIE_SECURE", "true" if IS_PRODUCTION else "false"
    ).lower() == "true"
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 8  # 8 hours
    SESSION_REFRESH_EACH_REQUEST = True
    WTF_CSRF_TIME_LIMIT = 3600
    MAX_CONTENT_LENGTH = 6 * 1024 * 1024
    SITE_URL = os.environ.get("SITE_URL", "https://shreedogadabhumiraj.onrender.com")
