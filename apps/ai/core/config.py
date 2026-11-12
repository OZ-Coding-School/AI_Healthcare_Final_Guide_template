import zoneinfo
from dataclasses import field
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))
    DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
    DOCS_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent / "docs"
    MODEL_DIR: Path = Path(__file__).resolve().parent.parent / "artifacts/models"
    MODEL_REPORT_DIR: Path = Path(__file__).resolve().parent.parent / "artifacts/reports"

    # Redis: Backend(apps/backend/app/core/config.py)와 같은 환경변수 이름을 사용합니다.
    # 컨테이너 밖에서 실행할 때는 REDIS_HOST=localhost로 지정합니다.
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_USER: str = "default"
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0


settings = Config()
