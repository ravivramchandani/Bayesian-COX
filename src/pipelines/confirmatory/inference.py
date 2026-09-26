"""Estimate paired prior and comparator effects from complete repeated-validation cell pairs."""

from __future__ import annotations

from itertools import combinations
from typing import Any

import numpy as np

from src.evaluation.metrics import integrated_brier
from src.statistics.hypothesis_tests import holm_adjust
from src.statistics.repeated_cv import nadeau_bengio_paired_effect

from .evaluation import administratively_truncate_for_ipcw
from .options import MODEL_LABELS, RunOptions, deterministic_seed


def _event_stratified_indices(event: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Resample within event groups, then shuffle using the same generator."""
    groups = []
    for status in (0, 1):
        indices = np.flatnonzero(event == status)
        groups.append(rng.choice(indices, size=len(indices), replace=True))
    sampled = np.concatenate(groups)
    rng.shuffle(sampled)
    return sampled


def _paired_oof_ibs_bootstrap(
    paired_cells: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    n_bootstraps: int,
    seed: int,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    """Event-stratified paired bootstrap over each out-of-fold subject set."""
    if n_bootstraps < 20:
        raise ValueError("paired OOF bootstrap requires at least 20 replicates")
    rng = np.random.default_rng(seed)
    samples: list[float] = []
    for _ in range(n_bootstraps):
        fold_differences: list[float] = []
        for left, right in paired_cells:
            difference = _bootstrap_fold_difference(left, right, rng)
            if difference is None:
                fold_differences = []
                break
            fold_differences.append(difference)
        if fold_differences:
            samples.append(float(np.mean(fold_differences)))

    required = max(20, int(np.ceil(0.8 * n_bootstraps)))
    if len(samples) < required:
        raise RuntimeError(
            f"only {len(samples)} of {n_bootstraps} paired OOF bootstrap "
            f"replicates were estimable; {required} required"
        )
    values = np.asarray(samples, dtype=float)
    alpha = 1.0 - confidence_level
    lower, upper = np.quantile(values, [alpha / 2.0, 1.0 - alpha / 2.0])
    return {
        "estimate": float(
            np.mean(
                [left["metrics"]["ibs"] - right["metrics"]["ibs"] for left, right in paired_cells]
            )
        ),
        "bootstrap_mean": float(np.mean(values)),
        "bootstrap_standard_error": float(np.std(values, ddof=1)),
        "confidence_lower": float(lower),
        "confidence_upper": float(upper),
        "confidence_level": confidence_level,
        "n_bootstraps": n_bootstraps,
        "n_successful": len(values),
        "resampling_unit": "event-stratified validation subjects within paired folds",
    }


def _paired_cells(
    lookup: dict[tuple[str, str, int, int], dict[str, Any]],
    dataset: str,
    model_a: str,
    model_b: str,
    options: RunOptions,
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Pair accepted cells in repeat-first, fold-second order."""
    paired = []
    for repeat in range(1, options.outer_repeats + 1):
        for fold in range(1, options.outer_splits + 1):
            left = lookup.get((dataset, model_a, repeat, fold))
            right = lookup.get((dataset, model_b, repeat, fold))
            if left is not None and right is not None:
                paired.append((left, right))
    return paired


def _contrast_record(
    dataset: str,
    model_a: str,
    model_b: str,
    paired: list[tuple[dict[str, Any], dict[str, Any]]],
    options: RunOptions,
) -> dict[str, Any]:
    """Record the contrast direction and the number of usable paired folds."""
    return {
        "dataset": dataset,
        "model_a": MODEL_LABELS[model_a],
        "model_b": MODEL_LABELS[model_b],
        "contrast_direction": "model_a minus model_b",
        "n_paired_folds": len(paired),
        "expected_paired_folds": options.outer_repeats * options.outer_splits,
    }


def _paired_metric_effect(
    paired: list[tuple[dict[str, Any], dict[str, Any]]],
    metric: str,
    options: RunOptions,
) -> dict[str, Any]:
    """Estimate a paired metric difference with the corrected repeated-CV interval."""
    return nadeau_bengio_paired_effect(
        np.asarray([left["metrics"][metric] for left, _ in paired]),
        np.asarray([right["metrics"][metric] for _, right in paired]),
        n_repeats=options.outer_repeats,
        n_folds=options.outer_splits,
    ).to_dict()


def _calibration_effects(
    paired: list[tuple[dict[str, Any], dict[str, Any]]],
    options: RunOptions,
    *,
    secondary_interpretation: bool = False,
) -> list[dict[str, Any]]:
    """Estimate three calibration-parameter differences at each frozen horizon."""
    effects = []
    for horizon_index in range(3):
        for parameter in ("calibration_in_the_large", "intercept", "slope"):
            left_values = np.asarray(
                [
                    left["metrics"]["calibration"][horizon_index]["summary"][parameter]["estimate"]
                    for left, _ in paired
                ]
            )
            right_values = np.asarray(
                [
                    right["metrics"]["calibration"][horizon_index]["summary"][parameter]["estimate"]
                    for _, right in paired
                ]
            )
            effect = nadeau_bengio_paired_effect(
                left_values,
                right_values,
                n_repeats=options.outer_repeats,
                n_folds=options.outer_splits,
            ).to_dict()
            if secondary_interpretation:
                effect["p_value_interpretation"] = "not_used_secondary"
            effects.append(
                {
                    "horizon_index": horizon_index + 1,
                    "parameter": parameter,
                    "effect": effect,
                }
            )
    return effects


def _primary_contrast(
    dataset: str,
    model_a: str,
    model_b: str,
    paired: list[tuple[dict[str, Any], dict[str, Any]]],
    options: RunOptions,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Estimate one primary prior contrast only when every planned pair exists."""
    record = _contrast_record(dataset, model_a, model_b, paired, options)
    if len(paired) != record["expected_paired_folds"]:
        record["status"] = "incomplete_no_confirmatory_inference"
        return record
    record["ibs"] = _paired_metric_effect(paired, "ibs", options)
    record["calibration_secondary_effects"] = _calibration_effects(paired, options)
    try:
        record["paired_oof_bootstrap"] = _paired_oof_ibs_bootstrap(
            paired,
            n_bootstraps=int(config["inference"]["paired_oof_bootstraps"]),
            seed=deterministic_seed(
                int(config["validation"]["base_seed"]),
                "paired_oof_bootstrap",
                dataset,
                model_a,
                model_b,
            ),
        )
    except (RuntimeError, ValueError) as exc:
        record["paired_oof_bootstrap"] = {
            "status": "not_estimable",
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
    return record


def _secondary_prior_effects(
    dataset: str,
    model_a: str,
    model_b: str,
    paired: list[tuple[dict[str, Any], dict[str, Any]]],
    options: RunOptions,
) -> list[dict[str, Any]]:
    """Estimate the three descriptive discrimination differences for a prior pair."""
    records = []
    for metric in ("uno_c_index", "harrell_c_index", "mean_auc"):
        record = {
            "dataset": dataset,
            "model_a": MODEL_LABELS[model_a],
            "model_b": MODEL_LABELS[model_b],
            "metric": metric,
            "n_paired_folds": len(paired),
        }
        if len(paired) == options.outer_repeats * options.outer_splits:
            record["effect"] = _paired_metric_effect(paired, metric, options)
        else:
            record["status"] = "incomplete"
        records.append(record)
    return records


def _benchmark_contrast(
    dataset: str,
    model_a: str,
    model_b: str,
    paired: list[tuple[dict[str, Any], dict[str, Any]]],
    options: RunOptions,
) -> dict[str, Any]:
    """Estimate one bounded Bayesian-versus-comparator contrast descriptively."""
    record = _contrast_record(dataset, model_a, model_b, paired, options)
    record["inferential_role"] = "secondary_estimation_no_multiplicity_claim"
    if len(paired) != record["expected_paired_folds"]:
        record["status"] = "incomplete_no_secondary_estimate"
        return record
    effects = {}
    for metric in ("ibs", "uno_c_index", "harrell_c_index", "mean_auc"):
        effect = _paired_metric_effect(paired, metric, options)
        effect["p_value_interpretation"] = "not_used_secondary"
        effects[metric] = effect
    record["metric_effects"] = effects
    record["calibration_effects"] = _calibration_effects(
        paired, options, secondary_interpretation=True
    )
    record["runtime_seconds"] = {
        "model_a_mean": float(np.mean([left["total_seconds"] for left, _ in paired])),
        "model_b_mean": float(np.mean([right["total_seconds"] for _, right in paired])),
    }
    return record


def _apply_primary_holm(primary: list[dict[str, Any]]) -> bool:
    """Apply Holm and the superiority gate only to the complete nine-test family."""
    complete_primary = [row for row in primary if "ibs" in row]
    family_complete = len(complete_primary) == 9
    if family_complete:
        adjusted, rejected = holm_adjust([row["ibs"]["p_value"] for row in complete_primary])
        for row, adjusted_p, reject in zip(complete_primary, adjusted, rejected, strict=True):
            row["holm_adjusted_p"] = adjusted_p
            row["holm_reject_0_05"] = reject
            interval = row["ibs"]
            row["superiority_language_permitted"] = bool(
                reject and (interval["confidence_upper"] < 0 or interval["confidence_lower"] > 0)
            )
    return family_complete


def _repeated_cv_inference(
    cells: list[dict[str, Any]], options: RunOptions, config: dict[str, Any]
) -> dict[str, Any]:
    """Build the prespecified primary and bounded secondary paired-effect records."""
    complete = [cell for cell in cells if cell.get("status") == "complete"]
    lookup = {
        (cell["dataset"], cell["model_key"], cell["repeat"], cell["fold"]): cell
        for cell in complete
    }
    bayesian = ("bayesian_normal", "bayesian_horseshoe", "bayesian_spike_slab")
    primary = []
    secondary = []
    secondary_benchmarks = []
    for dataset in options.datasets:
        for model_a, model_b in combinations(bayesian, 2):
            paired = _paired_cells(lookup, dataset, model_a, model_b, options)
            primary.append(_primary_contrast(dataset, model_a, model_b, paired, options, config))
            secondary.extend(_secondary_prior_effects(dataset, model_a, model_b, paired, options))
        for model_a in bayesian:
            for model_b in ("cox_ph", "random_survival_forest", "deepsurv"):
                paired = _paired_cells(lookup, dataset, model_a, model_b, options)
                secondary_benchmarks.append(
                    _benchmark_contrast(dataset, model_a, model_b, paired, options)
                )
    family_complete = _apply_primary_holm(primary)
    return {
        "status": "complete" if family_complete else "incomplete",
        "primary_family": "nine within-cohort Bayesian-prior IBS contrasts",
        "holm_family_complete": family_complete,
        "primary": primary,
        "secondary_estimation": secondary,
        "secondary_benchmark_estimation": secondary_benchmarks,
    }


def _bootstrap_fold_difference(
    left: dict[str, Any],
    right: dict[str, Any],
    rng: np.random.Generator,
) -> float | None:
    """Resample aligned validation subjects and recompute one paired IBS difference."""
    left_predictions = left["predictions"]
    right_predictions = right["predictions"]
    if left_predictions["subject_ids"] != right_predictions["subject_ids"]:
        raise ValueError("paired cells do not contain identical subject order")
    observed_time = np.asarray(left_predictions["observed_time"], dtype=float)
    observed_event = np.asarray(left_predictions["observed_event"], dtype=int)
    if not np.array_equal(
        observed_time,
        np.asarray(right_predictions["observed_time"], dtype=float),
    ) or not np.array_equal(
        observed_event,
        np.asarray(right_predictions["observed_event"], dtype=int),
    ):
        raise ValueError("paired cells do not contain identical outcomes")
    indices = _event_stratified_indices(observed_event, rng)
    training_time = np.asarray(left_predictions["training_time"], dtype=float)
    training_event = np.asarray(left_predictions["training_event"], dtype=int)
    grid = np.asarray(left_predictions["ibs_grid"], dtype=float)
    if not np.array_equal(grid, np.asarray(right_predictions["ibs_grid"], dtype=float)):
        raise ValueError("paired cells do not use an identical IBS grid")
    survival_left = np.asarray(left_predictions["survival_on_ibs_grid"], dtype=float)[indices]
    survival_right = np.asarray(right_predictions["survival_on_ibs_grid"], dtype=float)[indices]
    bootstrap_time, bootstrap_event = administratively_truncate_for_ipcw(
        observed_time[indices], observed_event[indices], float(grid[-1])
    )
    try:
        ibs_left = integrated_brier(
            training_time,
            training_event,
            bootstrap_time,
            bootstrap_event,
            survival_left,
            grid,
        )
        ibs_right = integrated_brier(
            training_time,
            training_event,
            bootstrap_time,
            bootstrap_event,
            survival_right,
            grid,
        )
    except (RuntimeError, ValueError):
        return None
    return ibs_left - ibs_right
