"""Reject invalid post-hoc evidence even when outer hashes are recomputed.

Covers ``verify_posthoc_run`` in ``src/utils/posthoc_evidence.py``,
``_write_or_verify`` in ``src/pipelines/posthoc_sampler.py`` and the separate
renderer ``scripts/render_horseshoe_sensitivity.py``. A constructed 75-cell run
with no clinical data stands in for the ADR-032 sampler sensitivity. Each
corruption is re-hashed, so only the content checks can catch it. Rendered
numbers must trace to the verified run (INV-007), and the sensitivity must stay
complete, separately labelled and acceptance-only (INV-009).
"""

from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.pipelines.posthoc_sampler import _write_or_verify, sensitivity_protocol
from src.utils.io import write_json_atomic
from src.utils.posthoc_evidence import EVIDENCE_STATUS, verify_posthoc_run
from src.utils.reproducibility import canonical_json_hash, sha256_file


def _write_hashed(path, record, field):
    """Set ``record[field]`` to the record's fresh content hash, in place, and write it."""
    record.pop(field, None)
    record[field] = canonical_json_hash(record)
    write_json_atomic(path, record)


@pytest.fixture
def sensitivity(tmp_path, monkeypatch):
    """Build a valid post-hoc run and a stub confirmatory source.

    Returns:
        The post-hoc run directory and the source directory.
    """
    source_dir, run = tmp_path / "source", tmp_path / "posthoc"
    source_dir.mkdir()
    # Only the protocol keys that the sensitivity changes, set below 0.999.
    original_protocol = {
        "models": {
            "bayesian_cox": {
                "priors": {"horseshoe": {"target_accept": 0.99}},
                "failed_fit_rule": {"refit_target_accept": 0.995},
            }
        }
    }
    source_manifest = {
        "protocol_freeze_sha256": "f" * 64,
        "run_config": {"protocol": original_protocol},
    }
    write_json_atomic(source_dir / "manifest.json", source_manifest)
    write_json_atomic(source_dir / "completion.json", {"source": True})
    # The full grid of 75 horseshoe folds: three cohorts, five repeats, five folds.
    keys = [
        (cohort, repeat, fold)
        for cohort in ("gbsg2", "metabric", "whas500")
        for repeat in range(1, 6)
        for fold in range(1, 6)
    ]
    cells, source_cells, inventory = [], [], {}
    for dataset, repeat, fold in keys:
        original = {
            "dataset": dataset,
            "repeat": repeat,
            "fold": fold,
            "model_key": "bayesian_horseshoe",
            "dataset_sha256": "a" * 64,
            "fold_seed": repeat * 10 + fold,
            "cell_seed": repeat * 100 + fold,
            "train_subject_ids": ["training"],
            "validation_subject_ids": ["validation"],
            "n_train": 1,
            "n_validation": 1,
            "events_train": 1,
            "events_validation": 1,
            "status": "complete",
        }
        relative = f"cells/{dataset}/repeat_{repeat:02d}_fold_{fold:02d}/bayesian_horseshoe.json"
        _write_hashed(source_dir / relative, original, "cell_content_sha256")
        source_cells.append((relative, original))
        # The unchanged normal and spike-and-slab comparators exist only in the
        # stubbed source record; the verifier never reads them from disk.
        for comparator in ("bayesian_normal", "bayesian_spike_slab"):
            comparator_cell = copy.deepcopy(original)
            comparator_cell["model_key"] = comparator
            source_cells.append(
                (relative.replace("bayesian_horseshoe", comparator), comparator_cell)
            )
        # The refit keeps the original fold lineage and adds the post-hoc labels,
        # the source-cell hash and 0.999 acceptance.
        refit = copy.deepcopy(original)
        refit.update(
            {
                "analysis_mode": EVIDENCE_STATUS,
                "evidence_status": EVIDENCE_STATUS,
                "source_confirmatory_cell_sha256": sha256_file(source_dir / relative),
                "sampler_sensitivity": {"target_accept": 0.999, "scope": "all_horseshoe_folds"},
                "fit_attempts": [{"target_accept": 0.999}],
            }
        )
        _write_hashed(run / relative, refit, "cell_content_sha256")
        cells.append(refit)
        inventory[relative] = sha256_file(run / relative)
    configuration = {
        "analysis_mode": EVIDENCE_STATUS,
        "decision": "ADR-032",
        "target_accept_every_attempt": 0.999,
        "source_manifest_sha256": sha256_file(source_dir / "manifest.json"),
        "source_completion_sha256": sha256_file(source_dir / "completion.json"),
        "protocol_freeze_sha256": "f" * 64,
        "source_protocol": original_protocol,
        "sensitivity_protocol": sensitivity_protocol(original_protocol),
        "planned_keys": [list(key) for key in keys],
    }
    manifest = {"run_config": configuration, "config_sha256": canonical_json_hash(configuration)}
    _write_hashed(run / "manifest.json", manifest, "manifest_content_sha256")
    # Nine primary contrasts (three prior pairs per cohort) on the integrated
    # Brier score (IBS), each with all 25 paired folds, so the Holm family is
    # complete.
    primary = [
        {
            "dataset": cohort,
            "model_a": model_a,
            "model_b": model_b,
            "n_paired_folds": 25,
            "ibs": {
                "mean_difference": 0.0002,
                "confidence_lower": -0.0001,
                "confidence_upper": 0.0005,
                "p_value": 0.3,
            },
            "holm_adjusted_p": 1.0,
        }
        for cohort in ("gbsg2", "metabric", "whas500")
        for model_a, model_b in (
            ("Bayesian Cox (normal)", "Bayesian Cox (horseshoe)"),
            ("Bayesian Cox (normal)", "Bayesian Cox (spike_slab)"),
            ("Bayesian Cox (horseshoe)", "Bayesian Cox (spike_slab)"),
        )
    ]
    inference = {
        "evidence_status": EVIDENCE_STATUS,
        "confirmatory_outcome_replaced": False,
        "primary": primary,
        "holm_family_complete": True,
    }
    _write_hashed(run / "inference.json", inference, "result_content_sha256")
    completion = {
        "analysis_mode": EVIDENCE_STATUS,
        "planned_cells": 75,
        "stored_cells": 75,
        "status_counts": {"complete": 75},
        "cell_sha256": inventory,
        "source_completion_sha256": configuration["source_completion_sha256"],
        "aggregate_sha256": {"inference.json": sha256_file(run / "inference.json")},
    }
    _write_hashed(run / "completion.json", completion, "completion_content_sha256")
    # Replaces ``verify_frozen_run``, so no real 450-cell source run is needed.
    source = SimpleNamespace(
        mode="confirmatory",
        run_dir=source_dir,
        manifest=source_manifest,
        cells=source_cells,
        inference={"primary": primary},
    )
    monkeypatch.setattr("src.utils.posthoc_evidence.verify_frozen_run", lambda _: source)
    return run, source_dir


def test_all75_posthoc_cells_verify(sensitivity):
    """An intact 75-cell sensitivity verifies and returns every cell (INV-009)."""
    run, source = sensitivity
    assert len(verify_posthoc_run(run, source)["cells"]) == 75


@pytest.mark.parametrize(
    "corruption",
    [
        "undeclared_method",
        "seed",
        "acceptance",
        "label",
        "missing_cell",
        "replacement_claim",
        "failed_hidden_as_complete",
        "unknown_status",
    ],
)
def test_rehashed_corrupt_evidence_still_fails(sensitivity, corruption):
    """Content corruptions fail verification even with every hash recomputed (INV-007, INV-009)."""
    run, source = sensitivity
    completion = json.loads((run / "completion.json").read_text())
    if corruption == "undeclared_method":
        manifest = json.loads((run / "manifest.json").read_text())
        manifest["run_config"]["sensitivity_protocol"]["new_method"] = True
        manifest["config_sha256"] = canonical_json_hash(manifest["run_config"])
        _write_hashed(run / "manifest.json", manifest, "manifest_content_sha256")
    elif corruption == "replacement_claim":
        inference = json.loads((run / "inference.json").read_text())
        inference["confirmatory_outcome_replaced"] = True
        _write_hashed(run / "inference.json", inference, "result_content_sha256")
        completion["aggregate_sha256"]["inference.json"] = sha256_file(run / "inference.json")
    else:
        relative = next(iter(completion["cell_sha256"]))
        path = run / relative
        if corruption == "missing_cell":
            path.unlink()
        else:
            cell = json.loads(path.read_text())
            if corruption == "seed":
                cell["cell_seed"] += 1
            elif corruption == "acceptance":
                cell["fit_attempts"][0]["target_accept"] = 0.99
            elif corruption == "failed_hidden_as_complete":
                # The counts admit the failure, but the inference still claims
                # 25 paired folds for every contrast.
                cell["status"] = "failed_diagnostics"
                completion["status_counts"] = {"complete": 74, "failed_diagnostics": 1}
            elif corruption == "unknown_status":
                cell["status"] = "ignored"
                completion["status_counts"] = {"complete": 74, "ignored": 1}
            else:
                cell["evidence_status"] = "confirmatory"
            _write_hashed(path, cell, "cell_content_sha256")
            completion["cell_sha256"][relative] = sha256_file(path)
    _write_hashed(run / "completion.json", completion, "completion_content_sha256")
    with pytest.raises(RuntimeError):
        verify_posthoc_run(run, source)


def test_partial_finalisation_reuses_equal_result_and_refuses_changed_result(tmp_path):
    """Resumed finalisation leaves an equal result untouched and refuses a different one."""
    path = tmp_path / "inference.json"
    _write_or_verify(path, {"estimate": 0.1})
    original = path.read_bytes()
    _write_or_verify(path, {"estimate": 0.1})
    assert path.read_bytes() == original
    with pytest.raises(RuntimeError, match="differs from recomputation"):
        _write_or_verify(path, {"estimate": 0.2})


def test_posthoc_renderer_uses_recorded_interval_and_separate_labels(sensitivity, tmp_path):
    """Stored intervals are rendered unchanged and outputs are labelled post-hoc (INV-007, INV-009)."""
    path = Path(__file__).resolve().parents[1] / "scripts/render_horseshoe_sensitivity.py"
    spec = importlib.util.spec_from_file_location("posthoc_renderer_test", path)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    run, source = sensitivity
    records = verify_posthoc_run(run, source)
    rows = renderer.primary_rows(records["inference"])
    assert rows.lower_95.tolist() == [-0.0001] * 9
    assert rows.upper_95.tolist() == [0.0005] * 9
    # Two renders of the same evidence must produce byte-identical files.
    first = renderer.render(run, source, tmp_path / "render_a")
    second = renderer.render(run, source, tmp_path / "render_b")
    assert {path.name: sha256_file(path) for path in first.iterdir()} == {
        path.name: sha256_file(path) for path in second.iterdir()
    }
    assert "POST-HOC" in (first / "POSTHOC_EVIDENCE_NOTICE.txt").read_text()
    assert json.loads((first / "lineage.json").read_text())["evidence_status"] == EVIDENCE_STATUS
