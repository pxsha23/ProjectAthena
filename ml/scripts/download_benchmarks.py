"""Downloads the four public benchmarks, converts them to the common format, and writes a data card each.

On Kaggle (internet on):
    python scripts/download_benchmarks.py
On a laptop (tiny hand-written fixtures in each source format, nothing is downloaded):
    python scripts/download_benchmarks.py --fixture
"""

import argparse
import json
from pathlib import Path

from athena_advisor.config import ConfigError, load_config
from athena_advisor.data.benchmarks import DATASETS, build_benchmarks, download
from athena_advisor.paths import resolve

FIXTURE_RAW = "tests/fixtures/benchmarks"
FIXTURE_OUT = "data/processed/benchmarks_fixture"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument("--raw-dir", help="where source files go (default: benchmarks.raw_dir)")
    parser.add_argument("--out", help="where converted files go (default: benchmarks.processed_dir)")
    parser.add_argument("--only", nargs="+", choices=DATASETS, help="only these datasets")
    parser.add_argument("--fixture", action="store_true", help="convert the tiny test fixtures instead")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="config override")
    args = parser.parse_args()
    try:
        config = load_config(args.config, args.set).benchmarks
    except ConfigError as exc:
        parser.error(str(exc))

    datasets = tuple(args.only or DATASETS)
    raw_dir = resolve(FIXTURE_RAW if args.fixture else (args.raw_dir or config.raw_dir))
    out_dir = resolve(args.out or (FIXTURE_OUT if args.fixture else config.processed_dir))
    if not args.fixture:
        for name in datasets:
            for path in download(name, raw_dir):
                print(f"{name}: {path.name} ({path.stat().st_size} bytes)")

    infos = build_benchmarks(Path(raw_dir), Path(out_dir), config, datasets)
    print(json.dumps({name: info["counts"] for name, info in infos.items()}, indent=2))
    print(f"Wrote {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
