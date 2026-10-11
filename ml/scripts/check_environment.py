"""Prints Python, PyTorch and GPU details and fails if any dependency is missing."""

import json

from athena_advisor.environment import environment_report


def main() -> int:
    report = environment_report()
    print(json.dumps(report, indent=2))
    if report["missing_modules"]:
        print(f"Missing: {', '.join(report['missing_modules'])}. Install them before running the pipeline.")
        return 1
    if not report.get("cuda_available"):
        print("No GPU found: data preparation still works, training will be slow.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
