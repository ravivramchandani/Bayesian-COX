"""
Statistical hypothesis testing and multiple comparison correction engine.
Includes Wilcoxon, Friedman, and pure-Python correction algorithms (Bonferroni, Holm, BH).
"""

import numpy as np
from scipy.stats import friedmanchisquare, wilcoxon


def holm_adjust(
    p_values: list[float] | np.ndarray, *, alpha: float = 0.05
) -> tuple[list[float], list[bool]]:
    """Holm step-down adjusted p-values and family-wise rejection decisions."""
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
    adjusted_ordered = np.maximum.accumulate(
        ordered * np.arange(count, 0, -1, dtype=float)
    )
    adjusted_ordered = np.minimum(adjusted_ordered, 1.0)
    adjusted = np.empty(count, dtype=float)
    adjusted[order] = adjusted_ordered
    return adjusted.tolist(), (adjusted <= alpha).tolist()


class SurvivalHypothesisTests:
    """Hypothesis testing for survival group differences and model benchmark validation."""

    @staticmethod
    def wilcoxon_signed_rank(
        scores_a: np.ndarray, scores_b: np.ndarray
    ) -> tuple[float, float]:
        """Perform a paired Wilcoxon signed-rank test."""
        stat, p_val = wilcoxon(scores_a, scores_b)
        return float(stat), float(p_val)

    @staticmethod
    def friedman_test(*args: np.ndarray) -> tuple[float, float]:
        """Performs Friedman test across multiple model score vectors."""
        stat, p_val = friedmanchisquare(*args)
        return float(stat), float(p_val)

    @staticmethod
    def multiple_comparison_correction(
        p_values: list[float], method: str = "bonferroni"
    ) -> list[float]:
        """
        Applies multiple-testing p-value correction.
        Supported methods: 'bonferroni', 'holm', 'fdr_bh' (Benjamini-Hochberg).
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
