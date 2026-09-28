"""Score one fitted model on its outer-validation fold.

After a cell's model is fitted on the outer-training fold, this module chooses
the evaluation times from the training data alone, predicts risk and survival
for the validation subjects, and computes discrimination, the integrated Brier
score (IBS) and calibration. :mod:`cells` stores the result; inner-fold tuning
and the robustness pipeline use the same horizons, grid and truncation rule.

Several metrics use inverse probability of censoring weighting (IPCW): each
validation subject is weighted by the inverse of the training-fold
Kaplan–Meier estimate of the censoring survival function G(t), so that subjects
whose status is hidden by censoring are represented by observed subjects with
similar follow-up. The weights are only reliable where G(t) is well above
zero, which is why every evaluation time must have enough training censoring
support.

Entry points: :func:`evaluation_horizons_and_grid`,
:func:`administratively_truncate_for_ipcw`,
:func:`validate_survival_prediction_matrix` and :func:`evaluate_predictions`.
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
    (``horizon_event_quantiles``; the 25th, 50th and 75th percentiles in the
    frozen protocol), with duplicates removed. The grid has
    ``ibs_grid_points`` (25) equally spaced times from the first to the last
    horizon. Every time must have training censoring survival G(t) above
    ``minimum_censoring_survival`` (0.10), so that IPCW weights stay bounded.

    Args:
        train_time: Training follow-up times in the cohort's own unit.
        train_event: Training event indicators (1 = event, 0 = censored).
        evaluation_config: The ``evaluation`` section of
            ``config/confirmatory.yaml``.

    Returns:
        ``(horizons, grid)``, both increasing arrays of times. The last grid
        time equals the last horizon.

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
    # The IBS averages the Brier score over this grid, which spans the first
    # to the last horizon as the protocol prescribes. ``linspace`` sets the
    # last point to the last horizon exactly, so truncating follow-up at the
    # last horizon or at the last grid time is the same rule.
    grid = np.linspace(
        float(horizons[0]),
        float(horizons[-1]),
        int(evaluation_config["ibs_grid_points"]),
    )
    # Defensive: G(t) is non-increasing, so grid points between supported
    # horizons are supported too; the check makes that explicit per point.
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
    not modified. Only IPCW metrics use the truncated follow-up; Harrell's
    C-index and calibration keep the observed follow-up.

    Args:
        time_values: Follow-up times, one per subject.
        event_values: Event indicators (1 = event, 0 = censored).
        tau: Truncation time; the last training-derived horizon.

    Returns:
        ``(times, events)`` after truncation.

    Raises:
        ValueError: ``tau`` is not finite and positive.
    """
    times = np.asarray(time_values, dtype=float).copy()
    events = np.asarray(event_values, dtype=int).copy()
    if not np.isfinite(tau) or tau <= 0:
        raise ValueError("IPCW truncation time must be finite and positive")
    # The reference IPCW estimators evaluate G at every validation time, and
    # G is undefined beyond the training follow-up. A subject still at risk
    # at ``tau`` counts as event-free at every evaluation time either way, so
    # censoring just after ``tau`` changes no status inside the window.
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

    Returns:
        None; valid input is left unchanged.

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
    follow-up. Uno's C-index, time-dependent area under the receiver operating
    characteristic curve (AUC) and the integrated Brier score use follow-up censored at the last horizon (see
    :func:`administratively_truncate_for_ipcw`), with censoring weights from
    the training fold.

    The risk scale differs between models: exp(linear predictor) for Cox proportional
    hazards (PH),
    ensemble cumulative hazard for the random survival forest, log-risk for
    DeepSurv, and the posterior-mean linear predictor for the Bayesian model.
    Only its ordering enters the C-indices and AUC.

    Args:
        model: A fitted model with ``predict_risk`` and ``predict_survival``.
        x_validation: Preprocessed validation features, shape (subjects, features).
        train_time: Outer-training follow-up times in the cohort's unit.
        train_event: Outer-training event indicators.
        validation_time: Outer-validation follow-up times in the same unit.
        validation_event: Outer-validation event indicators.
        evaluation_config: The ``evaluation`` section of ``config/confirmatory.yaml``.
        calibration_bootstraps: Bootstrap replicates for each calibration interval.
        seed: Cell seed; each horizon's calibration bootstrap derives its own seed.

    Returns:
        ``(metrics, predictions)``. ``metrics`` holds the scalar metrics, the
        AUC at each horizon, the horizons and grid, and one calibration
        summary and curve per horizon. ``predictions`` holds the risk scores
        and the predicted survival matrices of shape (validation subjects,
        evaluation times), at the horizons and on the grid.

    Raises:
        ValueError: The training fold cannot support the horizons, or the
            survival predictions fail :func:`validate_survival_prediction_matrix`.
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
    """Predict risk separately and obtain horizon and grid survival in one survival call.

    Returns:
        ``(risk, horizon_survival, grid_survival)``: one risk score per
        subject, and survival arrays of shape (subjects, horizons) and
        (subjects, grid times).
    """
    # One survival prediction on the sorted union of times; ``searchsorted``
    # then finds each horizon and grid time exactly, so a horizon that is also
    # a grid point gets the identical value in both arrays.
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
    """Return the C-indices, AUC, integrated Brier score and the times they used.

    Harrell's C-index uses the observed validation follow-up. Uno's C-index
    (truncated at ``tau``), the cumulative/dynamic AUC at each horizon and the
    IBS use the truncated ``ipcw_time``/``ipcw_event`` with training
    censoring weights. ``tau`` is the last horizon.
    """
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
    """Return a calibration summary (with bootstrap intervals) and a binned curve per horizon.

    Calibration uses the observed, untruncated validation follow-up. The
    summary holds calibration-in-the-large, intercept and slope from the
    complementary-log-log calibration model; each horizon's bootstrap has its
    own seed derived from the cell seed and the horizon index.
    """
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
