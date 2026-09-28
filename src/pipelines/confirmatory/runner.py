"""Orchestrate deterministic outer cells, write-once checkpoints and aggregate completion records.

:func:`execute_confirmatory_run` is the package entry point, called by
``scripts/run_confirmatory.py``. It runs the stages in order:

1. A completed confirmatory run requested with ``resume`` is only verified
   (:func:`_verified_closed_run`); nothing is fitted or rewritten.
2. :func:`_prepare_run` names the run directory by the hash of the run
   configuration and writes, or re-checks, the manifest of input hashes.
3. :func:`_execute_cohort_cells` builds each cohort's paired outer folds and
   fits every missing cell, fold by fold and model by model. Each cell file is
   written once, so an interrupted run resumes where it stopped.
4. :func:`_write_completion` re-checks the inputs, aggregates the tables,
   runs the paired inference and records the hash of every cell and output.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from src.data.cohorts import load_analysis_dataset
from src.data.cohorts import select_feature_spec as _feature_spec
from src.data.survival_folds import repeated_survival_folds
from src.utils.io import read_mapping
from src.utils.io import write_json_atomic as _atomic_json
from src.utils.reproducibility import build_run_manifest, canonical_json_hash, sha256_file

from .aggregation import _aggregate_tables, _cell_path, _load_cells
from .cells import run_cell
from .inference import _repeated_cv_inference
from .options import MODEL_KEYS, RunOptions
from .provenance import relevant_input_files, verify_protocol_freeze, verify_run_inputs_unchanged


def execute_confirmatory_run(
    project_root: Path,
    config: dict[str, Any],
    dataset_config: dict[str, Any],
    options: RunOptions,
) -> Path:
    """Execute or resume deterministic model cells and return the run directory.

    A completed confirmatory resume verifies the checkpoint and every stored
    artefact without rewriting them. An unfinished run requires unchanged live
    inputs and the original protocol freeze before any fitting or aggregation.

    Directory layout: ``manifest.json``; ``cells/<cohort>/repeat_RR_fold_FF/
    <model_key>.json``; ``fold_metrics.csv``; ``out_of_fold_predictions.csv.gz``;
    ``inference.json``; ``completion.json``.

    Args:
        project_root: Repository containing code, configuration and cohort CSVs.
        config: Study settings from ``config/confirmatory.yaml``.
        dataset_config: Cohort specifications from ``config/datasets.yaml``.
        options: Requested cohorts, models, folds, sampling and output location.

    Returns:
        The directory containing the manifest, cells, tables and completion record.

    Raises:
        ValueError: Unknown mode, model or cohort.
        RuntimeError: An input, configuration or protocol freeze check fails.
        FileExistsError: The run directory exists and ``resume`` is not set.
    """
    if options.mode not in {"rehearsal", "confirmatory"}:
        raise ValueError("mode must be 'rehearsal' or 'confirmatory'")
    if not set(options.models).issubset(MODEL_KEYS):
        raise ValueError("models contain an unknown model key")

    closed_run = _verified_closed_run(project_root, config, dataset_config, options)
    if closed_run is not None:
        return closed_run

    run_dir, manifest_path, inputs = _prepare_run(project_root, config, options)
    total_planned = 0
    for dataset_key in options.datasets:
        total_planned += _execute_cohort_cells(
            project_root, dataset_key, dataset_config, config, options, run_dir
        )
    _write_completion(project_root, run_dir, manifest_path, inputs, options, config, total_planned)
    return run_dir


def _actual_run_config(config: dict[str, Any], options: RunOptions) -> dict[str, Any]:
    """Construct the unchanged content-addressed execution settings.

    Its hash names the run directory, so any change to the protocol or to a
    run control other than ``resume`` or ``output_root`` starts a new run.
    """
    return {
        "protocol": config,
        "mode": options.mode,
        "datasets": options.datasets,
        "models": options.models,
        "outer_splits": options.outer_splits,
        "outer_repeats": options.outer_repeats,
        "fold_limit_per_dataset": options.fold_limit_per_dataset,
        "bayes_draws": options.bayes_draws,
        "bayes_tune": options.bayes_tune,
        "bayes_chains": options.bayes_chains,
        "calibration_bootstraps": options.calibration_bootstraps,
    }


def _verified_closed_run(
    project_root: Path,
    config: dict[str, Any],
    dataset_config: dict[str, Any],
    options: RunOptions,
) -> Path | None:
    """Verify an already completed frozen run without fitting or rewriting it.

    Returns:
        The run directory when a completed confirmatory run exists for these
        settings and passes every check; ``None`` when there is nothing to
        verify, so the caller continues with a normal run.

    Raises:
        RuntimeError: The completed run exists but does not match the
            requested settings, the dataset settings or the frozen evidence.
    """
    if options.mode != "confirmatory" or not options.resume:
        return None
    actual_config = _actual_run_config(config, options)
    digest = canonical_json_hash(actual_config)
    run_dir = options.output_root / f"{config['analysis_id']}_{options.mode}_{digest[:12]}"
    if not (run_dir / "completion.json").is_file():
        return None
    from src.rendering.verification import verify_frozen_run
    from src.utils.frozen_evidence import verify_frozen_evidence

    # Every stored cell, table and record is checked against its recorded
    # hash first.
    verified = verify_frozen_run(run_dir)
    if verified.manifest["config_sha256"] != digest:
        raise RuntimeError("completed run configuration differs from the requested settings")
    if dataset_config != read_mapping(project_root / "config/datasets.yaml"):
        raise RuntimeError("dataset settings differ from the frozen study inputs")
    # ADR-030: the recorded code inputs are checked against the blobs in the
    # checkpoint commit, not the working tree, so documentation and code can
    # change without making the completed evidence unverifiable. Protocol,
    # raw data and lock files must still match in the live tree.
    freeze = verify_frozen_evidence(project_root, verified.manifest["input_sha256"])
    if verified.manifest["protocol_freeze_sha256"] != freeze["freeze_content_sha256"]:
        raise RuntimeError("completed run refers to a different protocol freeze")
    return run_dir


def _prepare_run(
    project_root: Path,
    config: dict[str, Any],
    options: RunOptions,
) -> tuple[Path, Path, list[str]]:
    """Create or verify a run manifest before the first cell is fitted.

    Returns:
        ``(run_dir, manifest_path, inputs)``, where ``inputs`` are the paths
        whose hashes the manifest records.

    Raises:
        RuntimeError: The protocol freeze fails (confirmatory mode), or an
            existing manifest has a different configuration or inputs.
        FileExistsError: The run exists and ``resume`` is not set.
    """
    actual_config = _actual_run_config(config, options)
    run_hash = canonical_json_hash(actual_config)[:12]
    run_dir = options.output_root / f"{config['analysis_id']}_{options.mode}_{run_hash}"
    manifest_path = run_dir / "manifest.json"

    inputs = relevant_input_files(project_root, options.datasets)
    manifest = build_run_manifest(
        project_root,
        command=[sys.executable, *sys.argv],
        seeds={"outer_base": int(config["validation"]["base_seed"])},
        input_files=inputs,
        run_config=actual_config,
    )
    if options.mode == "confirmatory":
        freeze = verify_protocol_freeze(project_root, inputs)
        manifest["protocol_freeze_sha256"] = freeze["freeze_content_sha256"]
        manifest["manifest_content_sha256"] = canonical_json_hash(
            {key: value for key, value in manifest.items() if key != "manifest_content_sha256"}
        )
    # Resuming continues only on identical configuration and inputs, so one
    # run never mixes cells produced by different code, data or settings.
    if manifest_path.exists():
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        if existing["config_sha256"] != manifest["config_sha256"]:
            raise RuntimeError("existing run directory has a different configuration")
        if existing["input_sha256"] != manifest["input_sha256"]:
            raise RuntimeError(
                "run inputs changed after the first checkpoint; start a new run "
                "instead of combining cells from different code, data or configs"
            )
        if not options.resume:
            raise FileExistsError(
                f"run already exists at {run_dir}; pass --resume to verify/continue it"
            )
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
        _atomic_json(manifest_path, manifest)

    return run_dir, manifest_path, inputs


def _execute_cohort_cells(
    project_root: Path,
    dataset_key: str,
    dataset_config: dict[str, Any],
    config: dict[str, Any],
    options: RunOptions,
    run_dir: Path,
) -> int:
    """Execute missing cohort cells in the frozen fold-first, model-second order.

    Returns:
        The number of cells planned for this cohort, whether fitted now or
        already stored.
    """
    total_planned = 0
    if dataset_key not in dataset_config:
        raise ValueError(f"unknown dataset {dataset_key!r}")
    cohort_config = dataset_config[dataset_key]
    raw, times, events, subject_ids = load_analysis_dataset(
        project_root, dataset_key, cohort_config
    )
    feature_spec = _feature_spec(cohort_config, config["feature_set"])
    # The folds depend only on the outcomes and the base seed, so every model
    # sees the same training and validation subjects (paired folds).
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
    data_path = project_root / cohort_config["raw_file"]
    data_hash = sha256_file(data_path)
    for fold in folds:
        for model_key in options.models:
            total_planned += 1
            cell_path = _cell_path(run_dir, dataset_key, fold, model_key)
            # A stored cell is never refitted or overwritten. Each cell has its
            # own seed, so skipping it does not change any other cell.
            if cell_path.exists():
                continue
            cell = run_cell(
                dataset_key,
                model_key,
                fold,
                raw,
                times,
                events,
                subject_ids,
                feature_spec,
                config=config,
                options=options,
                data_sha256=data_hash,
            )
            _atomic_json(cell_path, cell)
            print(
                f"{dataset_key} repeat={fold.repeat} fold={fold.fold} "
                f"model={model_key} status={cell['status']} "
                f"seconds={cell['total_seconds']:.1f}",
                flush=True,
            )

    return total_planned


def _write_completion(
    project_root: Path,
    run_dir: Path,
    manifest_path: Path,
    inputs: list[str],
    options: RunOptions,
    config: dict[str, Any],
    total_planned: int,
) -> None:
    """Verify inputs around aggregation and record all cell and output hashes.

    Writes ``fold_metrics.csv``, ``out_of_fold_predictions.csv.gz``,
    ``inference.json`` and finally ``completion.json``, which lists the file
    hash of every stored cell and aggregate and its own content hash.
    """

    recorded_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    verify_run_inputs_unchanged(
        project_root,
        recorded_manifest.get("input_sha256", {}),
        inputs,
    )
    if options.mode == "confirmatory":
        verify_protocol_freeze(project_root, inputs)

    cells = _load_cells(run_dir)
    _aggregate_tables(run_dir, cells)
    inference = _repeated_cv_inference(cells, options, config)
    _atomic_json(run_dir / "inference.json", inference)
    counts: dict[str, int] = {}
    for cell in cells:
        counts[cell["status"]] = counts.get(cell["status"], 0) + 1
    completion = {
        "schema_version": "1.0.0",
        "analysis_mode": options.mode,
        "planned_cells_in_this_invocation": total_planned,
        "stored_cells": len(cells),
        "status_counts": counts,
        "all_stored_cell_hashes": {
            str(path.relative_to(run_dir)): sha256_file(path)
            for path in sorted((run_dir / "cells").glob("*/*/*.json"))
        },
        "aggregate_sha256": {
            name: sha256_file(run_dir / name)
            for name in (
                "fold_metrics.csv",
                "out_of_fold_predictions.csv.gz",
                "inference.json",
            )
        },
    }
    # Check again after aggregation so a concurrent edit cannot be hidden by a
    # run that began from valid inputs but ended from different code or data.
    verify_run_inputs_unchanged(
        project_root,
        recorded_manifest.get("input_sha256", {}),
        inputs,
    )
    if options.mode == "confirmatory":
        verify_protocol_freeze(project_root, inputs)
    completion["completion_content_sha256"] = canonical_json_hash(completion)
    _atomic_json(run_dir / "completion.json", completion)
