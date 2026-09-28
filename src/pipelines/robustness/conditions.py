"""Construct prespecified perturbations and their paired training subsets.

This is the planning stage of a robustness run. :func:`build_condition_plan`
turns the frozen ``robustness`` section of ``config/confirmatory.yaml`` into a
de-duplicated list of :class:`~.protocol.RobustnessCondition` records for one
cohort. For each outer fold, :func:`_fold_condition_indices` then selects the
condition's training subset and administrative cutoff, and
:func:`_condition_config` produces the protocol the fit uses.

The perturbations are:

- RQ2 (research question 2) training size: nested 25, 50, 75 and 100 percent
  subsets of the outer-training fold, identical for all three priors;
- RQ2 censoring: administrative truncation at the 75th and 50th percentiles
  of outer-training follow-up, at full training size, never crossed with
  training size;
- design: prior-scale scenarios and 4 or 10 baseline-hazard intervals, one
  factor at a time;
- feature: every sensitivity feature set, plus the METABRIC five-imputation
  condition.
"""

from __future__ import annotations

import copy
import hashlib
import math
from collections.abc import Iterable
from typing import Any

import numpy as np

from src.data.survival_folds import (
    SurvivalFold,
    event_time_strata,
)

from .protocol import (
    DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT,
    RobustnessCondition,
)


def _stable_hash(*parts: object) -> str:
    """Return the SHA-256 hex digest of the parts joined by ``"|"``."""
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def stratified_training_subsets(
    times: np.ndarray,
    events: np.ndarray,
    fractions: Iterable[float],
    *,
    seed: int,
    max_time_bins: int,
) -> dict[float, np.ndarray]:
    """Create nested event/time-stratified subsets from one outer training fold.

    A single seeded ordering is generated within every stratum. Each fraction
    takes the corresponding prefix, so subject membership is deterministic,
    nested across fractions and independent of the model or prior. Sharing
    the subsets keeps every prior contrast paired on the same training
    subjects.

    Args:
        times: Follow-up times of the outer-training fold.
        events: Event indicators of the outer-training fold.
        fractions: Requested fractions in ``(0, 1]``; must include 1.0.
        seed: Seed of the per-stratum orderings; the caller derives it from
            cohort, repeat and fold only.
        max_time_bins: Maximum follow-up bins within each event group, as
            used by the fold generator.

    Returns:
        Map from fraction to sorted positions within the outer-training fold.
        Fraction 1.0 selects every position.

    Raises:
        ValueError: The fractions or arrays are invalid.
        RuntimeError: The subsets are not nested (a defensive check).
    """
    time = np.asarray(times, dtype=float)
    event = np.asarray(events, dtype=int)
    requested = sorted({float(fraction) for fraction in fractions})
    if not requested or requested[-1] != 1.0:
        raise ValueError("training fractions must include 1.0")
    if requested[0] <= 0 or requested[-1] > 1:
        raise ValueError("training fractions must lie in (0, 1]")
    if time.ndim != 1 or event.ndim != 1 or len(time) != len(event):
        raise ValueError("times and events must be aligned one-dimensional arrays")

    # With ceil(1 / smallest fraction) as the stratifier's fold count, every
    # stratum holds at least that many subjects, so even the smallest
    # fraction takes at least one subject from each stratum.
    minimum_fraction = requested[0]
    subdivision_splits = max(2, int(math.ceil(1.0 / minimum_fraction)))
    strata = event_time_strata(
        time,
        event,
        n_splits=subdivision_splits,
        max_time_bins=max_time_bins,
    )
    rng = np.random.default_rng(seed)
    ordered: dict[str, np.ndarray] = {}
    for stratum in sorted(set(strata)):
        indices = np.flatnonzero(strata == stratum)
        ordered[stratum] = rng.permutation(indices)

    subsets: dict[float, np.ndarray] = {}
    previous: set[int] = set()
    for fraction in requested:
        selected: list[int] = []
        for stratum in sorted(ordered):
            indices = ordered[stratum]
            if fraction == 1.0:
                count = len(indices)
            else:
                # At least one subject per stratum keeps every stratum present.
                count = max(1, int(math.floor(fraction * len(indices))))
            selected.extend(indices[:count].tolist())
        subset = np.asarray(sorted(selected), dtype=int)
        if not previous.issubset(set(subset)):
            raise RuntimeError("fractional training subsets are not nested")
        previous = set(subset)
        subsets[fraction] = subset
    return subsets


def apply_administrative_censoring(
    times: np.ndarray,
    events: np.ndarray,
    cutoff: float | None,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply a fixed administrative cutoff without altering earlier events.

    Follow-up beyond ``cutoff`` is set to ``cutoff`` and censored; an event
    at or before the cutoff is kept. This mimics a study whose follow-up
    ended earlier, and can only increase the share of censored subjects.

    Args:
        times: Follow-up times, strictly positive.
        events: Event indicators (1 = event, 0 = censored).
        cutoff: Administrative end of follow-up, or ``None`` for no change.

    Returns:
        New ``(times, events)`` arrays; the inputs are not modified.

    Raises:
        ValueError: The inputs or the cutoff are invalid.
    """
    time = np.asarray(times, dtype=float)
    event = np.asarray(events, dtype=int)
    if time.ndim != 1 or event.ndim != 1 or len(time) != len(event):
        raise ValueError("times and events must be aligned one-dimensional arrays")
    if not np.isfinite(time).all() or np.any(time <= 0):
        raise ValueError("survival times must be finite and strictly positive")
    if not np.isin(event, (0, 1)).all():
        raise ValueError("events must contain only 0 and 1")
    if cutoff is None:
        return time.copy(), event.copy()
    threshold = float(cutoff)
    if not np.isfinite(threshold) or threshold <= 0:
        raise ValueError("administrative cutoff must be finite and positive")
    truncated_time = np.minimum(time, threshold)
    truncated_event = (event.astype(bool) & (time <= threshold)).astype(int)
    return truncated_time, truncated_event


def effective_information_ratio(events_train: int, transformed_columns: int) -> float:
    """Return observed training events per processed predictor degree of freedom.

    This is the RQ2 information measure. ``transformed_columns`` counts the
    columns after encoding, so a categorical variable contributes one degree
    of freedom per non-reference level.

    Args:
        events_train: Observed event count after subsetting and any cutoff.
        transformed_columns: Encoded predictor-column count, excluding a
            reference level for each categorical predictor.

    Returns:
        Training events divided by the processed predictor-column count.

    Raises:
        ValueError: ``events_train`` is negative or ``transformed_columns``
            is below 1.
    """
    events = int(events_train)
    columns = int(transformed_columns)
    if events < 0:
        raise ValueError("events_train cannot be negative")
    if columns < 1:
        raise ValueError("transformed feature count must be positive")
    return float(events / columns)


def build_rq2_conditions(config: dict[str, Any]) -> list[RobustnessCondition]:
    """Build the frozen, deliberately non-factorial RQ2 condition grid.

    One condition per training fraction with observed follow-up, plus one
    per truncation quantile at full training size. Sample size and censoring
    are never crossed, as ADR-023 prescribes, which keeps the grid within the
    compute budget. All conditions use the primary priors, the primary number
    of baseline intervals and outer folds 1 and 2 of every repeat.

    Args:
        config: Frozen protocol containing training fractions, censoring
            quantiles, selected folds and the primary Bayesian design.

    Returns:
        Training-fraction conditions followed by non-null censoring conditions,
        in their declared configuration order.

    Raises:
        ValueError: The protocol asks to cross fraction with censoring.
    """
    robustness = config["robustness"]
    if bool(robustness["cross_fraction_by_censoring"]):
        raise ValueError("RQ2 requires cross_fraction_by_censoring=false")
    fractions = [float(value) for value in robustness["training_fractions"]]
    selected = tuple(int(value) for value in robustness["outer_fold_numbers_per_repeat"])
    primary_intervals = int(config["models"]["bayesian_cox"]["n_intervals"])
    conditions = [
        RobustnessCondition(
            condition_id=f"rq2_fraction_{round(100 * fraction):03d}_observed",
            analyses=(("rq2", f"fraction_{round(100 * fraction):03d}_observed"),),
            feature_set=config["feature_set"],
            training_fraction=fraction,
            censoring_name="observed_followup",
            censoring_quantile=None,
            prior_scenario="primary",
            n_intervals=primary_intervals,
            selected_fold_numbers=selected,
        )
        for fraction in fractions
    ]
    for declaration in robustness["administrative_censoring"]:
        quantile = declaration["training_followup_quantile"]
        if quantile is None:
            continue
        conditions.append(
            RobustnessCondition(
                condition_id=f"rq2_{declaration['name']}",
                analyses=(("rq2", str(declaration["name"])),),
                feature_set=config["feature_set"],
                training_fraction=1.0,
                censoring_name=str(declaration["name"]),
                censoring_quantile=float(quantile),
                prior_scenario="primary",
                n_intervals=primary_intervals,
                selected_fold_numbers=selected,
            )
        )
    return conditions


def build_design_conditions(config: dict[str, Any]) -> list[RobustnessCondition]:
    """Build one-factor-at-a-time prior-scale and baseline-resolution checks.

    Each prior scenario (tighter, primary, wider) uses the primary baseline
    resolution; each non-primary number of baseline intervals uses the
    primary priors. The primary scenario keeps the RQ2 folds (1 and 2), so it
    merges with the full-size RQ2 condition; the others use fold 1 only.

    Args:
        config: Frozen protocol containing prior-scale scenarios, baseline
            interval counts and the primary design.

    Returns:
        Prior-scale conditions followed by non-primary baseline resolutions,
        in their declared configuration order.
    """
    robustness = config["robustness"]
    primary_anchor_folds = tuple(
        int(value) for value in robustness["outer_fold_numbers_per_repeat"]
    )
    primary_intervals = int(config["models"]["bayesian_cox"]["n_intervals"])
    conditions: list[RobustnessCondition] = []
    for scenario in robustness["prior_sensitivity_scenarios"]:
        conditions.append(
            RobustnessCondition(
                condition_id=f"design_prior_{scenario}_intervals_{primary_intervals}",
                analyses=(("design", f"prior_{scenario}"),),
                feature_set=config["feature_set"],
                training_fraction=1.0,
                censoring_name="observed_followup",
                censoring_quantile=None,
                prior_scenario=str(scenario),
                n_intervals=primary_intervals,
                selected_fold_numbers=(
                    primary_anchor_folds
                    if scenario == "primary"
                    else DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT
                ),
            )
        )
    for intervals in robustness["baseline_intervals"]:
        value = int(intervals)
        if value == primary_intervals:
            continue
        conditions.append(
            RobustnessCondition(
                condition_id=f"design_prior_primary_intervals_{value}",
                analyses=(("design", f"baseline_intervals_{value}"),),
                feature_set=config["feature_set"],
                training_fraction=1.0,
                censoring_name="observed_followup",
                censoring_quantile=None,
                prior_scenario="primary",
                n_intervals=value,
                selected_fold_numbers=DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT,
            )
        )
    return conditions


def build_feature_conditions(
    config: dict[str, Any], dataset_config: dict[str, Any]
) -> list[RobustnessCondition]:
    """Declare conditions for the named feature representations in datasets.yaml.

    The primary feature set keeps the RQ2 folds (1 and 2); every sensitivity
    feature set uses fold 1. For METABRIC, when ``npi_plus_stage`` is
    defined, a further condition fits that set with five stochastic
    imputations (see :mod:`~.imputation`).

    Args:
        config: Frozen protocol supplying the primary feature set and design.
        dataset_config: Cohort declaration with sensitivity feature-set names.

    Returns:
        The primary and sensitivity feature conditions, plus the five-imputation
        condition when METABRIC declares ``npi_plus_stage``. Feature contents are
        resolved later by the runner.
    """
    primary_intervals = int(config["models"]["bayesian_cox"]["n_intervals"])
    primary_anchor_folds = tuple(
        int(value) for value in config["robustness"]["outer_fold_numbers_per_repeat"]
    )
    names = [config["feature_set"], *dataset_config.get("sensitivity_feature_sets", {})]
    conditions = [
        RobustnessCondition(
            condition_id=f"feature_{name}",
            analyses=(("feature", str(name)),),
            feature_set=str(name),
            training_fraction=1.0,
            censoring_name="observed_followup",
            censoring_quantile=None,
            prior_scenario="primary",
            n_intervals=primary_intervals,
            selected_fold_numbers=(
                primary_anchor_folds
                if name == config["feature_set"]
                else DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT
            ),
        )
        for name in names
    ]
    if str(
        dataset_config.get("name", "")
    ).upper() == "METABRIC" and "npi_plus_stage" in dataset_config.get(
        "sensitivity_feature_sets", {}
    ):
        conditions.append(
            RobustnessCondition(
                condition_id="feature_npi_plus_stage_mi5",
                analyses=(("feature", "npi_plus_stage_multiple_imputation"),),
                feature_set="npi_plus_stage",
                training_fraction=1.0,
                censoring_name="observed_followup",
                censoring_quantile=None,
                prior_scenario="primary",
                n_intervals=primary_intervals,
                selected_fold_numbers=DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT,
                imputation_method="iterative_posterior_m5",
            )
        )
    return conditions


def _merge_conditions(conditions: Iterable[RobustnessCondition]) -> list[RobustnessCondition]:
    """Merge identical fits while retaining every analysis role.

    Conditions that would fit exactly the same model on the same subjects
    are fitted once; the merged record keeps the first condition's id and the
    union of the analyses it serves.

    Returns:
        The merged conditions, sorted by ``condition_id``.
    """
    merged: dict[tuple[Any, ...], RobustnessCondition] = {}
    for condition in conditions:
        key = (
            condition.feature_set,
            condition.training_fraction,
            condition.censoring_name,
            condition.censoring_quantile,
            condition.prior_scenario,
            condition.n_intervals,
            condition.selected_fold_numbers,
            condition.imputation_method,
        )
        if key not in merged:
            merged[key] = condition
            continue
        existing = merged[key]
        analyses = tuple(sorted(set(existing.analyses + condition.analyses)))
        merged[key] = RobustnessCondition(
            condition_id=existing.condition_id,
            analyses=analyses,
            feature_set=existing.feature_set,
            training_fraction=existing.training_fraction,
            censoring_name=existing.censoring_name,
            censoring_quantile=existing.censoring_quantile,
            prior_scenario=existing.prior_scenario,
            n_intervals=existing.n_intervals,
            selected_fold_numbers=existing.selected_fold_numbers,
            imputation_method=existing.imputation_method,
        )
    return sorted(merged.values(), key=lambda item: item.condition_id)


def build_condition_plan(
    config: dict[str, Any],
    dataset_config: dict[str, Any],
    components: Iterable[str],
) -> list[RobustnessCondition]:
    """Return the deduplicated fit plan for one cohort.

    Args:
        config: Frozen protocol from ``config/confirmatory.yaml``.
        dataset_config: This cohort's entry in ``config/datasets.yaml``.
        components: Fitted components to include: ``"rq2"``, ``"design"``
            and/or ``"feature"``.

    Returns:
        Conditions sorted by identifier, with identical fit specifications
        merged and every analysis role retained.

    Raises:
        ValueError: An unknown component was requested.
    """
    requested = set(components)
    unknown = requested - {"rq2", "design", "feature"}
    if unknown:
        raise ValueError(f"unknown fitted robustness components: {sorted(unknown)}")
    conditions: list[RobustnessCondition] = []
    if "rq2" in requested:
        conditions.extend(build_rq2_conditions(config))
    if "design" in requested:
        conditions.extend(build_design_conditions(config))
    if "feature" in requested:
        conditions.extend(build_feature_conditions(config, dataset_config))
    return _merge_conditions(conditions)


def _condition_config(config: dict[str, Any], condition: RobustnessCondition) -> dict[str, Any]:
    """Return a copy of the protocol with the condition's baseline intervals and prior scales.

    Raises:
        ValueError: The condition names an unknown prior scenario.
    """
    modified = copy.deepcopy(config)
    modified["models"]["bayesian_cox"]["n_intervals"] = condition.n_intervals
    scenarios = modified["robustness"]["prior_sensitivity_scenarios"]
    if condition.prior_scenario not in scenarios:
        raise ValueError(f"unknown prior scenario {condition.prior_scenario!r}")
    for prior, parameters in scenarios[condition.prior_scenario].items():
        modified["models"]["bayesian_cox"]["priors"][prior]["prior_params"] = dict(parameters)
    return modified


def _fold_condition_indices(
    condition: RobustnessCondition,
    fold: SurvivalFold,
    fold_times: np.ndarray,
    fold_events: np.ndarray,
    fractions: Iterable[float],
    *,
    seed: int,
    max_time_bins: int,
) -> tuple[np.ndarray, float | None]:
    """Return a condition's training rows in the cohort frame and its cutoff.

    Args:
        condition: The planned perturbation.
        fold: Outer fold whose training rows are subset.
        fold_times: Follow-up times of the outer-training rows.
        fold_events: Event indicators of the outer-training rows.
        fractions: Every RQ2 training fraction, so the nested subsets are the
            same whichever condition asks for them.
        seed: Subset seed for this cohort, repeat and fold.
        max_time_bins: Maximum follow-up bins used for stratification.

    Returns:
        ``(train_indices, cutoff)``: cohort row positions and the
        administrative cutoff, or ``None`` for observed follow-up.
    """
    subsets = stratified_training_subsets(
        fold_times,
        fold_events,
        fractions,
        seed=seed,
        max_time_bins=max_time_bins,
    )
    selected = subsets[condition.training_fraction]
    # The cutoff is a quantile of the whole outer-training follow-up, events
    # and censored times alike, so it uses no validation outcome.
    cutoff = (
        None
        if condition.censoring_quantile is None
        else float(np.quantile(fold_times, condition.censoring_quantile))
    )
    return fold.train_indices[selected], cutoff
