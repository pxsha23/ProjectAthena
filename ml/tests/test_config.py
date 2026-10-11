from pathlib import Path

import pytest

from athena_advisor.config import SPECIALISTS, AdvisorConfig, ConfigError, load_config


def test_base_yaml_matches_the_dataclass_defaults() -> None:
    # The base file documents every default; it must never drift from the code.
    assert load_config("configs/base.yaml") == AdvisorConfig()


def test_experiment_extends_base_and_overrides_only_what_it_lists() -> None:
    config = load_config("configs/experiments/smoke.yaml")
    assert config.experiment == "smoke"
    assert (config.data.sample_size, config.train.seeds, config.train.epochs) == (200, [0], 1)
    # Untouched values come from the base file.
    assert config.train.encoder_learning_rate == 2.0e-5
    assert config.model.specialists == SPECIALISTS


def test_ablation_config() -> None:
    config = load_config("configs/experiments/no_film.yaml")
    assert (config.experiment, config.condition, config.model.use_film) == ("ablations", "no_film", False)
    assert config.model.use_label_attention is True


def test_dotted_overrides_are_parsed_as_yaml() -> None:
    config = load_config(
        "configs/experiments/smoke.yaml",
        ["train.epochs=4", "train.seeds=[1, 2]", "data.sample_size=null", "decision.lambdas.fast=2"],
    )
    assert config.train.epochs == 4 and config.train.seeds == [1, 2]
    assert config.data.sample_size is None
    assert config.decision.lambdas == {"learner": 0.2, "builder": 0.5, "fast": 2.0}


def test_ints_are_accepted_where_floats_are_expected() -> None:
    assert load_config(overrides=["loss.focal_gamma=3"]).loss.focal_gamma == 3.0


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ("train.epoch=2", "Unknown key"),
        ("trian.epochs=2", "Unknown key"),
        ("train.epochs=two", "whole number"),
        ("train.epochs=2.5", "whole number"),
        ("model.use_film=yes please", "true or false"),
        ("train.seeds=3", "must be a list"),
        ("loss.focal_gamma=true", "must be a number"),
        ("no_equals_sign", "section.key=value"),
    ],
)
def test_bad_values_are_rejected(override: str, message: str) -> None:
    with pytest.raises(ConfigError, match=message):
        load_config("configs/base.yaml", [override])


def test_missing_file_and_circular_extends(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")
    a, b = tmp_path / "a.yaml", tmp_path / "b.yaml"
    a.write_text("extends: b.yaml\n", encoding="utf-8")
    b.write_text("extends: a.yaml\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="Circular"):
        load_config(a)


def test_fingerprint_changes_with_the_config() -> None:
    base = load_config("configs/base.yaml")
    assert base.fingerprint() == AdvisorConfig().fingerprint()
    assert base.fingerprint() != load_config("configs/experiments/smoke.yaml").fingerprint()
