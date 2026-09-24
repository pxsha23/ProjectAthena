"""Request and response bodies for the REST API (camelCase JSON, matching the frontend types)."""

from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, EmailStr, Field

from app.schemas.base import StrictModel

StageName = Literal["idea", "stack", "code", "eva", "export", "deploy"]


class ApiModel(StrictModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- auth


class RegisterIn(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginIn(ApiModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class UserOut(ApiModel):
    id: str
    name: str
    email: str | None
    github_username: str | None = Field(default=None, validation_alias="github_login")
    has_github_token: bool = False


# ---------------------------------------------------------------- projects


class ProjectCreate(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    idea: str = Field(min_length=15, max_length=5000)


class ProjectUpdate(ApiModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    starred: bool | None = None


class ProjectOut(ApiModel):
    id: str
    name: str
    description: str
    idea: str
    stage: str
    status: str
    spec_ready: bool
    running_stage: str | None = None
    starred: bool
    stack_names: list[str] = Field(default_factory=list, serialization_alias="stack")
    created_at: datetime
    updated_at: datetime


class ProjectDetailOut(ProjectOut):
    spec: dict[str, Any] | None
    stack_plan: dict[str, Any] | None
    eva: dict[str, Any] | None
    deployment: dict[str, Any] | None
    learning: dict[str, Any] | None


class FileOut(ApiModel):
    path: str
    language: str
    content: str
    source: str
    updated_at: datetime


class FileWrite(ApiModel):
    content: str = Field(max_length=500_000)
    language: str | None = None


class MessageOut(ApiModel):
    id: str
    role: str
    agent_id: str | None = Field(default=None, validation_alias="agent")
    content: str
    created_at: datetime


class ChatIn(ApiModel):
    content: str = Field(min_length=1, max_length=4000)
    agent_id: Literal["idea", "stack", "code", "deploy", "eva"]


# ---------------------------------------------------------------- pipeline & metrics


class StageRunOut(ApiModel):
    project_id: str
    stage: StageName
    status: Literal["started"]


class AgentRunOut(ApiModel):
    id: str
    agent: str
    stage: str | None
    provider: str
    model: str | None
    status: str
    started_at: datetime
    duration_ms: int | None
    input_tokens: int
    output_tokens: int
    retries: int
    validation_errors: list[dict[str, Any]]
    error: str | None


class CheckOut(ApiModel):
    id: str
    stage: str
    check_name: str
    passed: bool
    severity: str
    message: str
    details: dict[str, Any]
    duration_ms: int
    created_at: datetime


class AgentMetrics(ApiModel):
    agent: str
    runs: int
    succeeded: int
    success_rate: float
    avg_duration_ms: float
    avg_input_tokens: float
    avg_output_tokens: float
    avg_retries: float
    first_try_rate: float


class CheckMetrics(ApiModel):
    check_name: str
    runs: int
    passed: int
    pass_rate: float


class MetricsOut(ApiModel):
    agents: list[AgentMetrics]
    checks: list[CheckMetrics]


# ---------------------------------------------------------------- export & search


class GithubExportIn(ApiModel):
    repo_name: str = Field(pattern=r"^[A-Za-z0-9._-]{1,100}$")
    private: bool = True


class GithubExportOut(ApiModel):
    repo_url: str
    full_name: str
    commit_sha: str


class SearchHitOut(ApiModel):
    file_path: str
    start_line: int
    end_line: int
    content: str
    score: float
