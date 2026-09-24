"""Chooses the provider for each agent from settings (AGENT_<NAME>_PROVIDER in .env)."""

from app.core.config import AgentName, get_settings
from app.llm.anthropic_provider import AnthropicProvider
from app.llm.base import LLMProvider, LLMUnavailableError
from app.llm.fake_provider import FakeProvider
from app.llm.ollama_provider import OllamaProvider

# Tests swap providers in here instead of patching settings.
_overrides: dict[str, LLMProvider] = {}
# One provider (and so one HTTP connection pool) per backend + model.
_cache: dict[tuple[str, str], LLMProvider] = {}


def set_provider_override(agent: AgentName, provider: LLMProvider | None) -> None:
    if provider is None:
        _overrides.pop(agent, None)
    else:
        _overrides[agent] = provider


def clear_provider_cache() -> None:
    """Forget cached providers so they are rebuilt from current settings (overrides are kept)."""
    _cache.clear()


def clear_provider_overrides() -> None:
    _overrides.clear()
    _cache.clear()


def get_provider(agent: AgentName) -> LLMProvider:
    if agent in _overrides:
        return _overrides[agent]

    settings = get_settings()
    kind = settings.provider_for(agent)
    override_model = settings.model_override_for(agent)

    if kind == "fake":
        return FakeProvider()

    if kind == "api":
        model = override_model or settings.anthropic_model
        if not model:
            raise LLMUnavailableError(
                f"No model configured for the {agent} agent: "
                f"set ANTHROPIC_MODEL or AGENT_{agent.upper()}_MODEL"
            )
        if ("api", model) not in _cache:
            _cache[("api", model)] = AnthropicProvider(
                model,
                api_key=settings.anthropic_api_key,
                max_tokens=settings.anthropic_max_tokens,
                refusal_fallback=settings.anthropic_refusal_fallback,
            )
        return _cache[("api", model)]

    model = override_model or settings.ollama_model
    if not model:
        raise LLMUnavailableError(
            f"No model configured for the {agent} agent: set OLLAMA_MODEL or AGENT_{agent.upper()}_MODEL"
        )
    if ("local", model) not in _cache:
        _cache[("local", model)] = OllamaProvider(
            model,
            base_url=settings.ollama_base_url,
            timeout=settings.ollama_timeout_seconds,
            num_ctx=settings.ollama_num_ctx,
            max_tokens=settings.ollama_max_tokens,
            keep_alive=settings.ollama_keep_alive,
        )
    return _cache[("local", model)]
