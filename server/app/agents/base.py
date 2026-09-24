"""Base class shared by every LLM-backed agent.

Contract (the core of Research Paper 1):
- Input is a strict Pydantic model; output must validate against a strict Pydantic model.
- Invalid output is retried with the validation error fed back, up to AGENT_MAX_RETRIES times.
- Every run is logged to agent_runs: duration, tokens, retries, validation errors, pass/fail.
"""

import time
from dataclasses import dataclass
from typing import ClassVar, Generic, TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AgentName, get_settings
from app.core.db import utcnow
from app.llm.base import LLMError, LLMOutputError, LLMProvider
from app.llm.factory import get_provider
from app.models import AgentRun

BASE_RULES = (
    "You are one agent in Athena, a platform that takes a student's app idea from spec to deployed code. "
    "Write for a university student: clear, concrete and friendly. Never use emoji. "
    "Answer only with data that matches the required output schema."
)


class AgentRunFailed(Exception):
    def __init__(self, agent: str, run_id: str, message: str) -> None:
        super().__init__(f"{agent} agent failed: {message}")
        self.agent = agent
        self.run_id = run_id
        self.message = message


InT = TypeVar("InT", bound=BaseModel)
OutT = TypeVar("OutT", bound=BaseModel)


@dataclass
class AgentOutcome(Generic[OutT]):
    output: OutT
    run: AgentRun


class BaseAgent(Generic[InT, OutT]):
    name: ClassVar[AgentName]
    output_model: ClassVar[type[BaseModel]]
    instructions: ClassVar[str]
    max_tokens: ClassVar[int | None] = None

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self._provider = provider

    @property
    def provider(self) -> LLMProvider:
        if self._provider is None:
            self._provider = get_provider(self.name)
        return self._provider

    def system_prompt(self) -> str:
        return f"{BASE_RULES}\n\n{self.instructions}"

    def build_prompt(self, data: InT) -> str:
        return f"Input (JSON):\n{data.model_dump_json(by_alias=True, indent=2)}"

    def check_output(self, data: InT, output: OutT) -> None:
        """Extra semantic checks beyond the schema. Raise ValueError to trigger a retry."""

    async def run(
        self, session: AsyncSession, data: InT, *, project_id: str | None, stage: str | None = None
    ) -> AgentOutcome[OutT]:
        started = time.perf_counter()
        run = AgentRun(
            project_id=project_id,
            agent=self.name,
            stage=stage,
            provider="unknown",
            status="running",
            input_json=data.model_dump(mode="json", by_alias=True),
            validation_errors=[],
        )
        session.add(run)
        await session.commit()

        max_retries = get_settings().agent_max_retries
        prompt = self.build_prompt(data)
        errors: list[dict] = []
        input_tokens = output_tokens = attempts = 0

        try:
            provider = self.provider
            run.provider, run.model = provider.name, provider.model
            for attempt in range(max_retries + 1):
                attempts += 1
                try:
                    result = await provider.generate(
                        system=self.system_prompt(),
                        prompt=prompt,
                        schema=self.output_model,
                        max_tokens=self.max_tokens,
                    )
                    input_tokens += result.input_tokens
                    output_tokens += result.output_tokens
                    run.model = result.model
                    try:
                        self.check_output(data, result.output)  # type: ignore[arg-type]
                    except ValueError as exc:
                        raise LLMOutputError(str(exc)) from exc
                except LLMOutputError as exc:
                    errors.append({"attempt": attempt + 1, "error": str(exc)[:2000]})
                    if attempt == max_retries:
                        raise
                    prompt = (
                        f"{self.build_prompt(data)}\n\n"
                        f"Your previous answer was rejected:\n{str(exc)[:2000]}\n"
                        "Return a corrected answer that satisfies the schema and every rule above."
                    )
                    continue

                run.status = "succeeded"
                run.output_json = result.output.model_dump(mode="json", by_alias=True)
                return AgentOutcome(output=result.output, run=run)  # type: ignore[arg-type]

            raise AssertionError("unreachable")
        except LLMError as exc:
            run.status = "failed"
            run.error = str(exc)[:4000]
            raise AgentRunFailed(self.name, run.id, str(exc)) from exc
        finally:
            run.retries = max(0, attempts - 1)
            run.validation_errors = errors
            run.input_tokens, run.output_tokens = input_tokens, output_tokens
            run.finished_at = utcnow()
            run.duration_ms = int((time.perf_counter() - started) * 1000)
            await session.commit()
