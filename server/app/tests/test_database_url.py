"""DATABASE_URL conversion for asyncpg: Neon's libpq-style URLs, pooled endpoints, local URLs."""

import pytest

from app.core.config import Settings
from app.core.database_url import engine_target, normalise_url

SECRET = "x" * 40
NEON_POOLED = (
    "postgresql://athena_owner:s3cret-pass@ep-quiet-sky-123456-pooler.ap-southeast-1.aws.neon.tech/neondb"
    "?sslmode=require&channel_binding=require"
)
NEON_DIRECT = NEON_POOLED.replace("-pooler", "")
LOCAL = "postgresql+asyncpg://athena:athena@localhost:5433/athena"


def test_local_docker_url_is_unchanged() -> None:
    target = engine_target(LOCAL)
    assert target.url == LOCAL and target.connect_args == {}
    assert engine_target("postgresql://athena:athena@localhost:5433/athena").url == LOCAL


def test_neon_pooled_url() -> None:
    target = engine_target(NEON_POOLED)
    assert target.url.startswith("postgresql+asyncpg://athena_owner:s3cret-pass@ep-quiet-sky-123456-pooler.")
    # libpq-only parameters are removed from the URL; TLS goes to asyncpg through connect_args.
    assert "sslmode" not in target.url and "channel_binding" not in target.url
    assert target.connect_args["ssl"] == "require"
    # PgBouncer: no statement caching anywhere, and unique statement names.
    assert target.connect_args["statement_cache_size"] == 0
    assert "prepared_statement_cache_size=0" in target.url
    name = target.connect_args["prepared_statement_name_func"]
    assert name() != name() and target.is_pooled


def test_neon_direct_url_keeps_statement_caching() -> None:
    target = engine_target(NEON_DIRECT)
    assert target.connect_args == {"ssl": "require"} and not target.is_pooled
    assert target.url.endswith("aws.neon.tech/neondb")


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("?sslmode=disable", False),
        ("?sslmode=verify-full", "verify-full"),
        ("?ssl=require", "require"),
        ("", None),
    ],
)
def test_ssl_modes(query: str, expected: object) -> None:
    target = engine_target(f"postgres://u:p@db.example.com:5432/app{query}")
    assert target.connect_args.get("ssl") == expected
    assert "?" not in target.url  # sslmode and ssl never reach asyncpg as URL parameters


def test_other_parameters_are_kept_and_bad_modes_rejected() -> None:
    target = engine_target("postgresql://u:p@db.example.com/app?sslmode=require&application_name=athena")
    assert target.url.endswith("?application_name=athena")
    with pytest.raises(ValueError, match="sslmode"):
        engine_target("postgresql://u:p@db.example.com/app?sslmode=sometimes")


def test_non_postgres_urls_pass_through() -> None:
    sqlite = "sqlite+aiosqlite:///test.db"
    assert normalise_url(sqlite) == sqlite and engine_target(sqlite).url == sqlite


def test_repr_never_shows_the_password() -> None:
    assert "s3cret-pass" not in repr(engine_target(NEON_POOLED))


def test_settings_migration_url() -> None:
    plain = Settings(secret_key=SECRET, database_url=NEON_POOLED, _env_file=None)  # type: ignore[call-arg]
    assert plain.database_url.startswith("postgresql+asyncpg://") and "sslmode=require" in plain.database_url
    assert plain.migration_url == plain.database_url
    both = Settings(
        secret_key=SECRET,
        database_url=NEON_POOLED,
        database_url_direct=NEON_DIRECT,
        _env_file=None,  # type: ignore[call-arg]
    )
    assert both.migration_url == normalise_url(NEON_DIRECT)
