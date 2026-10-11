# Athena Advisor (ml/)

The model that decides, for each student message or platform event, which specialists work on it
(blueprint, code, checker, deploy, eva), which one leads, and whether to ask a clarifying question first.
This folder is its own Python project, separate from `server/`. The server never imports PyTorch: it will only
load the exported ONNX model.

## Folders

| Path | What |
| --- | --- |
| `src/athena_advisor/` | The installable package: config system, seeding, run records (model and data code come next) |
| `configs/base.yaml` | Every default setting used in the papers |
| `configs/experiments/` | One file per experiment or condition; each `extends` the base and lists only what changes |
| `data/raw/`, `data/processed/` | Datasets and derived splits. Never committed (see `.gitignore`) |
| `notebooks/` | Kaggle notebooks that run training and evaluation on GPU |
| `scripts/` | Command-line entry points |
| `tests/` | Unit tests; `tests/fixtures/` holds tiny hand-made samples in the real file formats |
| `results/` | One JSON record per run: `results/<experiment>/<condition>/<seed>.json`. Committed (small files) |

## Laptop vs Kaggle

| Laptop (CPU) | Kaggle (GPU) |
| --- | --- |
| Write code, run unit tests on the tiny fixtures | Download StackSample and the benchmarks |
| `smoke` config only, if anything trains at all | Full training: every condition, 5 seeds |
| Never loads the full dataset | Writes `results/` JSON files and the exported ONNX model |

On Kaggle, clone the repo, then inside `ml/`:

```bash
pip install -e . --no-deps        # Kaggle already has a GPU build of PyTorch; keep it
pip install setfit optimum        # anything Kaggle is missing
export ATHENA_ML_ROOT=$(pwd)      # so relative paths in configs resolve to this folder
```

Copy the `results/` files back into the repo and commit them.

## Commands (laptop, Windows)

Run everything from inside `ml/`.

```bash
python -m uv sync                          # create .venv with Python 3.12 and install everything
python -m uv run pytest                    # unit tests (tiny fixtures only, a few seconds)
python -m uv run ruff check .              # lint
python -m uv run ruff format .             # format

# Show the fully resolved config for an experiment, with optional dotted overrides
python -m uv run python scripts/show_config.py configs/experiments/smoke.yaml
python -m uv run python scripts/show_config.py configs/experiments/ablation_no_film.yaml --set train.epochs=1
```

## Configs

- Loading is strict: an unknown key or a wrong type stops the run with a clear message, so a typo can never
  silently fall back to a default.
- `extends: ../base.yaml` merges section by section; lists are replaced, not appended.
- `--set section.key=value` overrides one value; the value is read as YAML (`true`, `0.5`, `[0, 1]`).
- `experiment` and `condition` decide where results go. Ablations share `experiment: ablations` and differ by
  `condition`.

## Run records

`write_run_record(config, seed, metrics, data_files)` writes `results/<experiment>/<condition>/<seed>.json` with:

- the metrics and the seed,
- the full resolved config and a short fingerprint of it,
- the SHA-256 of every data file used (so test splits can be proven unchanged),
- the git commit and whether there were uncommitted changes,
- the hardware (CPU, GPU, PyTorch and CUDA versions) and a UTC timestamp.

It refuses to overwrite an existing record unless `overwrite=True`.

## Rules

- Public, human-labelled data only. Labels come from Stack Overflow tags through `configs/tag_map.yaml`; tags are
  never model input.
- Test splits are created once, saved with a hash, and used only for final runs.
- 5 seeds per trained condition; report mean and standard deviation with 95% bootstrap intervals.
