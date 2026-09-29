"""Paired effects from repeated cross-validation."""

from dataclasses import asdict, dataclass

import numpy as np
from scipy.stats import t as student_t


@dataclass(frozen=True)
class NadeauBengioResult:
    """Corrected repeated-CV mean difference and two-sided inference."""

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
        """Return a JSON-serialisable representation."""
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

    For K-fold CV, ``n_test / n_train`` defaults to ``1 / (K - 1)``. Scores
    must be paired in the same repeat/fold order. The correction addresses
    overlap between training sets; it does not make different cohorts
    exchangeable or justify pooling them.
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
