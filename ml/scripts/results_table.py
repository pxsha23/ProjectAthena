"""Prints test metrics per experiment and condition (mean and standard deviation over seeds)."""

import argparse

from athena_advisor.eval.table import results_table
from athena_advisor.paths import resolve


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_dir", nargs="?", default="results")
    args = parser.parse_args()
    print(results_table(resolve(args.results_dir)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
