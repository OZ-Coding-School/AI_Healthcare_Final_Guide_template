import zoneinfo
from dataclasses import field
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="allow")

    TIMEZONE: zoneinfo.ZoneInfo = field(default_factory=lambda: zoneinfo.ZoneInfo("Asia/Seoul"))
    DATA_DIR: Path = Path(__file__).resolve().parent.parent / "data"
    DOCS_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent / "docs"


settings = Config()
