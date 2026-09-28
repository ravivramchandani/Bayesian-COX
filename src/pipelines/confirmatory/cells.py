"""Fit one outer-validation cell and retain its complete result or explicit failure record.

A cell is one model on one outer fold of one cohort. :mod:`runner` calls
:func:`run_cell` for every planned cell that is not yet stored. The cell
preprocesses the fold, tunes and fits the model (:mod:`fitting`), scores it
(:mod:`evaluation`), collects model details (:mod:`posterior`) and returns one
cell mapping, possibly containing NumPy arrays, with a SHA-256 content hash. The runner writes that record
once through the shared JSON writer; :mod:`aggregation` and :mod:`inference` read it back.
"""

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
    A diagnostic failure retains the completed attempts supplied by the fitter;
    an execution exception inside the cell calculation becomes an explicit failed
    record without those attempts. Both retain the cell's identity and seed.
    The ``status`` field is ``"complete"``, ``"failed_diagnostics"`` or
    ``"failed"``.

    Args:
        dataset_key: Cohort key from ``config/datasets.yaml``.
        model_key: One of :data:`~.options.MODEL_KEYS`.
        fold: Training and validation row indices from the frozen fold generator.
        raw: Unprocessed cohort frame; ``times``, ``events`` and ``subject_ids``
            follow the same row order.
        times: Follow-up times in the cohort's own unit (days or months).
        events: Event indicators (1 = event, 0 = censored).
        subject_ids: Stable subject identifiers, stored so that paired cells
            can be checked for identical validation subjects.
        feature_spec: Frozen predictor declaration for the fold-local processor.
        config: Frozen study protocol, including model and evaluation settings.
        options: Actual run controls, including the diagnostic-gate mode.
        data_sha256: Hash of the authoritative cohort CSV.

    Returns:
        A complete or failed cell mapping with its content hash and elapsed time
        in seconds. NumPy values are converted by the runner when it writes JSON.
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
    # The hash covers the whole record as written, timings included, so any
    # later edit to a stored cell is detected when it is loaded. Because
    # wall-clock times differ between executions, a refit reproduces every
    # field except the timings and this hash; the reproduction check compares
    # all other fields.
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
    # The seed depends only on the cell's identity, not on run order, so a
    # cell refitted alone or in another process gets the same seed.
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
    """Preprocess, tune, fit and score a cell before collecting its model details.

    Returns:
        The fields added to a complete cell: selected hyperparameters, the
        tuning record, fit attempts, preprocessing metadata, metrics,
        validation predictions with the observed outcomes, the training
        outcomes that define inverse probability of censoring weighting (IPCW),
        and model details.
    """
    from . import _fit_with_diagnostic_rule

    # Imputation, encoding and scaling are fitted on the training rows only
    # and then applied unchanged to the validation rows.
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
            # The paired bootstrap in ``inference`` recomputes the IBS from the
            # stored cell alone; these training outcomes define its weights.
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
