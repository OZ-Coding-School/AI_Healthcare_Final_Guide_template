import logging
import uuid
import zoneinfo
from dataclasses import field
from enum import StrEnum
from pathlib import Path
from typing import Literal

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

    # 질병 위험도 예측 SSE: Nginx proxy_read_timeout(기본 60초)보다 짧게 유지합니다.
    PREDICTION_SSE_TIMEOUT_SECONDS: int = 30
    # 결과를 기다리는 동안 이 간격으로 heartbeat를 보내고 연결 종료 여부를 확인합니다.
    PREDICTION_SSE_HEARTBEAT_SECONDS: int = 10

    # LLM(Claude) 챌린지 추천: 키가 비어 있으면 추천은 LLM_NOT_CONFIGURED로 실패 처리됩니다.
    ANTHROPIC_API_KEY: SecretStr = SecretStr("")
    ANTHROPIC_API_URL: str = "https://api.anthropic.com/v1/messages"
    ANTHROPIC_API_VERSION: str = "2026-10-21"
    LLM_MODEL: str = "claude-haiku-5-5"
    # Claude Haiku 5.5는 thinking 필드를 생략하면 기본으로 생각(adaptive thinking)하고, 생각 토큰도 max_tokens에 포함됩니다.
    # effort로 생각 분량을 조절합니다. low에서 1회 추천 출력은 보통 1,000~2,400토큰이고,
    # 흡연·음주 요인이 겹친 복잡한 경우 3,400토큰까지 쓰므로 max_tokens는 여유를 두고 6144로 둡니다.
    LLM_EFFORT: Literal["low", "medium", "high", "xhigh", "max"] = "low"
    LLM_MAX_TOKENS: int = 6144
    LLM_TIMEOUT_SECONDS: float = 30.0
    # 호출 실패·응답 형식 오류를 합친 최대 시도 횟수
    LLM_MAX_ATTEMPTS: int = 2

    # 예측 1건당 추천할 챌린지 수
    CHALLENGE_RECOMMENDATION_COUNT: int = 3
    # 추천 챌린지 수락 기한(일)
    CHALLENGE_ACCEPT_EXPIRE_DAYS: int = 7
    # 주기형(일간·주간·월간) 챌린지 완료 기준: 기간이 끝났을 때 목표 회차 중 이 비율 이상 성공하면 완료, 미만이면 실패
    CHALLENGE_SUCCESS_RATE: float = 0.8
    # 횟수형 챌린지 기한(일): 수락 후 이 기간 안에 목표 횟수를 채우면 완료 (하루 최대 1회 기록)
    CHALLENGE_COUNT_BASED_DAYS: int = 30
    # 생성 중(PROCESSING) 상태가 이 시간보다 오래되면 서버 재시작 등으로 중단된 것으로 보고 다시 시작합니다.
    CHALLENGE_RECOMMENDATION_STALE_SECONDS: int = 300

    # Redis 캐시 TTL(초). Cache Stampede를 막기 위해 실제 TTL은 기본값에 0~CACHE_TTL_JITTER_RATIO만큼 무작위로 더합니다.
    CHALLENGE_RECOMMENDATION_CACHE_TTL_SECONDS: int = 600  # 완료된 챌린지 추천 (완료 후 내용이 바뀌지 않음)
    CHALLENGE_LIST_CACHE_TTL_SECONDS: int = 60  # 내 챌린지 목록
    CACHE_TTL_JITTER_RATIO: float = 0.2

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
