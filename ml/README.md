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

Copy the `results/` files back into the repo and commit them.

## How to run on Kaggle

The notebooks in `notebooks/` only call the scripts; all logic is in the package.

**Prepare the data** with `notebooks/01_prepare_data.ipynb`:

1. On kaggle.com, create a notebook and import `notebooks/01_prepare_data.ipynb` (File, then Import Notebook).
2. In the right-hand panel: turn **Internet** on, and under **Input** add the dataset `stackoverflow/stacksample`.
   No accelerator is needed for this notebook.
3. If the GitHub repository is private, add a secret named `GITHUB_TOKEN` (Add-ons, then Secrets) with read
   access to it. The notebook removes the token from the saved git remote and never prints it.
4. Run all cells. The notebook:
   - prints the Python version and GPU,
   - clones the repository and installs the package with `pip install -e ml --no-deps` (Kaggle's GPU build
     of PyTorch stays in place), plus `setfit optimum onnx onnxruntime`,
   - sets `ATHENA_ML_ROOT` and runs `scripts/check_environment.py`,
   - builds StackSample with `scripts/build_stacksample.py --input-root /kaggle/input` (it finds the
     attached files on its own),
   - downloads and converts the benchmarks with `scripts/download_benchmarks.py`,
   - prints the counts (`scripts/summarize_data.py`) and every data card,
   - writes `/kaggle/working/athena_data.zip` with `data/processed/` inside.
5. Download the zip from the Output panel, or attach this notebook's output to the training notebook.
   Unzip it inside `ml/` to get the same layout.

## Commands (laptop, Windows)

Run everything from inside `ml/`.

```bash
python -m uv sync                          # create .venv with Python 3.12 and install everything
python -m uv run pytest                    # unit tests (tiny fixtures only, a few seconds)
python -m uv run ruff check .              # lint
python -m uv run ruff format .             # format

# Build the dataset from the tiny fixtures (writes data/processed/fixture, including DATA_CARD.md)
python -m uv run python scripts/build_stacksample.py --fixture

# Convert the benchmark fixtures (writes data/processed/benchmarks_fixture, one DATA_CARD.md per dataset)
python -m uv run python scripts/download_benchmarks.py --fixture

# Show the fully resolved config for an experiment, with optional dotted overrides
python -m uv run python scripts/show_config.py configs/experiments/smoke.yaml
python -m uv run python scripts/show_config.py configs/experiments/ablation_no_film.yaml --set train.epochs=1
```

On Kaggle, with the StackSample dataset attached to the notebook:

```bash
python scripts/build_stacksample.py --raw-dir /kaggle/input/stacksample --out data/processed/stacksample
```

## Dataset pipeline (`src/athena_advisor/data/`)

| Module | What it does |
| --- | --- |
| `labels.py` | Team and lead from the question's tags through `configs/tag_map.yaml` (299 tags). Specific tags decide the lead before generic ones; ties go to checker, deploy, eva, blueprint, code. Questions with no mapped tag are dropped. |
| `text.py` | Model input: title plus the first 64 words of the body prose, with HTML and all code removed. Never sees tags. |
| `context.py` | `ContextSchema`: 16 fields read from the body with documented regex rules, encoded as a 43-value float32 vector (a `present` flag, then the fields; categories one-hot). `from_athena_state()` is planned. |
| `build.py` | Two chunked passes over `Questions.csv` and `Tags.csv`: labels and dates first, then text and context for the selected questions. Chronological train / val_tune / val_cal / test, train sampled to `data.train_max` with seed 0. One parquet file per split, a `.sha256` file for each, and `build_info.json`. |
| `data_card.py` | `DATA_CARD.md`: source, licence wording, filters, counts per split, specialist and lead, co-occurrence, context feature rates and the full tag map. |

The same input and config always give byte-identical parquet files (rows are sorted by date, then id).

## Public benchmarks (`src/athena_advisor/data/benchmarks/`)

On Kaggle (internet on), download and convert all four with `python scripts/download_benchmarks.py`
(`--only clinc150 nlbse` for a subset). Each dataset becomes `train.parquet`, `dev.parquet` and `test.parquet`
in one common format (`id`, `text`, `labels`, `lead`, `out_of_scope`, `split`), each with a `.sha256` file,
plus `info.json` and a `DATA_CARD.md` with the exact source, version, licence and citation.

| Dataset | Source (pinned) | Splits | Notes |
| --- | --- | --- | --- |
| MixATIS, MixSNIPS | AGIF repository, commit `6a4b26b`, `data/Mix*_clean/` | official train, dev, test | Intents only, split on `#`; no lead for multi-intent rows |
| CLINC150 | `clinc/oos-eval`, commit `828f809`, `data/data_full.json` | official train, val (as dev), test | Out-of-scope rows: `out_of_scope = true`, no labels |
| NLBSE'22 | Ticket Tagger storage, `github-labels-top3-803k-*.tar.gz` | official train and test; dev cut from train | Train sampled to `benchmarks.nlbse_train_max` (seed 0); test complete |

Source lookups (URLs, licences, citations) live in `sources.py` and were checked against the official pages.

## Evaluation (`src/athena_advisor/eval/`) and baselines (`src/athena_advisor/baselines/`)

| Module | What it does |
| --- | --- |
| `eval/predictions.py` | The one saved predictions format: `results/predictions/<model>/<dataset>/<split>/<seed>.npz` with ids, label list, team and lead probabilities (n x K), latency per item and run metadata. Calibration, conformal prediction, decisions and metrics only read these files, so nothing is retrained to try a new rule. |
| `eval/data.py` | Any split as arrays: ids, texts, 0/1 team matrix, lead index (-1 when none), out-of-scope flags. Benchmarks use every label from all their splits. |
| `eval/metrics.py` | Micro, macro and samples F1, exact match, Hamming loss, per-label precision, recall and F1, lead accuracy (rows with a lead only, count reported), team and lead ECE (15 bins), intent accuracy (MixATIS, MixSNIPS), in-scope accuracy and out-of-scope recall (CLINC150), micro and macro F1 (NLBSE). |
| `eval/stats.py` | Seeded bootstrap 95% intervals (1000 resamples), paired bootstrap for F1 differences, McNemar for lead accuracy, mean and standard deviation across seeds. |
| `baselines/` | `prior` (train label frequencies), `keyword` (StackSample only: tag names found in the text, labelled like the gold data; raises `NotApplicable` on benchmarks), `tfidf_lr` (TF-IDF 1-2 grams; one-vs-rest logistic regression for multi-label data, multinomial for the lead and for single-label data). |

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
