"""Independently verify the frozen three-cohort penalised-Cox subset."""

from __future__ import annotations

import argparse
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.reproduce_extensions import scientific_content
from src.data.cohorts import load_analysis_dataset
from src.data.survival_folds import repeated_survival_folds
from src.pipelines.confirmatory.evaluation import (
    evaluate_predictions,
    evaluation_horizons_and_grid,
    validate_survival_prediction_matrix,
)
from src.pipelines.extensions.planning import ExtensionJob
from src.pipelines.extensions.runner import verified_cell
from src.pipelines.extensions.verification import (
    SavedForecast,
    assert_scientific_equal,
    verify_cell_identity,
)
from src.utils.io import json_safe, read_mapping, write_json_atomic
from src.utils.reproducibility import canonical_json_hash, sha256_file

COHORTS = ("gbsg2", "whas500", "metabric")
MODELS = ("ridge", "lasso", "elastic_net")
FOLDS = {(repeat, fold) for repeat in range(1, 6) for fold in range(1, 6)}


def git_commit(root: Path) -> str:
    """Return the exact commit available at a producer or analysis checkout."""
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def verify_analysis_code_commit(root: Path) -> str:
    """Require the executing verifier and analysis modules to be committed."""
    relevant = ("src", "scripts/reproduce_extensions.py", "scripts/verify_clinical_methods_subset.py")
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--", *relevant],
                                    cwd=root, text=True).strip()
    if dirty:
        raise ValueError("clinical subset verifier or analysis modules are not committed")
    return git_commit(root)


def verify_source_identity(production: Path, matched: Path | None, manifest: dict[str, Any]) -> None:
    """Bind a run to its original complete plan, frozen inputs and producer commit."""
    if canonical_json_hash({k: v for k, v in manifest.items() if k != "manifest_content_sha256"}) != manifest["manifest_content_sha256"]:
        raise ValueError("extension manifest content changed")
    if manifest["code"]["git_dirty"] or manifest["code"]["git_changed_paths"]:
        raise ValueError("extension producer was not recorded as clean")
    if git_commit(production) != manifest["code"]["git_commit"]:
        raise ValueError("production checkout differs from the frozen fitted commit")
    if matched is not None and sha256_file(matched) != manifest["matched_sha256"]:
        raise ValueError("matched input differs from the frozen manifest")
    for name, digest in manifest["input_sha256"].items():
        if sha256_file(production / name) != digest:
            raise ValueError(f"frozen production input changed: {name}")
    freeze = read_mapping(production / "coordination/extension_protocol_freeze.json")
    if (canonical_json_hash({k: v for k, v in freeze.items() if k != "content_sha256"})
            != freeze["content_sha256"] or freeze["content_sha256"] != manifest["freeze_sha256"]):
        raise ValueError("extension protocol freeze differs from the fitted manifest")
    for name, digest in freeze["sha256"].items():
        if sha256_file(production / name) != digest:
            raise ValueError(f"frozen protocol input changed: {name}")


def verify_study_scope(root: Path, manifest: dict[str, Any], run: Path) -> str:
    """Bind the verification to the separately frozen post-hoc subset roster."""
    path = root / "coordination/clinical_methods_scope_freeze.json"
    scope = read_mapping(path)
    if (scope["classification"] != "post-hoc outcome-aware subset; not result-blind preregistration"
            or scope["source_extension_manifest_sha256"] != sha256_file(run / "manifest.json")
            or scope["source_fit_commit"] != manifest["code"]["git_commit"]
            or scope["source_penalised_cells"] != 225
            or scope["reference_bayesian_cells"] != 225
            or scope["primary_contrasts"] != 27
            or scope["selected_existing_refits_to_verify"] != 9):
        raise ValueError("clinical methods scope differs from the source run")
    if (scope["baseline_source_pins"] != "coordination/extension_sources/baseline_sources.json"
            or sha256_file(root / scope["baseline_source_pins"]) != scope["baseline_source_pins_sha256"]
            or sha256_file(root / "coordination/extension_protocol_freeze.json")
            != scope["original_extension_freeze_record_sha256"]):
        raise ValueError("clinical methods baseline or original extension freeze pin differs")
    for name, digest in scope["sha256"].items():
        if sha256_file(root / name) != digest:
            raise ValueError(f"clinical methods scope input changed: {name}")
    roster = read_mapping(root / "coordination/clinical_methods_roster.json")
    expected = {"datasets": list(COHORTS), "penalised_models": list(MODELS),
                "repeats": list(range(1, 6)), "folds": list(range(1, 6)),
                "condition": "full", "setting": "clinical", "source_cell_count": 225,
                "selected_reproduction": "all nine penalised-model by cohort cells at repeat 1 fold 1"}
    if any(roster.get(name) != value for name, value in expected.items()):
        raise ValueError("clinical methods roster differs from the fixed selection")
    return sha256_file(path)


def clinical_jobs(jobs: list[ExtensionJob]) -> list[ExtensionJob]:
    """Select exactly three models, three original cohorts and all 25 folds."""
    subset = [j for j in jobs if j.dataset in COHORTS and j.setting == "clinical"
              and j.condition == "full" and j.model in MODELS]
    counts = Counter((j.dataset, j.model) for j in subset)
    if len(subset) != 225 or set(counts) != {(cohort, model) for cohort in COHORTS for model in MODELS}:
        raise ValueError("clinical subset differs from the fixed 225-cell selection")
    for cohort in COHORTS:
        for model in MODELS:
            selected = [j for j in subset if j.dataset == cohort and j.model == model]
            if (counts[(cohort, model)] != 25
                    or {(j.repeat, j.fold) for j in selected} != FOLDS
                    or any(j.censoring_cutoff is not None or j.gene_budget != 0 for j in selected)):
                raise ValueError(f"clinical subset fold coverage differs: {cohort}/{model}")
    return subset


def rebuild_clinical_jobs(root: Path, config: dict[str, Any]) -> tuple[list[ExtensionJob], dict[str, pd.DataFrame]]:
    """Recreate the original three-cohort full-fold grid without expression data."""
    specs = read_mapping(root / "config/datasets.yaml")
    cohorts: dict[str, pd.DataFrame] = {}
    jobs: list[ExtensionJob] = []
    for key in COHORTS:
        raw, times, events, ids = load_analysis_dataset(root, key, specs[key])
        raw = raw.copy()
        raw["duration"], raw["event"], raw["subject_id"] = times, events, ids
        cohorts[key] = raw
        folds = repeated_survival_folds(times, events, n_splits=5, n_repeats=5,
                                        base_seed=config["base_seed"], max_time_bins=4)
        for outer in folds:
            for model in MODELS:
                identity = f"{key}__clinical__r{outer.repeat:02}f{outer.fold:02}__{model}__full"
                jobs.append(ExtensionJob(identity, key, "clinical", model, outer.repeat, outer.fold,
                                         "full", outer.train_indices, outer.validation_indices, None, 0))
    return clinical_jobs(jobs), cohorts


def verify_stored_cell(
    cell: dict[str, Any], job: ExtensionJob, raw: pd.DataFrame,
    *, base_seed: int, primary: dict[str, Any], extension: dict[str, Any],
) -> bool:
    """Check one stored forecast against reconstructed patients, outcomes and scores."""
    verify_cell_identity(cell, job, raw, base_seed)
    if cell["status"] not in {"complete", "failed", "failed_diagnostics"} or cell["model_key"] not in MODELS:
        raise ValueError(f"unrecognized selected penalised-Cox outcome: {job.cell_id}")
    if any(attempt.get("traces") for attempt in cell.get("fit_attempts", [])):
        raise ValueError(f"penalised-Cox cell unexpectedly has traces: {job.cell_id}")
    train_time = raw.duration.iloc[job.train].to_numpy(float)
    train_event = raw.event.iloc[job.train].to_numpy(int)
    validation_time = raw.duration.iloc[job.validation].to_numpy(float)
    validation_event = raw.event.iloc[job.validation].to_numpy(int)
    if cell["events_train"] != int(train_event.sum()):
        raise ValueError(f"training event count differs: {job.cell_id}")
    if cell["status"] != "complete":
        if "predictions" in cell or "metrics" in cell:
            raise ValueError(f"failed cell unexpectedly stores accepted forecasts: {job.cell_id}")
        return False
    predictions = cell["predictions"]
    if predictions["subject_ids"] != cell["validation_subject_ids"]:
        raise ValueError(f"forecast patient order differs: {job.cell_id}")
    for name, expected in (("training_time", train_time), ("training_event", train_event),
                           ("observed_time", validation_time), ("observed_event", validation_event)):
        if not np.array_equal(predictions[name], expected):
            raise ValueError(f"stored outcome differs: {job.cell_id}/{name}")
    horizons, grid = evaluation_horizons_and_grid(train_time, train_event, primary["evaluation"])
    if not np.array_equal(predictions["horizons"], horizons) or not np.array_equal(predictions["ibs_grid"], grid):
        raise ValueError(f"training-derived evaluation times differ: {job.cell_id}")
    risk = np.asarray(predictions["risk"], dtype=float)
    if risk.shape != (len(validation_time),) or not np.isfinite(risk).all():
        raise ValueError(f"invalid saved risk forecast: {job.cell_id}")
    for name, times in (("survival_at_horizons", horizons), ("survival_on_ibs_grid", grid)):
        validate_survival_prediction_matrix(np.asarray(predictions[name], dtype=float),
                                            n_samples=len(validation_time), n_times=len(times))
    metrics, _ = evaluate_predictions(
        SavedForecast(predictions), pd.DataFrame(index=range(len(validation_time))),
        train_time, train_event, validation_time, validation_event,
        evaluation_config=primary["evaluation"],
        calibration_bootstraps=extension["calibration_bootstraps"], seed=cell["seed"],
    )
    assert_scientific_equal(cell["metrics"], json_safe(metrics), f"{job.cell_id}/metrics")
    return True


def verify_selected_refit(source: dict[str, Any], refit: dict[str, Any], identity: str) -> dict[str, str]:
    """Require exact non-timing scientific agreement for one saved deterministic refit."""
    if source["cell_id"] != identity or refit["cell_id"] != identity:
        raise ValueError(f"selected refit identity differs: {identity}")
    if source["status"] != refit["status"]:
        raise ValueError(f"selected refit outcome differs: {identity}")
    if any(attempt.get("traces") for cell in (source, refit) for attempt in cell.get("fit_attempts", [])):
        raise ValueError(f"penalised-Cox selected refit unexpectedly has traces: {identity}")
    assert_scientific_equal(scientific_content(source), scientific_content(refit), identity)
    return {"source_content_sha256": source["cell_content_sha256"],
            "refit_content_sha256": refit["cell_content_sha256"],
            "status": source["status"],
            "comparison": "non-timing scientific content equal"}


def verify_subset(
    production: Path, matched: Path | None, run: Path, reproduction: Path,
    *, strict_inventory: bool = False, diagnostic: bool = False,
) -> dict[str, Any]:
    """Audit the bounded saved subset; never fit models or complete the wider grid."""
    root = Path(__file__).resolve().parents[1]
    manifest = read_mapping(run / "manifest.json")
    verify_source_identity(production, matched, manifest)
    scope_sha256 = verify_study_scope(root, manifest, run)
    extension = read_mapping(root / "config/extensions.yaml")
    primary = read_mapping(root / "config/confirmatory.yaml")
    if (manifest["run_config"] != extension
            or sha256_file(root / "config/extensions.yaml") != manifest["input_sha256"]["config/extensions.yaml"]
            or sha256_file(root / "config/confirmatory.yaml") != manifest["input_sha256"]["config/confirmatory.yaml"]
            or sha256_file(root / "config/datasets.yaml") != manifest["input_sha256"]["config/datasets.yaml"]
            or sha256_file(root / "data/manifest.yaml") != manifest["input_sha256"]["data/manifest.yaml"]):
        raise ValueError("analysis configuration differs from the frozen fit")
    specs = read_mapping(root / "config/datasets.yaml")
    for key in COHORTS:
        name = specs[key]["raw_file"]
        if sha256_file(root / name) != manifest["input_sha256"][name]:
            raise ValueError(f"analysis clinical raw input differs from the frozen fit: {name}")
    jobs, cohorts = rebuild_clinical_jobs(root, extension)
    rebuilt = [{"cell_id": j.cell_id,
                "train_sha256": canonical_json_hash(cohorts[j.dataset].subject_id.iloc[j.train].tolist()),
                "validation_sha256": canonical_json_hash(cohorts[j.dataset].subject_id.iloc[j.validation].tolist()),
                "censoring_cutoff": j.censoring_cutoff} for j in jobs]
    if (manifest["planned_fits"] != 1625 or len(manifest["plan"]) != 1625
            or len({row["cell_id"] for row in manifest["plan"]}) != 1625):
        raise ValueError("original extension manifest grid differs from 1,625 distinct jobs")
    selected_ids = {j.cell_id for j in jobs}
    if [row for row in manifest["plan"] if row["cell_id"] in selected_ids] != rebuilt:
        raise ValueError("clinical subset plan differs from rebuilt patient memberships")
    selected = jobs
    expected = {j.cell_id for j in selected}
    present = {path.stem for path in (run / "cells").glob("*.json")}
    missing = expected - present
    if missing:
        raise ValueError(f"selected penalised-Cox cells missing: {len(missing)}")
    if strict_inventory and present != expected:
        raise ValueError("restored clinical subset cell inventory differs from 225")
    refit_ids = {j.cell_id for j in selected if j.repeat == j.fold == 1}
    if len(refit_ids) != 9:
        raise ValueError("selected penalised-Cox refit set differs from nine")
    if {path.stem for path in (reproduction / "cells").glob("*.json")} & expected != refit_ids:
        raise ValueError("selected penalised-Cox refit inventory differs from nine")
    cell_hashes: dict[str, dict[str, str]] = {}
    refits: dict[str, dict[str, str]] = {}
    original_receipts_verified = 0
    rescored = 0
    statuses: Counter[str] = Counter()
    for job in selected:
        cell_path = run / "cells" / f"{job.cell_id}.json"
        cell = verified_cell(cell_path)
        accepted = verify_stored_cell(cell, job, cohorts[job.dataset], base_seed=extension["base_seed"],
                                      primary=primary, extension=extension)
        rescored += int(accepted)
        statuses[cell["status"]] += 1
        cell_hashes[job.cell_id] = {"file_sha256": sha256_file(cell_path),
                                    "cell_content_sha256": cell["cell_content_sha256"],
                                    "status": cell["status"]}
        if job.cell_id in refit_ids:
            refit_path = reproduction / "cells" / f"{job.cell_id}.json"
            refit = verified_cell(refit_path)
            refits[job.cell_id] = verify_selected_refit(cell, refit, job.cell_id)
            refits[job.cell_id]["source_file_sha256"] = cell_hashes[job.cell_id]["file_sha256"]
            refits[job.cell_id]["refit_file_sha256"] = sha256_file(refit_path)
            receipt_path = reproduction / "receipts" / f"{job.cell_id}.json"
            if receipt_path.exists():
                receipt = read_mapping(receipt_path)
                expected_receipt = {"cell_id": job.cell_id, "status": "scientific_match",
                                    "source_content_sha256": cell["cell_content_sha256"],
                                    "refit_content_sha256": refit["cell_content_sha256"],
                                    "trace_sample_arrays": "exact; timing/NetCDF metadata excluded"}
                if receipt != expected_receipt:
                    raise ValueError(f"original selected-refit receipt differs: {job.cell_id}")
                refits[job.cell_id]["original_receipt"] = "verified"
                original_receipts_verified += 1
            else:
                refits[job.cell_id]["original_receipt"] = "missing_pending"
        if len(cell_hashes) % 25 == 0:
            print(f"clinical subset verified {len(cell_hashes)}/225 saved cells", file=sys.stderr, flush=True)
    return {"schema_version": 1, "evidence_status": "post_hoc_clinical_methods_subset",
            "verification_status": "diagnostic_uncommitted" if diagnostic else "passed",
            "verification": "225 saved cells independently identity/hash checked; accepted forecasts rescored; nine saved refits compared",
            "full_extension_grid_verified": False,
            "scope_freeze_sha256": scope_sha256,
            "source_manifest_sha256": sha256_file(run / "manifest.json"),
            "manifest_matched_sha256": manifest["matched_sha256"],
            "matched_source_file_verified": matched is not None,
            "plan_verification": "225 selected clinical rows independently rebuilt; 1625-row manifest hash pinned",
            "production_code_commit": manifest["code"]["git_commit"],
            "analysis_code_commit": git_commit(root) if diagnostic else verify_analysis_code_commit(root),
            "verifier_committed": not diagnostic,
            "verifier_sha256": sha256_file(Path(__file__)),
            "cells": cell_hashes, "selected_refits": refits,
            "verified_cells": len(cell_hashes), "rescored_cells": rescored,
            "status_counts": dict(statuses), "refits_compared": len(refits),
            "original_refit_receipts_verified": original_receipts_verified,
            "original_refit_receipts_pending": len(refits) - original_receipts_verified}


def main() -> None:
    """Write a new receipt outside every preserved source tree after verification."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("production-code", "run", "reproduction", "report"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--matched", type=Path,
                        help="optional expression-source parquet hash check, not needed for clinical folds")
    parser.add_argument("--strict-inventory", action="store_true",
                        help="require exactly 225 selected files in a restored subset tree")
    parser.add_argument("--diagnostic", action="store_true",
                        help="mark a pre-commit read-only audit as non-release diagnostic")
    args = parser.parse_args()
    report = args.report.absolute()
    if report.exists() or report.is_symlink():
        raise FileExistsError(report)
    if any(report.is_relative_to(path.resolve()) for path in
           (args.production_code, args.run, args.reproduction)):
        raise ValueError("verification report must be outside the preserved source trees")
    receipt = verify_subset(args.production_code.resolve(), args.matched.resolve() if args.matched else None,
                            args.run.resolve(), args.reproduction.resolve(),
                            strict_inventory=args.strict_inventory, diagnostic=args.diagnostic)
    report.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(report, receipt, overwrite=False)
    print(f"verified {receipt['verified_cells']} cells, rescored {receipt['rescored_cells']}, "
          f"compared {receipt['refits_compared']} selected refits; receipt: {report}")


if __name__ == "__main__":
    main()
