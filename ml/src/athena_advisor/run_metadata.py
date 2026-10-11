"""Run records: every run writes results/<experiment>/<condition>/<seed>.json.

Each record carries what is needed to trust and repeat the numbers in the papers: the full config,
a hash of every data file used, the git commit (and whether the code had uncommitted changes),
the hardware, and when it ran.
"""

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from athena_advisor import __version__
from athena_advisor.config import AdvisorConfig
from athena_advisor.paths import ml_root, resolve

HASH_CHUNK_BYTES = 1 << 20


def file_sha256(path: str | Path) -> str:
    """SHA-256 of a file, read in 1 MB chunks so large dataset files never sit in memory."""
    digest = hashlib.sha256()
    with resolve(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(HASH_CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def git_info() -> dict[str, Any]:
    """Current commit and whether there are uncommitted changes. Unknown outside a git checkout."""

    def run(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args], cwd=ml_root(), capture_output=True, text=True, timeout=10, check=True
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout.strip()

    commit = run("rev-parse", "HEAD")
    status = run("status", "--porcelain")
    return {"commit": commit, "dirty": bool(status) if status is not None else None}


def hardware_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or None,
        "cpu_count": os.cpu_count(),
        "python": sys.version.split()[0],
    }
    try:
        import torch
    except ImportError:
        return info
    info["torch"] = torch.__version__
    info["cuda_available"] = torch.cuda.is_available()
    if torch.cuda.is_available():
        info["cuda"] = torch.version.cuda
        info["gpu"] = torch.cuda.get_device_name(0)
        info["gpu_count"] = torch.cuda.device_count()
    return info


def collect_run_metadata(config: AdvisorConfig, data_files: list[str | Path] = ()) -> dict[str, Any]:
    return {
        "package_version": __version__,
        "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "config": config.to_dict(),
        "config_fingerprint": config.fingerprint(),
        "data_hashes": {Path(p).as_posix(): file_sha256(p) for p in data_files},
        "git": git_info(),
        "hardware": hardware_info(),
    }


def result_path(config: AdvisorConfig, seed: int) -> Path:
    return resolve(config.results_dir) / config.experiment / config.condition / f"{seed}.json"


def write_run_record(
    config: AdvisorConfig,
    seed: int,
    metrics: dict[str, Any],
    data_files: list[str | Path] = (),
    *,
    overwrite: bool = False,
) -> Path:
    """Writes the run record and returns its path.

    Refuses to replace an existing record unless overwrite=True, so a finished result is never lost
    by accident.
    """
    path = result_path(config, seed)
    if path.exists() and not overwrite:
        raise FileExistsError(f"{path} already exists; pass overwrite=True to replace it")
    record = {"seed": seed, "metrics": metrics, "metadata": collect_run_metadata(config, data_files)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
