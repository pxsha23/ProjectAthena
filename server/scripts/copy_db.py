"""Copies every Athena table from a source database to a target database.

Run from server/, after migrations have created the tables on the target:

    SOURCE_DATABASE_URL=... TARGET_DATABASE_URL=... python -m uv run python scripts/copy_db.py --dry-run
    SOURCE_DATABASE_URL=... TARGET_DATABASE_URL=... python -m uv run python scripts/copy_db.py

The URLs are read from the environment so they never end up in shell history; --source-url and
--target-url exist too. URLs and passwords are never printed.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

# Make the app package importable when this file is run directly from server/scripts/.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.maintenance.copy_db import CopyError, copy_database, redact  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--source-url", default=os.environ.get("SOURCE_DATABASE_URL"))
    parser.add_argument("--target-url", default=os.environ.get("TARGET_DATABASE_URL"))
    parser.add_argument("--dry-run", action="store_true", help="only count rows, copy nothing")
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    if not args.source_url or not args.target_url:
        parser.error(
            "set SOURCE_DATABASE_URL and TARGET_DATABASE_URL (or pass --source-url and --target-url)"
        )
    urls = [args.source_url, args.target_url]
    try:
        asyncio.run(
            copy_database(args.source_url, args.target_url, dry_run=args.dry_run, batch_size=args.batch_size)
        )
    except CopyError as exc:
        print(f"Copy stopped: {redact(str(exc), urls)}", file=sys.stderr)
        return 1
    except Exception as exc:  # connection errors can quote the URL: scrub before printing
        print(f"Copy failed ({type(exc).__name__}): {redact(str(exc), urls)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
