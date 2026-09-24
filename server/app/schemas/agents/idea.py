from pydantic import Field

from app.schemas.base import StrictModel


class IdeaAgentInput(StrictModel):
    idea: str = Field(min_length=10, description="The app idea as the user wrote it.")
    project_name: str


class SpecSection(StrictModel):
    title: str = Field(description='Section heading, e.g. "Core features" or "Out of scope (v1)".')
    items: list[str] = Field(min_length=1, description="One requirement or feature per item.")


class ProjectSpec(StrictModel):
    """Output of the Idea Agent: the written spec."""

    summary: str = Field(description="Two or three sentences describing the app and who it helps.")
    target_users: list[str] = Field(min_length=1)
    sections: list[SpecSection] = Field(
        min_length=1, description='Must include a section titled "Core features".'
    )
    open_questions: list[str] = Field(
        default_factory=list, description="Assumptions the user should confirm."
    )
