"""Zips results/ (run records, predictions, training logs; never checkpoints) for download or reuse."""

import argparse

from athena_advisor.kaggle import pack_results
from athena_advisor.paths import ml_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True, help="zip file to write, for example /kaggle/working/x.zip")
    args = parser.parse_args()
    path, count = pack_results(ml_root(), args.out)
    print(f"Wrote {path} with {count} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
