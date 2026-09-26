"""Metric correctness against reference implementations and known values."""

import numpy as np
import pytest
from sksurv.metrics import (
    concordance_index_censored,
    concordance_index_ipcw,
    cumulative_dynamic_auc,
    integrated_brier_score,
)
from sksurv.util import Surv

from src.evaluation.metrics import (
    UnsupportedCensoringError,
    concordance_index,
    evaluation_times,
    harrell_c_index,
    integrated_brier,
    time_dependent_auc,
    training_event_time_horizons,
    uno_c_index,
    validate_ipcw_horizons,
)


def test_concordance_matches_scikit_survival():
    rng = np.random.default_rng(0)
    for _ in range(50):
        n = int(rng.integers(30, 200))
        time = rng.exponential(100, n).round(1)
        event = rng.integers(0, 2, n)
        risk = rng.normal(0, 1, n).round(2)
        if event.sum() == 0:
            continue

        ours, _ = concordance_index(time, event, risk)
        reference, *_ = concordance_index_censored(event.astype(bool), time, risk)
        assert ours == pytest.approx(reference, abs=1e-12)


def test_explicit_harrell_interface_matches_scikit_survival():
    time = np.array([1.0, 2.0, 4.0, 5.0, 8.0, 9.0])
    event = np.array([1, 0, 1, 1, 0, 1])
    risk = np.array([2.0, 0.5, 1.4, 0.2, -0.5, -1.0])
    reference, *_ = concordance_index_censored(event.astype(bool), time, risk)
    assert harrell_c_index(time, event, risk) == pytest.approx(reference, abs=1e-12)
    _, invalid_pair_se = concordance_index(time, event, risk)
    assert invalid_pair_se is None


def test_concordance_perfect_ranking():
    time = np.array([1.0, 2.0, 3.0, 4.0])
    event = np.array([1, 1, 1, 1])
    risk = np.array([4.0, 3.0, 2.0, 1.0])
    c, _ = concordance_index(time, event, risk)
    assert c == pytest.approx(1.0)


def test_concordance_inverted_ranking():
    time = np.array([1.0, 2.0, 3.0, 4.0])
    event = np.array([1, 1, 1, 1])
    risk = np.array([1.0, 2.0, 3.0, 4.0])
    c, _ = concordance_index(time, event, risk)
    assert c == pytest.approx(0.0)


def test_concordance_tied_risk_is_one_half():
    time = np.array([1.0, 2.0, 3.0, 4.0])
    event = np.array([1, 1, 1, 1])
    risk = np.ones(4)
    c, _ = concordance_index(time, event, risk)
    assert c == pytest.approx(0.5)


def test_evaluation_times_inside_follow_up():
    rng = np.random.default_rng(1)
    time = rng.exponential(50, 300)
    event = rng.integers(0, 2, 300)

    times = evaluation_times(time, event, n_times=5)
    assert times.min() > time.min()
    assert times.max() < time.max()
    assert np.all(np.diff(times) > 0)


def test_training_horizons_are_observed_event_quantiles():
    time = np.arange(1.0, 13.0)
    event = np.array([1, 0, 1, 1, 0, 1, 0, 1, 1, 0, 1, 0])
    horizons = training_event_time_horizons(
        time, event, quantiles=(0.25, 0.5, 0.75)
    )
    assert horizons == pytest.approx(np.quantile(time[event.astype(bool)], [0.25, 0.5, 0.75]))


def test_unsupported_censoring_horizon_fails_clearly():
    train_time = np.array([1.0, 2.0, 3.0, 4.0])
    train_event = np.array([1, 1, 0, 0])
    with pytest.raises(UnsupportedCensoringError, match="censoring survival"):
        validate_ipcw_horizons(train_time, train_event, [4.0])


def test_integrated_brier_rewards_a_better_model():
    """A survival curve matching the data beats a curve that ignores it."""
    rng = np.random.default_rng(2)
    n = 400
    time = rng.exponential(50, n)
    event = np.ones(n, dtype=int)
    eval_times = np.percentile(time, [25, 50, 75])

    informed = np.exp(-np.outer(1.0 / 50.0 * np.ones(n), eval_times))
    uninformed = np.full((n, len(eval_times)), 0.5)

    ibs_informed = integrated_brier(time, event, time, event, informed, eval_times)
    ibs_uninformed = integrated_brier(time, event, time, event, uninformed, eval_times)
    assert ibs_informed < ibs_uninformed


def test_integrated_brier_matches_scikit_survival():
    rng = np.random.default_rng(12)
    train_time = rng.uniform(2, 12, 300)
    train_event = rng.binomial(1, 0.7, 300)
    test_time = rng.uniform(2, 11, 120)
    test_event = rng.binomial(1, 0.7, 120)
    times = np.array([4.0, 6.0, 8.0])
    predictions = np.exp(-np.outer(rng.uniform(0.04, 0.2, 120), times))
    ours = integrated_brier(
        train_time, train_event, test_time, test_event, predictions, times
    )
    reference = integrated_brier_score(
        Surv.from_arrays(train_event.astype(bool), train_time),
        Surv.from_arrays(test_event.astype(bool), test_time),
        predictions,
        times,
    )
    assert ours == pytest.approx(reference, abs=1e-12)


def test_evaluate_model_rejects_test_events_beyond_training_support():
    """Metric code must not silently alter evaluation outcomes."""
    from src.evaluation.metrics import evaluate_model

    rng = np.random.default_rng(4)
    n = 200
    train_time = rng.uniform(1, 100, n)
    train_event = rng.integers(0, 2, n)

    # Two test subjects have observed events past the training horizon.
    test_time = np.concatenate([rng.uniform(1, 90, n), [150.0, 200.0]])
    test_event = np.concatenate([rng.integers(0, 2, n), [1, 1]])
    risk = rng.normal(0, 1, n + 2)
    eval_times = np.percentile(train_time, [25, 50, 75])

    with pytest.raises(UnsupportedCensoringError, match="unsupported"):
        evaluate_model(
            train_time, train_event, test_time, test_event, risk, eval_times=eval_times
        )


def test_time_dependent_auc_detects_signal():
    rng = np.random.default_rng(3)
    n = 500
    risk = rng.normal(0, 1, n)
    time = rng.exponential(np.exp(-risk) * 50)
    event = np.ones(n, dtype=int)
    eval_times = np.percentile(time, [25, 50, 75])

    _, mean_auc = time_dependent_auc(time, event, time, event, risk, eval_times)
    assert mean_auc > 0.7


def test_time_dependent_auc_matches_scikit_survival():
    rng = np.random.default_rng(13)
    train_time = rng.uniform(1, 20, 400)
    train_event = rng.binomial(1, 0.75, 400)
    test_time = rng.uniform(1, 18, 150)
    test_event = rng.binomial(1, 0.75, 150)
    risk = rng.normal(size=150)
    times = np.array([5.0, 9.0, 13.0])
    ours_auc, ours_mean = time_dependent_auc(
        train_time, train_event, test_time, test_event, risk, times
    )
    reference_auc, reference_mean = cumulative_dynamic_auc(
        Surv.from_arrays(train_event.astype(bool), train_time),
        Surv.from_arrays(test_event.astype(bool), test_time),
        risk,
        times,
    )
    assert ours_auc == pytest.approx(reference_auc, abs=1e-12)
    assert ours_mean == pytest.approx(reference_mean, abs=1e-12)


def test_uno_concordance_matches_scikit_survival():
    rng = np.random.default_rng(14)
    train_time = rng.uniform(1, 20, 400)
    train_event = rng.binomial(1, 0.75, 400)
    test_time = rng.uniform(1, 18, 150)
    test_event = rng.binomial(1, 0.75, 150)
    risk = rng.normal(size=150)
    tau = 12.0
    ours = uno_c_index(
        train_time, train_event, test_time, test_event, risk, tau=tau
    )
    reference, *_ = concordance_index_ipcw(
        Surv.from_arrays(train_event.astype(bool), train_time),
        Surv.from_arrays(test_event.astype(bool), test_time),
        risk,
        tau=tau,
    )
    assert ours == pytest.approx(reference, abs=1e-12)
