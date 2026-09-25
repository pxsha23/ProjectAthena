"""Groq provider: request shape, parsing, and how each kind of failure is reported."""

import json

import httpx
import pytest

from app.core.config import get_settings
from app.llm.base import LLMOutputError, LLMUnavailableError
from app.llm.factory import clear_provider_cache, get_provider
from app.llm.fake_data import SPEC
from app.llm.groq_provider import GroqProvider
from app.schemas.agents import ProjectSpec


def groq_with(handler, model: str = "openai/gpt-oss-120b") -> GroqProvider:
    return GroqProvider(
        model, api_key="test-key", base_url="http://groq", transport=httpx.MockTransport(handler)
    )


def completion(content: str, finish_reason: str = "stop") -> dict:
    return {
        "model": "openai/gpt-oss-120b",
        "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
        "usage": {"prompt_tokens": 11, "completion_tokens": 22},
    }


async def test_groq_sends_schema_and_parses_response() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["path"] = request.url.path
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=completion(json.dumps(SPEC)))

    result = await groq_with(handler).generate(system="sys", prompt="p", schema=ProjectSpec)
    assert result.output.target_users == SPEC["targetUsers"]
    assert (result.input_tokens, result.output_tokens, result.model) == (11, 22, "openai/gpt-oss-120b")
    assert seen["auth"] == "Bearer test-key" and seen["path"] == "/chat/completions"
    fmt = seen["response_format"]
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is False
    assert fmt["json_schema"]["schema"]["properties"]["targetUsers"]
    assert seen["messages"][0]["content"].startswith("sys\n\nRespond with a single JSON object")
    assert seen["reasoning_effort"] == "low" and seen["include_reasoning"] is False
    assert seen["max_completion_tokens"] == 6000


async def test_groq_reasoning_options_only_for_reasoning_models() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(200, json=completion("plain answer"))

    result = await groq_with(handler, model="llama-test").generate_text(system="s", prompt="p", kind="spec")
    assert result.text == "plain answer"
    assert "reasoning_effort" not in seen and "response_format" not in seen


async def test_groq_output_errors_are_retryable() -> None:
    wrong_shape = groq_with(lambda r: httpx.Response(200, json=completion('{"summary": 1}')))
    with pytest.raises(LLMOutputError):
        await wrong_shape.generate(system="s", prompt="p", schema=ProjectSpec)

    cut_off = groq_with(lambda r: httpx.Response(200, json=completion("{", finish_reason="length")))
    with pytest.raises(LLMOutputError, match="cut off"):
        await cut_off.generate(system="s", prompt="p", schema=ProjectSpec)

    schema_miss = groq_with(
        lambda r: httpx.Response(
            400, json={"error": {"code": "json_validate_failed", "message": "missing summary"}}
        )
    )
    with pytest.raises(LLMOutputError, match="missing summary"):
        await schema_miss.generate(system="s", prompt="p", schema=ProjectSpec)


async def test_groq_rate_limits() -> None:
    calls = []

    def short_wait(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "0"}, json={"error": {"message": "slow down"}})
        return httpx.Response(200, json=completion(json.dumps(SPEC)))

    await groq_with(short_wait).generate(system="s", prompt="p", schema=ProjectSpec)
    assert len(calls) == 2

    long_wait = groq_with(lambda r: httpx.Response(429, headers={"retry-after": "600"}, json={}))
    with pytest.raises(LLMUnavailableError, match="rate limit"):
        await long_wait.generate(system="s", prompt="p", schema=ProjectSpec)

    down = groq_with(lambda r: httpx.Response(503, json={"error": {"message": "over capacity"}}))
    with pytest.raises(LLMUnavailableError, match="over capacity"):
        await down.generate(system="s", prompt="p", schema=ProjectSpec)


def test_groq_needs_a_key() -> None:
    with pytest.raises(LLMUnavailableError, match="GROQ_API_KEY"):
        GroqProvider("m", api_key=None)


def test_factory_builds_groq_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_chat_provider", "groq")
    monkeypatch.setattr(settings, "groq_api_key", "k")
    monkeypatch.setattr(settings, "groq_model", "openai/gpt-oss-20b")
    clear_provider_cache()
    provider = get_provider("chat")
    assert isinstance(provider, GroqProvider) and provider.model == "openai/gpt-oss-20b"
    clear_provider_cache()
