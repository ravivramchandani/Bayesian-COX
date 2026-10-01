"""Invented V2 receipt contracts; no numerical work is started."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from scripts import seal_recovered_extension_lineage as sealer
from scripts.extension_release import recovery_lineage as lineage


def write(path: Path, value: dict[str, Any]) -> None:
    """Write one small synthetic capture at a fixed test path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def invented_v2_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                      ) -> tuple[Path, dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Build linked V1 failure, no-fit salvage, V2 and successor receipts."""
    repo, control = tmp_path / "repo", tmp_path / "control"
    monkeypatch.setattr(sealer.recovery, "REPO", repo)
    plan = {"python": "/locked/python", "content_sha256": "a" * 64,
            "sealed": str(tmp_path / "sealed"),
            "matched": str(tmp_path / "matched.parquet"),
            "shards": [[f"cell_{worker}"] for worker in range(6)]}
    plan["absent_cell_ids"] = [row[0] for row in plan["shards"]]
    write(control / "plan.json", plan)
    worker_hashes = {}
    for worker, identities in enumerate(plan["shards"]):
        path = control / "worker_returns" / f"worker_{worker}.json"
        write(path, {"worker": worker, "status": "complete", "cell_ids": identities})
        worker_hashes[str(worker)] = lineage.digest(path)

    identity = "fourth"
    incident_hashes = {}
    for name, relative in sealer.V1_INCIDENT_FILES.items():
        path = control / relative.format(identity=identity)
        write(path, {"historical": name})
        incident_hashes[name] = lineage.digest(path)
    salvage = control / "captures/no-fit-salvage-r01f03-v1"
    refit_proof = {"child_return_code": 0}
    salvage_proof = {"cell_id": identity,
                     "status": "fourth_refit_postfit_comparison_salvaged",
                     "new_fits_executed": 0, "old_wrapper_return_code": 1,
                     "saved_fit_child_return_code": 0,
                     "new_comparison_child_return_code": 0,
                     "official_refit_proof": refit_proof}
    salvage_proof["content_sha256"] = lineage.canonical_hash(salvage_proof)
    write(salvage / "proof.json", salvage_proof)
    salvage_sha = lineage.digest(salvage / "proof.json")
    write(salvage / "complete.json", {"proof_sha256": salvage_sha,
                                       "plan_content_sha256": plan["content_sha256"],
                                       "new_fits_executed": 0})
    incident = {"schema_version": 1, "control": str(control),
                "plan_file_sha256": lineage.digest(control / "plan.json"),
                "plan_content_sha256": plan["content_sha256"],
                "failed_v1_evidence_sha256": incident_hashes,
                "separate_salvage": {"proof_sha256": salvage_sha,
                                     "complete_sha256": lineage.digest(salvage / "complete.json"),
                                     "new_fits_executed": 0,
                                     "old_wrapper_return_remains": 1}}
    write(repo / "coordination/recovery" / sealer.V2_INCIDENT_PUBLISHED, incident)

    supervisor_capture = control / "captures/sequential-v2"
    supervisor_binding = {"analysis_git_commit": "1" * 40,
                          "v2_supervisor_sha256": "2" * 64}
    git_dir = "/frozen/git/.git"
    supervisor_start = {"owner_pid": 123, "control": str(control),
                        "plan_sha256": plan["content_sha256"],
                        "production_git_dir": git_dir, "stable_worker_cwd": "/private/tmp",
                        "remaining_refits": 17,
                        "initial_refit_ids": ["first", "second", "third", identity],
                        "analysis_binding": supervisor_binding,
                        "salvage_evidence": {"salvage_proof_sha256": salvage_sha,
                                             "fourth_refit": {
                                                 "official_refit_proof": refit_proof},
                                             "old_failed_capture_sha256": {
                                                 "v1_supervisor_failure":
                                                 incident_hashes["v1_supervisor_failure"]}}}
    write(supervisor_capture / "start.json", supervisor_start)
    supervisor_launch = {"pid": 123, "control": str(control),
                         "capture_root": str(supervisor_capture),
                         "production_git_dir": git_dir, "cwd": "/private/tmp",
                         "analysis_git_commit": supervisor_binding["analysis_git_commit"],
                         "v2_supervisor_sha256": supervisor_binding["v2_supervisor_sha256"],
                         "salvage_proof_sha256": salvage_sha,
                         "plan_file_sha256": lineage.digest(control / "plan.json"),
                         "argv": ["/locked/python", "-I", "-B",
                                  "/v2-runtime/scripts/supervise_extension_recovery_v2.py",
                                  "--control", str(control), "--capture-root",
                                  str(supervisor_capture), "--production-git-dir", git_dir,
                                  "--execute"]}
    supervisor_launch_path = control / "captures/sequential-v2.launch.json"
    write(supervisor_launch_path, supervisor_launch)
    supervisor_complete = {"analysis_binding": supervisor_binding,
                           "plan_sha256": plan["content_sha256"],
                           "salvage_proof_sha256": salvage_sha,
                           "initial_verified_refits": 4, "new_refits": 17,
                           "verified_refits": 21, "complete_workers": 6,
                           "v1_failure_preserved": True,
                           "worker_return_sha256": worker_hashes}
    write(supervisor_capture / "complete.json", supervisor_complete)
    write(supervisor_capture / "01_worker0_final/return.json", {"return_code": 0})
    write(supervisor_capture / "01_worker0_final/verified_worker.json", {"worker": 0})
    write(supervisor_capture / "02_worker1_cell/launch.json", {"worker": 1})
    supervisor_claim_snapshot = control / "captures/sequential-v2.claim-at-launch.json"
    write(supervisor_claim_snapshot, {"capture_root": str(supervisor_capture)})
    supervisor_published = {"schema_version": 1, "control": str(control),
                            "runtime_checkout": "/v2-runtime",
                            "fixed_plan_file_sha256": lineage.digest(control / "plan.json"),
                            "fixed_plan_content_sha256": plan["content_sha256"],
                            "launch_sha256": lineage.digest(supervisor_launch_path),
                            "start_sha256": lineage.digest(supervisor_capture / "start.json"),
                            "supervisor_pid_at_checkpoint": 123,
                            "v2_supervisor_source_sha256":
                            supervisor_binding["v2_supervisor_sha256"],
                            "analysis_git_commit": supervisor_binding["analysis_git_commit"],
                            "salvage_proof_sha256": salvage_sha,
                            "independent_frozen_git_dir": git_dir,
                            "stable_parent_and_worker_cwd": "/private/tmp",
                            "v1_failure_and_claims_preserved": True,
                            "v2_claim_sha256": lineage.digest(supervisor_claim_snapshot),
                            "worker0_terminal_return_sha256": lineage.digest(
                                supervisor_capture / "01_worker0_final/return.json"),
                            "worker0_terminal_verification_sha256": lineage.digest(
                                supervisor_capture / "01_worker0_final/verified_worker.json"),
                            "worker1_fit_launch_sha256": lineage.digest(
                                supervisor_capture / "02_worker1_cell/launch.json")}
    supervisor_published_path = (repo / "coordination/recovery" /
                                 sealer.V2_SUPERVISOR_PUBLISHED)
    write(supervisor_published_path, supervisor_published)

    successor_capture = control / "continuation_captures/sequential-v2"
    successor_binding = {"analysis_git_commit": "3" * 40,
                         "successor_sha256": "4" * 64,
                         "v2_supervisor_sha256": supervisor_binding["v2_supervisor_sha256"],
                         "supervisor_version": "v2"}
    start = {"owner_pid": 456, "control": str(control),
             "recovered_run": str(tmp_path / "recovered"),
             "assembly_plan": str(control / "assembly_adapter_plan_v2.json"),
             "plan_sha256": plan["content_sha256"],
             "production_git_dir": git_dir,
             "analysis_binding": successor_binding, "supervisor_version": "v2",
             "supervisor_source_sha256": supervisor_binding["v2_supervisor_sha256"],
             "successor_source_sha256": successor_binding["successor_sha256"],
             "supervisor_launch_sha256": lineage.digest(supervisor_launch_path)}
    write(successor_capture / "start.json", start)
    successor_claim_snapshot = control / "continuation_captures/sequential-v2.claim-at-launch.json"
    write(successor_claim_snapshot, {"capture_root": str(successor_capture)})
    successor_launch_path = control / "continuation_captures/sequential-v2.launch.json"
    write(successor_launch_path, {"pid": 456, "control": str(control),
                                  "capture_root": str(successor_capture),
                                  "recovered_run": start["recovered_run"],
                                  "assembly_plan": start["assembly_plan"],
                                  "production_git_dir": git_dir, "cwd": "/private/tmp",
                                  "plan_file_sha256": lineage.digest(control / "plan.json"),
                                  "analysis_git_commit": successor_binding["analysis_git_commit"],
                                  "successor_sha256": successor_binding["successor_sha256"],
                                  "supervisor_launch_sha256": lineage.digest(supervisor_launch_path),
                                  "argv": ["/locked/python", "-I", "-B",
                                           "/successor-runtime/scripts/continue_recovered_extension.py",
                                           "--supervisor-version", "v2", "--control",
                                           str(control), "--recovered-run", start["recovered_run"],
                                           "--assembly-plan", start["assembly_plan"],
                                           "--capture-root", str(successor_capture),
                                           "--production-git-dir", git_dir,
                                           "--poll-seconds", "60", "--execute"]})
    successor_published = {"schema_version": 1, "control": str(control),
                           "runtime_checkout": "/successor-runtime",
                           "recovered_run": start["recovered_run"],
                           "assembly_plan": start["assembly_plan"],
                           "fixed_plan_file_sha256": lineage.digest(control / "plan.json"),
                           "fixed_plan_content_sha256": plan["content_sha256"],
                           "successor_launch_sha256": lineage.digest(successor_launch_path),
                           "successor_start_sha256": lineage.digest(successor_capture / "start.json"),
                           "successor_pid_at_checkpoint": 456,
                           "successor_source_sha256": successor_binding["successor_sha256"],
                           "analysis_git_commit": successor_binding["analysis_git_commit"],
                           "supervisor_launch_sha256": lineage.digest(supervisor_launch_path),
                           "supervisor_published_launch_sha256":
                           lineage.digest(supervisor_published_path),
                           "v1_failed_chain_preserved": True}
    successor_published["successor_claim_sha256_at_checkpoint"] = lineage.digest(
        successor_claim_snapshot)
    write(repo / "coordination/recovery" / sealer.V2_CONTINUATION_PUBLISHED,
          successor_published)
    complete = {"supervisor_version": "v2", "v1_failure_preserved": True,
                "status": "full_grid_stored_pending_deep_verification",
                "plan_sha256": plan["content_sha256"],
                "assembly_plan_sha256": "b" * 64,
                "analysis_binding": successor_binding,
                "stored": 1625, "new_continuation_cells": 411,
                "supervisor_source_sha256": supervisor_binding["v2_supervisor_sha256"],
                "successor_source_sha256": successor_binding["successor_sha256"],
                "supervisor_launch_sha256": lineage.digest(supervisor_launch_path),
                "supervisor_complete_sha256": lineage.digest(
                    supervisor_capture / "complete.json"),
                "salvage_proof_sha256": salvage_sha}
    return control, plan, start, complete


def test_v2_seal_accepts_retained_v1_failure_and_rejects_changed_link(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Only the successful V2 claim must clear; V1 failures stay preserved."""
    control, plan, start, complete = invented_v2_chain(tmp_path, monkeypatch)
    result = sealer.require_v2_source_receipts(control, plan, start, complete)
    assert result["salvage_proof_sha256"] == complete["salvage_proof_sha256"]
    assert (control / "sequential_supervisor.claim").exists()
    changed = dict(complete)
    changed["supervisor_complete_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="does not bind its predecessor"):
        sealer.require_v2_source_receipts(control, plan, start, changed)
    claim = control / "sequential_supervisor_v2.claim"
    write(claim, {"unfinished": True})
    with pytest.raises(ValueError, match="claim remains incomplete"):
        sealer.require_v2_source_receipts(control, plan, start, complete)
    claim.unlink()
    failure = control / "continuation_captures/sequential-v1/failure.json"
    write(failure, {"historical": "changed"})
    with pytest.raises(ValueError, match="preserved V1 failure"):
        sealer.require_v2_source_receipts(control, plan, start, complete)


def test_v2_seal_requires_saved_launch_claim_bytes(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A successful controller removes live claims, so preserve their launch bytes."""
    control, plan, start, complete = invented_v2_chain(tmp_path, monkeypatch)
    claim = control / "captures/sequential-v2.claim-at-launch.json"
    write(claim, {"capture_root": "changed"})
    with pytest.raises(ValueError, match="published V2 supervisor launch"):
        sealer.require_v2_source_receipts(control, plan, start, complete)
    control, plan, start, complete = invented_v2_chain(tmp_path / "second", monkeypatch)
    claim = control / "continuation_captures/sequential-v2.claim-at-launch.json"
    write(claim, {"capture_root": "changed"})
    with pytest.raises(ValueError, match="published V2 continuation claim"):
        sealer.require_v2_source_receipts(control, plan, start, complete)


def test_v2_lineage_selects_new_capture_and_stable_worker_cwd(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A retained failed V1 watcher cannot block a complete V2 source seal."""
    control, plan, start, complete = invented_v2_chain(tmp_path, monkeypatch)
    run = Path(start["recovered_run"])
    write(run / "manifest.json", {"fixture": "invented"})
    write(run / "recovery_lineage.json", {"fixture": "invented"})
    capture = control / "continuation_captures/sequential-v2"
    write(capture / "complete.json", complete)
    runner = Path(plan["sealed"]) / "scripts/run_extensions.py"
    runner.parent.mkdir(parents=True)
    runner.write_text("# frozen runner fixture\n", encoding="utf-8")
    manifest = {"fixture": "invented"}
    assembled = {"content_sha256": "b" * 64,
                 "payload": {"producers": {}, "source_forensic_sha256": "c" * 64,
                             "absent_roster_sha256": "d" * 64}}
    monkeypatch.setattr(sealer.recovery, "load_plan", lambda _: plan)
    monkeypatch.setattr(sealer.continuation, "require_assembled_run",
                        lambda *_: (manifest, assembled))
    monkeypatch.setattr(sealer.continuation, "assigned_pending",
                        lambda *_: plan["shards"])
    monkeypatch.setattr(sealer.adapter, "validated_jobs",
                        lambda *_: ({"base_seed": 7}, {}, {}))
    monkeypatch.setattr(sealer.continuation, "verified_new_cells",
                        lambda _run, identities, *_: {
                            identity: {"status": "complete", "cell_file_sha256": "e" * 64,
                                       "cell_content_sha256": "f" * 64, "trace_sha256": {}}
                            for identity in identities})
    monkeypatch.setattr(sealer.continuation, "require_exact_cells", lambda *_: None)
    verified_hashes = {}
    for worker, identities in enumerate(plan["shards"]):
        folder = capture / f"worker_{worker}"
        (folder / "stdout.log").parent.mkdir(parents=True, exist_ok=True)
        (folder / "stdout.log").write_text("invented success\n", encoding="utf-8")
        (folder / "stderr.log").write_text("", encoding="utf-8")
        launch = {"owner_pid": start["owner_pid"], "pid": 1000 + worker,
                  "worker": worker, "expected_cell_ids": identities,
                  "analysis_binding": start["analysis_binding"],
                  "assembly_plan_sha256": assembled["content_sha256"],
                  "argv": ["/usr/bin/caffeinate", "-dimsu", "/usr/bin/nice", "-n", "10",
                           plan["python"], "-B", str(runner), "--matched", plan["matched"],
                           "--output", str(run), "--workers", "6", "--worker", str(worker)],
                  "cwd": "/private/tmp", "thread_limit": 1,
                  "production_runner_sha256": lineage.digest(runner)}
        write(folder / "launch.json", launch)
        write(folder / "return.json", {"owner_pid": start["owner_pid"],
                                       "pid": 1000 + worker, "return_code": 0})
        actual = sealer.continuation.verified_new_cells(run, identities, {}, {}, 7)
        receipt = {"worker": worker, "expected_cell_ids": identities,
                   "analysis_binding": start["analysis_binding"],
                   "assembly_plan_sha256": assembled["content_sha256"],
                   "plan_sha256": plan["content_sha256"],
                   "cell_producers": actual, "status_counts": {"complete": 1},
                   "launch_sha256": lineage.digest(folder / "launch.json"),
                   "return_sha256": lineage.digest(folder / "return.json"),
                   "stdout_sha256": lineage.digest(folder / "stdout.log"),
                   "stderr_sha256": lineage.digest(folder / "stderr.log")}
        write(folder / "verified_worker.json", receipt)
        verified_hashes[str(worker)] = lineage.digest(folder / "verified_worker.json")
    complete["verified_worker_sha256"] = verified_hashes
    write(capture / "complete.json", complete)
    result = sealer.source_lineage(control, run, "v2")
    assert result["supervisor_version"] == "v2"
    assert result["v2_source_sha256"]["salvage_proof_sha256"] == \
        complete["salvage_proof_sha256"]
    assert len(result["continuation_producers"]) == 6
    assert (control / "continuation_supervisor.claim").is_file()
    launch_path = capture / "worker_5/launch.json"
    launch = lineage.read(launch_path)
    launch["cwd"] = plan["sealed"]
    write(launch_path, launch)
    with pytest.raises(ValueError, match="zero-return proof"):
        sealer.source_lineage(control, run, "v2")
