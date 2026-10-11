"""Public human-labelled benchmarks in one common format: MixATIS, MixSNIPS, CLINC150 and NLBSE'22."""

import urllib.request
from pathlib import Path
from typing import Any

from athena_advisor.config import BenchmarksConfig
from athena_advisor.data.benchmarks import clinc, mix_intent, nlbse
from athena_advisor.data.benchmarks.common import Conversion, write_benchmark
from athena_advisor.data.benchmarks.sources import SOURCES

DATASETS = ("mixatis", "mixsnips", "clinc150", "nlbse")


def convert_dataset(dataset: str, raw_dir: Path, config: BenchmarksConfig) -> Conversion:
    """Converts one dataset from the source files in raw_dir/<dataset>/."""
    folder = raw_dir / dataset
    if dataset in ("mixatis", "mixsnips"):
        return mix_intent.convert(dataset, folder)
    if dataset == "clinc150":
        return clinc.convert(folder)
    if dataset == "nlbse":
        return nlbse.convert(folder, config)
    raise ValueError(f"Unknown dataset {dataset!r}; choose from {DATASETS}")


def build_benchmarks(
    raw_dir: Path, out_dir: Path, config: BenchmarksConfig, datasets: tuple[str, ...] = DATASETS
) -> dict[str, Any]:
    return {name: write_benchmark(convert_dataset(name, raw_dir, config), out_dir) for name in datasets}


def download(dataset: str, raw_dir: Path) -> list[Path]:
    """Downloads a dataset's official files into raw_dir/<dataset>/, skipping files already there."""
    folder = raw_dir / dataset
    folder.mkdir(parents=True, exist_ok=True)
    paths = []
    for name, url in SOURCES[dataset].files.items():
        path = folder / name
        if not path.exists():
            partial = path.with_name(path.name + ".part")
            # Download to a temporary name first, so an interrupted download never looks complete.
            with urllib.request.urlopen(url, timeout=120) as response, partial.open("wb") as out:
                while chunk := response.read(1 << 20):
                    out.write(chunk)
            partial.replace(path)
        paths.append(path)
    return paths
