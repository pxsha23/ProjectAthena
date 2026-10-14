"""Trains the Advisor model on one dataset for one seed, then writes predictions and a run record.

Examples (on Kaggle):
    python scripts/train.py --config configs/experiments/full.yaml --dataset stacksample --seed 0
    python scripts/train.py --config configs/experiments/plain.yaml --dataset clinc150 --seed 2
If a run is interrupted, run the same command again: it resumes from the last checkpoint.
--stop-after N ends the session after N epochs (for notebook time limits); run again to continue.
"""

import argparse
import json

from athena_advisor.config import ConfigError, load_config
from athena_advisor.eval.splits import DATASETS
from athena_advisor.train.trainer import train_run


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--dataset", required=True, choices=DATASETS)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--stop-after", type=int, help="stop this session after N epochs (resume later)")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="config override")
    args = parser.parse_args()
    try:
        config = load_config(args.config, args.set)
    except ConfigError as exc:
        parser.error(str(exc))

    result = train_run(config, args.dataset, args.seed, stop_after=args.stop_after)
    if result is None:
        print("Stopped before the end of training. Run the same command again to resume.")
        return 0
    test = json.loads(result.record.read_text(encoding="utf-8"))["metrics"]["test"]
    summary = {k: test.get(k) for k in ("micro_f1", "macro_f1", "lead_accuracy", "lead_rows")}
    print(json.dumps({"best_epoch": result.state.best_epoch, "test": summary}, indent=2))
    print(f"Run record: {result.record}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
