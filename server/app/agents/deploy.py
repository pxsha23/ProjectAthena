"""Deployment Agent: rule-based stack detection + Jinja2 templates. No LLM involved."""

import json
import re
import time
from pathlib import PurePosixPath

from jinja2 import Environment, PackageLoader, StrictUndefined
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import utcnow
from app.models import AgentRun
from app.schemas.agents import (
    DeployAgentInput,
    DeploymentBundle,
    DeploymentTarget,
    GeneratedFile,
    StackDetection,
)

_env = Environment(
    loader=PackageLoader("app", "templates/deploy"),
    undefined=StrictUndefined,
    keep_trailing_newline=True,
    trim_blocks=True,
    lstrip_blocks=True,
)

PY_FRAMEWORKS = {"fastapi": "fastapi", "flask": "flask", "django": "django"}
NODE_FRONTENDS = {"next": "nextjs", "react": "react", "vue": "vue", "svelte": "svelte"}
DB_MARKERS = {
    "postgresql": ("psycopg", "asyncpg", "psycopg2", "pg", "postgres"),
    "mysql": ("mysqlclient", "pymysql", "mysql2", "mysql"),
    "mongodb": ("pymongo", "motor", "mongoose", "mongodb"),
    "sqlite": ("aiosqlite", "sqlite3", "better-sqlite3"),
}


def _parent(path: str) -> str:
    parent = str(PurePosixPath(path).parent)
    return "" if parent == "." else parent


def _requirement_names(text: str) -> set[str]:
    names = set()
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0].strip().lower()
        if name:
            names.add(name)
    return names


def detect_stack(data: DeployAgentInput) -> StackDetection:
    files = {f.path: f.content for f in data.files}
    evidence: list[str] = []
    backend_language, backend_framework, backend_dir, entry = "none", None, None, None
    frontend_framework, frontend_dir = None, None
    deps: set[str] = set()

    # Python backend
    req_path = next((p for p in files if p.endswith("requirements.txt")), None)
    if req_path:
        req = _requirement_names(files[req_path])
        deps |= req
        backend_language, backend_dir = "python", _parent(req_path)
        evidence.append(f"{req_path} found: Python backend in '{backend_dir or '.'}'")
        for package, framework in PY_FRAMEWORKS.items():
            if package in req:
                backend_framework = framework
                evidence.append(f"{req_path} lists {package}")
                break
        for path, content in files.items():
            if not path.endswith(".py") or _parent(path) != backend_dir:
                continue
            match = re.search(r"^(\w+)\s*=\s*(FastAPI|Flask)\(", content, re.MULTILINE)
            if match:
                entry = f"{PurePosixPath(path).stem}:{match.group(1)}"
                evidence.append(f"{path} creates the app object '{match.group(1)}'")
                break

    # Node projects (frontend and/or backend)
    for path, content in files.items():
        if not path.endswith("package.json"):
            continue
        try:
            manifest = json.loads(content)
        except json.JSONDecodeError:
            evidence.append(f"{path} is not valid JSON; skipped")
            continue
        names = set(manifest.get("dependencies", {})) | set(manifest.get("devDependencies", {}))
        deps |= names
        found = next((fw for pkg, fw in NODE_FRONTENDS.items() if pkg in names), None)
        if found and frontend_framework is None:
            frontend_framework, frontend_dir = found, _parent(path)
            evidence.append(f"{path} depends on {found}: frontend in '{frontend_dir or '.'}'")
        if "express" in names and backend_language == "none":
            backend_language, backend_framework, backend_dir = "node", "express", _parent(path)
            evidence.append(f"{path} depends on express: Node backend")

    database = "none"
    for db, markers in DB_MARKERS.items():
        hit = next((m for m in markers if m in deps), None)
        if hit:
            database = db
            evidence.append(f"dependency '{hit}' indicates {db}")
            break
    if database == "none" and data.stack and data.stack.database != "none":
        database = data.stack.database
        evidence.append(f"stack plan lists {database} (no driver found in manifests yet)")

    return StackDetection(
        backend_language=backend_language,  # type: ignore[arg-type]
        backend_framework=backend_framework,
        backend_dir=backend_dir,
        python_entry_module=entry,
        frontend_framework=frontend_framework,
        frontend_dir=frontend_dir,
        database=database,  # type: ignore[arg-type]
        evidence=evidence,
    )


def render_deployment(data: DeployAgentInput, detection: StackDetection) -> DeploymentBundle:
    ctx = {"d": detection, "join": lambda *parts: "/".join(p for p in parts if p)}
    files: list[GeneratedFile] = []
    targets: list[DeploymentTarget] = []

    def add(path: str, template: str, language: str, purpose: str) -> None:
        files.append(
            GeneratedFile(
                path=path,
                language=language,
                content=_env.get_template(template).render(**ctx),
                purpose=purpose,
            )
        )

    if detection.backend_language == "python":
        add("Dockerfile", "Dockerfile.python.j2", "dockerfile", "Container image for the Python backend.")
    elif detection.backend_language == "node":
        add("Dockerfile", "Dockerfile.node.j2", "dockerfile", "Container image for the Node backend.")

    has_backend = detection.backend_language != "none"
    if has_backend:
        add("docker-compose.yml", "docker-compose.yml.j2", "yaml", "Run the app and database locally.")
        add(".env.example", "env.example.j2", "plaintext", "Environment variables the app needs.")
        targets.append(
            DeploymentTarget(
                id="docker",
                name="Docker",
                description="Run the backend"
                + (f" and {detection.database}" if detection.database != "none" else "")
                + " locally or on any container host.",
                files=["Dockerfile", "docker-compose.yml", ".env.example"],
            )
        )

    if has_backend or detection.frontend_framework:
        add("render.yaml", "render.yaml.j2", "yaml", "Render Blueprint: services defined as code.")
        targets.append(
            DeploymentTarget(
                id="render",
                name="Render",
                description="Free-tier hosting defined as code in a Render Blueprint.",
                files=["render.yaml"],
            )
        )
        add(".github/workflows/deploy.yml", "github-actions.yml.j2", "yaml", "Checks, then deploys on push.")
        targets.append(
            DeploymentTarget(
                id="actions",
                name="GitHub Actions",
                description="Checks every push to main, then triggers a deploy.",
                files=[".github/workflows/deploy.yml"],
            )
        )

    return DeploymentBundle(detection=detection, targets=targets, files=files)


class DeployAgent:
    name = "deploy"

    async def run(
        self, session: AsyncSession, data: DeployAgentInput, *, project_id: str | None, stage: str = "deploy"
    ) -> tuple[DeploymentBundle, AgentRun]:
        started = time.perf_counter()
        run = AgentRun(
            project_id=project_id,
            agent="deploy",
            stage=stage,
            provider="rules",
            model=None,
            status="running",
            input_json={
                "stack": data.stack.to_json_dict() if data.stack else None,
                "files": [f.path for f in data.files],
            },
            validation_errors=[],
        )
        session.add(run)
        try:
            bundle = render_deployment(data, detect_stack(data))
            run.status = "succeeded"
            run.output_json = bundle.to_json_dict()
            return bundle, run
        except Exception as exc:
            run.status = "failed"
            run.error = str(exc)[:4000]
            raise
        finally:
            run.finished_at = utcnow()
            run.duration_ms = int((time.perf_counter() - started) * 1000)
            await session.commit()
