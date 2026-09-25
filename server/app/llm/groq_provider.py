"""Groq provider ("groq"): hosted open models through Groq's OpenAI-compatible API, with a free tier.

Structured output uses `response_format` json_schema in best-effort mode (strict mode needs every field
to be required, which our schemas do not do). The answer is then validated with Pydantic like every
other provider, so a schema miss becomes an LLMOutputError and the agent retries with the error.
"""

import asyncio
import json
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.llm.base import LLMOutputError, LLMResult, LLMUnavailableError, TextResult

T = TypeVar("T", bound=BaseModel)

# Wait for a rate limit to reset only when the wait is short; otherwise report it to the user.
MAX_RATE_LIMIT_WAIT_SECONDS = 20.0


class GroqProvider:
    name = "groq"

    def __init__(
        self,
        model: str,
        *,
        api_key: str | None,
        base_url: str = "https://api.groq.com/openai/v1",
        timeout: float = 120.0,
        max_tokens: int = 6000,
        reasoning_effort: str | None = "low",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise LLMUnavailableError("GROQ_API_KEY is not set")
        self.model = model
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self._client = httpx.AsyncClient(
            base_url=base_url,
            timeout=timeout,
            transport=transport,
            headers={"Authorization": f"Bearer {api_key}"},
        )

    def _body(self, system: str, prompt: str, max_tokens: int | None) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_completion_tokens": max_tokens or self.max_tokens,
        }
        # Reasoning models (gpt-oss) think before answering; those tokens count against the rate limit.
        if self.reasoning_effort and self.model.startswith("openai/gpt-oss"):
            body["reasoning_effort"] = self.reasoning_effort
            body["include_reasoning"] = False
        return body

    async def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        for attempt in range(2):
            try:
                response = await self._client.post("/chat/completions", json=body)
            except httpx.HTTPError as exc:
                raise LLMUnavailableError(f"Could not reach Groq: {exc}") from exc
            if response.status_code == 429 and attempt == 0:
                wait = _retry_after(response)
                if wait is not None and wait <= MAX_RATE_LIMIT_WAIT_SECONDS:
                    await asyncio.sleep(wait)
                    continue
            if response.status_code == 429:
                raise LLMUnavailableError(
                    "The free AI model is busy (rate limit reached). "
                    "Please wait a minute and run the stage again."
                )
            if response.status_code == 400 and _error_code(response) == "json_validate_failed":
                # The model answered, but its JSON broke the schema: retrying with feedback may help.
                raise LLMOutputError(f"Response did not match the schema: {_error_message(response)}")
            if response.status_code >= 400:
                raise LLMUnavailableError(f"Groq returned {response.status_code}: {_error_message(response)}")
            return response.json()
        raise AssertionError("unreachable")

    async def generate(
        self, *, system: str, prompt: str, schema: type[T], max_tokens: int | None = None
    ) -> LLMResult[T]:
        json_schema = schema.model_json_schema(by_alias=True)
        body = self._body(
            # The schema in the prompt carries the field descriptions, which improves what goes in them.
            f"{system}\n\nRespond with a single JSON object that matches this JSON schema:\n"
            f"{json.dumps(json_schema)}",
            prompt,
            max_tokens,
        )
        body["response_format"] = {
            "type": "json_schema",
            "json_schema": {"name": schema.__name__, "strict": False, "schema": json_schema},
        }
        data = await self._post(body)
        content, finish_reason = _first_choice(data)
        if finish_reason == "length":
            raise LLMOutputError("Output was cut off by the token limit; give a shorter answer")
        try:
            output = schema.model_validate_json(content)
        except ValidationError as exc:
            raise LLMOutputError(f"Response did not match {schema.__name__}: {exc}") from exc
        usage = data.get("usage") or {}
        return LLMResult(
            output=output,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            model=data.get("model", self.model),
        )

    async def generate_text(
        self, *, system: str, prompt: str, kind: str, max_tokens: int | None = None
    ) -> TextResult:
        data = await self._post(self._body(system, prompt, max_tokens))
        content, finish_reason = _first_choice(data)
        if finish_reason == "length":
            raise LLMOutputError("Output was cut off by the token limit")
        usage = data.get("usage") or {}
        return TextResult(
            text=content,
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            model=data.get("model", self.model),
        )


def _first_choice(data: dict[str, Any]) -> tuple[str, str | None]:
    choices = data.get("choices") or [{}]
    message = choices[0].get("message") or {}
    return message.get("content") or "", choices[0].get("finish_reason")


def _retry_after(response: httpx.Response) -> float | None:
    try:
        return float(response.headers.get("retry-after", ""))
    except ValueError:
        return None


def _error_code(response: httpx.Response) -> str | None:
    try:
        return response.json().get("error", {}).get("code")
    except ValueError:
        return None


def _error_message(response: httpx.Response) -> str:
    try:
        return str(response.json().get("error", {}).get("message", response.text))[:500]
    except ValueError:
        return response.text[:500]
