"""Moving data and results in and out of Kaggle notebooks.

Kaggle mounts every attached input read-only under /kaggle/input, at a depth that depends on the input
type. These helpers find what they need by content, not by path:
- processed data: the athena_data.zip written by notebook 01, or an already unzipped data/processed folder
  (recognised by stacksample/build_info.json or benchmarks/<name>/info.json);
- earlier results: any zip whose entries start with results/, or a results folder holding run records.
Everything is copied into the working ml/ folder, because inputs are read-only.
"""

import shutil
import zipfile
from pathlib import Path

DATA_ZIP_PREFIX = "data/processed/"
RESULTS_PREFIX = "results/"
# Checkpoints are large and only needed to resume a run inside one session, so they are never packed.
SKIPPED_SUFFIXES = (".pt",)


def _zips(root: Path) -> list[Path]:
    return sorted(root.rglob("*.zip"), key=lambda p: (len(p.parts), str(p)))


def _zip_has(path: Path, prefix: str) -> bool:
    try:
        with zipfile.ZipFile(path) as archive:
            return any(name.startswith(prefix) for name in archive.namelist())
    except zipfile.BadZipFile:
        return False


def find_processed_data(root: str | Path) -> Path | None:
    """The data zip, or the processed folder (the one holding stacksample/ or benchmarks/), under root."""
    root = Path(root)
    for path in _zips(root):
        if _zip_has(path, DATA_ZIP_PREFIX):
            return path
    markers = [*root.rglob("stacksample/build_info.json"), *root.rglob("benchmarks/*/info.json")]
    folders = sorted(
        {m.parent.parent if m.name == "build_info.json" else m.parent.parent.parent for m in markers},
        key=lambda p: (len(p.parts), str(p)),
    )
    return folders[0] if folders else None


def restore_data(root: str | Path, ml_dir: str | Path) -> Path:
    """Copies the processed data into ml_dir/data/processed and returns that folder."""
    source = find_processed_data(root)
    if source is None:
        raise FileNotFoundError(
            f"No processed data under {root}. Attach the output of notebook 01 (athena_data.zip) as an input."
        )
    target = Path(ml_dir) / "data" / "processed"
    if source.suffix == ".zip":
        with zipfile.ZipFile(source) as archive:
            members = [n for n in archive.namelist() if n.startswith(DATA_ZIP_PREFIX)]
            archive.extractall(Path(ml_dir), members=members)
    else:
        shutil.copytree(source, target, dirs_exist_ok=True)
    return target


def restore_results(root: str | Path, ml_dir: str | Path) -> int:
    """Copies earlier results (zips or folders) into ml_dir/results without overwriting anything.

    Returns the number of files restored. Run records already present are kept, so finished jobs stay
    finished and the sweep skips them.
    """
    root, ml_dir = Path(root), Path(ml_dir)
    restored = 0
    for path in _zips(root):
        if not _zip_has(path, RESULTS_PREFIX):
            continue
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                target = ml_dir / name
                if name.startswith(RESULTS_PREFIX) and not name.endswith("/") and not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(name))
                    restored += 1
    for folder in {p.parent for p in root.rglob("results/*") if p.parent.name == "results"}:
        for file in folder.rglob("*"):
            target = ml_dir / "results" / file.relative_to(folder)
            if file.is_file() and not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, target)
                restored += 1
    return restored


def pack_results(ml_dir: str | Path, out: str | Path) -> tuple[Path, int]:
    """Zips ml_dir/results (run records, predictions, training logs; no checkpoints) into `out`."""
    ml_dir, out = Path(ml_dir), Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file in sorted((ml_dir / "results").rglob("*")):
            if file.is_file() and not file.name.endswith(SKIPPED_SUFFIXES):
                archive.write(file, file.relative_to(ml_dir).as_posix())
                count += 1
    return out, count
