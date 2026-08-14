"""Confirmatory paired-inference tests."""

import numpy as np
import pytest
from scipy.stats import t as student_t

from src.statistics.bootstrap import paired_event_stratified_bootstrap
from src.statistics.confidence_intervals import ConfidenceIntervalCalculator
from src.statistics.hypothesis_tests import SurvivalHypothesisTests, holm_adjust
from src.statistics.permutation import PermutationTest
from src.statistics.repeated_cv import nadeau_bengio_paired_effect


def test_nadeau_bengio_effect_matches_formula():
    a = np.array([0.71, 0.70, 0.72, 0.69, 0.73, 0.72, 0.71, 0.74, 0.70, 0.72])
    b = np.array([0.69, 0.69, 0.70, 0.68, 0.71, 0.70, 0.70, 0.71, 0.69, 0.70])
    result = nadeau_bengio_paired_effect(a, b, n_repeats=2, n_folds=5)
    differences = a - b
    expected_sd = np.std(differences, ddof=1)
    expected_se = np.sqrt((1 / 10 + 1 / 4) * expected_sd**2)
    expected_t = np.mean(differences) / expected_se
    expected_p = 2 * student_t.sf(abs(expected_t), 9)
    assert result.mean_difference == pytest.approx(np.mean(differences))
    assert result.standard_deviation == pytest.approx(expected_sd)
    assert result.corrected_standard_error == pytest.approx(expected_se)
    assert result.t_statistic == pytest.approx(expected_t)
    assert result.p_value == pytest.approx(expected_p)
    assert result.test_train_ratio == pytest.approx(0.25)


def test_nadeau_bengio_identical_scores_are_null():
    scores = np.linspace(0.6, 0.8, 10)
    result = nadeau_bengio_paired_effect(
        scores, scores, n_repeats=2, n_folds=5
    )
    assert result.mean_difference == 0
    assert result.corrected_standard_error == 0
    assert result.p_value == 1
    assert result.confidence_lower == result.confidence_upper == 0


def test_nadeau_bengio_requires_complete_paired_design():
    with pytest.raises(ValueError, match="10 values"):
        nadeau_bengio_paired_effect(
            np.ones(9), np.ones(9), n_repeats=2, n_folds=5
        )


def test_holm_adjustment_and_class_interface():
    adjusted, rejected = holm_adjust([0.01, 0.04, 0.03], alpha=0.05)
    assert adjusted == pytest.approx([0.03, 0.06, 0.06])
    assert rejected == [True, False, False]
    class_adjusted = SurvivalHypothesisTests.multiple_comparison_correction(
        [0.01, 0.04, 0.03], method="holm"
    )
    assert class_adjusted == pytest.approx(adjusted)


def test_confidence_intervals_reject_empty_samples_instead_of_inventing_zeros():
    with pytest.raises(ValueError, match="At least"):
        ConfidenceIntervalCalculator.percentile_ci(np.array([]))
    with pytest.raises(ValueError, match="At least 2"):
        ConfidenceIntervalCalculator.normal_ci(np.array([1.0]))
    lower, upper = ConfidenceIntervalCalculator.percentile_ci(
        np.arange(100.0), alpha=0.1
    )
    assert lower == pytest.approx(4.95)
    assert upper == pytest.approx(94.05)


def test_paired_permutation_exact_known_result():
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.zeros(4)
    test = PermutationTest(n_permutations=16, random_state=1)
    assert test.compare_models(a, b) == pytest.approx(2 / 16)
    assert test.compare_models(a, b, alternative="greater") == pytest.approx(1 / 16)
    assert test.compare_models(a, a) == 1.0


def test_monte_carlo_permutation_is_seeded_and_not_constant():
    rng = np.random.default_rng(31)
    b = rng.normal(size=30)
    a = b + rng.normal(0.3, 0.2, size=30)
    first = PermutationTest(n_permutations=999, random_state=4).compare_models(a, b)
    second = PermutationTest(n_permutations=999, random_state=4).compare_models(a, b)
    assert first == second
    assert 0 < first < 0.05


def test_event_stratified_paired_bootstrap_preserves_pairing():
    rng = np.random.default_rng(32)
    time = rng.uniform(1, 20, 80)
    event = np.repeat([0, 1], 40)
    predictions_b = rng.normal(size=80)
    predictions_a = predictions_b + 0.25

    def mean_prediction(_time, _event, predictions):
        return float(np.mean(predictions))

    result = paired_event_stratified_bootstrap(
        time,
        event,
        predictions_a,
        predictions_b,
        mean_prediction,
        n_bootstraps=100,
        random_state=5,
    )
    assert result.observed_difference == pytest.approx(0.25)
    assert result.bootstrap_mean_difference == pytest.approx(0.25)
    assert result.confidence_lower == pytest.approx(0.25)
    assert result.confidence_upper == pytest.approx(0.25)
    assert result.n_successful == 100


def test_paired_bootstrap_is_deterministic_for_nonconstant_effect():
    rng = np.random.default_rng(33)
    time = rng.uniform(1, 20, 100)
    event = rng.binomial(1, 0.5, 100)
    a = rng.normal(size=100)
    b = rng.normal(size=100)

    def mean_prediction(_time, _event, predictions):
        return float(np.mean(predictions))

    first = paired_event_stratified_bootstrap(
        time, event, a, b, mean_prediction, n_bootstraps=50, random_state=6
    )
    second = paired_event_stratified_bootstrap(
        time, event, a, b, mean_prediction, n_bootstraps=50, random_state=6
    )
    assert first == second
