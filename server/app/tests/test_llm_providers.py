import json
from types import SimpleNamespace

import httpx
import pytest

from app.core.config import get_settings
from app.llm.anthropic_provider import FALLBACK_BETA, AnthropicProvider
from app.llm.base import LLMOutputError, LLMRefusalError, LLMUnavailableError
from app.llm.factory import get_provider
from app.llm.fake_data import SPEC
from app.llm.ollama_provider import OllamaProvider
from app.schemas.agents import ProjectSpec


class FakeMessages:
    def __init__(self, response: SimpleNamespace) -> None:
        self.response = response
        self.kwargs: dict = {}

    async def parse(self, **kwargs):
        self.kwargs = kwargs
        return self.response


def anthropic_with(stop_reason: str, parsed=None) -> tuple[AnthropicProvider, FakeMessages]:
    response = SimpleNamespace(
        stop_reason=stop_reason,
        parsed_output=parsed,
        model="test-model",
        usage=SimpleNamespace(input_tokens=120, output_tokens=340),
    )
    messages = FakeMessages(response)
    client = SimpleNamespace(messages=messages)
    return AnthropicProvider("test-model", client=client, max_tokens=1000), messages


async def test_anthropic_returns_parsed_output_and_usage() -> None:
    spec = ProjectSpec.model_validate(SPEC)
    provider, messages = anthropic_with("end_turn", spec)
    result = await provider.generate(system="sys", prompt="hi", schema=ProjectSpec)

    assert result.output is spec
    assert (result.input_tokens, result.output_tokens, result.model) == (120, 340, "test-model")
    assert messages.kwargs["output_format"] is ProjectSpec
    assert messages.kwargs["model"] == "test-model" and messages.kwargs["system"] == "sys"
    assert messages.kwargs["extra_headers"] == {"anthropic-beta": FALLBACK_BETA}
    assert messages.kwargs["extra_body"] == {"fallbacks": "default"}


async def test_anthropic_refusal_and_truncation() -> None:
    provider, _ = anthropic_with("refusal")
    with pytest.raises(LLMRefusalError):
        await provider.generate(system="s", prompt="p", schema=ProjectSpec)

    provider, _ = anthropic_with("max_tokens")
    with pytest.raises(LLMOutputError, match="max_tokens"):
        await provider.generate(system="s", prompt="p", schema=ProjectSpec)

    provider, _ = anthropic_with("end_turn", None)
    with pytest.raises(LLMOutputError):
        await provider.generate(system="s", prompt="p", schema=ProjectSpec)


async def test_anthropic_fallback_can_be_disabled() -> None:
    provider, messages = anthropic_with("end_turn", ProjectSpec.model_validate(SPEC))
    provider.refusal_fallback = False
    await provider.generate(system="s", prompt="p", schema=ProjectSpec)
    assert "extra_body" not in messages.kwargs and "extra_headers" not in messages.kwargs


def ollama_with(handler) -> OllamaProvider:
    return OllamaProvider("llama-test", base_url="http://ollama", transport=httpx.MockTransport(handler))


async def test_ollama_sends_schema_and_parses_response() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "model": "llama-test",
                "message": {"content": json.dumps(SPEC)},
                "prompt_eval_count": 11,
                "eval_count": 22,
            },
        )

    result = await ollama_with(handler).generate(system="sys", prompt="p", schema=ProjectSpec)
    assert result.output.target_users == SPEC["targetUsers"]
    assert (result.input_tokens, result.output_tokens) == (11, 22)
    assert seen["format"]["properties"]["targetUsers"]
    assert seen["format"]["additionalProperties"] is False
    assert seen["messages"][0]["content"].startswith("sys\n\nRespond with a single JSON object")
    assert "targetUsers" in seen["messages"][0]["content"]
    assert seen["options"]["num_ctx"] == 16384 and seen["options"]["num_predict"] == 8192
    assert seen["keep_alive"] == "30m"


async def test_ollama_errors() -> None:
    bad_json = ollama_with(lambda r: httpx.Response(200, json={"message": {"content": '{"summary": 1}'}}))
    with pytest.raises(LLMOutputError):
        await bad_json.generate(system="s", prompt="p", schema=ProjectSpec)

    truncated = ollama_with(
        lambda r: httpx.Response(
            200, json={"message": {"content": "{"}, "done_reason": "length", "eval_count": 8192}
        )
    )
    with pytest.raises(LLMOutputError, match="cut off"):
        await truncated.generate(system="s", prompt="p", schema=ProjectSpec)

    down = ollama_with(lambda r: httpx.Response(500, text="model not loaded"))
    with pytest.raises(LLMUnavailableError, match="500"):
        await down.generate(system="s", prompt="p", schema=ProjectSpec)


def test_factory_requires_a_model_name(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "agent_idea_provider", "api")
    monkeypatch.setattr(settings, "anthropic_model", None)
    with pytest.raises(LLMUnavailableError, match="ANTHROPIC_MODEL"):
        get_provider("idea")

    monkeypatch.setattr(settings, "anthropic_model", "model-from-env")
    monkeypatch.setattr(settings, "agent_idea_model", "model-override")
    provider = get_provider("idea")
    assert isinstance(provider, AnthropicProvider) and provider.model == "model-override"

    monkeypatch.setattr(settings, "agent_idea_provider", "local")
    monkeypatch.setattr(settings, "agent_idea_model", None)
    monkeypatch.setattr(settings, "ollama_model", "qwen-from-env")
    assert get_provider("idea").model == "qwen-from-env"
