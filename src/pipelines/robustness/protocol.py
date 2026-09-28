"""Execution controls and frozen perturbation definitions for robustness analyses.

Run planning, fitting and inference use these definitions. ``scripts/run_robustness.py``
builds a :class:`RobustnessOptions`; :mod:`conditions` builds one
:class:`RobustnessCondition` per planned perturbation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Only the Bayesian models are refitted, always in this order.
BAYESIAN_MODEL_KEYS = (
    "bayesian_normal",
    "bayesian_horseshoe",
    "bayesian_spike_slab",
)
# Imputed data sets, and so posterior fits, in the multiple-imputation cell.
MULTIPLE_IMPUTATIONS = 5
ITERATIVE_IMPUTER_MAX_ITER = 10
# Outer fold numbers, within every repeat, for the non-primary design and
# feature conditions; their contrasts are also restricted to these folds.
DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT = (1,)
# Allowance applied to the projected fit time for the rest of each
# cell's work in the result-blind runtime projection.
RUNTIME_OVERHEAD_MULTIPLIER = 1.30


@dataclass(frozen=True)
class RobustnessOptions:
    """Execution controls for a rehearsal or frozen robustness run.

    Args:
        mode: ``"rehearsal"`` or ``"robustness"``. Only ``robustness`` applies
            the confirmatory diagnostic gate, checks the frozen evidence and
            production controls, and labels cells as evidence.
        datasets: Cohort keys, in run order.
        components: Any of ``"rq2"`` (research question 2), ``"design"``,
            ``"feature"`` and ``"ph"`` (proportional hazards, PH); production
            requires all four.
        outer_splits: Outer folds per repeat, as in the confirmatory study.
        outer_repeats: Outer repeats, as in the confirmatory study.
        fold_limit_per_dataset: Keep only the first this-many outer folds of
            each cohort; ``None`` keeps all.
        bayes_draws: Posterior draws per chain.
        bayes_tune: No-U-Turn Sampler (NUTS) tuning steps per chain before any
            refit multiplier.
        bayes_chains: Chains per Bayesian fit.
        sensitivity_bootstraps: Replicates of the three-stage bootstrap.
        resume: Continue or verify an existing run directory.
        output_root: Parent directory of the run directory.
        confirmatory_run_dir: Completed confirmatory run that supplies the
            runtime projection and the Cox PH tests; required in
            ``robustness`` mode.
    """

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
    """One prespecified perturbation, possibly serving several analyses.

    Args:
        condition_id: Unique name, also the cell directory name.
        analyses: ``(component, condition name)`` pairs this fit serves; one
            fit can serve several after :func:`~.conditions._merge_conditions`.
        feature_set: Feature-set name from ``config/datasets.yaml``.
        training_fraction: Share of the outer-training fold used, from the
            nested event/time-stratified subsets.
        censoring_name: ``"observed_followup"`` or the name of a truncation.
        censoring_quantile: Quantile of the outer-training follow-up times
            used as an administrative cutoff; ``None`` keeps observed
            follow-up.
        prior_scenario: Key in ``robustness.prior_sensitivity_scenarios``.
        n_intervals: Number of piecewise-constant baseline-hazard intervals.
        selected_fold_numbers: Outer fold numbers fitted within every repeat;
            ``None`` means all folds.
        imputation_method: ``"single_fold_local"`` (the fold preprocessor's
            own imputation) or ``"iterative_posterior_m5"`` (five stochastic
            imputations).
    """

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
        """Return the condition with explicit component and condition labels.

        Returns:
            All dataclass fields, with ``analyses`` represented as a list of
            ``{"component", "condition"}`` mappings. Selected fold numbers remain
            a tuple or ``None`` until JSON serialisation.
        """
        value = asdict(self)
        value["analyses"] = [
            {"component": component, "condition": condition}
            for component, condition in self.analyses
        ]
        return value
