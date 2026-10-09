"""Focused checks for the frozen RSF surrogate protocol and evidence writer."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.run_rsf_surrogate import (
    _sha256,
    _sha256_text,
    _verify_pilot_run,
    _verify_protocol_and_review,
)
from src.pipelines import rsf_surrogate as surrogate_pipeline
from src.pipelines.rsf_surrogate import (
    PROTOCOL_SHA256,
    average_repeated_fold_percentiles,
    bootstrap_seed,
    feature_group_stability,
    fit_and_evaluate_surrogate_fold,
    fit_surrogate_tree,
    score_surrogate_fold,
    summarize_subject_predictions,
    surrogate_seed,
    tree_diagnostics,
    validate_owner_waiver_receipt,
    validate_review_receipt,
    verify_surrogate_run,
    verify_teacher_replay,
)
from src.utils.reproducibility import canonical_json_hash, sha256_file


def test_surrogate_fit_is_deterministic_and_training_only() -> None:
    rng = np.random.default_rng(414)
    features = pd.DataFrame(rng.normal(size=(90, 3)), columns=["age", "score", "noise"])
    teacher = 2.0 * features["score"].to_numpy() - features["age"].to_numpy()

    first = fit_surrogate_tree(features, teacher, seed=47047)
    second = fit_surrogate_tree(features, teacher, seed=47047)

    assert first.selection == second.selection
    np.testing.assert_array_equal(first.estimator.predict(features), second.estimator.predict(features))
    assert first.selection["training_rows"] == 90
    assert first.selection["selected_candidate"]["max_depth"] in {1, 2, 3, 4}
    assert first.selection["selected_candidate"]["min_samples_leaf"] in {0.05, 0.10, 0.20}


def test_outer_validation_values_cannot_change_tree_selection() -> None:
    rng = np.random.default_rng(515)
    train = pd.DataFrame(rng.normal(size=(60, 2)), columns=["x", "z"])
    teacher_train = train["x"].to_numpy() - train["z"].to_numpy()
    validation = pd.DataFrame(rng.normal(size=(12, 2)), columns=["x", "z"])
    time_values = np.arange(1, 13, dtype=float)
    events = np.tile([1, 0], 6)
    common = {
        "seed": 47047,
        "feature_groups": {"x": "x", "z": "z"},
        "preprocessing": {"feature_spec": {"engineered": []}, "scaling": {}},
    }
    first = fit_and_evaluate_surrogate_fold(
        train,
        teacher_train,
        validation,
        validation["x"].to_numpy() - validation["z"].to_numpy(),
        time_values,
        events,
        **common,
    )
    changed_validation = validation + 1000.0
    second = fit_and_evaluate_surrogate_fold(
        train,
        teacher_train,
        changed_validation,
        np.arange(12, dtype=float)[::-1],
        time_values,
        events,
        **common,
    )

    assert first["fit"].selection == second["fit"].selection
    np.testing.assert_array_equal(
        first["fit"].estimator.predict(train), second["fit"].estimator.predict(train)
    )
    assert first["metrics"]["fidelity"] != second["metrics"]["fidelity"]


def test_replay_requires_exact_subject_order_and_frozen_tolerance() -> None:
    expected = [0.2, 0.4, 0.8]
    result = verify_teacher_replay(expected, [0.2, 0.4, 0.8 + 1e-13], ["a", "b", "c"], ["a", "b", "c"])

    assert result["subject_order_match"] is True
    assert result["n_validation"] == 3
    with pytest.raises(ValueError, match="subject order"):
        verify_teacher_replay(expected, expected, ["a", "b", "c"], ["b", "a", "c"])
    with pytest.raises(ValueError, match="risk differs"):
        verify_teacher_replay(expected, [0.2, 0.41, 0.8], ["a", "b", "c"], ["a", "b", "c"])


def _two_repeat_records() -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    fold_subjects = {1: ["s1", "s2"], 2: ["s3", "s4"]}
    for repeat in (1, 2):
        for fold, ids in fold_subjects.items():
            offset = repeat * 0.01
            records.append(
                {
                    "repeat": repeat,
                    "fold": fold,
                    "predictions": {
                        "subject_ids": ids,
                        "teacher_risk": [1.0 + offset, 4.0 + offset] if fold == 1 else [2.0 + offset, 3.0 + offset],
                        "student_risk": [1.1 + offset, 3.9 + offset] if fold == 1 else [2.1 + offset, 2.9 + offset],
                        "observed_time": [10.0, 20.0] if fold == 1 else [30.0, 40.0],
                        "observed_event": [1, 0] if fold == 1 else [1, 0],
                    },
                }
            )
    return records


def test_subject_averages_require_each_subject_in_each_repeat() -> None:
    records = _two_repeat_records()
    result = average_repeated_fold_percentiles(
        records, ["s1", "s2", "s3", "s4"], n_repeats=2, n_folds=2
    )

    assert result["n_repeats"] == 2
    assert result["teacher_percentiles"].shape == (4,)
    assert result["observed_event"].tolist() == [1, 0, 1, 0]
    with pytest.raises(ValueError, match="complete repeated outer-fold grid"):
        average_repeated_fold_percentiles(records[:-1], ["s1", "s2", "s3", "s4"], n_repeats=2, n_folds=2)


def test_survival_metrics_and_subject_bootstrap_are_deterministic() -> None:
    teacher = np.array([0.1, 0.3, 0.6, 0.9, 0.2, 0.7])
    student = np.array([0.12, 0.31, 0.58, 0.85, 0.25, 0.69])
    times = np.array([1, 2, 3, 4, 5, 6], dtype=float)
    events = np.array([1, 1, 0, 1, 0, 1])
    first = score_surrogate_fold(teacher, student, times, events)
    second = score_surrogate_fold(teacher, student, times, events)
    assert first == second
    assert first["survival_performance"]["teacher"]["estimate"] is not None
    first_summary = summarize_subject_predictions(
        np.linspace(0.05, 0.95, 6),
        np.linspace(0.08, 0.92, 6),
        times,
        events,
        seed=147047,
        bootstrap_replicates=30,
    )
    second_summary = summarize_subject_predictions(
        np.linspace(0.05, 0.95, 6),
        np.linspace(0.08, 0.92, 6),
        times,
        events,
        seed=147047,
        bootstrap_replicates=30,
    )
    assert first_summary == second_summary
    assert first_summary["uncertainty"]["intervals"]["fidelity_spearman"]["successful_replicates"] == 30


def test_tree_diagnostics_and_group_use_keep_full_planned_denominator() -> None:
    features = pd.DataFrame({"x": np.arange(50, dtype=float), "z": np.tile([0.0, 1.0], 25)})
    teacher = features["x"].to_numpy() + features["z"].to_numpy()
    fitted = fit_surrogate_tree(features, teacher, seed=47047)
    diagnostics = tree_diagnostics(
        fitted.estimator,
        list(features.columns),
        {"x": "clinical_x", "z": "clinical_z"},
        {"feature_spec": {"engineered": []}, "scaling": {}},
    )
    records = [
        {"status": "complete", "tree_diagnostics": diagnostics},
        {"status": "student_fit_failed"},
    ]
    stability = feature_group_stability(
        records, planned_cells=25, candidate_groups=["clinical_x", "clinical_z", "unused"]
    )

    assert sum(diagnostics["feature_group_importance"].values()) == pytest.approx(1.0)
    assert stability["planned_cell_denominator"] == 25
    assert stability["feature_groups"]["unused"]["fold_use_count"] == 0


def test_frozen_seed_formulas_and_independent_review_receipt() -> None:
    assert surrogate_seed(0, 1, 1) == 47047
    assert surrogate_seed(2, 5, 5) == 251087
    assert bootstrap_seed(2) == 147049
    receipt = {
        "reviewer_name": "Independent Reviewer",
        "reviewer_affiliation": "Research institute",
        "reviewer_role": "independent scientific reviewer",
        "reviewed_at_utc": "2026-10-07T12:00:00Z",
        "decision": "accepted",
        "protocol_sha256": PROTOCOL_SHA256,
    }
    validate_review_receipt(receipt)
    with pytest.raises(ValueError, match="requires an accepted"):
        validate_review_receipt({**receipt, "decision": "pending"})


def test_owner_waiver_is_separate_from_independent_review(tmp_path: Path) -> None:
    receipt = {
        "receipt_type": "owner_gate_waiver",
        "owner_role": "project owner",
        "instruction_date": "2026-10-07",
        "receipt_recorded_at_utc": "2026-10-07T10:08:13Z",
        "decision": "proceed_under_owner_waiver",
        "protocol_sha256": PROTOCOL_SHA256,
        "authorization_context": "Owner instructed execution after Q-008 was disclosed as pending.",
        "scope": ["T-193", "T-194 Windows pilot and budget-qualified production"],
        "independent_review_obtained": False,
    }
    validate_owner_waiver_receipt(receipt)
    receipt_path = tmp_path / "owner-waiver.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    verified, receipt_sha256 = _verify_protocol_and_review(receipt_path)
    assert verified["receipt_type"] == "owner_gate_waiver"
    assert verified["independent_review_obtained"] is False
    assert len(receipt_sha256) == 64
    with pytest.raises(ValueError, match="must not claim independent review"):
        validate_owner_waiver_receipt({**receipt, "independent_review_obtained": True})


def _write_hashed_json(path: Path, record: dict[str, object], field: str) -> None:
    record[field] = canonical_json_hash(record)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, sort_keys=True) + "\n", encoding="utf-8")


def test_run_verifier_checks_full_inventory_and_cell_hashes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    identity = "a" * 64
    manifest: dict[str, object] = {
        "analysis": "posthoc_rsf_surrogate_v1",
        "run_type": "production",
        "protocol_sha256": PROTOCOL_SHA256,
        "run_identity_sha256": identity,
        "pilot_completion_sha256": "b" * 64,
        "source_release": {"manifest_sha256": "d" * 64, "completion_sha256": "c" * 64},
    }
    _write_hashed_json(run_dir / "manifest.json", manifest, "manifest_content_sha256")
    inventory: dict[str, str] = {}
    statuses = {"source_cell_absent": 75}
    for cohort in ("gbsg2", "whas500", "metabric"):
        for repeat in range(1, 6):
            for fold in range(1, 6):
                relative = f"cells/{cohort}/r{repeat:02d}f{fold:02d}.json"
                cell: dict[str, object] = {
                    "dataset": cohort,
                    "repeat": repeat,
                    "fold": fold,
                    "run_identity_sha256": identity,
                    "status": "source_cell_absent",
                }
                _write_hashed_json(run_dir / relative, cell, "cell_content_sha256")
                inventory[relative] = sha256_file(run_dir / relative)
    summaries = {
        cohort: {
            "planned_cells": 25,
            "status_counts": {"source_cell_absent": 25},
        }
        for cohort in ("gbsg2", "whas500", "metabric")
    }
    (run_dir / "cohort_summaries.json").write_text(
        json.dumps(summaries, sort_keys=True) + "\n", encoding="utf-8"
    )
    (run_dir / "report.md").write_text("Post-hoc study.\n", encoding="utf-8")
    completion: dict[str, object] = {
        "protocol_sha256": PROTOCOL_SHA256,
        "source_completion_sha256": "c" * 64,
        "planned_cells": 75,
        "stored_cells": 75,
        "status_counts": statuses,
        "cell_sha256": inventory,
        "aggregate_sha256": {
            "cohort_summaries.json": sha256_file(run_dir / "cohort_summaries.json"),
            "report.md": sha256_file(run_dir / "report.md"),
        },
    }
    _write_hashed_json(run_dir / "completion.json", completion, "completion_content_sha256")

    verified = verify_surrogate_run(run_dir)
    assert verified["status"] == "verified"
    assert verified["planned_cells"] == 75

    damaged = run_dir / "cells/gbsg2/r01f01.json"
    damaged.write_text(damaged.read_text(encoding="utf-8").replace("source_cell_absent", "tampered"), encoding="utf-8")
    with pytest.raises(RuntimeError, match="SHA-256 mismatch"):
        verify_surrogate_run(run_dir)


def test_compute_pilot_must_match_source_review_code_and_budget(tmp_path: Path) -> None:
    pilot_dir = tmp_path / "pilot"
    project_root = Path(__file__).resolve().parents[1]
    environment_lock = project_root / "conda-lock-win-64.yml"
    identity = "a" * 64
    review_sha = "e" * 64
    source = {
        "manifest_sha256": "d" * 64,
        "completion_sha256": "c" * 64,
        "manifest": {
            "input_sha256": {
                f"data/raw/{cohort}.csv": str(index + 1) * 64
                for index, cohort in enumerate(("gbsg2", "whas500", "metabric"))
            }
        },
    }
    code_hashes = {
        "src/pipelines/rsf_surrogate.py": _sha256(project_root / "src/pipelines/rsf_surrogate.py"),
        "scripts/run_rsf_surrogate.py": _sha256(project_root / "scripts/run_rsf_surrogate.py"),
    }
    manifest: dict[str, object] = {
        "run_type": "pilot",
        "protocol_sha256": PROTOCOL_SHA256,
        "protocol_gate_receipt": {
            "type": "owner_gate_waiver",
            "sha256": review_sha,
            "independent_acceptance": False,
        },
        "source_release": {
            "manifest_sha256": source["manifest_sha256"],
            "completion_sha256": source["completion_sha256"],
        },
        "code_sha256": code_hashes,
        "lock_sha256": _sha256_text(project_root / "conda-lock.yml"),
        "execution_environment": {
            "lock_file": environment_lock.name,
            "lock_sha256": _sha256_text(environment_lock),
            "platform": "win-64",
        },
        "raw_input_sha256": source["manifest"]["input_sha256"],
        "run_identity_sha256": identity,
    }
    _write_hashed_json(pilot_dir / "manifest.json", manifest, "manifest_content_sha256")
    cell_hashes: dict[str, str] = {}
    for cohort in ("gbsg2", "whas500", "metabric"):
        relative = f"cells/{cohort}/r01f01.json"
        cell: dict[str, object] = {
            "dataset": cohort,
            "repeat": 1,
            "fold": 1,
            "status": "complete",
            "total_seconds": 1.0,
            "run_identity_sha256": identity,
        }
        _write_hashed_json(pilot_dir / relative, cell, "cell_content_sha256")
        cell_hashes[relative] = sha256_file(pilot_dir / relative)
    summary = {
        "protocol_sha256": PROTOCOL_SHA256,
        "source_completion_sha256": source["completion_sha256"],
        "status": "complete",
        "projected_total_seconds": 75.0,
        "full_run_within_compute_allowance": True,
    }
    (pilot_dir / "pilot_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (pilot_dir / "pilot_report.md").write_text("pilot\n", encoding="utf-8")
    completion: dict[str, object] = {
        "protocol_sha256": PROTOCOL_SHA256,
        "source_completion_sha256": source["completion_sha256"],
        "planned_cells": 3,
        "stored_cells": 3,
        "status_counts": {"complete": 3},
        "cell_sha256": cell_hashes,
        "aggregate_sha256": {
            "pilot_summary.json": sha256_file(pilot_dir / "pilot_summary.json"),
            "pilot_report.md": sha256_file(pilot_dir / "pilot_report.md"),
        },
    }
    _write_hashed_json(pilot_dir / "pilot_completion.json", completion, "completion_content_sha256")

    verified, completion_sha = _verify_pilot_run(
        pilot_dir,
        checkpoint_root=project_root,
        environment_lock=environment_lock,
        environment_platform="win-64",
        source=source,
        review_sha256=review_sha,
        gate_receipt_type="owner_gate_waiver",
        pipeline=surrogate_pipeline,
    )
    assert verified["projected_total_seconds"] == 75.0
    assert len(completion_sha) == 64
