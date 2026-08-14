"""Checkpointed repeated nested-CV pipeline for the confirmatory study."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sys
import time
import traceback
from dataclasses import dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.data.survival_folds import SurvivalFold, repeated_survival_folds
from src.evaluation.calibration import (
    survival_calibration_curve,
    survival_calibration_summary,
)
from src.evaluation.metrics import (
    harrell_c_index,
    integrated_brier,
    time_dependent_auc,
    training_event_time_horizons,
    uno_c_index,
    validate_ipcw_horizons,
)
from src.models.bayesian.model import BayesianCoxModel
from src.models.cox import CoxPHModel
from src.models.deepsurv import DeepSurvModel
from src.models.random_survival_forest import RandomSurvivalForestModel
from src.statistics.hypothesis_tests import holm_adjust
from src.statistics.repeated_cv import nadeau_bengio_paired_effect
from src.utils.reproducibility import (
    build_run_manifest,
    canonical_json_hash,
    sha256_file,
)

MODEL_KEYS = (
    "cox_ph",
    "random_survival_forest",
    "deepsurv",
    "bayesian_normal",
    "bayesian_horseshoe",
    "bayesian_spike_slab",
)

MODEL_LABELS = {
    "cox_ph": "Cox PH",
    "random_survival_forest": "Random Survival Forest",
    "deepsurv": "DeepSurv",
    "bayesian_normal": "Bayesian Cox (normal)",
    "bayesian_horseshoe": "Bayesian Cox (horseshoe)",
    "bayesian_spike_slab": "Bayesian Cox (spike_slab)",
}


class DiagnosticFailure(RuntimeError):
    """A Bayesian cell failed the frozen all-parameter diagnostic gate."""

    def __init__(self, attempts: list[dict[str, Any]]) -> None:
        super().__init__("Bayesian fit did not pass the confirmatory diagnostic gate")
        self.attempts = attempts


@dataclass(frozen=True)
class RunOptions:
    """Actual run controls after applying rehearsal-only reductions."""

    mode: str
    datasets: tuple[str, ...]
    models: tuple[str, ...]
    outer_splits: int
    outer_repeats: int
    fold_limit_per_dataset: int | None
    bayes_draws: int
    bayes_tune: int
    bayes_chains: int
    calibration_bootstraps: int
    resume: bool
    output_root: Path


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return [_json_safe(item) for item in value.tolist()]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if value is None or isinstance(value, str):
        return value
    return str(value)


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_json_safe(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def deterministic_seed(base_seed: int, *parts: object) -> int:
    """Derive a stable positive 31-bit seed independent of Python hashing."""
    payload = "|".join([str(base_seed), *(str(part) for part in parts)])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % (2**31 - 1)


def _feature_spec(dataset_config: dict[str, Any], feature_set: str) -> dict[str, Any]:
    if feature_set == "primary":
        return dict(dataset_config["primary_features"])
    sensitivities = dataset_config.get("sensitivity_feature_sets", {})
    if feature_set not in sensitivities:
        raise ValueError(
            f"dataset {dataset_config['name']} has no feature set {feature_set!r}"
        )
    return dict(sensitivities[feature_set])


def load_analysis_dataset(
    project_root: Path,
    dataset_key: str,
    dataset_config: dict[str, Any],
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    """Load and validate one already-derived authoritative cohort."""
    path = project_root / dataset_config["raw_file"]
    if not path.is_file():
        raise FileNotFoundError(f"authoritative raw dataset is missing: {path}")
    frame = pd.read_csv(path)
    duration_col = dataset_config["duration_col"]
    event_col = dataset_config["event_col"]
    missing = [name for name in (duration_col, event_col) if name not in frame]
    if missing:
        raise ValueError(f"{dataset_key} is missing outcome columns {missing}")

    time_values = pd.to_numeric(frame[duration_col], errors="coerce").to_numpy(float)
    event_values = pd.to_numeric(frame[event_col], errors="coerce").to_numpy(float)
    if not np.isfinite(time_values).all() or np.any(time_values <= 0):
        raise ValueError(f"{dataset_key} contains non-positive or missing survival time")
    if not np.isin(event_values, [0.0, 1.0]).all():
        raise ValueError(f"{dataset_key} event indicator is not binary")
    events = event_values.astype(int)
    if events.sum() < 2 or (len(events) - events.sum()) < 2:
        raise ValueError(f"{dataset_key} requires both events and censoring")

    id_col = dataset_config.get("id_col")
    if id_col:
        if id_col not in frame:
            raise ValueError(f"{dataset_key} is missing ID column {id_col!r}")
        subject_ids = frame[id_col].astype(str).to_numpy()
    else:
        width = len(str(len(frame)))
        subject_ids = np.asarray(
            [f"{dataset_key}-{index:0{width}d}" for index in range(len(frame))]
        )
    if len(set(subject_ids)) != len(subject_ids):
        raise ValueError(f"{dataset_key} subject identifiers are not unique")
    return frame, time_values, events, subject_ids


def _ibs_times(
    train_time: np.ndarray,
    train_event: np.ndarray,
    evaluation_config: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    horizons = training_event_time_horizons(
        train_time,
        train_event,
        quantiles=evaluation_config["horizon_event_quantiles"],
        min_censoring_survival=float(
            evaluation_config["minimum_censoring_survival"]
        ),
    )
    grid = np.linspace(
        float(horizons[0]),
        float(horizons[-1]),
        int(evaluation_config["ibs_grid_points"]),
    )
    grid = validate_ipcw_horizons(
        train_time,
        train_event,
        grid,
        min_censoring_survival=float(
            evaluation_config["minimum_censoring_survival"]
        ),
    )
    return horizons, grid


def administratively_truncate_for_ipcw(
    time_values: np.ndarray,
    event_values: np.ndarray,
    tau: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Censor follow-up after a training-derived IPCW boundary.

    The next representable float above ``tau`` preserves that these subjects
    are known to be event-free through the last evaluation time and satisfies
    reference estimators requiring evaluation times below maximum follow-up.
    """
    times = np.asarray(time_values, dtype=float).copy()
    events = np.asarray(event_values, dtype=int).copy()
    if not np.isfinite(tau) or tau <= 0:
        raise ValueError("IPCW truncation time must be finite and positive")
    after = times > tau
    times[after] = np.nextafter(float(tau), np.inf)
    events[after] = 0
    return times, events


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
    model_config = confirmatory_config["models"]
    if model_key == "cox_ph":
        return CoxPHModel(
            l2_reg=float(parameters["l2_reg"]), random_state=seed
        )
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


def _model_candidates(
    model_key: str, confirmatory_config: dict[str, Any]
) -> list[dict[str, Any]]:
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
    """Select compact RSF/DeepSurv hyperparameters by inner-fold IPCW IBS."""
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
        scores: list[float] = []
        failures: list[dict[str, Any]] = []
        for inner in inner_folds:
            inner_seed = deterministic_seed(
                seed, model_key, candidate_index, inner.fold
            )
            train_idx = inner.train_indices
            valid_idx = inner.validation_indices
            try:
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
                scores.append(float(score))
            except Exception as exc:  # the complete failure is retained in the cell
                failures.append(
                    {
                        "fold": inner.fold,
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
                )
        candidate_records.append(
            {
                "candidate_index": candidate_index,
                "parameters": candidate,
                "fold_ibs": scores,
                "mean_ibs": float(np.mean(scores))
                if len(scores) == len(inner_folds)
                else None,
                "failures": failures,
            }
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
            if (
                options.mode == "confirmatory"
                and not model.diagnostics.get("converged", False)
            ):
                attempt_record["posterior_trace_snapshot"] = (
                    _posterior_trace_snapshot(model)
                )
                attempt_record["model_checks"] = {
                    "prior_predictive": model.prior_predictive_summary,
                    "posterior_predictive": model.posterior_predictive_summary,
                }
        attempts.append(attempt_record)
        if not bayesian or options.mode != "confirmatory" or model.diagnostics.get(
            "converged", False
        ):
            return model, attempts
    raise DiagnosticFailure(attempts)


def _evaluate_predictions(
    model: Any,
    x_validation: pd.DataFrame,
    train_time: np.ndarray,
    train_event: np.ndarray,
    validation_time: np.ndarray,
    validation_event: np.ndarray,
    *,
    evaluation_config: dict[str, Any],
    calibration_bootstraps: int,
    seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    horizons, ibs_grid = _ibs_times(train_time, train_event, evaluation_config)
    prediction_times = np.unique(np.concatenate([horizons, ibs_grid]))
    risk = np.asarray(model.predict_risk(x_validation), dtype=float)
    survival = np.asarray(
        model.predict_survival(x_validation, prediction_times), dtype=float
    )
    validate_survival_prediction_matrix(
        survival, n_samples=len(x_validation), n_times=len(prediction_times)
    )
    horizon_indices = np.searchsorted(prediction_times, horizons)
    grid_indices = np.searchsorted(prediction_times, ibs_grid)
    horizon_survival = survival[:, horizon_indices]
    grid_survival = survival[:, grid_indices]
    ipcw_time, ipcw_event = administratively_truncate_for_ipcw(
        validation_time, validation_event, float(horizons[-1])
    )

    auc, mean_auc = time_dependent_auc(
        train_time,
        train_event,
        ipcw_time,
        ipcw_event,
        risk,
        horizons,
    )
    metrics = {
        "harrell_c_index": harrell_c_index(
            validation_time, validation_event, risk
        ),
        "uno_c_index": uno_c_index(
            train_time,
            train_event,
            ipcw_time,
            ipcw_event,
            risk,
            tau=float(horizons[-1]),
        ),
        "uno_tau": float(horizons[-1]),
        "ipcw_administrative_truncation_tau": float(horizons[-1]),
        "ibs": integrated_brier(
            train_time,
            train_event,
            ipcw_time,
            ipcw_event,
            grid_survival,
            ibs_grid,
        ),
        "mean_auc": mean_auc,
        "auc_at_horizons": auc,
        "horizons": horizons,
        "ibs_grid": ibs_grid,
    }

    calibration: list[dict[str, Any]] = []
    for index, horizon in enumerate(horizons):
        summary = survival_calibration_summary(
            train_time,
            train_event,
            validation_time,
            validation_event,
            horizon_survival[:, index],
            float(horizon),
            n_bootstraps=calibration_bootstraps,
            confidence_level=float(evaluation_config["confidence_level"]),
            random_state=deterministic_seed(seed, "calibration", index),
        )
        curve = survival_calibration_curve(
            validation_time,
            validation_event,
            horizon_survival[:, index],
            float(horizon),
            n_bins=int(evaluation_config["calibration_bins"]),
            confidence_level=float(evaluation_config["confidence_level"]),
        )
        calibration.append({"summary": summary, "curve": curve})
    metrics["calibration"] = calibration
    predictions = {
        "risk": risk,
        "horizons": horizons,
        "survival_at_horizons": horizon_survival,
        "ibs_grid": ibs_grid,
        "survival_on_ibs_grid": grid_survival,
    }
    return metrics, predictions


def validate_survival_prediction_matrix(
    survival: np.ndarray,
    *,
    n_samples: int,
    n_times: int,
    tolerance: float = 1e-8,
) -> None:
    """Reject malformed or non-monotone predicted survival functions."""
    values = np.asarray(survival, dtype=float)
    if values.shape != (n_samples, n_times):
        raise ValueError(
            f"survival prediction shape must be {(n_samples, n_times)}, "
            f"got {values.shape}"
        )
    if not np.isfinite(values).all():
        raise ValueError("survival predictions must be finite")
    if np.any(values < -tolerance) or np.any(values > 1.0 + tolerance):
        raise ValueError("survival predictions must lie in [0, 1]")
    if np.any(np.diff(values, axis=1) > tolerance):
        raise ValueError("survival predictions must be non-increasing over time")


def _posterior_trace_snapshot(model: BayesianCoxModel) -> dict[str, Any]:
    """Archive a deterministic thinned trace for pure visual rendering.

    Numerical diagnostics always use every retained draw in ``model.idata``;
    this snapshot is only for trace and marginal plots in the supplement.
    """
    posterior = model.idata.posterior
    n_draws = int(posterior.sizes["draw"])
    draw_indices = np.linspace(0, n_draws - 1, min(250, n_draws), dtype=int)
    variables: dict[str, Any] = {}
    for name in posterior.data_vars:
        data = posterior[name]
        values = np.asarray(data.isel(draw=draw_indices).values, dtype=float)
        variables[name] = {
            "dims": list(data.dims),
            "values": values,
        }
    return {
        "purpose": "visualisation_only_full_trace_used_for_numeric_diagnostics",
        "draw_indices": draw_indices,
        "variables": variables,
    }


def _model_details(
    model: Any,
    model_key: str,
    x_train: pd.DataFrame,
    train_time: np.ndarray,
    train_event: np.ndarray,
    x_validation: pd.DataFrame,
    feature_groups: dict[str, str],
) -> dict[str, Any]:
    if model_key == "cox_ph":
        summary = model.summary().to_dict(orient="records")
        ph = model.proportional_hazards_test(
            x_train, train_time, train_event
        ).to_dict(orient="records")
        adjusted, rejected = holm_adjust([row["p"] for row in ph])
        for row, adjusted_p, reject in zip(ph, adjusted, rejected, strict=True):
            row["holm_adjusted_p"] = adjusted_p
            row["holm_reject_0_05"] = reject
        return {"coefficient_summary": summary, "ph_test": ph}
    if model_key == "random_survival_forest":
        return {
            "implementation": "sksurv.ensemble.RandomSurvivalForest",
            "n_features": len(model.feature_names),
        }
    if model_key == "deepsurv":
        return {
            "training_configuration": model.get_summary().to_dict(orient="records"),
            "training_log": model.training_log.to_dict(orient="records"),
        }
    if model_key.startswith("bayesian_"):
        inclusion = model.inclusion_signal()
        grouped_contribution = model.posterior_expected_absolute_group_contribution(
            x_validation, feature_groups
        )
        return {
            "diagnostics": model.diagnostics,
            "prior_predictive": model.prior_predictive_summary,
            "posterior_predictive": model.posterior_predictive_summary,
            "coefficient_summary": model.get_summary().to_dict(orient="records"),
            "posterior_expected_absolute_contribution": (
                model.posterior_expected_absolute_contribution(x_validation).to_dict(
                    orient="records"
                )
            ),
            "posterior_expected_absolute_group_contribution_by_subject": {
                "definition": (
                    "E_posterior(|sum of x_j beta_j within source group|) "
                    "for each outer-validation subject"
                ),
                "group_names": list(grouped_contribution.columns),
                "values": grouped_contribution.to_numpy(dtype=float),
            },
            "inclusion_signal": inclusion.to_dict(orient="records")
            if inclusion is not None
            else None,
            "posterior_mean_beta": dict(
                zip(
                    model.feature_names,
                    np.mean(model.beta_samples, axis=0).tolist(),
                    strict=True,
                )
            ),
            "posterior_trace_snapshot": _posterior_trace_snapshot(model),
        }
    return {}


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
    """Fit, evaluate and fully serialise one paired outer-fold/model cell."""
    started = time.perf_counter()
    cell_seed = deterministic_seed(
        int(config["validation"]["base_seed"]),
        dataset_key,
        fold.repeat,
        fold.fold,
        model_key,
    )
    base = {
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
        "evidence_status": (
            "confirmatory" if options.mode == "confirmatory" else "rehearsal_only"
        ),
        "train_subject_ids": subject_ids[fold.train_indices],
        "validation_subject_ids": subject_ids[fold.validation_indices],
        "n_train": len(fold.train_indices),
        "n_validation": len(fold.validation_indices),
        "events_train": int(events[fold.train_indices].sum()),
        "events_validation": int(events[fold.validation_indices].sum()),
    }
    try:
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
        base.update(
            {
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


def _cell_path(run_dir: Path, dataset: str, fold: SurvivalFold, model: str) -> Path:
    return (
        run_dir
        / "cells"
        / dataset
        / f"repeat_{fold.repeat:02d}_fold_{fold.fold:02d}"
        / f"{model}.json"
    )


def _load_cells(run_dir: Path) -> list[dict[str, Any]]:
    cells = []
    for path in sorted((run_dir / "cells").glob("*/*/*.json")):
        with path.open(encoding="utf-8") as handle:
            cell = json.load(handle)
        claimed_hash = cell.get("cell_content_sha256")
        unhashed = dict(cell)
        unhashed.pop("cell_content_sha256", None)
        observed_hash = canonical_json_hash(unhashed)
        if claimed_hash != observed_hash:
            raise RuntimeError(f"cell content hash does not match: {path}")
        cells.append(cell)
    return cells


def _aggregate_tables(run_dir: Path, cells: list[dict[str, Any]]) -> None:
    metrics_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    for cell in cells:
        if cell.get("status") != "complete":
            continue
        metrics = cell["metrics"]
        row = {
            "dataset": cell["dataset"],
            "model": cell["model"],
            "model_key": cell["model_key"],
            "repeat": cell["repeat"],
            "fold": cell["fold"],
            "n_train": cell["n_train"],
            "n_validation": cell["n_validation"],
            "events_train": cell["events_train"],
            "events_validation": cell["events_validation"],
            "harrell_c_index": metrics["harrell_c_index"],
            "uno_c_index": metrics["uno_c_index"],
            "ibs": metrics["ibs"],
            "mean_auc": metrics["mean_auc"],
            "total_seconds": cell["total_seconds"],
            "cell_content_sha256": cell["cell_content_sha256"],
        }
        for index, (horizon, auc) in enumerate(
            zip(metrics["horizons"], metrics["auc_at_horizons"], strict=True),
            start=1,
        ):
            row[f"horizon_{index}"] = horizon
            row[f"auc_{index}"] = auc
            summary = metrics["calibration"][index - 1]["summary"]
            row[f"calibration_intercept_{index}"] = summary["intercept"]["estimate"]
            row[f"calibration_slope_{index}"] = summary["slope"]["estimate"]
            row[f"calibration_large_{index}"] = summary[
                "calibration_in_the_large"
            ]["estimate"]
        metrics_rows.append(row)

        predictions = cell["predictions"]
        for index, subject_id in enumerate(predictions["subject_ids"]):
            prediction_rows.append(
                {
                    "dataset": cell["dataset"],
                    "model": cell["model"],
                    "model_key": cell["model_key"],
                    "repeat": cell["repeat"],
                    "fold": cell["fold"],
                    "subject_id": subject_id,
                    "observed_time": predictions["observed_time"][index],
                    "observed_event": predictions["observed_event"][index],
                    "risk": predictions["risk"][index],
                    "horizons_json": json.dumps(predictions["horizons"]),
                    "survival_at_horizons_json": json.dumps(
                        predictions["survival_at_horizons"][index]
                    ),
                    "ibs_grid_json": json.dumps(predictions["ibs_grid"]),
                    "survival_on_ibs_grid_json": json.dumps(
                        predictions["survival_on_ibs_grid"][index]
                    ),
                }
            )
    pd.DataFrame(metrics_rows).to_csv(run_dir / "fold_metrics.csv", index=False)
    pd.DataFrame(prediction_rows).to_csv(
        run_dir / "out_of_fold_predictions.csv.gz",
        index=False,
        compression={"method": "gzip", "compresslevel": 9, "mtime": 0},
    )


def _event_stratified_indices(
    event: np.ndarray, rng: np.random.Generator
) -> np.ndarray:
    groups = []
    for status in (0, 1):
        indices = np.flatnonzero(event == status)
        groups.append(rng.choice(indices, size=len(indices), replace=True))
    sampled = np.concatenate(groups)
    rng.shuffle(sampled)
    return sampled


def _paired_oof_ibs_bootstrap(
    paired_cells: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    n_bootstraps: int,
    seed: int,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Event-stratified paired bootstrap over each out-of-fold subject set."""
    if n_bootstraps < 20:
        raise ValueError("paired OOF bootstrap requires at least 20 replicates")
    rng = np.random.default_rng(seed)
    samples: list[float] = []
    for _ in range(n_bootstraps):
        fold_differences: list[float] = []
        for left, right in paired_cells:
            left_predictions = left["predictions"]
            right_predictions = right["predictions"]
            if left_predictions["subject_ids"] != right_predictions["subject_ids"]:
                raise ValueError("paired cells do not contain identical subject order")
            observed_time = np.asarray(left_predictions["observed_time"], dtype=float)
            observed_event = np.asarray(
                left_predictions["observed_event"], dtype=int
            )
            if not np.array_equal(
                observed_time,
                np.asarray(right_predictions["observed_time"], dtype=float),
            ) or not np.array_equal(
                observed_event,
                np.asarray(right_predictions["observed_event"], dtype=int),
            ):
                raise ValueError("paired cells do not contain identical outcomes")
            indices = _event_stratified_indices(observed_event, rng)
            training_time = np.asarray(
                left_predictions["training_time"], dtype=float
            )
            training_event = np.asarray(
                left_predictions["training_event"], dtype=int
            )
            grid = np.asarray(left_predictions["ibs_grid"], dtype=float)
            if not np.array_equal(
                grid, np.asarray(right_predictions["ibs_grid"], dtype=float)
            ):
                raise ValueError("paired cells do not use an identical IBS grid")
            survival_left = np.asarray(
                left_predictions["survival_on_ibs_grid"], dtype=float
            )[indices]
            survival_right = np.asarray(
                right_predictions["survival_on_ibs_grid"], dtype=float
            )[indices]
            bootstrap_time, bootstrap_event = administratively_truncate_for_ipcw(
                observed_time[indices], observed_event[indices], float(grid[-1])
            )
            try:
                ibs_left = integrated_brier(
                    training_time,
                    training_event,
                    bootstrap_time,
                    bootstrap_event,
                    survival_left,
                    grid,
                )
                ibs_right = integrated_brier(
                    training_time,
                    training_event,
                    bootstrap_time,
                    bootstrap_event,
                    survival_right,
                    grid,
                )
            except (RuntimeError, ValueError):
                fold_differences = []
                break
            fold_differences.append(ibs_left - ibs_right)
        if fold_differences:
            samples.append(float(np.mean(fold_differences)))

    required = max(20, int(np.ceil(0.8 * n_bootstraps)))
    if len(samples) < required:
        raise RuntimeError(
            f"only {len(samples)} of {n_bootstraps} paired OOF bootstrap "
            f"replicates were estimable; {required} required"
        )
    values = np.asarray(samples, dtype=float)
    alpha = 1.0 - confidence_level
    lower, upper = np.quantile(values, [alpha / 2.0, 1.0 - alpha / 2.0])
    return {
        "estimate": float(
            np.mean(
                [
                    left["metrics"]["ibs"] - right["metrics"]["ibs"]
                    for left, right in paired_cells
                ]
            )
        ),
        "bootstrap_mean": float(np.mean(values)),
        "bootstrap_standard_error": float(np.std(values, ddof=1)),
        "confidence_lower": float(lower),
        "confidence_upper": float(upper),
        "confidence_level": confidence_level,
        "n_bootstraps": n_bootstraps,
        "n_successful": len(values),
        "resampling_unit": "event-stratified validation subjects within paired folds",
    }


def _repeated_cv_inference(
    cells: list[dict[str, Any]], options: RunOptions, config: dict[str, Any]
) -> dict[str, Any]:
    complete = [cell for cell in cells if cell.get("status") == "complete"]
    lookup = {
        (cell["dataset"], cell["model_key"], cell["repeat"], cell["fold"]): cell
        for cell in complete
    }
    bayesian = ("bayesian_normal", "bayesian_horseshoe", "bayesian_spike_slab")
    primary: list[dict[str, Any]] = []
    secondary: list[dict[str, Any]] = []
    secondary_benchmarks: list[dict[str, Any]] = []
    expected = options.outer_repeats * options.outer_splits

    for dataset in options.datasets:
        for model_a, model_b in combinations(bayesian, 2):
            paired = []
            for repeat in range(1, options.outer_repeats + 1):
                for fold in range(1, options.outer_splits + 1):
                    left = lookup.get((dataset, model_a, repeat, fold))
                    right = lookup.get((dataset, model_b, repeat, fold))
                    if left is not None and right is not None:
                        paired.append((left, right))
            record: dict[str, Any] = {
                "dataset": dataset,
                "model_a": MODEL_LABELS[model_a],
                "model_b": MODEL_LABELS[model_b],
                "contrast_direction": "model_a minus model_b",
                "n_paired_folds": len(paired),
                "expected_paired_folds": expected,
            }
            if len(paired) == expected:
                ibs_effect = nadeau_bengio_paired_effect(
                    np.asarray([left["metrics"]["ibs"] for left, _ in paired]),
                    np.asarray([right["metrics"]["ibs"] for _, right in paired]),
                    n_repeats=options.outer_repeats,
                    n_folds=options.outer_splits,
                ).to_dict()
                record["ibs"] = ibs_effect
                calibration_effects: list[dict[str, Any]] = []
                for horizon_index in range(3):
                    for parameter in (
                        "calibration_in_the_large",
                        "intercept",
                        "slope",
                    ):
                        left_values = np.asarray(
                            [
                                left["metrics"]["calibration"][horizon_index][
                                    "summary"
                                ][parameter]["estimate"]
                                for left, _ in paired
                            ]
                        )
                        right_values = np.asarray(
                            [
                                right["metrics"]["calibration"][horizon_index][
                                    "summary"
                                ][parameter]["estimate"]
                                for _, right in paired
                            ]
                        )
                        effect = nadeau_bengio_paired_effect(
                            left_values,
                            right_values,
                            n_repeats=options.outer_repeats,
                            n_folds=options.outer_splits,
                        ).to_dict()
                        calibration_effects.append(
                            {
                                "horizon_index": horizon_index + 1,
                                "parameter": parameter,
                                "effect": effect,
                            }
                        )
                record["calibration_secondary_effects"] = calibration_effects
                try:
                    record["paired_oof_bootstrap"] = _paired_oof_ibs_bootstrap(
                        paired,
                        n_bootstraps=int(
                            config["inference"]["paired_oof_bootstraps"]
                        ),
                        seed=deterministic_seed(
                            int(config["validation"]["base_seed"]),
                            "paired_oof_bootstrap",
                            dataset,
                            model_a,
                            model_b,
                        ),
                    )
                except (RuntimeError, ValueError) as exc:
                    record["paired_oof_bootstrap"] = {
                        "status": "not_estimable",
                        "error_type": type(exc).__name__,
                        "message": str(exc),
                    }
            else:
                record["status"] = "incomplete_no_confirmatory_inference"
            primary.append(record)

            for metric in ("uno_c_index", "harrell_c_index", "mean_auc"):
                secondary_record = {
                    "dataset": dataset,
                    "model_a": MODEL_LABELS[model_a],
                    "model_b": MODEL_LABELS[model_b],
                    "metric": metric,
                    "n_paired_folds": len(paired),
                }
                if len(paired) == expected:
                    secondary_record["effect"] = nadeau_bengio_paired_effect(
                        np.asarray(
                            [left["metrics"][metric] for left, _ in paired]
                        ),
                        np.asarray(
                            [right["metrics"][metric] for _, right in paired]
                        ),
                        n_repeats=options.outer_repeats,
                        n_folds=options.outer_splits,
                    ).to_dict()
                else:
                    secondary_record["status"] = "incomplete"
                secondary.append(secondary_record)

        comparator_keys = ("cox_ph", "random_survival_forest", "deepsurv")
        for bayesian_key in bayesian:
            for comparator_key in comparator_keys:
                paired = []
                for repeat in range(1, options.outer_repeats + 1):
                    for fold in range(1, options.outer_splits + 1):
                        left = lookup.get((dataset, bayesian_key, repeat, fold))
                        right = lookup.get((dataset, comparator_key, repeat, fold))
                        if left is not None and right is not None:
                            paired.append((left, right))
                benchmark: dict[str, Any] = {
                    "dataset": dataset,
                    "model_a": MODEL_LABELS[bayesian_key],
                    "model_b": MODEL_LABELS[comparator_key],
                    "contrast_direction": "model_a minus model_b",
                    "n_paired_folds": len(paired),
                    "expected_paired_folds": expected,
                    "inferential_role": "secondary_estimation_no_multiplicity_claim",
                }
                if len(paired) == expected:
                    effects: dict[str, Any] = {}
                    for metric in (
                        "ibs",
                        "uno_c_index",
                        "harrell_c_index",
                        "mean_auc",
                    ):
                        effect = nadeau_bengio_paired_effect(
                            np.asarray(
                                [left["metrics"][metric] for left, _ in paired]
                            ),
                            np.asarray(
                                [right["metrics"][metric] for _, right in paired]
                            ),
                            n_repeats=options.outer_repeats,
                            n_folds=options.outer_splits,
                        ).to_dict()
                        effect["p_value_interpretation"] = "not_used_secondary"
                        effects[metric] = effect
                    calibration_effects = []
                    for horizon_index in range(3):
                        for parameter in (
                            "calibration_in_the_large",
                            "intercept",
                            "slope",
                        ):
                            effect = nadeau_bengio_paired_effect(
                                np.asarray(
                                    [
                                        left["metrics"]["calibration"][
                                            horizon_index
                                        ]["summary"][parameter]["estimate"]
                                        for left, _ in paired
                                    ]
                                ),
                                np.asarray(
                                    [
                                        right["metrics"]["calibration"][
                                            horizon_index
                                        ]["summary"][parameter]["estimate"]
                                        for _, right in paired
                                    ]
                                ),
                                n_repeats=options.outer_repeats,
                                n_folds=options.outer_splits,
                            ).to_dict()
                            effect["p_value_interpretation"] = "not_used_secondary"
                            calibration_effects.append(
                                {
                                    "horizon_index": horizon_index + 1,
                                    "parameter": parameter,
                                    "effect": effect,
                                }
                            )
                    benchmark["metric_effects"] = effects
                    benchmark["calibration_effects"] = calibration_effects
                    benchmark["runtime_seconds"] = {
                        "model_a_mean": float(
                            np.mean([left["total_seconds"] for left, _ in paired])
                        ),
                        "model_b_mean": float(
                            np.mean([right["total_seconds"] for _, right in paired])
                        ),
                    }
                else:
                    benchmark["status"] = "incomplete_no_secondary_estimate"
                secondary_benchmarks.append(benchmark)

    complete_primary = [row for row in primary if "ibs" in row]
    family_complete = len(complete_primary) == 9
    if family_complete:
        adjusted, rejected = holm_adjust(
            [row["ibs"]["p_value"] for row in complete_primary]
        )
        for row, adjusted_p, reject in zip(
            complete_primary, adjusted, rejected, strict=True
        ):
            row["holm_adjusted_p"] = adjusted_p
            row["holm_reject_0_05"] = reject
            interval = row["ibs"]
            row["superiority_language_permitted"] = bool(
                reject
                and (
                    interval["confidence_upper"] < 0
                    or interval["confidence_lower"] > 0
                )
            )
    return {
        "status": "complete" if family_complete else "incomplete",
        "primary_family": "nine within-cohort Bayesian-prior IBS contrasts",
        "holm_family_complete": family_complete,
        "primary": primary,
        "secondary_estimation": secondary,
        "secondary_benchmark_estimation": secondary_benchmarks,
    }


def relevant_input_files(project_root: Path, datasets: tuple[str, ...]) -> list[str]:
    """Return every code, configuration, environment and data input used here."""
    files = [
        "Makefile",
        "config/confirmatory.yaml",
        "config/datasets.yaml",
        "coordination/DECISIONS.md",
        "data/manifest.yaml",
        "docs/claim_evidence_register.md",
        "docs/study_protocol.md",
        "environment.yml",
        "pyproject.toml",
        "conda-lock.yml",
        "conda-lock.yml.sha256",
        "conda-lock-virtual-packages.yml",
        "scripts/verify_environment.py",
        "scripts/run_confirmatory_explainability.py",
        "scripts/run_confirmatory.py",
        "scripts/run_robustness.py",
        "scripts/freeze_protocol.py",
        "scripts/render_confirmatory.py",
        "src/data/fold_preprocessing.py",
        "src/data/survival_folds.py",
        "src/evaluation/calibration.py",
        "src/evaluation/metrics.py",
        "src/explainability/__init__.py",
        "src/explainability/frozen_cells.py",
        "src/explainability/posterior_analysis.py",
        "src/explainability/shap_analysis.py",
        "src/models/base.py",
        "src/models/cox.py",
        "src/models/deepsurv.py",
        "src/models/random_survival_forest.py",
        "src/models/bayesian/diagnostics.py",
        "src/models/bayesian/model.py",
        "src/pipelines/confirmatory.py",
        "src/pipelines/robustness.py",
        "src/statistics/bootstrap.py",
        "src/statistics/hypothesis_tests.py",
        "src/statistics/repeated_cv.py",
        "src/utils/reproducibility.py",
    ]
    # Importing a submodule executes its parent packages' ``__init__.py`` files,
    # and several compatibility initialisers import additional local modules.
    # Freeze every source module so no executed or transitively imported project
    # code can change while an otherwise valid content freeze still passes.
    files.extend(
        str(path.relative_to(project_root))
        for path in project_root.glob("src/**/*.py")
        if path.is_file()
    )
    dataset_config = _load_yaml(project_root / "config" / "datasets.yaml")
    files.extend(dataset_config[name]["raw_file"] for name in datasets)
    return sorted(set(files))


def verify_protocol_freeze(project_root: Path, inputs: list[str]) -> dict[str, Any]:
    """Verify the content-addressed protocol freeze before confirmatory fitting."""
    freeze_path = project_root / "config" / "protocol_freeze.json"
    if not freeze_path.is_file():
        raise RuntimeError("config/protocol_freeze.json is required for confirmatory mode")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    claimed = freeze.get("freeze_content_sha256")
    unhashed = dict(freeze)
    unhashed.pop("freeze_content_sha256", None)
    if claimed != canonical_json_hash(unhashed):
        raise RuntimeError("protocol freeze content hash is invalid")
    expected = freeze.get("frozen_input_sha256", {})
    verify_run_inputs_unchanged(project_root, expected, inputs, label="protocol freeze")
    if not freeze.get("no_comparative_effects_inspected_before_freeze", False):
        raise RuntimeError("protocol freeze lacks the result-blind rehearsal attestation")
    return freeze


def verify_run_inputs_unchanged(
    project_root: Path,
    expected: dict[str, str],
    inputs: list[str],
    *,
    label: str = "run manifest",
) -> None:
    """Fail if any content-addressed run input changed since it was recorded."""
    current = {
        relative: sha256_file(project_root / relative)
        if (project_root / relative).is_file()
        else "MISSING"
        for relative in inputs
    }
    if expected != current:
        changed = sorted(
            name
            for name in set(expected) | set(current)
            if expected.get(name) != current.get(name)
        )
        raise RuntimeError(
            f"confirmatory inputs differ from the {label}: " + ", ".join(changed)
        )


def execute_confirmatory_run(
    project_root: Path,
    config: dict[str, Any],
    dataset_config: dict[str, Any],
    options: RunOptions,
) -> Path:
    """Execute or resume the requested analysis and return its run directory."""
    if options.mode not in {"rehearsal", "confirmatory"}:
        raise ValueError("mode must be 'rehearsal' or 'confirmatory'")
    if not set(options.models).issubset(MODEL_KEYS):
        raise ValueError("models contain an unknown model key")

    actual_config = {
        "protocol": config,
        "mode": options.mode,
        "datasets": options.datasets,
        "models": options.models,
        "outer_splits": options.outer_splits,
        "outer_repeats": options.outer_repeats,
        "fold_limit_per_dataset": options.fold_limit_per_dataset,
        "bayes_draws": options.bayes_draws,
        "bayes_tune": options.bayes_tune,
        "bayes_chains": options.bayes_chains,
        "calibration_bootstraps": options.calibration_bootstraps,
    }
    run_hash = canonical_json_hash(actual_config)[:12]
    run_dir = options.output_root / f"{config['analysis_id']}_{options.mode}_{run_hash}"
    manifest_path = run_dir / "manifest.json"

    inputs = relevant_input_files(project_root, options.datasets)
    manifest = build_run_manifest(
        project_root,
        command=[sys.executable, *sys.argv],
        seeds={"outer_base": int(config["validation"]["base_seed"])},
        input_files=inputs,
        run_config=actual_config,
    )
    if options.mode == "confirmatory":
        freeze = verify_protocol_freeze(project_root, inputs)
        manifest["protocol_freeze_sha256"] = freeze["freeze_content_sha256"]
        manifest["manifest_content_sha256"] = canonical_json_hash(
            {key: value for key, value in manifest.items() if key != "manifest_content_sha256"}
        )
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing["config_sha256"] != manifest["config_sha256"]:
            raise RuntimeError("existing run directory has a different configuration")
        if existing["input_sha256"] != manifest["input_sha256"]:
            raise RuntimeError(
                "run inputs changed after the first checkpoint; start a new run "
                "instead of combining cells from different code, data or configs"
            )
        if not options.resume:
            raise FileExistsError(
                f"run already exists at {run_dir}; pass --resume to verify/continue it"
            )
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
        _atomic_json(manifest_path, manifest)

    total_planned = 0
    for dataset_key in options.datasets:
        if dataset_key not in dataset_config:
            raise ValueError(f"unknown dataset {dataset_key!r}")
        cohort_config = dataset_config[dataset_key]
        raw, times, events, subject_ids = load_analysis_dataset(
            project_root, dataset_key, cohort_config
        )
        feature_spec = _feature_spec(cohort_config, config["feature_set"])
        folds = repeated_survival_folds(
            times,
            events,
            n_splits=options.outer_splits,
            n_repeats=options.outer_repeats,
            base_seed=int(config["validation"]["base_seed"]),
            max_time_bins=int(config["validation"]["followup_time_bins"]),
        )
        if options.fold_limit_per_dataset is not None:
            folds = folds[: options.fold_limit_per_dataset]
        data_path = project_root / cohort_config["raw_file"]
        data_hash = sha256_file(data_path)
        for fold in folds:
            for model_key in options.models:
                total_planned += 1
                cell_path = _cell_path(run_dir, dataset_key, fold, model_key)
                if cell_path.exists():
                    continue
                cell = run_cell(
                    dataset_key,
                    model_key,
                    fold,
                    raw,
                    times,
                    events,
                    subject_ids,
                    feature_spec,
                    config=config,
                    options=options,
                    data_sha256=data_hash,
                )
                _atomic_json(cell_path, cell)
                print(
                    f"{dataset_key} repeat={fold.repeat} fold={fold.fold} "
                    f"model={model_key} status={cell['status']} "
                    f"seconds={cell['total_seconds']:.1f}",
                    flush=True,
                )

    recorded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verify_run_inputs_unchanged(
        project_root,
        recorded_manifest.get("input_sha256", {}),
        inputs,
    )
    if options.mode == "confirmatory":
        verify_protocol_freeze(project_root, inputs)

    cells = _load_cells(run_dir)
    _aggregate_tables(run_dir, cells)
    inference = _repeated_cv_inference(cells, options, config)
    _atomic_json(run_dir / "inference.json", inference)
    counts: dict[str, int] = {}
    for cell in cells:
        counts[cell["status"]] = counts.get(cell["status"], 0) + 1
    completion = {
        "schema_version": "1.0.0",
        "analysis_mode": options.mode,
        "planned_cells_in_this_invocation": total_planned,
        "stored_cells": len(cells),
        "status_counts": counts,
        "all_stored_cell_hashes": {
            str(path.relative_to(run_dir)): sha256_file(path)
            for path in sorted((run_dir / "cells").glob("*/*/*.json"))
        },
        "aggregate_sha256": {
            name: sha256_file(run_dir / name)
            for name in (
                "fold_metrics.csv",
                "out_of_fold_predictions.csv.gz",
                "inference.json",
            )
        },
    }
    # Check again after aggregation so a concurrent edit cannot be hidden by a
    # run that began from valid inputs but ended from different code or data.
    verify_run_inputs_unchanged(
        project_root,
        recorded_manifest.get("input_sha256", {}),
        inputs,
    )
    if options.mode == "confirmatory":
        verify_protocol_freeze(project_root, inputs)
    completion["completion_content_sha256"] = canonical_json_hash(completion)
    _atomic_json(run_dir / "completion.json", completion)
    return run_dir
