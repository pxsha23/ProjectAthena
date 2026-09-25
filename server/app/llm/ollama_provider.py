"""Local Ollama provider ("local"). Uses Ollama's JSON-schema constrained output."""

import json
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

from app.llm.base import LLMOutputError, LLMResult, LLMUnavailableError, TextResult

T = TypeVar("T", bound=BaseModel)


class OllamaProvider:
    name = "local"

    def __init__(
        self,
        model: str,
        *,
        base_url: str = "http://localhost:11434",
        timeout: float = 1800.0,
        num_ctx: int = 16384,
        max_tokens: int = 8192,
        keep_alive: str = "30m",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.model = model
        self.num_ctx = num_ctx
        self.max_tokens = max_tokens
        self.keep_alive = keep_alive
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)

    async def generate(
        self, *, system: str, prompt: str, schema: type[T], max_tokens: int | None = None
    ) -> LLMResult[T]:
        json_schema = schema.model_json_schema(by_alias=True)
        # `format` constrains the output shape; showing the schema too lets small local models
        # read the field descriptions (what each field should contain), which improves quality.
        system_with_schema = (
            f"{system}\n\nRespond with a single JSON object that matches this JSON schema:\n"
            f"{json.dumps(json_schema)}"
        )
        body = {
            "model": self.model,
            "stream": False,
            "format": json_schema,
            "messages": [
                {"role": "system", "content": system_with_schema},
                {"role": "user", "content": prompt},
            ],
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": 0.2,
                "num_ctx": self.num_ctx,
                "num_predict": max_tokens or self.max_tokens,
            },
        }
        try:
            response = await self._client.post("/api/chat", json=body)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailableError(
                f"Ollama returned {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMUnavailableError(
                f"Ollama did not answer within {self._client.timeout.read} seconds; the model is too slow "
                "for this request on this machine"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Could not reach Ollama: {exc!r}") from exc

        data = response.json()
        content = (data.get("message") or {}).get("content", "")
        if data.get("done_reason") == "length":
            raise LLMOutputError(
                f"Output was cut off after {data.get('eval_count')} tokens; raise OLLAMA_MAX_TOKENS "
                "or OLLAMA_NUM_CTX"
            )
        try:
            output = schema.model_validate_json(content)
        except ValidationError as exc:
            raise LLMOutputError(f"Response did not match {schema.__name__}: {exc}") from exc

        return LLMResult(
            output=output,
            input_tokens=int(data.get("prompt_eval_count") or 0),
            output_tokens=int(data.get("eval_count") or 0),
            model=data.get("model", self.model),
        )

    async def generate_text(
        self, *, system: str, prompt: str, kind: str, max_tokens: int | None = None
    ) -> TextResult:
        body = {
            "model": self.model,
            "stream": False,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "keep_alive": self.keep_alive,
            "options": {
                "temperature": 0.2,
                "num_ctx": self.num_ctx,
                "num_predict": max_tokens or self.max_tokens,
            },
        }
        try:
            response = await self._client.post("/api/chat", json=body)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMUnavailableError(
                f"Ollama returned {exc.response.status_code}: {exc.response.text}"
            ) from exc
        except httpx.TimeoutException as exc:
            raise LLMUnavailableError(
                f"Ollama did not answer within {self._client.timeout.read} seconds; the model is too slow "
                "for this request on this machine"
            ) from exc
        except httpx.HTTPError as exc:
            raise LLMUnavailableError(f"Could not reach Ollama: {exc!r}") from exc
        data = response.json()
        if data.get("done_reason") == "length":
            raise LLMOutputError(
                f"Output was cut off after {data.get('eval_count')} tokens; raise OLLAMA_MAX_TOKENS"
            )
        return TextResult(
            text=(data.get("message") or {}).get("content", ""),
            input_tokens=int(data.get("prompt_eval_count") or 0),
            output_tokens=int(data.get("eval_count") or 0),
            model=data.get("model", self.model),
        )
