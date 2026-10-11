"""Prints split counts for everything built under a processed-data folder (default: data/processed)."""

import argparse

from athena_advisor.data.summary import summarize
from athena_advisor.paths import resolve


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("processed_dir", nargs="?", default="data/processed")
    args = parser.parse_args()
    print(summarize(resolve(args.processed_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
