"""Create each model, tune its inner-fold candidates and apply the frozen diagnostic remedies."""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.data.survival_folds import repeated_survival_folds
from src.evaluation.metrics import integrated_brier
from src.models.bayesian.model import BayesianCoxModel
from src.models.cox import CoxPHModel
from src.models.deepsurv import DeepSurvModel
from src.models.random_survival_forest import RandomSurvivalForestModel

from .evaluation import administratively_truncate_for_ipcw
from .evaluation import evaluation_horizons_and_grid as _ibs_times
from .options import DiagnosticFailure, RunOptions, deterministic_seed


def _model_from_parameters(
    model_key: str,
    parameters: dict[str, Any],
    *,
    seed: int,
    confirmatory_config: dict[str, Any],
    bayes_draws: int,
    bayes_tune: int,
    bayes_chains: int,
    target_accept_override: float | None = None,
    noncentered_baseline: bool = False,
) -> Any:
    """Construct one model with explicit sampling controls and a deterministic seed."""
    model_config = confirmatory_config["models"]
    if model_key == "cox_ph":
        return CoxPHModel(l2_reg=float(parameters["l2_reg"]), random_state=seed)
    if model_key == "random_survival_forest":
        return RandomSurvivalForestModel(random_state=seed, **parameters)
    if model_key == "deepsurv":
        return DeepSurvModel(random_state=seed, **parameters)
    if model_key.startswith("bayesian_"):
        prior = model_key.removeprefix("bayesian_")
        bayesian = model_config["bayesian_cox"]
        prior_config = bayesian["priors"][prior]
        target_accept = (
            float(target_accept_override)
            if target_accept_override is not None
            else float(prior_config["target_accept"])
        )
        return BayesianCoxModel(
            n_intervals=int(bayesian["n_intervals"]),
            inference_method="nuts",
            draws=bayes_draws,
            tune=bayes_tune,
            chains=bayes_chains,
            cores=int(bayesian["cores"]),
            target_accept=target_accept,
            random_state=seed,
            coefficient_prior=prior,
            prior_params=dict(prior_config["prior_params"]),
            noncentered_baseline=noncentered_baseline,
        )
    raise ValueError(f"unknown model key {model_key!r}")


def _model_candidates(model_key: str, confirmatory_config: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the fixed candidate order used to break exact inner-CV ties."""
    config = confirmatory_config["models"]
    if model_key == "cox_ph":
        return [dict(config[model_key])]
    if model_key in {"random_survival_forest", "deepsurv"}:
        fixed = dict(config[model_key]["fixed"])
        return [fixed | dict(candidate) for candidate in config[model_key]["inner_grid"]]
    if model_key.startswith("bayesian_"):
        return [{}]
    raise ValueError(f"unknown model key {model_key!r}")


def tune_candidate(
    model_key: str,
    candidates: list[dict[str, Any]],
    raw_training: pd.DataFrame,
    train_time: np.ndarray,
    train_event: np.ndarray,
    feature_spec: dict[str, Any],
    *,
    seed: int,
    confirmatory_config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Select compact forest or DeepSurv hyperparameters by inner-fold IPCW IBS.

    Preprocessing and censoring weights are fitted again within each inner
    training fold. A candidate is eligible only if all of its folds succeed;
    list order breaks exact ties in mean IBS. Untuned models have one candidate.

    Args:
        candidates: Frozen parameter dictionaries in their prescribed order.
        raw_training: Unprocessed outer-training rows, indexed from zero.
        feature_spec: Predictor declaration used by every inner-fold processor.
        seed: Seed for inner folds and their model fits.
        confirmatory_config: Frozen model, validation and evaluation settings.

    Returns:
        The selected parameter dictionary and the complete tuning record.
    """
    if len(candidates) == 1:
        return candidates[0], {"tuned": False, "candidates": []}

    validation = confirmatory_config["validation"]
    inner_folds = repeated_survival_folds(
        train_time,
        train_event,
        n_splits=int(validation["inner_splits"]),
        n_repeats=1,
        base_seed=seed,
        max_time_bins=int(validation["followup_time_bins"]),
    )
    candidate_records: list[dict[str, Any]] = []
    for candidate_index, candidate in enumerate(candidates):
        candidate_records.append(
            _candidate_record(
                model_key,
                candidate_index,
                candidate,
                raw_training,
                train_time,
                train_event,
                feature_spec,
                inner_folds,
                seed,
                confirmatory_config,
            )
        )

    valid = [row for row in candidate_records if row["mean_ibs"] is not None]
    if not valid:
        raise RuntimeError(
            f"every {model_key} inner-CV candidate had an unsupported or failed fold"
        )
    selected = min(valid, key=lambda row: (row["mean_ibs"], row["candidate_index"]))
    return dict(selected["parameters"]), {
        "tuned": True,
        "selection_metric": "IPCW integrated Brier score (lower is better)",
        "selected_candidate_index": selected["candidate_index"],
        "candidates": candidate_records,
    }


def _fit_with_diagnostic_rule(
    model_key: str,
    parameters: dict[str, Any],
    x_train: pd.DataFrame,
    train_time: np.ndarray,
    train_event: np.ndarray,
    *,
    seed: int,
    config: dict[str, Any],
    options: RunOptions,
) -> tuple[Any, list[dict[str, Any]]]:
    """Apply at most the frozen remedies and retain diagnostics from every attempt."""
    # Resolve the historical package hooks at call time for callers that replace
    # a model factory or trace collector, including the diagnostic-failure tests.
    from . import _model_from_parameters, _posterior_trace_snapshot

    attempts: list[dict[str, Any]] = []
    bayesian = model_key.startswith("bayesian_")
    maximum_attempts = 1
    if bayesian and options.mode == "confirmatory":
        maximum_attempts += int(
            config["models"]["bayesian_cox"]["failed_fit_rule"]["maximum_refits"]
        )

    for attempt in range(maximum_attempts):
        target_override = None
        tune = options.bayes_tune
        if attempt > 0:
            rule = config["models"]["bayesian_cox"]["failed_fit_rule"]
            target_override = float(rule["refit_target_accept"])
            tune = int(options.bayes_tune * int(rule["refit_tune_multiplier"]))
        noncentered_baseline = attempt >= 2
        model = _model_from_parameters(
            model_key,
            parameters,
            seed=deterministic_seed(seed, "fit_attempt", attempt),
            confirmatory_config=config,
            bayes_draws=options.bayes_draws,
            bayes_tune=tune,
            bayes_chains=options.bayes_chains,
            target_accept_override=target_override,
            noncentered_baseline=noncentered_baseline,
        )
        started = time.perf_counter()
        model.fit(x_train, train_time, train_event)
        attempt_record: dict[str, Any] = {
            "attempt": attempt + 1,
            "fit_seconds": time.perf_counter() - started,
            "target_accept": getattr(model, "target_accept", None),
            "tune": getattr(model, "tune", None),
            "noncentered_baseline": getattr(model, "noncentered_baseline", None),
        }
        if bayesian:
            attempt_record["diagnostics"] = model.diagnostics
            if options.mode == "confirmatory" and not model.diagnostics.get("converged", False):
                attempt_record["posterior_trace_snapshot"] = _posterior_trace_snapshot(model)
                attempt_record["model_checks"] = {
                    "prior_predictive": model.prior_predictive_summary,
                    "posterior_predictive": model.posterior_predictive_summary,
                }
        attempts.append(attempt_record)
        if (
            not bayesian
            or options.mode != "confirmatory"
            or model.diagnostics.get("converged", False)
        ):
            return model, attempts
    raise DiagnosticFailure(attempts)


def _candidate_record(
    model_key: str,
    candidate_index: int,
    candidate: dict[str, Any],
    raw_training: pd.DataFrame,
    train_time: np.ndarray,
    train_event: np.ndarray,
    feature_spec: dict[str, Any],
    inner_folds: list[Any],
    seed: int,
    confirmatory_config: dict[str, Any],
) -> dict[str, Any]:
    """Record every inner-fold score or explicit failure for one fixed candidate."""
    scores: list[float] = []
    failures: list[dict[str, Any]] = []
    for inner in inner_folds:
        inner_seed = deterministic_seed(seed, model_key, candidate_index, inner.fold)
        try:
            scores.append(
                _inner_fold_score(
                    model_key,
                    candidate,
                    raw_training,
                    train_time,
                    train_event,
                    feature_spec,
                    inner,
                    inner_seed,
                    confirmatory_config,
                )
            )
        except Exception as exc:  # the complete failure is retained in the cell
            failures.append(
                {
                    "fold": inner.fold,
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )
    return {
        "candidate_index": candidate_index,
        "parameters": candidate,
        "fold_ibs": scores,
        "mean_ibs": float(np.mean(scores)) if len(scores) == len(inner_folds) else None,
        "failures": failures,
    }


def _inner_fold_score(
    model_key: str,
    candidate: dict[str, Any],
    raw_training: pd.DataFrame,
    train_time: np.ndarray,
    train_event: np.ndarray,
    feature_spec: dict[str, Any],
    inner: Any,
    inner_seed: int,
    confirmatory_config: dict[str, Any],
) -> float:
    """Fit preprocessing and one candidate wholly within an inner-training fold."""
    train_idx = inner.train_indices
    valid_idx = inner.validation_indices
    processor = FoldFeaturePreprocessor(feature_spec)
    x_train = processor.fit_transform(raw_training.iloc[train_idx])
    x_valid = processor.transform(raw_training.iloc[valid_idx])
    _horizons, grid = _ibs_times(
        train_time[train_idx],
        train_event[train_idx],
        confirmatory_config["evaluation"],
    )
    model = _model_from_parameters(
        model_key,
        candidate,
        seed=inner_seed,
        confirmatory_config=confirmatory_config,
        bayes_draws=0,
        bayes_tune=0,
        bayes_chains=0,
    )
    model.fit(
        x_train,
        train_time[train_idx],
        train_event[train_idx],
    )
    survival = model.predict_survival(x_valid, grid)
    valid_time, valid_event = administratively_truncate_for_ipcw(
        train_time[valid_idx], train_event[valid_idx], float(grid[-1])
    )
    score = integrated_brier(
        train_time[train_idx],
        train_event[train_idx],
        valid_time,
        valid_event,
        survival,
        grid,
    )
    return float(score)
