"""Count the frozen sensitivity fits and project their result-blind runtime.

:mod:`runner` calls both functions before any robustness fit. The fit counts
are stored in the manifest and feasibility plan, and verification of a
completed run recomputes them. In ``robustness`` mode the projected serial
runtime must not exceed the protocol's ``maximum_projected_hours`` (72), or
the run stops before fitting. The projection uses only recorded fit timings from the confirmatory cells;
those source records, including their other fields, are hash-verified.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from src.utils.io import read_mapping
from src.utils.reproducibility import (
    canonical_json_hash,
    sha256_file,
)

from .protocol import (
    BAYESIAN_MODEL_KEYS,
    DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT,
    MULTIPLE_IMPUTATIONS,
    RUNTIME_OVERHEAD_MULTIPLIER,
    RobustnessCondition,
)


def planned_fit_counts(
    plans: dict[str, list[RobustnessCondition]],
    *,
    outer_repeats: int,
    outer_splits: int,
) -> dict[str, Any]:
    """Count checkpoint cells and underlying Bayesian fits before execution.

    Each condition contributes ``outer_repeats`` times its number of selected
    folds cells per prior; the multiple-imputation condition needs five
    Bayesian fits per cell. Refits after a failed diagnostic gate are not
    counted.

    Args:
        plans: Condition plan per cohort, from
            :func:`~.conditions.build_condition_plan`.
        outer_repeats: Outer repeats in the frozen protocol.
        outer_splits: Outer folds per repeat in the frozen protocol.

    Returns:
        Counts per cohort and prior, the totals, and the fold numbers used
        by research question 2 (RQ2) and by the design and feature conditions.

    Raises:
        ValueError: A condition selects a fold number outside
            ``1..outer_splits``.
    """
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
    """Project serial runtime from result-blind confirmatory fit timings.

    For each cohort and prior, the median total fit time of the confirmatory
    Bayesian cells (summed over their fit attempts) is scaled by the ratio of
    Markov chain Monte Carlo (MCMC) work, (draws + tune) x chains, between the
    target and the source run, and multiplied by the planned number of fits.
    The group totals are summed and inflated by
    :data:`~.protocol.RUNTIME_OVERHEAD_MULTIPLIER`. Cells without a positive
    recorded fit time are skipped.

    Args:
        confirmatory_run_dir: Completed confirmatory run with timed cells.
        fit_counts: Output of :func:`planned_fit_counts`.
        maximum_hours: Feasibility limit in hours.
        target_draws: Posterior draws per chain planned for robustness.
        target_tune: Tuning steps per chain planned for robustness.
        target_chains: Chains planned for robustness.

    Returns:
        The per-group projection, the total in hours, whether it is feasible,
        the hashes of every timing source cell and the record's content hash.

    Raises:
        FileNotFoundError: The confirmatory manifest is missing.
        ValueError: A source cell fails its content hash or a work count is
            not positive.
        RuntimeError: A cohort and prior has no usable timing.
    """
    manifest_path = confirmatory_run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"runtime source manifest is missing: {manifest_path}")
    source_config = read_mapping(manifest_path)["run_config"]
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
        # Projection uses fit times only; verify the complete source record first.
        cell = read_mapping(path)
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
