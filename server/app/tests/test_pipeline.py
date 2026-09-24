import io
import zipfile

import httpx
import yaml

from app.llm.base import LLMUnavailableError
from app.llm.factory import set_provider_override
from app.llm.fake_provider import FakeProvider
from app.schemas.agents import ProjectSpec
from app.tests.conftest import create_project, run_stage


async def test_full_pipeline_with_fake_agents(auth_client: httpx.AsyncClient) -> None:
    project = await create_project(auth_client)
    pid = project["id"]

    # Stage order is enforced.
    assert (await run_stage(auth_client, pid, "stack")).status_code == 409
    assert (await run_stage(auth_client, pid, "code")).status_code == 409

    # 1. Idea & Spec
    assert (await run_stage(auth_client, pid, "idea")).status_code == 202
    detail = (await auth_client.get(f"/api/projects/{pid}")).json()
    assert detail["specReady"] is True
    assert detail["spec"]["targetUsers"]
    assert detail["stage"] == "idea"

    # 2. Tech Stack
    await run_stage(auth_client, pid, "stack")
    detail = (await auth_client.get(f"/api/projects/{pid}")).json()
    assert detail["stage"] == "stack" and detail["status"] == "in-progress"
    assert detail["stackPlan"]["backendFramework"] == "fastapi"
    assert "FastAPI (Python)" in detail["stack"]

    # 3. Code
    await run_stage(auth_client, pid, "code")
    files = {f["path"]: f for f in (await auth_client.get(f"/api/projects/{pid}/files")).json()}
    assert "backend/main.py" in files and files["backend/main.py"]["source"] == "code"
    assert files["backend/main.py"]["content"].startswith("from fastapi import")

    # EVA (does not advance the stage)
    await run_stage(auth_client, pid, "eva")
    detail = (await auth_client.get(f"/api/projects/{pid}")).json()
    assert detail["stage"] == "code"
    assert [p["name"] for p in detail["eva"]["personas"]] == ["Alpha", "Bravo", "Charlie"]

    # 4. Export (zip)
    zipped = await auth_client.get(f"/api/projects/{pid}/export/zip")
    assert zipped.status_code == 200
    assert zipped.headers["content-disposition"] == 'attachment; filename="studysync.zip"'
    names = zipfile.ZipFile(io.BytesIO(zipped.content)).namelist()
    assert "studysync/backend/main.py" in names
    assert (await auth_client.get(f"/api/projects/{pid}")).json()["stage"] == "export"

    # 5. Deploy + learning summary
    await run_stage(auth_client, pid, "deploy")
    detail = (await auth_client.get(f"/api/projects/{pid}")).json()
    assert detail["stage"] == "deploy" and detail["status"] == "deployed"
    assert {t["id"] for t in detail["deployment"]["targets"]} == {"docker", "render", "actions"}
    stats = {s["label"]: s["value"] for s in detail["learning"]["overview"]["stats"]}
    assert stats["API routes"] == "2"
    assert int(stats["Files generated"]) >= 9

    files = {f["path"]: f["content"] for f in (await auth_client.get(f"/api/projects/{pid}/files")).json()}
    assert 'CMD ["uvicorn", "main:app"' in files["Dockerfile"]
    for path in ("docker-compose.yml", "render.yaml", ".github/workflows/deploy.yml"):
        assert yaml.safe_load(files[path]), path

    # Every agent run was logged, with tokens and timing.
    runs = (await auth_client.get(f"/api/projects/{pid}/runs")).json()
    assert {r["agent"] for r in runs} == {"idea", "stack", "code", "eva", "deploy", "summary"}
    assert all(r["status"] == "succeeded" for r in runs)
    llm_runs = [r for r in runs if r["provider"] == "fake"]
    assert all(
        r["inputTokens"] > 0 and r["outputTokens"] > 0 and r["durationMs"] is not None for r in llm_runs
    )
    assert next(r for r in runs if r["agent"] == "deploy")["provider"] == "rules"

    # Every consistency check was logged; the canned project passes them all.
    checks = (await auth_client.get(f"/api/projects/{pid}/checks")).json()
    names = {c["checkName"] for c in checks}
    assert {
        "spec_has_core_features",
        "stack_covers_layers",
        "files_parse",
        "python_lint",
        "python_dependencies_declared",
        "node_dependencies_declared",
        "code_matches_stack",
        "deployment_files_parse",
    } <= names
    assert all(c["passed"] for c in checks), [c for c in checks if not c["passed"]]

    # Chat messages from each stage.
    agents = [m["agentId"] for m in (await auth_client.get(f"/api/projects/{pid}/messages")).json()]
    assert agents[:1] == [None] and "deploy" in agents

    # Metrics aggregate the logs for the papers.
    metrics = (await auth_client.get("/api/metrics")).json()
    by_agent = {m["agent"]: m for m in metrics["agents"]}
    assert by_agent["code"]["runs"] == 1 and by_agent["code"]["successRate"] == 1.0
    assert all(c["passRate"] == 1.0 for c in metrics["checks"])


async def test_failed_agent_is_logged_and_reported(auth_client: httpx.AsyncClient) -> None:
    project = await create_project(auth_client)
    broken = FakeProvider()
    broken.queue(ProjectSpec, LLMUnavailableError("provider is down"))
    set_provider_override("idea", broken)

    assert (await run_stage(auth_client, project["id"], "idea")).status_code == 202
    detail = (await auth_client.get(f"/api/projects/{project['id']}")).json()
    assert detail["specReady"] is False

    [run] = (await auth_client.get(f"/api/projects/{project['id']}/runs")).json()
    assert run["status"] == "failed"
    assert "provider is down" in run["error"]
    assert run["retries"] == 0  # unavailability is not retried by the agent


async def test_chat_uses_selected_agent(auth_client: httpx.AsyncClient) -> None:
    project = await create_project(auth_client)
    response = await auth_client.post(
        f"/api/projects/{project['id']}/messages",
        json={"content": "Where is the list loaded?", "agentId": "code"},
    )
    assert response.status_code == 201
    question, reply = response.json()
    assert question["role"] == "user"
    assert reply["role"] == "agent" and reply["agentId"] == "code" and reply["content"]
    runs = (await auth_client.get(f"/api/projects/{project['id']}/runs")).json()
    assert runs[0]["agent"] == "chat"


async def test_semantic_search_finds_relevant_code(auth_client: httpx.AsyncClient) -> None:
    project = await create_project(auth_client)
    for stage in ("idea", "stack", "code"):
        await run_stage(auth_client, project["id"], stage)
    hits = (
        await auth_client.get(f"/api/projects/{project['id']}/search", params={"q": "join session capacity"})
    ).json()
    assert hits and hits[0]["filePath"] == "backend/main.py"
    assert hits[0]["startLine"] == 1 and 0 < hits[0]["score"] <= 1


async def test_saving_a_file_reindexes_search(auth_client: httpx.AsyncClient) -> None:
    project = await create_project(auth_client)
    base = f"/api/projects/{project['id']}"
    await auth_client.put(f"{base}/files/notes/zebra.md", json={"content": "zebra giraffe elephant"})
    hits = (await auth_client.get(f"{base}/search", params={"q": "giraffe"})).json()
    assert hits[0]["filePath"] == "notes/zebra.md"
