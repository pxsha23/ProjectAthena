"""The hand-written migration must produce exactly the schema the models describe."""

import os
import subprocess
import sys
from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine

from app import models  # noqa: F401
from app.core.db import Base

SERVER_DIR = Path(__file__).resolve().parents[2]


def _alembic(*args: str, url: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=SERVER_DIR,
        env={**os.environ, "DATABASE_URL": url},
        capture_output=True,
        text=True,
        check=False,
    )


def test_migration_matches_models(tmp_path: Path) -> None:
    db_file = tmp_path / "migrated.db"
    result = _alembic("upgrade", "head", url=f"sqlite+aiosqlite:///{db_file.as_posix()}")
    assert result.returncode == 0, result.stderr

    engine = create_engine(f"sqlite:///{db_file.as_posix()}")
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    engine.dispose()
    assert diff == [], diff


def test_postgres_sql_is_generated_with_pgvector() -> None:
    result = _alembic("upgrade", "head", "--sql", url="postgresql+asyncpg://u:p@localhost/athena")
    assert result.returncode == 0, result.stderr
    sql = result.stdout
    assert "CREATE EXTENSION IF NOT EXISTS vector" in sql
    assert "embedding VECTOR(384) NOT NULL" in sql
    assert "USING hnsw (embedding vector_cosine_ops)" in sql
    assert "spec JSONB" in sql
