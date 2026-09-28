"""Confirmatory paired-inference tests and checks of the supporting statistical utilities.

Protects ``src/statistics``: the NB (Nadeau-Bengio) corrected paired effect for
repeated CV (cross-validation) in ``repeated_cv.py`` and Holm adjustment in
``hypothesis_tests.py``, which the confirmatory inference uses, plus the
confidence-interval, sign-flip permutation and event-stratified paired
bootstrap utilities. Results are compared with closed-form values or with a
rerun under the same seed.
"""

import numpy as np
import pytest
from scipy.stats import t as student_t

from src.statistics.bootstrap import paired_event_stratified_bootstrap
from src.statistics.confidence_intervals import ConfidenceIntervalCalculator
from src.statistics.hypothesis_tests import SurvivalHypothesisTests, holm_adjust
from src.statistics.permutation import PermutationTest
from src.statistics.repeated_cv import nadeau_bengio_paired_effect


def test_nadeau_bengio_effect_matches_formula():
    """The NB effect matches the corrected formula for 2 repeats of 5 folds (ADR-017)."""
    # NB corrected variance: (1 / (R K) + n_test / n_train) * s^2, where s^2 is the
    # sample variance of the R K paired differences and n_test / n_train = 1 / (K - 1)
    # = 0.25 for K = 5. The extra term allows for the positive correlation between
    # fold scores that overlapping training sets cause. The t-test uses R K - 1 = 9
    # degrees of freedom.
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
    """Identical score vectors give a zero effect and standard error and a p-value of 1."""
    # Zero variance is an edge case: t is set to 0 and p to 1 instead of dividing by zero.
    scores = np.linspace(0.6, 0.8, 10)
    result = nadeau_bengio_paired_effect(
        scores, scores, n_repeats=2, n_folds=5
    )
    assert result.mean_difference == 0
    assert result.corrected_standard_error == 0
    assert result.p_value == 1
    assert result.confidence_lower == result.confidence_upper == 0


def test_nadeau_bengio_requires_complete_paired_design():
    """Score vectors with fewer than repeats x folds values are rejected (ADR-017)."""
    with pytest.raises(ValueError, match="10 values"):
        nadeau_bengio_paired_effect(
            np.ones(9), np.ones(9), n_repeats=2, n_folds=5
        )


def test_holm_adjustment_and_class_interface():
    """Holm gives the step-down adjusted p-values and the class wrapper agrees (ADR-017)."""
    # Sorted p-values 0.01, 0.03, 0.04 are multiplied by 3, 2, 1, giving 0.03, 0.06,
    # 0.04; the running maximum raises the last to 0.06. Output is in input order.
    adjusted, rejected = holm_adjust([0.01, 0.04, 0.03], alpha=0.05)
    assert adjusted == pytest.approx([0.03, 0.06, 0.06])
    assert rejected == [True, False, False]
    class_adjusted = SurvivalHypothesisTests.multiple_comparison_correction(
        [0.01, 0.04, 0.03], method="holm"
    )
    assert class_adjusted == pytest.approx(adjusted)


def test_confidence_intervals_reject_empty_samples_instead_of_inventing_zeros():
    """Interval helpers reject too-small samples and return interpolated percentile bounds."""
    with pytest.raises(ValueError, match="At least"):
        ConfidenceIntervalCalculator.percentile_ci(np.array([]))
    with pytest.raises(ValueError, match="At least 2"):
        ConfidenceIntervalCalculator.normal_ci(np.array([1.0]))
    # With linear interpolation the 5th and 95th percentiles of 0..99 are 4.95 and 94.05.
    lower, upper = ConfidenceIntervalCalculator.percentile_ci(
        np.arange(100.0), alpha=0.1
    )
    assert lower == pytest.approx(4.95)
    assert upper == pytest.approx(94.05)


def test_paired_permutation_exact_known_result():
    """The exact sign-flip test enumerates every sign pattern and returns the known p-values."""
    # Four non-zero differences give 2^4 = 16 sign patterns, all enumerated because
    # 16 <= n_permutations. Only the all-positive and all-negative patterns reach
    # |sum| = 10, so two-sided p = 2/16 and one-sided p = 1/16; identical scores give 1.
    a = np.array([1.0, 2.0, 3.0, 4.0])
    b = np.zeros(4)
    test = PermutationTest(n_permutations=16, random_state=1)
    assert test.compare_models(a, b) == pytest.approx(2 / 16)
    assert test.compare_models(a, b, alternative="greater") == pytest.approx(1 / 16)
    assert test.compare_models(a, a) == 1.0


def test_monte_carlo_permutation_is_seeded_and_not_constant():
    """The Monte Carlo sign-flip p-value is reproducible for a seed and detects a clear shift."""
    # 2^30 patterns exceed 999, so seeded Monte Carlo sampling is used; its plus-one
    # correction keeps p above zero. Scores a are b plus noise with mean 0.3.
    rng = np.random.default_rng(31)
    b = rng.normal(size=30)
    a = b + rng.normal(0.3, 0.2, size=30)
    first = PermutationTest(n_permutations=999, random_state=4).compare_models(a, b)
    second = PermutationTest(n_permutations=999, random_state=4).compare_models(a, b)
    assert first == second
    assert 0 < first < 0.05


def test_event_stratified_paired_bootstrap_preserves_pairing():
    """Both models share each resample, so a constant shift gives a constant difference."""
    rng = np.random.default_rng(32)
    time = rng.uniform(1, 20, 80)
    event = np.repeat([0, 1], 40)
    # Model a is model b plus 0.25 for every subject. With a mean metric, every
    # replicate difference is 0.25 only if both models use the same sampled indices.
    predictions_b = rng.normal(size=80)
    predictions_a = predictions_b + 0.25

    def mean_prediction(_time, _event, predictions):
        """Return the mean prediction, ignoring the outcomes."""
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
    """The paired bootstrap returns identical results for the same seed."""
    rng = np.random.default_rng(33)
    time = rng.uniform(1, 20, 100)
    event = rng.binomial(1, 0.5, 100)
    a = rng.normal(size=100)
    b = rng.normal(size=100)

    def mean_prediction(_time, _event, predictions):
        """Return the mean prediction, ignoring the outcomes."""
        return float(np.mean(predictions))

    first = paired_event_stratified_bootstrap(
        time, event, a, b, mean_prediction, n_bootstraps=50, random_state=6
    )
    second = paired_event_stratified_bootstrap(
        time, event, a, b, mean_prediction, n_bootstraps=50, random_state=6
    )
    assert first == second
