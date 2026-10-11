"""Experiment configuration: YAML files loaded into typed dataclasses.

- configs/base.yaml holds every default used in the papers.
- An experiment file starts with `extends: <path>` and only lists what it changes.
- Single values can be overridden on the command line as dotted keys: train.epochs=1.
Loading is strict, like the backend's Pydantic schemas: an unknown key or a wrong type is an error,
so a typo in a config can never silently fall back to a default.
"""

import dataclasses
import hashlib
import json
import types
import typing
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from athena_advisor.paths import resolve

SPECIALISTS = ["blueprint", "code", "checker", "deploy", "eva"]
SPLITS = ["train", "val_tune", "val_cal", "test"]


@dataclass
class DataConfig:
    raw_dir: str = "data/raw/stacksample"
    processed_dir: str = "data/processed"
    tag_map: str = "configs/tag_map.yaml"
    # Model input is the title plus the first N words of the body's prose (code removed).
    body_prose_words: int = 64
    max_length: int = 128
    # Chronological split by CreationDate into SPLITS (oldest to newest): train, val_tune, val_cal, test.
    split_fractions: list[float] = field(default_factory=lambda: [0.80, 0.07, 0.06, 0.07])
    # Only read the first N questions of the file, for quick runs. None reads everything.
    sample_size: int | None = None
    # The train split is randomly sampled down to this many questions; validation and test stay complete.
    train_max: int | None = 300000
    sample_seed: int = 0
    # The StackSample CSV files are Latin-1 encoded.
    csv_encoding: str = "latin-1"
    chunk_size: int = 100000


@dataclass
class ModelConfig:
    encoder: str = "sentence-transformers/all-MiniLM-L6-v2"
    specialists: list[str] = field(default_factory=lambda: list(SPECIALISTS))
    # Plain-English description per specialist, used to initialise the label-attention queries.
    specialists_file: str = "configs/specialists.yaml"
    dropout: float = 0.1
    context_hidden: int = 64
    # Each component can be switched off for the ablation study.
    use_film: bool = True
    use_label_attention: bool = True
    use_coactivation: bool = True
    coactivation_pmi_scale: float = 0.1
    coactivation_l2: float = 0.001


@dataclass
class LossConfig:
    focal_gamma: float = 2.0
    # Total loss = focal BCE (team) + lead_weight * CE (lead) + contrastive_weight * supervised contrastive.
    lead_weight: float = 1.0
    use_contrastive: bool = True
    contrastive_weight: float = 0.1
    contrastive_temperature: float = 0.07


@dataclass
class TrainConfig:
    seeds: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])
    batch_size: int = 32
    epochs: int = 3
    encoder_learning_rate: float = 2.0e-5
    head_learning_rate: float = 1.0e-3
    weight_decay: float = 0.01
    warmup_ratio: float = 0.1
    # "auto" picks the GPU when there is one.
    device: str = "auto"
    # Slower but bit-for-bit repeatable GPU runs.
    deterministic: bool = False


@dataclass
class BenchmarksConfig:
    raw_dir: str = "data/raw/benchmarks"
    processed_dir: str = "data/processed/benchmarks"
    # NLBSE has no official dev split: one is cut from the official train split with this seed.
    nlbse_dev_fraction: float = 0.1
    # The official NLBSE train file has about 720k issues; it is sampled down to this many before the
    # dev split is cut. The official test split always stays complete.
    nlbse_train_max: int | None = 200000
    seed: int = 0


@dataclass
class BaselinesConfig:
    tfidf_min_df: int = 2
    tfidf_max_features: int = 200000
    # SetFit is a few-shot method: it trains on a small, seeded, stratified sample of train.
    setfit_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    setfit_train_max: int = 2000
    setfit_num_iterations: int = 20
    setfit_epochs: int = 1
    setfit_batch_size: int = 16
    # Probability threshold that turns team probabilities into labels in the baseline run records.
    report_threshold: float = 0.5


@dataclass
class DecisionConfig:
    use_temperature_scaling: bool = True
    use_conformal: bool = True
    conformal_coverage: float = 0.9
    # Used instead of conformal prediction and cost-aware selection in the ablations.
    fixed_threshold: float = 0.5
    use_cost_aware: bool = True
    max_team_size: int = 4
    # Lambda per learning level: a higher value means fewer specialists are called.
    lambdas: dict[str, float] = field(default_factory=lambda: {"learner": 0.2, "builder": 0.5, "fast": 1.0})
    # Fallback relative cost per specialist when agent_runs has no history yet.
    default_costs: dict[str, float] = field(
        default_factory=lambda: {"blueprint": 1.0, "code": 2.0, "checker": 0.2, "deploy": 1.0, "eva": 1.5}
    )


@dataclass
class AdvisorConfig:
    experiment: str = "base"
    condition: str = "full"
    results_dir: str = "results"
    data: DataConfig = field(default_factory=DataConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    loss: LossConfig = field(default_factory=LossConfig)
    train: TrainConfig = field(default_factory=TrainConfig)
    decision: DecisionConfig = field(default_factory=DecisionConfig)
    benchmarks: BenchmarksConfig = field(default_factory=BenchmarksConfig)
    baselines: BaselinesConfig = field(default_factory=BaselinesConfig)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def fingerprint(self) -> str:
        """Short hash of the resolved config, to tell runs apart."""
        blob = json.dumps(self.to_dict(), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:12]


class ConfigError(ValueError):
    """A config file or override does not match the dataclasses."""


# ---------------------------------------------------------------- loading


def load_config(path: str | Path | None = None, overrides: list[str] | tuple[str, ...] = ()) -> AdvisorConfig:
    """Loads a YAML config (following `extends`), applies dotted overrides, and validates the result."""
    data = _read_with_extends(resolve(path), seen=()) if path is not None else {}
    for override in overrides:
        _apply_override(data, override)
    return _build(AdvisorConfig, data, "config")


def _read_with_extends(path: Path, seen: tuple[Path, ...]) -> dict[str, Any]:
    if path in seen:
        raise ConfigError(f"Circular extends: {' -> '.join(str(p) for p in (*seen, path))}")
    if not path.is_file():
        raise ConfigError(f"Config file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")
    parent = data.pop("extends", None)
    if parent is None:
        return data
    base = _read_with_extends((path.parent / parent).resolve(), (*seen, path))
    return _deep_merge(base, data)


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Nested mappings merge key by key; anything else in `update` replaces the base value."""
    merged = dict(base)
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _apply_override(data: dict[str, Any], override: str) -> None:
    """`train.epochs=1` sets data["train"]["epochs"] = 1. The value is parsed as YAML."""
    key, sep, raw = override.partition("=")
    if not sep or not key.strip():
        raise ConfigError(f"Override must look like section.key=value, got {override!r}")
    *parents, leaf = key.strip().split(".")
    node = data
    for part in parents:
        node = node.setdefault(part, {})
        if not isinstance(node, dict):
            raise ConfigError(f"Cannot set {key}: {part} is not a section")
    node[leaf] = yaml.safe_load(raw)


def _build(cls: type, data: Any, where: str) -> Any:
    if not isinstance(data, dict):
        raise ConfigError(f"{where} must be a mapping")
    hints = typing.get_type_hints(cls)
    names = {f.name for f in dataclasses.fields(cls)}
    unknown = sorted(set(data) - names)
    if unknown:
        raise ConfigError(f"Unknown key(s) in {where}: {', '.join(unknown)}")
    values = {name: _coerce(value, hints[name], f"{where}.{name}") for name, value in data.items()}
    return cls(**values)


def _coerce(value: Any, tp: Any, where: str) -> Any:
    if dataclasses.is_dataclass(tp):
        return _build(tp, value, where)
    origin, args = typing.get_origin(tp), typing.get_args(tp)
    if origin in (typing.Union, types.UnionType):
        if value is None and type(None) in args:
            return None
        inner = [a for a in args if a is not type(None)]
        return _coerce(value, inner[0], where)
    if origin is list:
        if not isinstance(value, list):
            raise ConfigError(f"{where} must be a list")
        return [_coerce(v, args[0], f"{where}[{i}]") for i, v in enumerate(value)]
    if origin is dict:
        if not isinstance(value, dict):
            raise ConfigError(f"{where} must be a mapping")
        return {_coerce(k, args[0], where): _coerce(v, args[1], f"{where}.{k}") for k, v in value.items()}
    if tp is bool:
        if not isinstance(value, bool):
            raise ConfigError(f"{where} must be true or false")
        return value
    if tp is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ConfigError(f"{where} must be a whole number")
        return value
    if tp is float:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ConfigError(f"{where} must be a number")
        return float(value)
    if tp is str:
        if not isinstance(value, str):
            raise ConfigError(f"{where} must be text")
        return value
    raise ConfigError(f"{where}: unsupported type {tp}")
