"""Trains the Advisor model on one dataset for one seed, then writes predictions and a run record.

Training:
- AdamW with two learning rates: a small one for the pretrained encoder (train.encoder_learning_rate) and a
  larger one for the new layers (train.head_learning_rate). Biases and normalisation weights get no
  weight decay.
- Linear warmup over train.warmup_ratio of all steps, then linear decay to 0.
- Mixed precision (float16 autocast with loss scaling) on GPU; full precision on CPU.
- Gradients are clipped to train.max_grad_norm.
- After every epoch: macro F1 on val_tune, one row in train_log.csv, and a checkpoint (last.pt). The best
  epoch so far is also kept as best.pt. Training stops early after train.early_stopping_patience epochs
  without improvement.
- If last.pt exists, training resumes from it: model, optimizer, scheduler, loss scaler, early-stopping
  state and random number generator states are all restored, so the result matches an uninterrupted run.
Afterwards the best checkpoint is loaded and predictions are written for val_tune, val_cal and test.

Files:
    results/runs/<experiment>/<condition>/<dataset>/seed_<seed>/   last.pt, best.pt, train_log.csv
    results/predictions/advisor_<condition>/<dataset>/<split>/<seed>.npz
    results/<experiment>_<dataset>/<condition>/<seed>.json            run record with metrics
"""

import csv
import math
import random
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import nn

from athena_advisor.config import AdvisorConfig
from athena_advisor.eval import metrics as m
from athena_advisor.eval.data import LabelledSplit
from athena_advisor.eval.predictions import Predictions, predictions_path
from athena_advisor.eval.report import dataset_metrics
from athena_advisor.eval.splits import EVAL_SPLITS, MODES, dataset_folder
from athena_advisor.losses import MultiTaskLoss
from athena_advisor.model.advisor import AdvisorModel
from athena_advisor.paths import resolve
from athena_advisor.run_metadata import write_run_record
from athena_advisor.train.data import make_loader

LOG_FIELDS = [
    "epoch",
    "train_loss",
    "val_macro_f1",
    "val_micro_f1",
    "lr_encoder",
    "lr_head",
    "seconds",
    "best",
]


@dataclass
class TrainState:
    epoch: int = 0  # epochs finished
    best_metric: float = -math.inf
    best_epoch: int = -1
    bad_epochs: int = 0  # epochs since the last improvement


@dataclass
class TrainResult:
    state: TrainState
    record: Path
    predictions: dict[str, Path]
    log: Path


def model_name(config: AdvisorConfig) -> str:
    return f"advisor_{config.condition}"


def run_dir(config: AdvisorConfig, dataset: str, seed: int) -> Path:
    return (
        resolve(config.results_dir) / "runs" / config.experiment / config.condition / dataset / f"seed_{seed}"
    )


def pick_device(name: str) -> torch.device:
    if name == "auto":
        return torch.device("cuda" if torch.cuda.is_available() else "cpu")
    return torch.device(name)


class Trainer:
    def __init__(
        self,
        config: AdvisorConfig,
        dataset: str,
        seed: int,
        model: AdvisorModel,
        tokenizer,  # type: ignore[no-untyped-def]
        splits: dict[str, LabelledSplit],
    ) -> None:
        self.config, self.dataset, self.seed = config, dataset, seed
        self.mode = MODES[dataset]
        self.splits = splits
        self.tokenizer = tokenizer
        self.device = pick_device(config.train.device)
        self.model = model.to(self.device)
        self.out_dir = run_dir(config, dataset, seed)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = self.out_dir / "train_log.csv"
        self.use_amp = self.device.type == "cuda"

        train = config.train
        self.optimizer = torch.optim.AdamW(self._parameter_groups(), weight_decay=train.weight_decay)
        steps_per_epoch = math.ceil(len(splits["train"]) / train.batch_size)
        total_steps = max(1, steps_per_epoch * train.epochs)
        warmup_steps = int(train.warmup_ratio * total_steps)

        def schedule(step: int) -> float:
            # Linear warmup to the full learning rate, then linear decay to 0 at the last step.
            if step < warmup_steps:
                return (step + 1) / max(1, warmup_steps)
            return max(0.0, (total_steps - step) / max(1, total_steps - warmup_steps))

        self.scheduler = torch.optim.lr_scheduler.LambdaLR(self.optimizer, schedule)
        self.scaler = torch.amp.GradScaler("cuda", enabled=self.use_amp)
        self.loss_fn = MultiTaskLoss(config.loss, self.mode)
        self.state = TrainState()

    # ------------------------------------------------------------ setup

    def _parameter_groups(self) -> list[dict[str, Any]]:
        train = self.config.train
        groups: dict[tuple[bool, bool], list[nn.Parameter]] = {}
        for name, param in self.model.named_parameters():
            if not param.requires_grad:
                continue
            is_encoder = name.startswith("encoder.")
            no_decay = name.endswith("bias") or "LayerNorm" in name or "norm" in name.lower()
            groups.setdefault((is_encoder, no_decay), []).append(param)
        return [
            {
                "params": params,
                "lr": train.encoder_learning_rate if is_encoder else train.head_learning_rate,
                "weight_decay": 0.0 if no_decay else train.weight_decay,
                "name": "encoder" if is_encoder else "head",
            }
            for (is_encoder, no_decay), params in groups.items()
        ]

    def _learning_rates(self) -> tuple[float, float]:
        rates = {group["name"]: group["lr"] for group in self.optimizer.param_groups}
        return rates.get("encoder", 0.0), rates.get("head", 0.0)

    # ------------------------------------------------------------ checkpoints

    def _save_last(self) -> None:
        torch.save(
            {
                "model": self.model.state_dict(),
                "optimizer": self.optimizer.state_dict(),
                "scheduler": self.scheduler.state_dict(),
                "scaler": self.scaler.state_dict(),
                "state": asdict(self.state),
                "rng": {
                    "torch": torch.get_rng_state(),
                    "cuda": torch.cuda.get_rng_state_all() if torch.cuda.is_available() else [],
                    "numpy": np.random.get_state(),
                    "python": random.getstate(),
                },
            },
            self.out_dir / "last.pt",
        )

    def _resume(self) -> bool:
        path = self.out_dir / "last.pt"
        if not path.exists():
            return False
        # Our own checkpoint (it holds optimizer state and RNG states, not just tensors).
        checkpoint = torch.load(path, map_location=self.device, weights_only=False)
        self.model.load_state_dict(checkpoint["model"])
        self.optimizer.load_state_dict(checkpoint["optimizer"])
        self.scheduler.load_state_dict(checkpoint["scheduler"])
        self.scaler.load_state_dict(checkpoint["scaler"])
        self.state = TrainState(**checkpoint["state"])
        rng = checkpoint["rng"]
        torch.set_rng_state(rng["torch"])
        if rng["cuda"]:
            torch.cuda.set_rng_state_all(rng["cuda"])
        np.random.set_state(rng["numpy"])
        random.setstate(rng["python"])
        return True

    # ------------------------------------------------------------ training

    def _train_epoch(self, epoch: int) -> float:
        train = self.config.train
        # The shuffle order depends only on the seed and the epoch, so a resumed run sees the same order.
        loader = make_loader(
            self.splits["train"],
            self.tokenizer,
            self.config.data.max_length,
            train.batch_size,
            shuffle=True,
            seed=self.seed * 10_007 + epoch,
        )
        self.model.train()
        total, batches = 0.0, 0
        for batch in loader:
            batch = batch.to(self.device)
            self.optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=self.device.type, dtype=torch.float16, enabled=self.use_amp):
                output = self.model(batch.input_ids, batch.attention_mask, batch.context)
                loss = self.loss_fn(output, batch.team, batch.lead).total
            self.scaler.scale(loss).backward()
            self.scaler.unscale_(self.optimizer)
            nn.utils.clip_grad_norm_(self.model.parameters(), train.max_grad_norm)
            self.scaler.step(self.optimizer)
            self.scaler.update()
            self.scheduler.step()
            total += float(loss.detach())
            batches += 1
        return total / max(1, batches)

    @torch.no_grad()
    def predict(self, split: LabelledSplit) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Team probabilities, lead probabilities and per-item latency (ms) for a split, in row order."""
        loader = make_loader(
            split,
            self.tokenizer,
            self.config.data.max_length,
            self.config.train.eval_batch_size,
            shuffle=False,
        )
        self.model.eval()
        k = len(split.labels)
        team, lead = np.zeros((len(split), k), np.float32), np.zeros((len(split), k), np.float32)
        latency = np.zeros(len(split), np.float32)
        for batch in loader:
            start = time.perf_counter()
            batch = batch.to(self.device)
            with torch.autocast(device_type=self.device.type, dtype=torch.float16, enabled=self.use_amp):
                output = self.model(batch.input_ids, batch.attention_mask, batch.context)
            rows = batch.rows.cpu().numpy()
            team[rows] = self.model.team_probs(output).float().cpu().numpy()
            lead[rows] = self.model.lead_probs(output).float().cpu().numpy()
            latency[rows] = (time.perf_counter() - start) * 1000 / len(rows)
        return team, lead, latency

    def validation_scores(self) -> tuple[float, float]:
        """(macro F1, micro F1) on val_tune: the early-stopping metric."""
        split = self.splits["val_tune"]
        team, lead, _ = self.predict(split)
        if self.mode == "singlelabel":
            rows = split.has_lead  # out-of-scope rows have no label to score
            scores = m.single_label_f1(split.lead[rows], m.single_label_predictions(lead[rows]), split.labels)
            return scores["macro_f1"], scores["micro_f1"]
        predicted = m.threshold(team, self.config.baselines.report_threshold)
        return m.macro_f1(split.team, predicted), m.micro_f1(split.team, predicted)

    def _log(self, row: dict[str, Any]) -> None:
        new = not self.log_path.exists()
        with self.log_path.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS)
            if new:
                writer.writeheader()
            writer.writerow(row)

    def fit(self, stop_after: int | None = None) -> TrainState:
        """Trains until the configured epochs or early stopping. stop_after ends this call after that many
        epochs (to fit a time limit); a later call resumes from last.pt."""
        resumed = self._resume()
        if resumed:
            print(f"Resumed from epoch {self.state.epoch}")
        epochs_this_call = 0
        train = self.config.train
        while self.state.epoch < train.epochs and self.state.bad_epochs < train.early_stopping_patience:
            if stop_after is not None and epochs_this_call >= stop_after:
                break
            start = time.perf_counter()
            epoch = self.state.epoch
            lr_encoder, lr_head = self._learning_rates()
            train_loss = self._train_epoch(epoch)
            macro, micro = self.validation_scores()
            self.state.epoch += 1
            improved = macro > self.state.best_metric
            if improved:
                self.state.best_metric, self.state.best_epoch, self.state.bad_epochs = macro, epoch, 0
                torch.save(self.model.state_dict(), self.out_dir / "best.pt")
            else:
                self.state.bad_epochs += 1
            self._log(
                {
                    "epoch": epoch,
                    "train_loss": round(train_loss, 6),
                    "val_macro_f1": round(macro, 6),
                    "val_micro_f1": round(micro, 6),
                    "lr_encoder": lr_encoder,
                    "lr_head": lr_head,
                    "seconds": round(time.perf_counter() - start, 2),
                    "best": int(improved),
                }
            )
            self._save_last()
            epochs_this_call += 1
        return self.state

    @property
    def finished(self) -> bool:
        train = self.config.train
        return self.state.epoch >= train.epochs or self.state.bad_epochs >= train.early_stopping_patience

    # ------------------------------------------------------------ outputs

    def write_outputs(self) -> TrainResult:
        """Loads the best checkpoint, writes predictions for the evaluation splits and the run record."""
        best = torch.load(self.out_dir / "best.pt", map_location=self.device, weights_only=True)
        self.model.load_state_dict(best)
        config = self.config
        name = model_name(config)
        paths: dict[str, Path] = {}
        metrics: dict[str, Any] = {
            "training": {
                **asdict(self.state),
                "train_rows": len(self.splits["train"]),
                "mode": self.mode,
                "parameters": sum(p.numel() for p in self.model.parameters()),
                "device": self.device.type,
                "mixed_precision": self.use_amp,
            }
        }
        for split in EVAL_SPLITS:
            team, lead, latency = self.predict(self.splits[split])
            predictions = Predictions(
                ids=self.splits[split].ids,
                labels=self.splits[split].labels,
                team_probs=team,
                lead_probs=lead,
                latency_ms=latency,
                meta={
                    "model": name,
                    "dataset": self.dataset,
                    "split": split,
                    "seed": self.seed,
                    "best_epoch": self.state.best_epoch,
                    "latency": f"batch time divided evenly over the rows, {self.device.type}",
                },
            )
            paths[split] = predictions.save(
                predictions_path(config.results_dir, name, self.dataset, split, self.seed)
            )
            metrics[split] = dataset_metrics(
                self.dataset, self.splits[split], predictions, config.baselines.report_threshold
            )
        record_config = replace(config, experiment=f"{config.experiment}_{self.dataset}")
        data_files = sorted(dataset_folder(config, self.dataset).glob("*.parquet"))
        record = write_run_record(record_config, self.seed, metrics, data_files, overwrite=True)
        return TrainResult(state=self.state, record=record, predictions=paths, log=self.log_path)


def train_run(
    config: AdvisorConfig,
    dataset: str,
    seed: int,
    *,
    tokenizer=None,  # type: ignore[no-untyped-def]
    encoder_model: nn.Module | None = None,
    stop_after: int | None = None,
) -> TrainResult | None:
    """Builds the model and trains it. Returns None when stopped early by stop_after (resume later)."""
    from athena_advisor.eval.splits import load_dataset
    from athena_advisor.model.advisor import build_model
    from athena_advisor.seed import set_seed

    if tokenizer is None:
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(config.model.encoder)
    set_seed(seed, deterministic=config.train.deterministic)
    splits = load_dataset(config, dataset)
    model = build_model(
        config,
        splits["train"].labels,
        MODES[dataset],
        tokenizer=tokenizer,
        encoder_model=encoder_model,
        train_team=splits["train"].team,
    )
    trainer = Trainer(config, dataset, seed, model, tokenizer, splits)
    trainer.fit(stop_after=stop_after)
    if not trainer.finished:
        return None
    return trainer.write_outputs()
