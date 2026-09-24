"""Integration tests against the real PostgreSQL + pgvector from docker-compose.yml (port 5433).

They use a separate database, athena_test, created and migrated here, so development data is untouched.
Skipped automatically when the database is not reachable (e.g. Docker is not running).
Override the server with INTEGRATION_POSTGRES_URL=postgresql://user:pass@host:port.
"""

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from pathlib import Path

import asyncpg
import httpx
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core import db as db_module
from app.main import app
from app.tests.conftest import create_project, register, run_stage

pytestmark = pytest.mark.integration

ADMIN_URL = os.environ.get("INTEGRATION_POSTGRES_URL", "postgresql://athena:athena@localhost:5433")
TEST_DB = "athena_test"
SERVER_DIR = Path(__file__).resolve().parents[2]


async def _reachable() -> bool:
    try:
        conn = await asyncpg.connect(f"{ADMIN_URL}/athena", timeout=3)
    except (OSError, asyncpg.PostgresError, TimeoutError):
        return False
    await conn.close()
    return True


@pytest.fixture(scope="module")
async def postgres() -> AsyncIterator[str]:
    if not await _reachable():
        pytest.skip("Docker Postgres on port 5433 is not running (docker compose up -d)")

    admin = await asyncpg.connect(f"{ADMIN_URL}/athena")
    await admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
    await admin.execute(f"CREATE DATABASE {TEST_DB}")
    await admin.close()

    url = f"{ADMIN_URL.replace('postgresql://', 'postgresql+asyncpg://')}/{TEST_DB}"
    migrated = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=SERVER_DIR,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
        check=False,
    )
    assert migrated.returncode == 0, migrated.stderr

    # Point the app at the test database for this module only.
    saved = db_module._engine, db_module._session_factory
    engine = create_async_engine(url)
    db_module._engine, db_module._session_factory = engine, async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield url
    finally:
        await engine.dispose()
        db_module._engine, db_module._session_factory = saved
        admin = await asyncpg.connect(f"{ADMIN_URL}/athena")
        await admin.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        await admin.close()


@pytest.fixture
async def pg_client(postgres: str) -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver") as c:
        await register(c)
        yield c


async def test_pgvector_extension_and_schema(postgres: str) -> None:
    conn = await asyncpg.connect(postgres.replace("+asyncpg", ""))
    try:
        extensions = {r["extname"] for r in await conn.fetch("select extname from pg_extension")}
        column = await conn.fetchval(
            "select format_type(atttypid, atttypmod) from pg_attribute "
            "where attrelid = 'code_chunks'::regclass and attname = 'embedding'"
        )
        index = await conn.fetchval(
            "select indexdef from pg_indexes where indexname = 'ix_code_chunks_embedding'"
        )
    finally:
        await conn.close()
    assert "vector" in extensions
    assert column == "vector(384)"
    assert "hnsw" in index


async def test_full_pipeline_on_postgres(pg_client: httpx.AsyncClient) -> None:
    project = await create_project(pg_client)
    pid = project["id"]
    for stage in ("idea", "stack", "code", "eva", "deploy"):
        response = await run_stage(pg_client, pid, stage)
        assert response.status_code == 202, response.text

    detail = (await pg_client.get(f"/api/projects/{pid}")).json()
    assert detail["stage"] == "deploy" and detail["learning"]["topics"]
    # JSONB round trip keeps nested agent outputs intact.
    assert detail["eva"]["personas"][0]["name"] == "Alpha"

    runs = (await pg_client.get(f"/api/projects/{pid}/runs")).json()
    assert {r["agent"] for r in runs} >= {"idea", "stack", "code", "eva", "deploy", "summary"}
    assert all(r["status"] == "succeeded" for r in runs)

    checks = (await pg_client.get(f"/api/projects/{pid}/checks")).json()
    assert checks and all(c["passed"] for c in checks)

    metrics = (await pg_client.get("/api/metrics")).json()
    assert {m["agent"] for m in metrics["agents"]} >= {"idea", "code", "summary"}


async def test_vector_search_uses_pgvector(pg_client: httpx.AsyncClient) -> None:
    project = await create_project(pg_client)
    for stage in ("idea", "stack", "code"):
        await run_stage(pg_client, project["id"], stage)
    hits = (
        await pg_client.get(f"/api/projects/{project['id']}/search", params={"q": "join session capacity"})
    ).json()
    assert hits[0]["filePath"] == "backend/main.py"
    assert 0 < hits[0]["score"] <= 1
