from typing import Literal

from pydantic import Field, field_validator

from app.schemas.agents.idea import ProjectSpec
from app.schemas.agents.stack import StackPlan
from app.schemas.base import StrictModel

FileLanguage = Literal[
    "typescript",
    "javascript",
    "python",
    "json",
    "markdown",
    "css",
    "html",
    "yaml",
    "toml",
    "dockerfile",
    "plaintext",
]


class CodeAgentInput(StrictModel):
    spec: ProjectSpec
    stack: StackPlan


class GeneratedFile(StrictModel):
    path: str = Field(description='Relative POSIX path, e.g. "backend/main.py". No leading slash, no "..".')
    language: FileLanguage
    content: str
    purpose: str = Field(description="One line: what this file is for.")

    @field_validator("path")
    @classmethod
    def safe_relative_path(cls, value: str) -> str:
        value = value.replace("\\", "/")
        parts = value.split("/")
        if value.startswith("/") or ".." in parts or not value or ":" in parts[0]:
            raise ValueError("path must be a relative path inside the project")
        return value


class DependencyManifest(StrictModel):
    python: list[str] = Field(default_factory=list, description="Python packages the code imports.")
    node: list[str] = Field(default_factory=list, description="npm packages the code imports.")


class CodeBundle(StrictModel):
    """Output of the Code Agent: the full set of generated files."""

    files: list[GeneratedFile] = Field(min_length=1)
    entrypoints: list[str] = Field(default_factory=list, description="Paths of the files that start the app.")
    dependencies: DependencyManifest

    @field_validator("files")
    @classmethod
    def unique_paths(cls, files: list[GeneratedFile]) -> list[GeneratedFile]:
        paths = [f.path for f in files]
        duplicates = {p for p in paths if paths.count(p) > 1}
        if duplicates:
            raise ValueError(f"duplicate file paths: {sorted(duplicates)}")
        return files
