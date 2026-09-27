"""Evaluate robustness predictions with the confirmatory IPCW truncation rule."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sksurv.nonparametric import CensoringDistributionEstimator

from src.evaluation.metrics import (
    harrell_c_index,
    integrated_brier,
    time_dependent_auc,
    uno_c_index,
)
from src.pipelines.confirmatory import (
    _ibs_times,
    administratively_truncate_for_ipcw,
    validate_survival_prediction_matrix,
)


def _as_structured(times: np.ndarray, events: np.ndarray) -> np.ndarray:
    outcome = np.empty(len(times), dtype=[("event", "?"), ("time", "<f8")])
    outcome["event"] = np.asarray(events, dtype=bool)
    outcome["time"] = np.asarray(times, dtype=float)
    return outcome


def individual_integrated_brier_losses(
    train_time: np.ndarray,
    train_event: np.ndarray,
    validation_time: np.ndarray,
    validation_event: np.ndarray,
    survival_probabilities: np.ndarray,
    evaluation_times: np.ndarray,
) -> np.ndarray:
    """Return subject contributions whose mean equals reference IPCW IBS."""
    train_t = np.asarray(train_time, dtype=float)
    train_e = np.asarray(train_event, dtype=int)
    valid_t = np.asarray(validation_time, dtype=float)
    valid_e = np.asarray(validation_event, dtype=int)
    predictions = np.asarray(survival_probabilities, dtype=float)
    grid = np.asarray(evaluation_times, dtype=float)
    if predictions.shape != (len(valid_t), len(grid)):
        raise ValueError("survival probabilities do not match validation rows/grid")
    if len(grid) < 2 or np.any(np.diff(grid) <= 0):
        raise ValueError("evaluation times must contain at least two increasing values")
    valid_t, valid_e = administratively_truncate_for_ipcw(valid_t, valid_e, float(grid[-1]))

    censoring = CensoringDistributionEstimator().fit(_as_structured(train_t, train_e))
    censoring_at_grid = censoring.predict_proba(grid)
    censoring_at_observation = censoring.predict_proba(valid_t)
    censoring_at_grid[censoring_at_grid == 0] = np.inf
    censoring_at_observation[censoring_at_observation == 0] = np.inf

    contributions = np.empty_like(predictions, dtype=float)
    for column, horizon in enumerate(grid):
        probability = predictions[:, column]
        cases = (valid_t <= horizon) & valid_e.astype(bool)
        controls = valid_t > horizon
        contributions[:, column] = (
            probability**2 * cases / censoring_at_observation
            + (1.0 - probability) ** 2 * controls / censoring_at_grid[column]
        )
    return np.trapezoid(contributions, grid, axis=1) / (grid[-1] - grid[0])


def summarize_imputation_predictions(
    train_time: np.ndarray,
    train_event: np.ndarray,
    validation_time: np.ndarray,
    validation_event: np.ndarray,
    risk: np.ndarray,
    survival_on_ibs_grid: np.ndarray,
    ibs_grid: np.ndarray,
    horizons: np.ndarray,
) -> dict[str, Any]:
    """Evaluate one imputation with the confirmatory IPCW truncation rule."""
    horizon_values = np.asarray(horizons, dtype=float)
    tau = float(horizon_values[-1])
    ipcw_time, ipcw_event = administratively_truncate_for_ipcw(
        validation_time, validation_event, tau
    )
    risk_values = np.asarray(risk, dtype=float)
    losses = individual_integrated_brier_losses(
        train_time,
        train_event,
        ipcw_time,
        ipcw_event,
        survival_on_ibs_grid,
        ibs_grid,
    )
    auc, mean_auc = time_dependent_auc(
        train_time,
        train_event,
        ipcw_time,
        ipcw_event,
        risk_values,
        horizon_values,
    )
    return {
        "ibs": float(np.mean(losses)),
        "harrell_c_index": harrell_c_index(validation_time, validation_event, risk_values),
        "uno_c_index": uno_c_index(
            train_time,
            train_event,
            ipcw_time,
            ipcw_event,
            risk_values,
            tau=tau,
        ),
        "auc_at_horizons": auc,
        "mean_auc": mean_auc,
        "ipcw_administrative_truncation_tau": tau,
    }


def evaluate_robustness_predictions(
    model: Any,
    x_validation: pd.DataFrame,
    train_time: np.ndarray,
    train_event: np.ndarray,
    validation_time: np.ndarray,
    validation_event: np.ndarray,
    *,
    evaluation_config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Evaluate frozen IBS sensitivities without calibration refitting/bootstrap.

    Calibration belongs to the full 5x5 confirmatory analysis. Robustness cells
    preserve the primary IBS estimand plus discrimination descriptors and do
    not spend compute re-estimating calibration in every sensitivity cell.
    """
    horizons, ibs_grid = _ibs_times(train_time, train_event, evaluation_config)
    prediction_times = np.unique(np.concatenate([horizons, ibs_grid]))
    risk = np.asarray(model.predict_risk(x_validation), dtype=float)
    survival = np.asarray(model.predict_survival(x_validation, prediction_times), dtype=float)
    validate_survival_prediction_matrix(
        survival, n_samples=len(x_validation), n_times=len(prediction_times)
    )
    horizon_indices = np.searchsorted(prediction_times, horizons)
    grid_indices = np.searchsorted(prediction_times, ibs_grid)
    horizon_survival = survival[:, horizon_indices]
    grid_survival = survival[:, grid_indices]
    tau = float(horizons[-1])
    ipcw_time, ipcw_event = administratively_truncate_for_ipcw(
        validation_time, validation_event, tau
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
        "harrell_c_index": harrell_c_index(validation_time, validation_event, risk),
        "uno_c_index": uno_c_index(
            train_time,
            train_event,
            ipcw_time,
            ipcw_event,
            risk,
            tau=tau,
        ),
        "uno_tau": tau,
        "ipcw_administrative_truncation_tau": tau,
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
        "calibration": {
            "status": "not_reestimated_in_ibs_robustness_sensitivity",
            "bootstrap_replicates": 0,
            "source": "full 5x5 confirmatory analysis",
        },
    }
    predictions = {
        "risk": risk,
        "horizons": horizons,
        "survival_at_horizons": horizon_survival,
        "ibs_grid": ibs_grid,
        "survival_on_ibs_grid": grid_survival,
    }
    return metrics, predictions
