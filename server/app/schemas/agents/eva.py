from typing import Literal

from pydantic import Field, model_validator

from app.schemas.agents.code import GeneratedFile
from app.schemas.agents.idea import ProjectSpec
from app.schemas.base import StrictModel

# Virtual users are identified by codenames, never by personal names.
PersonaCodename = Literal["Alpha", "Bravo", "Charlie", "Delta", "Echo"]


class EvaAgentInput(StrictModel):
    spec: ProjectSpec
    files: list[GeneratedFile]


class EvaPersona(StrictModel):
    id: str = Field(description='Short id such as "p1".')
    name: PersonaCodename
    archetype: str = Field(description='Kind of user, e.g. "First-year student".')
    goal: str = Field(description="What this user is trying to do in the app.")


class EvaFinding(StrictModel):
    id: str
    persona_id: str
    severity: Literal["pass", "warn", "fail"]
    title: str
    detail: str = Field(description="What happened and a concrete suggestion to fix it.")


class EvaReport(StrictModel):
    """Output of EVA: a simulated usability test based on reading the code (nothing is executed)."""

    score: int = Field(ge=0, le=100)
    personas: list[EvaPersona] = Field(min_length=2, max_length=5)
    findings: list[EvaFinding] = Field(min_length=1)

    @model_validator(mode="after")
    def findings_reference_personas(self) -> "EvaReport":
        ids = {p.id for p in self.personas}
        unknown = {f.persona_id for f in self.findings} - ids
        if unknown:
            raise ValueError(f"findings reference unknown personas: {sorted(unknown)}")
        return self
