"""Provider-neutral interface every LLM backend implements."""

from dataclasses import dataclass
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMResult(Generic[T]):
    output: T
    input_tokens: int
    output_tokens: int
    model: str


@dataclass
class TextResult:
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMError(Exception):
    """Base class for provider failures."""


class LLMOutputError(LLMError):
    """The model answered, but not with valid output for the schema. Retrying with feedback may help."""


class LLMRefusalError(LLMError):
    """The model declined the request."""


class LLMUnavailableError(LLMError):
    """The provider could not be reached, is misconfigured, or kept failing after its own retries."""


class LLMProvider(Protocol):
    name: str
    model: str

    async def generate(
        self, *, system: str, prompt: str, schema: type[T], max_tokens: int | None = None
    ) -> LLMResult[T]:
        """Return an instance of `schema` or raise an LLMError subclass."""
        ...

    async def generate_text(
        self, *, system: str, prompt: str, kind: str, max_tokens: int | None = None
    ) -> TextResult:
        """Free-text answer with no schema (the naive baseline of Paper 1).

        `kind` names what is being produced ("spec", "stack", "code"); only the fake provider uses it.
        """
        ...
