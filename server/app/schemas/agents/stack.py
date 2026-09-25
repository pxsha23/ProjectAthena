from typing import Literal

from pydantic import Field

from app.schemas.agents.idea import ProjectSpec
from app.schemas.base import StrictModel

StackLayer = Literal["frontend", "backend", "database", "auth", "hosting", "other"]


class StackAgentInput(StrictModel):
    spec: ProjectSpec
    student_notes: str = Field(
        default="",
        description="What the student told the Tech Stack Agent: languages they know, what they want to "
        "learn, time available, hosting. Empty if they have not said anything yet.",
    )


class StackChoice(StrictModel):
    layer: StackLayer
    name: str = Field(description='Main technology, e.g. "React + Vite + TypeScript" or "FastAPI (Python)".')
    reason: str = Field(description="One or two sentences tying the choice to the spec.")
    alternatives: list[str] = Field(default_factory=list)


class StackPlan(StrictModel):
    """Output of the Tech Stack Agent."""

    choices: list[StackChoice] = Field(min_length=1)
    backend_language: Literal["python", "typescript", "javascript", "none"]
    frontend_framework: Literal["react", "vue", "svelte", "nextjs", "none"]
    backend_framework: Literal["fastapi", "flask", "django", "express", "nextjs", "none"]
    database: Literal["postgresql", "mysql", "sqlite", "mongodb", "none"]
