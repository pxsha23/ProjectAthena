"""Naive free-text pipeline: the Paper 1 baseline.

Agents hand plain Markdown to each other. There is no schema, no validation and no retry.
The role instructions match the strict agents so that only the handoff format differs.
Everything is logged to agent_runs (mode="naive") and consistency_checks, like the strict pipeline.
"""

import re
import time
from dataclasses import dataclass, field
from pathlib import PurePosixPath

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.base import AgentRunFailed
from app.checker import checks
from app.checker.checks import CheckResult, timed
from app.checker.runner import run_checks
from app.core.db import utcnow
from app.llm.base import LLMError, LLMProvider
from app.llm.factory import get_provider
from app.models import AgentRun, Project, ProjectFile
from app.schemas.agents import GeneratedFile, StackChoice, StackPlan

NAIVE_RULES = (
    "You are one agent in Athena, a platform that takes a student's app idea from spec to deployed code. "
    "Write for a university student: clear, concrete and friendly. Never use emoji. Answer in Markdown."
)

INSTRUCTIONS = {
    "idea": (
        "You are the Idea Agent. Turn the user's app idea into a clear, realistic spec for a first version "
        "that a student can build. Write a short summary, the target users, a 'Core features' section with "
        "3 to 7 concrete, testable features, non-functional requirements, what is out of scope for v1, and "
        "open questions. Keep the scope small enough for a final year project."
    ),
    "stack": (
        "You are the Tech Stack Agent. Choose a stack that fits the spec and that a student can learn and "
        "deploy for free: frontend, backend, database, auth and hosting as needed, each with a one-sentence "
        "reason tied to the spec and one or two alternatives. Prefer mainstream, well documented tools."
    ),
    "code": (
        "You are the Code Agent. Generate a small, working first version of the app described by the spec, "
        "using exactly the chosen stack. Put the backend under backend/ and the frontend under "
        "frontend/ when both exist. Include backend/requirements.txt for Python and "
        "frontend/package.json for Node, listing every third-party import. Include a README.md. "
        "Do not include deployment files.\n"
        "Write every file as a line 'FILE: <relative path>' followed by a fenced code block with its content."
    ),
}

KIND_FOR_AGENT = {"idea": "spec", "stack": "stack", "code": "code"}

EXTENSION_LANGUAGE = {
    ".py": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".json": "json",
    ".md": "markdown",
    ".css": "css",
    ".html": "html",
    ".yml": "yaml",
    ".yaml": "yaml",
    ".toml": "toml",
}


# ---------------------------------------------------------------- parsing the free text

# "FILE: path" (optionally as a heading, bold or in backticks) followed by a fenced block.
_FILE_HEADER = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]*)?(?:\*\*)?(?:FILE|File|file)(?:\*\*)?[ \t]*[:\-](?:\*\*)?"
    r"[ \t]*`?\*{0,2}([^\s`*]+)\*{0,2}`?[ \t]*$",
    re.MULTILINE,
)
# Alternatives models often use: "```python backend/main.py", or a line that is just "`path`" / "**path**".
_FENCE_WITH_PATH = re.compile(r"^```[\w+-]*[ \t]+(?:title=)?\"?([\w./-]+\.\w+)\"?[ \t]*$", re.MULTILINE)
_BARE_PATH_LINE = re.compile(
    r"^[ \t]*(?:#{1,6}[ \t]*)?[`*]{1,2}([\w./-]+\.\w+|Dockerfile)[`*]{1,2}:?[ \t]*$", re.MULTILINE
)
_FENCE_BODY = re.compile(r"```[^\n]*\n(.*?)^```", re.MULTILINE | re.DOTALL)


def _language_for(path: str) -> str:
    if PurePosixPath(path).name.lower() == "dockerfile":
        return "dockerfile"
    return EXTENSION_LANGUAGE.get(PurePosixPath(path).suffix.lower(), "plaintext")


@dataclass
class ParsedFiles:
    files: list[GeneratedFile] = field(default_factory=list)
    rejected_paths: list[str] = field(default_factory=list)


def parse_files(text: str) -> ParsedFiles:
    """Extracts files from free text.

    Lenient on purpose: the baseline should not fail on trivial formatting differences.
    Unsafe paths ("../x", "/etc/x") are rejected by GeneratedFile and reported, never written.
    """
    result = ParsedFiles()
    seen: set[str] = set()

    def add(path: str, content: str) -> None:
        path = path.strip().replace("\\", "/")
        if path.startswith("./"):
            path = path[2:]
        if path in seen:
            return
        try:
            result.files.append(
                GeneratedFile(
                    path=path,
                    language=_language_for(path),  # type: ignore[arg-type]
                    content=content,
                    purpose="",
                )
            )
            seen.add(path)
        except ValueError:
            result.rejected_paths.append(path)

    for pattern in (_FILE_HEADER, _BARE_PATH_LINE):
        for match in pattern.finditer(text):
            body = _FENCE_BODY.search(text, match.end())
            # The code block must start right after the header (only blank lines in between).
            if body and not text[match.end() : body.start()].strip():
                add(match.group(1), body.group(1))

    for match in _FENCE_WITH_PATH.finditer(text):
        end = text.find("\n```", match.end())
        if end != -1:
            add(match.group(1), text[match.end() + 1 : end + 1])
    return result


FRONTENDS = {"next.js": "nextjs", "nextjs": "nextjs", "react": "react", "vue": "vue", "svelte": "svelte"}
BACKENDS = {"fastapi": "fastapi", "flask": "flask", "django": "django", "express": "express"}
DATABASES = {"postgres": "postgresql", "mysql": "mysql", "sqlite": "sqlite", "mongo": "mongodb"}


def infer_stack(text: str) -> StackPlan:
    """Best-effort reading of a free-text stack description (the naive handoff has no structured stack)."""
    low = text.lower()

    def first(table: dict[str, str]) -> str:
        hits = [(low.find(k), v) for k, v in table.items() if k in low]
        return min(hits)[1] if hits else "none"

    frontend, backend, database = first(FRONTENDS), first(BACKENDS), first(DATABASES)
    language = {"fastapi": "python", "flask": "python", "django": "python", "express": "javascript"}.get(
        backend, "none"
    )
    choices = [
        StackChoice(
            layer=layer, name=name, reason="Inferred from the free-text stack answer.", alternatives=[]
        )
        for layer, name in (("frontend", frontend), ("backend", backend), ("database", database))
        if name != "none"
    ] or [
        StackChoice(
            layer="other", name="unknown", reason="No known technology found in the text.", alternatives=[]
        )
    ]
    return StackPlan(
        choices=choices,
        backend_language=language,  # type: ignore[arg-type]
        frontend_framework=frontend,  # type: ignore[arg-type]
        backend_framework=backend,  # type: ignore[arg-type]
        database=database,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------- text versions of the spec checks


@timed
def check_spec_text(text: str) -> list[CheckResult]:
    """The same two spec checks as the strict mode, applied to Markdown with simple heuristics."""
    low = text.lower()
    core = re.search(r"core features[^\n]*\n((?:[ \t]*(?:[-*]|\d+\.)[^\n]*\n?)+)", low)
    count = len(re.findall(r"^[ \t]*(?:[-*]|\d+\.)", core.group(1), re.MULTILINE)) if core else 0
    has_users = bool(re.search(r"target users|users?:|who (?:it|this) is for|audience", low))
    return [
        CheckResult(
            "spec_has_core_features",
            count >= 1,
            "error",
            f"Found {count} core feature(s) in the text",
            {"count": count},
        ),
        CheckResult(
            "spec_has_target_users",
            has_users,
            "error",
            "Text names target users" if has_users else "No target users found in the text",
        ),
    ]


@timed
def check_files_extracted(parsed: ParsedFiles) -> CheckResult:
    return CheckResult(
        "files_extracted",
        bool(parsed.files),
        "error",
        f"Extracted {len(parsed.files)} file(s) from the free text",
        {"files": [f.path for f in parsed.files], "rejectedPaths": parsed.rejected_paths},
    )


# ---------------------------------------------------------------- running the naive pipeline


@dataclass
class NaiveOutputs:
    spec: str = ""
    stack: str = ""
    code: str = ""
    files: list[GeneratedFile] = field(default_factory=list)


async def _step(
    session: AsyncSession, provider: LLMProvider, agent: str, prompt: str, project_id: str
) -> str:
    started = time.perf_counter()
    run = AgentRun(
        project_id=project_id,
        agent=agent,
        stage=agent,
        mode="naive",
        provider=provider.name,
        model=provider.model,
        status="running",
        input_json={"prompt": prompt},
        validation_errors=[],
    )
    session.add(run)
    await session.commit()
    try:
        result = await provider.generate_text(
            system=f"{NAIVE_RULES}\n\n{INSTRUCTIONS[agent]}", prompt=prompt, kind=KIND_FOR_AGENT[agent]
        )
        run.status, run.model = "succeeded", result.model
        run.input_tokens, run.output_tokens = result.input_tokens, result.output_tokens
        run.output_json = {"text": result.text}
        return result.text
    except LLMError as exc:
        run.status, run.error = "failed", str(exc)[:4000]
        raise AgentRunFailed(agent, run.id, str(exc)) from exc
    finally:
        run.finished_at = utcnow()
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        await session.commit()


async def run_naive_pipeline(
    session: AsyncSession, project: Project, provider: LLMProvider | None = None
) -> NaiveOutputs:
    """Idea -> Tech Stack -> Code with free-text handoffs, then the same static checks as strict mode."""
    out = NaiveOutputs()

    def provider_for(agent: str) -> LLMProvider:
        return provider or get_provider(agent)  # type: ignore[arg-type]

    out.spec = await _step(
        session,
        provider_for("idea"),
        "idea",
        f"Project name: {project.name}\n\nIdea:\n{project.idea}",
        project.id,
    )
    await run_checks(
        session,
        project_id=project.id,
        stage="idea",
        agent_run_id=None,
        check=lambda: check_spec_text(out.spec),
    )

    out.stack = await _step(session, provider_for("stack"), "stack", f"Spec:\n{out.spec}", project.id)
    inferred = infer_stack(out.stack)
    await run_checks(
        session,
        project_id=project.id,
        stage="stack",
        agent_run_id=None,
        check=lambda: checks.check_stack(inferred),
    )

    out.code = await _step(
        session, provider_for("code"), "code", f"Spec:\n{out.spec}\n\nTech stack:\n{out.stack}", project.id
    )
    parsed = parse_files(out.code)
    out.files = parsed.files
    for f in parsed.files:
        session.add(
            ProjectFile(
                project_id=project.id, path=f.path, language=f.language, content=f.content, source="code"
            )
        )
    await session.commit()
    await run_checks(
        session,
        project_id=project.id,
        stage="code",
        agent_run_id=None,
        check=lambda: [check_files_extracted(parsed), *checks.check_code(parsed.files, inferred)],
    )
    project.stage, project.status = "code", "in-progress"
    await session.commit()
    return out
