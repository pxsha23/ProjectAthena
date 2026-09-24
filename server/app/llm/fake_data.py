"""Canned, schema-valid outputs for the "fake" provider (tests, demos, offline development)."""

from typing import Any

from app.schemas.agents import (
    ChatAgentOutput,
    CodeBundle,
    EvaReport,
    LearningSummary,
    ProjectSpec,
    StackPlan,
)

SPEC: dict[str, Any] = {
    "summary": "A web app that helps students form study groups with classmates from the same course, "
    "find a time that suits everyone and reserve a study room.",
    "targetUsers": ["University students", "Course representatives"],
    "sections": [
        {
            "title": "Core features",
            "items": [
                "List upcoming study sessions",
                "Join a study session if it is not full",
                "See which course each session belongs to",
            ],
        },
        {"title": "Out of scope (v1)", "items": ["Video calls inside the app"]},
    ],
    "openQuestions": ["Should sign-up be limited to university email addresses?"],
}

STACK: dict[str, Any] = {
    "choices": [
        {
            "layer": "frontend",
            "name": "React + Vite + TypeScript",
            "reason": "Fast development and type safety for an interactive UI.",
            "alternatives": ["Next.js"],
        },
        {
            "layer": "backend",
            "name": "FastAPI (Python)",
            "reason": "Readable request validation and automatic API docs.",
            "alternatives": ["Express"],
        },
        {
            "layer": "database",
            "name": "PostgreSQL",
            "reason": "Relational data with constraints that prevent double bookings.",
            "alternatives": ["SQLite"],
        },
    ],
    "backendLanguage": "python",
    "frontendFramework": "react",
    "backendFramework": "fastapi",
    "database": "postgresql",
}

MAIN_PY = """from fastapi import FastAPI, HTTPException

from models import StudySession

app = FastAPI(title="StudySync API")

SESSIONS: dict[str, StudySession] = {}


@app.get("/sessions", response_model=list[StudySession])
def list_sessions() -> list[StudySession]:
    return sorted(SESSIONS.values(), key=lambda s: s.starts_at)


@app.post("/sessions/{session_id}/join", response_model=StudySession)
def join_session(session_id: str, user: str = "demo") -> StudySession:
    session = SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    if len(session.members) >= session.capacity:
        raise HTTPException(status_code=409, detail="Session is full")
    session.members.append(user)
    return session
"""

MODELS_PY = """from datetime import datetime

from pydantic import BaseModel, Field


class StudySession(BaseModel):
    id: str
    title: str = Field(min_length=3)
    course_code: str
    starts_at: datetime
    capacity: int = Field(ge=2, le=20)
    members: list[str] = []
"""

APP_TSX = """import { useEffect, useState } from 'react'

interface StudySession {
  id: string
  title: string
  capacity: number
  members: string[]
}

export default function App() {
  const [sessions, setSessions] = useState<StudySession[]>([])

  useEffect(() => {
    fetch('/sessions')
      .then((res) => res.json())
      .then(setSessions)
  }, [])

  return (
    <ul>
      {sessions.map((s) => (
        <li key={s.id}>
          {s.title} ({s.members.length}/{s.capacity})
        </li>
      ))}
    </ul>
  )
}
"""

PACKAGE_JSON = """{
  "name": "studysync-frontend",
  "private": true,
  "type": "module",
  "scripts": { "dev": "vite", "build": "vite build" },
  "dependencies": { "react": "^19.0.0", "react-dom": "^19.0.0" },
  "devDependencies": { "vite": "^7.0.0", "typescript": "^5.6.0" }
}
"""

CODE: dict[str, Any] = {
    "files": [
        {"path": "backend/main.py", "language": "python", "content": MAIN_PY, "purpose": "API routes."},
        {"path": "backend/models.py", "language": "python", "content": MODELS_PY, "purpose": "Data models."},
        {
            "path": "backend/requirements.txt",
            "language": "plaintext",
            "content": "fastapi==0.118.0\nuvicorn[standard]==0.37.0\npydantic==2.11.0\n",
            "purpose": "Python dependencies.",
        },
        {
            "path": "frontend/src/App.tsx",
            "language": "typescript",
            "content": APP_TSX,
            "purpose": "Main page.",
        },
        {
            "path": "frontend/package.json",
            "language": "json",
            "content": PACKAGE_JSON,
            "purpose": "npm config.",
        },
        {
            "path": "README.md",
            "language": "markdown",
            "content": "# StudySync\n\nFind study partners and book rooms.\n",
            "purpose": "Project readme.",
        },
    ],
    "entrypoints": ["backend/main.py", "frontend/src/App.tsx"],
    "dependencies": {"python": ["fastapi", "uvicorn", "pydantic"], "node": ["react", "react-dom"]},
}

EVA: dict[str, Any] = {
    "score": 82,
    "personas": [
        {"id": "p1", "name": "Alpha", "archetype": "First-year student", "goal": "Join a first study group."},
        {"id": "p2", "name": "Bravo", "archetype": "Busy part-timer", "goal": "Find a session on a phone."},
        {"id": "p3", "name": "Charlie", "archetype": "Course rep", "goal": "Organise sessions for a class."},
    ],
    "findings": [
        {
            "id": "f1",
            "personaId": "p1",
            "severity": "pass",
            "title": "Session list is clear",
            "detail": "Alpha found an upcoming session straight away.",
        },
        {
            "id": "f2",
            "personaId": "p3",
            "severity": "fail",
            "title": "Joining a full session shows a raw error",
            "detail": "The API returns 409 with no friendly message. Show 'This session is full' instead.",
        },
    ],
}


def _topic(title: str, files: list[str]) -> dict[str, Any]:
    return {
        "title": title,
        "summary": [f"This topic explains {title.lower()} in the generated project."],
        "concepts": [title],
        "howItWorks": ["First, the relevant file is loaded.", "Then it handles the request."],
        "files": files,
        "keyTerms": [{"term": title, "meaning": f"The idea behind {title.lower()}."}],
        "tryIt": "Change one line in the file and see what happens.",
    }


SUMMARY: dict[str, Any] = {
    "overview": {
        "summary": [
            "You built StudySync, a small full-stack app with a React frontend and a FastAPI backend.",
            "The agents chose the stack, generated the code and wrote deployment files.",
        ],
        "stats": [],
        "nextSteps": [
            "Store sessions in PostgreSQL instead of memory.",
            "Show a friendly message when a session is full.",
            "Add tests for the API.",
        ],
    },
    "topics": [
        _topic("How the project fits together", ["backend/main.py", "frontend/src/App.tsx"]),
        _topic("REST APIs with FastAPI", ["backend/main.py"]),
        _topic("Validating data with Pydantic", ["backend/models.py"]),
        _topic("React state and data fetching", ["frontend/src/App.tsx"]),
    ],
}

CHAT: dict[str, Any] = {
    "reply": "Good question. The session list is loaded in App.tsx when the page first appears.",
    "suggestedActions": ["Open frontend/src/App.tsx"],
}

CANNED: dict[type, dict[str, Any]] = {
    ProjectSpec: SPEC,
    StackPlan: STACK,
    CodeBundle: CODE,
    EvaReport: EVA,
    LearningSummary: SUMMARY,
    ChatAgentOutput: CHAT,
}


def _naive_code() -> str:
    parts = ["Here is the project.\n"]
    fences = {"python": "python", "typescript": "tsx", "json": "json", "markdown": "markdown"}
    for f in CODE["files"]:
        fence = fences.get(f["language"], "")
        parts.append(f"FILE: {f['path']}\n```{fence}\n{f['content'].rstrip()}\n```\n")
    return "\n".join(parts)


# Free-text answers for the naive (no schema) mode used in the Paper 1 comparison.
NAIVE_TEXT: dict[str, str] = {
    "spec": (
        "# Spec\n\n"
        f"{SPEC['summary']}\n\n"
        "## Target users\n- University students\n- Course representatives\n\n"
        "## Core features\n- List upcoming study sessions\n- Join a study session if it is not full\n"
        "- See which course each session belongs to\n\n"
        "## Out of scope (v1)\n- Video calls inside the app\n"
    ),
    "stack": (
        "# Tech stack\n\n- Frontend: React + Vite + TypeScript\n"
        "- Backend: FastAPI (Python)\n- Database: PostgreSQL\n"
    ),
    "code": _naive_code(),
}
