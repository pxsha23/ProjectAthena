"""Workspace chat: retrieval context, proposals the student applies or dismisses, stack consultation."""

import json

import httpx

from app.llm.base import LLMOutputError
from app.llm.factory import set_provider_override
from app.llm.fake_data import SPEC, STACK
from app.llm.fake_provider import FakeProvider
from app.schemas.agents import ChatAgentOutput, StackPlan
from app.tests.conftest import _client, create_project, register, run_stage


def chat_provider() -> FakeProvider:
    provider = FakeProvider()
    set_provider_override("chat", provider)
    return provider


async def send(client: httpx.AsyncClient, pid: str, agent: str, content: str) -> httpx.Response:
    return await client.post(f"/api/projects/{pid}/messages", json={"content": content, "agentId": agent})


def last_input(provider: FakeProvider) -> dict:
    prompt = provider.calls[-1]["prompt"]
    return json.loads(prompt[prompt.index("Input (JSON):") + len("Input (JSON):") :])


async def test_code_agent_gets_named_file_and_search_results(auth_client: httpx.AsyncClient) -> None:
    pid = (await create_project(auth_client))["id"]
    for stage in ("idea", "stack", "code"):
        await run_stage(auth_client, pid, stage)
    provider = chat_provider()

    response = await send(auth_client, pid, "code", "How does join_session work in main.py?")
    assert response.status_code == 201, response.text
    data = last_input(provider)
    paths = [snippet["path"] for snippet in data["code"]]
    assert paths[0] == "backend/main.py" and data["code"][0]["startLine"] == 1
    assert "def join_session" in data["code"][0]["content"]
    assert len(paths) == len(set(paths))
    context = data["context"]
    assert "backend/main.py" in context["files"] and "failedChecks" in context
    assert "Code Agent" in provider.calls[-1]["prompt"]

    # The student's message records which agent it was for; suggestions come back to the client.
    user, agent = response.json()
    assert user["agentId"] == "code" and agent["agentId"] == "code"


async def test_idea_agent_proposes_and_student_applies(auth_client: httpx.AsyncClient) -> None:
    pid = (await create_project(auth_client))["id"]
    await run_stage(auth_client, pid, "idea")
    provider = chat_provider()
    revised = {**SPEC, "summary": "Students rent textbooks from each other for a semester."}
    provider.queue(
        ChatAgentOutput,
        {
            "reply": "Added a return reminder, as you asked.",
            "suggestedActions": ["What else is risky?"],
            "specUpdate": revised,
            "changes": ["Added return reminders"],
        },
    )
    [_, answer] = (await send(auth_client, pid, "idea", "Add reminders before the return date")).json()
    assert answer["proposalStatus"] == "pending" and answer["proposal"]["kind"] == "spec"
    assert answer["proposal"]["changes"] == ["Added return reminders"]
    assert answer["suggestions"] == ["What else is risky?"]
    # The Idea Agent sees only the idea and spec: no code search for brainstorming.
    assert last_input(provider)["code"] == []

    before = (await auth_client.get(f"/api/projects/{pid}")).json()
    assert before["spec"]["summary"] != revised["summary"]

    applied = await auth_client.post(f"/api/projects/{pid}/messages/{answer['id']}/apply")
    assert applied.status_code == 200 and applied.json()["proposalStatus"] == "applied"
    after = (await auth_client.get(f"/api/projects/{pid}")).json()
    assert after["spec"]["summary"] == revised["summary"]
    checks = (await auth_client.get(f"/api/projects/{pid}/checks")).json()
    assert sum(c["checkName"] == "spec_has_core_features" for c in checks) == 2

    again = await auth_client.post(f"/api/projects/{pid}/messages/{answer['id']}/apply")
    assert again.status_code == 409


async def test_stack_consultation_shapes_the_recommendation(auth_client: httpx.AsyncClient) -> None:
    pid = (await create_project(auth_client))["id"]
    await run_stage(auth_client, pid, "idea")
    chat_provider()
    stack_provider = FakeProvider()
    set_provider_override("stack", stack_provider)

    await send(auth_client, pid, "stack", "I know Python well and want to learn React")
    await run_stage(auth_client, pid, "stack")
    stack_input = json.loads(
        stack_provider.calls[-1]["prompt"][stack_provider.calls[-1]["prompt"].index("{") :]
    )
    assert "I know Python well and want to learn React" in stack_input["studentNotes"]


async def test_stack_proposal_advances_to_stack_and_warns_about_old_code(
    auth_client: httpx.AsyncClient,
) -> None:
    pid = (await create_project(auth_client))["id"]
    for stage in ("idea", "stack", "code"):
        await run_stage(auth_client, pid, stage)
    provider = chat_provider()
    flask = {**STACK, "backendFramework": "flask"}
    flask["choices"] = [
        {**c, "name": "Flask (Python)"} if c["layer"] == "backend" else c for c in STACK["choices"]
    ]
    provider.queue(
        ChatAgentOutput,
        {"reply": "Flask it is.", "stackUpdate": flask, "changes": ["Backend: FastAPI to Flask"]},
    )
    [_, answer] = (await send(auth_client, pid, "stack", "I would rather use Flask")).json()
    assert (await auth_client.post(f"/api/projects/{pid}/messages/{answer['id']}/apply")).status_code == 200

    project = (await auth_client.get(f"/api/projects/{pid}")).json()
    assert StackPlan.model_validate(project["stackPlan"]).backend_framework == "flask"
    assert project["stage"] == "code"  # applying never moves a project backwards
    messages = (await auth_client.get(f"/api/projects/{pid}/messages")).json()
    assert "run the Code stage again" in messages[-1]["content"]


async def test_wrong_agent_update_is_retried(auth_client: httpx.AsyncClient) -> None:
    pid = (await create_project(auth_client))["id"]
    await run_stage(auth_client, pid, "idea")
    provider = chat_provider()
    provider.queue(
        ChatAgentOutput,
        {"reply": "x", "specUpdate": SPEC, "changes": ["y"]},  # the Code Agent may not change the spec
        {"reply": "Here is how it works."},
    )
    [_, answer] = (await send(auth_client, pid, "code", "Explain the models")).json()
    assert answer["content"] == "Here is how it works." and answer["proposal"] is None
    runs = (await auth_client.get(f"/api/projects/{pid}/runs")).json()
    chat_run = next(r for r in runs if r["agent"] == "chat")
    assert chat_run["retries"] == 1 and "Idea Agent" in chat_run["validationErrors"][0]["error"]


async def test_dismiss_and_privacy(auth_client: httpx.AsyncClient) -> None:
    pid = (await create_project(auth_client))["id"]
    await run_stage(auth_client, pid, "idea")
    provider = chat_provider()
    provider.queue(ChatAgentOutput, {"reply": "Smaller scope?", "specUpdate": SPEC, "changes": ["Cut chat"]})
    [_, answer] = (await send(auth_client, pid, "idea", "Make it smaller")).json()

    async with _client() as other:
        await register(other, "Someone Else")
        forbidden = await other.post(f"/api/projects/{pid}/messages/{answer['id']}/dismiss")
        assert forbidden.status_code == 404

    dismissed = await auth_client.post(f"/api/projects/{pid}/messages/{answer['id']}/dismiss")
    assert dismissed.json()["proposalStatus"] == "dismissed"
    assert (await auth_client.post(f"/api/projects/{pid}/messages/{answer['id']}/apply")).status_code == 409


async def test_agent_failure_keeps_the_question(auth_client: httpx.AsyncClient) -> None:
    pid = (await create_project(auth_client))["id"]
    provider = chat_provider()
    provider.queue(ChatAgentOutput, *[LLMOutputError("bad")] * 3)
    response = await send(auth_client, pid, "idea", "Hello?")
    assert response.status_code == 502
    messages = (await auth_client.get(f"/api/projects/{pid}/messages")).json()
    assert messages[-1]["content"] == "Hello?"
