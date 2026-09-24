"""Deterministic provider ("fake") for tests and for running Athena without any LLM."""

from collections import defaultdict, deque
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from app.llm.base import LLMOutputError, LLMResult, TextResult
from app.llm.fake_data import CANNED, NAIVE_TEXT

T = TypeVar("T", bound=BaseModel)


class FakeProvider:
    name = "fake"

    def __init__(self, model: str = "fake-model") -> None:
        self.model = model
        # Per-schema queue of scripted responses: a dict (validated against the schema) or an Exception.
        self._queued: dict[type, deque[Any]] = defaultdict(deque)
        self.calls: list[dict[str, Any]] = []
        # Per-kind queue of scripted free-text answers (str) or Exceptions, for the naive mode.
        self._queued_text: dict[str, deque[Any]] = defaultdict(deque)

    def queue(self, schema: type[BaseModel], *responses: Any) -> None:
        self._queued[schema].extend(responses)

    def queue_text(self, kind: str, *responses: Any) -> None:
        self._queued_text[kind].extend(responses)

    async def generate(
        self, *, system: str, prompt: str, schema: type[T], max_tokens: int | None = None
    ) -> LLMResult[T]:
        self.calls.append({"schema": schema.__name__, "system": system, "prompt": prompt})
        if self._queued[schema]:
            response = self._queued[schema].popleft()
        elif schema in CANNED:
            response = CANNED[schema]
        else:
            raise LLMOutputError(f"FakeProvider has no canned output for {schema.__name__}")

        if isinstance(response, Exception):
            raise response
        try:
            output = schema.model_validate(response)
        except ValidationError as exc:
            raise LLMOutputError(f"Response did not match {schema.__name__}: {exc}") from exc
        # Rough token estimate so the metrics tables have realistic-looking numbers.
        return LLMResult(
            output=output,
            input_tokens=(len(system) + len(prompt)) // 4,
            output_tokens=len(output.model_dump_json()) // 4,
            model=self.model,
        )

    async def generate_text(
        self, *, system: str, prompt: str, kind: str, max_tokens: int | None = None
    ) -> TextResult:
        self.calls.append({"kind": kind, "system": system, "prompt": prompt})
        if self._queued_text[kind]:
            response = self._queued_text[kind].popleft()
        elif kind in NAIVE_TEXT:
            response = NAIVE_TEXT[kind]
        else:
            raise LLMOutputError(f"FakeProvider has no canned text for {kind}")
        if isinstance(response, Exception):
            raise response
        return TextResult(
            text=response,
            input_tokens=(len(system) + len(prompt)) // 4,
            output_tokens=len(response) // 4,
            model=self.model,
        )
