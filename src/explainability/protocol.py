"""Frozen settings and seed derivation for the confirmatory explanation stage.

The protocol records the sampling budgets, convergence thresholds and descriptive
bootstrap controls for Shapley additive explanations (SHAP), copied into every
frozen explanation result. The frozen-cell
pipeline combines :class:`ExplanationProtocol` with cohort, repeat and fold
labels through :func:`_stable_seed` to select subjects and bootstrap draws
reproducibly."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SamplingBudget:
    """How many subjects one explanation estimate uses.

    Attributes:
        validation_subjects: Outer-validation subjects whose predictions are
            explained.
        training_background: Outer-training subjects that form the SHAP
            background (the reference point each attribution is measured from).
    """

    validation_subjects: int
    training_background: int


@dataclass(frozen=True)
class ExplanationProtocol:
    """Frozen controls for the exact linear-SHAP stability analysis.

    Every fold is explained once per seed at each budget. Budgets must grow
    strictly, because the convergence gate compares each budget with the next
    larger one. The top-five rule and the overlap threshold of four are fixed
    by the study protocol and cannot be changed here.

    The convergence gate asks whether a grouped SHAP ranking has settled: two
    rankings agree when their Spearman correlation is at least
    ``convergence_spearman`` (0.95) and they share at least
    ``convergence_top_overlap`` (four) of their ``top_k`` (five) highest
    groups. The rule is applied in :mod:`src.explainability.stability`.

    Attributes:
        seeds: The three explanation seeds.
        budgets: Nested subject and background budgets, smallest first.
        top_k: Size of the top-ranked group set used for overlap and Jaccard.
        convergence_spearman: Minimum Spearman correlation between two
            successive grouped SHAP rankings.
        convergence_top_overlap: Minimum number of shared top-five groups
            between two successive grouped SHAP rankings.
        uncertainty_bootstraps: Resamples for each three-stage bootstrap.
        uncertainty_seed: Base seed for every bootstrap.
    """

    seeds: tuple[int, ...] = (104729, 130363, 155921)
    budgets: tuple[SamplingBudget, ...] = (
        SamplingBudget(25, 50),
        SamplingBudget(50, 100),
        SamplingBudget(100, 200),
    )
    top_k: int = 5
    convergence_spearman: float = 0.95
    convergence_top_overlap: int = 4
    uncertainty_bootstraps: int = 2000
    uncertainty_seed: int = 196613

    def __post_init__(self) -> None:
        """Reject settings that depart from the frozen protocol.

        Raises:
            ValueError: If there are not three distinct non-negative seeds,
                fewer than two budgets, a non-positive or non-increasing
                budget, a top-five or overlap rule other than five and four,
                a Spearman threshold outside ``[0, 1]`` or fewer than 100
                bootstrap resamples.
        """
        if len(self.seeds) != 3 or len(set(self.seeds)) != 3:
            raise ValueError("the confirmatory explanation protocol requires three seeds")
        if any(seed < 0 for seed in self.seeds):
            raise ValueError("explanation seeds must be non-negative")
        if len(self.budgets) < 2:
            raise ValueError("at least two successive sampling budgets are required")
        validation_sizes = [budget.validation_subjects for budget in self.budgets]
        background_sizes = [budget.training_background for budget in self.budgets]
        if any(value <= 0 for value in validation_sizes + background_sizes):
            raise ValueError("sampling budgets must be positive")
        if validation_sizes != sorted(set(validation_sizes)):
            raise ValueError("validation-subject budgets must increase strictly")
        if background_sizes != sorted(set(background_sizes)):
            raise ValueError("training-background budgets must increase strictly")
        if self.top_k != 5 or self.convergence_top_overlap != 4:
            raise ValueError("the frozen convergence rule is top-five overlap of at least four")
        if not 0.0 <= self.convergence_spearman <= 1.0:
            raise ValueError("the convergence Spearman threshold must be in [0, 1]")
        if self.uncertainty_bootstraps < 100:
            raise ValueError("uncertainty requires at least 100 bootstrap resamples")


def _stable_seed(base_seed: int, *parts: object) -> int:
    """Derive a reproducible 32-bit seed from a base seed and labels.

    The labels are joined with ``|``, hashed with SHA-256, and the first eight
    bytes are reduced modulo ``2**32 - 1``. The frozen result depends on this
    exact rule, so it must not be replaced by another seed helper.
    """
    payload = "|".join([str(base_seed), *(str(part) for part in parts)])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % (2**32 - 1)


def protocol_record(protocol: ExplanationProtocol) -> dict[str, Any]:
    """Return the protocol settings and a plain description of each estimand.

    The descriptions are part of the hashed explanation result, so their text
    is kept exactly as frozen. ``primary_intrinsic_estimand`` names the
    per-term form ``E(|x_j beta_j|)``; the grouped score actually compared,
    in which signed terms are summed within a source group before the
    absolute value is taken, is described under ``grouping``.

    Args:
        protocol: Immutable explanation sampling and uncertainty controls.

    Returns:
        Plain settings and estimand descriptions included in the result hash.
    """
    return {
        **asdict(protocol),
        "primary_intrinsic_estimand": "posterior expected absolute contribution E(|x_j beta_j|)",
        "primary_post_hoc_estimand": (
            "mean absolute exact interventional SHAP attribution from "
            "shap.LinearExplainer on the same posterior-mean linear risk score"
        ),
        "sampling": (
            "separate seeded permutations without replacement for validation "
            "subjects and outer-training backgrounds; selections are nested "
            "across successive budgets and paired across Bayesian priors"
        ),
        "grouping": (
            "cell preprocessing feature_groups metadata; signed transformed terms "
            "are summed within subject and source group before absolute magnitude"
        ),
        "coalition_budget": (
            "not applicable: LinearExplainer is exact for the frozen linear risk model"
        ),
        "convergence_rule": (
            "successive grouped SHAP rankings require Spearman >= 0.95 and "
            "at least four common top-five groups"
        ),
    }
