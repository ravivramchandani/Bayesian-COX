"""Paired effects from repeated cross-validation (CV) with the Nadeau-Bengio correction.

The confirmatory inference stage (``src/pipelines/confirmatory/inference.py``)
calls :func:`nadeau_bengio_paired_effect` for every model contrast: the
primary integrated Brier score contrasts, the secondary metrics and the
calibration parameters. Its p-values for the nine primary contrasts then go
to Holm's procedure (``hypothesis_tests.holm_adjust``).

Why a correction is needed
    Repeated K-fold cross-validation gives n = R * K paired fold differences
    ``d = score_a - score_b``. The naive standard error ``s / sqrt(n)``
    treats them as independent, but any two training sets share most of
    their subjects and every subject is validated once per repeat, so the
    fold differences can be correlated, making the naive standard error
    too small. Nadeau and Bengio (2003) inflate the variance by a term that
    grows with the test-to-training size ratio:

    ``SE = sqrt((1 / n + n_test / n_train) * s^2)``,

    where ``s^2`` is the sample variance (denominator n - 1) of the n
    differences. For K-fold splits ``n_test / n_train = 1 / (K - 1)``, 0.25
    for the five-fold design. The statistic ``t = mean(d) / SE`` is referred
    to a Student-t distribution with n - 1 degrees of freedom (24 for five
    repeats of five folds), giving a two-sided p-value and the interval
    ``mean(d) +/- t_{n-1, 1-alpha/2} * SE``.

The correction accounts for overlap between training sets within one cohort;
it does not make different cohorts exchangeable or justify pooling them.
"""

from dataclasses import asdict, dataclass

import numpy as np
from scipy.stats import t as student_t


@dataclass(frozen=True)
class NadeauBengioResult:
    """Corrected repeated-CV mean difference and two-sided inference.

    ``standard_deviation`` is the sample standard deviation of the paired
    differences; ``corrected_standard_error`` is the Nadeau-Bengio standard
    error; the confidence bounds and ``p_value`` use a Student-t reference
    with ``degrees_of_freedom`` = n_repeats * n_folds - 1.
    """

    mean_difference: float
    standard_deviation: float
    corrected_standard_error: float
    confidence_lower: float
    confidence_upper: float
    t_statistic: float
    p_value: float
    degrees_of_freedom: int
    n_repeats: int
    n_folds: int
    test_train_ratio: float
    confidence_level: float

    def to_dict(self) -> dict[str, float | int]:
        """Return the recorded effect and design fields as a plain dictionary.

        Returns:
            JSON-serialisable scalar values keyed by the dataclass field names.
        """
        return asdict(self)


def nadeau_bengio_paired_effect(
    scores_a: np.ndarray,
    scores_b: np.ndarray,
    *,
    n_repeats: int,
    n_folds: int,
    test_train_ratio: float | None = None,
    confidence_level: float = 0.95,
) -> NadeauBengioResult:
    """Estimate ``mean(scores_a - scores_b)`` with corrected repeated-CV SE.

    The Nadeau-Bengio correction is

    ``SE = sqrt((1 / (R K) + n_test / n_train) * sample_variance)``.

    For K-fold CV, ``n_test / n_train`` defaults to ``1 / (K - 1)``, which
    is exact for equal-sized folds. Scores must be paired in the same
    repeat/fold order. The correction addresses overlap between training
    sets; it does not make different cohorts exchangeable or justify pooling
    them.

    Args:
        scores_a: Metric of model A, one value per fold (R * K values).
        scores_b: Metric of model B on the same folds, in the same order.
        n_repeats: Number of cross-validation repeats R.
        n_folds: Number of folds per repeat K.
        test_train_ratio: Override for ``n_test / n_train``.
        confidence_level: Level of the two-sided interval.

    Returns:
        The mean difference, its corrected standard error, interval,
        t statistic and two-sided p-value, all effects retaining the
        supplied metric scale. With zero variance, a zero mean gives
        p=1; a non-zero mean gives infinite signed t and p=0.

    Raises:
        ValueError: The design arguments are invalid, the score vectors do
            not hold R * K finite values, the ratio is non-finite or non-positive,
            or the interval level is invalid.
    """
    if n_repeats < 1 or n_folds < 2:
        raise ValueError("n_repeats must be positive and n_folds must be at least 2.")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must lie strictly between 0 and 1.")

    a = np.asarray(scores_a, dtype=float).reshape(-1)
    b = np.asarray(scores_b, dtype=float).reshape(-1)
    expected = n_repeats * n_folds
    if len(a) != expected or len(b) != expected:
        raise ValueError(
            f"Each score vector must contain n_repeats * n_folds = {expected} values."
        )
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("scores_a and scores_b must contain only finite values.")

    ratio = 1.0 / (n_folds - 1) if test_train_ratio is None else test_train_ratio
    if not np.isfinite(ratio) or ratio <= 0:
        raise ValueError("test_train_ratio must be finite and positive.")

    differences = a - b
    n = len(differences)
    degrees_of_freedom = n - 1
    mean_difference = float(np.mean(differences))
    standard_deviation = float(np.std(differences, ddof=1))
    corrected_se = float(
        np.sqrt((1.0 / n + float(ratio)) * standard_deviation**2)
    )

    # Identical differences in every fold give a zero standard error: the
    # test is then decided by the sign of the mean alone.
    if corrected_se == 0:
        if mean_difference == 0:
            statistic = 0.0
            p_value = 1.0
        else:
            statistic = float(np.copysign(np.inf, mean_difference))
            p_value = 0.0
    else:
        statistic = mean_difference / corrected_se
        p_value = float(2 * student_t.sf(abs(statistic), degrees_of_freedom))

    alpha = 1 - confidence_level
    critical = float(student_t.ppf(1 - alpha / 2, degrees_of_freedom))
    half_width = critical * corrected_se
    return NadeauBengioResult(
        mean_difference=mean_difference,
        standard_deviation=standard_deviation,
        corrected_standard_error=corrected_se,
        confidence_lower=float(mean_difference - half_width),
        confidence_upper=float(mean_difference + half_width),
        t_statistic=float(statistic),
        p_value=p_value,
        degrees_of_freedom=degrees_of_freedom,
        n_repeats=n_repeats,
        n_folds=n_folds,
        test_train_ratio=float(ratio),
        confidence_level=float(confidence_level),
    )
