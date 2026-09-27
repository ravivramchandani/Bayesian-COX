"""Construct prespecified perturbations and their paired training subsets."""

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
    nested across fractions and independent of the model or prior.
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
    """Apply a fixed administrative cutoff without altering earlier events."""
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
    """Return observed training events per processed predictor degree of freedom."""
    events = int(events_train)
    columns = int(transformed_columns)
    if events < 0:
        raise ValueError("events_train cannot be negative")
    if columns < 1:
        raise ValueError("transformed feature count must be positive")
    return float(events / columns)


def build_rq2_conditions(config: dict[str, Any]) -> list[RobustnessCondition]:
    """Build the frozen, deliberately non-factorial RQ2 condition grid."""
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
    """Build one-factor-at-a-time prior-scale and baseline-resolution checks."""
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
    """Use every complete, named feature representation in datasets.yaml."""
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
    """Merge identical fits while retaining every analysis role."""
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
    """Return the deduplicated fit plan for one cohort."""
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
    subsets = stratified_training_subsets(
        fold_times,
        fold_events,
        fractions,
        seed=seed,
        max_time_bins=max_time_bins,
    )
    selected = subsets[condition.training_fraction]
    cutoff = (
        None
        if condition.censoring_quantile is None
        else float(np.quantile(fold_times, condition.censoring_quantile))
    )
    return fold.train_indices[selected], cutoff
