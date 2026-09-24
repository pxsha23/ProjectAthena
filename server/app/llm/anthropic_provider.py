"""Anthropic provider ("api"). Structured output via messages.parse + Pydantic."""

from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel, ValidationError

from app.llm.base import LLMOutputError, LLMRefusalError, LLMResult, LLMUnavailableError, TextResult

T = TypeVar("T", bound=BaseModel)

# Server-side refusal fallback: if the model declines, the API re-runs the request on a
# fallback model chosen by refusal category, inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider:
    name = "api"

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None = None,
        max_tokens: int = 16000,
        refusal_fallback: bool = True,
        client: Any | None = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.refusal_fallback = refusal_fallback
        # With api_key=None the SDK reads ANTHROPIC_API_KEY (or an `ant auth login` profile).
        # The SDK itself retries connection errors, 408/409/429 and 5xx with backoff.
        self._client = client or anthropic.AsyncAnthropic(api_key=api_key)

    async def generate(
        self, *, system: str, prompt: str, schema: type[T], max_tokens: int | None = None
    ) -> LLMResult[T]:
        extra: dict[str, Any] = {}
        if self.refusal_fallback:
            extra["extra_headers"] = {"anthropic-beta": FALLBACK_BETA}
            extra["extra_body"] = {"fallbacks": "default"}

        try:
            response = await self._client.messages.parse(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                output_format=schema,
                **extra,
            )
        except ValidationError as exc:
            raise LLMOutputError(f"Response did not match {schema.__name__}: {exc}") from exc
        except anthropic.AuthenticationError as exc:
            raise LLMUnavailableError("Anthropic authentication failed; check ANTHROPIC_API_KEY") from exc
        except anthropic.BadRequestError as exc:
            raise LLMUnavailableError(f"Anthropic rejected the request: {exc.message}") from exc
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
            raise LLMUnavailableError(f"Anthropic request failed: {exc}") from exc

        usage = response.usage
        tokens = {"input_tokens": usage.input_tokens, "output_tokens": usage.output_tokens}

        if response.stop_reason == "refusal":
            raise LLMRefusalError("The model declined this request")
        if response.stop_reason == "max_tokens":
            raise LLMOutputError(
                f"Output was cut off at max_tokens={max_tokens or self.max_tokens}; "
                "raise ANTHROPIC_MAX_TOKENS"
            )
        parsed = response.parsed_output
        if parsed is None:
            raise LLMOutputError("The model returned no structured output")

        return LLMResult(output=parsed, model=response.model, **tokens)

    async def generate_text(
        self, *, system: str, prompt: str, kind: str, max_tokens: int | None = None
    ) -> TextResult:
        extra: dict[str, Any] = {}
        if self.refusal_fallback:
            extra["extra_headers"] = {"anthropic-beta": FALLBACK_BETA}
            extra["extra_body"] = {"fallbacks": "default"}
        try:
            response = await self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens or self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                **extra,
            )
        except anthropic.AuthenticationError as exc:
            raise LLMUnavailableError("Anthropic authentication failed; check ANTHROPIC_API_KEY") from exc
        except anthropic.BadRequestError as exc:
            raise LLMUnavailableError(f"Anthropic rejected the request: {exc.message}") from exc
        except (anthropic.RateLimitError, anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
            raise LLMUnavailableError(f"Anthropic request failed: {exc}") from exc

        if response.stop_reason == "refusal":
            raise LLMRefusalError("The model declined this request")
        text = "".join(block.text for block in response.content if block.type == "text")
        if response.stop_reason == "max_tokens":
            raise LLMOutputError("Output was cut off at max_tokens; raise ANTHROPIC_MAX_TOKENS")
        return TextResult(
            text=text,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            model=response.model,
        )
