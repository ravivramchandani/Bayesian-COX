"""Verify the portable producer map of a recovered extension run."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

HASH = re.compile(r"[0-9a-f]{64}\Z")
COUNTS = {"intact_original": 1193, "new_refit": 21, "new_continuation": 411}
SHARD_COUNTS = (45, 84, 40, 93, 62, 87)


def digest(path: Path) -> str:
    """Hash a regular evidence file without loading traces into memory."""
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or linked recovery file: {path}")
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def read(path: Path) -> dict[str, Any]:
    """Read one regular JSON mapping, rejecting malformed evidence."""
    digest(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"recovery record is not a mapping: {path}")
    return value


def canonical_hash(value: Any) -> str:
    """Hash a mapping using the frozen canonical JSON encoding."""
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require_hash(value: Any, label: str) -> str:
    """Reject absent or malformed SHA-256 claims."""
    if not isinstance(value, str) or HASH.fullmatch(value) is None:
        raise ValueError(f"invalid recovery SHA-256: {label}")
    return value


def bound_file(run: Path, relative: str, expected: str) -> None:
    """Check a run-relative file without following a linked directory."""
    if not isinstance(relative, str) or not relative or relative.startswith("/"):
        raise ValueError(f"unsafe recovery file path: {relative!r}")
    parts = Path(relative).parts
    if any(part in {"", ".", ".."} for part in parts) or "\\" in relative:
        raise ValueError(f"unsafe recovery file path: {relative!r}")
    current = run
    for part in parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"linked recovery path: {relative}")
    if digest(current) != require_hash(expected, relative):
        raise ValueError(f"recovery file hash differs: {relative}")


def cell_traces(cell: dict[str, Any], identity: str) -> dict[str, str]:
    """Derive the actual trace paths and hashes declared by a saved cell."""
    result: dict[str, str] = {}
    for attempt in cell.get("fit_attempts", []):
        for trace in attempt.get("traces", {}).values():
            relative = f"traces/{identity}/{trace['filename']}"
            if relative in result:
                raise ValueError(f"duplicate recovery trace: {relative}")
            result[relative] = require_hash(trace["sha256"], relative)
    return result


def verify_recovered_lineage(run: Path, *, candidate: dict[str, Any] | None = None) -> dict[str, Any]:
    """Rehash all 1,625 saved producers and the final 411-cell supplement.

    This check is location-independent: recorded source paths are historical
    provenance and are never opened on a receiving computer.
    """
    run = run.resolve()
    manifest_path = run / "manifest.json"
    base_path = run / "recovery_lineage.json"
    final_path = run / "recovery_continuation.json"
    manifest, base = read(manifest_path), read(base_path)
    final = read(final_path) if candidate is None else candidate
    if canonical_hash({k: v for k, v in manifest.items()
                       if k != "manifest_content_sha256"}) != manifest.get("manifest_content_sha256"):
        raise ValueError("recovered manifest content changed")
    if canonical_hash({k: v for k, v in base.items()
                       if k != "content_sha256"}) != base.get("content_sha256"):
        raise ValueError("pre-continuation lineage content changed")
    if canonical_hash({k: v for k, v in final.items()
                       if k != "content_sha256"}) != final.get("content_sha256"):
        raise ValueError("final recovery lineage content changed")
    planned = [entry["cell_id"] for entry in manifest["plan"]]
    payload = base["payload"]
    inherited = payload["producers"]
    pending = payload["pending_cell_ids"]
    new = final["continuation_producers"]
    if (len(planned) != 1625 or len(set(planned)) != 1625
            or len(inherited) != 1214 or len(new) != 411
            or len(pending) != 411 or len(set(pending)) != 411
            or [identity for identity in planned if identity not in inherited] != pending
            or set(new) != set(pending)
            or payload["producer_counts"] !=
            {"intact_original": 1193, "new_refit": 21, "pending": 411}
            or final.get("producer_counts") != COUNTS
            or final.get("schema_version") != 1
            or final.get("status") != "full_recovered_extension_provenance"
            or base.get("status") != "pre_continuation_recovered_extension"
            or final.get("manifest_sha256") != digest(manifest_path)
            or final.get("base_lineage_sha256") != digest(base_path)
            or final.get("assembly_plan_sha256") != base["assembly_plan_sha256"]
            or final.get("controller_plan_sha256") != payload["controller_plan_sha256"]
            or final.get("source_forensic_sha256") != payload["source_forensic_sha256"]
            or final.get("absent_roster_sha256") != payload["absent_roster_sha256"]
            or payload["source_manifest_sha256"] != digest(manifest_path)):
        raise ValueError("recovered producer partition or source bindings differ")
    if ({"intact_original": sum(row.get("producer") == "intact_original"
                                for row in inherited.values()),
         "new_refit": sum(row.get("producer") == "new_refit"
                          for row in inherited.values())} !=
            {"intact_original": 1193, "new_refit": 21}):
        raise ValueError("inherited recovery producer labels differ")
    workers = final["continuation_workers"]
    if not isinstance(workers, list) or len(workers) != 6:
        raise ValueError("six continuation workers are required")
    for worker, record in enumerate(workers):
        expected = [identity for index, identity in enumerate(planned)
                    if index % 6 == worker and identity in new]
        if (record.get("worker") != worker or record.get("cell_ids") != expected
                or len(expected) != SHARD_COUNTS[worker]):
            raise ValueError(f"continuation worker {worker} has the wrong frozen shard")
        for key in ("verified_worker_sha256", "launch_sha256", "return_sha256",
                    "stdout_sha256", "stderr_sha256"):
            require_hash(record.get(key), f"worker {worker}/{key}")
        if any(new[identity]["worker"] != worker for identity in expected):
            raise ValueError(f"continuation producer has wrong worker: {worker}")
    for key in ("continuation_start_sha256", "continuation_complete_sha256"):
        require_hash(final.get(key), key)
    if not isinstance(final.get("continuation_analysis_binding"), dict):
        raise ValueError("continuation analysis binding is absent")
    actual = {path.stem for path in (run / "cells").glob("*.json")}
    if actual != set(planned):
        raise ValueError("recovered cell inventory differs from frozen manifest")
    expected_traces: set[str] = set()
    for identity in planned:
        record = inherited.get(identity, new.get(identity))
        relative = f"cells/{identity}.json"
        bound_file(run, relative, record["cell_file_sha256"])
        cell = read(run / relative)
        if cell.get("cell_id") != identity or cell.get("status") != record["status"]:
            raise ValueError(f"recovered cell identity or status differs: {identity}")
        if identity in new and cell.get("cell_content_sha256") != record["cell_content_sha256"]:
            raise ValueError(f"continuation cell content binding differs: {identity}")
        traces = cell_traces(cell, identity)
        if traces != record["trace_sha256"]:
            raise ValueError(f"recovered trace declaration differs: {identity}")
        for name, value in traces.items():
            bound_file(run, name, value)
        expected_traces.update(traces)
    trace_root = run / "traces"
    actual_traces = {path.relative_to(run).as_posix() for path in trace_root.rglob("*")
                     if path.is_file() or path.is_symlink()} if trace_root.exists() else set()
    if actual_traces != expected_traces:
        raise ValueError("recovered trace inventory contains missing or extra files")
    return {"status": "recovered_lineage_verified",
            "manifest_sha256": digest(manifest_path),
            "base_lineage_sha256": digest(base_path),
            "final_lineage_sha256": digest(final_path) if candidate is None else None,
            "continuation_complete_sha256": final["continuation_complete_sha256"],
            "producer_counts": COUNTS,
            "stored_cells": 1625, "worker_shard_counts": list(SHARD_COUNTS)}


def optional_recovered_lineage(run: Path) -> dict[str, Any] | None:
    """Require the final supplement whenever either recovery marker exists."""
    if not any((run / name).exists() or (run / name).is_symlink()
               for name in ("recovery_lineage.json", "recovery_continuation.json")):
        return None
    return verify_recovered_lineage(run)
