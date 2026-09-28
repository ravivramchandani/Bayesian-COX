"""Deterministic paired randomisation tests.

A general tool retained for older callers; the confirmatory contrasts use
the Nadeau-Bengio corrected test in ``repeated_cv``.
"""

import itertools

import numpy as np


class PermutationTest:
    """Paired label-swap test for exchangeable model scores.

    Args:
        n_permutations: Positive budget for sign patterns, used as the
            number of Monte Carlo draws when exact enumeration exceeds it.
        random_state: Seed for Monte Carlo sign draws.

    Raises:
        ValueError: ``n_permutations`` is below one.
    """

    def __init__(self, n_permutations: int = 1000, random_state: int = 42):
        """Validate the permutation budget and store the random seed."""
        if n_permutations < 1:
            raise ValueError("n_permutations must be positive.")
        self.n_permutations = n_permutations
        self.random_state = random_state

    def compare_models(
        self,
        scores_a: np.ndarray,
        scores_b: np.ndarray,
        *,
        alternative: str = "two-sided",
    ) -> float:
        """Return a paired sign-flip randomisation p-value.

        Under the sharp null, swapping the two model labels within a pair is
        exchangeable. All permutations are enumerated when feasible; otherwise
        a seeded Monte Carlo estimate uses the plus-one correction. Repeated-CV
        fold scores are dependent and should instead use the Nadeau-Bengio
        correction in :mod:`src.statistics.repeated_cv`.

        The statistic is the sum of the non-zero paired differences
        ``scores_a - scores_b``; zero differences are dropped because their
        sign cannot change. Exact enumeration of all ``2^k`` sign patterns is
        used when there are at most 20 non-zero differences and ``2^k`` does
        not exceed ``n_permutations``. Otherwise ``n_permutations`` random sign
        patterns give ``(extreme + 1) / (n_permutations + 1)``, which is never
        zero. A tolerance of 1e-12 treats ties with the observed statistic as
        extreme. Returns 1.0 when every difference is zero.

        Args:
            scores_a: Finite model A scores of shape (n_pairs,).
            scores_b: Model B scores on the same observations and score scale.
            alternative: ``"two-sided"`` compares absolute differences;
                ``"greater"`` tests A minus B above zero; ``"less"`` below zero.

        Returns:
            The exact or plus-one Monte Carlo p-value in (0, 1].

        Raises:
            ValueError: The score vectors are misaligned or non-finite, or
                ``alternative`` is not ``"two-sided"``, ``"greater"`` or
                ``"less"``.
        """
        a = np.asarray(scores_a, dtype=float)
        b = np.asarray(scores_b, dtype=float)
        if a.ndim != 1 or b.ndim != 1 or len(a) == 0 or len(a) != len(b):
            raise ValueError("scores_a and scores_b must be equal-length 1D arrays.")
        if not np.isfinite(a).all() or not np.isfinite(b).all():
            raise ValueError("scores_a and scores_b must contain only finite values.")
        if alternative not in {"two-sided", "greater", "less"}:
            raise ValueError("alternative must be 'two-sided', 'greater', or 'less'.")

        differences = a - b
        nonzero = differences[differences != 0]
        if len(nonzero) == 0:
            return 1.0
        observed = float(np.sum(nonzero))

        def is_extreme(statistic: float) -> bool:
            """Return whether a sign-flipped statistic is at least as extreme as observed."""
            tolerance = 1e-12
            if alternative == "two-sided":
                return abs(statistic) >= abs(observed) - tolerance
            if alternative == "greater":
                return statistic >= observed - tolerance
            return statistic <= observed + tolerance

        total_exact = 2 ** len(nonzero)
        if len(nonzero) <= 20 and total_exact <= self.n_permutations:
            extreme = 0
            for signs in itertools.product((-1.0, 1.0), repeat=len(nonzero)):
                statistic = float(np.dot(nonzero, np.asarray(signs)))
                extreme += int(is_extreme(statistic))
            return float(extreme / total_exact)

        rng = np.random.default_rng(self.random_state)
        signs = rng.choice(
            np.asarray([-1.0, 1.0]),
            size=(self.n_permutations, len(nonzero)),
            replace=True,
        )
        statistics = signs @ nonzero
        if alternative == "two-sided":
            extreme = int(np.sum(np.abs(statistics) >= abs(observed) - 1e-12))
        elif alternative == "greater":
            extreme = int(np.sum(statistics >= observed - 1e-12))
        else:
            extreme = int(np.sum(statistics <= observed + 1e-12))
        return float((extreme + 1) / (self.n_permutations + 1))
