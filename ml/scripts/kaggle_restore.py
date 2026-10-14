"""Copies the processed data (required) and any earlier results (optional) from Kaggle inputs into ml/."""

import argparse

from athena_advisor.kaggle import restore_data, restore_results
from athena_advisor.paths import ml_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", default="/kaggle/input")
    args = parser.parse_args()
    target = restore_data(args.input_root, ml_root())
    print(f"Processed data in {target}: {sorted(p.name for p in target.iterdir())}")
    restored = restore_results(args.input_root, ml_root())
    print(f"Restored {restored} files from earlier results" if restored else "No earlier results attached")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
