"""Fixed-horizon survival calibration for the outer-validation predictions.

Descriptive curves compare predicted survival with Kaplan-Meier estimates.
IPCW complementary-log-log models estimate calibration-in-the-large,
intercept and slope, with event-stratified bootstrap intervals.
"""

from typing import Any

import numpy as np
from sksurv.nonparametric import CensoringDistributionEstimator, kaplan_meier_estimator
from sksurv.util import Surv

from src.evaluation.calibration_model import (
    _cloglog_probability,  # noqa: F401 - retained for callers of the original helper
    _fit_weighted_calibration,
)
from src.evaluation.metrics import UnsupportedCensoringError, validate_ipcw_horizons
from src.statistics.resampling import event_stratified_indices


def _survival_array(
    time: np.ndarray, event: np.ndarray, *, name: str
) -> tuple[np.ndarray, np.ndarray]:
    time_array = np.asarray(time, dtype=float)
    event_array = np.asarray(event)
    if time_array.ndim != 1 or event_array.ndim != 1:
        raise ValueError(f"{name} time and event must be one-dimensional.")
    if len(time_array) == 0 or len(time_array) != len(event_array):
        raise ValueError(f"{name} time and event must have equal non-zero length.")
    if not np.isfinite(time_array).all() or np.any(time_array < 0):
        raise ValueError(f"{name} times must be finite and non-negative.")
    if not np.isin(event_array, (0, 1, False, True)).all():
        raise ValueError(f"{name} event must contain only 0/1 values.")
    return time_array, event_array.astype(bool)


def _prediction_array(pred_survival: np.ndarray, n_samples: int) -> np.ndarray:
    predictions = np.asarray(pred_survival, dtype=float)
    if predictions.ndim != 1 or len(predictions) != n_samples:
        raise ValueError(f"pred_survival must be one-dimensional with length {n_samples}.")
    if not np.isfinite(predictions).all() or np.any((predictions < 0) | (predictions > 1)):
        raise ValueError("pred_survival must contain finite probabilities in [0, 1].")
    return predictions


def _step_value(times: np.ndarray, values: np.ndarray, horizon: float, *, initial: float) -> float:
    index = int(np.searchsorted(times, horizon, side="right") - 1)
    return initial if index < 0 else float(values[index])


class KaplanMeierSurvivalEstimator:
    """Small compatibility wrapper around scikit-survival Kaplan-Meier."""

    def __init__(self) -> None:
        self.times = np.array([], dtype=float)
        self.survival_probs = np.array([], dtype=float)

    def fit(self, y_time: np.ndarray, y_event: np.ndarray) -> "KaplanMeierSurvivalEstimator":
        time, event = _survival_array(y_time, y_event, name="Evaluation")
        self.times, self.survival_probs = kaplan_meier_estimator(event, time)
        return self

    def predict(self, eval_times: np.ndarray) -> np.ndarray:
        horizons = np.asarray(eval_times, dtype=float)
        if horizons.ndim != 1 or not np.isfinite(horizons).all():
            raise ValueError("eval_times must be a finite one-dimensional array.")
        return np.asarray(
            [
                _step_value(self.times, self.survival_probs, value, initial=1.0)
                for value in horizons
            ],
            dtype=float,
        )


def survival_calibration_curve(
    y_time: np.ndarray,
    y_event: np.ndarray,
    pred_survival: np.ndarray,
    horizon: float,
    *,
    n_bins: int = 5,
    confidence_level: float = 0.95,
    min_bin_size: int = 5,
) -> dict[str, Any]:
    """Quantile-binned survival calibration curve with Kaplan-Meier intervals.

    Within each prediction bin, observed survival at ``horizon`` is estimated
    by Kaplan-Meier. The log-log confidence interval is the one implemented by
    scikit-survival. Bins are descriptive; formal calibration parameters are
    provided by :func:`survival_calibration_summary`.
    """
    time, event = _survival_array(y_time, y_event, name="Evaluation")
    predictions = _prediction_array(pred_survival, len(time))
    if not np.isfinite(horizon) or horizon <= 0:
        raise ValueError("horizon must be finite and positive.")
    if horizon >= np.max(time):
        raise ValueError("horizon must be earlier than the maximum evaluation follow-up.")
    if n_bins < 2:
        raise ValueError("n_bins must be at least 2.")
    if min_bin_size < 2 or n_bins * min_bin_size > len(time):
        raise ValueError("Requested bins cannot satisfy min_bin_size.")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must lie strictly between 0 and 1.")

    order = np.argsort(predictions, kind="stable")
    bins = np.array_split(order, n_bins)
    rows: list[dict[str, float | int]] = []
    for bin_number, indices in enumerate(bins, start=1):
        if len(indices) < min_bin_size:
            raise ValueError("A calibration bin is smaller than min_bin_size.")
        km_time, km_survival, km_ci = kaplan_meier_estimator(
            event[indices],
            time[indices],
            conf_level=confidence_level,
            conf_type="log-log",
        )
        observed = _step_value(km_time, km_survival, horizon, initial=1.0)
        lower = _step_value(km_time, km_ci[0], horizon, initial=1.0)
        upper = _step_value(km_time, km_ci[1], horizon, initial=1.0)
        rows.append(
            {
                "bin": bin_number,
                "n": len(indices),
                "mean_predicted_survival": float(np.mean(predictions[indices])),
                "observed_survival": observed,
                "observed_lower": lower,
                "observed_upper": upper,
            }
        )
    return {
        "horizon": float(horizon),
        "confidence_level": float(confidence_level),
        "bins": rows,
    }


def compute_calibration_curve(
    y_time: np.ndarray,
    y_event: np.ndarray,
    pred_surv: np.ndarray,
    eval_time: float,
    n_bins: int = 5,
) -> tuple[np.ndarray, np.ndarray]:
    """Backward-compatible predicted/observed calibration curve arrays."""
    result = survival_calibration_curve(
        y_time,
        y_event,
        pred_surv,
        eval_time,
        n_bins=n_bins,
        min_bin_size=2,
    )
    predicted = np.asarray([row["mean_predicted_survival"] for row in result["bins"]], dtype=float)
    observed = np.asarray([row["observed_survival"] for row in result["bins"]], dtype=float)
    return predicted, observed


def _ipcw_binary_outcome(
    train_time: np.ndarray,
    train_event: np.ndarray,
    test_time: np.ndarray,
    test_event: np.ndarray,
    horizon: float,
) -> tuple[np.ndarray, np.ndarray]:
    """IPCW event-by-horizon outcome and weights.

    Observed events by the horizon receive ``1/G(T-)``; subjects known to be
    event-free beyond the horizon receive ``1/G(horizon)``; subjects censored
    by the horizon have weight zero because their binary outcome is unknown.
    """
    validate_ipcw_horizons(train_time, train_event, [horizon])
    estimator = CensoringDistributionEstimator().fit(
        Surv.from_arrays(event=train_event, time=train_time)
    )
    y = ((test_event) & (test_time <= horizon)).astype(float)
    weights = np.zeros(len(test_time), dtype=float)

    cases = (test_event) & (test_time <= horizon)
    controls = test_time > horizon
    if cases.any():
        just_before = np.nextafter(test_time[cases], -np.inf)
        try:
            case_g = np.asarray(estimator.predict_proba(just_before), dtype=float)
        except ValueError as exc:
            raise UnsupportedCensoringError(
                "Training censoring survival does not support an observed event time."
            ) from exc
        if np.any(case_g <= 0):
            raise UnsupportedCensoringError(
                "Training censoring survival is zero at an observed event time."
            )
        weights[cases] = 1.0 / case_g

    if controls.any():
        horizon_g = float(estimator.predict_proba(np.asarray([horizon]))[0])
        if horizon_g <= 0:
            raise UnsupportedCensoringError(
                "Training censoring survival is zero at the calibration horizon."
            )
        weights[controls] = 1.0 / horizon_g
    return y, weights


_event_stratified_indices = event_stratified_indices


def _calibration_point_estimate(
    train_time: np.ndarray,
    train_event: np.ndarray,
    test_time: np.ndarray,
    test_event: np.ndarray,
    pred_survival: np.ndarray,
    horizon: float,
) -> dict[str, float]:
    y, weights = _ipcw_binary_outcome(train_time, train_event, test_time, test_event, horizon)
    clipped_survival = np.clip(pred_survival, 1e-12, 1 - 1e-12)
    log_cumulative_hazard = np.log(-np.log(clipped_survival))
    return _fit_weighted_calibration(log_cumulative_hazard, y, weights)


def survival_calibration_summary(
    train_time: np.ndarray,
    train_event: np.ndarray,
    test_time: np.ndarray,
    test_event: np.ndarray,
    pred_survival: np.ndarray,
    horizon: float,
    *,
    n_bootstraps: int = 500,
    confidence_level: float = 0.95,
    random_state: int = 42,
) -> dict[str, Any]:
    """IPCW calibration-in-the-large, intercept, and slope with bootstrap CIs.

    The complementary-log-log calibration model uses
    ``x = log(-log(predicted survival))``. Calibration-in-the-large is the
    intercept from a model with slope fixed at one. ``intercept`` and ``slope``
    are jointly estimated; ideal values are zero and one. Event-stratified
    bootstrap resampling is paired with predictions and resamples the training
    set separately so uncertainty in the censoring distribution is represented.
    """
    train_t, train_e = _survival_array(train_time, train_event, name="Training")
    test_t, test_e = _survival_array(test_time, test_event, name="Evaluation")
    predictions = _prediction_array(pred_survival, len(test_t))
    if not np.isfinite(horizon) or horizon <= 0:
        raise ValueError("horizon must be finite and positive.")
    if horizon >= np.max(test_t):
        raise ValueError("horizon must be earlier than the maximum evaluation follow-up.")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must lie strictly between 0 and 1.")
    if n_bootstraps < 20:
        raise ValueError("n_bootstraps must be at least 20.")

    point = _calibration_point_estimate(train_t, train_e, test_t, test_e, predictions, horizon)
    rng = np.random.default_rng(random_state)
    samples: dict[str, list[float]] = {
        "calibration_in_the_large": [],
        "intercept": [],
        "slope": [],
    }
    for _ in range(n_bootstraps):
        train_indices = _event_stratified_indices(train_e, rng)
        test_indices = _event_stratified_indices(test_e, rng)
        try:
            estimate = _calibration_point_estimate(
                train_t[train_indices],
                train_e[train_indices],
                test_t[test_indices],
                test_e[test_indices],
                predictions[test_indices],
                horizon,
            )
        except (RuntimeError, UnsupportedCensoringError, ValueError):
            continue
        for key in samples:
            samples[key].append(estimate[key])

    successful = len(samples["slope"])
    required = max(20, int(np.ceil(0.8 * n_bootstraps)))
    if successful < required:
        raise RuntimeError(
            f"Only {successful} of {n_bootstraps} calibration bootstrap replicates "
            f"were estimable; at least {required} are required."
        )
    alpha = 1 - confidence_level
    result: dict[str, Any] = {
        "horizon": float(horizon),
        "n": len(test_t),
        "n_known": point["n_known"],
        "effective_weight": point["effective_weight"],
        "confidence_level": float(confidence_level),
        "n_bootstrap_successful": successful,
    }
    for key, values in samples.items():
        lower, upper = np.quantile(values, [alpha / 2, 1 - alpha / 2])
        result[key] = {
            "estimate": point[key],
            "lower": float(lower),
            "upper": float(upper),
        }
    return result
