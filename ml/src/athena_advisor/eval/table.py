"""A short results table from the run records: one row per experiment and condition, mean ± sd over seeds."""

import json
from pathlib import Path

from athena_advisor.eval.stats import across_seeds, format_mean_std

COLUMNS = ("micro_f1", "macro_f1", "lead_accuracy")


def collect(results_dir: str | Path) -> dict[tuple[str, str], list[dict]]:
    """Test metrics of every run record, grouped by (experiment, condition)."""
    groups: dict[tuple[str, str], list[dict]] = {}
    for path in sorted(Path(results_dir).glob("*/*/*.json")):
        if path.parent.parent.name in ("predictions", "runs") or not path.stem.isdigit():
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        test = record.get("metrics", {}).get("test")
        if test is not None:
            groups.setdefault((path.parent.parent.name, path.parent.name), []).append(test)
    return groups


def results_table(results_dir: str | Path) -> str:
    groups = collect(results_dir)
    if not groups:
        return f"No run records under {results_dir} yet."
    header = ["experiment", "condition", "seeds", *COLUMNS]
    rows = []
    for (experiment, condition), runs in sorted(groups.items()):
        cells = [experiment, condition, str(len(runs))]
        for column in COLUMNS:
            values = [run[column] for run in runs if run.get(column) is not None]
            cells.append(format_mean_std(across_seeds(values)) if values else "n/a")
        rows.append(cells)
    widths = [max(len(str(r[i])) for r in [header, *rows]) for i in range(len(header))]
    line = lambda cells: "  ".join(str(c).ljust(w) for c, w in zip(cells, widths, strict=True))  # noqa: E731
    return "\n".join([line(header), line(["-" * w for w in widths]), *(line(r) for r in rows)])
