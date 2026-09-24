"""Test setup: SQLite database file, fake LLM providers, hash embeddings. No network, no Docker."""

import os
import tempfile
import uuid
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

# Settings are read once and cached, so the environment must be ready before `app` is imported.
_tmp = Path(tempfile.mkdtemp(prefix="athena-tests-"))
os.environ.update(
    {
        "APP_ENV": "test",
        "SECRET_KEY": "test-secret-key-that-is-long-enough-1234567890",
        "DATABASE_URL": f"sqlite+aiosqlite:///{(_tmp / 'test.db').as_posix()}",
        "EMBEDDINGS_BACKEND": "hash",
        "ANTHROPIC_API_KEY": "",
        "ANTHROPIC_MODEL": "",
        "GITHUB_CLIENT_ID": "",
        "GITHUB_CLIENT_SECRET": "",
        **{f"AGENT_{name}_PROVIDER": "fake" for name in ("IDEA", "STACK", "CODE", "SUMMARY", "EVA", "CHAT")},
    }
)

import httpx  # noqa: E402
import pytest  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402

from app import models  # noqa: E402,F401  (registers tables)
from app.core.config import get_settings  # noqa: E402
from app.core.db import Base, get_session_factory  # noqa: E402
from app.llm.factory import clear_provider_overrides  # noqa: E402
from app.main import app  # noqa: E402
from app.services import pipeline  # noqa: E402

TEST_PASSWORD = "correct-horse-battery"


@pytest.fixture(scope="session", autouse=True)
def _schema() -> Iterator[None]:
    """Creates tables with a plain sync engine so both sync and async tests can use them."""
    engine = create_engine(get_settings().database_url.replace("+aiosqlite", ""))
    Base.metadata.create_all(engine)
    engine.dispose()
    yield


@pytest.fixture(autouse=True)
def _reset() -> Iterator[None]:
    clear_provider_overrides()
    pipeline._running.clear()
    yield
    clear_provider_overrides()


@pytest.fixture
async def db() -> AsyncIterator:
    async with get_session_factory()() as session:
        yield session


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with _client() as c:
        yield c


async def register(client: httpx.AsyncClient, name: str = "Test Student") -> dict:
    email = f"user-{uuid.uuid4().hex[:10]}@example.com"
    response = await client.post(
        "/api/auth/register", json={"name": name, "email": email, "password": TEST_PASSWORD}
    )
    assert response.status_code == 201, response.text
    return {**response.json(), "password": TEST_PASSWORD}


@pytest.fixture
async def auth_client() -> AsyncIterator[httpx.AsyncClient]:
    """A client that is signed in as a fresh user (cookies set by /register)."""
    async with _client() as c:
        c.user = await register(c)  # type: ignore[attr-defined]
        yield c


IDEA = "An app where university students find study partners from the same course and book a room."


async def create_project(client: httpx.AsyncClient, name: str = "StudySync") -> dict:
    response = await client.post("/api/projects", json={"name": name, "idea": IDEA})
    assert response.status_code == 201, response.text
    return response.json()


async def run_stage(client: httpx.AsyncClient, project_id: str, stage: str) -> httpx.Response:
    # Background tasks finish before ASGITransport returns, so the stage is complete here.
    return await client.post(f"/api/projects/{project_id}/stages/{stage}/run")
