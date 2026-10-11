"""A short text summary of everything built under a processed-data folder."""

import json
from pathlib import Path


def summarize(processed_dir: str | Path) -> str:
    """Counts per split for StackSample (build_info.json) and every benchmark (info.json) found."""
    processed_dir = Path(processed_dir)
    lines: list[str] = []
    for info_path in sorted(processed_dir.rglob("build_info.json")):
        info = json.loads(info_path.read_text(encoding="utf-8"))
        lines.append(f"StackSample ({info_path.parent.relative_to(processed_dir).as_posix()})")
        lines.append(
            f"  read {info['questions_read']}, kept {info['questions_kept']} ({info['kept_share']:.1%}), "
            f"dropped {info['dropped_no_mapped_tag']}"
        )
        for split, rows in info["split_counts"].items():
            before = info["split_counts_before_sampling"][split]
            sampled = f" (sampled from {before})" if before != rows else ""
            lines.append(f"  {split:<9} {rows:>8}{sampled}")
    for info_path in sorted(processed_dir.rglob("info.json")):
        info = json.loads(info_path.read_text(encoding="utf-8"))
        lines.append(f"{info['dataset']} ({info_path.parent.relative_to(processed_dir).as_posix()})")
        for split, counts in info["counts"].items():
            extra = []
            if counts["out_of_scope"]:
                extra.append(f"{counts['out_of_scope']} out of scope")
            if counts["multi_label"]:
                extra.append(f"{counts['multi_label']} multi-label")
            suffix = f" ({', '.join(extra)})" if extra else ""
            lines.append(f"  {split:<9} {counts['rows']:>8}  {len(counts['labels'])} labels{suffix}")
    return "\n".join(lines) if lines else f"Nothing built under {processed_dir} yet."
