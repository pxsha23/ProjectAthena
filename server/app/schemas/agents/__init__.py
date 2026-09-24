"""Strict input/output schemas for every agent. Agents never exchange free text."""

from app.schemas.agents.chat import ChatAgentInput, ChatAgentOutput
from app.schemas.agents.code import CodeAgentInput, CodeBundle, DependencyManifest, GeneratedFile
from app.schemas.agents.deploy import DeployAgentInput, DeploymentBundle, DeploymentTarget, StackDetection
from app.schemas.agents.eva import EvaAgentInput, EvaFinding, EvaPersona, EvaReport
from app.schemas.agents.idea import IdeaAgentInput, ProjectSpec, SpecSection
from app.schemas.agents.stack import StackAgentInput, StackChoice, StackPlan
from app.schemas.agents.summary import (
    LearningOverview,
    LearningStat,
    LearningSummary,
    LearningTerm,
    LearningTopic,
    SummaryAgentInput,
)

__all__ = [
    "ChatAgentInput",
    "ChatAgentOutput",
    "CodeAgentInput",
    "CodeBundle",
    "DependencyManifest",
    "DeployAgentInput",
    "DeploymentBundle",
    "DeploymentTarget",
    "EvaAgentInput",
    "EvaFinding",
    "EvaPersona",
    "EvaReport",
    "GeneratedFile",
    "IdeaAgentInput",
    "LearningOverview",
    "LearningStat",
    "LearningSummary",
    "LearningTerm",
    "LearningTopic",
    "ProjectSpec",
    "SpecSection",
    "StackAgentInput",
    "StackChoice",
    "StackDetection",
    "StackPlan",
    "SummaryAgentInput",
]
