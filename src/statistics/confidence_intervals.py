"""Percentile and Student-t confidence intervals for a sample of values.

These are general helpers; the confirmatory analysis computes its intervals
in ``repeated_cv`` and in the calibration bootstrap.
"""

import numpy as np
from scipy.stats import sem, t


class ConfidenceIntervalCalculator:
    """Calculates non-parametric and parametric confidence bounds."""

    @staticmethod
    def _samples(samples: np.ndarray, *, minimum: int = 1) -> np.ndarray:
        """Return a finite one-dimensional float array with at least ``minimum`` values."""
        values = np.asarray(samples, dtype=float)
        if values.ndim != 1 or len(values) < minimum:
            raise ValueError(f"At least {minimum} one-dimensional samples are required.")
        if not np.isfinite(values).all():
            raise ValueError("Samples must contain only finite values.")
        return values

    @staticmethod
    def percentile_ci(samples: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
        """Return percentile bounds using NumPy's default linear interpolation.

        Args:
            samples: Non-empty, finite one-dimensional sample of values.
            alpha: Two-sided error probability, strictly between 0 and 1.

        Returns:
            Lower and upper ``alpha/2`` and ``1 - alpha/2`` quantiles, in
            the same unit as the samples.

        Raises:
            ValueError: Samples or ``alpha`` are invalid.
        """
        values = ConfidenceIntervalCalculator._samples(samples)
        if not 0 < alpha < 1:
            raise ValueError("alpha must lie strictly between 0 and 1.")
        lower = float(np.percentile(values, 100 * (alpha / 2.0)))
        upper = float(np.percentile(values, 100 * (1.0 - alpha / 2.0)))
        return lower, upper

    @staticmethod
    def normal_ci(samples: np.ndarray, alpha: float = 0.05) -> tuple[float, float]:
        """Calculate a Student-t interval for the sample mean.

        The interval is ``mean +/- t_{n-1, 1-alpha/2} * s / sqrt(n)``,
        where s is the sample standard deviation. Despite the method name,
        it uses Student-t, not the normal distribution. This standard error
        assumes independent observations; it does not correct dependence from repeated cross-validation.

        Args:
            samples: At least two finite values in a one-dimensional array.
            alpha: Two-sided error probability, strictly between 0 and 1.

        Returns:
            Lower and upper bounds for the mean, in the samples' unit.

        Raises:
            ValueError: Samples or ``alpha`` are invalid.
        """
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
        """Summarise a sample and its percentile bounds.

        Args:
            samples: At least two finite values in a one-dimensional array.
            alpha: Two-sided error probability, strictly between 0 and 1.

        Returns:
            ``mean``, ``std`` (denominator n - 1), ``se`` (std / sqrt(n)),
            and percentile ``ci_lower``/``ci_upper`` at level ``1 - alpha``.
            All quantities have the same unit as the samples.

        Raises:
            ValueError: Samples or ``alpha`` are invalid.
        """
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
