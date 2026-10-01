"""Check fail-closed continuation gates without running a scientific fit."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from scripts import continue_recovered_extension as continuation
from scripts import recover_extension_run as recovery


def fixed_manifest_and_absent() -> tuple[dict, list[str]]:
    """Create the exact six-shard cardinalities without using result scores."""
    planned = [f"cell_{number:04d}" for number in range(1625)]
    pending = {planned[index] for worker, limit in
               enumerate(continuation.EXPECTED_ABSENT_BY_WORKER)
               for index in range(worker, 1625, 6)[:limit]}
    return {"plan": [{"cell_id": identity} for identity in planned]}, [
        identity for identity in planned if identity in pending]


def test_411_roster_has_exact_six_production_shards() -> None:
    manifest, pending = fixed_manifest_and_absent()
    shards = continuation.assigned_pending(manifest, pending)
    assert tuple(map(len, shards)) == continuation.EXPECTED_ABSENT_BY_WORKER
    assert len({identity for shard in shards for identity in shard}) == 411
    with pytest.raises(ValueError, match="manifest order"):
        continuation.assigned_pending(manifest, list(reversed(pending)))
    with pytest.raises(ValueError, match="manifest order"):
        continuation.assigned_pending(manifest, pending[:-1] + pending[:1])


def test_typed_capture_keeps_real_zero_and_nonzero_returns(tmp_path: Path) -> None:
    success = tmp_path / "success"
    continuation.captured_command(success, [sys.executable, "-c", "print('done')"],
                                  tmp_path, os.environ.copy(), {"kind": "fixture"})
    assert recovery.read_json(success / "launch.json")["kind"] == "fixture"
    assert recovery.read_json(success / "return.json")["return_code"] == 0
    assert (success / "stdout.log").read_text().strip() == "done"
    failed = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="returned 3"):
        continuation.captured_command(failed, [sys.executable, "-c", "raise SystemExit(3)"],
                                      tmp_path, os.environ.copy(), {})
    assert recovery.read_json(failed / "return.json")["return_code"] == 3


def test_incomplete_receipt_is_not_counted(tmp_path: Path) -> None:
    receipt = tmp_path / "return.json"
    receipt.write_text("{\n")
    assert continuation.read_ready_json(receipt) is None
    receipt.write_text(json.dumps({"return_code": 0}) + "\n")
    assert continuation.read_ready_json(receipt) == {"return_code": 0}


def test_changed_prior_producer_blocks_next_worker(tmp_path: Path) -> None:
    run = tmp_path / "run"
    cells = run / "cells"
    traces = run / "traces" / "new"
    cells.mkdir(parents=True)
    traces.mkdir(parents=True)
    (cells / "old.json").write_text("original\n")
    (cells / "new.json").write_text("new cell\n")
    (traces / "posterior.nc").write_bytes(b"trace")
    prior = {"new": {"cell_file_sha256": recovery.sha256_file(cells / "new.json"),
                     "trace_sha256": {"traces/new/posterior.nc":
                                      recovery.sha256_file(traces / "posterior.nc")}}}
    continuation.require_exact_cells(run, {"old"}, prior)
    (traces / "posterior.nc").write_bytes(b"changed")
    with pytest.raises(ValueError, match="prior continuation trace changed"):
        continuation.require_exact_cells(run, {"old"}, prior)
    (traces / "posterior.nc").write_bytes(b"trace")
    (cells / "extra.json").write_text("extra\n")
    with pytest.raises(ValueError, match="unexpected or missing cell"):
        continuation.require_exact_cells(run, {"old"}, prior)


def test_successor_waits_for_bound_supervisor_completion(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control = tmp_path / "control"
    capture = control / "captures/sequential-v1"
    capture.mkdir(parents=True)
    repo = tmp_path / "analysis"
    published_path = repo / "coordination/recovery/2026-10-01-sequential-recovery-supervisor-launch.json"
    published_path.parent.mkdir(parents=True)
    monkeypatch.setattr(recovery, "REPO", repo)
    binding = {"analysis_git_commit": "analysis_commit", "supervisor_sha256": "source_hash"}
    plan = {"content_sha256": "plan_hash", "source": str(tmp_path / "original"),
            "shards": [[f"cell_{worker}"] for worker in range(6)]}
    launch_path = control / "captures/sequential-v1.launch.json"
    launch_path.write_text(json.dumps({"pid": 1234, "analysis_git_commit": "analysis_commit",
                                       "supervisor_sha256": "source_hash"}) + "\n")
    (capture / "start.json").write_text(json.dumps({"owner_pid": 1234,
                                                      "plan_sha256": "plan_hash",
                                                      "analysis_binding": binding}) + "\n")
    published_path.write_text(json.dumps({
        "supervisor_launch_sha256": recovery.sha256_file(launch_path),
        "supervisor_start_sha256": recovery.sha256_file(capture / "start.json"),
        "fixed_plan_content_sha256": "plan_hash"}) + "\n")
    completion = {"plan_sha256": "plan_hash", "analysis_binding": binding,
                  "verified_refits": 21, "complete_workers": 6}
    (capture / "complete.json").write_text(json.dumps(completion) + "\n")
    returns = control / "worker_returns"
    returns.mkdir()
    for worker, identities in enumerate(plan["shards"]):
        (returns / f"worker_{worker}.json").write_text(json.dumps({
            "worker": worker, "status": "complete", "cell_ids": identities}) + "\n")
    assert continuation.wait_for_refits(control, plan, 1) == completion
    (returns / "worker_5.json").write_text(json.dumps({
        "worker": 5, "status": "complete", "cell_ids": []}) + "\n")
    with pytest.raises(ValueError, match="fixed-shard return"):
        continuation.wait_for_refits(control, plan, 1)
