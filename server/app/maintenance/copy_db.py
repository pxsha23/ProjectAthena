"""Copies every Athena table from one database to another (for example Render Postgres to Neon).

The target must already have the tables: run `alembic upgrade head` against it first. Tables are copied in
foreign-key order (parents before children), in batches, inside one transaction on the target, so a failed
copy leaves the target as it was. Afterwards every id sequence on the target is moved past the highest copied
id, so new rows do not collide with copied ones.

Safety:
- the target must be empty (a second copy would duplicate rows);
- --dry-run only counts rows;
- URLs and passwords are never printed: output names the databases "source" and "target", and error
  messages are scrubbed of both URLs and their passwords.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, insert, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.core.database_url import make_engine
from app.core.db import Base

BATCH_SIZE = 1000

# Every column filled from a sequence: serial columns (nextval default) and identity columns.
SEQUENCES_SQL = text(
    """
    SELECT table_name, column_name, pg_get_serial_sequence(quote_ident(table_name), column_name) AS sequence
    FROM information_schema.columns
    WHERE table_schema = current_schema()
      AND (column_default LIKE 'nextval(%' OR is_identity = 'YES')
    """
)


class CopyError(Exception):
    """The copy cannot run (target not migrated, target not empty) or did not copy every row."""


@dataclass
class CopyReport:
    tables: list[str]
    source_before: dict[str, int]
    target_before: dict[str, int]
    target_after: dict[str, int] = field(default_factory=dict)
    sequences_reset: list[str] = field(default_factory=list)
    dry_run: bool = False


def redact(message: str, urls: list[str]) -> str:
    """Removes the given URLs, their passwords and any other URL with credentials from a message."""
    secrets: list[str] = []
    for url in urls:
        secrets.append(url)
        try:
            parsed = make_url(url)
        except Exception:  # an unparsable URL is still scrubbed as a whole
            continue
        secrets.append(parsed.render_as_string(hide_password=False))
        if parsed.password:
            secrets.append(str(parsed.password))
    for secret in sorted(set(secrets), key=len, reverse=True):
        if secret:
            message = message.replace(secret, "***")
    return re.sub(r"\b[\w+]+://[^\s'\"]*@[^\s'\"]*", "***", message)


async def _counts(connection: AsyncConnection, tables: list[str]) -> dict[str, int]:
    metadata = Base.metadata.tables
    return {
        name: int(await connection.scalar(select(func.count()).select_from(metadata[name])))
        for name in tables
    }


async def _missing_tables(engine: AsyncEngine, tables: list[str]) -> list[str]:
    async with engine.connect() as connection:
        present = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
    return [name for name in tables if name not in present]


async def _reset_sequences(connection: AsyncConnection) -> list[str]:
    reset = []
    for table, column, sequence in (await connection.execute(SEQUENCES_SQL)).all():
        if sequence is None:
            continue
        # Next value = highest id + 1; on an empty table the sequence starts again at 1.
        await connection.execute(
            text(
                f'SELECT setval(:sequence, COALESCE((SELECT MAX("{column}") FROM "{table}"), 1), '
                f'(SELECT MAX("{column}") FROM "{table}") IS NOT NULL)'
            ),
            {"sequence": sequence},
        )
        reset.append(f"{table}.{column}")
    return reset


async def copy_database(
    source_url: str,
    target_url: str,
    *,
    dry_run: bool = False,
    batch_size: int = BATCH_SIZE,
    log: Callable[[str], Any] = print,
) -> CopyReport:
    # sorted_tables lists every table after the tables its foreign keys point to.
    tables = [table.name for table in Base.metadata.sorted_tables]
    source, target = make_engine(source_url), make_engine(target_url)
    try:
        for label, engine in (("source", source), ("target", target)):
            missing = await _missing_tables(engine, tables)
            if missing:
                raise CopyError(
                    f"The {label} database has no tables {missing}. "
                    "Run 'alembic upgrade head' against it first."
                )
        async with source.connect() as s, target.connect() as t:
            report = CopyReport(tables, await _counts(s, tables), await _counts(t, tables), dry_run=dry_run)
        log(f"{'table':<22}{'source':>10}{'target':>10}")
        for name in tables:
            log(f"{name:<22}{report.source_before[name]:>10}{report.target_before[name]:>10}")
        if dry_run:
            log("Dry run: nothing was copied.")
            return report

        not_empty = [name for name in tables if report.target_before[name]]
        if not_empty:
            raise CopyError(
                f"The target database already has rows in {not_empty}; copy into an empty database."
            )

        metadata = Base.metadata.tables
        async with source.connect() as s, target.begin() as t:
            for name in tables:
                table = metadata[name]
                result = await s.stream(select(table))
                async for rows in result.partitions(batch_size):
                    await t.execute(insert(table), [dict(row._mapping) for row in rows])
            report.sequences_reset = await _reset_sequences(t)
        async with target.connect() as t:
            report.target_after = await _counts(t, tables)

        log("After the copy:")
        log(f"{'table':<22}{'source':>10}{'target':>10}")
        for name in tables:
            log(f"{name:<22}{report.source_before[name]:>10}{report.target_after[name]:>10}")
        log(f"Sequences reset: {', '.join(report.sequences_reset) or 'none'}")
        if report.target_after != report.source_before:
            raise CopyError("Row counts differ between source and target after the copy.")
        return report
    finally:
        await source.dispose()
        await target.dispose()
