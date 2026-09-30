"""Focused analysis gates for the separately frozen clinical subset."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.finalize_clinical_methods import (
    COHORTS,
    PENALISED,
    check_baseline_pins,
    check_programme_evidence,
    check_source_receipt,
    descriptive_summary,
    fixed_family,
    selected_ids,
)
from src.utils.io import read_mapping, write_json_atomic
from src.utils.reproducibility import canonical_json_hash, sha256_file


def fake_cell(dataset: str, model: str, repeat: int, fold: int, *,
              status: str = "complete") -> dict:
    """Make one schema-shaped fold without a fitted model or patient data."""
    reference = model.startswith("bayesian_")
    cell = {"dataset": dataset, "setting": "clinical", "condition": "full",
            "model_key": model, "repeat": repeat, "fold": fold,
            "status": status, "train_subject_ids": [f"train-{dataset}-{repeat}-{fold}"],
            "predictions": {key: [f"value-{dataset}-{repeat}-{fold}"] for key in
                            ("subject_ids", "observed_time", "observed_event", "ibs_grid",
                             "training_time", "training_event")},
            "fit_attempts": [], "total_seconds" if reference else "seconds": 3.0,
            "n_train": 10, "events_train": 5}
    if status == "complete":
        cell["metrics"] = {"ibs": 0.3 if reference else 0.2,
                           "harrell_c_index": 0.6, "uno_c_index": 0.6, "mean_auc": 0.6,
                           "calibration": [{"summary": {"horizon": h, "n_known": 8,
                               "calibration_in_the_large": {"estimate": 0.0},
                               "intercept": {"estimate": 0.0}, "slope": {"estimate": 1.0}}}
                               for h in (1, 2, 3)]}
    return cell


def synthetic_sources(*, fail_reference: bool = False, fail_penalised: bool = False) -> tuple:
    """Construct the full fixed roster with one optional failed outcome."""
    selected, original, sampler = [], [], []
    for dataset in COHORTS:
        for repeat in range(1, 6):
            for fold in range(1, 6):
                for model in PENALISED:
                    status = "failed" if fail_penalised and (dataset, model, repeat, fold) == (
                        "gbsg2", "ridge", 1, 1) else "complete"
                    selected.append(fake_cell(dataset, model, repeat, fold, status=status))
                for model in ("bayesian_normal", "bayesian_spike_slab", "bayesian_horseshoe"):
                    status = "failed_diagnostics" if fail_reference and (dataset, model, repeat, fold) == (
                        "whas500", "bayesian_normal", 1, 1) else "complete"
                    original.append((f"{dataset}/{repeat}/{fold}/{model}",
                                     fake_cell(dataset, model, repeat, fold, status=status)))
                sampler.append(fake_cell(dataset, "bayesian_horseshoe", repeat, fold))
    return selected, SimpleNamespace(cells=original), {"cells": sampler}


def test_fixed_family_withholds_holm_if_one_reference_fold_fails() -> None:
    """An outcome-aware subset cannot convert an incomplete family into significance."""
    selected, original, sampler = synthetic_sources(fail_reference=True)
    family = fixed_family(selected, original, sampler)
    assert len(family["contrasts"]) == 27
    assert family["family_complete"] is False
    assert any(row["status"] == "incomplete_no_inference" for row in family["contrasts"])
    assert any(row["status"] == "estimable" for row in family["contrasts"])
    assert all("holm_reject" not in row for row in family["contrasts"])


def test_fixed_family_uses_all_27_when_every_pair_is_available() -> None:
    """A complete family alone receives Holm fields, without a global winner claim."""
    selected, original, sampler = synthetic_sources()
    family = fixed_family(selected, original, sampler)
    assert family["family_complete"] is True
    assert len(family["contrasts"]) == 27
    assert all(row["n_pairs"] == 25 and "holm_adjusted_p" in row
               for row in family["contrasts"])


def test_descriptive_status_counts_keep_failed_cells_in_denominator() -> None:
    """Accepted-only metrics retain every planned cell and failed original context."""
    selected, original, sampler = synthetic_sources(fail_penalised=True)
    horseshoe = next(cell for _, cell in original.cells if cell["model_key"] == "bayesian_horseshoe")
    horseshoe["status"] = "failed_diagnostics"
    horseshoe.pop("metrics")
    summary = descriptive_summary(selected, original, sampler)
    target = next(row for row in summary["group_rows"]
                  if row["dataset"] == "gbsg2" and row["model_key"] == "ridge")
    assert target["planned"] == 25
    assert target["accepted"] == 24
    assert target["status_counts"] == {"failed": 1, "complete": 24}
    assert target["metrics_accepted_only"]["ibs"]["available"] == 24
    assert len(summary["original_horseshoe_context"]) == 75
    assert Counter(row["status"] for row in summary["original_horseshoe_context"])["failed_diagnostics"] == 1
    assert summary["interpretation"]["no_equivalence_or_global_winner_claim"] is True


def fake_receipt_tree(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Write a synthetic 225-cell source and a bound independent PASS receipt."""
    root, run = tmp_path / "code", tmp_path / "source"
    (root / "coordination/extension_sources").mkdir(parents=True)
    (root / "docs").mkdir()
    (root / "scripts").mkdir()
    (run / "cells").mkdir(parents=True)
    (root / "scripts/verify_clinical_methods_subset.py").write_text("# fixture verifier\n")
    (root / "docs/protocol_addendum_clinical_methods.md").write_text("fixed scope\n")
    (root / "coordination/extension_sources/baseline_sources.json").write_text("{}\n")
    roster = {"datasets": list(COHORTS), "penalised_models": list(PENALISED),
              "source_cell_count": 225}
    roster_path = root / "coordination/clinical_methods_roster.json"
    write_json_atomic(roster_path, roster)
    manifest = {"code": {"git_commit": "1" * 40}, "matched_sha256": "2" * 64}
    manifest["manifest_content_sha256"] = canonical_json_hash(manifest)
    write_json_atomic(run / "manifest.json", manifest)
    scope = {"sha256": {
        "docs/protocol_addendum_clinical_methods.md": sha256_file(
            root / "docs/protocol_addendum_clinical_methods.md"),
        "coordination/clinical_methods_roster.json": sha256_file(roster_path)},
        "baseline_source_pins": "coordination/extension_sources/baseline_sources.json",
        "baseline_source_pins_sha256": sha256_file(
            root / "coordination/extension_sources/baseline_sources.json"),
        "source_extension_manifest_sha256": sha256_file(run / "manifest.json"),
        "source_fit_commit": "1" * 40}
    scope_path = root / "coordination/clinical_methods_scope_freeze.json"
    write_json_atomic(scope_path, scope)
    entries = {}
    for identity in selected_ids():
        cell = {"cell_id": identity, "status": "complete"}
        cell["cell_content_sha256"] = canonical_json_hash(cell)
        path = run / "cells" / f"{identity}.json"
        write_json_atomic(path, cell)
        entries[identity] = {"file_sha256": sha256_file(path),
                             "cell_content_sha256": cell["cell_content_sha256"],
                             "status": "complete"}
    refits = {identity: {"source_content_sha256": entries[identity]["cell_content_sha256"],
                         "refit_content_sha256": "3" * 64,
                         "comparison": "non-timing scientific content equal",
                         "original_receipt": "missing_pending"}
              for identity in entries if "__r01f01__" in identity}
    assert len(refits) == 9
    receipt = {"evidence_status": "post_hoc_clinical_methods_subset",
               "verification_status": "passed", "verifier_committed": True,
               "verified_cells": 225,
               "rescored_cells": 225, "refits_compared": 9,
               "full_extension_grid_verified": False,
               "scope_freeze_sha256": sha256_file(scope_path),
               "source_manifest_sha256": sha256_file(run / "manifest.json"),
               "production_code_commit": "1" * 40,
               "manifest_matched_sha256": "2" * 64,
               "verifier_sha256": sha256_file(root / "scripts/verify_clinical_methods_subset.py"),
               "cells": entries, "selected_refits": refits,
               "original_refit_receipts_verified": 0,
               "original_refit_receipts_pending": 9,
               "status_counts": {"complete": 225}}
    report = tmp_path / "verification.json"
    write_json_atomic(report, receipt)
    return root, run, report


def test_source_receipt_rejects_changed_cell_and_missing_pass(tmp_path: Path) -> None:
    """An analysis cannot consume a stale cell or an unpassed verifier report."""
    root, run, report = fake_receipt_tree(tmp_path)
    cells, _ = check_source_receipt(root, run, report)
    assert len(cells) == 225
    receipt = read_mapping(report)
    receipt["verification_status"] = "pending"
    write_json_atomic(report, receipt)
    with pytest.raises(ValueError, match="not passed"):
        check_source_receipt(root, run, report)
    receipt["verification_status"] = "passed"
    receipt["verifier_committed"] = False
    write_json_atomic(report, receipt)
    with pytest.raises(ValueError, match="not passed"):
        check_source_receipt(root, run, report)
    receipt["verifier_committed"] = True
    write_json_atomic(report, receipt)
    identity = next(iter(selected_ids()))
    path = run / "cells" / f"{identity}.json"
    cell = read_mapping(path)
    cell["new_field"] = "changed"
    cell["cell_content_sha256"] = canonical_json_hash({k: v for k, v in cell.items()
                                                         if k != "cell_content_sha256"})
    write_json_atomic(path, cell)
    with pytest.raises(ValueError, match="changed or has invalid status"):
        check_source_receipt(root, run, report)


def test_source_receipt_binds_manifest_matched_hash(tmp_path: Path) -> None:
    """A verifier report from a different matched-input manifest is rejected."""
    root, run, report = fake_receipt_tree(tmp_path)
    receipt = read_mapping(report)
    receipt["manifest_matched_sha256"] = "4" * 64
    write_json_atomic(report, receipt)
    with pytest.raises(ValueError, match="cannot certify the full extension grid"):
        check_source_receipt(root, run, report)


def test_baseline_pin_mismatch_stops_before_reference_loading(tmp_path: Path) -> None:
    """The focused finalizer cannot bypass frozen original and ADR-032 hashes."""
    root = tmp_path / "code"
    path = root / "coordination/extension_sources/baseline_sources.json"
    path.parent.mkdir(parents=True)
    write_json_atomic(path, {"primary": {"manifest_sha256": "0" * 64,
                                                 "completion_sha256": "0" * 64},
                             "sampler_adr032": {"manifest_sha256": "0" * 64,
                                                 "completion_sha256": "0" * 64}})
    primary = tmp_path / "primary"
    sampler = tmp_path / "sampler"
    primary.mkdir()
    sampler.mkdir()
    (primary / "manifest.json").write_text("untrusted\n")
    with pytest.raises(ValueError, match="frozen baseline source changed"):
        check_baseline_pins(root, primary, sampler)


def test_baseline_programme_pin_requires_450_identical_refits(tmp_path: Path) -> None:
    """A release hash and 450 matching saved refits support only the stated bound."""
    root = tmp_path / "code"
    pin_path = root / "coordination/clinical_methods_baseline_evidence.json"
    pin_path.parent.mkdir(parents=True)
    programme = tmp_path / "programme"
    sampler = programme / "sampler_run"
    sampler.mkdir(parents=True)
    reproduction_path = programme / "reproduction/verification.json"
    analysis_path = programme / "release_metadata/programme_analysis_verified.json"
    ready_path = programme / "release_metadata/programme_release_ready.json"
    reproduction = {"evidence_status": "verification_only",
                    "analysis": "confirmatory_refit_reproduction", "selection": "all",
                    "cells_checked": 450, "cells_identical": 450,
                    "cells": [{"cell": f"cell-{index}", "identical": True, "n_differences": 0}
                              for index in range(450)]}
    reproduction["report_content_sha256"] = canonical_json_hash(reproduction)
    write_json_atomic(reproduction_path, reproduction)
    analysis = {"status": "analysis_and_rendering_verified_pending_final_visual_qa",
                "reproduction_cells_identical": 450,
                "confirmatory_status_counts": {"complete": 430, "failed_diagnostics": 20},
                "posthoc_sampler_status_counts": {"complete": 75}}
    analysis["result_content_sha256"] = canonical_json_hash(analysis)
    write_json_atomic(analysis_path, analysis)
    write_json_atomic(ready_path, {"status": "release_ready"})
    pin = {"version": 1,
           "reproduction_verification_relative_path": "reproduction/verification.json",
           "reproduction_verification_sha256": sha256_file(reproduction_path),
           "reproduction_cells_checked": 450, "reproduction_cells_identical": 450,
           "programme_analysis_verified_relative_path":
               "release_metadata/programme_analysis_verified.json",
           "programme_analysis_verified_sha256": sha256_file(analysis_path),
           "programme_release_ready_relative_path":
               "release_metadata/programme_release_ready.json",
           "programme_release_ready_sha256": sha256_file(ready_path),
           "verification_limit": "saved records corroborated; raw posterior arrays unavailable"}
    write_json_atomic(pin_path, pin)
    assert check_programme_evidence(root, sampler)["original_refits_identical"] == 450
    reproduction["cells"][0]["identical"] = False
    reproduction["report_content_sha256"] = canonical_json_hash({
        k: v for k, v in reproduction.items() if k != "report_content_sha256"})
    write_json_atomic(reproduction_path, reproduction)
    with pytest.raises(ValueError, match="restored baseline programme evidence changed"):
        check_programme_evidence(root, sampler)
    pin["reproduction_verification_sha256"] = sha256_file(reproduction_path)
    write_json_atomic(pin_path, pin)
    with pytest.raises(ValueError, match="does not cover 450 identical cells"):
        check_programme_evidence(root, sampler)
