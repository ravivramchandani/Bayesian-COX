"""Frozen robustness analyses built on the confirmatory outer folds."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import sys
import time
import traceback
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.experimental import enable_iterative_imputer  # noqa: F401
from sklearn.impute import IterativeImputer
from sksurv.nonparametric import CensoringDistributionEstimator

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.data.survival_folds import (
    SurvivalFold,
    event_time_strata,
    repeated_survival_folds,
)
from src.evaluation.metrics import (
    harrell_c_index,
    integrated_brier,
    time_dependent_auc,
    uno_c_index,
)
from src.pipelines.confirmatory import (
    DiagnosticFailure,
    RunOptions,
    _feature_spec,
    _fit_with_diagnostic_rule,
    _ibs_times,
    administratively_truncate_for_ipcw,
    deterministic_seed,
    load_analysis_dataset,
    relevant_input_files,
    validate_survival_prediction_matrix,
    verify_protocol_freeze,
)
from src.statistics.hypothesis_tests import holm_adjust
from src.utils.reproducibility import (
    build_run_manifest,
    canonical_json_hash,
    sha256_file,
)

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


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, np.ndarray):
        return _json_safe(value.tolist())
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.floating, float)):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    if value is None or isinstance(value, str):
        return value
    return str(value)


def _atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(_json_safe(value), indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


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


def planned_fit_counts(
    plans: dict[str, list[RobustnessCondition]],
    *,
    outer_repeats: int,
    outer_splits: int,
) -> dict[str, Any]:
    """Count checkpoint cells and underlying Bayesian fits before execution."""
    grouped: list[dict[str, Any]] = []
    total_cells = 0
    total_fits = 0
    for dataset, conditions in sorted(plans.items()):
        for model_key in BAYESIAN_MODEL_KEYS:
            cells = 0
            fits = 0
            for condition in conditions:
                selected = condition.selected_fold_numbers
                fold_count = outer_splits if selected is None else len(selected)
                if selected is not None and any(
                    fold < 1 or fold > outer_splits for fold in selected
                ):
                    raise ValueError("robustness condition selects an invalid outer fold")
                condition_cells = outer_repeats * fold_count
                multiplier = (
                    MULTIPLE_IMPUTATIONS
                    if condition.imputation_method == "iterative_posterior_m5"
                    else 1
                )
                cells += condition_cells
                fits += condition_cells * multiplier
            grouped.append(
                {
                    "dataset": dataset,
                    "model_key": model_key,
                    "checkpoint_cells": cells,
                    "bayesian_fits": fits,
                }
            )
            total_cells += cells
            total_fits += fits
    return {
        "schema_version": "1.0.0",
        "grouped": grouped,
        "total_checkpoint_cells": total_cells,
        "total_bayesian_fits": total_fits,
        "calibration_bootstrap_replicates_per_cell": 0,
        "rq2_fold_numbers_per_repeat": sorted(
            {
                fold
                for conditions in plans.values()
                for condition in conditions
                for component, _name in condition.analyses
                if component == "rq2"
                for fold in condition.selected_fold_numbers or ()
            }
        ),
        "design_feature_fold_numbers_per_repeat": list(DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT),
    }


def projected_runtime_from_confirmatory(
    confirmatory_run_dir: Path,
    fit_counts: dict[str, Any],
    *,
    maximum_hours: float,
    target_draws: int,
    target_tune: int,
    target_chains: int,
) -> dict[str, Any]:
    """Project serial runtime from result-blind confirmatory fit timings."""
    manifest_path = confirmatory_run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"runtime source manifest is missing: {manifest_path}")
    source_config = json.loads(manifest_path.read_text(encoding="utf-8"))["run_config"]
    source_work = (int(source_config["bayes_draws"]) + int(source_config["bayes_tune"])) * int(
        source_config["bayes_chains"]
    )
    target_work = (int(target_draws) + int(target_tune)) * int(target_chains)
    if source_work <= 0 or target_work <= 0:
        raise ValueError("runtime projection requires positive MCMC work counts")
    mcmc_work_multiplier = float(target_work / source_work)
    timings: dict[tuple[str, str], list[float]] = {}
    source_hashes: dict[str, str] = {}
    for path in sorted(confirmatory_run_dir.glob("cells/*/*/bayesian_*.json")):
        cell = json.loads(path.read_text(encoding="utf-8"))
        claimed = cell.get("cell_content_sha256")
        unhashed = dict(cell)
        unhashed.pop("cell_content_sha256", None)
        if claimed != canonical_json_hash(unhashed):
            raise ValueError(f"confirmatory cell hash does not match: {path}")
        attempts = cell.get("fit_attempts", [])
        seconds = float(sum(float(item["fit_seconds"]) for item in attempts))
        if not np.isfinite(seconds) or seconds <= 0:
            continue
        key = (str(cell["dataset"]), str(cell["model_key"]))
        timings.setdefault(key, []).append(seconds)
        source_hashes[str(path.relative_to(confirmatory_run_dir))] = sha256_file(path)

    grouped_projection: list[dict[str, Any]] = []
    projected_seconds = 0.0
    for row in fit_counts["grouped"]:
        key = (str(row["dataset"]), str(row["model_key"]))
        values = timings.get(key, [])
        if not values:
            raise RuntimeError(
                "runtime projection requires completed confirmatory Bayesian "
                f"timings for {key[0]}/{key[1]}"
            )
        median_seconds = float(np.median(values)) * mcmc_work_multiplier
        group_seconds = median_seconds * int(row["bayesian_fits"])
        projected_seconds += group_seconds
        grouped_projection.append(
            {
                **row,
                "n_confirmatory_timing_cells": len(values),
                "median_confirmatory_fit_seconds": median_seconds,
                "projected_fit_seconds_before_overhead": group_seconds,
            }
        )
    projected_with_overhead = projected_seconds * RUNTIME_OVERHEAD_MULTIPLIER
    projected_hours = projected_with_overhead / 3600.0
    result = {
        "schema_version": "1.0.0",
        "basis": (
            "median same-cohort/same-prior total sampler time from frozen "
            "confirmatory cells; no performance effect is inspected"
        ),
        "grouped": grouped_projection,
        "overhead_multiplier": RUNTIME_OVERHEAD_MULTIPLIER,
        "mcmc_work_multiplier": mcmc_work_multiplier,
        "source_sampling": {
            "draws": int(source_config["bayes_draws"]),
            "tune": int(source_config["bayes_tune"]),
            "chains": int(source_config["bayes_chains"]),
        },
        "target_sampling": {
            "draws": int(target_draws),
            "tune": int(target_tune),
            "chains": int(target_chains),
        },
        "projected_serial_hours": projected_hours,
        "maximum_projected_hours": float(maximum_hours),
        "feasible": bool(projected_hours <= maximum_hours),
        "source_cell_sha256": source_hashes,
    }
    result["projection_content_sha256"] = canonical_json_hash(result)
    return result


def _condition_config(config: dict[str, Any], condition: RobustnessCondition) -> dict[str, Any]:
    modified = copy.deepcopy(config)
    modified["models"]["bayesian_cox"]["n_intervals"] = condition.n_intervals
    scenarios = modified["robustness"]["prior_sensitivity_scenarios"]
    if condition.prior_scenario not in scenarios:
        raise ValueError(f"unknown prior scenario {condition.prior_scenario!r}")
    for prior, parameters in scenarios[condition.prior_scenario].items():
        modified["models"]["bayesian_cox"]["priors"][prior]["prior_params"] = dict(parameters)
    return modified


def _as_structured(times: np.ndarray, events: np.ndarray) -> np.ndarray:
    outcome = np.empty(len(times), dtype=[("event", "?"), ("time", "<f8")])
    outcome["event"] = np.asarray(events, dtype=bool)
    outcome["time"] = np.asarray(times, dtype=float)
    return outcome


def individual_integrated_brier_losses(
    train_time: np.ndarray,
    train_event: np.ndarray,
    validation_time: np.ndarray,
    validation_event: np.ndarray,
    survival_probabilities: np.ndarray,
    evaluation_times: np.ndarray,
) -> np.ndarray:
    """Return subject contributions whose mean equals reference IPCW IBS."""
    train_t = np.asarray(train_time, dtype=float)
    train_e = np.asarray(train_event, dtype=int)
    valid_t = np.asarray(validation_time, dtype=float)
    valid_e = np.asarray(validation_event, dtype=int)
    predictions = np.asarray(survival_probabilities, dtype=float)
    grid = np.asarray(evaluation_times, dtype=float)
    if predictions.shape != (len(valid_t), len(grid)):
        raise ValueError("survival probabilities do not match validation rows/grid")
    if len(grid) < 2 or np.any(np.diff(grid) <= 0):
        raise ValueError("evaluation times must contain at least two increasing values")
    valid_t, valid_e = administratively_truncate_for_ipcw(valid_t, valid_e, float(grid[-1]))

    censoring = CensoringDistributionEstimator().fit(_as_structured(train_t, train_e))
    censoring_at_grid = censoring.predict_proba(grid)
    censoring_at_observation = censoring.predict_proba(valid_t)
    censoring_at_grid[censoring_at_grid == 0] = np.inf
    censoring_at_observation[censoring_at_observation == 0] = np.inf

    contributions = np.empty_like(predictions, dtype=float)
    for column, horizon in enumerate(grid):
        probability = predictions[:, column]
        cases = (valid_t <= horizon) & valid_e.astype(bool)
        controls = valid_t > horizon
        contributions[:, column] = (
            probability**2 * cases / censoring_at_observation
            + (1.0 - probability) ** 2 * controls / censoring_at_grid[column]
        )
    return np.trapezoid(contributions, grid, axis=1) / (grid[-1] - grid[0])


def summarize_imputation_predictions(
    train_time: np.ndarray,
    train_event: np.ndarray,
    validation_time: np.ndarray,
    validation_event: np.ndarray,
    risk: np.ndarray,
    survival_on_ibs_grid: np.ndarray,
    ibs_grid: np.ndarray,
    horizons: np.ndarray,
) -> dict[str, Any]:
    """Evaluate one imputation with the confirmatory IPCW truncation rule."""
    horizon_values = np.asarray(horizons, dtype=float)
    tau = float(horizon_values[-1])
    ipcw_time, ipcw_event = administratively_truncate_for_ipcw(
        validation_time, validation_event, tau
    )
    risk_values = np.asarray(risk, dtype=float)
    losses = individual_integrated_brier_losses(
        train_time,
        train_event,
        ipcw_time,
        ipcw_event,
        survival_on_ibs_grid,
        ibs_grid,
    )
    auc, mean_auc = time_dependent_auc(
        train_time,
        train_event,
        ipcw_time,
        ipcw_event,
        risk_values,
        horizon_values,
    )
    return {
        "ibs": float(np.mean(losses)),
        "harrell_c_index": harrell_c_index(validation_time, validation_event, risk_values),
        "uno_c_index": uno_c_index(
            train_time,
            train_event,
            ipcw_time,
            ipcw_event,
            risk_values,
            tau=tau,
        ),
        "auc_at_horizons": auc,
        "mean_auc": mean_auc,
        "ipcw_administrative_truncation_tau": tau,
    }


def evaluate_robustness_predictions(
    model: Any,
    x_validation: pd.DataFrame,
    train_time: np.ndarray,
    train_event: np.ndarray,
    validation_time: np.ndarray,
    validation_event: np.ndarray,
    *,
    evaluation_config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Evaluate frozen IBS sensitivities without calibration refitting/bootstrap.

    Calibration belongs to the full 5x5 confirmatory analysis. Robustness cells
    preserve the primary IBS estimand plus discrimination descriptors and do
    not spend compute re-estimating calibration in every sensitivity cell.
    """
    horizons, ibs_grid = _ibs_times(train_time, train_event, evaluation_config)
    prediction_times = np.unique(np.concatenate([horizons, ibs_grid]))
    risk = np.asarray(model.predict_risk(x_validation), dtype=float)
    survival = np.asarray(model.predict_survival(x_validation, prediction_times), dtype=float)
    validate_survival_prediction_matrix(
        survival, n_samples=len(x_validation), n_times=len(prediction_times)
    )
    horizon_indices = np.searchsorted(prediction_times, horizons)
    grid_indices = np.searchsorted(prediction_times, ibs_grid)
    horizon_survival = survival[:, horizon_indices]
    grid_survival = survival[:, grid_indices]
    tau = float(horizons[-1])
    ipcw_time, ipcw_event = administratively_truncate_for_ipcw(
        validation_time, validation_event, tau
    )
    auc, mean_auc = time_dependent_auc(
        train_time,
        train_event,
        ipcw_time,
        ipcw_event,
        risk,
        horizons,
    )
    metrics = {
        "harrell_c_index": harrell_c_index(validation_time, validation_event, risk),
        "uno_c_index": uno_c_index(
            train_time,
            train_event,
            ipcw_time,
            ipcw_event,
            risk,
            tau=tau,
        ),
        "uno_tau": tau,
        "ipcw_administrative_truncation_tau": tau,
        "ibs": integrated_brier(
            train_time,
            train_event,
            ipcw_time,
            ipcw_event,
            grid_survival,
            ibs_grid,
        ),
        "mean_auc": mean_auc,
        "auc_at_horizons": auc,
        "horizons": horizons,
        "ibs_grid": ibs_grid,
        "calibration": {
            "status": "not_reestimated_in_ibs_robustness_sensitivity",
            "bootstrap_replicates": 0,
            "source": "full 5x5 confirmatory analysis",
        },
    }
    predictions = {
        "risk": risk,
        "horizons": horizons,
        "survival_at_horizons": horizon_survival,
        "ibs_grid": ibs_grid,
        "survival_on_ibs_grid": grid_survival,
    }
    return metrics, predictions


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


def multiple_imputed_fold_frames(
    raw_training: pd.DataFrame,
    raw_validation: pd.DataFrame,
    feature_spec: dict[str, Any],
    *,
    seeds: Iterable[int],
) -> list[tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]]:
    """Fit five stochastic numeric imputers on training data only.

    Numeric variables use posterior draws from an iterative Bayesian-ridge
    imputer. Categorical and ordinal missing values use a mode learned from
    the same outer-training fold. Each returned validation frame is transformed
    by its corresponding fitted imputer without refitting.
    """
    numeric = [str(name) for name in feature_spec.get("numeric", [])]
    categorical = [str(name) for name in feature_spec.get("categorical", [])]
    ordinal = [str(name) for name in feature_spec.get("ordinal", {})]
    if set(numeric) != {
        "age_at_diagnosis",
        "nottingham_prognostic_index",
        "tumor_stage",
    }:
        raise ValueError(
            "the frozen multiple-imputation sensitivity is defined only for "
            "METABRIC age, NPI and tumour stage"
        )
    seed_values = [int(seed) for seed in seeds]
    if len(seed_values) != MULTIPLE_IMPUTATIONS or len(set(seed_values)) != len(seed_values):
        raise ValueError("multiple imputation requires five distinct seeds")

    train_base = raw_training.copy()
    validation_base = raw_validation.copy()
    modes: dict[str, Any] = {}
    for name in [*categorical, *ordinal]:
        observed = train_base[name].dropna()
        if observed.empty:
            raise ValueError(f"categorical feature {name!r} has no training mode")
        mode_values = observed.mode(dropna=True)
        mode = mode_values.iloc[0]
        modes[name] = mode
        train_base[name] = train_base[name].fillna(mode)
        validation_base[name] = validation_base[name].fillna(mode)

    train_numeric = train_base[numeric].apply(pd.to_numeric, errors="coerce")
    validation_numeric = validation_base[numeric].apply(pd.to_numeric, errors="coerce")
    results: list[tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]] = []
    for imputation, seed in enumerate(seed_values, start=1):
        imputer = IterativeImputer(
            max_iter=ITERATIVE_IMPUTER_MAX_ITER,
            sample_posterior=True,
            random_state=seed,
            skip_complete=False,
        )
        imputed_training = imputer.fit_transform(train_numeric)
        imputed_validation = imputer.transform(validation_numeric)
        train_frame = train_base.copy()
        validation_frame = validation_base.copy()
        train_frame.loc[:, numeric] = imputed_training
        validation_frame.loc[:, numeric] = imputed_validation
        metadata = {
            "imputation": imputation,
            "seed": seed,
            "implementation": "sklearn.impute.IterativeImputer",
            "estimator": "BayesianRidge (IterativeImputer default)",
            "sample_posterior": True,
            "max_iter": ITERATIVE_IMPUTER_MAX_ITER,
            "numeric_columns": numeric,
            "categorical_mode_columns": [*categorical, *ordinal],
            "categorical_modes": {name: str(value) for name, value in modes.items()},
            "fit_scope": "outer training fold only",
            "validation_refit": False,
        }
        results.append((train_frame, validation_frame, metadata))
    return results


class _MultipleImputationPredictionEnsemble:
    """Average predictions from independently fitted imputation-specific models."""

    def __init__(self, models: list[Any], validation_frames: list[pd.DataFrame]) -> None:
        if len(models) != MULTIPLE_IMPUTATIONS or len(models) != len(validation_frames):
            raise ValueError("prediction ensemble requires all five imputations")
        self.models = models
        self.validation_frames = validation_frames

    def predict_risk(self, frame: pd.DataFrame) -> np.ndarray:
        """Average imputation-specific posterior-mean risk scores."""
        if len(frame) != len(self.validation_frames[0]):
            raise ValueError("ensemble is bound to its outer-validation fold")
        values = [
            np.asarray(model.predict_risk(validation), dtype=float)
            for model, validation in zip(self.models, self.validation_frames, strict=True)
        ]
        return np.mean(values, axis=0)

    def predict_survival(self, frame: pd.DataFrame, evaluation_times: np.ndarray) -> np.ndarray:
        """Average survival probabilities across imputations."""
        if len(frame) != len(self.validation_frames[0]):
            raise ValueError("ensemble is bound to its outer-validation fold")
        values = [
            np.asarray(model.predict_survival(validation, evaluation_times), dtype=float)
            for model, validation in zip(self.models, self.validation_frames, strict=True)
        ]
        return np.mean(values, axis=0)


def run_robustness_cell(
    dataset_key: str,
    model_key: str,
    fold: SurvivalFold,
    condition: RobustnessCondition,
    raw: pd.DataFrame,
    times: np.ndarray,
    events: np.ndarray,
    subject_ids: np.ndarray,
    feature_spec: dict[str, Any],
    train_indices: np.ndarray,
    censoring_cutoff: float | None,
    *,
    config: dict[str, Any],
    options: RobustnessOptions,
    data_sha256: str,
) -> dict[str, Any]:
    """Fit and evaluate one content-addressed Bayesian robustness cell."""
    started = time.perf_counter()
    validation_indices = fold.validation_indices
    train_time, train_event = apply_administrative_censoring(
        times[train_indices], events[train_indices], censoring_cutoff
    )
    validation_time, validation_event = apply_administrative_censoring(
        times[validation_indices], events[validation_indices], censoring_cutoff
    )
    seed = deterministic_seed(
        int(config["validation"]["base_seed"]),
        "robustness",
        dataset_key,
        fold.repeat,
        fold.fold,
        condition.condition_id,
        model_key,
    )
    subset_hash = canonical_json_hash(subject_ids[train_indices].tolist())
    outcome_hash = canonical_json_hash(
        {
            "train_time": train_time.tolist(),
            "train_event": train_event.tolist(),
            "validation_time": validation_time.tolist(),
            "validation_event": validation_event.tolist(),
        }
    )
    base: dict[str, Any] = {
        "schema_version": "1.0.0",
        "analysis_id": f"{config['analysis_id']}_robustness",
        "analysis_mode": options.mode,
        "evidence_status": (
            "frozen_robustness" if options.mode == "robustness" else "rehearsal_only"
        ),
        "dataset": dataset_key,
        "dataset_sha256": data_sha256,
        "model_key": model_key,
        "prior": model_key.removeprefix("bayesian_"),
        "repeat": fold.repeat,
        "fold": fold.fold,
        "fold_seed": fold.seed,
        "cell_seed": seed,
        "condition": condition.to_dict(),
        "train_subject_ids": subject_ids[train_indices],
        "validation_subject_ids": subject_ids[validation_indices],
        "training_subset_sha256": subset_hash,
        "modified_outcomes_sha256": outcome_hash,
        "n_train": len(train_indices),
        "n_validation": len(validation_indices),
        "events_train": int(train_event.sum()),
        "events_validation": int(validation_event.sum()),
        "processed_feature_degrees_of_freedom": None,
        "effective_information_events_per_degree_of_freedom": None,
        "original_events_validation": events[validation_indices],
        "administrative_cutoff": censoring_cutoff,
    }
    minimum_events = int(config["robustness"]["minimum_training_events"])
    if int(train_event.sum()) < minimum_events:
        base.update(
            {
                "status": "unavailable_minimum_training_events",
                "minimum_training_events": minimum_events,
                "message": (
                    f"condition has {int(train_event.sum())} training events; "
                    f"at least {minimum_events} are required"
                ),
                "total_seconds": time.perf_counter() - started,
            }
        )
        base["cell_content_sha256"] = canonical_json_hash(_json_safe(base))
        return base

    try:
        fit_config = _condition_config(config, condition)
        confirmatory_options = RunOptions(
            mode="confirmatory" if options.mode == "robustness" else "rehearsal",
            datasets=(dataset_key,),
            models=(model_key,),
            outer_splits=options.outer_splits,
            outer_repeats=options.outer_repeats,
            fold_limit_per_dataset=None,
            bayes_draws=options.bayes_draws,
            bayes_tune=options.bayes_tune,
            bayes_chains=options.bayes_chains,
            calibration_bootstraps=0,
            resume=options.resume,
            output_root=options.output_root,
        )
        if condition.imputation_method == "iterative_posterior_m5":
            imputation_seeds = [
                deterministic_seed(seed, "imputation", number)
                for number in range(1, MULTIPLE_IMPUTATIONS + 1)
            ]
            imputed = multiple_imputed_fold_frames(
                raw.iloc[train_indices],
                raw.iloc[validation_indices],
                feature_spec,
                seeds=imputation_seeds,
            )
            models: list[Any] = []
            x_validations: list[pd.DataFrame] = []
            preprocessing_records: list[dict[str, Any]] = []
            fit_records: list[dict[str, Any]] = []
            for number, (
                imputed_train,
                imputed_validation,
                imputation_metadata,
            ) in enumerate(imputed, start=1):
                processor = FoldFeaturePreprocessor(feature_spec)
                x_train = processor.fit_transform(imputed_train)
                x_validation = processor.transform(imputed_validation)
                try:
                    model, attempts = _fit_with_diagnostic_rule(
                        model_key,
                        {},
                        x_train,
                        train_time,
                        train_event,
                        seed=deterministic_seed(seed, "imputed_fit", number),
                        config=fit_config,
                        options=confirmatory_options,
                    )
                except DiagnosticFailure as exc:
                    tagged = [{"imputation": number, **attempt} for attempt in exc.attempts]
                    raise DiagnosticFailure(tagged) from exc
                models.append(model)
                x_validations.append(x_validation)
                preprocessing_records.append(
                    {
                        "imputation": imputation_metadata,
                        "fold_preprocessor": processor.metadata(),
                    }
                )
                fit_records.append(
                    {
                        "imputation": number,
                        "imputation_seed": imputation_seeds[number - 1],
                        "attempts": attempts,
                    }
                )
            feature_schemas = [tuple(frame.columns) for frame in x_validations]
            if any(schema != feature_schemas[0] for schema in feature_schemas[1:]):
                raise RuntimeError("multiple-imputation transformed feature schemas do not match")
            transformed_columns = len(feature_schemas[0])
            ensemble = _MultipleImputationPredictionEnsemble(models, x_validations)
            metrics, predictions = evaluate_robustness_predictions(
                ensemble,
                x_validations[0],
                train_time,
                train_event,
                validation_time,
                validation_event,
                evaluation_config=config["evaluation"],
            )
            imputation_metrics: list[dict[str, Any]] = []
            for number, (model, x_validation) in enumerate(
                zip(models, x_validations, strict=True), start=1
            ):
                risk = np.asarray(model.predict_risk(x_validation), dtype=float)
                grid_survival = np.asarray(
                    model.predict_survival(x_validation, predictions["ibs_grid"]),
                    dtype=float,
                )
                imputation_metric = summarize_imputation_predictions(
                    train_time,
                    train_event,
                    validation_time,
                    validation_event,
                    risk,
                    grid_survival,
                    predictions["ibs_grid"],
                    predictions["horizons"],
                )
                imputation_metrics.append(
                    {
                        "imputation": number,
                        **imputation_metric,
                    }
                )
            preprocessing: dict[str, Any] = {
                "method": "five-fold-local-multiple-imputation prediction ensemble",
                "imputations": preprocessing_records,
            }
            attempts_output: list[dict[str, Any]] = fit_records
            model_details: dict[str, Any] = {
                "combination_rule": (
                    "arithmetic mean of imputation-specific risk and survival "
                    "predictions; pooled metrics are recomputed from those predictions"
                ),
                "per_imputation_metrics": imputation_metrics,
                "per_imputation_diagnostics": [
                    {
                        "imputation": number,
                        "diagnostics": model.diagnostics,
                        "prior_predictive": model.prior_predictive_summary,
                        "posterior_predictive": model.posterior_predictive_summary,
                        "time_scale": model.time_scale,
                    }
                    for number, model in enumerate(models, start=1)
                ],
                "posterior_uncertainty_statement": (
                    "The five posterior fits and prediction ensemble represent "
                    "imputation sensitivity; they do not form one Bayesian posterior "
                    "that propagates covariate-imputation uncertainty."
                ),
                "n_intervals": condition.n_intervals,
                "prior_parameters": fit_config["models"]["bayesian_cox"]["priors"][
                    model_key.removeprefix("bayesian_")
                ]["prior_params"],
            }
        else:
            processor = FoldFeaturePreprocessor(feature_spec)
            x_train = processor.fit_transform(raw.iloc[train_indices])
            x_validation = processor.transform(raw.iloc[validation_indices])
            model, attempts = _fit_with_diagnostic_rule(
                model_key,
                {},
                x_train,
                train_time,
                train_event,
                seed=seed,
                config=fit_config,
                options=confirmatory_options,
            )
            metrics, predictions = evaluate_robustness_predictions(
                model,
                x_validation,
                train_time,
                train_event,
                validation_time,
                validation_event,
                evaluation_config=config["evaluation"],
            )
            preprocessing = processor.metadata()
            attempts_output = attempts
            model_details = {
                "diagnostics": model.diagnostics,
                "prior_predictive": model.prior_predictive_summary,
                "posterior_predictive": model.posterior_predictive_summary,
                "time_scale": model.time_scale,
                "n_intervals": condition.n_intervals,
                "prior_parameters": fit_config["models"]["bayesian_cox"]["priors"][
                    model_key.removeprefix("bayesian_")
                ]["prior_params"],
            }
            transformed_columns = len(x_train.columns)
        losses = individual_integrated_brier_losses(
            train_time,
            train_event,
            validation_time,
            validation_event,
            predictions["survival_on_ibs_grid"],
            predictions["ibs_grid"],
        )
        if not np.isclose(float(np.mean(losses)), float(metrics["ibs"]), atol=1e-12):
            raise RuntimeError("individual IBS contributions do not match reference IBS")
        ipcw_time, ipcw_event = administratively_truncate_for_ipcw(
            validation_time,
            validation_event,
            float(predictions["horizons"][-1]),
        )
        base.update(
            {
                "status": "complete",
                "tuning": "none_prespecified_robustness_configuration",
                "processed_feature_degrees_of_freedom": transformed_columns,
                "effective_information_events_per_degree_of_freedom": (
                    effective_information_ratio(int(train_event.sum()), transformed_columns)
                ),
                "fit_attempts": attempts_output,
                "preprocessing": preprocessing,
                "metrics": metrics,
                "individual_ibs_loss": losses,
                "predictions": {
                    **predictions,
                    "subject_ids": subject_ids[validation_indices],
                    "observed_time": validation_time,
                    "observed_event": validation_event,
                    "ipcw_evaluation_time": ipcw_time,
                    "ipcw_evaluation_event": ipcw_event,
                },
                "model_details": model_details,
            }
        )
    except DiagnosticFailure as exc:
        base.update(
            {
                "status": "failed_diagnostics",
                "fit_attempts": exc.attempts,
                "error_type": type(exc).__name__,
                "message": str(exc),
            }
        )
    except Exception as exc:
        base.update(
            {
                "status": "failed",
                "error_type": type(exc).__name__,
                "message": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
    base["total_seconds"] = time.perf_counter() - started
    base["cell_content_sha256"] = canonical_json_hash(_json_safe(base))
    return base


def validate_robustness_cell(cell: dict[str, Any]) -> None:
    """Validate the common schema and content hash of a stored cell."""
    required = {
        "schema_version",
        "analysis_id",
        "analysis_mode",
        "dataset",
        "dataset_sha256",
        "model_key",
        "prior",
        "repeat",
        "fold",
        "condition",
        "training_subset_sha256",
        "modified_outcomes_sha256",
        "n_train",
        "n_validation",
        "events_train",
        "processed_feature_degrees_of_freedom",
        "effective_information_events_per_degree_of_freedom",
        "status",
        "cell_content_sha256",
    }
    missing = sorted(required - set(cell))
    if missing:
        raise ValueError(f"robustness cell is missing required keys: {missing}")
    if cell["model_key"] not in BAYESIAN_MODEL_KEYS:
        raise ValueError("robustness cell has an unknown Bayesian model key")
    condition = cell["condition"]
    for key in (
        "condition_id",
        "analyses",
        "feature_set",
        "training_fraction",
        "censoring_name",
        "prior_scenario",
        "n_intervals",
        "imputation_method",
    ):
        if key not in condition:
            raise ValueError(f"robustness condition is missing {key!r}")
    unhashed = dict(cell)
    claimed = unhashed.pop("cell_content_sha256")
    if claimed != canonical_json_hash(unhashed):
        raise ValueError("robustness cell content hash does not match")
    if cell["status"] == "complete":
        degrees = int(cell["processed_feature_degrees_of_freedom"])
        observed = float(cell["effective_information_events_per_degree_of_freedom"])
        expected = effective_information_ratio(int(cell["events_train"]), degrees)
        if not np.isclose(observed, expected, atol=1e-12):
            raise ValueError("effective-information ratio does not match events/df")


def _cell_path(
    run_dir: Path,
    dataset: str,
    fold: SurvivalFold,
    condition: RobustnessCondition,
    model_key: str,
) -> Path:
    return (
        run_dir
        / "cells"
        / dataset
        / f"repeat_{fold.repeat:02d}_fold_{fold.fold:02d}"
        / condition.condition_id
        / f"{model_key}.json"
    )


def load_robustness_cells(run_dir: Path) -> list[dict[str, Any]]:
    """Load cells only after validating their declared content hashes."""
    cells: list[dict[str, Any]] = []
    for path in sorted((run_dir / "cells").glob("*/*/*/*.json")):
        cell = json.loads(path.read_text(encoding="utf-8"))
        validate_robustness_cell(cell)
        cells.append(cell)
    return cells


def _cell_analysis_names(cell: dict[str, Any]) -> set[tuple[str, str]]:
    return {
        (str(item["component"]), str(item["condition"])) for item in cell["condition"]["analyses"]
    }


def _bootstrap_contributions(
    fold_contributions: list[np.ndarray],
    fold_events: list[np.ndarray],
    fold_ids: list[dict[str, int]],
    *,
    n_bootstraps: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    if n_bootstraps < 20:
        raise ValueError("sensitivity bootstrap requires at least 20 replicates")
    if (
        len(fold_contributions) == 0
        or len(fold_contributions) != len(fold_events)
        or len(fold_contributions) != len(fold_ids)
    ):
        raise ValueError("paired contributions, events and fold identifiers are required")
    repeat_to_indices: dict[int, list[int]] = {}
    for index, fold_id in enumerate(fold_ids):
        repeat = int(fold_id["repeat"])
        repeat_to_indices.setdefault(repeat, []).append(index)
    repeats = np.asarray(sorted(repeat_to_indices), dtype=int)
    if len(repeats) == 0:
        raise ValueError("at least one outer repeat is required")
    observed = float(np.mean([np.mean(values) for values in fold_contributions]))
    rng = np.random.default_rng(seed)
    samples = np.empty(n_bootstraps, dtype=float)
    for bootstrap in range(n_bootstraps):
        fold_means: list[float] = []
        sampled_repeats = rng.choice(repeats, size=len(repeats), replace=True)
        selected_fold_indices: list[int] = []
        for repeat in sampled_repeats:
            candidates = np.asarray(repeat_to_indices[int(repeat)], dtype=int)
            selected_fold_indices.extend(
                rng.choice(candidates, size=len(candidates), replace=True).tolist()
            )
        for fold_index in selected_fold_indices:
            values = fold_contributions[fold_index]
            events = fold_events[fold_index]
            sampled: list[np.ndarray] = []
            for status in (0, 1):
                indices = np.flatnonzero(events == status)
                if len(indices):
                    sampled.append(rng.choice(indices, size=len(indices), replace=True))
            selected = np.concatenate(sampled)
            fold_means.append(float(np.mean(values[selected])))
        samples[bootstrap] = float(np.mean(fold_means))
    alpha = 1.0 - confidence_level
    lower, upper = np.quantile(samples, [alpha / 2, 1 - alpha / 2])
    return {
        "observed": observed,
        "bootstrap_mean": float(np.mean(samples)),
        "bootstrap_standard_error": float(np.std(samples, ddof=1)),
        "confidence_lower": float(lower),
        "confidence_upper": float(upper),
        "confidence_level": confidence_level,
        "n_bootstraps": n_bootstraps,
        "n_successful": n_bootstraps,
        "resampling_unit": (
            "outer repeats, then folds within repeat, then validation subjects "
            "within fold and event stratum"
        ),
        "n_outer_repeats": len(repeats),
        "n_outer_folds": len(fold_contributions),
    }


def paired_ibs_inference(
    cells: list[dict[str, Any]],
    *,
    components: Iterable[str],
    n_bootstraps: int,
    confidence_level: float,
    seed: int,
) -> dict[str, Any]:
    """Compute paired IBS contrasts and RQ2 difference-in-differences."""
    complete = [cell for cell in cells if cell.get("status") == "complete"]
    datasets = sorted({str(cell["dataset"]) for cell in cells})
    requested = set(components)
    contrasts: list[dict[str, Any]] = []
    contribution_lookup: dict[
        tuple[str, str, str, str, int, int], tuple[np.ndarray, np.ndarray, list[str]]
    ] = {}

    for cell in complete:
        for component, condition in _cell_analysis_names(cell):
            if component not in requested:
                continue
            if (
                component in {"design", "feature"}
                and int(cell["fold"]) not in DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT
            ):
                continue
            key = (
                str(cell["dataset"]),
                component,
                condition,
                str(cell["model_key"]),
                int(cell["repeat"]),
                int(cell["fold"]),
            )
            contribution_lookup[key] = (
                np.asarray(cell["individual_ibs_loss"], dtype=float),
                np.asarray(cell["original_events_validation"], dtype=int),
                [str(value) for value in cell["validation_subject_ids"]],
            )

    condition_names = sorted(
        {
            (dataset, component, condition)
            for dataset, component, condition, _model, _repeat, _fold in contribution_lookup
        }
    )
    for dataset, component, condition in condition_names:
        for model_a, model_b in combinations(BAYESIAN_MODEL_KEYS, 2):
            fold_values: list[np.ndarray] = []
            fold_events: list[np.ndarray] = []
            fold_ids: list[dict[str, int]] = []
            keys_a = sorted(
                key
                for key in contribution_lookup
                if key[:4] == (dataset, component, condition, model_a)
            )
            for key_a in keys_a:
                repeat, fold = key_a[-2:]
                key_b = (dataset, component, condition, model_b, repeat, fold)
                if key_b not in contribution_lookup:
                    continue
                loss_a, events_a, subjects_a = contribution_lookup[key_a]
                loss_b, events_b, subjects_b = contribution_lookup[key_b]
                if subjects_a != subjects_b or not np.array_equal(events_a, events_b):
                    raise ValueError("paired robustness cells do not share validation rows")
                fold_values.append(loss_a - loss_b)
                fold_events.append(events_a)
                fold_ids.append({"repeat": repeat, "fold": fold})
            record: dict[str, Any] = {
                "dataset": dataset,
                "component": component,
                "condition": condition,
                "model_a": model_a,
                "model_b": model_b,
                "direction": "IBS(model_a) minus IBS(model_b)",
                "paired_folds": fold_ids,
            }
            if fold_values:
                record["effect"] = _bootstrap_contributions(
                    fold_values,
                    fold_events,
                    fold_ids,
                    n_bootstraps=n_bootstraps,
                    confidence_level=confidence_level,
                    seed=deterministic_seed(seed, dataset, component, condition, model_a, model_b),
                )
                record["status"] = "complete"
            else:
                record["status"] = "incomplete_no_paired_cells"
            contrasts.append(record)

    full_condition = "fraction_100_observed"
    differences_in_differences: list[dict[str, Any]] = []
    rq2_conditions = sorted(
        {
            condition
            for _dataset, component, condition in condition_names
            if component == "rq2" and condition != full_condition
        }
    )
    for dataset in datasets:
        for condition in rq2_conditions:
            for model_a, model_b in combinations(BAYESIAN_MODEL_KEYS, 2):
                fold_values = []
                fold_events = []
                fold_ids = []
                keys = sorted(
                    key
                    for key in contribution_lookup
                    if key[:4] == (dataset, "rq2", condition, model_a)
                )
                for key_a in keys:
                    repeat, fold = key_a[-2:]
                    keys_needed = (
                        (dataset, "rq2", condition, model_b, repeat, fold),
                        (dataset, "rq2", full_condition, model_a, repeat, fold),
                        (dataset, "rq2", full_condition, model_b, repeat, fold),
                    )
                    if any(key not in contribution_lookup for key in keys_needed):
                        continue
                    condition_a = contribution_lookup[key_a]
                    condition_b = contribution_lookup[keys_needed[0]]
                    full_a = contribution_lookup[keys_needed[1]]
                    full_b = contribution_lookup[keys_needed[2]]
                    subject_lists = [
                        condition_a[2],
                        condition_b[2],
                        full_a[2],
                        full_b[2],
                    ]
                    if any(subjects != subject_lists[0] for subjects in subject_lists[1:]):
                        raise ValueError("RQ2 difference-in-differences is not subject-paired")
                    if not all(
                        np.array_equal(events, condition_a[1])
                        for events in (condition_b[1], full_a[1], full_b[1])
                    ):
                        raise ValueError("RQ2 difference-in-differences strata disagree")
                    did = (condition_a[0] - condition_b[0]) - (full_a[0] - full_b[0])
                    fold_values.append(did)
                    fold_events.append(condition_a[1])
                    fold_ids.append({"repeat": repeat, "fold": fold})
                record = {
                    "dataset": dataset,
                    "condition": condition,
                    "reference_condition": full_condition,
                    "model_a": model_a,
                    "model_b": model_b,
                    "direction": ("[IBS(model_a)-IBS(model_b)] condition minus full observed"),
                    "paired_folds": fold_ids,
                }
                if fold_values:
                    record["effect"] = _bootstrap_contributions(
                        fold_values,
                        fold_events,
                        fold_ids,
                        n_bootstraps=n_bootstraps,
                        confidence_level=confidence_level,
                        seed=deterministic_seed(seed, "did", dataset, condition, model_a, model_b),
                    )
                    record["status"] = "complete"
                else:
                    record["status"] = "incomplete_no_paired_cells"
                differences_in_differences.append(record)
    return {
        "schema_version": "1.0.0",
        "metric": "IPCW integrated Brier score",
        "contrast_direction": "lower IBS is better",
        "uncertainty": (
            "three-stage bootstrap of outer repeats, folds within repeat, and "
            "paired event-stratified validation subjects within fold"
        ),
        "contrasts": contrasts,
        "difference_in_differences": differences_in_differences,
    }


def aggregate_ph_tests(confirmatory_run_dir: Path) -> dict[str, Any]:
    """Purely aggregate stored Cox PH test details with within-fit Holm control."""
    cell_paths = sorted((confirmatory_run_dir / "cells").glob("*/*/cox_ph.json"))
    if not cell_paths:
        raise FileNotFoundError(
            f"no confirmatory Cox cells were found under {confirmatory_run_dir}"
        )
    rows: list[dict[str, Any]] = []
    fit_decisions: list[dict[str, Any]] = []
    source_hashes: dict[str, str] = {}
    for path in cell_paths:
        cell = json.loads(path.read_text(encoding="utf-8"))
        claimed = cell.get("cell_content_sha256")
        unhashed = dict(cell)
        unhashed.pop("cell_content_sha256", None)
        if claimed != canonical_json_hash(unhashed):
            raise ValueError(f"confirmatory cell hash does not match: {path}")
        source_hashes[str(path.relative_to(confirmatory_run_dir))] = sha256_file(path)
        if cell.get("status") != "complete":
            fit_decisions.append(
                {
                    "dataset": cell.get("dataset"),
                    "repeat": cell.get("repeat"),
                    "fold": cell.get("fold"),
                    "status": "unavailable_incomplete_cox_cell",
                }
            )
            continue
        tests = cell.get("model_details", {}).get("ph_test", [])
        if not tests:
            fit_decisions.append(
                {
                    "dataset": cell["dataset"],
                    "repeat": cell["repeat"],
                    "fold": cell["fold"],
                    "status": "unavailable_no_ph_details",
                }
            )
            continue
        adjusted, rejected = holm_adjust([float(row["p"]) for row in tests])
        for test, adjusted_p, reject in zip(tests, adjusted, rejected, strict=True):
            rows.append(
                {
                    "dataset": cell["dataset"],
                    "repeat": cell["repeat"],
                    "fold": cell["fold"],
                    "covariate": test.get("feature", test.get("covariate")),
                    "test_statistic": test.get("test_statistic"),
                    "p_value": float(test["p"]),
                    "holm_adjusted_p": float(adjusted_p),
                    "holm_reject_0_05": bool(reject),
                }
            )
        fit_decisions.append(
            {
                "dataset": cell["dataset"],
                "repeat": cell["repeat"],
                "fold": cell["fold"],
                "status": "complete",
                "global_family_decision": (
                    "departure_detected" if any(rejected) else "no_departure_detected"
                ),
                "n_covariates": len(tests),
                "n_holm_rejections": int(sum(rejected)),
            }
        )

    summary: list[dict[str, Any]] = []
    if rows:
        table = pd.DataFrame(rows)
        for (dataset, covariate), group in table.groupby(
            ["dataset", "covariate"], dropna=False, sort=True
        ):
            summary.append(
                {
                    "dataset": dataset,
                    "covariate": covariate,
                    "n_outer_fits": len(group),
                    "n_holm_rejections": int(group["holm_reject_0_05"].sum()),
                    "proportion_holm_rejections": float(group["holm_reject_0_05"].mean()),
                    "median_raw_p": float(group["p_value"].median()),
                    "minimum_raw_p": float(group["p_value"].min()),
                }
            )
    result = {
        "schema_version": "1.0.0",
        "source_run": confirmatory_run_dir.name,
        "source_cell_sha256": source_hashes,
        "method": (
            "scaled Schoenfeld residual tests with Holm adjustment within each outer Cox fit"
        ),
        "scope_note": (
            "These Cox diagnostics warn about the shared proportional-hazards "
            "structure; they are not residual tests of DeepSurv or Bayesian fits."
        ),
        "frozen_response": (
            "Any supported departure is reported as a limitation. This pure "
            "aggregation neither adds nor tunes time interactions after results."
        ),
        "covariate_tests": rows,
        "fit_level_family_decisions": fit_decisions,
        "covariate_stability_summary": summary,
    }
    result["result_content_sha256"] = canonical_json_hash(result)
    return result


def robustness_input_files(project_root: Path, datasets: tuple[str, ...]) -> list[str]:
    """Return every frozen methodological input used by robustness fitting."""
    files = relevant_input_files(project_root, datasets)
    files.extend(
        [
            "scripts/run_robustness.py",
            "src/pipelines/robustness.py",
            "src/statistics/bootstrap.py",
        ]
    )
    return sorted(set(files))


def _external_result_inputs(project_root: Path, path: Path | None) -> list[str]:
    if path is None:
        return []
    try:
        relative_root = path.resolve().relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError("confirmatory result directory must be inside project_root") from exc
    files = [
        str(candidate.relative_to(project_root))
        for candidate in sorted(path.glob("cells/*/*/*.json"))
        if candidate.name == "cox_ph.json" or candidate.name.startswith("bayesian_")
    ]
    for name in ("manifest.json", "completion.json"):
        candidate = path / name
        if candidate.is_file():
            files.append(str(relative_root / name))
    return sorted(set(files))


def _write_aggregates(
    run_dir: Path,
    cells: list[dict[str, Any]],
    *,
    options: RobustnessOptions,
    config: dict[str, Any],
) -> None:
    inference = paired_ibs_inference(
        cells,
        components=set(options.components) & {"rq2", "design", "feature"},
        n_bootstraps=options.sensitivity_bootstraps,
        confidence_level=float(config["evaluation"]["confidence_level"]),
        seed=deterministic_seed(int(config["validation"]["base_seed"]), "robustness_inference"),
    )
    _atomic_json(run_dir / "paired_ibs_inference.json", inference)
    if "ph" in options.components:
        if options.confirmatory_run_dir is None:
            ph = {
                "schema_version": "1.0.0",
                "status": "unavailable_confirmatory_run_not_supplied",
                "message": (
                    "PH aggregation requires completed confirmatory Cox cell details; "
                    "no PH finding is claimed."
                ),
            }
            ph["result_content_sha256"] = canonical_json_hash(ph)
        else:
            ph = aggregate_ph_tests(options.confirmatory_run_dir)
        _atomic_json(run_dir / "ph_assessment.json", ph)


def execute_robustness_run(
    project_root: Path,
    config: dict[str, Any],
    dataset_config: dict[str, Any],
    options: RobustnessOptions,
) -> Path:
    """Execute or resume all selected frozen robustness components."""
    if options.mode not in {"rehearsal", "robustness"}:
        raise ValueError("mode must be 'rehearsal' or 'robustness'")
    allowed_components = {"rq2", "design", "feature", "ph"}
    if not set(options.components).issubset(allowed_components):
        raise ValueError("components contain an unknown robustness analysis")
    fitted_components = tuple(component for component in options.components if component != "ph")
    plans = {
        dataset: build_condition_plan(config, dataset_config[dataset], fitted_components)
        for dataset in options.datasets
    }
    production_fit_plan = planned_fit_counts(
        plans,
        outer_repeats=int(config["validation"]["outer_repeats"]),
        outer_splits=int(config["validation"]["outer_splits"]),
    )
    if options.mode == "robustness":
        if options.confirmatory_run_dir is None:
            raise RuntimeError(
                "frozen robustness execution requires the completed confirmatory "
                "run for PH aggregation and result-blind runtime projection"
            )
        runtime_projection: dict[str, Any] = projected_runtime_from_confirmatory(
            options.confirmatory_run_dir,
            production_fit_plan,
            maximum_hours=float(config["validation"]["maximum_projected_hours"]),
            target_draws=options.bayes_draws,
            target_tune=options.bayes_tune,
            target_chains=options.bayes_chains,
        )
        if not runtime_projection["feasible"]:
            raise RuntimeError(
                "the frozen lean robustness plan exceeds the result-blind "
                f"{runtime_projection['maximum_projected_hours']:.0f}-hour limit "
                f"({runtime_projection['projected_serial_hours']:.1f} hours)"
            )
    else:
        runtime_projection = {
            "schema_version": "1.0.0",
            "status": "pending_completed_confirmatory_timings",
            "claim_permitted": False,
        }
    feasibility = {
        "schema_version": "1.0.0",
        "fit_plan": production_fit_plan,
        "runtime_projection": runtime_projection,
        "rationale": (
            "RQ2 retains outer folds 1 and 2 per repeat. Design and feature "
            "sensitivities use fold 1 per repeat, and calibration is not "
            "re-estimated in IBS-only robustness cells. The core confirmatory "
            "5x5 analysis is unchanged."
        ),
    }
    feasibility["feasibility_content_sha256"] = canonical_json_hash(feasibility)
    multiple_imputation = {
        "status": "implemented_metabric_npi_plus_stage_sensitivity",
        "number_of_imputations": MULTIPLE_IMPUTATIONS,
        "numeric_method": (
            "training-fold IterativeImputer(sample_posterior=True) with distinct seeds"
        ),
        "categorical_method": "training-fold mode",
        "combination": "average predictions, then recompute metrics",
        "posterior_uncertainty_propagated": False,
        "claim_limit": (
            "This sensitivity does not form one Bayesian posterior that propagates "
            "covariate-imputation uncertainty."
        ),
    }
    actual_config = {
        "protocol": config,
        "mode": options.mode,
        "datasets": options.datasets,
        "components": options.components,
        "outer_splits": options.outer_splits,
        "outer_repeats": options.outer_repeats,
        "fold_limit_per_dataset": options.fold_limit_per_dataset,
        "bayes_draws": options.bayes_draws,
        "bayes_tune": options.bayes_tune,
        "bayes_chains": options.bayes_chains,
        "robustness_calibration": {
            "status": "not_reestimated_in_ibs_only_sensitivities",
            "bootstrap_replicates": 0,
            "source": "full 5x5 confirmatory analysis",
        },
        "sensitivity_bootstraps": options.sensitivity_bootstraps,
        "condition_plan": {
            dataset: [condition.to_dict() for condition in plan] for dataset, plan in plans.items()
        },
        "frozen_production_fit_plan": production_fit_plan,
        "runtime_projection": runtime_projection,
        "multiple_imputation_sensitivity": multiple_imputation,
        "confirmatory_run": (
            options.confirmatory_run_dir.name if options.confirmatory_run_dir is not None else None
        ),
    }
    run_hash = canonical_json_hash(actual_config)[:12]
    run_dir = options.output_root / (
        f"{config['analysis_id']}_robustness_{options.mode}_{run_hash}"
    )
    manifest_path = run_dir / "manifest.json"
    frozen_inputs = robustness_input_files(project_root, options.datasets)
    result_inputs = _external_result_inputs(project_root, options.confirmatory_run_dir)
    manifest = build_run_manifest(
        project_root,
        command=[sys.executable, *sys.argv],
        seeds={"outer_base": int(config["validation"]["base_seed"])},
        input_files=[*frozen_inputs, *result_inputs],
        run_config=actual_config,
    )
    if options.mode == "robustness":
        freeze = verify_protocol_freeze(project_root, frozen_inputs)
        manifest["protocol_freeze_sha256"] = freeze["freeze_content_sha256"]
        manifest["manifest_content_sha256"] = canonical_json_hash(
            {key: value for key, value in manifest.items() if key != "manifest_content_sha256"}
        )
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing["config_sha256"] != manifest["config_sha256"]:
            raise RuntimeError("existing robustness run has a different configuration")
        if existing["input_sha256"] != manifest["input_sha256"]:
            raise RuntimeError(
                "robustness inputs changed after the first checkpoint; start a new run"
            )
        if not options.resume:
            raise FileExistsError(f"run already exists at {run_dir}; pass --resume")
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
        _atomic_json(manifest_path, manifest)
        _atomic_json(run_dir / "analysis_availability.json", multiple_imputation)
        _atomic_json(run_dir / "feasibility_plan.json", feasibility)

    total_planned = 0
    for dataset_key in options.datasets:
        cohort = dataset_config[dataset_key]
        raw, times, events, subject_ids = load_analysis_dataset(project_root, dataset_key, cohort)
        folds = repeated_survival_folds(
            times,
            events,
            n_splits=options.outer_splits,
            n_repeats=options.outer_repeats,
            base_seed=int(config["validation"]["base_seed"]),
            max_time_bins=int(config["validation"]["followup_time_bins"]),
        )
        if options.fold_limit_per_dataset is not None:
            folds = folds[: options.fold_limit_per_dataset]
        data_sha256 = sha256_file(project_root / cohort["raw_file"])
        fractions = [float(value) for value in config["robustness"]["training_fractions"]]
        for fold in folds:
            relative_times = times[fold.train_indices]
            relative_events = events[fold.train_indices]
            subset_seed = deterministic_seed(
                int(config["validation"]["base_seed"]),
                "robustness_subset",
                dataset_key,
                fold.repeat,
                fold.fold,
            )
            for condition in plans[dataset_key]:
                if (
                    condition.selected_fold_numbers is not None
                    and fold.fold not in condition.selected_fold_numbers
                ):
                    continue
                train_indices, cutoff = _fold_condition_indices(
                    condition,
                    fold,
                    relative_times,
                    relative_events,
                    fractions,
                    seed=subset_seed,
                    max_time_bins=int(config["validation"]["followup_time_bins"]),
                )
                feature_spec = _feature_spec(cohort, condition.feature_set)
                for model_key in BAYESIAN_MODEL_KEYS:
                    total_planned += 1
                    path = _cell_path(run_dir, dataset_key, fold, condition, model_key)
                    if path.exists():
                        continue
                    cell = run_robustness_cell(
                        dataset_key,
                        model_key,
                        fold,
                        condition,
                        raw,
                        times,
                        events,
                        subject_ids,
                        feature_spec,
                        train_indices,
                        cutoff,
                        config=config,
                        options=options,
                        data_sha256=data_sha256,
                    )
                    _atomic_json(path, cell)
                    print(
                        f"{dataset_key} repeat={fold.repeat} fold={fold.fold} "
                        f"condition={condition.condition_id} model={model_key} "
                        f"status={cell['status']} seconds={cell['total_seconds']:.1f}",
                        flush=True,
                    )

    cells = load_robustness_cells(run_dir)
    _write_aggregates(run_dir, cells, options=options, config=config)
    counts: dict[str, int] = {}
    for cell in cells:
        counts[cell["status"]] = counts.get(cell["status"], 0) + 1
    aggregate_files = [
        run_dir / "paired_ibs_inference.json",
        run_dir / "analysis_availability.json",
        run_dir / "feasibility_plan.json",
    ]
    if (run_dir / "ph_assessment.json").is_file():
        aggregate_files.append(run_dir / "ph_assessment.json")
    completion = {
        "schema_version": "1.0.0",
        "analysis_mode": options.mode,
        "planned_cells_in_this_invocation": total_planned,
        "stored_cells": len(cells),
        "status_counts": counts,
        "cell_sha256": {
            str(path.relative_to(run_dir)): sha256_file(path)
            for path in sorted((run_dir / "cells").glob("*/*/*/*.json"))
        },
        "aggregate_sha256": {path.name: sha256_file(path) for path in aggregate_files},
    }
    completion["completion_content_sha256"] = canonical_json_hash(completion)
    _atomic_json(run_dir / "completion.json", completion)
    return run_dir
