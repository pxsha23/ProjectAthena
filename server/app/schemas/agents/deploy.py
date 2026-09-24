from typing import Literal

from pydantic import Field

from app.schemas.agents.code import GeneratedFile
from app.schemas.agents.stack import StackPlan
from app.schemas.base import StrictModel


class DeployAgentInput(StrictModel):
    stack: StackPlan | None
    files: list[GeneratedFile]


class StackDetection(StrictModel):
    """What the rule-based detector found by reading the project files."""

    backend_language: Literal["python", "node", "none"]
    backend_framework: str | None
    backend_dir: str | None = Field(description='Folder holding the backend, "" for the project root.')
    python_entry_module: str | None = Field(description='e.g. "main:app" for uvicorn.')
    frontend_framework: str | None
    frontend_dir: str | None
    database: Literal["postgresql", "mysql", "sqlite", "mongodb", "none"]
    evidence: list[str] = Field(description="Which files or lines led to each conclusion.")


class DeploymentTarget(StrictModel):
    id: str
    name: str
    description: str
    files: list[str]


class DeploymentBundle(StrictModel):
    """Output of the Deployment Agent (rule-based, no LLM)."""

    detection: StackDetection
    targets: list[DeploymentTarget]
    files: list[GeneratedFile]
