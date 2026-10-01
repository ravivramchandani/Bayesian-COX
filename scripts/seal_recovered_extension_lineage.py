"""Seal 411 continuation producers after captured workers actually finish."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import assemble_recovered_extension as adapter
from scripts import continue_recovered_extension as continuation
from scripts import recover_extension_run as recovery
from scripts.extension_release.recovery_lineage import digest, read, verify_recovered_lineage

V2_SUPERVISOR_PUBLISHED = "2026-10-01-sequential-recovery-v2-launch.json"
V2_CONTINUATION_PUBLISHED = "2026-10-01-recovered-extension-continuation-v2-launch.json"
V2_INCIDENT_PUBLISHED = "2026-10-01-fourth-refit-postfit-salvage.json"
V1_INCIDENT_FILES = {
    "fourth_child_return": "refits/{identity}/attempt_001/child_return.json",
    "fourth_wrapper_return": "captures/worker00_ramp2/return.json",
    "fourth_wrapper_stderr": "captures/worker00_ramp2/worker.stderr.log",
    "v1_supervisor_claim": "sequential_supervisor.claim",
    "v1_supervisor_failure": "captures/sequential-v1/failure.json",
    "v1_successor_claim": "continuation_supervisor.claim",
    "v1_successor_failure": "continuation_captures/sequential-v1/failure.json",
    "v1_post_successor_claim": "post_successor_stage.claim",
    "v1_post_successor_failure": "post_successor_captures/sequential-v1/failure.json",
}


def require_v2_source_receipts(control: Path, plan: dict[str, Any],
                               start: dict[str, Any], complete: dict[str, Any]
                               ) -> dict[str, str]:
    """Bind the successful V2 sequence without relabelling failed V1 attempts."""
    supervisor_capture = control / "captures/sequential-v2"
    successor_capture = control / "continuation_captures/sequential-v2"
    if (not (supervisor_capture / "complete.json").is_file()
            or (supervisor_capture / "failure.json").exists()
            or (control / "sequential_supervisor_v2.claim").exists()
            or (control / "continuation_supervisor_v2.claim").exists()):
        raise ValueError("V2 supervisor or continuation claim remains incomplete")
    supervisor_launch_path = control / "captures/sequential-v2.launch.json"
    successor_launch_path = control / "continuation_captures/sequential-v2.launch.json"
    published_root = recovery.REPO / "coordination/recovery"
    supervisor_launch = read(supervisor_launch_path)
    supervisor_start = read(supervisor_capture / "start.json")
    supervisor_complete = read(supervisor_capture / "complete.json")
    supervisor_published = read(published_root / V2_SUPERVISOR_PUBLISHED)
    successor_launch = read(successor_launch_path)
    successor_published = read(published_root / V2_CONTINUATION_PUBLISHED)
    incident = read(published_root / V2_INCIDENT_PUBLISHED)
    salvage_capture = control / "captures/no-fit-salvage-r01f03-v1"
    salvage_proof = read(salvage_capture / "proof.json")
    salvage_complete = read(salvage_capture / "complete.json")
    supervisor_binding = supervisor_start.get("analysis_binding")
    successor_binding = start.get("analysis_binding")
    if not isinstance(supervisor_binding, dict) or not isinstance(successor_binding, dict):
        raise ValueError("V2 capture lacks an analysis binding")
    supervisor_sha = supervisor_binding.get("v2_supervisor_sha256")
    successor_sha = successor_binding.get("successor_sha256")
    salvage_sha = digest(salvage_capture / "proof.json")
    supervisor_launch_sha = digest(supervisor_launch_path)
    supervisor_complete_sha = digest(supervisor_capture / "complete.json")
    successor_launch_sha = digest(successor_launch_path)
    supervisor_claim_snapshot_sha = digest(control / "captures/sequential-v2.claim-at-launch.json")
    successor_claim_snapshot_sha = digest(
        control / "continuation_captures/sequential-v2.claim-at-launch.json")
    expected_supervisor_command = [
        plan["python"], "-I", "-B",
        str(Path(supervisor_published["runtime_checkout"]) /
            "scripts/supervise_extension_recovery_v2.py"),
        "--control", str(control), "--capture-root", str(supervisor_capture),
        "--production-git-dir", supervisor_start["production_git_dir"], "--execute",
    ]
    expected_successor_command = [
        plan["python"], "-I", "-B",
        str(Path(successor_published["runtime_checkout"]) /
            "scripts/continue_recovered_extension.py"),
        "--supervisor-version", "v2", "--control", str(control),
        "--recovered-run", start["recovered_run"],
        "--assembly-plan", start["assembly_plan"],
        "--capture-root", str(successor_capture),
        "--production-git-dir", start["production_git_dir"],
        "--poll-seconds", "60", "--execute",
    ]
    if (supervisor_launch.get("argv") != expected_supervisor_command
            or supervisor_launch.get("control") != str(control)
            or supervisor_launch.get("capture_root") != str(supervisor_capture)
            or supervisor_launch.get("cwd") != "/private/tmp"
            or supervisor_launch.get("production_git_dir") !=
            supervisor_start["production_git_dir"]
            or supervisor_launch.get("plan_file_sha256") != digest(control / "plan.json")
            or supervisor_launch.get("pid") != supervisor_start.get("owner_pid")
            or supervisor_launch.get("analysis_git_commit") !=
            supervisor_binding.get("analysis_git_commit")
            or supervisor_launch.get("v2_supervisor_sha256") != supervisor_sha
            or supervisor_launch.get("salvage_proof_sha256") != salvage_sha
            or supervisor_start.get("control") != str(control)
            or supervisor_start.get("plan_sha256") != plan["content_sha256"]
            or supervisor_start.get("stable_worker_cwd") != "/private/tmp"
            or supervisor_start.get("remaining_refits") != 17
            or len(supervisor_start.get("initial_refit_ids", [])) != 4
            or supervisor_start.get("salvage_evidence", {}).get("salvage_proof_sha256") !=
            salvage_sha
            or supervisor_complete.get("analysis_binding") != supervisor_binding
            or supervisor_complete.get("plan_sha256") != plan["content_sha256"]
            or supervisor_complete.get("salvage_proof_sha256") != salvage_sha
            or supervisor_complete.get("initial_verified_refits") != 4
            or supervisor_complete.get("new_refits") != 17
            or supervisor_complete.get("verified_refits") != 21
            or supervisor_complete.get("complete_workers") != 6
            or supervisor_complete.get("v1_failure_preserved") is not True):
        raise ValueError("V2 supervisor source receipts differ")
    for worker, identities in enumerate(plan["shards"]):
        worker_path = control / "worker_returns" / f"worker_{worker}.json"
        if (supervisor_complete.get("worker_return_sha256", {}).get(str(worker)) !=
                digest(worker_path)
                or read(worker_path).get("cell_ids") != identities):
            raise ValueError(f"V2 fixed-shard worker {worker} return differs")
    if (supervisor_published.get("schema_version") != 1
            or supervisor_published.get("control") != str(control)
            or supervisor_published.get("fixed_plan_file_sha256") !=
            digest(control / "plan.json")
            or supervisor_published.get("fixed_plan_content_sha256") !=
            plan["content_sha256"]
            or supervisor_published.get("launch_sha256") != supervisor_launch_sha
            or supervisor_published.get("start_sha256") !=
            digest(supervisor_capture / "start.json")
            or supervisor_published.get("supervisor_pid_at_checkpoint") !=
            supervisor_start["owner_pid"]
            or supervisor_published.get("v2_supervisor_source_sha256") != supervisor_sha
            or supervisor_published.get("analysis_git_commit") !=
            supervisor_binding["analysis_git_commit"]
            or supervisor_published.get("salvage_proof_sha256") != salvage_sha
            or supervisor_published.get("independent_frozen_git_dir") !=
            supervisor_start["production_git_dir"]
            or supervisor_published.get("stable_parent_and_worker_cwd") !=
            supervisor_start["stable_worker_cwd"]
            or supervisor_published.get("v1_failure_and_claims_preserved") is not True
            or supervisor_published.get("v2_claim_sha256") !=
            supervisor_claim_snapshot_sha
            or supervisor_published.get("worker0_terminal_return_sha256") !=
            digest(supervisor_capture / "01_worker0_final/return.json")
            or supervisor_published.get("worker0_terminal_verification_sha256") !=
            digest(supervisor_capture / "01_worker0_final/verified_worker.json")
            or supervisor_published.get("worker1_fit_launch_sha256") !=
            digest(supervisor_capture / "02_worker1_cell/launch.json")):
        raise ValueError("published V2 supervisor launch differs")
    if (successor_launch.get("argv") != expected_successor_command
            or successor_launch.get("control") != str(control)
            or successor_launch.get("capture_root") != str(successor_capture)
            or successor_launch.get("recovered_run") != start["recovered_run"]
            or successor_launch.get("assembly_plan") != start["assembly_plan"]
            or successor_launch.get("production_git_dir") != start["production_git_dir"]
            or successor_launch.get("cwd") != "/private/tmp"
            or successor_launch.get("pid") != start.get("owner_pid")
            or successor_launch.get("plan_file_sha256") != digest(control / "plan.json")
            or successor_launch.get("analysis_git_commit") !=
            successor_binding.get("analysis_git_commit")
            or successor_launch.get("successor_sha256") != successor_sha
            or successor_launch.get("supervisor_launch_sha256") != supervisor_launch_sha
            or successor_published.get("schema_version") != 1
            or successor_published.get("successor_launch_sha256") != successor_launch_sha
            or successor_published.get("successor_start_sha256") !=
            digest(successor_capture / "start.json")
            or successor_published.get("successor_pid_at_checkpoint") != start["owner_pid"]
            or successor_published.get("successor_source_sha256") != successor_sha
            or successor_published.get("analysis_git_commit") !=
            successor_binding["analysis_git_commit"]
            or successor_published.get("supervisor_launch_sha256") !=
            supervisor_launch_sha
            or successor_published.get("supervisor_published_launch_sha256") !=
            digest(published_root / V2_SUPERVISOR_PUBLISHED)
            or successor_published.get("fixed_plan_file_sha256") !=
            digest(control / "plan.json")
            or successor_published.get("fixed_plan_content_sha256") !=
            plan["content_sha256"]
            or successor_published.get("control") != str(control)
            or successor_published.get("recovered_run") != start["recovered_run"]
            or successor_published.get("assembly_plan") != start["assembly_plan"]
            or successor_published.get("v1_failed_chain_preserved") is not True):
        raise ValueError("published V2 continuation launch differs")
    if (successor_published.get("successor_claim_sha256_at_checkpoint") !=
            successor_claim_snapshot_sha):
        raise ValueError("published V2 continuation claim differs")
    incident_hashes = {
        name: digest(control / relative.format(identity=salvage_proof["cell_id"]))
        for name, relative in V1_INCIDENT_FILES.items()
    }
    if (incident.get("schema_version") != 1
            or incident.get("control") != str(control)
            or incident.get("plan_file_sha256") != digest(control / "plan.json")
            or incident.get("plan_content_sha256") != plan["content_sha256"]
            or incident.get("failed_v1_evidence_sha256") != incident_hashes
            or incident.get("separate_salvage", {}).get("proof_sha256") != salvage_sha
            or incident.get("separate_salvage", {}).get("complete_sha256") !=
            digest(salvage_capture / "complete.json")
            or incident.get("separate_salvage", {}).get("new_fits_executed") != 0
            or incident.get("separate_salvage", {}).get("old_wrapper_return_remains") != 1
            or salvage_complete.get("proof_sha256") != salvage_sha
            or salvage_complete.get("plan_content_sha256") != plan["content_sha256"]
            or salvage_complete.get("new_fits_executed") != 0
            or salvage_proof.get("content_sha256") != recovery.content_sha256({
                key: value for key, value in salvage_proof.items()
                if key != "content_sha256"})
            or salvage_proof.get("status") != "fourth_refit_postfit_comparison_salvaged"
            or salvage_proof.get("new_fits_executed") != 0
            or salvage_proof.get("old_wrapper_return_code") != 1
            or salvage_proof.get("saved_fit_child_return_code") != 0
            or salvage_proof.get("new_comparison_child_return_code") != 0
            or salvage_proof.get("official_refit_proof") !=
            supervisor_start["salvage_evidence"]["fourth_refit"]["official_refit_proof"]
            or supervisor_start["salvage_evidence"].get("old_failed_capture_sha256", {}).get(
                "v1_supervisor_failure") != incident_hashes["v1_supervisor_failure"]):
        raise ValueError("preserved V1 failure or no-fit salvage differs")
    if (start.get("supervisor_version") != "v2"
            or complete.get("supervisor_version") != "v2"
            or successor_binding.get("supervisor_version") != "v2"
            or start.get("supervisor_source_sha256") != supervisor_sha
            or complete.get("supervisor_source_sha256") != supervisor_sha
            or start.get("successor_source_sha256") != successor_sha
            or complete.get("successor_source_sha256") != successor_sha
            or start.get("supervisor_launch_sha256") != supervisor_launch_sha
            or complete.get("supervisor_launch_sha256") != supervisor_launch_sha
            or complete.get("supervisor_complete_sha256") != supervisor_complete_sha
            or complete.get("salvage_proof_sha256") != salvage_sha
            or complete.get("v1_failure_preserved") is not True):
        raise ValueError("V2 continuation does not bind its predecessor")
    return {"supervisor_launch_sha256": supervisor_launch_sha,
            "supervisor_start_sha256": digest(supervisor_capture / "start.json"),
            "supervisor_complete_sha256": supervisor_complete_sha,
            "supervisor_published_launch_sha256":
            digest(published_root / V2_SUPERVISOR_PUBLISHED),
            "supervisor_claim_at_launch_sha256": supervisor_claim_snapshot_sha,
            "successor_launch_sha256": successor_launch_sha,
            "successor_published_launch_sha256":
            digest(published_root / V2_CONTINUATION_PUBLISHED),
            "successor_claim_at_launch_sha256": successor_claim_snapshot_sha,
            "incident_sha256": digest(published_root / V2_INCIDENT_PUBLISHED),
            "salvage_proof_sha256": salvage_sha,
            "salvage_complete_sha256": digest(salvage_capture / "complete.json")}


def source_lineage(control: Path, run: Path,
                   supervisor_version: str = "v1") -> dict[str, Any]:
    """Reconstruct the final lineage from six real worker exits and saved cells."""
    if supervisor_version not in {"v1", "v2"}:
        raise ValueError("unknown recovery supervisor version")
    plan = recovery.load_plan(control)
    assembly_path = control / f"assembly_adapter_plan_{supervisor_version}.json"
    capture = control / "continuation_captures" / f"sequential-{supervisor_version}"
    claim_name = ("continuation_supervisor_v2.claim" if supervisor_version == "v2"
                  else "continuation_supervisor.claim")
    if (not (capture / "complete.json").is_file() or (capture / "failure.json").exists()
            or (control / claim_name).exists()
            or list((run / "claims").glob("*.json"))
            or list((control / "worker_claims").glob("*.json"))
            or list((control / "cell_claims").glob("*.json"))):
        raise ValueError("continuation is incomplete or a producer claim remains")
    manifest, assembled = continuation.require_assembled_run(control, plan, run, assembly_path)
    start, complete = (recovery.read_json(capture / name) for name in
                       ("start.json", "complete.json"))
    binding = start["analysis_binding"]
    if (start.get("control") != str(control)
            or start.get("recovered_run") != str(run)
            or start.get("assembly_plan") != str(assembly_path)
            or start.get("plan_sha256") != plan["content_sha256"]
            or complete.get("status") != "full_grid_stored_pending_deep_verification"
            or complete.get("plan_sha256") != plan["content_sha256"]
            or complete.get("assembly_plan_sha256") != assembled["content_sha256"]
            or complete.get("analysis_binding") != binding
            or complete.get("stored") != 1625
            or complete.get("new_continuation_cells") != 411):
        raise ValueError("continuation start or completion differs from fixed plan")
    v2_source = (require_v2_source_receipts(control, plan, start, complete)
                 if supervisor_version == "v2" else None)
    shards = continuation.assigned_pending(manifest, plan["absent_cell_ids"])
    config, cohorts, jobs = adapter.validated_jobs(manifest, Path(plan["sealed"]),
                                                   Path(plan["matched"]))
    worker_records = []
    new_producers: dict[str, dict[str, Any]] = {}
    for worker, identities in enumerate(shards):
        folder = capture / f"worker_{worker}"
        launch, returned, verified = (recovery.read_json(folder / name) for name in
                                      ("launch.json", "return.json", "verified_worker.json"))
        actual = continuation.verified_new_cells(run, identities, jobs, cohorts,
                                                 config["base_seed"])
        receipt_hash = recovery.sha256_file(folder / "verified_worker.json")
        runner = Path(plan["sealed"]) / "scripts/run_extensions.py"
        expected_argv = ["/usr/bin/caffeinate", "-dimsu", "/usr/bin/nice", "-n", "10",
                         plan["python"], "-B", str(runner), "--matched", plan["matched"],
                         "--output", str(run), "--workers", "6", "--worker", str(worker)]
        if (not isinstance(start.get("owner_pid"), int)
                or launch.get("owner_pid") != start["owner_pid"]
                or returned.get("owner_pid") != start["owner_pid"]
                or returned.get("pid") != launch.get("pid")
                or returned.get("return_code") != 0
                or launch.get("worker") != worker
                or launch.get("expected_cell_ids") != identities
                or launch.get("analysis_binding") != binding
                or launch.get("assembly_plan_sha256") != assembled["content_sha256"]
                or launch.get("argv") != expected_argv
                or launch.get("cwd") != ("/private/tmp" if supervisor_version == "v2"
                                              else plan["sealed"])
                or launch.get("thread_limit") != 1
                or launch.get("production_runner_sha256") != recovery.sha256_file(runner)
                or verified.get("worker") != worker
                or verified.get("expected_cell_ids") != identities
                or verified.get("cell_producers") != actual
                or verified.get("plan_sha256") != plan["content_sha256"]
                or verified.get("assembly_plan_sha256") != assembled["content_sha256"]
                or verified.get("analysis_binding") != binding
                or verified.get("status_counts") !=
                dict(Counter(record["status"] for record in actual.values()))
                or verified.get("launch_sha256") != recovery.sha256_file(folder / "launch.json")
                or verified.get("return_sha256") != recovery.sha256_file(folder / "return.json")
                or verified.get("stdout_sha256") != recovery.sha256_file(folder / "stdout.log")
                or verified.get("stderr_sha256") != recovery.sha256_file(folder / "stderr.log")
                or complete.get("verified_worker_sha256", {}).get(str(worker)) != receipt_hash):
            raise ValueError(f"continuation worker {worker} lacks bound zero-return proof")
        for identity, record in actual.items():
            new_producers[identity] = {"worker": worker, **record}
        worker_records.append({"worker": worker, "cell_ids": identities,
                               "verified_worker_sha256": receipt_hash,
                               "launch_sha256": verified["launch_sha256"],
                               "return_sha256": verified["return_sha256"],
                               "stdout_sha256": verified["stdout_sha256"],
                               "stderr_sha256": verified["stderr_sha256"]})
    original = set(assembled["payload"]["producers"])
    continuation.require_exact_cells(run, original, {
        identity: {k: record[k] for k in ("cell_file_sha256", "trace_sha256")}
        for identity, record in new_producers.items()})
    result = {"schema_version": 1,
              "status": "full_recovered_extension_provenance",
              "manifest_sha256": recovery.sha256_file(run / "manifest.json"),
              "base_lineage_sha256": recovery.sha256_file(run / "recovery_lineage.json"),
              "assembly_plan_sha256": assembled["content_sha256"],
              "controller_plan_sha256": plan["content_sha256"],
              "source_forensic_sha256": assembled["payload"]["source_forensic_sha256"],
              "absent_roster_sha256": assembled["payload"]["absent_roster_sha256"],
              "continuation_start_sha256": recovery.sha256_file(capture / "start.json"),
              "continuation_complete_sha256": recovery.sha256_file(capture / "complete.json"),
              "continuation_analysis_binding": binding,
              "producer_counts": {"intact_original": 1193, "new_refit": 21,
                                  "new_continuation": 411},
              "continuation_workers": worker_records,
              "continuation_producers": new_producers}
    if v2_source is not None:
        result["supervisor_version"] = "v2"
        result["v2_source_sha256"] = v2_source
    result["content_sha256"] = recovery.content_sha256(result)
    return result


def main() -> None:
    """Write a new supplement only after the complete source proof passes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--supervisor-version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--verify-only", action="store_true",
                        help="recompute actual producer proof without writing")
    args = parser.parse_args()
    control, run = args.control.resolve(), args.run.resolve()
    target = run / "recovery_continuation.json"
    if args.verify_only:
        stored_version = recovery.read_json(target).get("supervisor_version", "v1")
        if stored_version != args.supervisor_version:
            raise ValueError("stored recovery supervisor version differs from requested proof")
    result = source_lineage(control, run, args.supervisor_version)
    if args.verify_only:
        if recovery.read_json(target) != result:
            raise ValueError("stored final lineage differs from actual source proof")
        print(json.dumps(verify_recovered_lineage(run), sort_keys=True))
        return
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    verify_recovered_lineage(run, candidate=result)
    recovery.write_new_json(target, result)
    print(verify_recovered_lineage(run))


if __name__ == "__main__":
    main()
