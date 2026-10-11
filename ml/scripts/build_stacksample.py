"""Builds the StackSample splits and writes DATA_CARD.md.

On Kaggle:
    python scripts/build_stacksample.py --raw-dir /kaggle/input/stacksample --out data/processed/stacksample
On a laptop (tiny hand-made sample, never the real data):
    python scripts/build_stacksample.py --fixture
"""

import argparse
import json

from athena_advisor.config import ConfigError, load_config
from athena_advisor.data.build import build
from athena_advisor.data.data_card import write_data_card
from athena_advisor.paths import resolve

FIXTURE_DIR = "tests/fixtures/stacksample_tiny"
FIXTURE_OUT = "data/processed/fixture"
# With 7 kept fixture questions, the default 80/7/6/7 split would leave the validation splits empty.
FIXTURE_FRACTIONS = "data.split_fractions=[0.4, 0.2, 0.2, 0.2]"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", default="configs/base.yaml", help="experiment config (default: base)")
    parser.add_argument("--raw-dir", help="folder with Questions.csv and Tags.csv (default: data.raw_dir)")
    parser.add_argument("--out", help="output folder (default: data.processed_dir/stacksample)")
    parser.add_argument("--fixture", action="store_true", help="build from the tiny test fixtures instead")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="config override")
    args = parser.parse_args()

    overrides = [FIXTURE_FRACTIONS, *args.set] if args.fixture else args.set
    try:
        config = load_config(args.config, overrides)
    except ConfigError as exc:
        parser.error(str(exc))
    raw_dir = FIXTURE_DIR if args.fixture else (args.raw_dir or config.data.raw_dir)
    out_dir = args.out or (FIXTURE_OUT if args.fixture else f"{config.data.processed_dir}/stacksample")

    info = build(config, raw_dir, out_dir)
    card = write_data_card(out_dir)
    summary = {k: info[k] for k in ("questions_read", "questions_kept", "split_counts", "split_starts")}
    print(json.dumps(summary, indent=2))
    print(f"Wrote {resolve(out_dir)} and {card.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
