"""Fail-closed checks for the bounded clinical methods evidence verifier."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from scripts import verify_clinical_methods_subset as subset
from src.pipelines.confirmatory.evaluation import evaluation_horizons_and_grid
from src.pipelines.confirmatory.options import deterministic_seed
from src.utils.reproducibility import canonical_json_hash, sha256_file


def test_source_identity_rejects_changed_manifest_and_production_input(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A subset cannot use a changed source even when its selected cells are intact."""
    producer = tmp_path / "producer"
    freeze_path = producer / "coordination/extension_protocol_freeze.json"
    freeze_path.parent.mkdir(parents=True)
    input_path = producer / "config/extensions.yaml"
    input_path.parent.mkdir(parents=True)
    input_path.write_text("frozen config\n")
    protocol_path = producer / "docs/protocol_addendum_extensions.md"
    protocol_path.parent.mkdir(parents=True)
    protocol_path.write_text("frozen protocol\n")
    freeze = {"sha256": {"docs/protocol_addendum_extensions.md": sha256_file(protocol_path)}}
    freeze["content_sha256"] = canonical_json_hash(freeze)
    freeze_path.write_text(json.dumps(freeze))
    matched = tmp_path / "matched.parquet"
    matched.write_bytes(b"matched patients")
    manifest = {"code": {"git_commit": "fixed", "git_dirty": False, "git_changed_paths": []},
                "matched_sha256": sha256_file(matched),
                "input_sha256": {"config/extensions.yaml": sha256_file(input_path)},
                "freeze_sha256": freeze["content_sha256"]}
    manifest["manifest_content_sha256"] = canonical_json_hash(manifest)
    monkeypatch.setattr(subset, "git_commit", lambda _root: "fixed")
    subset.verify_source_identity(producer, matched, manifest)
    input_path.write_text("changed config\n")
    with pytest.raises(ValueError, match="production input"):
        subset.verify_source_identity(producer, matched, manifest)
    input_path.write_text("frozen config\n")
    manifest["code"]["git_dirty"] = True
    with pytest.raises(ValueError, match="manifest content"):
        subset.verify_source_identity(producer, matched, manifest)


def test_study_scope_requires_pinned_roster_and_source(tmp_path: Path) -> None:
    """A post-hoc subset cannot silently switch its original run or model roster."""
    root = tmp_path / "analysis"
    coordination = root / "coordination"
    coordination.mkdir(parents=True)
    addendum = root / "docs/protocol_addendum_clinical_methods.md"
    addendum.parent.mkdir(parents=True)
    addendum.write_text("frozen focus\n")
    roster_path = coordination / "clinical_methods_roster.json"
    roster = {"datasets": list(subset.COHORTS), "penalised_models": list(subset.MODELS),
              "repeats": list(range(1, 6)), "folds": list(range(1, 6)),
              "condition": "full", "setting": "clinical", "source_cell_count": 225,
              "selected_reproduction": "all nine penalised-model by cohort cells at repeat 1 fold 1"}
    roster_path.write_text(json.dumps(roster))
    run = tmp_path / "run"
    run.mkdir()
    manifest_path = run / "manifest.json"
    manifest_path.write_text("frozen manifest\n")
    scope_path = coordination / "clinical_methods_scope_freeze.json"
    scope = {"classification": "post-hoc outcome-aware subset; not result-blind preregistration",
             "source_extension_manifest_sha256": sha256_file(manifest_path),
             "source_fit_commit": "fixed", "source_penalised_cells": 225,
             "reference_bayesian_cells": 225, "primary_contrasts": 27,
             "selected_existing_refits_to_verify": 9,
             "baseline_source_pins": "coordination/extension_sources/baseline_sources.json",
             "sha256": {"coordination/clinical_methods_roster.json": sha256_file(roster_path),
                        "docs/protocol_addendum_clinical_methods.md": sha256_file(addendum)}}
    baseline = coordination / "extension_sources/baseline_sources.json"
    baseline.parent.mkdir()
    baseline.write_text("pinned baseline source\n")
    original_freeze = coordination / "extension_protocol_freeze.json"
    original_freeze.write_text("pinned original freeze\n")
    scope["baseline_source_pins_sha256"] = sha256_file(baseline)
    scope["original_extension_freeze_record_sha256"] = sha256_file(original_freeze)
    scope_path.write_text(json.dumps(scope))
    assert subset.verify_study_scope(root, {"code": {"git_commit": "fixed"}}, run) == sha256_file(scope_path)
    roster_path.write_text(json.dumps({**roster, "datasets": ["gbsg2"]}))
    with pytest.raises(ValueError, match="scope input changed"):
        subset.verify_study_scope(root, {"code": {"git_commit": "fixed"}}, run)
    roster_path.write_text(json.dumps(roster))
    manifest_path.write_text("other source\n")
    with pytest.raises(ValueError, match="scope differs"):
        subset.verify_study_scope(root, {"code": {"git_commit": "fixed"}}, run)


def test_selection_requires_all_nine_model_cohort_blocks_and_25_folds() -> None:
    """The subset gate rejects a missing or duplicated outer position."""
    jobs = [SimpleNamespace(dataset=cohort, model=model, setting="clinical", condition="full",
                            repeat=repeat, fold=fold, censoring_cutoff=None, gene_budget=0)
            for cohort in subset.COHORTS for model in subset.MODELS
            for repeat, fold in sorted(subset.FOLDS)]
    jobs.append(SimpleNamespace(dataset="metabric_matched", model="ridge", setting="expression",
                                condition="full", repeat=1, fold=1, censoring_cutoff=None, gene_budget=100))
    assert len(subset.clinical_jobs(jobs)) == 225
    with pytest.raises(ValueError, match="225-cell"):
        subset.clinical_jobs(jobs[1:])
    duplicate = jobs.copy()
    duplicate[1] = jobs[0]
    with pytest.raises(ValueError, match="fold coverage"):
        subset.clinical_jobs(duplicate)


def _cell_fixture() -> tuple[dict, SimpleNamespace, pd.DataFrame, dict, dict]:
    raw = pd.DataFrame({"subject_id": [f"p{i}" for i in range(50)],
                        "duration": np.arange(1, 51, dtype=float),
                        "event": np.ones(50, dtype=int)})
    train, validation = np.arange(40), np.arange(40, 50)
    job = SimpleNamespace(cell_id="gbsg2__clinical__r01f01__ridge__full", dataset="gbsg2",
                          model="ridge", setting="clinical", condition="full", repeat=1, fold=1,
                          train=train, validation=validation, censoring_cutoff=None, gene_budget=0)
    primary = {"evaluation": {"horizon_event_quantiles": [0.25, 0.5, 0.75],
                              "minimum_censoring_survival": 0.1, "ibs_grid_points": 5}}
    extension = {"calibration_bootstraps": 5}
    horizons, grid = evaluation_horizons_and_grid(raw.duration.iloc[train].to_numpy(),
                                                  raw.event.iloc[train].to_numpy(), primary["evaluation"])
    predictions = {"subject_ids": raw.subject_id.iloc[validation].tolist(),
                   "training_time": raw.duration.iloc[train].tolist(),
                   "training_event": raw.event.iloc[train].tolist(),
                   "observed_time": raw.duration.iloc[validation].tolist(),
                   "observed_event": raw.event.iloc[validation].tolist(),
                   "horizons": horizons.tolist(), "ibs_grid": grid.tolist(),
                   "risk": list(np.arange(10, dtype=float)),
                   "survival_at_horizons": np.tile([0.8, 0.6, 0.4], (10, 1)).tolist(),
                   "survival_on_ibs_grid": np.tile(np.linspace(0.8, 0.4, 5), (10, 1)).tolist()}
    cell = {"cell_id": job.cell_id, "dataset": job.dataset, "model_key": job.model,
            "repeat": 1, "fold": 1, "setting": "clinical", "condition": "full",
            "gene_budget": 0, "censoring_cutoff": None, "n_train": 40, "n_validation": 10,
            "train_subject_ids": raw.subject_id.iloc[train].tolist(),
            "validation_subject_ids": raw.subject_id.iloc[validation].tolist(),
            "training_membership_sha256": canonical_json_hash(raw.subject_id.iloc[train].tolist()),
            "seed": deterministic_seed(123, "extensions", job.cell_id),
            "evidence_status": "post_hoc_extension", "status": "complete", "events_train": 40,
            "predictions": predictions, "metrics": {"ibs": 0.25}}
    return cell, job, raw, primary, extension


def test_one_cell_rechecks_membership_forecasts_and_recomputed_metrics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Outcome, saved forecast and independent metric discrepancies are rejected."""
    cell, job, raw, primary, extension = _cell_fixture()
    calls = []

    def score(*args, **kwargs):
        calls.append((args, kwargs))
        return {"ibs": 0.25}, {}

    monkeypatch.setattr(subset, "evaluate_predictions", score)
    subset.verify_stored_cell(cell, job, raw, base_seed=123, primary=primary, extension=extension)
    assert len(calls) == 1 and calls[0][1]["seed"] == cell["seed"]
    changed = {**cell, "metrics": {"ibs": 0.30}}
    with pytest.raises(ValueError, match="metrics"):
        subset.verify_stored_cell(changed, job, raw, base_seed=123, primary=primary, extension=extension)
    changed = {**cell, "predictions": {**cell["predictions"], "observed_time": [1] * 10}}
    with pytest.raises(ValueError, match="stored outcome"):
        subset.verify_stored_cell(changed, job, raw, base_seed=123, primary=primary, extension=extension)
    changed = {**cell, "predictions": {**cell["predictions"], "risk": [float("nan")] * 10}}
    with pytest.raises(ValueError, match="invalid saved risk"):
        subset.verify_stored_cell(changed, job, raw, base_seed=123, primary=primary, extension=extension)
    changed = {**cell, "train_subject_ids": list(reversed(cell["train_subject_ids"]))}
    with pytest.raises(ValueError, match="identity/membership"):
        subset.verify_stored_cell(changed, job, raw, base_seed=123, primary=primary, extension=extension)


def test_failed_cell_keeps_denominator_without_claiming_a_score() -> None:
    """A saved failure is verified as an outcome, never silently dropped or rescored."""
    cell, job, raw, primary, extension = _cell_fixture()
    failed = {key: value for key, value in cell.items() if key not in {"predictions", "metrics"}}
    failed["status"] = "failed"
    failed["message"] = "documented fitting error"
    assert not subset.verify_stored_cell(failed, job, raw, base_seed=123,
                                         primary=primary, extension=extension)
    with pytest.raises(ValueError, match="accepted forecasts"):
        subset.verify_stored_cell({**failed, "predictions": cell["predictions"]}, job, raw,
                                  base_seed=123, primary=primary, extension=extension)


def test_selected_refit_allows_timing_only_and_rejects_scientific_change() -> None:
    """A saved refit cannot silently differ in selected tuning or predictions."""
    source = {"cell_id": "id", "status": "complete", "selected_parameters": {"penalty": 0.1},
              "predictions": {"risk": [1.0, 2.0]}, "fit_attempts": [{"traces": {}}],
              "seconds": 12, "cell_content_sha256": "a" * 64}
    refit = {**source, "seconds": 13, "cell_content_sha256": "b" * 64}
    assert subset.verify_selected_refit(source, refit, "id")["comparison"] == "non-timing scientific content equal"
    with pytest.raises(ValueError, match="scientific number"):
        subset.verify_selected_refit(source, {**refit, "predictions": {"risk": [1.0, 3.0]}}, "id")
