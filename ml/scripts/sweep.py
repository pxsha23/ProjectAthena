"""Runs every unfinished job in a sweep file; jobs that already have a run record are skipped.

    python scripts/sweep.py configs/sweeps/main.yaml --time-budget-hours 11
Start it again (with earlier results restored) to continue a sweep in a new session.
"""

import argparse

from athena_advisor.sweep import run_sweep


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("sweep", help="sweep file, for example configs/sweeps/main.yaml")
    parser.add_argument("--time-budget-hours", type=float, help="start no new job after this many hours")
    parser.add_argument(
        "--set", action="append", default=[], metavar="KEY=VALUE", help="override for every job"
    )
    args = parser.parse_args()
    results = run_sweep(args.sweep, args.set, args.time_budget_hours)
    return 1 if any(r.status == "failed" for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
