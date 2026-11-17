"""
LLM 호출 클라이언트입니다. 공급자 SDK 없이 기존 의존성인 httpx로 Claude Messages API를 호출합니다.

- 응답 형식은 Structured outputs(output_config.format=json_schema)로 JSON 스키마를 지정합니다.
- 서비스는 LLMClient 프로토콜에만 의존하므로, 테스트에서는 가짜 클라이언트로 바꿔 끼웁니다.
- API 키와 프롬프트·응답 본문은 로그에 남기지 않습니다.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx

from app.core import logger, settings

# 일시적인 장애로 보고 다시 시도할 수 있는 상태 코드 (429 요청 한도, 5xx 서버 오류, 529 과부하)
RETRYABLE_STATUS_CODES = {408, 429, 500, 502, 503, 504, 529}


class LLMError(Exception):
    """LLM 호출 실패의 공통 부모입니다."""


class LLMNotConfiguredError(LLMError):
    """API 키가 설정되지 않았습니다."""


class LLMUnavailableError(LLMError):
    """네트워크 오류, 시간 초과, 요청 한도, 서버 오류처럼 다시 시도하면 성공할 수 있는 실패입니다."""


class LLMRequestError(LLMError):
    """잘못된 키·모델·요청 형식처럼 다시 시도해도 실패하는 요청입니다."""

    def __init__(self, status_code: int, error_type: str | None) -> None:
        super().__init__(f"LLM request rejected: status={status_code}, type={error_type}")
        self.status_code = status_code
        self.error_type = error_type


@dataclass(frozen=True)
class LLMResponse:
    text: str
    model: str
    stop_reason: str | None
    usage: dict[str, Any] = field(default_factory=dict)


class LLMClient(Protocol):
    model_name: str

    async def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> LLMResponse:
        """system·user 프롬프트로 schema를 따르는 JSON 문자열을 생성합니다."""
        ...


class ClaudeClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        api_url: str = "https://api.anthropic.com/v1/messages",
        api_version: str = "2026-10-21",
        max_tokens: int = 2048,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self.model_name = model
        self._api_url = api_url
        self._api_version = api_version
        self._max_tokens = max_tokens
        self._timeout = timeout_seconds
        self._transport = transport

    async def generate_json(self, system: str, user: str, schema: dict[str, Any]) -> LLMResponse:
        if not self._api_key:
            raise LLMNotConfiguredError("ANTHROPIC_API_KEY is not set.")

        body = {
            "model": self.model_name,
            "max_tokens": self._max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
        }
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self._api_version,
            "content-type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
                response = await client.post(self._api_url, json=body, headers=headers)
        except httpx.HTTPError as error:
            raise LLMUnavailableError(f"LLM request failed: {type(error).__name__}") from None

        if response.status_code != httpx.codes.OK:
            error_type = _error_type(response)
            logger.warning("LLM request failed: status=%s, type=%s", response.status_code, error_type)
            if response.status_code in RETRYABLE_STATUS_CODES:
                raise LLMUnavailableError(f"LLM service error: status={response.status_code}")
            raise LLMRequestError(response.status_code, error_type)

        try:
            data = response.json()
            text = "".join(block.get("text", "") for block in data.get("content", []) if block.get("type") == "text")
        except (ValueError, AttributeError, TypeError):
            raise LLMUnavailableError("LLM returned an unreadable response.") from None
        return LLMResponse(
            text=text,
            model=str(data.get("model") or self.model_name),
            stop_reason=data.get("stop_reason"),
            usage=data.get("usage") or {},
        )


def _error_type(response: httpx.Response) -> str | None:
    try:
        error = response.json().get("error") or {}
        return error.get("type")
    except (ValueError, AttributeError):
        return None


def get_llm_client() -> LLMClient:
    return ClaudeClient(
        api_key=settings.ANTHROPIC_API_KEY.get_secret_value(),
        model=settings.LLM_MODEL,
        api_url=settings.ANTHROPIC_API_URL,
        api_version=settings.ANTHROPIC_API_VERSION,
        max_tokens=settings.LLM_MAX_TOKENS,
        timeout_seconds=settings.LLM_TIMEOUT_SECONDS,
    )
