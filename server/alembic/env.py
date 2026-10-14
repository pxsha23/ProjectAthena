"""Alembic environment: async engine, URL from app settings.

Migrations connect to DATABASE_URL_DIRECT when it is set (Neon's direct, unpooled endpoint), otherwise to
DATABASE_URL. An explicit sqlalchemy.url in alembic.ini or on the command line wins over both.
"""

import asyncio

from sqlalchemy.engine import Connection

from alembic import context
from app import models  # noqa: F401  (registers tables on Base.metadata)
from app.core.config import get_settings
from app.core.database_url import engine_target, make_engine
from app.core.db import Base

config = context.config
target_metadata = Base.metadata


def database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or get_settings().migration_url


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of connecting (alembic upgrade head --sql)."""
    context.configure(
        url=engine_target(database_url()).url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    engine = make_engine(database_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
