from typing import Any, Literal

from pydantic import Field

from app.schemas.agents.idea import ProjectSpec
from app.schemas.agents.stack import StackPlan
from app.schemas.base import StrictModel

ChatAgentId = Literal["idea", "stack", "code", "deploy", "eva"]


class ChatTurn(StrictModel):
    role: Literal["user", "agent"]
    content: str


class CodeSnippet(StrictModel):
    path: str
    start_line: int
    end_line: int
    content: str


class ChatAgentInput(StrictModel):
    agent: ChatAgentId
    question: str = Field(min_length=1)
    project_name: str
    stage: str
    context: dict[str, Any] = Field(description="Relevant project state: spec, stack, files, checks, EVA.")
    code: list[CodeSnippet] = Field(
        default_factory=list, description="The parts of the project's code most relevant to the question."
    )
    history: list[ChatTurn] = Field(default_factory=list)


class ChatAgentOutput(StrictModel):
    reply: str = Field(
        description="The answer to the student, in plain words. Markdown lists and code are fine."
    )
    suggested_actions: list[str] = Field(
        default_factory=list,
        description="Up to 3 short follow-up messages the student could send next, written as the student.",
    )
    spec_update: ProjectSpec | None = Field(
        default=None,
        description="Idea Agent only: the complete revised spec, when the student agreed to change it.",
    )
    stack_update: StackPlan | None = Field(
        default=None,
        description="Tech Stack Agent only: the complete stack plan, when it is recommended or the student "
        "decided on a change.",
    )
    changes: list[str] = Field(
        default_factory=list,
        description="What the update changes, one short line each. Empty with no update.",
    )
