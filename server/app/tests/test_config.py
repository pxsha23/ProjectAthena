"""Settings parsing that matters for deployment."""

import pytest

from app.core.config import Settings

SECRET = "x" * 40


@pytest.mark.parametrize(
    ("given", "expected"),
    [
        ("postgres://u:p@host:5432/db", "postgresql+asyncpg://u:p@host:5432/db"),
        ("postgresql://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("postgresql+asyncpg://u:p@host/db", "postgresql+asyncpg://u:p@host/db"),
        ("sqlite+aiosqlite:///test.db", "sqlite+aiosqlite:///test.db"),
    ],
)
def test_database_url_gets_the_async_driver(given: str, expected: str) -> None:
    settings = Settings(secret_key=SECRET, database_url=given, _env_file=None)  # type: ignore[call-arg]
    assert settings.database_url == expected


def test_cors_origins_accept_a_comma_separated_list() -> None:
    settings = Settings(
        secret_key=SECRET,
        cors_origins="https://a.vercel.app, https://b.dev",
        _env_file=None,  # type: ignore[call-arg]
    )
    assert settings.cors_origins == ["https://a.vercel.app", "https://b.dev"]
