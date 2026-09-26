"""Verify the separate ADR-032 sampler evidence without fitting any model."""

from __future__ import annotations

import copy
import json
from collections import Counter
from pathlib import Path
from typing import Any

from src.rendering.verification import _safe_child, _verify_content_hash, verify_frozen_run
from src.utils.reproducibility import canonical_json_hash, sha256_file

EVIDENCE_STATUS = "posthoc_sampler_sensitivity"
TARGET_ACCEPT = 0.999


def verify_posthoc_cell(path: Path, source_dir: Path, key: tuple[str, int, int]) -> dict[str, Any]:
    """Verify a refit's hash, sampler setting and original fold lineage."""
    cell = json.loads(path.read_text())
    _verify_content_hash(cell, "cell_content_sha256", path)
    if (
        cell.get("analysis_mode") != EVIDENCE_STATUS
        or cell.get("evidence_status") != EVIDENCE_STATUS
    ):
        raise RuntimeError(f"post-hoc cell evidence label is invalid: {path}")
    if (cell.get("dataset"), cell.get("repeat"), cell.get("fold")) != key:
        raise RuntimeError(f"post-hoc cell fold key is invalid: {path}")
    if cell.get("model_key") != "bayesian_horseshoe":
        raise RuntimeError(f"post-hoc cell model is invalid: {path}")
    dataset, repeat, fold = key
    original_path = (
        source_dir
        / "cells"
        / dataset
        / f"repeat_{repeat:02d}_fold_{fold:02d}"
        / "bayesian_horseshoe.json"
    )
    if cell.get("source_confirmatory_cell_sha256") != sha256_file(original_path):
        raise RuntimeError(f"post-hoc source cell hash differs: {path}")
    if cell.get("sampler_sensitivity") != {
        "target_accept": TARGET_ACCEPT,
        "scope": "all_horseshoe_folds",
    }:
        raise RuntimeError(f"post-hoc declared sampler sensitivity differs: {path}")
    attempts = cell.get("fit_attempts", [])
    if not attempts or any(attempt.get("target_accept") != TARGET_ACCEPT for attempt in attempts):
        raise RuntimeError(f"post-hoc attempt acceptance differs: {path}")
    original = json.loads(original_path.read_text())
    for field in (
        "dataset_sha256",
        "fold_seed",
        "cell_seed",
        "train_subject_ids",
        "validation_subject_ids",
        "n_train",
        "n_validation",
        "events_train",
        "events_validation",
    ):
        if field not in original or cell.get(field) != original[field]:
            raise RuntimeError(f"post-hoc original fold lineage differs at {field}: {path}")
    return cell


def verify_posthoc_run(run_dir: Path, source_dir: Path) -> dict[str, Any]:
    """Verify the complete 75-cell sensitivity and its paired-inference sources.

    Args:
        run_dir: Separate sensitivity directory containing its completion record.
        source_dir: Immutable 450-cell confirmatory directory.

    Returns:
        Verified manifest, completion, inference and cells for a pure renderer.
    """
    source = verify_frozen_run(source_dir)
    if source.mode != "confirmatory":
        raise ValueError("post-hoc evidence requires a confirmatory source")
    records = {}
    for name, field in (
        ("manifest", "manifest_content_sha256"),
        ("completion", "completion_content_sha256"),
        ("inference", "result_content_sha256"),
    ):
        path = run_dir / f"{name}.json"
        record = json.loads(path.read_text())
        _verify_content_hash(record, field, path)
        records[name] = record
    manifest, completion, inference = (
        records[name] for name in ("manifest", "completion", "inference")
    )
    configuration = manifest["run_config"]
    if manifest["config_sha256"] != canonical_json_hash(configuration):
        raise RuntimeError("post-hoc configuration content hash differs")
    for name, expected in (
        ("analysis_mode", EVIDENCE_STATUS),
        ("decision", "ADR-032"),
        ("target_accept_every_attempt", TARGET_ACCEPT),
        ("source_manifest_sha256", sha256_file(source.run_dir / "manifest.json")),
        ("source_completion_sha256", sha256_file(source.run_dir / "completion.json")),
        ("protocol_freeze_sha256", source.manifest["protocol_freeze_sha256"]),
        ("source_protocol", source.manifest["run_config"]["protocol"]),
    ):
        if configuration.get(name) != expected:
            raise RuntimeError(f"post-hoc configuration lineage differs at {name}")
    changed = copy.deepcopy(configuration["source_protocol"])
    changed["models"]["bayesian_cox"]["priors"]["horseshoe"]["target_accept"] = TARGET_ACCEPT
    changed["models"]["bayesian_cox"]["failed_fit_rule"]["refit_target_accept"] = TARGET_ACCEPT
    if configuration.get("sensitivity_protocol") != changed:
        raise RuntimeError("post-hoc protocol includes an undeclared methodological change")
    keys = sorted(
        (cell["dataset"], cell["repeat"], cell["fold"])
        for _, cell in source.cells
        if cell["model_key"] == "bayesian_horseshoe"
    )
    if (
        len(keys) != 75
        or len(set(keys)) != 75
        or configuration["planned_keys"] != [list(key) for key in keys]
    ):
        raise RuntimeError("post-hoc planned grid differs from all 75 original horseshoe folds")
    expected_inventory = {
        f"cells/{dataset}/repeat_{repeat:02d}_fold_{fold:02d}/bayesian_horseshoe.json": (
            dataset,
            repeat,
            fold,
        )
        for dataset, repeat, fold in keys
    }
    inventory = completion.get("cell_sha256", {})
    actual_files = {
        str(path.relative_to(run_dir)) for path in (run_dir / "cells").glob("*/*/*.json")
    }
    if set(inventory) != set(expected_inventory) or actual_files != set(expected_inventory):
        raise RuntimeError("post-hoc cell inventory is incomplete or contains unexpected cells")
    cells = []
    for relative, key in expected_inventory.items():
        path = _safe_child(run_dir, relative)
        if sha256_file(path) != inventory[relative]:
            raise RuntimeError(f"post-hoc cell file hash differs: {relative}")
        cells.append(verify_posthoc_cell(path, source.run_dir, key))
    if (
        completion.get("analysis_mode") != EVIDENCE_STATUS
        or completion.get("planned_cells") != 75
        or completion.get("stored_cells") != 75
    ):
        raise RuntimeError("post-hoc completion grid or evidence status differs")
    if completion.get("status_counts") != dict(Counter(cell["status"] for cell in cells)):
        raise RuntimeError("post-hoc completion status counts differ")
    if completion.get("source_completion_sha256") != configuration["source_completion_sha256"]:
        raise RuntimeError("post-hoc completion refers to a different source run")
    if completion.get("aggregate_sha256") != {
        "inference.json": sha256_file(run_dir / "inference.json")
    }:
        raise RuntimeError("post-hoc inference file hash differs")
    if (
        inference.get("evidence_status") != EVIDENCE_STATUS
        or inference.get("confirmatory_outcome_replaced") is not False
    ):
        raise RuntimeError("post-hoc inference evidence boundary differs")
    if len(inference.get("primary", [])) != 9:
        raise RuntimeError("post-hoc inference does not retain the nine-contrast family")
    expected_pairs = {
        (row["dataset"], row["model_a"], row["model_b"]) for row in source.inference["primary"]
    }
    observed_pairs = {
        (row["dataset"], row["model_a"], row["model_b"]) for row in inference["primary"]
    }
    if len(expected_pairs) != 9 or observed_pairs != expected_pairs:
        raise RuntimeError("post-hoc contrast family differs from the frozen source")
    complete_family = all(
        row.get("n_paired_folds") == 25 and isinstance(row.get("ibs"), dict)
        for row in inference["primary"]
    )
    if inference.get("holm_family_complete") is not complete_family:
        raise RuntimeError("post-hoc Holm completeness differs from available contrasts")
    records["cells"] = cells
    return records
