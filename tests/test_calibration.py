"""Fixed-horizon survival calibration tests.

Covers ``src/evaluation/calibration.py`` and the weighted fits in
``calibration_model.py``: Kaplan-Meier (KM) binned calibration curves, and
calibration-in-the-large, intercept and slope from complementary-log-log
(cloglog) models with inverse probability of censoring weights (IPCW), the
calibration estimands chosen in ADR-017. Simulated exponential data with a
known survival function show that the estimators recover ideal and shifted
calibration.
"""

import numpy as np
import pytest

from src.evaluation.calibration import (
    compute_calibration_curve,
    survival_calibration_curve,
    survival_calibration_summary,
)


def _exponential_sample(rng: np.random.Generator, n: int):
    """Simulate ``(predictor, time, event)`` for n subjects with hazard exp(predictor)."""
    # True survival is S(t | x) = exp(-exp(x) t), so exp(-exp(x) * horizon) is
    # perfectly calibrated at any horizon. Censoring is independent and
    # exponential with mean 4.
    predictor = rng.normal(size=n)
    event_time = rng.exponential(scale=np.exp(-predictor))
    censor_time = rng.exponential(scale=4.0, size=n)
    time = np.minimum(event_time, censor_time)
    event = event_time <= censor_time
    return predictor, time, event


def test_calibration_curve_reports_km_intervals():
    """Bins cover all subjects, KM intervals bracket their estimates, legacy arrays hold one per bin."""
    rng = np.random.default_rng(21)
    predictor, time, event = _exponential_sample(rng, 1200)
    horizon = 0.8
    predicted = np.exp(-np.exp(predictor) * horizon)
    result = survival_calibration_curve(
        time, event, predicted, horizon, n_bins=6, min_bin_size=20
    )
    assert result["horizon"] == horizon
    assert len(result["bins"]) == 6
    assert sum(row["n"] for row in result["bins"]) == len(time)
    for row in result["bins"]:
        assert 0 <= row["mean_predicted_survival"] <= 1
        assert 0 <= row["observed_lower"] <= row["observed_survival"]
        assert row["observed_survival"] <= row["observed_upper"] <= 1

    predicted_curve, observed_curve = compute_calibration_curve(
        time, event, predicted, horizon, n_bins=6
    )
    assert predicted_curve.shape == observed_curve.shape == (6,)


def test_well_calibrated_cloglog_model_recovers_ideal_parameters():
    """True survival gives intercepts near 0, slope near 1 and ordered intervals (ADR-017)."""
    rng = np.random.default_rng(22)
    # The training sample supplies only the censoring distribution for IPCW.
    _, train_time, train_event = _exponential_sample(rng, 2500)
    predictor, test_time, test_event = _exponential_sample(rng, 2500)
    horizon = 0.8
    predicted = np.exp(-np.exp(predictor) * horizon)
    result = survival_calibration_summary(
        train_time,
        train_event,
        test_time,
        test_event,
        predicted,
        horizon,
        n_bootstraps=40,
        random_state=7,
    )
    assert abs(result["calibration_in_the_large"]["estimate"]) < 0.15
    assert abs(result["intercept"]["estimate"]) < 0.2
    assert result["slope"]["estimate"] == pytest.approx(1.0, abs=0.2)
    for name in ("calibration_in_the_large", "intercept", "slope"):
        assert result[name]["lower"] < result[name]["upper"]
    assert result["n_bootstrap_successful"] == 40


def test_calibration_in_the_large_detects_underpredicted_hazard():
    """Halving the predicted cumulative hazard moves calibration-in-the-large to about log 2."""
    rng = np.random.default_rng(23)
    _, train_time, train_event = _exponential_sample(rng, 3000)
    predictor, test_time, test_event = _exponential_sample(rng, 3000)
    horizon = 0.8
    predicted = np.exp(-0.5 * np.exp(predictor) * horizon)
    result = survival_calibration_summary(
        train_time,
        train_event,
        test_time,
        test_event,
        predicted,
        horizon,
        n_bootstraps=30,
        random_state=8,
    )
    # Predicted cumulative hazard is half the data-generating hazard. On the
    # cloglog scale log(-log S) = log H, so the ideal offset is log(2).
    assert result["calibration_in_the_large"]["estimate"] == pytest.approx(
        np.log(2), abs=0.15
    )


def test_calibration_rejects_horizon_without_outcome_classes():
    """Calibration raises ValueError when no subject has an event by the horizon."""
    # Every time is at least 1.0, beyond the 0.5 horizon, so all known
    # outcomes are event-free and the binary outcome has one class.
    time = np.arange(1.0, 31.0)
    event = np.ones(30, dtype=int)
    predictions = np.full(30, 0.8)
    with pytest.raises(ValueError, match="both classes"):
        survival_calibration_summary(
            time,
            event,
            time,
            event,
            predictions,
            0.5,
            n_bootstraps=20,
        )
