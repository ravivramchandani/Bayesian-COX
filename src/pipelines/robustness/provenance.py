"""Record current execution inputs and verify robustness evidence without refitting."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from src.pipelines.confirmatory import (
    relevant_input_files,
)
from src.utils.frozen_evidence import CHECKPOINT_COMMIT, verify_frozen_evidence
from src.utils.io import json_safe, read_mapping, write_json_atomic
from src.utils.reproducibility import build_run_manifest, canonical_json_hash, sha256_file

from .cells import validate_robustness_cell
from .conditions import build_condition_plan
from .planning import planned_fit_counts
from .protocol import BAYESIAN_MODEL_KEYS, RobustnessOptions


def robustness_input_files(project_root: Path, datasets: tuple[str, ...]) -> list[str]:
    """Record the current source files together with required study inputs.

    Retired code remains verifiable at the historical checkpoint. New runs
    instead record every current source and script file, including package
    initialisers and newly extracted modules.
    """
    files = [
        relative
        for relative in relevant_input_files(project_root, datasets)
        if not relative.startswith(("src/", "scripts/"))
    ]
    for pattern in ("src/**/*.py", "scripts/**/*.py"):
        files.extend(
            str(path.relative_to(project_root))
            for path in project_root.glob(pattern)
            if path.is_file()
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


def _verify_content_hash(record: dict[str, Any], field: str, path: Path) -> None:
    """Reject a metadata record whose content hash differs from its declared hash."""
    unhashed = dict(record)
    claimed = unhashed.pop(field, None)
    if claimed != canonical_json_hash(unhashed):
        raise RuntimeError(f"robustness {field} does not match: {path}")


def _source_input_path(
    project_root: Path,
    relative: str,
    source_name: str | None,
    confirmatory_run_dir: Path | None,
) -> Path:
    """Resolve a recorded source-result input without changing its recorded key."""
    prefix = f"reports/confirmatory/{source_name}/"
    if confirmatory_run_dir is not None and relative.startswith(prefix):
        return confirmatory_run_dir / relative.removeprefix(prefix)
    return project_root / relative


def _verify_manifest_inputs(
    project_root: Path, manifest: dict[str, Any], confirmatory_run_dir: Path | None
) -> None:
    """Verify historical code at its checkpoint and every used source-result file."""
    inputs = manifest.get("input_sha256")
    if not isinstance(inputs, dict) or not inputs:
        raise RuntimeError("robustness manifest has no recorded inputs")
    source_name = manifest["run_config"].get("confirmatory_run")
    historical = False
    if manifest["run_config"].get("mode") == "robustness":
        freeze = verify_frozen_evidence(project_root)
        study_inputs = {
            key: value for key, value in inputs.items() if not key.startswith("reports/")
        }
        historical = study_inputs == freeze["frozen_input_sha256"]
        if manifest.get("protocol_freeze_sha256") != freeze["freeze_content_sha256"]:
            raise RuntimeError("robustness manifest identifies a different protocol freeze")
    for relative, digest in sorted(inputs.items()):
        if historical and not relative.startswith("reports/"):
            continue
        path = _source_input_path(project_root, relative, source_name, confirmatory_run_dir)
        if not path.is_file() or sha256_file(path) != digest:
            raise RuntimeError(f"robustness recorded input differs: {relative}")


def verify_completed_robustness_run(
    run_dir: Path, project_root: Path, *, confirmatory_run_dir: Path | None = None
) -> dict[str, Any]:
    """Verify completed robustness evidence without fitting or rewriting anything.

    Historical code is checked against the pinned Git checkpoint, while live
    protocol, raw data and lock files must retain their frozen content. A
    production run must match all 825 frozen cells and the feasibility plan.

    Args:
        run_dir: Completed run containing its original manifest and completion.
        project_root: Checkout with historical Git objects and live study inputs.
        confirmatory_run_dir: Source run when it is outside this checkout.

    Returns:
        The verified original completion record.
    """
    manifest_path = run_dir / "manifest.json"
    manifest = read_mapping(manifest_path)
    _verify_content_hash(manifest, "manifest_content_sha256", manifest_path)
    if manifest.get("config_sha256") != canonical_json_hash(manifest["run_config"]):
        raise RuntimeError("robustness configuration hash does not match")
    _verify_manifest_inputs(project_root, manifest, confirmatory_run_dir)
    completion_path = run_dir / "completion.json"
    completion = read_mapping(completion_path)
    _verify_content_hash(completion, "completion_content_sha256", completion_path)
    paths = sorted((run_dir / "cells").glob("*/*/*/*.json"))
    recorded = completion.get("cell_sha256", {})
    if set(recorded) != {str(path.relative_to(run_dir)) for path in paths}:
        raise RuntimeError("robustness cells differ from the completion inventory")
    if len(paths) != completion.get("stored_cells") or len(paths) != completion.get(
        "planned_cells_in_this_invocation"
    ):
        raise RuntimeError("robustness completion does not contain every planned cell")
    run_config = manifest["run_config"]
    if set(recorded) != _planned_cell_paths(run_config):
        raise RuntimeError("robustness completion does not match the declared condition grid")
    datasets = read_mapping(project_root / "config/datasets.yaml")
    status_counts: dict[str, int] = {}
    for path in paths:
        if sha256_file(path) != recorded[str(path.relative_to(run_dir))]:
            raise RuntimeError(f"robustness stored cell file hash differs: {path}")
        cell = read_mapping(path)
        validate_robustness_cell(cell)
        if cell["analysis_mode"] != run_config["mode"]:
            raise RuntimeError("robustness cell analysis mode differs from the manifest")
        _verify_cell_identity(cell, path, run_dir, manifest, datasets)
        status_counts[cell["status"]] = status_counts.get(cell["status"], 0) + 1
    if completion.get("status_counts") != status_counts:
        raise RuntimeError("robustness completion status counts differ from the cells")
    _verify_aggregates(run_dir, completion, run_config)
    _verify_frozen_plan(project_root, run_dir, run_config)
    return completion


def _verify_cell_identity(
    cell: dict[str, Any],
    path: Path,
    run_dir: Path,
    manifest: dict[str, Any],
    datasets: dict[str, Any],
) -> None:
    """Bind each cell body to its planned path, condition and frozen raw input."""
    if type(cell["repeat"]) is not int or type(cell["fold"]) is not int:
        raise RuntimeError("robustness cell repeat and fold must be integers")
    condition = cell["condition"]
    expected_path = (
        Path("cells")
        / cell["dataset"]
        / f"repeat_{cell['repeat']:02d}_fold_{cell['fold']:02d}"
        / condition["condition_id"]
        / f"{cell['model_key']}.json"
    )
    if expected_path != path.relative_to(run_dir):
        raise RuntimeError("robustness cell identity differs from its planned path")
    declared = {
        item["condition_id"]: item
        for item in manifest["run_config"]["condition_plan"][cell["dataset"]]
    }
    if condition != declared.get(condition["condition_id"]):
        raise RuntimeError("robustness cell condition differs from the declared frozen plan")
    raw_file = datasets[cell["dataset"]]["raw_file"]
    if cell["dataset_sha256"] != manifest["input_sha256"].get(raw_file):
        raise RuntimeError("robustness cell raw-data hash differs from the frozen input")
    if cell["status"] not in {"complete", "failed", "failed_diagnostics"}:
        raise RuntimeError("robustness cell has an unrecognised completed-run status")


def _planned_cell_paths(run_config: dict[str, Any]) -> set[str]:
    """Reconstruct the exact recorded grid without fitting any model."""
    expected: set[str] = set()
    for dataset in run_config["datasets"]:
        outer_folds = [
            (repeat, fold)
            for repeat in range(1, int(run_config["outer_repeats"]) + 1)
            for fold in range(1, int(run_config["outer_splits"]) + 1)
        ]
        limit = run_config.get("fold_limit_per_dataset")
        if limit is not None:
            outer_folds = outer_folds[: int(limit)]
        for repeat, fold in outer_folds:
            for condition in run_config["condition_plan"][dataset]:
                selected = condition.get("selected_fold_numbers")
                if selected is not None and fold not in selected:
                    continue
                for model in BAYESIAN_MODEL_KEYS:
                    expected.add(
                        f"cells/{dataset}/repeat_{repeat:02d}_fold_{fold:02d}/"
                        f"{condition['condition_id']}/{model}.json"
                    )
    return expected


def _verify_aggregates(
    run_dir: Path, completion: dict[str, Any], run_config: dict[str, Any]
) -> None:
    """Verify the complete set of generated aggregate files and their byte hashes."""
    expected = {"paired_ibs_inference.json", "analysis_availability.json", "feasibility_plan.json"}
    if "ph" in run_config.get("components", []):
        expected.add("ph_assessment.json")
    recorded = completion.get("aggregate_sha256", {})
    if set(recorded) != expected:
        raise RuntimeError("robustness completion has an incomplete aggregate inventory")
    for name, digest in recorded.items():
        path = run_dir / name
        if not path.is_file() or sha256_file(path) != digest:
            raise RuntimeError(f"robustness aggregate file hash differs: {name}")


def _verify_frozen_plan(project_root: Path, run_dir: Path, run_config: dict[str, Any]) -> None:
    """Require production evidence to match the frozen protocol and full feasibility grid."""
    if run_config["mode"] != "robustness":
        return
    config = read_mapping(project_root / "config/confirmatory.yaml")
    dataset_config = read_mapping(project_root / "config/datasets.yaml")
    if canonical_json_hash(run_config.get("protocol")) != canonical_json_hash(config):
        raise RuntimeError("robustness manifest protocol differs from the frozen study")
    _verify_execution_controls(run_config, config)
    plans = {
        dataset: build_condition_plan(config, dataset_config[dataset], ("rq2", "design", "feature"))
        for dataset in config["datasets"]
    }
    declared = json_safe(
        {key: [condition.to_dict() for condition in plan] for key, plan in plans.items()}
    )
    if run_config.get("condition_plan") != declared:
        raise RuntimeError("robustness condition grid differs from the frozen study")
    fit_plan = planned_fit_counts(
        plans,
        outer_repeats=int(config["validation"]["outer_repeats"]),
        outer_splits=int(config["validation"]["outer_splits"]),
    )
    if fit_plan["total_checkpoint_cells"] != 825:
        raise RuntimeError("frozen robustness grid must contain exactly 825 cells")
    if run_config.get("frozen_production_fit_plan") != fit_plan:
        raise RuntimeError("robustness fit plan differs from the frozen study")
    feasibility_path = run_dir / "feasibility_plan.json"
    feasibility = read_mapping(feasibility_path)
    _verify_content_hash(feasibility, "feasibility_content_sha256", feasibility_path)
    if feasibility.get("fit_plan") != fit_plan or feasibility.get(
        "runtime_projection"
    ) != run_config.get("runtime_projection"):
        raise RuntimeError("robustness feasibility plan differs from the manifest")


def _verify_execution_controls(run_config: dict[str, Any], config: dict[str, Any]) -> None:
    """Reject production overrides of the frozen datasets, folds, sampler and components."""
    validation = config["validation"]
    bayesian = config["models"]["bayesian_cox"]
    expected = {
        "datasets": config["datasets"],
        "components": ["rq2", "design", "feature", "ph"],
        "outer_splits": validation["outer_splits"],
        "outer_repeats": validation["outer_repeats"],
        "fold_limit_per_dataset": None,
        "bayes_draws": bayesian["draws"],
        "bayes_tune": bayesian["tune"],
        "bayes_chains": bayesian["chains"],
        "sensitivity_bootstraps": 2000,
    }
    for key, value in expected.items():
        if run_config.get(key) != value:
            raise RuntimeError(f"robustness production control differs from frozen study: {key}")


def build_execution_manifest(
    project_root: Path, actual_config: dict[str, Any], options: RobustnessOptions
) -> dict[str, Any]:
    """Capture current code separately from the unchanged methodological freeze."""
    inputs = robustness_input_files(project_root, options.datasets)
    source_inputs = _external_result_inputs(project_root, options.confirmatory_run_dir)
    manifest = build_run_manifest(
        project_root,
        command=[sys.executable, *sys.argv],
        seeds={"outer_base": int(actual_config["protocol"]["validation"]["base_seed"])},
        input_files=[*inputs, *source_inputs],
        run_config=actual_config,
    )
    if any(value == "MISSING" for value in manifest["input_sha256"].values()):
        raise RuntimeError("robustness execution has missing required inputs")
    if options.mode == "robustness":
        _verify_execution_controls(json_safe(actual_config), actual_config["protocol"])
        freeze = verify_frozen_evidence(project_root)
        manifest["protocol_freeze_sha256"] = freeze["freeze_content_sha256"]
        manifest["methodological_checkpoint"] = CHECKPOINT_COMMIT
    code_inputs = {
        key: value
        for key, value in manifest["input_sha256"].items()
        if key.startswith(("src/", "scripts/"))
    }
    manifest["execution_code_sha256"] = canonical_json_hash(code_inputs)
    manifest["manifest_content_sha256"] = canonical_json_hash(
        {key: value for key, value in manifest.items() if key != "manifest_content_sha256"}
    )
    return manifest


def initialise_run_directory(
    project_root: Path,
    actual_config: dict[str, Any],
    options: RobustnessOptions,
    availability: dict[str, Any],
    feasibility: dict[str, Any],
) -> tuple[Path, bool]:
    """Choose a code-specific run directory and refuse mixed-code unfinished resumes."""
    manifest = build_execution_manifest(project_root, actual_config, options)
    analysis_id = actual_config["protocol"]["analysis_id"]
    prefix = f"{analysis_id}_robustness_{options.mode}_"
    legacy_dir = options.output_root / f"{prefix}{manifest['config_sha256'][:12]}"
    if options.resume and (legacy_dir / "manifest.json").is_file():
        if not (legacy_dir / "completion.json").is_file():
            raise RuntimeError(
                "unfinished checkpoint robustness run requires its unchanged original "
                "code and runtime; use a new output root for current code"
            )
        existing = read_mapping(legacy_dir / "manifest.json")
        if existing.get("config_sha256") != manifest["config_sha256"]:
            raise RuntimeError("existing robustness run has a different configuration")
        verify_completed_robustness_run(
            legacy_dir, project_root, confirmatory_run_dir=options.confirmatory_run_dir
        )
        return legacy_dir, True
    run_hash = canonical_json_hash(
        {
            "config_sha256": manifest["config_sha256"],
            "execution_code_sha256": manifest["execution_code_sha256"],
        }
    )[:12]
    run_dir = options.output_root / f"{prefix}{run_hash}"
    manifest_path = run_dir / "manifest.json"
    if manifest_path.exists():
        _validate_resume_manifest(read_mapping(manifest_path), manifest, options, run_dir)
        if (run_dir / "completion.json").is_file():
            verify_completed_robustness_run(
                run_dir, project_root, confirmatory_run_dir=options.confirmatory_run_dir
            )
            return run_dir, True
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
        write_json_atomic(manifest_path, manifest)
        write_json_atomic(run_dir / "analysis_availability.json", availability)
        write_json_atomic(run_dir / "feasibility_plan.json", feasibility)
    return run_dir, False


def _validate_resume_manifest(
    existing: dict[str, Any], current: dict[str, Any], options: RobustnessOptions, run_dir: Path
) -> None:
    """Require identical configuration, execution inputs and runtime before any new fit."""
    _verify_content_hash(existing, "manifest_content_sha256", run_dir / "manifest.json")
    if existing["config_sha256"] != current["config_sha256"]:
        raise RuntimeError("existing robustness run has a different configuration")
    if existing["input_sha256"] != current["input_sha256"]:
        raise RuntimeError("robustness inputs changed after the first checkpoint; start a new run")
    if existing.get("environment") != current.get("environment"):
        raise RuntimeError("robustness runtime changed after the first checkpoint; start a new run")
    if not options.resume:
        raise FileExistsError(f"run already exists at {run_dir}; pass --resume")
