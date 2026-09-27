"""Execution controls and frozen perturbation definitions for robustness analyses."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

BAYESIAN_MODEL_KEYS = (
    "bayesian_normal",
    "bayesian_horseshoe",
    "bayesian_spike_slab",
)
MULTIPLE_IMPUTATIONS = 5
ITERATIVE_IMPUTER_MAX_ITER = 10
DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT = (1,)
RUNTIME_OVERHEAD_MULTIPLIER = 1.30


@dataclass(frozen=True)
class RobustnessOptions:
    """Execution controls for a rehearsal or frozen robustness run."""

    mode: str
    datasets: tuple[str, ...]
    components: tuple[str, ...]
    outer_splits: int
    outer_repeats: int
    fold_limit_per_dataset: int | None
    bayes_draws: int
    bayes_tune: int
    bayes_chains: int
    sensitivity_bootstraps: int
    resume: bool
    output_root: Path
    confirmatory_run_dir: Path | None = None


@dataclass(frozen=True)
class RobustnessCondition:
    """One prespecified perturbation, possibly serving several analyses."""

    condition_id: str
    analyses: tuple[tuple[str, str], ...]
    feature_set: str
    training_fraction: float
    censoring_name: str
    censoring_quantile: float | None
    prior_scenario: str
    n_intervals: int
    selected_fold_numbers: tuple[int, ...] | None
    imputation_method: str = "single_fold_local"

    def to_dict(self) -> dict[str, Any]:
        """Return the condition as a JSON-compatible mapping."""
        value = asdict(self)
        value["analyses"] = [
            {"component": component, "condition": condition}
            for component, condition in self.analyses
        ]
        return value
