import json

import httpx
import pytest

from app.core.llm import ClaudeClient, LLMNotConfiguredError, LLMRequestError, LLMUnavailableError

SCHEMA = {"type": "object", "properties": {}, "required": [], "additionalProperties": False}


def make_client(handler, api_key: str = "test-key") -> ClaudeClient:
    return ClaudeClient(
        api_key=api_key,
        model="claude-haiku-5-5",
        api_url="https://api.anthropic.com/v1/messages",
        api_version="2026-10-21",
        max_tokens=1024,
        transport=httpx.MockTransport(handler),
    )


async def test_generate_json_sends_messages_request_with_json_schema() -> None:
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "model": "claude-haiku-5-5",
                "content": [{"type": "text", "text": '{"challenges": '}, {"type": "text", "text": "[]}"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 10, "output_tokens": 5},
            },
        )

    response = await make_client(handler).generate_json("system prompt", "user prompt", SCHEMA)

    assert response.text == '{"challenges": []}'
    assert response.model == "claude-haiku-5-5"
    assert response.stop_reason == "end_turn"
    assert captured["headers"]["x-api-key"] == "test-key"
    assert captured["headers"]["anthropic-version"] == "2026-10-21"
    assert captured["body"] == {
        "model": "claude-haiku-5-5",
        "max_tokens": 1024,
        "system": "system prompt",
        "messages": [{"role": "user", "content": "user prompt"}],
        "output_config": {"format": {"type": "json_schema", "schema": SCHEMA}},
    }


async def test_generate_json_requires_api_key() -> None:
    with pytest.raises(LLMNotConfiguredError):
        await make_client(lambda request: httpx.Response(200), api_key="").generate_json("s", "u", SCHEMA)


@pytest.mark.parametrize("status_code", [429, 500, 529])
async def test_retryable_status_raises_unavailable(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"type": "error", "error": {"type": "overloaded_error"}})

    with pytest.raises(LLMUnavailableError):
        await make_client(handler).generate_json("s", "u", SCHEMA)


@pytest.mark.parametrize("status_code", [400, 401, 404])
async def test_client_error_raises_request_error(status_code: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"type": "error", "error": {"type": "invalid_request_error"}})

    with pytest.raises(LLMRequestError) as error:
        await make_client(handler).generate_json("s", "u", SCHEMA)
    assert error.value.status_code == status_code
    assert error.value.error_type == "invalid_request_error"


async def test_network_error_raises_unavailable() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("timeout", request=request)

    with pytest.raises(LLMUnavailableError):
        await make_client(handler).generate_json("s", "u", SCHEMA)


async def test_unreadable_body_raises_unavailable() -> None:
    with pytest.raises(LLMUnavailableError):
        await make_client(lambda request: httpx.Response(200, text="not json")).generate_json("s", "u", SCHEMA)
