"""Invented V2 successor receipts; never start numerical workers."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import continue_recovered_extension as successor
from scripts import recover_extension_run as recovery
from scripts import supervise_extension_recovery_v2 as supervisor_v2


def write(path: Path, value: dict[str, Any]) -> None:
    """Create a deterministic invented receipt."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def v2_receipts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                ) -> tuple[Path, dict[str, Any], Path, Path, dict[str, Any]]:
    """Make a matching published launch, start, completion, and six returns."""
    control = tmp_path / "control"
    capture = control / "captures/sequential-v2"
    capture.mkdir(parents=True)
    repo = tmp_path / "analysis"
    monkeypatch.setattr(recovery, "REPO", repo)
    git_dir = tmp_path / "frozen-git/.git"
    git_dir.mkdir(parents=True)
    monkeypatch.setattr(supervisor_v2, "MAC_GIT_DIR", git_dir)
    monkeypatch.setattr(supervisor_v2, "SAFE_CWD", tmp_path)
    plan = {"python": sys.executable, "content_sha256": "fixed_plan",
            "source": str(tmp_path / "source"),
            "affected_cell_ids": [f"cell_{worker}" for worker in range(6)],
            "shards": [[f"cell_{worker}"] for worker in range(6)]}
    write(control / "plan.json", {"invented": True})
    source = Path(supervisor_v2.__file__)
    source_sha256 = recovery.sha256_file(source)
    binding = {"analysis_git_commit": "a" * 40,
               "v2_supervisor_sha256": source_sha256}
    salvage_evidence = {"salvage_proof_sha256": "b" * 64,
                        "salvage_complete_sha256": "d" * 64,
                        "old_failed_capture_sha256": {"v1_supervisor_failure": "c" * 64}}
    start = {"owner_pid": 12345, "control": str(control),
             "plan_sha256": plan["content_sha256"], "analysis_binding": binding,
             "production_git_dir": str(git_dir), "stable_worker_cwd": str(tmp_path),
             "initial_refit_ids": sorted(supervisor_v2.FIRST_FOUR),
             "remaining_refits": 17, "salvage_evidence": salvage_evidence}
    write(capture / "start.json", start)
    launch = {"pid": 12345, "argv": [
        sys.executable, "-I", "-B", str(source), "--control", str(control),
        "--capture-root", str(capture), "--production-git-dir", str(git_dir), "--execute"],
        "control": str(control), "capture_root": str(capture), "cwd": str(tmp_path),
        "production_git_dir": str(git_dir),
        "plan_file_sha256": recovery.sha256_file(control / "plan.json"),
        "v2_supervisor_sha256": source_sha256,
        "salvage_proof_sha256": salvage_evidence["salvage_proof_sha256"],
        "analysis_git_commit": binding["analysis_git_commit"]}
    launch_path = control / "captures/sequential-v2.launch.json"
    write(launch_path, launch)
    worker_hashes = {}
    for worker, identities in enumerate(plan["shards"]):
        path = control / "worker_returns" / f"worker_{worker}.json"
        write(path, {"worker": worker, "status": "complete", "cell_ids": identities})
        worker_hashes[str(worker)] = recovery.sha256_file(path)
    write(capture / "01_worker0_final/return.json", {"return_code": 0})
    write(capture / "01_worker0_final/verified_worker.json", {"worker": 0})
    completion = {"plan_sha256": plan["content_sha256"], "analysis_binding": binding,
                  "salvage_proof_sha256": salvage_evidence["salvage_proof_sha256"],
                  "initial_verified_refits": 4, "new_refits": 17,
                  "verified_refits": 21, "complete_workers": 6,
                  "v1_failure_preserved": True, "worker_return_sha256": worker_hashes}
    write(capture / "complete.json", completion)
    claim = {"pid": 12345, "capture_root": str(capture),
             "plan_sha256": plan["content_sha256"], "analysis_binding": binding,
             "salvage_proof_sha256": salvage_evidence["salvage_proof_sha256"]}
    claim_path = control / supervisor_v2.CLAIM_NAME
    write(claim_path, claim)
    claim_sha256 = recovery.sha256_file(claim_path)
    claim_path.unlink()
    published = {
        "schema_version": 1, "control": str(control),
        "runtime_checkout": str(source.parents[1]),
        "independent_frozen_git_dir": str(git_dir),
        "fixed_plan_content_sha256": plan["content_sha256"],
        "fixed_plan_file_sha256": recovery.sha256_file(control / "plan.json"),
        "analysis_git_commit": binding["analysis_git_commit"],
        "v2_supervisor_source_sha256": source_sha256,
        "supervisor_pid_at_checkpoint": 12345,
        "launch_sha256": recovery.sha256_file(launch_path),
        "start_sha256": recovery.sha256_file(capture / "start.json"),
        "salvage_proof_sha256": salvage_evidence["salvage_proof_sha256"],
        "stable_parent_and_worker_cwd": str(tmp_path),
        "v1_failure_and_claims_preserved": True,
        "worker0_terminal_return_sha256":
        recovery.sha256_file(capture / "01_worker0_final/return.json"),
        "worker0_terminal_verification_sha256":
        recovery.sha256_file(capture / "01_worker0_final/verified_worker.json"),
        "v2_claim_sha256": claim_sha256}
    published_path = (repo / "coordination/recovery/"
                      "2026-10-01-sequential-recovery-v2-launch.json")
    write(published_path, published)
    monkeypatch.setattr(supervisor_v2, "require_salvage",
                        lambda *_args: salvage_evidence)
    monkeypatch.setattr(supervisor_v2, "attempt_roster",
                        lambda *_args: set(plan["affected_cell_ids"]))
    monkeypatch.setattr(supervisor_v2, "verified_refit",
                        lambda *_args: {"verified": True})
    monkeypatch.setattr(successor.adapter, "require_no_active_producer",
                        lambda *_args: None)
    monkeypatch.setattr(successor, "require_preserved_v1_chain",
                        lambda *_args: {"preserved": "yes"})
    return control, plan, published_path, claim_path, completion


def test_v2_waiter_accepts_only_published_completed_supervisor(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control, plan, published_path, _, completion = v2_receipts(tmp_path, monkeypatch)
    assert successor.wait_for_refits(control, plan, 1, "v2") == completion
    worker = control / "worker_returns/worker_5.json"
    write(worker, {"worker": 5, "status": "complete", "cell_ids": []})
    with pytest.raises(ValueError, match="hashed fixed-shard return"):
        successor.wait_for_refits(control, plan, 1, "v2")
    write(worker, {"worker": 5, "status": "complete", "cell_ids": plan["shards"][5]})
    published = recovery.read_json(published_path)
    published["launch_sha256"] = "0" * 64
    write(published_path, published)
    with pytest.raises(ValueError, match="published V2 supervisor launch"):
        successor.wait_for_refits(control, plan, 1, "v2")


def test_v2_waiter_blocks_retained_claim_failure_and_dead_owner(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control, plan, _, claim_path, _ = v2_receipts(tmp_path, monkeypatch)
    capture = control / "captures/sequential-v2"
    claim = {"pid": 12345, "capture_root": str(capture),
             "plan_sha256": plan["content_sha256"],
             "analysis_binding": recovery.read_json(capture / "start.json")["analysis_binding"],
             "salvage_proof_sha256": "b" * 64}
    write(claim_path, claim)
    monkeypatch.setattr(successor.supervisor, "process_exists", lambda _: False)
    with pytest.raises(RuntimeError, match="left a claim after completion"):
        successor.wait_for_refits(control, plan, 1, "v2")
    (capture / "complete.json").unlink()
    with pytest.raises(RuntimeError, match="vanished without completion"):
        successor.wait_for_refits(control, plan, 1, "v2")
    write(capture / "failure.json", {"error": "invented stop"})
    with pytest.raises(RuntimeError, match="supervisor failed"):
        successor.wait_for_refits(control, plan, 1, "v2")


def test_v2_historical_gate_preserves_failed_claims_and_dead_owners(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control = tmp_path / "control"
    repo = tmp_path / "analysis"
    monkeypatch.setattr(recovery, "REPO", repo)
    plan = {"content_sha256": "fixed_plan"}
    write(control / "plan.json", {"invented": True})
    paths = {
        "fourth_child_return": control / "refits" / supervisor_v2.salvage.IDENTITY /
        "attempt_001/child_return.json",
        "fourth_wrapper_return": control / "captures/worker00_ramp2/return.json",
        "fourth_wrapper_stderr": control / "captures/worker00_ramp2/worker.stderr.log",
        "v1_supervisor_claim": control / "sequential_supervisor.claim",
        "v1_supervisor_failure": control / "captures/sequential-v1/failure.json",
        "v1_successor_claim": control / "continuation_supervisor.claim",
        "v1_successor_failure": control / "continuation_captures/sequential-v1/failure.json",
        "v1_post_successor_claim": control / "post_successor_stage.claim",
        "v1_post_successor_failure":
        control / "post_successor_captures/sequential-v1/failure.json"}
    for name in ("fourth_child_return", "fourth_wrapper_return", "fourth_wrapper_stderr"):
        write(paths[name], {"invented": name})
    for number, (kind, key, directory) in enumerate((
            ("supervisor", "v1_supervisor_claim", "captures/sequential-v1"),
            ("successor", "v1_successor_claim", "continuation_captures/sequential-v1"),
            ("post-successor", "v1_post_successor_claim",
             "post_successor_captures/sequential-v1")), 11):
        assert kind
        write(paths[key], {"pid": number, "capture_root": str(control / directory),
                           "plan_sha256": plan["content_sha256"]})
    for name in ("v1_supervisor_failure", "v1_successor_failure",
                 "v1_post_successor_failure"):
        write(paths[name], {"claim_retained_for_review": True})
    hashes = {name: recovery.sha256_file(path) for name, path in paths.items()}
    salvage = {"salvage_proof_sha256": "a" * 64, "salvage_complete_sha256": "b" * 64}
    incident = {"control": str(control),
                "plan_file_sha256": recovery.sha256_file(control / "plan.json"),
                "plan_content_sha256": plan["content_sha256"],
                "failed_v1_evidence_sha256": hashes,
                "separate_salvage": {"proof_sha256": salvage["salvage_proof_sha256"],
                                     "complete_sha256": salvage["salvage_complete_sha256"],
                                     "old_wrapper_return_remains": 1,
                                     "new_fits_executed": 0}}
    write(repo / "coordination/recovery/2026-10-01-fourth-refit-postfit-salvage.json",
          incident)
    monkeypatch.setattr(successor.supervisor, "process_exists", lambda _: False)
    assert successor.require_preserved_v1_chain(control, plan, salvage) == hashes
    write(paths["v1_successor_failure"], {"claim_retained_for_review": False})
    with pytest.raises(ValueError, match="incident receipt"):
        successor.require_preserved_v1_chain(control, plan, salvage)
    write(paths["v1_successor_failure"], {"claim_retained_for_review": True})
    monkeypatch.setattr(successor.supervisor, "process_exists", lambda pid: pid == 12)
    with pytest.raises(ValueError, match="successor claim is changed or still active"):
        successor.require_preserved_v1_chain(control, plan, salvage)


def test_v1_default_binding_and_wait_signature_remain_available(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(successor.supervisor, "require_launch_binding",
                        lambda *_: {"analysis_git_commit": "v1"})
    binding = successor.analysis_binding({}, tmp_path)
    assert binding["analysis_git_commit"] == "v1"
    assert "supervisor_version" not in binding
    with pytest.raises(ValueError, match="unknown recovery supervisor version"):
        successor.wait_for_refits(tmp_path, {}, 1, "v3")


def test_v2_successor_uses_distinct_claim_and_records_versioned_sources(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control = tmp_path / "control"
    git_dir = tmp_path / "frozen-git/.git"
    git_dir.mkdir(parents=True)
    monkeypatch.setattr(supervisor_v2, "MAC_GIT_DIR", git_dir)
    write(control / "plan.json", {"invented": True})
    write(control / "captures/sequential-v2.launch.json", {"invented": "launch"})
    plan = {"workers": 6, "affected_cell_ids": [f"cell_{i}" for i in range(21)],
            "content_sha256": supervisor_v2.salvage.PLAN_CONTENT_SHA256}
    monkeypatch.setattr(recovery, "load_plan", lambda _: plan)
    monkeypatch.setattr(recovery, "require_apfs", lambda _: None)
    monkeypatch.setattr(recovery, "require_free_space", lambda *_args, **_kwargs: None)
    original_hash = recovery.sha256_file
    monkeypatch.setattr(recovery, "sha256_file",
                        lambda path: (supervisor_v2.salvage.PLAN_FILE_SHA256
                                      if Path(path).name == "plan.json"
                                      else original_hash(path)))
    binding = {"v2_supervisor_sha256": "a" * 64,
               "successor_sha256": "b" * 64}

    def bound(_plan: dict[str, Any], _git_dir: Path,
              _expected: dict[str, Any] | None = None,
              supervisor_version: str = "v1") -> dict[str, Any]:
        assert supervisor_version == "v2"
        return binding

    def stop(_control: Path, _plan: dict[str, Any], _poll: int,
             version: str) -> dict[str, Any]:
        assert version == "v2"
        raise RuntimeError("bounded invented stop before assembly")

    monkeypatch.setattr(successor, "analysis_binding", bound)
    monkeypatch.setattr(successor, "wait_for_refits", stop)
    capture_root = control / "continuation_captures/sequential-v2"
    with pytest.raises(RuntimeError, match="bounded invented stop"):
        successor.run(SimpleNamespace(
            execute=True, supervisor_version="v2", control=control,
            recovered_run=tmp_path / "recovered", assembly_plan=tmp_path / "assembly.json",
            capture_root=capture_root, production_git_dir=git_dir, poll_seconds=1))
    start = recovery.read_json(capture_root / "start.json")
    assert start["supervisor_version"] == "v2"
    assert start["supervisor_source_sha256"] == binding["v2_supervisor_sha256"]
    assert start["successor_source_sha256"] == binding["successor_sha256"]
    assert start["supervisor_launch_sha256"] == original_hash(
        control / "captures/sequential-v2.launch.json")
    assert (control / "continuation_supervisor_v2.claim").is_file()
    assert not (control / "continuation_supervisor.claim").exists()
    assert (capture_root / "failure.json").is_file()
