"""Trains a baseline on one dataset, writes predictions for val_tune, val_cal and test, and a run record.

Examples:
    python scripts/run_baseline.py --baseline tfidf_lr --dataset stacksample
    python scripts/run_baseline.py --baseline setfit --dataset clinc150 --seed 0 --seed 1
Runs every seed in train.seeds unless --seed is given. Finished runs are skipped unless --force.
"""

import argparse

from athena_advisor.baselines import BASELINES
from athena_advisor.baselines.run import DATASETS, run_baseline
from athena_advisor.config import ConfigError, load_config


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--baseline", required=True, choices=sorted(BASELINES))
    parser.add_argument("--dataset", required=True, choices=DATASETS)
    parser.add_argument("--config", default="configs/base.yaml")
    parser.add_argument(
        "--seed", type=int, action="append", help="seed to run (repeatable; default train.seeds)"
    )
    parser.add_argument("--force", action="store_true", help="run again even if results exist")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="config override")
    args = parser.parse_args()
    try:
        config = load_config(args.config, args.set)
    except ConfigError as exc:
        parser.error(str(exc))

    for seed in args.seed or config.train.seeds:
        outcome = run_baseline(args.baseline, args.dataset, config, seed, force=args.force)
        print(f"[{args.baseline} / {args.dataset} / seed {seed}] {outcome.message}")
        if outcome.status == "not_applicable":
            break  # the same for every seed
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
