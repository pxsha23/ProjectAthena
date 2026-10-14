"""scripts/copy_db.py against the Docker Postgres on port 5433, with two throwaway databases.

The target is migrated with a broken DATABASE_URL and a working DATABASE_URL_DIRECT, which also proves that
Alembic uses the direct URL when it is set. Skipped when Docker is not running.
"""

import os
import subprocess
import sys
from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.database_url import make_engine
from app.core.db import utcnow
from app.maintenance.copy_db import CopyError, copy_database, redact
from app.models import (
    AgentRun,
    ChatMessage,
    CodeChunk,
    ConsistencyCheck,
    Project,
    ProjectFile,
    RefreshToken,
    User,
)

pytestmark = pytest.mark.integration

ADMIN_URL = os.environ.get("INTEGRATION_POSTGRES_URL", "postgresql://athena:athena@localhost:5433")
SOURCE_DB, TARGET_DB = "athena_copy_source", "athena_copy_target"
SERVER_DIR = Path(__file__).resolve().parents[2]
BROKEN_URL = "postgresql+asyncpg://nobody:nothing@127.0.0.1:1/missing"


def url(database: str) -> str:
    return f"{ADMIN_URL.replace('postgresql://', 'postgresql+asyncpg://')}/{database}"


def migrate(database: str, *, via_direct: bool) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "DATABASE_URL": url(database)}
    if via_direct:
        env.update(DATABASE_URL=BROKEN_URL, DATABASE_URL_DIRECT=url(database))
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=SERVER_DIR,
        env=env,
        capture_output=True,
        text=True,
    )


async def recreate(*databases: str) -> None:
    admin = await asyncpg.connect(f"{ADMIN_URL}/athena")
    for database in databases:
        await admin.execute(f"DROP DATABASE IF EXISTS {database} WITH (FORCE)")
        await admin.execute(f"CREATE DATABASE {database}")
    await admin.close()


async def seed(database: str) -> None:
    engine = make_engine(url(database))
    async with async_sessionmaker(engine, expire_on_commit=False)() as session:
        user = User(name="Copy Test", email="copy@example.com", password_hash="hash")
        session.add(user)
        await session.flush()
        session.add(RefreshToken(id="t" * 64, user_id=user.id, expires_at=utcnow() + timedelta(days=7)))
        project = Project(
            owner_id=user.id,
            name="Book Swap",
            idea="Students rent textbooks to each other.",
            spec={"summary": "Rent books", "targetUsers": ["students"]},
        )
        session.add(project)
        await session.flush()
        session.add(ProjectFile(project_id=project.id, path="backend/main.py", content="print('hi')\n"))
        session.add(
            ChatMessage(
                project_id=project.id,
                role="agent",
                agent="idea",
                content="Proposed",
                proposal={"kind": "spec", "changes": ["Add photos"], "value": {}},
                proposal_status="pending",
                suggestions=["What next?"],
            )
        )
        run = AgentRun(
            project_id=project.id,
            agent="idea",
            provider="fake",
            model="m",
            status="succeeded",
            validation_errors=[],
            input_json={"a": 1},
        )
        session.add(run)
        await session.flush()
        session.add(
            ConsistencyCheck(
                project_id=project.id,
                agent_run_id=run.id,
                stage="idea",
                check_name="spec_has_core_features",
                passed=True,
                severity="error",
                message="ok",
                details={"count": 3},
            )
        )
        session.add(
            CodeChunk(
                project_id=project.id,
                file_path="backend/main.py",
                start_line=1,
                end_line=1,
                content="print('hi')",
                embedding=[0.5] + [0.0] * 383,
            )
        )
        await session.commit()
    await engine.dispose()


@pytest.fixture
async def databases() -> AsyncIterator[tuple[str, str]]:
    try:
        probe = await asyncpg.connect(f"{ADMIN_URL}/athena", timeout=3)
        await probe.close()
    except (OSError, asyncpg.PostgresError, TimeoutError):
        pytest.skip("Docker Postgres on port 5433 is not running (docker compose up -d)")
    await recreate(SOURCE_DB, TARGET_DB)
    source = migrate(SOURCE_DB, via_direct=False)
    assert source.returncode == 0, source.stderr
    target = migrate(TARGET_DB, via_direct=True)  # DATABASE_URL is broken: only the direct URL can work
    assert target.returncode == 0, target.stderr
    await seed(SOURCE_DB)
    try:
        yield url(SOURCE_DB), url(TARGET_DB)
    finally:
        admin = await asyncpg.connect(f"{ADMIN_URL}/athena")
        for database in (SOURCE_DB, TARGET_DB):
            await admin.execute(f"DROP DATABASE IF EXISTS {database} WITH (FORCE)")
        await admin.close()


async def test_dry_run_counts_and_copies_nothing(databases: tuple[str, str]) -> None:
    source, target = databases
    lines: list[str] = []
    report = await copy_database(source, target, dry_run=True, log=lines.append)
    assert (
        report.dry_run and report.source_before["projects"] == 1 and report.source_before["code_chunks"] == 1
    )
    assert all(count == 0 for count in report.target_before.values())
    assert any(line.startswith("projects") for line in lines) and lines[-1] == "Dry run: nothing was copied."
    check = await copy_database(source, target, dry_run=True, log=lambda *_: None)
    assert all(count == 0 for count in check.target_before.values())


async def test_copy_moves_every_row_in_foreign_key_order(databases: tuple[str, str]) -> None:
    source, target = databases
    report = await copy_database(source, target, batch_size=2, log=lambda *_: None)
    assert report.target_after == report.source_before
    assert (
        report.tables.index("users") < report.tables.index("projects") < report.tables.index("project_files")
    )

    engine = make_engine(target)
    async with async_sessionmaker(engine)() as session:
        chunk = (await session.scalars(select(CodeChunk))).one()
        assert chunk.embedding[0] == pytest.approx(0.5) and len(chunk.embedding) == 384
        message = (await session.scalars(select(ChatMessage))).one()
        assert message.proposal["changes"] == ["Add photos"] and message.suggestions == ["What next?"]
        project = (await session.scalars(select(Project))).one()
        assert project.spec["targetUsers"] == ["students"] and project.created_at.tzinfo is not None
    await engine.dispose()

    with pytest.raises(CopyError, match="already has rows"):
        await copy_database(source, target, log=lambda *_: None)


async def test_sequences_are_moved_past_the_copied_ids(databases: tuple[str, str]) -> None:
    source, target = databases
    # A serial column on the target whose rows were written with explicit ids, so its sequence lags behind.
    engine = make_engine(target)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE TABLE sequence_probe (id SERIAL PRIMARY KEY, note TEXT)"))
        await connection.execute(
            text("INSERT INTO sequence_probe (id, note) VALUES (1, 'a'), (2, 'b'), (7, 'c')")
        )
    report = await copy_database(source, target, log=lambda *_: None)
    assert "sequence_probe.id" in report.sequences_reset
    async with engine.begin() as connection:
        new_id = await connection.scalar(text("INSERT INTO sequence_probe (note) VALUES ('d') RETURNING id"))
    await engine.dispose()
    assert new_id == 8


async def test_unmigrated_target_is_refused(databases: tuple[str, str]) -> None:
    source, _ = databases
    await recreate("athena_copy_empty")
    try:
        with pytest.raises(CopyError, match="alembic upgrade head"):
            await copy_database(source, url("athena_copy_empty"), log=lambda *_: None)
    finally:
        admin = await asyncpg.connect(f"{ADMIN_URL}/athena")
        await admin.execute("DROP DATABASE IF EXISTS athena_copy_empty WITH (FORCE)")
        await admin.close()


async def test_local_url_with_libpq_parameters_still_connects(databases: tuple[str, str]) -> None:
    source, _ = databases
    engine = make_engine(f"{source}?sslmode=disable&channel_binding=disable")
    async with engine.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM users")) == 1
    await engine.dispose()


def test_script_never_prints_urls_or_passwords(databases: tuple[str, str]) -> None:
    source, target = databases
    env = {**os.environ, "SOURCE_DATABASE_URL": source, "TARGET_DATABASE_URL": target}
    script = [sys.executable, str(SERVER_DIR / "scripts" / "copy_db.py")]
    dry = subprocess.run([*script, "--dry-run"], cwd=SERVER_DIR, env=env, capture_output=True, text=True)
    real = subprocess.run(script, cwd=SERVER_DIR, env=env, capture_output=True, text=True)
    again = subprocess.run(
        script, cwd=SERVER_DIR, env=env, capture_output=True, text=True
    )  # target not empty
    assert dry.returncode == 0 and real.returncode == 0 and again.returncode == 1
    assert "Copy stopped" in again.stderr
    broken = subprocess.run(
        script, cwd=SERVER_DIR, env={**env, "TARGET_DATABASE_URL": BROKEN_URL}, capture_output=True, text=True
    )
    assert broken.returncode == 1
    for result in (dry, real, again, broken):
        output = result.stdout + result.stderr
        for secret in ("athena:athena", "localhost:5433", "nothing@127.0.0.1", "postgresql+asyncpg://"):
            assert secret not in output, (secret, output)


def test_redact() -> None:
    message = "could not connect to postgresql://user:hunter2@db.example.com/app (password hunter2)"
    clean = redact(message, ["postgresql://user:hunter2@db.example.com/app"])
    assert "hunter2" not in clean and "db.example.com" not in clean
    assert redact("other://a:b@host/x failed", []) == "*** failed"
