import json

import httpx
import yaml

from app.agents.deploy import detect_stack, render_deployment
from app.llm.fake_data import CODE, STACK
from app.models import ProjectFile
from app.schemas.agents import CodeBundle, DeployAgentInput, GeneratedFile, StackPlan
from app.services.github import push_to_new_repo
from app.tests.conftest import create_project


def test_detects_python_backend_and_react_frontend() -> None:
    data = DeployAgentInput(
        stack=StackPlan.model_validate(STACK), files=CodeBundle.model_validate(CODE).files
    )
    d = detect_stack(data)
    assert (d.backend_language, d.backend_framework, d.backend_dir) == ("python", "fastapi", "backend")
    assert d.python_entry_module == "main:app"
    assert (d.frontend_framework, d.frontend_dir) == ("react", "frontend")
    assert d.database == "postgresql"  # from the stack plan: no driver in requirements yet
    assert any("stack plan" in e for e in d.evidence)

    bundle = render_deployment(data, d)
    files = {f.path: f.content for f in bundle.files}
    assert "COPY backend/requirements.txt ." in files["Dockerfile"]
    compose = yaml.safe_load(files["docker-compose.yml"])
    assert set(compose["services"]) == {"api", "db"}
    render = yaml.safe_load(files["render.yaml"])
    assert [s["name"] for s in render["services"]] == ["api", "frontend"]
    assert render["services"][1]["rootDir"] == "frontend"
    workflow = yaml.safe_load(files[".github/workflows/deploy.yml"])
    assert workflow["jobs"]["deploy"]["needs"] == "check"
    assert "${{ secrets.RENDER_DEPLOY_HOOK }}" in files[".github/workflows/deploy.yml"]


def test_detects_node_express_backend() -> None:
    manifest = json.dumps({"dependencies": {"express": "^5.0.0", "mongoose": "^8.0.0"}})
    data = DeployAgentInput(
        stack=None,
        files=[
            GeneratedFile(path="package.json", language="json", content=manifest, purpose=""),
            GeneratedFile(
                path="server.js",
                language="javascript",
                content="const express = require('express')",
                purpose="",
            ),
        ],
    )
    d = detect_stack(data)
    assert (d.backend_language, d.backend_framework, d.backend_dir, d.database) == (
        "node",
        "express",
        "",
        "mongodb",
    )
    files = {f.path: f.content for f in render_deployment(data, d).files}
    assert "FROM node:22-alpine" in files["Dockerfile"]
    assert "mongo:8" in files["docker-compose.yml"]


async def test_push_to_github_creates_repo_and_single_commit() -> None:
    calls: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content) if request.content else {}
        calls.append((request.method, request.url.path, body))
        assert request.headers["authorization"] == "Bearer tok"
        path = request.url.path
        if path == "/user/repos":
            return httpx.Response(
                201,
                json={
                    "full_name": "me/app",
                    "html_url": "https://github.com/me/app",
                    "default_branch": "main",
                },
            )
        if path.endswith("/git/ref/heads/main"):
            return httpx.Response(200, json={"object": {"sha": "parent"}})
        if path.endswith("/git/trees"):
            return httpx.Response(201, json={"sha": "tree"})
        if path.endswith("/git/commits"):
            return httpx.Response(201, json={"sha": "commit"})
        if path.endswith("/git/refs/heads/main"):
            return httpx.Response(200, json={})
        return httpx.Response(404)

    files = [ProjectFile(path="a.py", content="x = 1\n"), ProjectFile(path="b/c.md", content="# c\n")]
    result = await push_to_new_repo("tok", "app", files, transport=httpx.MockTransport(handler))

    assert result.repo_url == "https://github.com/me/app" and result.commit_sha == "commit"
    tree = next(body for method, path, body in calls if path.endswith("/git/trees"))
    assert [entry["path"] for entry in tree["tree"]] == ["a.py", "b/c.md"]
    commit = next(body for method, path, body in calls if path.endswith("/git/commits"))
    assert commit["parents"] == ["parent"] and commit["tree"] == "tree"


async def test_github_export_needs_a_connected_account(auth_client: httpx.AsyncClient) -> None:
    project = await create_project(auth_client)
    response = await auth_client.post(
        f"/api/projects/{project['id']}/export/github", json={"repoName": "app"}
    )
    assert response.status_code == 409
    assert "GitHub" in response.json()["detail"]


async def test_zip_export_needs_files(auth_client: httpx.AsyncClient) -> None:
    project = await create_project(auth_client)
    assert (await auth_client.get(f"/api/projects/{project['id']}/export/zip")).status_code == 409
