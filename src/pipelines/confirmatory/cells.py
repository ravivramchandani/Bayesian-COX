"""Fit one outer-validation cell and retain its complete result or explicit failure record."""

from __future__ import annotations

import time
import traceback
from typing import Any

import numpy as np
import pandas as pd

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.data.survival_folds import SurvivalFold
from src.utils.io import json_safe as _json_safe
from src.utils.reproducibility import canonical_json_hash

from .evaluation import evaluate_predictions as _evaluate_predictions
from .fitting import _model_candidates, tune_candidate
from .options import MODEL_LABELS, DiagnosticFailure, RunOptions, deterministic_seed
from .posterior import _model_details


def run_cell(
    dataset_key: str,
    model_key: str,
    fold: SurvivalFold,
    raw: pd.DataFrame,
    times: np.ndarray,
    events: np.ndarray,
    subject_ids: np.ndarray,
    feature_spec: dict[str, Any],
    *,
    config: dict[str, Any],
    options: RunOptions,
    data_sha256: str,
) -> dict[str, Any]:
    """Fit, evaluate and serialise one model on one paired outer fold.

    Predictor processing and model selection use the outer-training rows only.
    A diagnostic failure retains every permitted attempt; another exception
    becomes an explicit failed record. Both retain the cell's identity and seed.

    Args:
        fold: Training and validation row indices from the frozen fold generator.
        raw: Unprocessed cohort frame; ``times``, ``events`` and ``subject_ids``
            follow the same row order.
        feature_spec: Frozen predictor declaration for the fold-local processor.
        config: Frozen study protocol, including model and evaluation settings.
        options: Actual run controls, including the diagnostic-gate mode.
        data_sha256: Hash of the authoritative cohort CSV.

    Returns:
        A complete or failed cell record with its content hash and elapsed time.
    """
    started = time.perf_counter()
    base = _cell_metadata(
        dataset_key, model_key, fold, events, subject_ids, config, options, data_sha256
    )
    cell_seed = base["cell_seed"]
    try:
        base.update(
            _successful_cell(
                model_key,
                fold,
                raw,
                times,
                events,
                subject_ids,
                feature_spec,
                config,
                options,
                cell_seed,
            )
        )
    except DiagnosticFailure as exc:
        base.update(
            {
                "status": "failed_diagnostics",
                "fit_attempts": exc.attempts,
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
        )
    except Exception as exc:
        base.update(
            {
                "status": "failed",
                "error_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    base["total_seconds"] = time.perf_counter() - started
    base["cell_content_sha256"] = canonical_json_hash(_json_safe(base))
    return base


def _cell_metadata(
    dataset_key: str,
    model_key: str,
    fold: SurvivalFold,
    events: np.ndarray,
    subject_ids: np.ndarray,
    config: dict[str, Any],
    options: RunOptions,
    data_sha256: str,
) -> dict[str, Any]:
    """Build the unchanged identity, sample and seed fields shared by every cell status."""
    cell_seed = deterministic_seed(
        int(config["validation"]["base_seed"]),
        dataset_key,
        fold.repeat,
        fold.fold,
        model_key,
    )
    return {
        "schema_version": "1.0.0",
        "dataset": dataset_key,
        "dataset_sha256": data_sha256,
        "model_key": model_key,
        "model": MODEL_LABELS[model_key],
        "repeat": fold.repeat,
        "fold": fold.fold,
        "fold_seed": fold.seed,
        "cell_seed": cell_seed,
        "analysis_mode": options.mode,
        "evidence_status": ("confirmatory" if options.mode == "confirmatory" else "rehearsal_only"),
        "train_subject_ids": subject_ids[fold.train_indices],
        "validation_subject_ids": subject_ids[fold.validation_indices],
        "n_train": len(fold.train_indices),
        "n_validation": len(fold.validation_indices),
        "events_train": int(events[fold.train_indices].sum()),
        "events_validation": int(events[fold.validation_indices].sum()),
    }


def _successful_cell(
    model_key: str,
    fold: SurvivalFold,
    raw: pd.DataFrame,
    times: np.ndarray,
    events: np.ndarray,
    subject_ids: np.ndarray,
    feature_spec: dict[str, Any],
    config: dict[str, Any],
    options: RunOptions,
    cell_seed: int,
) -> dict[str, Any]:
    """Preprocess, tune, fit and score a cell before collecting its model details."""
    from . import _fit_with_diagnostic_rule

    processor = FoldFeaturePreprocessor(feature_spec)
    x_train = processor.fit_transform(raw.iloc[fold.train_indices])
    x_validation = processor.transform(raw.iloc[fold.validation_indices])
    candidates = _model_candidates(model_key, config)
    selected, tuning = tune_candidate(
        model_key,
        candidates,
        raw.iloc[fold.train_indices].reset_index(drop=True),
        times[fold.train_indices],
        events[fold.train_indices],
        feature_spec,
        seed=deterministic_seed(cell_seed, "inner_cv"),
        confirmatory_config=config,
    )
    model, attempts = _fit_with_diagnostic_rule(
        model_key,
        selected,
        x_train,
        times[fold.train_indices],
        events[fold.train_indices],
        seed=cell_seed,
        config=config,
        options=options,
    )
    metrics, predictions = _evaluate_predictions(
        model,
        x_validation,
        times[fold.train_indices],
        events[fold.train_indices],
        times[fold.validation_indices],
        events[fold.validation_indices],
        evaluation_config=config["evaluation"],
        calibration_bootstraps=options.calibration_bootstraps,
        seed=cell_seed,
    )
    return {
        "status": "complete",
        "selected_hyperparameters": selected,
        "inner_tuning": tuning,
        "fit_attempts": attempts,
        "preprocessing": processor.metadata(),
        "metrics": metrics,
        "predictions": {
            **predictions,
            "subject_ids": subject_ids[fold.validation_indices],
            "observed_time": times[fold.validation_indices],
            "observed_event": events[fold.validation_indices],
            "training_time": times[fold.train_indices],
            "training_event": events[fold.train_indices],
        },
        "model_details": _model_details(
            model,
            model_key,
            x_train,
            times[fold.train_indices],
            events[fold.train_indices],
            x_validation,
            processor.feature_groups,
        ),
    }
