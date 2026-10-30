"""render.yaml: the Neon database URLs are dashboard values, and migrations prefer the direct URL."""

from pathlib import Path

import yaml

BLUEPRINT = Path(__file__).resolve().parents[3] / "render.yaml"


def load_service() -> dict:
    data = yaml.safe_load(BLUEPRINT.read_text(encoding="utf-8"))
    assert "databases" not in data
    (service,) = data["services"]
    return service


def test_database_urls_are_set_in_the_dashboard() -> None:
    env = {item["key"]: item for item in load_service()["envVars"]}
    for key in ("DATABASE_URL", "DATABASE_URL_DIRECT"):
        assert env[key] == {"key": key, "sync": False}


def test_migrations_use_the_direct_url_with_fallback() -> None:
    start = load_service()["startCommand"]
    migrate, serve = start.split(" && ", 1)
    assert migrate == 'DATABASE_URL="${DATABASE_URL_DIRECT:-$DATABASE_URL}" uv run alembic upgrade head'
    assert "DATABASE_URL" not in serve
