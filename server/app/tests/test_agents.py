import pytest

from app.agents.base import AgentRunFailed
from app.agents.idea import IdeaAgent
from app.agents.summary import SummaryAgent
from app.core.config import get_settings
from app.llm.base import LLMRefusalError
from app.llm.fake_data import SPEC, STACK, SUMMARY
from app.llm.fake_provider import FakeProvider
from app.schemas.agents import IdeaAgentInput, LearningSummary, ProjectSpec, StackPlan, SummaryAgentInput

INPUT = IdeaAgentInput(idea="A marketplace for students to rent out textbooks.", project_name="Books")


async def test_valid_output_first_try(db) -> None:
    outcome = await IdeaAgent(FakeProvider()).run(db, INPUT, project_id=None, stage="idea")
    assert isinstance(outcome.output, ProjectSpec)
    run = outcome.run
    assert run.status == "succeeded" and run.retries == 0 and run.validation_errors == []
    assert run.output_json["targetUsers"] == SPEC["targetUsers"]
    assert run.input_json == {"idea": INPUT.idea, "projectName": "Books"}


async def test_invalid_output_is_retried_with_feedback(db) -> None:
    provider = FakeProvider()
    provider.queue(ProjectSpec, {"summary": "missing fields"}, SPEC)
    outcome = await IdeaAgent(provider).run(db, INPUT, project_id=None)

    assert outcome.run.status == "succeeded"
    assert outcome.run.retries == 1
    assert len(outcome.run.validation_errors) == 1
    assert "targetUsers" in outcome.run.validation_errors[0]["error"]
    # The second prompt tells the model what was wrong.
    assert "previous answer was rejected" in provider.calls[1]["prompt"]


async def test_unknown_fields_are_rejected(db) -> None:
    provider = FakeProvider()
    provider.queue(ProjectSpec, {**SPEC, "extraField": "not allowed"}, SPEC)
    outcome = await IdeaAgent(provider).run(db, INPUT, project_id=None)
    assert outcome.run.retries == 1
    assert "extra" in outcome.run.validation_errors[0]["error"].lower()


async def test_semantic_check_triggers_retry(db) -> None:
    no_core = {**SPEC, "sections": [{"title": "Ideas", "items": ["something"]}]}
    provider = FakeProvider()
    provider.queue(ProjectSpec, no_core, SPEC)
    outcome = await IdeaAgent(provider).run(db, INPUT, project_id=None)
    assert outcome.run.retries == 1
    assert "Core features" in outcome.run.validation_errors[0]["error"]


async def test_gives_up_after_max_retries(db) -> None:
    attempts = get_settings().agent_max_retries + 1
    provider = FakeProvider()
    provider.queue(ProjectSpec, *[{"summary": "bad"}] * attempts)
    with pytest.raises(AgentRunFailed) as info:
        await IdeaAgent(provider).run(db, INPUT, project_id=None)
    assert len(provider.calls) == attempts

    from app.models import AgentRun

    run = await db.get(AgentRun, info.value.run_id)
    assert run.status == "failed"
    assert run.retries == attempts - 1
    assert len(run.validation_errors) == attempts


async def test_refusal_is_not_retried(db) -> None:
    provider = FakeProvider()
    provider.queue(ProjectSpec, LLMRefusalError("declined"))
    with pytest.raises(AgentRunFailed):
        await IdeaAgent(provider).run(db, INPUT, project_id=None)
    assert len(provider.calls) == 1


async def test_summary_may_only_cite_real_files(db) -> None:
    data = SummaryAgentInput(
        project_name="StudySync",
        spec=ProjectSpec.model_validate(SPEC),
        stack=StackPlan.model_validate(STACK),
        file_paths=["backend/main.py", "backend/models.py", "frontend/src/App.tsx"],
        deployment_targets=[],
        eva=None,
    )
    invented = {
        **SUMMARY,
        "topics": [{**SUMMARY["topics"][0], "files": ["backend/imaginary.py"]}] + SUMMARY["topics"][1:],
    }
    provider = FakeProvider()
    provider.queue(LearningSummary, invented, SUMMARY)
    outcome = await SummaryAgent(provider).run(db, data, project_id=None)
    assert outcome.run.retries == 1
    assert "backend/imaginary.py" in outcome.run.validation_errors[0]["error"]
