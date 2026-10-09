#!/usr/bin/env python3
"""Run the separately frozen RSF surrogate study after its review gate passes."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CHECKPOINT_COMMIT = "44b608572a5e1006a05ed5e3c4985471b2ba594d"
DEFAULT_SOURCE_RUN = PROJECT_ROOT / "reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651"
DEFAULT_REVIEW = PROJECT_ROOT / "coordination/reviews/rsf-surrogate-protocol-review.json"
DEFAULT_ENVIRONMENT_PLATFORM = "win-64" if sys.platform == "win32" else "osx-arm64"
DEFAULT_ENVIRONMENT_LOCK = PROJECT_ROOT / (
    "conda-lock-win-64.yml" if DEFAULT_ENVIRONMENT_PLATFORM == "win-64" else "conda-lock.yml"
)
PROTOCOL_SHA256 = "291ad6843e96297717883e3d784503836e150b0e58e9a9314af14d4fef0c1bcf"
EXPECTED_COHORTS = ("gbsg2", "whas500", "metabric")
SOURCE_MANIFEST_FILE_SHA256 = "2a1817365675aa179174b5edf5b3da67bbcb2be1b2eb4143347e4b295052ce02"
SOURCE_COMPLETION_FILE_SHA256 = "44d5d6e2c3cf4d0350c3bc8cb27291436c9934b219c4c895cb139525e6fa25f6"
MAX_PROJECTED_SECONDS = 60 * 60


def _sha256(path: Path) -> str:
    """Hash a file's exact bytes with SHA-256."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(path: Path) -> str:
    """Hash UTF-8 text using canonical LF newlines across operating systems."""
    return hashlib.sha256(path.read_text(encoding="utf-8").encode("utf-8")).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    """Load a JSON mapping and reject non-mapping records."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def _current_frozen_run_verifier() -> Any:
    """Load the portable value-integrity verifier without importing checkpoint model code."""
    source = PROJECT_ROOT / "src/rendering/verification.py"
    spec = importlib.util.spec_from_file_location("_portable_frozen_run_verification", source)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the portable frozen-run verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_portable_frozen_run_verification"] = module
    spec.loader.exec_module(module)
    return module.verify_frozen_run


def _current_frozen_evidence_verifier() -> Any:
    """Load the portable frozen-input verifier while retaining checkpoint imports."""
    source = PROJECT_ROOT / "src/utils/frozen_evidence.py"
    name = "_portable_frozen_evidence_verification"
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the portable frozen-input verifier")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module.verify_frozen_evidence


def _current_cohort_loader() -> Any:
    """Load the active raw-cohort reader without shadowing checkpoint modules."""
    source = PROJECT_ROOT / "src/data/cohorts.py"
    name = "_current_rsf_surrogate_cohorts"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the active cohort reader")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _current_io_helpers() -> Any:
    """Load the active result serializer without changing checkpoint imports."""
    source = PROJECT_ROOT / "src/utils/io.py"
    name = "_current_rsf_surrogate_io"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the active result serializer")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _load_current_pipeline(checkpoint_root: Path) -> Any:
    """Load this study's code while absolute project imports resolve to checkpoint code."""
    source = PROJECT_ROOT / "src/pipelines/rsf_surrogate.py"
    name = "_current_rsf_surrogate_pipeline"
    spec = importlib.util.spec_from_file_location(name, source)
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load the RSF surrogate implementation")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    if Path(sys.path[0]).resolve() != checkpoint_root.resolve():
        raise RuntimeError("checkpoint source package is not first on the worker import path")
    return module


def _verify_protocol(protocol_sha256: str = PROTOCOL_SHA256) -> None:
    """Check the write-once protocol receipt without reading study results."""
    freeze_path = PROJECT_ROOT / "coordination/rsf_surrogate_protocol_freeze.json"
    addendum_path = PROJECT_ROOT / "docs/protocol_addendum_rsf_surrogate.md"
    freeze = _read_json(freeze_path)
    if _sha256(addendum_path) != PROTOCOL_SHA256:
        raise RuntimeError("the frozen RSF surrogate protocol has changed")
    if freeze.get("protocol_sha256") != PROTOCOL_SHA256:
        raise RuntimeError("the protocol freeze receipt does not match the frozen protocol")
    if freeze.get("production_gate") != "hold_until_independent_review_acceptance":
        raise RuntimeError("the frozen protocol production gate has been altered")


def _verify_protocol_and_review(
    review_path: Path,
    reviewer_validator: Any | None = None,
    waiver_validator: Any | None = None,
) -> tuple[dict[str, Any], str]:
    """Validate either independent acceptance or a transparently recorded owner waiver."""
    _verify_protocol()
    receipt = _read_json(review_path)
    if receipt.get("receipt_type") == "owner_gate_waiver":
        if waiver_validator is None:
            from src.pipelines.rsf_surrogate import validate_owner_waiver_receipt

            waiver_validator = validate_owner_waiver_receipt
        waiver_validator(receipt)
    else:
        if reviewer_validator is None:
            from src.pipelines.rsf_surrogate import validate_review_receipt

            reviewer_validator = validate_review_receipt
        reviewer_validator(receipt)
    return receipt, _sha256(review_path)


def _verify_source(run_dir: Path, checkpoint_root: Path) -> dict[str, Any]:
    """Verify the released run and its historical code/data inputs without fitting."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=checkpoint_root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    if head != CHECKPOINT_COMMIT:
        raise RuntimeError(f"checkpoint checkout is {head}, expected {CHECKPOINT_COMMIT}")
    if _sha256(run_dir / "manifest.json") != SOURCE_MANIFEST_FILE_SHA256:
        raise RuntimeError("source manifest is not from the pinned confirmatory release")
    if _sha256(run_dir / "completion.json") != SOURCE_COMPLETION_FILE_SHA256:
        raise RuntimeError("source completion record is not from the pinned release")
    frozen = _current_frozen_run_verifier()(run_dir)
    if frozen.mode != "confirmatory" or len(frozen.cells) != 450:
        raise RuntimeError("source must be the complete frozen 450-cell confirmatory run")
    run_config = frozen.manifest.get("run_config", {})
    if (
        tuple(run_config.get("datasets", ())) != EXPECTED_COHORTS
        or "random_survival_forest" not in run_config.get("models", ())
        or int(run_config.get("outer_repeats", 0)) != 5
        or int(run_config.get("outer_splits", 0)) != 5
    ):
        raise RuntimeError("source confirmatory grid differs from the frozen surrogate plan")
    rsf_cells = [cell for _, cell in frozen.cells if cell.get("model_key") == "random_survival_forest"]
    if len(rsf_cells) != 75:
        raise RuntimeError(f"source has {len(rsf_cells)} RSF cells; expected 75")
    _current_frozen_evidence_verifier()(
        checkpoint_root,
        frozen.manifest.get("input_sha256"),
        checkpoint=CHECKPOINT_COMMIT,
    )
    return {
        "manifest_sha256": _sha256(run_dir / "manifest.json"),
        "completion_sha256": _sha256(run_dir / "completion.json"),
        "manifest": frozen.manifest,
        "cells": frozen.cells,
        "source_hashes": frozen.source_hashes,
    }


def _verify_cell_hash(record: dict[str, Any]) -> None:
    """Check a surrogate cell's embedded canonical content digest."""
    from src.utils.reproducibility import canonical_json_hash

    unhashed = dict(record)
    claimed = unhashed.pop("cell_content_sha256", None)
    if claimed != canonical_json_hash(unhashed):
        raise RuntimeError("stored surrogate cell content hash is invalid")


def _write_record(path: Path, record: dict[str, Any], *, overwrite: bool = False) -> None:
    """Write one immutable JSON record through the project's atomic writer."""
    _current_io_helpers().write_json_atomic(path, record, overwrite=overwrite)


def _build_manifest(
    *,
    source: dict[str, Any],
    checkpoint_root: Path,
    environment_lock: Path,
    environment_platform: str,
    output_dir: Path,
    review_sha256: str,
    gate_receipt_type: str,
    pipeline: Any,
    pilot: bool,
    pilot_completion_sha256: str | None,
) -> dict[str, Any]:
    """Build the immutable provenance record for this new post-hoc run."""
    from src.utils.reproducibility import canonical_json_hash

    source_manifest = source["manifest"]
    source_hashes = {
        "source_manifest.json": source["manifest_sha256"],
        "source_completion.json": source["completion_sha256"],
    }
    input_hashes = {
        path: digest
        for path, digest in source_manifest["input_sha256"].items()
        if path.startswith("data/raw/")
    }
    code_hashes = {
        "src/pipelines/rsf_surrogate.py": _sha256(PROJECT_ROOT / "src/pipelines/rsf_surrogate.py"),
        "src/data/cohorts.py": _sha256(PROJECT_ROOT / "src/data/cohorts.py"),
        "src/utils/io.py": _sha256(PROJECT_ROOT / "src/utils/io.py"),
        "scripts/run_rsf_surrogate.py": _sha256(Path(__file__).resolve()),
    }
    gate_receipt = {
        "type": gate_receipt_type,
        "sha256": review_sha256,
        "independent_acceptance": gate_receipt_type == "independent_review",
    }
    identity = {
        "protocol_sha256": pipeline.PROTOCOL_SHA256,
        "source_hashes": source_hashes,
        "raw_input_sha256": input_hashes,
        "code_sha256": code_hashes,
        "protocol_gate_receipt": gate_receipt,
        "checkpoint_commit": CHECKPOINT_COMMIT,
        "lock_sha256": _sha256_text(checkpoint_root / "conda-lock.yml"),
        "execution_environment_lock_sha256": _sha256_text(environment_lock),
        "execution_environment_platform": environment_platform,
        "cohorts": list(pipeline.COHORTS),
        "planned_cells_per_cohort": pipeline.PLANNED_FOLDS_PER_COHORT,
        "run_type": "pilot" if pilot else "production",
        "pilot_completion_sha256": pilot_completion_sha256,
    }
    record: dict[str, Any] = {
        "schema_version": "1.0.0",
        "analysis": "posthoc_rsf_surrogate_v1",
        "created_at_utc": datetime.now(UTC).isoformat(),
        "protocol_sha256": pipeline.PROTOCOL_SHA256,
        "protocol_version": "1.0",
        "run_type": "pilot" if pilot else "production",
        "pilot_completion_sha256": pilot_completion_sha256,
        "protocol_gate_receipt": gate_receipt,
        "source_release": {
            "manifest_sha256": source["manifest_sha256"],
            "completion_sha256": source["completion_sha256"],
            "verified_files": source_hashes,
            "source_git_commit": source_manifest["code"]["git_commit"],
            "checkpoint_commit": CHECKPOINT_COMMIT,
        },
        "raw_input_sha256": input_hashes,
        "code_sha256": code_hashes,
        "lock_sha256": identity["lock_sha256"],
        "execution_environment": {
            "lock_file": environment_lock.name,
            "lock_sha256": identity["execution_environment_lock_sha256"],
            "platform": environment_platform,
        },
        "run_identity_sha256": canonical_json_hash(identity),
        "planned_denominator": {
            cohort: pipeline.PLANNED_FOLDS_PER_COHORT for cohort in pipeline.COHORTS
        },
        "runtime": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "executable": Path(sys.executable).name,
        },
        "claim_boundary": (
            "Post-hoc approximation of the RSF prediction function. Fidelity and "
            "survival performance are separate. No causal, biological, clinical-utility, "
            "deployment, superiority, equivalence, independent-validation, or original "
            "explanation-stability claim is supported."
        ),
    }
    record["manifest_content_sha256"] = canonical_json_hash(record)
    return record


def _resume_cells(run_dir: Path, manifest: dict[str, Any]) -> dict[tuple[str, int, int], dict[str, Any]]:
    """Load only hash-valid cells bound to the same run identity."""
    records: dict[tuple[str, int, int], dict[str, Any]] = {}
    root = run_dir / "cells"
    if not root.exists():
        return records
    for path in sorted(root.glob("*/*.json")):
        record = _read_json(path)
        _verify_cell_hash(record)
        if record.get("run_identity_sha256") != manifest["run_identity_sha256"]:
            raise RuntimeError(f"saved cell belongs to another run identity: {path}")
        key = (str(record["dataset"]), int(record["repeat"]), int(record["fold"]))
        if key in records:
            raise RuntimeError(f"duplicate saved cell identity: {key}")
        records[key] = record
    return records


def _cell_record(
    dataset: str,
    repeat: int,
    fold_number: int,
    source_cell: dict[str, Any] | None,
    source_cell_hash: str | None,
    *,
    run_identity: str,
) -> dict[str, Any]:
    """Create the stable identity fields shared by every cell status."""
    return {
        "schema_version": "1.0.0",
        "dataset": dataset,
        "repeat": repeat,
        "fold": fold_number,
        "model_key": "random_survival_forest",
        "source_status": None if source_cell is None else source_cell.get("status"),
        "source_cell_sha256": source_cell_hash,
        "source_cell_content_sha256": (
            None if source_cell is None else source_cell.get("cell_content_sha256")
        ),
        "run_identity_sha256": run_identity,
        "status": "pending",
    }


def _source_cell_index(source: dict[str, Any]) -> tuple[dict[tuple[str, int, int], dict[str, Any]], dict[str, str]]:
    """Index the frozen RSF cells and their exact relative file hashes."""
    cells: dict[tuple[str, int, int], dict[str, Any]] = {}
    hashes: dict[str, str] = {}
    for relative, cell in source["cells"]:
        if cell.get("model_key") != "random_survival_forest":
            continue
        key = (str(cell["dataset"]), int(cell["repeat"]), int(cell["fold"]))
        cells[key] = cell
        hashes[key] = source["source_hashes"][relative]
    return cells, hashes


def _run_cells(
    *,
    source: dict[str, Any],
    checkpoint_root: Path,
    output_dir: Path,
    manifest: dict[str, Any],
    resume: bool,
    pilot: bool,
    pipeline: Any,
) -> dict[str, Any]:
    """Replay source forests, fit fold-safe students and seal every planned cell."""
    import numpy as np
    import yaml

    from src.data.fold_preprocessing import FoldFeaturePreprocessor
    from src.data.survival_folds import repeated_survival_folds
    from src.models.random_survival_forest import RandomSurvivalForestModel
    from src.utils.reproducibility import canonical_json_hash, sha256_file

    cohorts = _current_cohort_loader()
    load_analysis_dataset = cohorts.load_analysis_dataset
    select_feature_spec = cohorts.select_feature_spec
    json_safe = _current_io_helpers().json_safe

    config = yaml.safe_load((checkpoint_root / "config/confirmatory.yaml").read_text(encoding="utf-8"))
    dataset_config = yaml.safe_load((checkpoint_root / "config/datasets.yaml").read_text(encoding="utf-8"))
    if resume and (output_dir / "completion.json").exists():
        raise FileExistsError("run is already sealed; do not resume a completed result")
    source_cells, source_hashes = _source_cell_index(source)
    manifest_path = output_dir / "manifest.json"
    if resume:
        if not manifest_path.is_file():
            raise FileNotFoundError("cannot resume without the original run manifest")
        saved_manifest = _read_json(manifest_path)
        claimed = saved_manifest.pop("manifest_content_sha256", None)
        if claimed != canonical_json_hash(saved_manifest):
            raise RuntimeError("saved run manifest content hash is invalid")
        if saved_manifest.get("run_identity_sha256") != manifest["run_identity_sha256"]:
            raise RuntimeError("saved run manifest belongs to different source or code inputs")
        records = _resume_cells(output_dir, manifest)
    else:
        if output_dir.exists():
            raise FileExistsError(f"refusing to reuse an existing run directory: {output_dir}")
        output_dir.parent.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir()
        records = {}
    expected_count = len(pipeline.COHORTS) if pilot else len(pipeline.COHORTS) * pipeline.PLANNED_FOLDS_PER_COHORT
    if len(records) > expected_count:
        raise RuntimeError("saved run contains more cells than the frozen plan")

    if not resume:
        _write_record(manifest_path, manifest)
    for cohort_index, dataset in enumerate(pipeline.COHORTS):
        entry = dataset_config[dataset]
        raw_path = checkpoint_root / entry["raw_file"]
        if sha256_file(raw_path) != source["manifest"]["input_sha256"][entry["raw_file"]]:
            raise RuntimeError(f"raw input changed after source preflight: {dataset}")
        raw, times, events, subject_ids = load_analysis_dataset(checkpoint_root, dataset, entry)
        if sha256_file(raw_path) != source["manifest"]["input_sha256"][entry["raw_file"]]:
            raise RuntimeError(f"raw input hash mismatch for {dataset}")
        folds = repeated_survival_folds(
            times,
            events,
            n_splits=int(config["validation"]["outer_splits"]),
            n_repeats=int(config["validation"]["outer_repeats"]),
            base_seed=int(config["validation"]["base_seed"]),
            max_time_bins=int(config["validation"]["followup_time_bins"]),
        )
        if len(folds) != pipeline.PLANNED_FOLDS_PER_COHORT:
            raise RuntimeError("source fold plan differs from the frozen 25-cell cohort design")
        feature_spec = select_feature_spec(entry, "primary")
        for fold in folds:
            if pilot and (fold.repeat, fold.fold) != (1, 1):
                continue
            key = (dataset, fold.repeat, fold.fold)
            if key in records:
                continue
            source_cell = source_cells.get(key)
            cell = _cell_record(
                dataset,
                fold.repeat,
                fold.fold,
                source_cell,
                source_hashes.get(key),
                run_identity=manifest["run_identity_sha256"],
            )
            started = time.perf_counter()
            phase = "source_validation"
            try:
                if source_cell is None:
                    cell.update({"status": "source_cell_absent", "failure_reason": "no frozen RSF cell"})
                elif source_cell["status"] != "complete":
                    cell.update(
                        {
                            "status": "source_cell_failed",
                            "source_failure_status": source_cell["status"],
                            "failure_reason": source_cell.get("message", "source cell did not complete"),
                        }
                    )
                else:
                    expected_train_ids = [str(value) for value in subject_ids[fold.train_indices]]
                    expected_validation_ids = [str(value) for value in subject_ids[fold.validation_indices]]
                    if [str(value) for value in source_cell["train_subject_ids"]] != expected_train_ids:
                        raise ValueError("source outer-training subject order differs from frozen folds")
                    if [str(value) for value in source_cell["validation_subject_ids"]] != expected_validation_ids:
                        raise ValueError("source outer-validation subject order differs from frozen folds")
                    if int(source_cell["fold_seed"]) != int(fold.seed):
                        raise ValueError("source fold seed differs from frozen fold generator")
                    if source_cell.get("dataset_sha256") != source["manifest"]["input_sha256"][entry["raw_file"]]:
                        raise ValueError("source cell dataset hash differs from the frozen raw cohort")
                    preprocessing = source_cell["preprocessing"]
                    processor = FoldFeaturePreprocessor.from_metadata(feature_spec, preprocessing)
                    x_train = processor.transform(raw.iloc[fold.train_indices])
                    x_validation = processor.transform(raw.iloc[fold.validation_indices])
                    if list(x_train.columns) != list(preprocessing["feature_names"]):
                        raise ValueError("restored feature order differs from source preprocessor")
                    phase = "rsf_replay"
                    model = RandomSurvivalForestModel(
                        random_state=int(source_cell["cell_seed"]),
                        **source_cell["selected_hyperparameters"],
                    )
                    model.fit(x_train, times[fold.train_indices], events[fold.train_indices])
                    replay_train = model.predict_risk(x_train)
                    replay_validation = model.predict_risk(x_validation)
                    prediction = source_cell["predictions"]
                    replay_check = pipeline.verify_teacher_replay(
                        prediction["risk"],
                        replay_validation,
                        prediction["subject_ids"],
                        expected_validation_ids,
                    )
                    if not np.allclose(
                        np.asarray(prediction["observed_time"], dtype=float),
                        times[fold.validation_indices],
                        rtol=0.0,
                        atol=0.0,
                    ) or not np.array_equal(
                        np.asarray(prediction["observed_event"], dtype=int),
                        events[fold.validation_indices],
                    ):
                        raise ValueError("source validation outcomes differ from frozen cohort rows")
                    seed = pipeline.surrogate_seed(cohort_index, fold.repeat, fold.fold)
                    phase = "student_fit"
                    evaluation = pipeline.fit_and_evaluate_surrogate_fold(
                        x_train,
                        replay_train,
                        x_validation,
                        replay_validation,
                        times[fold.validation_indices],
                        events[fold.validation_indices],
                        seed=seed,
                        feature_groups=processor.feature_groups,
                        preprocessing=preprocessing,
                    )
                    fit = evaluation["fit"]
                    cell.update(
                        {
                            "status": "complete",
                            "teacher_replay": replay_check,
                            "seeds": {
                                "rsf_replay": int(source_cell["cell_seed"]),
                                "student_inner_cv_and_tree": seed,
                            },
                            "selected_hyperparameters": source_cell["selected_hyperparameters"],
                            "preprocessing_state_sha256": preprocessing["training_state_sha256"],
                            "student_selection": fit.selection,
                            "metrics": evaluation["metrics"],
                            "tree_diagnostics": evaluation["tree_diagnostics"],
                            "predictions": {
                                "subject_ids": expected_validation_ids,
                                "teacher_risk": replay_validation,
                                "student_risk": evaluation["student_risk"],
                                "observed_time": times[fold.validation_indices],
                                "observed_event": events[fold.validation_indices],
                            },
                        }
                    )
            except Exception as exc:
                status = {
                    "source_validation": "source_integrity_failed",
                    "rsf_replay": "rsf_replay_failed",
                    "student_fit": "student_fit_failed",
                }.get(phase, "analysis_failed")
                if phase == "rsf_replay" and "risk differs from source" in str(exc):
                    status = "replay_mismatch"
                cell.update(
                    {
                        "status": status,
                        "failure_phase": phase,
                        "error_type": type(exc).__name__,
                        "failure_reason": str(exc),
                        "traceback": traceback.format_exc(),
                    }
                )
            cell["total_seconds"] = time.perf_counter() - started
            unhashed = json_safe(cell)
            cell["cell_content_sha256"] = canonical_json_hash(unhashed)
            cell_path = output_dir / "cells" / dataset / f"r{fold.repeat:02d}f{fold.fold:02d}.json"
            _write_record(cell_path, cell)
            records[key] = cell

    if len(records) != expected_count:
        raise RuntimeError(f"surrogate run has {len(records)} of {expected_count} planned cells")
    if pilot:
        _write_pilot_summary(output_dir, records, source, pipeline, overwrite=resume)
        return _seal_pilot(output_dir, records, source, pipeline)
    _write_aggregates(output_dir, records, source, pipeline, overwrite=resume)
    return _seal_run(output_dir, records, source, pipeline)


def _write_pilot_summary(
    run_dir: Path,
    records: dict[tuple[str, int, int], dict[str, Any]],
    source: dict[str, Any],
    pipeline: Any,
    *,
    overwrite: bool,
) -> None:
    """Record one measured r01f01 replay per cohort and a simple runtime projection."""
    rows = []
    projected = 0.0
    complete = True
    for cohort in pipeline.COHORTS:
        record = records[(cohort, 1, 1)]
        seconds = float(record["total_seconds"])
        succeeded = record["status"] == "complete"
        complete = complete and succeeded
        cohort_projection = seconds * pipeline.PLANNED_FOLDS_PER_COHORT if succeeded else None
        if cohort_projection is not None:
            projected += cohort_projection
        rows.append(
            {
                "dataset": cohort,
                "repeat": 1,
                "fold": 1,
                "status": record["status"],
                "measured_seconds": seconds,
                "projected_25_cell_seconds": cohort_projection,
            }
        )
    summary = {
        "protocol_sha256": pipeline.PROTOCOL_SHA256,
        "source_completion_sha256": source["completion_sha256"],
        "status": "complete" if complete else "incomplete",
        "pilot_cells": rows,
        "projected_total_seconds": projected if complete else None,
        "maximum_allowed_projected_seconds": MAX_PROJECTED_SECONDS,
        "projection_method": "25 times each cohort's measured r01f01 replay-and-fit runtime; no overhead adjustment",
        "full_run_within_compute_allowance": bool(complete and projected <= MAX_PROJECTED_SECONDS),
    }
    _current_io_helpers().write_json_atomic(
        run_dir / "pilot_summary.json", summary, overwrite=overwrite
    )
    lines = [
        "# RSF surrogate compute pilot",
        "",
        "This separate pilot measures one replay and fold-safe tree fit per cohort.",
        "It is not the 75-cell study result.",
        "",
        "| Cohort | Cell | Status | Measured seconds | Projected seconds for 25 cells |",
        "| --- | --- | --- | ---: | ---: |",
    ]
    for row in rows:
        projection = row["projected_25_cell_seconds"]
        projection_text = "unavailable" if projection is None else f"{projection:.2f}"
        lines.append(
            f"| {row['dataset']} | r01f01 | {row['status']} | "
            f"{row['measured_seconds']:.2f} | {projection_text} |"
        )
    lines.extend(
        [
            "",
            f"Total projected seconds: {summary['projected_total_seconds']}",
            f"Maximum allowed projection: {MAX_PROJECTED_SECONDS} seconds.",
            "",
        ]
    )
    (run_dir / "pilot_report.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _seal_pilot(
    run_dir: Path,
    records: dict[tuple[str, int, int], dict[str, Any]],
    source: dict[str, Any],
    pipeline: Any,
) -> dict[str, Any]:
    """Seal the three-cell runtime pilot independently from the 75-cell study."""
    from src.utils.reproducibility import canonical_json_hash

    statuses = Counter(record["status"] for record in records.values())
    cells = {
        f"cells/{dataset}/r01f01.json": _sha256(
            run_dir / "cells" / dataset / "r01f01.json"
        )
        for dataset in pipeline.COHORTS
    }
    aggregates = {
        name: _sha256(run_dir / name)
        for name in ("pilot_summary.json", "pilot_report.md")
    }
    completion: dict[str, Any] = {
        "schema_version": "1.0.0",
        "analysis": "posthoc_rsf_surrogate_v1_pilot",
        "protocol_sha256": pipeline.PROTOCOL_SHA256,
        "source_completion_sha256": source["completion_sha256"],
        "planned_cells": len(pipeline.COHORTS),
        "stored_cells": len(cells),
        "status_counts": dict(sorted(statuses.items())),
        "cell_sha256": cells,
        "aggregate_sha256": aggregates,
        "sealed_at_utc": datetime.now(UTC).isoformat(),
    }
    completion["completion_content_sha256"] = canonical_json_hash(completion)
    _write_record(run_dir / "pilot_completion.json", completion)
    return completion


def _verify_pilot_run(
    pilot_dir: Path,
    *,
    checkpoint_root: Path,
    environment_lock: Path,
    environment_platform: str,
    source: dict[str, Any],
    review_sha256: str,
    gate_receipt_type: str,
    pipeline: Any,
    require_complete: bool = True,
    require_budget: bool = True,
) -> tuple[dict[str, Any], str]:
    """Verify the pilot's three cell files, measured runtimes and compute bound."""
    from src.utils.reproducibility import canonical_json_hash

    manifest = _read_json(pilot_dir / "manifest.json")
    claimed_manifest = manifest.pop("manifest_content_sha256", None)
    if claimed_manifest != canonical_json_hash(manifest):
        raise RuntimeError("pilot manifest content hash is invalid")
    if manifest.get("run_type") != "pilot" or manifest.get("protocol_sha256") != pipeline.PROTOCOL_SHA256:
        raise RuntimeError("pilot does not match the frozen RSF surrogate protocol")
    expected_gate_receipt = {
        "type": gate_receipt_type,
        "sha256": review_sha256,
        "independent_acceptance": gate_receipt_type == "independent_review",
    }
    if manifest.get("protocol_gate_receipt") != expected_gate_receipt:
        raise RuntimeError("pilot used a different protocol gate receipt")
    if manifest.get("source_release", {}).get("manifest_sha256") != source["manifest_sha256"]:
        raise RuntimeError("pilot points to a different frozen source manifest")
    if manifest.get("source_release", {}).get("completion_sha256") != source["completion_sha256"]:
        raise RuntimeError("pilot points to a different frozen source completion")
    expected_code = {
        "src/pipelines/rsf_surrogate.py": _sha256(PROJECT_ROOT / "src/pipelines/rsf_surrogate.py"),
        "src/data/cohorts.py": _sha256(PROJECT_ROOT / "src/data/cohorts.py"),
        "src/utils/io.py": _sha256(PROJECT_ROOT / "src/utils/io.py"),
        "scripts/run_rsf_surrogate.py": _sha256(Path(__file__).resolve()),
    }
    if manifest.get("code_sha256") != expected_code:
        raise RuntimeError("pilot code differs from the current frozen implementation")
    checkpoint_root = checkpoint_root.resolve()
    if manifest.get("lock_sha256") != _sha256_text(checkpoint_root / "conda-lock.yml"):
        raise RuntimeError("pilot used a different environment lock")
    expected_execution_environment = {
        "lock_file": environment_lock.name,
        "lock_sha256": _sha256_text(environment_lock),
        "platform": environment_platform,
    }
    if manifest.get("execution_environment") != expected_execution_environment:
        raise RuntimeError("pilot used a different execution environment lock")
    expected_raw = {
        path: digest
        for path, digest in source["manifest"]["input_sha256"].items()
        if path.startswith("data/raw/")
    }
    if manifest.get("raw_input_sha256") != expected_raw:
        raise RuntimeError("pilot raw-data hashes differ from the frozen source run")
    completion_path = pilot_dir / "pilot_completion.json"
    completion = _read_json(completion_path)
    claimed_completion = completion.pop("completion_content_sha256", None)
    if claimed_completion != canonical_json_hash(completion):
        raise RuntimeError("pilot completion content hash is invalid")
    if (
        completion.get("protocol_sha256") != pipeline.PROTOCOL_SHA256
        or completion.get("source_completion_sha256") != source["completion_sha256"]
    ):
        raise RuntimeError("pilot completion points to a different protocol or source run")
    if completion.get("planned_cells") != len(pipeline.COHORTS) or completion.get("stored_cells") != len(pipeline.COHORTS):
        raise RuntimeError("pilot completion does not account for one cell per cohort")
    expected_cells = {
        f"cells/{cohort}/r01f01.json": pilot_dir / "cells" / cohort / "r01f01.json"
        for cohort in pipeline.COHORTS
    }
    inventory = completion.get("cell_sha256")
    if not isinstance(inventory, dict) or set(inventory) != set(expected_cells):
        raise RuntimeError("pilot cell inventory does not contain one fold per cohort")
    actual_cells = {
        path.relative_to(pilot_dir).as_posix()
        for path in (pilot_dir / "cells").glob("*/*.json")
    }
    if actual_cells != set(expected_cells):
        raise RuntimeError("pilot directory has an unexpected cell inventory")
    runtimes: dict[str, float] = {}
    statuses: Counter[str] = Counter()
    for relative, path in expected_cells.items():
        if _sha256(path) != inventory[relative]:
            raise RuntimeError(f"pilot cell file hash mismatch: {relative}")
        cell = _read_json(path)
        _verify_cell_hash(cell)
        if (
            cell.get("dataset") != Path(relative).parts[1]
            or (cell.get("repeat"), cell.get("fold")) != (1, 1)
        ):
            raise RuntimeError(f"pilot cell identity differs from its path: {relative}")
        status = str(cell.get("status"))
        statuses[status] += 1
        if status == "complete":
            runtimes[str(cell["dataset"])] = float(cell["total_seconds"])
    if dict(sorted(statuses.items())) != completion.get("status_counts"):
        raise RuntimeError("pilot completion status counts differ from its cells")
    summary_path = pilot_dir / "pilot_summary.json"
    aggregate_inventory = completion.get("aggregate_sha256", {})
    if set(aggregate_inventory) != {"pilot_summary.json", "pilot_report.md"}:
        raise RuntimeError("pilot aggregate inventory is incomplete")
    if any(_sha256(pilot_dir / name) != digest for name, digest in aggregate_inventory.items()):
        raise RuntimeError("pilot aggregate file hash mismatch")
    summary = _read_json(summary_path)
    if (
        summary.get("protocol_sha256") != pipeline.PROTOCOL_SHA256
        or summary.get("source_completion_sha256") != source["completion_sha256"]
    ):
        raise RuntimeError("pilot summary points to a different protocol or source run")
    all_complete = len(runtimes) == len(pipeline.COHORTS)
    if summary.get("status") != ("complete" if all_complete else "incomplete"):
        raise RuntimeError("pilot summary status differs from the cell records")
    if require_complete and not all_complete:
        raise RuntimeError("pilot has an absent or failed source/student cell")
    if all_complete:
        projected = sum(runtimes[cohort] for cohort in pipeline.COHORTS) * pipeline.PLANNED_FOLDS_PER_COHORT
        within_budget = projected <= MAX_PROJECTED_SECONDS
        if abs(float(summary["projected_total_seconds"]) - projected) > 1e-9:
            raise RuntimeError("pilot runtime projection differs from the measured cell runtimes")
        if bool(summary.get("full_run_within_compute_allowance")) != within_budget:
            raise RuntimeError("pilot compute-allowance decision differs from the measured projection")
        if require_budget and not within_budget:
            raise RuntimeError("pilot runtime projection exceeds the 60-minute compute allowance")
    elif summary.get("projected_total_seconds") is not None:
        raise RuntimeError("incomplete pilot must not project an incomplete cohort grid")
    elif summary.get("full_run_within_compute_allowance"):
        raise RuntimeError("incomplete pilot cannot approve the full-grid compute allowance")
    return summary, _sha256(completion_path)


def _write_aggregates(
    run_dir: Path,
    records: dict[tuple[str, int, int], dict[str, Any]],
    source: dict[str, Any],
    pipeline: Any,
    *,
    overwrite: bool,
) -> None:
    """Write cohort summaries and a concise report without dropping failures."""
    by_cohort: dict[str, Any] = {}
    for cohort_index, cohort in enumerate(pipeline.COHORTS):
        cohort_records = [
            record for (dataset, _, _), record in sorted(records.items()) if dataset == cohort
        ]
        statuses = Counter(record["status"] for record in cohort_records)
        complete = [record for record in cohort_records if record["status"] == "complete"]
        candidate_groups = sorted(
            {
                group
                for record in complete
                for group in record["tree_diagnostics"]["candidate_feature_groups"]
            }
        )
        group_stability = pipeline.feature_group_stability(
            cohort_records, candidate_groups=candidate_groups
        )
        fold_metrics = {
            metric: _finite_distribution(
                [
                    _metric_value(record, metric)
                    for record in complete
                ]
            )
            for metric in (
                "fidelity.spearman",
                "fidelity.normalized_rmse",
                "survival_performance.teacher",
                "survival_performance.student",
                "survival_performance.student_minus_teacher",
            )
        }
        complexity_rows = [record["tree_diagnostics"] for record in complete]
        summary: dict[str, Any] = {
            "planned_cells": pipeline.PLANNED_FOLDS_PER_COHORT,
            "stored_cells": len(cohort_records),
            "status_counts": dict(sorted(statuses.items())),
            "fold_metric_distributions": fold_metrics,
            "feature_group_stability": group_stability,
            "tree_complexity_summary": {
                name: _finite_distribution([float(row[name]) for row in complexity_rows])
                for name in ("depth", "node_count", "leaf_count")
            },
            "fold_tree_complexity": [
                {
                    "repeat": record["repeat"],
                    "fold": record["fold"],
                    "depth": record["tree_diagnostics"]["depth"],
                    "node_count": record["tree_diagnostics"]["node_count"],
                    "leaf_count": record["tree_diagnostics"]["leaf_count"],
                }
                for record in complete
            ],
            "fold_rules": [
                {
                    "repeat": record["repeat"],
                    "fold": record["fold"],
                    "rules_text": record["tree_diagnostics"]["rules_text"],
                    "feature_group_importance": record["tree_diagnostics"]["feature_group_importance"],
                }
                for record in complete
            ],
        }
        if len(complete) == pipeline.PLANNED_FOLDS_PER_COHORT:
            raw_frame, time_values, event_values, subject_ids = _load_cohort_for_summary(cohort)
            fold_average = pipeline.average_repeated_fold_percentiles(
                complete, subject_ids, n_repeats=5, n_folds=5
            )
            summary["repeated_fold_subject_summary"] = pipeline.summarize_subject_predictions(
                fold_average["teacher_percentiles"],
                fold_average["student_percentiles"],
                time_values,
                event_values,
                seed=pipeline.bootstrap_seed(cohort_index),
                bootstrap_replicates=2000,
            )
            summary["repeated_fold_subject_summary"]["n_subjects"] = len(raw_frame)
        else:
            summary["repeated_fold_subject_summary"] = {
                "status": "unavailable_incomplete_grid",
                "reason": "the frozen cohort bootstrap requires all 25 complete outer folds",
            }
        by_cohort[cohort] = summary

    _current_io_helpers().write_json_atomic(
        run_dir / "cohort_summaries.json", by_cohort, overwrite=overwrite
    )
    _write_markdown_report(run_dir / "report.md", by_cohort, source, pipeline)


def _load_cohort_for_summary(cohort: str) -> tuple[Any, Any, Any, Any]:
    """Load raw cohort outcomes using the pinned checkpoint package and root."""
    import yaml

    checkpoint_root = Path(sys.path[0]).resolve()
    dataset_config = yaml.safe_load((checkpoint_root / "config/datasets.yaml").read_text(encoding="utf-8"))
    load_analysis_dataset = _current_cohort_loader().load_analysis_dataset
    return load_analysis_dataset(checkpoint_root, cohort, dataset_config[cohort])


def _metric_value(record: dict[str, Any], path: str) -> float | None:
    """Get a nested numeric point estimate, preserving undefined values."""
    current: Any = record["metrics"]
    for key in path.split("."):
        current = current[key]
    if isinstance(current, dict):
        current = current.get("estimate")
    return None if current is None else float(current)


def _finite_distribution(values: list[float | None]) -> dict[str, Any]:
    """Summarise finite fold-level values without treating folds as replicates."""
    import numpy as np

    finite = np.asarray([value for value in values if value is not None and np.isfinite(value)], dtype=float)
    if not len(finite):
        return {"n_defined": 0, "median": None, "q25": None, "q75": None}
    q25, median, q75 = np.quantile(finite, [0.25, 0.5, 0.75])
    return {
        "n_defined": int(len(finite)),
        "median": float(median),
        "q25": float(q25),
        "q75": float(q75),
    }


def _write_markdown_report(
    path: Path, summaries: dict[str, Any], source: dict[str, Any], pipeline: Any
) -> None:
    """Render status and metric summaries with explicit post-hoc claim limits."""
    lines = [
        "# RSF surrogate-tree study",
        "",
        "This is a separate post-hoc approximation study. It does not modify the frozen baseline.",
        "Fidelity measures agreement with RSF predictions; Harrell concordance measures survival ranking.",
        "Neither is a clinical-utility, causal, biological, superiority, equivalence, or deployment result.",
        "Full per-fold rules and diagnostics are retained in `cohort_summaries.json`.",
        "",
        f"Protocol SHA-256: `{pipeline.PROTOCOL_SHA256}`",
        f"Source completion SHA-256: `{source['completion_sha256']}`",
        "",
    ]
    for cohort, summary in summaries.items():
        lines.extend(
            [
                f"## {cohort}",
                "",
                f"Cell status counts: `{json.dumps(summary['status_counts'], sort_keys=True)}`",
                "",
                "| Fold metric | n | Median | IQR |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for metric, values in summary["fold_metric_distributions"].items():
            iqr = "unavailable" if values["q25"] is None else f"{values['q25']:.4g}–{values['q75']:.4g}"
            median = "unavailable" if values["median"] is None else f"{values['median']:.4g}"
            lines.append(f"| {metric} | {values['n_defined']} | {median} | {iqr} |")
        lines.extend(
            [
                "",
                "Tree complexity medians:",
                "",
                "; ".join(
                    f"{name}={values['median'] if values['median'] is not None else 'unavailable'}"
                    for name, values in summary["tree_complexity_summary"].items()
                ),
                "",
                "Feature-group use against all 25 planned trees:",
                "",
                "| Feature group | Trees using group | Planned proportion | Split count |",
                "| --- | ---: | ---: | ---: |",
            ]
        )
        for group, values in summary["feature_group_stability"]["feature_groups"].items():
            lines.append(
                f"| {group} | {values['fold_use_count']} | "
                f"{values['planned_fold_proportion']:.3f} | {values['split_count']} |"
            )
        subject_summary = summary["repeated_fold_subject_summary"]
        if subject_summary.get("status") == "unavailable_incomplete_grid":
            lines.extend(["", f"Subject-level bootstrap: unavailable ({subject_summary['reason']})."])
        else:
            lines.extend(
                [
                    "",
                    "Subject-level repeated-fold summary:",
                    "",
                    "```json",
                    json.dumps(subject_summary, indent=2, sort_keys=True),
                    "```",
                ]
            )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def _seal_run(
    run_dir: Path,
    records: dict[tuple[str, int, int], dict[str, Any]],
    source: dict[str, Any],
    pipeline: Any,
) -> dict[str, Any]:
    """Write a completion record covering all planned cells and aggregates."""
    from src.utils.reproducibility import canonical_json_hash

    statuses = Counter(record["status"] for record in records.values())
    cells = {
        f"cells/{dataset}/r{repeat:02d}f{fold:02d}.json": _sha256(
            run_dir / "cells" / dataset / f"r{repeat:02d}f{fold:02d}.json"
        )
        for dataset, repeat, fold in sorted(records)
    }
    aggregates = {
        name: _sha256(run_dir / name)
        for name in ("cohort_summaries.json", "report.md")
    }
    completion: dict[str, Any] = {
        "schema_version": "1.0.0",
        "analysis": "posthoc_rsf_surrogate_v1",
        "protocol_sha256": pipeline.PROTOCOL_SHA256,
        "source_completion_sha256": source["completion_sha256"],
        "planned_cells": len(pipeline.COHORTS) * pipeline.PLANNED_FOLDS_PER_COHORT,
        "stored_cells": len(cells),
        "status_counts": dict(sorted(statuses.items())),
        "cell_sha256": cells,
        "aggregate_sha256": aggregates,
        "sealed_at_utc": datetime.now(UTC).isoformat(),
    }
    completion["completion_content_sha256"] = canonical_json_hash(completion)
    _write_record(run_dir / "completion.json", completion)
    return completion


def _worker(args: argparse.Namespace) -> int:
    """Verify inputs and perform production only after the independent-review receipt."""
    checkpoint_root = args.checkpoint_root.resolve(strict=True)
    sys.path.insert(0, str(checkpoint_root))
    pipeline = _load_current_pipeline(checkpoint_root)
    _verify_protocol(pipeline.PROTOCOL_SHA256)
    if args.preflight:
        review_sha256 = None
        gate_receipt_type = None
    else:
        review_path = args.review_receipt.resolve(strict=True)
        gate_receipt, review_sha256 = _verify_protocol_and_review(
            review_path,
            pipeline.validate_review_receipt,
            pipeline.validate_owner_waiver_receipt,
        )
        gate_receipt_type = str(gate_receipt.get("receipt_type", "independent_review"))
        subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts/verify_environment.py"),
                "--platform",
                args.environment_platform,
                "--lock-file",
                str(args.environment_lock.resolve(strict=True)),
                "--hash-file",
                str(Path(f"{args.environment_lock}.sha256").resolve(strict=True)),
            ],
            cwd=PROJECT_ROOT,
            check=True,
        )
    source = _verify_source(args.source_run.resolve(strict=True), checkpoint_root)
    if args.preflight:
        print(
            json.dumps(
                {
        "status": "preflight_passed",
                    "production_started": False,
                    "source_cells": len(source["cells"]),
                    "protocol_sha256": pipeline.PROTOCOL_SHA256,
                    "source_manifest_sha256": source["manifest_sha256"],
                },
                sort_keys=True,
            )
        )
        return 0
    pilot_completion_sha256 = None
    pilot_summary = None
    if args.pilot:
        if args.pilot_run is not None:
            raise ValueError("--pilot and --pilot-run cannot be used together")
    else:
        if args.pilot_run is None:
            raise ValueError("full production requires a verified --pilot-run")
        pilot_summary, pilot_completion_sha256 = _verify_pilot_run(
            args.pilot_run.resolve(strict=True),
            checkpoint_root=checkpoint_root,
            environment_lock=args.environment_lock.resolve(strict=True),
            environment_platform=args.environment_platform,
            source=source,
            review_sha256=str(review_sha256),
            gate_receipt_type=str(gate_receipt_type),
            pipeline=pipeline,
        )
    manifest = _build_manifest(
        source=source,
        checkpoint_root=checkpoint_root,
        environment_lock=args.environment_lock.resolve(strict=True),
        environment_platform=args.environment_platform,
        output_dir=args.output_dir,
        review_sha256=str(review_sha256),
        gate_receipt_type=str(gate_receipt_type),
        pipeline=pipeline,
        pilot=args.pilot,
        pilot_completion_sha256=pilot_completion_sha256,
    )
    completion = _run_cells(
        source=source,
        checkpoint_root=checkpoint_root,
        output_dir=args.output_dir.resolve(),
        manifest=manifest,
        resume=args.resume,
        pilot=args.pilot,
        pipeline=pipeline,
    )
    if args.pilot:
        pilot_summary, pilot_completion_sha256 = _verify_pilot_run(
            args.output_dir.resolve(),
            checkpoint_root=checkpoint_root,
            environment_lock=args.environment_lock.resolve(strict=True),
            environment_platform=args.environment_platform,
            source=source,
            review_sha256=str(review_sha256),
            gate_receipt_type=str(gate_receipt_type),
            pipeline=pipeline,
            require_complete=False,
            require_budget=False,
        )
        verification = {
            "status": "pilot_verified",
            "projected_total_seconds": pilot_summary["projected_total_seconds"],
            "full_run_within_compute_allowance": pilot_summary["full_run_within_compute_allowance"],
            "pilot_completion_sha256": pilot_completion_sha256,
        }
    else:
        verification = pipeline.verify_surrogate_run(args.output_dir.resolve())
    print(
        json.dumps(
            {
                "status": "production_cells_accounted",
                "output_dir": str(args.output_dir.resolve()),
                "stored_cells": completion["stored_cells"],
                "status_counts": completion["status_counts"],
                "completion_content_sha256": completion["completion_content_sha256"],
                "verification": verification,
            },
            sort_keys=True,
        )
    )
    return 0


def _parse_args() -> argparse.Namespace:
    """Parse the user-facing and isolated worker command-line options."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-run", type=Path, default=DEFAULT_SOURCE_RUN)
    parser.add_argument("--checkpoint-root", type=Path, required=True)
    parser.add_argument(
        "--review-receipt",
        "--protocol-gate-receipt",
        dest="review_receipt",
        type=Path,
        default=DEFAULT_REVIEW,
        help="independent review or explicit owner-waiver receipt",
    )
    parser.add_argument("--environment-platform", choices=("osx-arm64", "win-64"), default=DEFAULT_ENVIRONMENT_PLATFORM)
    parser.add_argument("--environment-lock", type=Path, default=DEFAULT_ENVIRONMENT_LOCK)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--pilot", action="store_true", help="run only r01f01 in each cohort for timing")
    parser.add_argument("--pilot-run", type=Path, default=None, help="verified pilot required for full production")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--preflight", action="store_true", help="verify lineage and inputs; fit no models")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    """Run a value-free preflight or start the gated production worker."""
    args = _parse_args()
    if args.worker:
        return _worker(args)
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    if not args.checkpoint_root.is_dir():
        raise FileNotFoundError(f"checkpoint checkout is unavailable: {args.checkpoint_root}")
    if args.preflight:
        command = "preflight"
    else:
        _verify_protocol_and_review(args.review_receipt.resolve(strict=True))
        if not args.pilot and args.pilot_run is None:
            raise ValueError("full production requires --pilot-run from a completed three-cohort timing pilot")
        command = "production"
    if args.output_dir is None:
        if args.resume:
            raise ValueError("--resume requires the original --output-dir")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        args.output_dir = PROJECT_ROOT / "reports/posthoc" / f"rsf_surrogate_v1_{stamp}"
        if args.pilot:
            args.output_dir = PROJECT_ROOT / "reports/posthoc" / f"rsf_surrogate_v1_pilot_{stamp}"
    worker_args = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--worker",
        "--checkpoint-root",
        str(args.checkpoint_root.resolve()),
        "--source-run",
        str(args.source_run.resolve()),
        "--environment-platform",
        args.environment_platform,
        "--environment-lock",
        str(args.environment_lock.resolve()),
    ]
    if args.preflight:
        worker_args.append("--preflight")
    else:
        worker_args.extend(["--review-receipt", str(args.review_receipt.resolve())])
        worker_args.extend(["--output-dir", str(args.output_dir.resolve())])
        if args.pilot:
            worker_args.append("--pilot")
        elif args.pilot_run is not None:
            worker_args.extend(["--pilot-run", str(args.pilot_run.resolve())])
        if args.resume:
            worker_args.append("--resume")
    env = os.environ.copy()
    old_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(args.checkpoint_root.resolve()) + (
        os.pathsep + old_pythonpath if old_pythonpath else ""
    )
    subprocess.run(worker_args, cwd=args.checkpoint_root.resolve(), env=env, check=True)
    if command == "preflight":
        print("No RSF replay or surrogate fit was performed.")
    return 0


def _entrypoint() -> int:
    """Report command failures briefly while retaining cell-level tracebacks in the run."""
    try:
        if "--worker" in sys.argv:
            return _worker(_parse_args())
        return main()
    except Exception as exc:
        print(f"RSF surrogate run failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(_entrypoint())
