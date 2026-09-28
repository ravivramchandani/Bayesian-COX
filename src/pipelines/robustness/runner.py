"""Orchestrate checkpointed robustness fitting and pure aggregate generation.

:func:`execute_robustness_run` is the package entry point, called by
``scripts/run_robustness.py``. It runs the stages in order:

1. :func:`_prepare_run_configuration` builds each cohort's condition plan,
   counts the planned fits and, in ``robustness`` mode, checks the
   result-blind runtime projection against the protocol limit.
2. :func:`~.provenance.initialise_run_directory` writes or re-checks the
   manifest; a completed run is only verified and returned.
3. :func:`_fit_dataset` fits every missing cell, fold by fold, condition by
   condition and prior by prior. Each cell file is written once, so an
   interrupted run resumes where it stopped.
4. :func:`_complete_run` loads the validated cells, writes the paired integrated Brier score (IBS)
   inference and the proportional-hazards (PH) assessment, and records every cell and aggregate
   hash in ``completion.json``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.data.survival_folds import (
    repeated_survival_folds,
)
from src.pipelines.confirmatory import (
    _feature_spec,
    deterministic_seed,
    load_analysis_dataset,
)
from src.utils.io import write_json_atomic as _atomic_json
from src.utils.reproducibility import (
    canonical_json_hash,
    sha256_file,
)

from .cells import _cell_path, load_robustness_cells, run_robustness_cell
from .conditions import (
    _fold_condition_indices,
    build_condition_plan,
)
from .inference import (
    aggregate_ph_tests,
    paired_ibs_inference,
)
from .planning import planned_fit_counts, projected_runtime_from_confirmatory
from .protocol import (
    BAYESIAN_MODEL_KEYS,
    MULTIPLE_IMPUTATIONS,
    RobustnessOptions,
)
from .provenance import initialise_run_directory


def _write_aggregates(
    run_dir: Path,
    cells: list[dict[str, Any]],
    *,
    options: RobustnessOptions,
    config: dict[str, Any],
) -> None:
    """Write ``paired_ibs_inference.json`` and, with the ``ph`` component, ``ph_assessment.json``.

    Without a confirmatory source run the PH record states that no PH
    finding is claimed.
    """
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


def _prepare_run_configuration(
    config: dict[str, Any], dataset_config: dict[str, Any], options: RobustnessOptions
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build the frozen condition grid, feasibility statement and actual run configuration.

    The fit plan is always counted at the frozen protocol's repeats and
    folds, whatever reduced controls a rehearsal uses.

    Returns:
        ``(plans, actual_config, multiple_imputation, feasibility)``: the
        condition plan per cohort, the configuration whose hash identifies the
        run, the multiple-imputation statement and the feasibility record.

    Raises:
        ValueError: Unknown mode or component.
        RuntimeError: ``robustness`` mode without a confirmatory run, or a
            projected runtime above the limit.
    """
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
    return plans, actual_config, multiple_imputation, feasibility


def _fit_dataset(
    project_root: Path,
    dataset_key: str,
    cohort: dict[str, Any],
    conditions: list[Any],
    config: dict[str, Any],
    options: RobustnessOptions,
    run_dir: Path,
) -> int:
    """Fit missing cells for one dataset in frozen fold, condition and prior order.

    Returns:
        The number of cells planned for this cohort, whether fitted now or
        already stored.
    """
    total_planned = 0
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
        # The subset seed depends on cohort, repeat and fold only, so every
        # condition and prior on this fold draws the same nested subsets.
        subset_seed = deterministic_seed(
            int(config["validation"]["base_seed"]),
            "robustness_subset",
            dataset_key,
            fold.repeat,
            fold.fold,
        )
        for condition in conditions:
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
                # A stored cell is never refitted or overwritten; each cell has
                # its own seed, so skipping it changes no other cell.
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

    return total_planned


def _complete_run(
    run_dir: Path, total_planned: int, config: dict[str, Any], options: RobustnessOptions
) -> Path:
    """Aggregate validated cells and record all stored outcomes and file hashes.

    Returns:
        The run directory.
    """
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


def execute_robustness_run(
    project_root: Path,
    config: dict[str, Any],
    dataset_config: dict[str, Any],
    options: RobustnessOptions,
) -> Path:
    """Execute selected robustness components without mixing different execution code.

    Directory layout: ``manifest.json``, ``analysis_availability.json``,
    ``feasibility_plan.json``, ``cells/<cohort>/repeat_RR_fold_FF/
    <condition_id>/<model_key>.json``, ``paired_ibs_inference.json``,
    ``ph_assessment.json`` (with the ``ph`` component) and ``completion.json``.

    Args:
        project_root: Checkout holding the live frozen study inputs.
        config: Frozen confirmatory and robustness protocol.
        dataset_config: Source and feature definitions for each cohort.
        options: Execution controls and immutable confirmatory source run.

    Returns:
        The new run directory, or a verified completed checkpoint directory.

    Raises:
        ValueError: The mode or a requested component is unknown, or a stored
            cell is invalid.
        RuntimeError: Production controls, frozen inputs, runtime feasibility
            or resumed evidence fail verification.
        FileExistsError: A run exists and ``resume`` is not set.
    """
    plans, actual_config, availability, feasibility = _prepare_run_configuration(
        config, dataset_config, options
    )
    run_dir, already_complete = initialise_run_directory(
        project_root, actual_config, options, availability, feasibility
    )
    if already_complete:
        return run_dir
    total_planned = 0
    for dataset_key in options.datasets:
        total_planned += _fit_dataset(
            project_root,
            dataset_key,
            dataset_config[dataset_key],
            plans[dataset_key],
            config,
            options,
            run_dir,
        )
    return _complete_run(run_dir, total_planned, config, options)
