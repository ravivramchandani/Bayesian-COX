"""Deterministic complete clinical, information-regime and matched fit grid."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.data.survival_folds import repeated_survival_folds
from src.pipelines.confirmatory.options import MODEL_KEYS, deterministic_seed
from src.pipelines.extensions.fitting import CATALYTIC_MODELS, NEW_MODELS
from src.pipelines.robustness.conditions import stratified_training_subsets


@dataclass(frozen=True)
class ExtensionJob:
    """A unique attempted fit and its exact analysis-training membership."""

    cell_id: str
    dataset: str
    setting: str
    model: str
    repeat: int
    fold: int
    condition: str
    train: np.ndarray
    validation: np.ndarray
    censoring_cutoff: float | None
    gene_budget: int


def build_extension_jobs(
    datasets: dict[str, pd.DataFrame], config: dict[str, Any],
) -> list[ExtensionJob]:
    """Build 1625 distinct fits; RQ2 full anchors reuse 90 clinical fits."""
    jobs = []
    for key in ("gbsg2", "whas500", "metabric", "metabric_matched"):
        raw = datasets[key]
        times, events = raw.duration.to_numpy(float), raw.event.to_numpy(int)
        folds = repeated_survival_folds(times, events, n_splits=5, n_repeats=5,
                                       base_seed=config["base_seed"], max_time_bins=4)
        settings = ("clinical", "expression") if key == "metabric_matched" else ("clinical",)
        models = MODEL_KEYS + NEW_MODELS if key == "metabric_matched" else NEW_MODELS
        for fold in folds:
            for setting in settings:
                for model in models:
                    cell_id = f"{key}__{setting}__r{fold.repeat:02}f{fold.fold:02}__{model}__full"
                    jobs.append(ExtensionJob(cell_id, key, setting, model, fold.repeat, fold.fold,
                                             "full", fold.train_indices, fold.validation_indices, None,
                                             config["gene_budget"] if setting == "expression" else 0))
            if key != "metabric_matched" and fold.fold in (1, 2):
                subsets = stratified_training_subsets(
                    times[fold.train_indices], events[fold.train_indices], [0.25, 0.5, 0.75, 1],
                    seed=deterministic_seed(config["base_seed"], "robustness_subset", key, fold.repeat, fold.fold),
                    max_time_bins=4,
                )
                conditions = [(f"fraction_{f:.2f}", fold.train_indices[subsets[f]], None)
                              for f in (0.25, 0.5, 0.75)]
                conditions += [(f"admin_q{q:.2f}", fold.train_indices,
                                float(np.quantile(times[fold.train_indices], q))) for q in (0.75, 0.5)]
                for condition, train, cutoff in conditions:
                    for model in CATALYTIC_MODELS:
                        cell_id = f"{key}__clinical__r{fold.repeat:02}f{fold.fold:02}__{model}__{condition}"
                        jobs.append(ExtensionJob(cell_id, key, "clinical", model, fold.repeat, fold.fold,
                                                 condition, train, fold.validation_indices, cutoff, 0))
    if len(jobs) != 1625 or len({j.cell_id for j in jobs}) != 1625:
        raise RuntimeError("extension grid is incomplete or contains duplicate fits")
    return jobs
