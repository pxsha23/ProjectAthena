from typing import Literal

from pydantic import Field

from app.schemas.base import StrictModel


class ChatTurn(StrictModel):
    role: Literal["user", "agent"]
    content: str


class ChatAgentInput(StrictModel):
    agent: Literal["idea", "stack", "code", "deploy", "eva"]
    question: str = Field(min_length=1)
    project_name: str
    stage: str
    context: str = Field(description="Relevant project state (spec, stack, file list) as JSON.")
    history: list[ChatTurn] = Field(default_factory=list)


class ChatAgentOutput(StrictModel):
    reply: str = Field(description="The answer to the user, in plain words.")
    suggested_actions: list[str] = Field(
        default_factory=list, description="Optional follow-up actions the user could take."
    )
