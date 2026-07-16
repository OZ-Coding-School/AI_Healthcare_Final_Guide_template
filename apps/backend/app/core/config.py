import logging
import uuid
import zoneinfo
from dataclasses import field
from enum import StrEnum
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Env(StrEnum):
    LOCAL = "local"
    DEV = "dev"
    PROD = "prod"


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    ENV: Env = Env.LOCAL
    SECRET_KEY: str = f"default-secret-key{uuid.uuid4().hex}"
    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))
    BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
    TEMPLATE_DIR: Path = BASE_DIR / "templates"
    MEDIA_DIR: Path = BASE_DIR / "media"

    LOG_LEVEL: int = logging.INFO

    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "pw1234"
    DB_NAME: str = "ai_health"
    DB_CONNECT_TIMEOUT: int = 5
    DB_CONNECTION_POOL_MAXSIZE: int = 10

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_USER: str = "default"
    REDIS_PASSWORD: str = "1234"
    REDIS_DB: int = 0
    REDIS_MAX_CONNECTION: int = 100

    COOKIE_DOMAIN: str = "localhost"
    CORS_ALLOW_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 14 * 24 * 60
    JWT_LEEWAY: int = 5

    SMTP_PORT: int = 587
    SMTP_USERNAME: str = "example@gmail.com"
    SMTP_PASSWORD: SecretStr = SecretStr("password")
    SMTP_FROM: str = "example@gmail.com"
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_START_TLS: bool = True
    SMTP_SSL_TLS: bool = False
    EMAIL_VERIFICATION_TTL: int = 600

    def __init__(self, **data) -> None:
        super().__init__(**data)
        self.REDIS_URL = self.get_redis_url()

    def get_redis_url(self) -> str:
        return f"redis://{self.REDIS_USER}:{self.REDIS_PASSWORD}@{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


settings = Config()
