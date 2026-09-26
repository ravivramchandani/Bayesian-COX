"""Percentile and Student-t confidence intervals."""

import numpy as np
from scipy.stats import sem, t


class ConfidenceIntervalCalculator:
    """Calculates non-parametric and parametric confidence bounds."""

    @staticmethod
    def _samples(samples: np.ndarray, *, minimum: int = 1) -> np.ndarray:
        values = np.asarray(samples, dtype=float)
        if values.ndim != 1 or len(values) < minimum:
            raise ValueError(f"At least {minimum} one-dimensional samples are required.")
        if not np.isfinite(values).all():
            raise ValueError("Samples must contain only finite values.")
        return values

    @staticmethod
    def percentile_ci(samples: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
        """Calculates percentile confidence interval."""
        values = ConfidenceIntervalCalculator._samples(samples)
        if not 0 < alpha < 1:
            raise ValueError("alpha must lie strictly between 0 and 1.")
        lower = float(np.percentile(values, 100 * (alpha / 2.0)))
        upper = float(np.percentile(values, 100 * (1.0 - alpha / 2.0)))
        return lower, upper

    @staticmethod
    def normal_ci(samples: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
        """Calculate a Student-t interval for the sample mean."""
        values = ConfidenceIntervalCalculator._samples(samples, minimum=2)
        if not 0 < alpha < 1:
            raise ValueError("alpha must lie strictly between 0 and 1.")
        mean = np.mean(values)
        se = sem(values)
        h = se * t.ppf(1.0 - alpha / 2.0, len(values) - 1)
        return float(mean - h), float(mean + h)

    @staticmethod
    def get_summary_statistics(
        samples: np.ndarray, alpha: float = 0.05
    ) -> dict[str, float]:
        """Returns mean, std, se, and 95% CI bounds."""
        values = ConfidenceIntervalCalculator._samples(samples, minimum=2)
        mean_val = float(np.mean(values))
        std_val = float(np.std(values, ddof=1))
        se_val = float(sem(values))
        ci_lower, ci_upper = ConfidenceIntervalCalculator.percentile_ci(values, alpha)
        return {
            "mean": mean_val,
            "std": std_val,
            "se": se_val,
            "ci_lower": ci_lower,
            "ci_upper": ci_upper,
        }
