from pydantic import Field

from app.schemas.agents.deploy import DeploymentTarget
from app.schemas.agents.eva import EvaReport
from app.schemas.agents.idea import ProjectSpec
from app.schemas.agents.stack import StackPlan
from app.schemas.base import StrictModel


class SummaryAgentInput(StrictModel):
    project_name: str
    spec: ProjectSpec
    stack: StackPlan
    file_paths: list[str]
    deployment_targets: list[DeploymentTarget]
    eva: EvaReport | None


class LearningTerm(StrictModel):
    term: str
    meaning: str


class LearningTopic(StrictModel):
    title: str
    summary: list[str] = Field(min_length=1, description="One to three paragraphs in plain words.")
    concepts: list[str] = Field(min_length=1)
    how_it_works: list[str] = Field(
        min_length=2, description="Steps explaining how this works in THIS project."
    )
    files: list[str] = Field(description="Paths from file_paths that illustrate the topic.")
    key_terms: list[LearningTerm] = Field(min_length=1)
    try_it: str = Field(description="A small exercise the student can do in the editor.")


class LearningStat(StrictModel):
    label: str
    value: str


class LearningOverview(StrictModel):
    summary: list[str] = Field(min_length=2, description="Two or three paragraphs: what was built and how.")
    stats: list[LearningStat] = Field(default_factory=list)
    next_steps: list[str] = Field(min_length=3)


class LearningSummary(StrictModel):
    """Output of the Summary Agent: the long, detailed learning summary."""

    overview: LearningOverview
    topics: list[LearningTopic] = Field(min_length=4, max_length=10)
