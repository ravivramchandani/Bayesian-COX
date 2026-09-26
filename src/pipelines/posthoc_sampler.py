"""Separate, checkpointed horseshoe sampler sensitivity prescribed by ADR-032.

All 75 original horseshoe folds are refitted. Only target acceptance changes,
to 0.999 on every attempt; the original folds, seeds, likelihood, priors and
diagnostic gate are retained. These outputs never replace confirmatory cells.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import yaml

from src.data.survival_folds import repeated_survival_folds
from src.pipelines import confirmatory
from src.utils.frozen_evidence import verify_frozen_evidence
from src.utils.io import json_safe, write_json_atomic
from src.utils.reproducibility import build_run_manifest, canonical_json_hash, sha256_file

TARGET_ACCEPT = 0.999
EVIDENCE_STATUS = "posthoc_sampler_sensitivity"


def sensitivity_protocol(original: dict[str, Any]) -> dict[str, Any]:
    """Copy the frozen protocol and change only acceptance on the remedy ladder."""
    protocol = copy.deepcopy(original)
    bayesian = protocol["models"]["bayesian_cox"]
    bayesian["priors"]["horseshoe"]["target_accept"] = TARGET_ACCEPT
    bayesian["failed_fit_rule"]["refit_target_accept"] = TARGET_ACCEPT
    return protocol


def _options(settings: dict[str, Any], output: Path) -> confirmatory.RunOptions:
    """Keep internal confirmatory fitting controls to retain the remedy ladder."""
    return confirmatory.RunOptions(
        mode="confirmatory",
        datasets=tuple(settings["datasets"]),
        models=tuple(settings["models"]),
        outer_splits=settings["outer_splits"],
        outer_repeats=settings["outer_repeats"],
        fold_limit_per_dataset=settings["fold_limit_per_dataset"],
        bayes_draws=settings["bayes_draws"],
        bayes_tune=settings["bayes_tune"],
        bayes_chains=settings["bayes_chains"],
        calibration_bootstraps=settings["calibration_bootstraps"],
        resume=True,
        output_root=output,
    )


def _cell_path(run_dir: Path, key: tuple[str, int, int]) -> Path:
    dataset, repeat, fold = key
    return (
        run_dir
        / "cells"
        / dataset
        / f"repeat_{repeat:02d}_fold_{fold:02d}"
        / "bayesian_horseshoe.json"
    )


def _fit_one(project_root: Path, source_dir: Path, key: tuple[str, int, int]) -> dict[str, Any]:
    """Refit an original fold and relabel the serialised cell as post-hoc."""
    source = json.loads((source_dir / "manifest.json").read_text())
    settings = source["run_config"]
    original = settings["protocol"]
    protocol = sensitivity_protocol(original)
    options = _options(settings, source_dir.parent)
    cohorts = yaml.safe_load((project_root / "config/datasets.yaml").read_text())
    dataset, repeat, number = key
    cohort = cohorts[dataset]
    raw, times, events, subjects = confirmatory.load_analysis_dataset(project_root, dataset, cohort)
    folds = repeated_survival_folds(
        times,
        events,
        n_splits=options.outer_splits,
        n_repeats=options.outer_repeats,
        base_seed=int(original["validation"]["base_seed"]),
        max_time_bins=int(original["validation"]["followup_time_bins"]),
    )
    fold = next(item for item in folds if item.repeat == repeat and item.fold == number)
    stored_path = _cell_path(source_dir, key)
    stored = json.loads(stored_path.read_text())
    if list(subjects[fold.train_indices]) != stored["train_subject_ids"]:
        raise RuntimeError(f"post-hoc training fold differs from source: {key}")
    if list(subjects[fold.validation_indices]) != stored["validation_subject_ids"]:
        raise RuntimeError(f"post-hoc validation fold differs from source: {key}")
    data_hash = sha256_file(project_root / cohort["raw_file"])
    if data_hash != source["input_sha256"][cohort["raw_file"]]:
        raise RuntimeError(f"post-hoc raw cohort differs from source: {dataset}")
    cell = confirmatory.run_cell(
        dataset,
        "bayesian_horseshoe",
        fold,
        raw,
        times,
        events,
        subjects,
        confirmatory._feature_spec(cohort, protocol["feature_set"]),
        config=protocol,
        options=options,
        data_sha256=data_hash,
    )
    if cell["cell_seed"] != stored["cell_seed"]:
        raise RuntimeError(f"post-hoc cell seed differs from source: {key}")
    if any(attempt["target_accept"] != TARGET_ACCEPT for attempt in cell.get("fit_attempts", [])):
        raise RuntimeError(f"post-hoc acceptance differs from declared sensitivity: {key}")
    cell["analysis_mode"] = EVIDENCE_STATUS
    cell["evidence_status"] = EVIDENCE_STATUS
    cell["source_confirmatory_cell_sha256"] = sha256_file(stored_path)
    cell["sampler_sensitivity"] = {"target_accept": TARGET_ACCEPT, "scope": "all_horseshoe_folds"}
    cell.pop("cell_content_sha256")
    cell = json_safe(cell)
    cell["cell_content_sha256"] = canonical_json_hash(cell)
    return cell


def _verify_saved_cell(path: Path, source_dir: Path, key: tuple[str, int, int]) -> dict[str, Any]:
    """Reject corrupt or incorrectly labelled resume cells."""
    cell = json.loads(path.read_text())
    content = dict(cell)
    digest = content.pop("cell_content_sha256", None)
    if digest != canonical_json_hash(content):
        raise RuntimeError(f"post-hoc cell content hash is invalid: {path}")
    if (
        cell.get("analysis_mode") != EVIDENCE_STATUS
        or cell.get("evidence_status") != EVIDENCE_STATUS
    ):
        raise RuntimeError(f"post-hoc cell evidence label is invalid: {path}")
    if (cell.get("dataset"), cell.get("repeat"), cell.get("fold")) != key:
        raise RuntimeError(f"post-hoc cell fold key is invalid: {path}")
    if cell.get("model_key") != "bayesian_horseshoe":
        raise RuntimeError(f"post-hoc cell model is invalid: {path}")
    if cell.get("source_confirmatory_cell_sha256") != sha256_file(_cell_path(source_dir, key)):
        raise RuntimeError(f"post-hoc source cell hash differs: {path}")
    if cell.get("sampler_sensitivity", {}).get("target_accept") != TARGET_ACCEPT:
        raise RuntimeError(f"post-hoc target acceptance differs: {path}")
    if any(
        attempt.get("target_accept") != TARGET_ACCEPT for attempt in cell.get("fit_attempts", [])
    ):
        raise RuntimeError(f"post-hoc attempt acceptance differs: {path}")
    return cell


def execute_sampler_sensitivity(
    project_root: Path,
    source_dir: Path,
    output_root: Path,
    *,
    workers: int = 1,
    resume: bool = False,
) -> Path:
    """Run all 75 post-hoc refits and write explicitly labelled paired inference."""
    from scripts.render_confirmatory import verify_frozen_run

    if workers < 1:
        raise ValueError("workers must be positive")
    source = verify_frozen_run(source_dir)
    if source.mode != "confirmatory":
        raise ValueError("sampler sensitivity requires a confirmatory source")
    freeze = verify_frozen_evidence(project_root, source.manifest["input_sha256"])
    settings = source.manifest["run_config"]
    keys = sorted(
        (cell["dataset"], cell["repeat"], cell["fold"])
        for _, cell in source.cells
        if cell["model_key"] == "bayesian_horseshoe"
    )
    if len(keys) != 75 or len(set(keys)) != 75:
        raise RuntimeError("sampler sensitivity requires all 75 original horseshoe cells")
    configuration = {
        "analysis_mode": EVIDENCE_STATUS,
        "decision": "ADR-032",
        "target_accept_every_attempt": TARGET_ACCEPT,
        "source_manifest_sha256": sha256_file(source.run_dir / "manifest.json"),
        "source_completion_sha256": sha256_file(source.run_dir / "completion.json"),
        "protocol_freeze_sha256": freeze["freeze_content_sha256"],
        "source_protocol": settings["protocol"],
        "sensitivity_protocol": sensitivity_protocol(settings["protocol"]),
        "planned_keys": keys,
    }
    run_dir = output_root / f"horseshoe_ta0999_posthoc_{canonical_json_hash(configuration)[:12]}"
    if run_dir.resolve() == source.run_dir or source.run_dir in run_dir.resolve().parents:
        raise ValueError("post-hoc output must be outside the immutable source run")
    inputs = sorted(
        {str(path.relative_to(project_root)) for path in project_root.glob("src/**/*.py")}
        | set(source.manifest["input_sha256"]) - {"src/pipelines/confirmatory.py"}
    )
    inputs = [name for name in inputs if (project_root / name).is_file()]
    inputs.append("scripts/run_horseshoe_sampler_sensitivity.py")
    manifest = build_run_manifest(
        project_root,
        command=["run_horseshoe_sampler_sensitivity"],
        seeds={"outer_base": int(settings["protocol"]["validation"]["base_seed"])},
        input_files=inputs,
        run_config=configuration,
    )
    path = run_dir / "manifest.json"
    if path.exists():
        if not resume:
            raise FileExistsError(f"post-hoc run exists: {run_dir}; use --resume")
        recorded = json.loads(path.read_text())
        if (
            recorded["config_sha256"] != manifest["config_sha256"]
            or recorded["input_sha256"] != manifest["input_sha256"]
        ):
            raise RuntimeError("post-hoc code or inputs changed after the first checkpoint")
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
        write_json_atomic(path, manifest, overwrite=False)
    pending = []
    for key in keys:
        target = _cell_path(run_dir, key)
        if target.exists():
            _verify_saved_cell(target, source.run_dir, key)
        else:
            pending.append(key)
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_fit_one, project_root, source.run_dir, key): key for key in pending}
        for future in as_completed(futures):
            key = futures[future]
            cell = future.result()
            write_json_atomic(_cell_path(run_dir, key), cell, overwrite=False)
            print(
                f"posthoc {key} status={cell['status']} seconds={cell['total_seconds']:.1f}",
                flush=True,
            )
    verify_frozen_evidence(project_root, source.manifest["input_sha256"])
    for name, digest in manifest["input_sha256"].items():
        if sha256_file(project_root / name) != digest:
            raise RuntimeError(f"post-hoc runtime input changed: {name}")
    refits = [_verify_saved_cell(_cell_path(run_dir, key), source.run_dir, key) for key in keys]
    if {str(p.relative_to(run_dir)) for p in (run_dir / "cells").glob("*/*/*.json")} != {
        str(_cell_path(run_dir, key).relative_to(run_dir)) for key in keys
    }:
        raise RuntimeError("post-hoc run has an unexpected cell inventory")
    mixed = [cell for _, cell in source.cells if cell["model_key"] != "bayesian_horseshoe"] + refits
    inference = confirmatory._repeated_cv_inference(
        mixed, _options(settings, output_root), settings["protocol"]
    )
    inference["evidence_status"] = EVIDENCE_STATUS
    inference["source_policy"] = (
        "all 75 horseshoe refits; all other cells unchanged from confirmatory source"
    )
    inference["confirmatory_outcome_replaced"] = False
    inference["result_content_sha256"] = canonical_json_hash(inference)
    write_json_atomic(run_dir / "inference.json", inference)
    completion = {
        "analysis_mode": EVIDENCE_STATUS,
        "planned_cells": 75,
        "stored_cells": len(refits),
        "status_counts": dict(Counter(cell["status"] for cell in refits)),
        "cell_sha256": {
            str(_cell_path(run_dir, key).relative_to(run_dir)): sha256_file(
                _cell_path(run_dir, key)
            )
            for key in keys
        },
        "aggregate_sha256": {"inference.json": sha256_file(run_dir / "inference.json")},
        "source_completion_sha256": sha256_file(source.run_dir / "completion.json"),
    }
    completion["completion_content_sha256"] = canonical_json_hash(completion)
    write_json_atomic(run_dir / "completion.json", completion)
    return run_dir
