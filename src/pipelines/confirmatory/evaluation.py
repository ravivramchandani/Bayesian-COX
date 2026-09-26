"""Score one fitted model on its outer-validation fold.

After a cell's model is fitted on the outer-training fold, this module chooses
the evaluation times from the training data alone, predicts risk and survival
for the validation subjects, and computes discrimination, integrated Brier
score and calibration. Inner-fold tuning uses the same time grid.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

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
from src.pipelines.confirmatory.options import deterministic_seed


def evaluation_horizons_and_grid(
    train_time: np.ndarray,
    train_event: np.ndarray,
    evaluation_config: dict[str, Any],
) -> tuple[np.ndarray, np.ndarray]:
    """Choose evaluation horizons and the integrated Brier grid from training data.

    The horizons are quantiles of the training event times
    (``horizon_event_quantiles``), with duplicates removed. The grid has
    ``ibs_grid_points`` equally spaced times from the first to the last
    horizon. Every time must have training censoring survival G(t) above
    ``minimum_censoring_survival``, so that IPCW weights stay bounded.

    Returns:
        ``(horizons, grid)``, both increasing arrays of times.

    Raises:
        UnsupportedCensoringError: A horizon or grid time has too little
            censoring support (a ``ValueError`` subclass).
    """
    horizons = training_event_time_horizons(
        train_time,
        train_event,
        quantiles=evaluation_config["horizon_event_quantiles"],
        min_censoring_survival=float(evaluation_config["minimum_censoring_survival"]),
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
        min_censoring_survival=float(evaluation_config["minimum_censoring_survival"]),
    )
    return horizons, grid


def administratively_truncate_for_ipcw(
    time_values: np.ndarray,
    event_values: np.ndarray,
    tau: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Censor follow-up after a training-derived IPCW boundary ``tau``.

    Subjects followed beyond ``tau`` become censored at the next float above
    ``tau``. That keeps them known to be event-free through the last
    evaluation time, and satisfies reference estimators that require every
    evaluation time to lie below the maximum follow-up. The inputs are copied,
    not modified.
    """
    times = np.asarray(time_values, dtype=float).copy()
    events = np.asarray(event_values, dtype=int).copy()
    if not np.isfinite(tau) or tau <= 0:
        raise ValueError("IPCW truncation time must be finite and positive")
    after = times > tau
    times[after] = np.nextafter(float(tau), np.inf)
    events[after] = 0
    return times, events


def validate_survival_prediction_matrix(
    survival: np.ndarray,
    *,
    n_samples: int,
    n_times: int,
    tolerance: float = 1e-8,
) -> None:
    """Reject a survival matrix that is misshapen, non-finite, outside [0, 1] or increasing.

    Args:
        survival: Predicted survival, one row per subject and one column per time.
        n_samples: Expected number of rows.
        n_times: Expected number of columns.
        tolerance: Slack allowed for the range and monotonicity checks.

    Raises:
        ValueError: Any check fails.
    """
    values = np.asarray(survival, dtype=float)
    if values.shape != (n_samples, n_times):
        raise ValueError(
            f"survival prediction shape must be {(n_samples, n_times)}, got {values.shape}"
        )
    if not np.isfinite(values).all():
        raise ValueError("survival predictions must be finite")
    if np.any(values < -tolerance) or np.any(values > 1.0 + tolerance):
        raise ValueError("survival predictions must lie in [0, 1]")
    if np.any(np.diff(values, axis=1) > tolerance):
        raise ValueError("survival predictions must be non-increasing over time")


def evaluate_predictions(
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
    """Compute a fitted model's outer-validation metrics and stored predictions.

    The model predicts a risk score and a survival curve for each validation
    subject. Harrell's C-index and calibration use the observed validation
    follow-up. Uno's C-index, time-dependent AUC and the integrated Brier
    score use follow-up censored at the last horizon (see
    :func:`administratively_truncate_for_ipcw`), with censoring weights from
    the training fold.

    The risk scale differs between models: exp(linear predictor) for Cox PH,
    ensemble cumulative hazard for the random survival forest, log-risk for
    DeepSurv, and the posterior-mean linear predictor for the Bayesian model.
    Only its ordering enters the C-indices and AUC.

    Args:
        model: A fitted model with ``predict_risk`` and ``predict_survival``.
        x_validation: Preprocessed validation features.
        train_time: Outer-training follow-up times.
        train_event: Outer-training event indicators.
        validation_time: Outer-validation follow-up times.
        validation_event: Outer-validation event indicators.
        evaluation_config: The ``evaluation`` section of ``config/confirmatory.yaml``.
        calibration_bootstraps: Bootstrap replicates for each calibration interval.
        seed: Cell seed; each horizon's calibration bootstrap derives its own seed.

    Returns:
        ``(metrics, predictions)``. ``metrics`` holds the scalar metrics, the
        AUC at each horizon, the horizons and grid, and one calibration
        summary and curve per horizon. ``predictions`` holds the risk scores
        and the predicted survival at the horizons and on the grid.
    """
    horizons, ibs_grid = evaluation_horizons_and_grid(train_time, train_event, evaluation_config)
    risk, horizon_survival, grid_survival = _predict_risk_and_survival(
        model, x_validation, horizons, ibs_grid
    )
    tau = float(horizons[-1])
    ipcw_time, ipcw_event = administratively_truncate_for_ipcw(
        validation_time, validation_event, tau
    )
    metrics = _discrimination_and_brier_metrics(
        train_time,
        train_event,
        validation_time,
        validation_event,
        ipcw_time,
        ipcw_event,
        risk,
        grid_survival,
        horizons=horizons,
        ibs_grid=ibs_grid,
    )
    metrics["calibration"] = _calibration_at_horizons(
        train_time,
        train_event,
        validation_time,
        validation_event,
        horizon_survival,
        horizons,
        evaluation_config=evaluation_config,
        calibration_bootstraps=calibration_bootstraps,
        seed=seed,
    )
    predictions = {
        "risk": risk,
        "horizons": horizons,
        "survival_at_horizons": horizon_survival,
        "ibs_grid": ibs_grid,
        "survival_on_ibs_grid": grid_survival,
    }
    return metrics, predictions


def _predict_risk_and_survival(
    model: Any, x_validation: pd.DataFrame, horizons: np.ndarray, ibs_grid: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Predict risk scores and survival at the horizons and on the grid in one call."""
    prediction_times = np.unique(np.concatenate([horizons, ibs_grid]))
    risk = np.asarray(model.predict_risk(x_validation), dtype=float)
    survival = np.asarray(model.predict_survival(x_validation, prediction_times), dtype=float)
    validate_survival_prediction_matrix(
        survival, n_samples=len(x_validation), n_times=len(prediction_times)
    )
    horizon_survival = survival[:, np.searchsorted(prediction_times, horizons)]
    grid_survival = survival[:, np.searchsorted(prediction_times, ibs_grid)]
    return risk, horizon_survival, grid_survival


def _discrimination_and_brier_metrics(
    train_time: np.ndarray,
    train_event: np.ndarray,
    validation_time: np.ndarray,
    validation_event: np.ndarray,
    ipcw_time: np.ndarray,
    ipcw_event: np.ndarray,
    risk: np.ndarray,
    grid_survival: np.ndarray,
    *,
    horizons: np.ndarray,
    ibs_grid: np.ndarray,
) -> dict[str, Any]:
    """Return the C-indices, AUC, integrated Brier score and the times they used."""
    tau = float(horizons[-1])
    auc, mean_auc = time_dependent_auc(
        train_time, train_event, ipcw_time, ipcw_event, risk, horizons
    )
    return {
        "harrell_c_index": harrell_c_index(validation_time, validation_event, risk),
        "uno_c_index": uno_c_index(train_time, train_event, ipcw_time, ipcw_event, risk, tau=tau),
        "uno_tau": tau,
        "ipcw_administrative_truncation_tau": tau,
        "ibs": integrated_brier(
            train_time, train_event, ipcw_time, ipcw_event, grid_survival, ibs_grid
        ),
        "mean_auc": mean_auc,
        "auc_at_horizons": auc,
        "horizons": horizons,
        "ibs_grid": ibs_grid,
    }


def _calibration_at_horizons(
    train_time: np.ndarray,
    train_event: np.ndarray,
    validation_time: np.ndarray,
    validation_event: np.ndarray,
    horizon_survival: np.ndarray,
    horizons: np.ndarray,
    *,
    evaluation_config: dict[str, Any],
    calibration_bootstraps: int,
    seed: int,
) -> list[dict[str, Any]]:
    """Return a calibration summary (with bootstrap intervals) and a binned curve per horizon."""
    confidence_level = float(evaluation_config["confidence_level"])
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
            confidence_level=confidence_level,
            random_state=deterministic_seed(seed, "calibration", index),
        )
        curve = survival_calibration_curve(
            validation_time,
            validation_event,
            horizon_survival[:, index],
            float(horizon),
            n_bins=int(evaluation_config["calibration_bins"]),
            confidence_level=confidence_level,
        )
        calibration.append({"summary": summary, "curve": curve})
    return calibration
