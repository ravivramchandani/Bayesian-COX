"""Preserve complete failure provenance and reject broken source/array bindings."""

from __future__ import annotations

import hashlib
import json
import runpy
from pathlib import Path

import pytest


def failure_fixture(tmp_path: Path, module: dict) -> tuple[Path, Path, Path]:
    """Build transfer-only fixture records, with no patient data or fitted result."""
    run, audit, helper = tmp_path / "run", tmp_path / "audit", tmp_path / "helper.py"
    cells = run / "cells"
    cells.mkdir(parents=True)
    helper.write_text("# transfer test fixture\n")
    identity = "fixture_0000"
    cell = {"status": "failed", "error_type": "ValueError", "message": module["RANK_MESSAGE"],
            "cell_content_sha256": "a" * 64, "seed": 17,
            "preprocessing": {"state_sha256": "b" * 64}}
    for i in range(1625):
        (cells / f"fixture_{i:04}.json").write_text(json.dumps(cell if i == 0 else {"status": "complete"}))
    manifest = {"planned_fits": 1625, "plan": [{"cell_id": p.stem} for p in sorted(cells.iterdir())],
                "manifest_content_sha256": "c" * 64, "code": {"git_commit": "fixture"},
                "freeze_sha256": "d" * 64, "matched_sha256": "e" * 64}
    (run / "manifest.json").write_text(json.dumps(manifest))
    bindings = {"source_manifest_sha256": module["_hash"](run / "manifest.json"),
                "source_manifest_content_sha256": manifest["manifest_content_sha256"],
                "source_git_commit": "fixture", "source_freeze_content_sha256": manifest["freeze_sha256"],
                "matched_sha256": manifest["matched_sha256"], "audit_helper_sha256": module["_hash"](helper),
                "runtime": {"test_only": True}}
    case_dir = audit / "cases" / identity
    (case_dir / "draws/outer").mkdir(parents=True)
    arrays = {}
    for name in ("X.npy", "time.npy"):
        path = case_dir / "draws/outer" / name
        path.write_bytes(b"transfer fixture array bytes")
        arrays[name] = {"path": f"draws/outer/{name}", "bytes": path.stat().st_size,
                        "sha256": module["_hash"](path)}
    source_hash = module["_hash"](cells / f"{identity}.json")
    case = {"evidence_status": module["CLASSIFICATION"], "programme_completion": "not_assessed",
            "scientific_model_fits_performed": False, "patient_level_records_written": False,
            "bindings": {**bindings, "failed_cell_sha256": source_hash,
                         "failed_cell_content_sha256": cell["cell_content_sha256"]},
            "cell_id": identity, "cell_seed": 17, "saved_outer_preprocessing_verified": True,
            "source_failure_error_type": "ValueError", "source_outer_fit_attempts_absent": True,
            "source_metrics_and_predictions_absent": True,
            "outer_preprocessing_state_sha256": "b" * 64, "first_failing_draw": "outer",
            "draws": [{"stage": "outer", "p": 1, "source_generator_called": True,
                       "unchanged_original_constructor_called": True, "arrays": arrays,
                       "matrix": {"constructor_error": module["RANK_MESSAGE"], "rank": 0,
                                  "full_column_rank": False, "zero_columns": ["group=rare"]}}]}
    case["content_sha256"] = module["_canonical"](case)
    (case_dir / "case.json").write_text(json.dumps(case))
    snapshot = {"evidence_status": module["CLASSIFICATION"], "programme_completion": "not_assessed",
                "scientific_model_fits_performed": False, "patient_level_records_written": False,
                "bindings": bindings, "source_grid_counts": {"planned": 1625, "stored": 1625},
                "available_source_cells_scanned": 1625, "planned_source_cells": 1625,
                "rank_failed_cells_audited": 1,
                "cases": [{"cell_id": identity, "sidecar": f"cases/{identity}/case.json",
                           "source_cell_sha256": source_hash, "sidecar_sha256": module["_hash"](case_dir / "case.json"),
                           "rank": 0, "p": 1, "zero_columns": ["group=rare"]}]}
    snapshot["content_sha256"] = module["_canonical"](snapshot)
    (audit / "snapshots").mkdir()
    (audit / "snapshots" / f"failure_provenance_{snapshot['content_sha256']}.json").write_text(json.dumps(snapshot))
    return run, audit, helper


@pytest.fixture
def failure_module():
    """Load ``failure_transfer.py`` as a module namespace for testing."""
    path = Path(__file__).resolve().parents[1] / "scripts/extension_release/failure_transfer.py"
    return runpy.run_path(str(path))


def test_failure_transfer_preserves_supplemental_classification(failure_module, tmp_path):
    """Transferred failure provenance retains its supplemental classification."""
    args = failure_fixture(tmp_path, failure_module)
    before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*") if p.is_file()}
    result = failure_module["verify_failure_transfer"](*args)
    assert result["rank_failed_cells_audited"] == 1
    assert result["programme_completion"] == "not_assessed"
    assert before == {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in tmp_path.rglob("*") if p.is_file()}


@pytest.mark.parametrize("broken", ["array", "case", "helper", "source", "missing_case", "extra_case"])
def test_failure_transfer_rejects_changed_or_missing_provenance(failure_module, tmp_path, broken):
    """Changed or missing failure provenance is rejected."""
    run, audit, helper = failure_fixture(tmp_path, failure_module)
    case = audit / "cases/fixture_0000"
    if broken == "missing_case":
        (case / "case.json").unlink()
    elif broken == "extra_case":
        (audit / "cases/unplanned").mkdir()
    else:
        target = {"array": case / "draws/outer/X.npy", "case": case / "case.json",
                  "helper": helper, "source": run / "cells/fixture_0000.json"}[broken]
        target.write_bytes(target.read_bytes() + b" ")
    with pytest.raises(ValueError):
        failure_module["verify_failure_transfer"](run, audit, helper)


def test_failure_transfer_requires_complete_source_grid(failure_module, tmp_path):
    """Failure transfer requires the complete planned source grid."""
    run, audit, helper = failure_fixture(tmp_path, failure_module)
    (run / "cells/fixture_0001.json").unlink()
    with pytest.raises(ValueError, match="complete original grid"):
        failure_module["verify_failure_transfer"](run, audit, helper)
