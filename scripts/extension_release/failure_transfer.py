"""Bind supplemental rank-failure provenance to its original frozen cells."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

CLASSIFICATION = "post_hoc_failure_provenance"
RANK_MESSAGE = "synthetic design is not full column rank"


def _require(condition: bool, message: str) -> None:
    """Raise ``ValueError(message)`` when ``condition`` is false."""
    if not condition:
        raise ValueError(message)


def _hash(path: Path) -> str:
    """Return the SHA-256 of a regular, non-linked failure-audit file."""
    _require(path.is_file() and not path.is_symlink(), f"missing or linked failure-audit file: {path}")
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _read(path: Path) -> dict[str, Any]:
    """Check the file is a regular, non-linked file, then return its parsed JSON."""
    _hash(path)
    return json.loads(path.read_text())


def _canonical(value: Any) -> str:
    """Return the SHA-256 of a value's compact, key-sorted JSON encoding."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _checked_content(value: dict[str, Any], identity: str) -> None:
    """Check a failure-audit record's own content hash and its classification fields.

    The record must declare the supplemental evidence status and that it
    performed no model fits and wrote no patient-level records.
    """
    _require(value.get("content_sha256") == _canonical({k: v for k, v in value.items() if k != "content_sha256"}),
             f"failure-audit content changed: {identity}")
    _require(value.get("evidence_status") == CLASSIFICATION
             and value.get("programme_completion") == "not_assessed"
             and value.get("scientific_model_fits_performed") is False
             and value.get("patient_level_records_written") is False,
             f"failure-audit classification differs: {identity}")


def _relative(root: Path, name: str) -> Path:
    """Resolve ``name`` inside ``root``, rejecting absolute, escaping or linked paths."""
    relative = Path(name)
    _require(not relative.is_absolute() and bool(relative.parts)
             and not ({".", ".."} & set(relative.parts)), "unsafe failure-audit path")
    target = root / relative
    _require(target.resolve().is_relative_to(root.resolve())
             and not any(p.is_symlink() for p in (target, *target.parents)),
             "linked or escaping failure-audit path")
    return target


def verify_failure_transfer(run: Path, audit: Path, helper: Path) -> dict[str, Any]:
    """Require a complete supplemental audit without claiming programme completion.

    This checks the source bindings and every retained reconstruction byte.
    Independent replay of the original generator is a separate restore check.
    """
    manifest = _read(run / "manifest.json")
    paths = {p.stem: p for p in (run / "cells").glob("*.json")}
    planned = {row["cell_id"] for row in manifest["plan"]}
    _require(len(planned) == manifest["planned_fits"] == 1625 and set(paths) == planned,
             "failure transfer requires the complete original grid")
    failed = {}
    for identity, path in paths.items():
        cell = _read(path)
        if cell.get("status") == "failed" and cell.get("message") == RANK_MESSAGE:
            _require(cell.get("error_type") == "ValueError"
                     and not any(k in cell for k in ("fit_attempts", "metrics", "predictions")),
                     "rank rejection is not an execution failure before sampling")
            failed[identity] = (cell, _hash(path))
    helper_hash = _hash(helper)
    source_bindings = {"source_manifest_sha256": _hash(run / "manifest.json"),
                       "source_manifest_content_sha256": manifest["manifest_content_sha256"],
                       "source_git_commit": manifest["code"]["git_commit"],
                       "source_freeze_content_sha256": manifest["freeze_sha256"],
                       "matched_sha256": manifest["matched_sha256"],
                       "audit_helper_sha256": helper_hash}
    candidates = []
    for path in sorted((audit / "snapshots").glob("failure_provenance_*.json")):
        snapshot = _read(path)
        _checked_content(snapshot, path.name)
        _require(all(snapshot["bindings"].get(k) == v for k, v in source_bindings.items()),
                 "failure-audit source/helper binding differs")
        _require(path.name == f"failure_provenance_{snapshot['content_sha256']}.json",
                 "failure-audit snapshot filename differs from content")
        if snapshot.get("source_grid_counts") == {"planned": 1625, "stored": 1625}:
            candidates.append((path, snapshot))
    _require(len(candidates) == 1, "one complete-grid failure-audit snapshot is required")
    snapshot_path, snapshot = candidates[0]
    rows = snapshot["cases"]
    _require(snapshot.get("available_source_cells_scanned") == snapshot.get("planned_source_cells") == 1625
             and snapshot.get("rank_failed_cells_audited") == len(rows) == len(failed)
             and len({r["cell_id"] for r in rows}) == len(rows)
             and {r["cell_id"] for r in rows} == set(failed),
             "failure-audit coverage differs from frozen rank failures")
    case_roots = audit / "cases"
    _require({p.name for p in case_roots.iterdir()} == set(failed) if case_roots.exists() else not failed,
             "failure-audit case inventory differs")
    for row in rows:
        identity = row["cell_id"]
        cell, source_hash = failed[identity]
        path = _relative(audit, row["sidecar"])
        _require(row["sidecar"] == f"cases/{identity}/case.json"
                 and row["source_cell_sha256"] == source_hash
                 and _hash(path) == row["sidecar_sha256"], "failure-audit sidecar binding differs")
        case = _read(path)
        _checked_content(case, identity)
        _require(case["bindings"] == {**snapshot["bindings"], "failed_cell_sha256": source_hash,
                                      "failed_cell_content_sha256": cell["cell_content_sha256"]}
                 and case["cell_id"] == identity and case["cell_seed"] == cell["seed"]
                 and case["source_failure_error_type"] == "ValueError"
                 and case["source_outer_fit_attempts_absent"] is True
                 and case["source_metrics_and_predictions_absent"] is True
                 and case["saved_outer_preprocessing_verified"] is True
                 and case["outer_preprocessing_state_sha256"] == cell["preprocessing"]["state_sha256"],
                 "failure-audit reconstruction identity differs")
        expected_files = {"case.json"}
        first_fail = []
        for draw in case["draws"]:
            _require(draw["source_generator_called"] is True
                     and draw["unchanged_original_constructor_called"] is True,
                     "failure audit did not use the original generator and validator")
            _require(set(draw["arrays"]) == {"X.npy", "time.npy"}, "failure-audit array inventory differs")
            for name, array in draw["arrays"].items():
                _require(array["path"] == f"draws/{draw['stage']}/{name}", "failure-audit array path differs")
                array_path = _relative(path.parent, array["path"])
                _require(_hash(array_path) == array["sha256"] and array_path.stat().st_size == array["bytes"],
                         "failure-audit matrix/time bytes changed")
                expected_files.add(array["path"])
            if draw["stage"] == case["first_failing_draw"]:
                first_fail.append(draw)
            else:
                _require(draw["matrix"]["full_column_rank"] is True
                         and draw["matrix"]["constructor_error"] is None
                         and draw["successful_original_generator_metadata_verified"] is True,
                         "a preceding generator draw did not pass unchanged validation")
        _require(len(first_fail) == 1 and case["draws"][-1] == first_fail[0],
                 "failure audit contains an unreached or ambiguous draw")
        draw = first_fail[0]
        _require(draw["matrix"]["constructor_error"] == RANK_MESSAGE
                 and draw["matrix"]["full_column_rank"] is False
                 and draw["matrix"]["rank"] == row["rank"] < row["p"] == draw["p"]
                 and draw["matrix"]["zero_columns"] == row["zero_columns"],
                 "failure-audit rank result differs")
        actual_files = {p.relative_to(path.parent).as_posix() for p in path.parent.rglob("*") if p.is_file()}
        _require(actual_files == expected_files, "failure-audit retained array inventory differs")
    return {"evidence_status": CLASSIFICATION, "programme_completion": "not_assessed",
            "snapshot": snapshot_path.relative_to(audit).as_posix(),
            "snapshot_sha256": _hash(snapshot_path), "snapshot_content_sha256": snapshot["content_sha256"],
            "source_manifest_sha256": source_bindings["source_manifest_sha256"],
            "audit_helper_sha256": helper_hash, "rank_failed_cells_audited": len(failed),
            "verification": "source bindings and retained reconstruction bytes; no new fits"}
