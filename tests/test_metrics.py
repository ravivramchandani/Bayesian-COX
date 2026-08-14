"""Metric correctness against reference implementations and known values."""

import numpy as np
import pytest
from sksurv.metrics import concordance_index_censored

from src.evaluation.metrics import (
    concordance_index,
    evaluation_times,
    integrated_brier,
    time_dependent_auc,
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


def test_evaluate_model_handles_test_events_beyond_training_horizon():
    """Censoring weights come from training follow-up, so later test events
    must be administratively censored rather than raising."""
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

    result = evaluate_model(
        train_time, train_event, test_time, test_event, risk, eval_times=eval_times
    )
    assert result["n_administratively_censored"] == 2
    assert 0.0 <= result["mean_auc"] <= 1.0


def test_time_dependent_auc_detects_signal():
    rng = np.random.default_rng(3)
    n = 500
    risk = rng.normal(0, 1, n)
    time = rng.exponential(np.exp(-risk) * 50)
    event = np.ones(n, dtype=int)
    eval_times = np.percentile(time, [25, 50, 75])

    _, mean_auc = time_dependent_auc(time, event, time, event, risk, eval_times)
    assert mean_auc > 0.7
