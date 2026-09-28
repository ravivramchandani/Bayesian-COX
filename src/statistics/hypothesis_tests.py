"""Holm correction for paired inference and legacy rank-test interfaces.

The confirmatory analysis calls ``holm_adjust`` on its prespecified family of
nine primary tests (three prior pairs in each of three cohorts), and on the
per-covariate proportional-hazards tests of each Cox fit.

Holm's step-down procedure controls the family-wise error rate, the
probability of at least one false rejection, at ``alpha`` under any
dependence between the tests. With m p-values sorted as
``p_(1) <= ... <= p_(m)``, it compares ``p_(1)`` with ``alpha / m``,
``p_(2)`` with ``alpha / (m - 1)``, and so on, rejecting each hypothesis in
turn and stopping at the first that is not rejected. The equivalent adjusted
p-value is ``max_{j <= i} min(1, (m - j + 1) p_(j))``, and a hypothesis is
rejected when its adjusted p-value is at most ``alpha``. It is at least as
powerful as Bonferroni, which multiplies every p-value by m.

The class retains Wilcoxon, Friedman, Bonferroni and Benjamini-Hochberg
interfaces for older callers; they do not replace corrected repeated cross-validation (CV) tests.
"""

import numpy as np
from scipy.stats import friedmanchisquare, wilcoxon


def holm_adjust(
    p_values: list[float] | np.ndarray, *, alpha: float = 0.05
) -> tuple[list[float], list[bool]]:
    """Return Holm-adjusted p-values and family-wise rejection decisions.

    Args:
        p_values: Finite p-values for one complete prespecified family.
        alpha: Family-wise significance level.

    Returns:
        Adjusted p-values and rejection flags in the original input order.
        Tied p-values receive the same adjusted value.

    Raises:
        ValueError: The p-values are empty or outside [0, 1], or ``alpha``
            is not in (0, 1).
    """
    values = np.asarray(p_values, dtype=float)
    if values.ndim != 1 or len(values) == 0:
        raise ValueError("p_values must be a non-empty one-dimensional sequence.")
    if not np.isfinite(values).all() or np.any((values < 0) | (values > 1)):
        raise ValueError("p_values must be finite values in [0, 1].")
    if not 0 < alpha < 1:
        raise ValueError("alpha must lie strictly between 0 and 1.")

    count = len(values)
    order = np.argsort(values, kind="stable")
    ordered = values[order]
    # Multiply the i-th smallest p-value by m - i + 1, then take the running
    # maximum so adjusted values never decrease along the step-down order.
    adjusted_ordered = np.maximum.accumulate(ordered * np.arange(count, 0, -1, dtype=float))
    adjusted_ordered = np.minimum(adjusted_ordered, 1.0)
    adjusted = np.empty(count, dtype=float)
    adjusted[order] = adjusted_ordered
    return adjusted.tolist(), (adjusted <= alpha).tolist()


class SurvivalHypothesisTests:
    """Legacy rank tests and p-value corrections for model score vectors.

    The rank tests treat fold scores as independent, which repeated
    cross-validation does not satisfy; confirmatory contrasts use
    :mod:`src.statistics.repeated_cv` instead.
    """

    @staticmethod
    def wilcoxon_signed_rank(scores_a: np.ndarray, scores_b: np.ndarray) -> tuple[float, float]:
        """Run SciPy's two-sided paired Wilcoxon signed-rank test.

        Args:
            scores_a: Model A scores of shape (n_pairs,).
            scores_b: Model B scores on the same observations and score scale.

        Returns:
            Test statistic and two-sided p-value, using SciPy's default
            method and zero-difference handling.

        Raises:
            ValueError: The supplied samples are unsupported by SciPy's test.
        """
        stat, p_val = wilcoxon(scores_a, scores_b)
        return float(stat), float(p_val)

    @staticmethod
    def friedman_test(*args: np.ndarray) -> tuple[float, float]:
        """Run SciPy's Friedman test across matched score vectors.

        Args:
            *args: At least three model score vectors of equal length,
                aligned on the same observations and score scale.

        Returns:
            Friedman statistic and its chi-square-reference p-value.

        Raises:
            ValueError: The number or lengths of samples are unsupported.
        """
        stat, p_val = friedmanchisquare(*args)
        return float(stat), float(p_val)

    @staticmethod
    def multiple_comparison_correction(
        p_values: list[float], method: str = "bonferroni"
    ) -> list[float]:
        """Return multiplicity-adjusted p-values in their original order.

        ``"bonferroni"`` and ``"holm"`` control family-wise error under
        arbitrary dependence. ``"fdr_bh"`` is the Benjamini-Hochberg procedure;
        its false discovery rate guarantee assumes independent or suitable
        positively dependent tests. A single valid p-value is returned unchanged
        before the method name is checked.

        Args:
            p_values: Non-empty one-dimensional finite p-values in [0, 1].
            method: ``"bonferroni"``, ``"holm"`` or ``"fdr_bh"``.

        Returns:
            Adjusted p-values in [0, 1], without rejection flags.

        Raises:
            ValueError: The p-values are invalid, or more than one p-value
                is supplied with an unknown method.
        """
        p_arr = np.asarray(p_values, dtype=float)
        m = len(p_arr)
        if p_arr.ndim != 1 or m == 0:
            raise ValueError("p_values must be a non-empty one-dimensional sequence.")
        if not np.isfinite(p_arr).all() or np.any((p_arr < 0) | (p_arr > 1)):
            raise ValueError("p_values must be finite values in [0, 1].")
        if m == 1:
            return [float(p_arr[0])]

        if method == "bonferroni":
            corrected = p_arr * m
            return list(np.minimum(corrected, 1.0))

        elif method == "holm":
            corrected, _ = holm_adjust(p_arr)
            return corrected

        elif method == "fdr_bh":
            # Benjamini-Hochberg FDR controlling procedure
            idx = np.argsort(p_arr)
            sorted_p = p_arr[idx]
            corrected_sorted = np.zeros(m)
            for i, p in enumerate(sorted_p):
                corrected_sorted[i] = p * m / (i + 1)
            # Enforce monotonicity (working backwards)
            for i in range(m - 2, -1, -1):
                corrected_sorted[i] = min(corrected_sorted[i], corrected_sorted[i + 1])
            corrected_sorted = np.minimum(corrected_sorted, 1.0)
            # Restore original order
            corrected = np.zeros(m)
            corrected[idx] = corrected_sorted
            return list(corrected)

        else:
            raise ValueError(f"Unknown correction method: {method}")
