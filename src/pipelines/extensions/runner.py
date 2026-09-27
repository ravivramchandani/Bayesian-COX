"""Write-once extension fits bound to a separately frozen addendum and code."""

from __future__ import annotations

import json
import os
import socket
import sys
import time
import traceback
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.cohorts import load_analysis_dataset
from src.pipelines.confirmatory.evaluation import evaluate_predictions
from src.pipelines.confirmatory.options import DiagnosticFailure, deterministic_seed
from src.pipelines.extensions.fitting import (
    CATALYTIC_MODELS,
    FitExecutionFailure,
    fit_with_attempts,
    select_parameters,
)
from src.pipelines.extensions.planning import ExtensionJob, build_extension_jobs
from src.pipelines.extensions.preprocessing import ExtensionPreprocessor, generate_catalytic_data
from src.pipelines.robustness.conditions import apply_administrative_censoring
from src.utils.io import json_safe, read_mapping, write_json_atomic
from src.utils.reproducibility import build_run_manifest, canonical_json_hash, sha256_file


def load_extension_cohorts(root: Path, matched: Path) -> dict[str, pd.DataFrame]:
    """Read unchanged primary cohorts and the explicitly aligned expression cohort."""
    specs = read_mapping(root / "config/datasets.yaml")
    cohorts = {}
    for key in ("gbsg2", "whas500", "metabric"):
        raw, times, events, ids = load_analysis_dataset(root, key, specs[key])
        raw = raw.copy()
        raw["duration"], raw["event"], raw["subject_id"] = times, events, ids
        cohorts[key] = raw
    raw = pd.read_parquet(matched)
    if raw.patient_id.duplicated().any() or not np.isfinite(raw.duration).all() or np.any(raw.duration <= 0):
        raise ValueError("invalid matched patients or outcomes")
    raw["subject_id"] = raw.patient_id.astype(str)
    cohorts["metabric_matched"] = raw
    return cohorts


def verified_cell(path: Path) -> dict[str, Any]:
    """Reject changed checkpoint content before any resume reuses a cell."""
    cell = read_mapping(path)
    expected = cell["cell_content_sha256"]
    if canonical_json_hash({k: v for k, v in cell.items() if k != "cell_content_sha256"}) != expected:
        raise ValueError(f"extension checkpoint content changed: {path}")
    for attempt in cell.get("fit_attempts", []):
        for trace in attempt.get("traces", {}).values():
            trace_path = path.parent.parent / "traces" / cell["cell_id"] / trace["filename"]
            if sha256_file(trace_path) != trace["sha256"]:
                raise ValueError(f"extension trace content changed: {trace_path}")
    return cell


def run_extension_cell(
    job: ExtensionJob, raw: pd.DataFrame, feature_spec: dict[str, Any],
    primary: dict[str, Any], config: dict[str, Any], run_dir: Path,
) -> dict[str, Any]:
    """Account for one attempted fit with its memberships, failures and predictions."""
    started = time.perf_counter()
    tr, va = job.train, job.validation
    times, events = raw.duration.to_numpy(float), raw.event.to_numpy(int)
    tt, ee = apply_administrative_censoring(times[tr], events[tr], job.censoring_cutoff)
    vt, ve = apply_administrative_censoring(times[va], events[va], job.censoring_cutoff)
    seed = deterministic_seed(config["base_seed"], "extensions", job.cell_id)
    cell: dict[str, Any] = {
        "schema_version": 1, "cell_id": job.cell_id, "dataset": job.dataset,
        "setting": job.setting, "model_key": job.model, "repeat": job.repeat, "fold": job.fold,
        "condition": job.condition, "evidence_status": "post_hoc_extension",
        "seed": seed, "train_subject_ids": raw.subject_id.iloc[tr].tolist(),
        "validation_subject_ids": raw.subject_id.iloc[va].tolist(),
        "training_membership_sha256": canonical_json_hash(raw.subject_id.iloc[tr].tolist()),
        "n_train": len(tr), "n_validation": len(va), "events_train": int(ee.sum()),
        "censoring_cutoff": job.censoring_cutoff, "gene_budget": job.gene_budget,
    }
    try:
        if ee.sum() < 20:
            raise ValueError("fewer than 20 training events under frozen information-regime rule")
        training = raw.iloc[tr]
        processor = ExtensionPreprocessor(feature_spec, job.gene_budget).fit(training)
        xt, xv = processor.transform(training), processor.transform(raw.iloc[va])
        cell["preprocessing"] = processor.metadata()
        cell["p"] = xt.shape[1]
        cell["events_per_coefficient"] = float(ee.sum() / xt.shape[1])
        selected, tuning = select_parameters(job.model, training, tt, ee, feature_spec, job.gene_budget,
                                              primary=primary, config=config,
                                              seed=deterministic_seed(seed, "inner_cv"))
        cell["selected_parameters"], cell["inner_tuning"] = selected, tuning
        synthetic = None
        if job.model in CATALYTIC_MODELS:
            synthetic, cell["synthetic_prior_data"] = generate_catalytic_data(
                training, processor, tt, ee, deterministic_seed(seed, "outer_prior"))
        model, attempts = fit_with_attempts(
            job.model, selected, xt, tt, ee, synthetic, primary=primary, config=config, seed=seed,
            trace_dir=run_dir / "traces" / job.cell_id,
        )
        cell["fit_attempts"] = attempts
        cell["model_details"] = getattr(model, "details", {})
        cell["model_checks"] = {"prior_predictive": getattr(model, "prior_predictive_summary", {}),
                                 "posterior_predictive": getattr(model, "posterior_predictive_summary", {})}
        metrics, predictions = evaluate_predictions(
            model, xv, tt, ee, vt, ve, evaluation_config=primary["evaluation"],
            calibration_bootstraps=config["calibration_bootstraps"], seed=seed,
        )
        cell.update({"status": "complete", "metrics": metrics, "predictions": {
            **predictions, "subject_ids": raw.subject_id.iloc[va].tolist(),
            "observed_time": vt, "observed_event": ve,
            "training_time": tt, "training_event": ee,
        }})
    except DiagnosticFailure as exc:
        cell.update({"status": "failed_diagnostics", "fit_attempts": exc.attempts, "message": str(exc)})
    except FitExecutionFailure as exc:
        cell.update({"status": "failed", "error_type": type(exc.__cause__).__name__,
                     "fit_attempts": exc.attempts, "message": str(exc), "traceback": traceback.format_exc()})
    except Exception as exc:
        cell.update({"status": "failed", "error_type": type(exc).__name__, "message": str(exc),
                     "traceback": traceback.format_exc()})
    cell["seconds"] = time.perf_counter() - started
    cell = json_safe(cell)
    cell["cell_content_sha256"] = canonical_json_hash(cell)
    return cell


def initialize_extension_run(root: Path, matched: Path, output: Path) -> tuple[dict[str, Any], list[ExtensionJob], dict[str, pd.DataFrame]]:
    """Bind complete job coverage to frozen config, source, data and environment."""
    config = read_mapping(root / "config/extensions.yaml")
    freeze = read_mapping(root / "coordination/extension_protocol_freeze.json")
    for name, digest in freeze["sha256"].items():
        if sha256_file(root / name) != digest:
            raise ValueError(f"extension addendum changed after freeze: {name}")
    if canonical_json_hash({k: v for k, v in freeze.items() if k != "content_sha256"}) != freeze["content_sha256"]:
        raise ValueError("extension freeze content changed")
    cohorts = load_extension_cohorts(root, matched)
    jobs = build_extension_jobs(cohorts, config)
    inputs = [str(p.relative_to(root)) for p in sorted((root / "src").rglob("*.py"))]
    inputs += [str(p.relative_to(root)) for p in sorted((root / "scripts").glob("*.py"))]
    inputs += ["config/extensions.yaml", "config/confirmatory.yaml", "config/datasets.yaml",
               "data/manifest.yaml", "conda-lock.yml", "coordination/extension_protocol_freeze.json"]
    inputs += [read_mapping(root / "config/datasets.yaml")[k]["raw_file"] for k in ("gbsg2", "whas500", "metabric")]
    plan = [{"cell_id": j.cell_id, "train_sha256": canonical_json_hash(cohorts[j.dataset].subject_id.iloc[j.train].tolist()),
             "validation_sha256": canonical_json_hash(cohorts[j.dataset].subject_id.iloc[j.validation].tolist()),
             "censoring_cutoff": j.censoring_cutoff} for j in jobs]
    manifest = build_run_manifest(root, command=[sys.executable, "scripts/run_extensions.py"],
                                  seeds={"base": config["base_seed"]}, input_files=inputs, run_config=config)
    if manifest["code"]["git_dirty"]:
        raise RuntimeError("extension production requires committed clean sealed code")
    manifest.update({"matched_sha256": sha256_file(matched), "freeze_sha256": freeze["content_sha256"],
                     "planned_fits": len(jobs), "plan": plan, "evidence_status": "post_hoc_extension"})
    manifest["manifest_content_sha256"] = canonical_json_hash({k: v for k, v in manifest.items() if k != "manifest_content_sha256"})
    output.mkdir(parents=True, exist_ok=True)
    path = output / "manifest.json"
    if path.exists():
        old = read_mapping(path)
        if old != manifest:
            raise ValueError("extension run inputs/code/plan/environment changed; do not combine checkpoints")
    else:
        lock_path = output / "manifest.claim"
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            deadline = time.monotonic() + 60
            while not path.exists() and time.monotonic() < deadline:
                time.sleep(0.1)
            if not path.exists() or read_mapping(path) != manifest:
                raise RuntimeError("manifest creation claim did not complete with identical inputs") from None
        else:
            os.close(descriptor)
            try:
                if path.exists():
                    if read_mapping(path) != manifest:
                        raise ValueError("concurrent manifest differs")
                else:
                    write_json_atomic(path, manifest, overwrite=False)
            finally:
                lock_path.unlink()
    return config, jobs, cohorts


def execute_extension_worker(root: Path, matched: Path, output: Path, worker: int, workers: int) -> None:
    """Execute a deterministic disjoint shard with exclusive per-cell claims."""
    if not 0 <= worker < workers:
        raise ValueError("invalid worker index/count")
    config, jobs, cohorts = initialize_extension_run(root, matched, output)
    primary, datasets = read_mapping(root / "config/confirmatory.yaml"), read_mapping(root / "config/datasets.yaml")
    claims = output / "claims"
    claims.mkdir(exist_ok=True)
    for index, job in enumerate(jobs):
        if index % workers != worker:
            continue
        path = output / "cells" / f"{job.cell_id}.json"
        if path.exists():
            cell = verified_cell(path)
            if cell["cell_id"] != job.cell_id:
                raise ValueError("checkpoint identity differs from planned job")
            continue
        claim = claims / f"{job.cell_id}.json"
        descriptor = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump({"pid": os.getpid(), "host": socket.gethostname(), "cell_id": job.cell_id}, handle)
        try:
            key = "metabric" if job.dataset == "metabric_matched" else job.dataset
            cell = run_extension_cell(job, cohorts[job.dataset], datasets[key]["primary_features"], primary, config, output)
            write_json_atomic(path, cell, overwrite=False)
            print(job.cell_id, cell["status"], round(cell["seconds"], 2), flush=True)
        finally:
            claim.unlink()
