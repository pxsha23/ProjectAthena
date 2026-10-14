"""Turns a DATABASE_URL into what SQLAlchemy's asyncpg driver needs.

Hosted Postgres providers hand out libpq-style URLs, for example Neon:
    postgresql://user:pass@ep-x-pooler.ap-southeast-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require
asyncpg does not understand `sslmode` or `channel_binding` as URL parameters, so they are removed from the URL
and the TLS mode is passed through connect_args as asyncpg's `ssl` argument instead. `channel_binding` has no
asyncpg equivalent and is dropped (TLS is still required by `ssl`).

Neon's pooled endpoint (a host containing "-pooler") runs PgBouncer in transaction mode, where prepared
statements cannot be cached per connection, so both asyncpg's and SQLAlchemy's statement caches are turned
off and every prepared statement gets a unique name.

Local URLs (the Docker database on port 5433) pass through unchanged apart from the driver name.
"""

from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

ASYNC_DRIVER = "postgresql+asyncpg"
SSL_MODES = {"disable", "allow", "prefer", "require", "verify-ca", "verify-full"}
# libpq-only parameters asyncpg rejects.
DROPPED_PARAMS = ("sslmode", "channel_binding", "ssl")


def normalise_url(url: str) -> str:
    """postgres:// and postgresql:// URLs get the asyncpg driver; anything else is returned unchanged."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return f"{ASYNC_DRIVER}://" + url[len(prefix) :]
    return url


@dataclass(frozen=True)
class EngineTarget:
    url: str
    connect_args: dict[str, Any] = field(default_factory=dict)

    @property
    def is_pooled(self) -> bool:
        return "statement_cache_size" in self.connect_args

    def __repr__(self) -> str:
        # Never show the password, even in a debugger or a stack trace.
        safe = make_url(self.url).render_as_string(hide_password=True)
        return f"EngineTarget(url={safe!r}, connect_args={sorted(self.connect_args)})"


def engine_target(url: str) -> EngineTarget:
    parsed = make_url(normalise_url(url))
    if parsed.drivername != ASYNC_DRIVER:
        return EngineTarget(url=parsed.render_as_string(hide_password=False))

    query = dict(parsed.query)
    mode = query.get("ssl") or query.get("sslmode")
    for name in DROPPED_PARAMS:
        query.pop(name, None)
    connect_args: dict[str, Any] = {}
    if mode is not None:
        mode = str(mode)
        if mode not in SSL_MODES:
            raise ValueError(f"Unsupported sslmode {mode!r}; use one of {sorted(SSL_MODES)}")
        connect_args["ssl"] = False if mode == "disable" else mode

    if parsed.host and "-pooler." in parsed.host:
        # PgBouncer (transaction mode): no statement caching, unique statement names.
        connect_args["statement_cache_size"] = 0
        connect_args["prepared_statement_name_func"] = lambda: f"__athena_{uuid4().hex}__"
        query["prepared_statement_cache_size"] = "0"

    return EngineTarget(
        url=parsed.set(query=query).render_as_string(hide_password=False), connect_args=connect_args
    )


def make_engine(url: str, **kwargs: Any) -> AsyncEngine:
    target = engine_target(url)
    return create_async_engine(target.url, connect_args=target.connect_args, **kwargs)
