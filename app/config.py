from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Salamatian"
    APP_ENV: str = "development"
    DEBUG: bool = False
    SECRET_KEY: str = "dev-secret-change-me"
    BASE_URL: str = "http://localhost:8000"

    DATABASE_URL: str = "postgresql+asyncpg://salamatian:salamatian@postgres:8003/salamatian"

    REDIS_URL: str = "redis://redis:8002/0"
    CELERY_BROKER_URL: str = "redis://redis:8002/1"
    CELERY_RESULT_BACKEND: str = "redis://redis:8002/2"

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 14

    STORAGE_ROOT: Path = Path("/app/storage/uploads")
    EXCEL_INBOX_DIR: Path = Path("/app/storage/uploads/excel/inbox")
    MAX_IMAGE_SIZE_MB: int = 5
    MAX_LEAD_IMAGES: int = 10

    PUBLIC_LEAD_RATE_PER_HOUR: int = 10

    BOOTSTRAP_ADMIN_USERNAME: str = "admin"
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@salamatian.local"
    BOOTSTRAP_ADMIN_PASSWORD: str = "ChangeMe!123"

    TELEGRAM_BOT_TOKEN: str | None = None
    TELEGRAM_CHAT_ID: str | None = None
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USER: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM: str = "no-reply@salamatian.local"

    CACHE_TTL_LIST: int = 60
    CACHE_TTL_DETAIL: int = 300

    @property
    def cars_upload_dir(self) -> Path:
        return self.STORAGE_ROOT / "cars"

    @property
    def leads_upload_dir(self) -> Path:
        return self.STORAGE_ROOT / "leads"

    @property
    def excel_upload_dir(self) -> Path:
        return self.STORAGE_ROOT / "excel"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
