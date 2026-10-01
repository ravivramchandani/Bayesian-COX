"""Assemble the verified recovery and run only its 411 fixed absent cells.

This unattended successor waits for the 21-refit supervisor's actual complete
receipt. It uses the frozen six-shard production runner, captures real exits,
and stops on the first unexpected file, claim, result or code binding. Full
deep verification, selected reproduction and release remain separate gates.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import assemble_recovered_extension as adapter
from scripts import recover_extension_run as recovery
from scripts import supervise_extension_recovery as supervisor
from scripts import supervise_extension_recovery_v2 as supervisor_v2

EXPECTED_ABSENT_BY_WORKER = (45, 84, 40, 93, 62, 87)


def read_ready_json(path: Path) -> dict[str, Any] | None:
    """Return a complete write-once JSON receipt, or wait for its writer."""
    if not path.is_file():
        return None
    try:
        return recovery.read_json(path)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def analysis_binding(plan: dict[str, Any], git_dir: Path,
                     expected: dict[str, Any] | None = None,
                     supervisor_version: str = "v1") -> dict[str, Any]:
    """Pin the published analysis checkout across the whole continuation."""
    if supervisor_version == "v1":
        value = supervisor.require_launch_binding(plan, git_dir)
    elif supervisor_version == "v2":
        value = supervisor_v2.analysis_binding(plan, git_dir)
        value["supervisor_version"] = "v2"
    else:
        raise ValueError("unknown recovery supervisor version")
    value["successor_sha256"] = recovery.sha256_file(Path(__file__))
    if expected is not None and value != expected:
        raise ValueError("continuation analysis commit or code changed")
    return value


def wait_for_refits(control: Path, plan: dict[str, Any], poll_seconds: int,
                    supervisor_version: str = "v1") -> dict[str, Any]:
    """Require the prior supervisor's real terminal completion before assembly."""
    if supervisor_version == "v2":
        return wait_for_refits_v2(control, plan, poll_seconds)
    if supervisor_version != "v1":
        raise ValueError("unknown recovery supervisor version")
    capture = control / "captures" / "sequential-v1"
    launch_path = control / "captures/sequential-v1.launch.json"
    launch = recovery.read_json(launch_path)
    start = recovery.read_json(capture / "start.json")
    published = recovery.read_json(recovery.REPO / "coordination/recovery/"
                                   "2026-10-01-sequential-recovery-supervisor-launch.json")
    pid = launch.get("pid")
    if (not isinstance(pid, int) or pid <= 0 or start.get("owner_pid") != pid
            or start.get("plan_sha256") != plan["content_sha256"]
            or launch.get("analysis_git_commit") != start["analysis_binding"]["analysis_git_commit"]
            or launch.get("supervisor_sha256") != start["analysis_binding"]["supervisor_sha256"]
            or published.get("supervisor_launch_sha256") != recovery.sha256_file(launch_path)
            or published.get("supervisor_start_sha256") != recovery.sha256_file(capture / "start.json")
            or published.get("fixed_plan_content_sha256") != plan["content_sha256"]):
        raise ValueError("21-refit supervisor launch does not bind its start")
    while True:
        if (capture / "failure.json").exists():
            raise RuntimeError("21-refit supervisor failed; inspect its retained claim")
        complete = read_ready_json(capture / "complete.json")
        if complete is not None:
            if (complete.get("plan_sha256") != plan["content_sha256"]
                    or complete.get("analysis_binding") != start["analysis_binding"]
                    or complete.get("verified_refits") != 21
                    or complete.get("complete_workers") != 6):
                raise ValueError("21-refit supervisor completion differs from its plan")
            if (control / "sequential_supervisor.claim").exists():
                if not supervisor.process_exists(pid):
                    raise RuntimeError("21-refit supervisor left a claim after completion")
                time.sleep(poll_seconds)
                continue
            adapter.require_no_active_producer(control, Path(plan["source"]))
            for worker, identities in enumerate(plan["shards"]):
                receipt = recovery.read_json(control / "worker_returns" / f"worker_{worker}.json")
                if (receipt.get("worker") != worker or receipt.get("status") != "complete"
                        or receipt.get("cell_ids") != identities):
                    raise ValueError(f"recovery worker {worker} lacks a fixed-shard return")
            return complete
        if not supervisor.process_exists(pid):
            raise RuntimeError("21-refit supervisor vanished without complete or failure receipt")
        time.sleep(poll_seconds)


def require_preserved_v1_chain(control: Path, plan: dict[str, Any],
                               salvage_evidence: dict[str, Any]) -> dict[str, str]:
    """Bind the old failed supervisor, successor, watcher and their dead owners."""
    incident = recovery.read_json(recovery.REPO / "coordination/recovery/"
                                  "2026-10-01-fourth-refit-postfit-salvage.json")
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
        "v1_post_successor_failure": control / "post_successor_captures/sequential-v1/failure.json",
    }
    hashes = {name: supervisor_v2.file_sha(path) for name, path in paths.items()}
    separate = incident.get("separate_salvage", {})
    if (incident.get("control") != str(control)
            or incident.get("plan_file_sha256") != recovery.sha256_file(control / "plan.json")
            or incident.get("plan_content_sha256") != plan["content_sha256"]
            or incident.get("failed_v1_evidence_sha256") != hashes
            or separate.get("proof_sha256") != salvage_evidence["salvage_proof_sha256"]
            or separate.get("complete_sha256") !=
            salvage_evidence["salvage_complete_sha256"]
            or separate.get("old_wrapper_return_remains") != 1
            or separate.get("new_fits_executed") != 0):
        raise ValueError("preserved V1 failure chain differs from incident receipt")
    for name, claim_path, capture_name in (
            ("supervisor", paths["v1_supervisor_claim"], "captures/sequential-v1"),
            ("successor", paths["v1_successor_claim"], "continuation_captures/sequential-v1"),
            ("post-successor", paths["v1_post_successor_claim"],
             "post_successor_captures/sequential-v1")):
        claim = recovery.read_json(claim_path)
        if (claim.get("plan_sha256") != plan["content_sha256"]
                or claim.get("capture_root") != str(control / capture_name)
                or not isinstance(claim.get("pid"), int)
                or claim["pid"] <= 0 or supervisor.process_exists(claim["pid"])):
            raise ValueError(f"retained V1 {name} claim is changed or still active")
    for name in ("v1_supervisor_failure", "v1_successor_failure",
                 "v1_post_successor_failure"):
        failure = recovery.read_json(paths[name])
        if failure.get("claim_retained_for_review",
                       failure.get("supervisor_claim_retained")) is not True:
            raise ValueError(f"retained {name} receipt does not preserve its claim")
    return hashes


def wait_for_refits_v2(control: Path, plan: dict[str, Any],
                       poll_seconds: int) -> dict[str, Any]:
    """Require the published V2 launch, released claim and 21 verified refits."""
    capture = control / "captures/sequential-v2"
    launch_path = control / "captures/sequential-v2.launch.json"
    claim_path = control / supervisor_v2.CLAIM_NAME
    published_path = (recovery.REPO / "coordination/recovery/"
                      "2026-10-01-sequential-recovery-v2-launch.json")
    published = recovery.read_json(published_path)
    launch = recovery.read_json(launch_path)
    start = recovery.read_json(capture / "start.json")
    pid = launch.get("pid")
    runtime = Path(published.get("runtime_checkout", ""))
    source = runtime / "scripts/supervise_extension_recovery_v2.py"
    source_sha256 = recovery.sha256_file(source)
    binding = start.get("analysis_binding")
    if not isinstance(binding, dict):
        raise ValueError("V2 supervisor start lacks its analysis binding")
    expected_command = [
        plan["python"], "-I", "-B", str(source), "--control", str(control),
        "--capture-root", str(capture), "--production-git-dir",
        str(supervisor_v2.MAC_GIT_DIR), "--execute"]
    if (not isinstance(pid, int) or pid <= 0
            or launch.get("argv") != expected_command
            or launch.get("control") != str(control)
            or launch.get("capture_root") != str(capture)
            or launch.get("cwd") != str(supervisor_v2.SAFE_CWD)
            or launch.get("production_git_dir") != str(supervisor_v2.MAC_GIT_DIR)
            or launch.get("plan_file_sha256") != recovery.sha256_file(control / "plan.json")
            or launch.get("v2_supervisor_sha256") != source_sha256
            or launch.get("salvage_proof_sha256") !=
            start.get("salvage_evidence", {}).get("salvage_proof_sha256")
            or launch.get("analysis_git_commit") != binding.get("analysis_git_commit")
            or start.get("owner_pid") != pid
            or start.get("control") != str(control)
            or start.get("plan_sha256") != plan["content_sha256"]
            or start.get("production_git_dir") != str(supervisor_v2.MAC_GIT_DIR)
            or start.get("stable_worker_cwd") != str(supervisor_v2.SAFE_CWD)
            or start.get("initial_refit_ids") != sorted(supervisor_v2.FIRST_FOUR)
            or start.get("remaining_refits") != 17
            or binding.get("v2_supervisor_sha256") != source_sha256
            or source_sha256 != recovery.sha256_file(Path(supervisor_v2.__file__))
            or published.get("schema_version") != 1
            or published.get("control") != str(control)
            or published.get("runtime_checkout") != str(runtime)
            or published.get("independent_frozen_git_dir") !=
            str(supervisor_v2.MAC_GIT_DIR)
            or published.get("fixed_plan_content_sha256") != plan["content_sha256"]
            or published.get("fixed_plan_file_sha256") !=
            recovery.sha256_file(control / "plan.json")
            or published.get("analysis_git_commit") != binding.get("analysis_git_commit")
            or published.get("v2_supervisor_source_sha256") != source_sha256
            or published.get("supervisor_pid_at_checkpoint") != pid
            or published.get("launch_sha256") != recovery.sha256_file(launch_path)
            or published.get("start_sha256") != recovery.sha256_file(capture / "start.json")
            or published.get("salvage_proof_sha256") !=
            start["salvage_evidence"]["salvage_proof_sha256"]
            or published.get("stable_parent_and_worker_cwd") !=
            str(supervisor_v2.SAFE_CWD)
            or published.get("v1_failure_and_claims_preserved") is not True
            or published.get("worker0_terminal_return_sha256") !=
            recovery.sha256_file(capture / "01_worker0_final/return.json")
            or published.get("worker0_terminal_verification_sha256") !=
            recovery.sha256_file(capture / "01_worker0_final/verified_worker.json")):
        raise ValueError("published V2 supervisor launch does not bind its start")
    salvage_evidence = supervisor_v2.require_salvage(control, plan)
    if start["salvage_evidence"] != salvage_evidence:
        raise ValueError("V2 supervisor start does not bind preserved salvage")
    historical = require_preserved_v1_chain(control, plan, salvage_evidence)
    while True:
        if (capture / "failure.json").exists():
            raise RuntimeError("V2 21-refit supervisor failed; inspect its retained claim")
        claim_exists = claim_path.exists()
        if claim_exists:
            claim = recovery.read_json(claim_path)
            if (recovery.sha256_file(claim_path) != published.get("v2_claim_sha256")
                    or claim.get("pid") != pid
                    or claim.get("capture_root") != str(capture)
                    or claim.get("plan_sha256") != plan["content_sha256"]
                    or claim.get("analysis_binding") != binding
                    or claim.get("salvage_proof_sha256") !=
                    salvage_evidence["salvage_proof_sha256"]):
                raise ValueError("active V2 supervisor claim differs from published launch")
        complete = read_ready_json(capture / "complete.json")
        if complete is not None:
            if (complete.get("plan_sha256") != plan["content_sha256"]
                    or complete.get("analysis_binding") != binding
                    or complete.get("salvage_proof_sha256") !=
                    salvage_evidence["salvage_proof_sha256"]
                    or complete.get("initial_verified_refits") != 4
                    or complete.get("new_refits") != 17
                    or complete.get("verified_refits") != 21
                    or complete.get("complete_workers") != 6
                    or complete.get("v1_failure_preserved") is not True):
                raise ValueError("V2 21-refit completion differs from its fixed plan")
            if claim_exists:
                if not supervisor.process_exists(pid):
                    raise RuntimeError("V2 supervisor left a claim after completion")
                time.sleep(poll_seconds)
                continue
            if supervisor_v2.require_salvage(control, plan) != salvage_evidence:
                raise ValueError("preserved V1 failure or salvage changed after V2 completion")
            if require_preserved_v1_chain(control, plan, salvage_evidence) != historical:
                raise ValueError("preserved V1 incident chain changed after V2 completion")
            adapter.require_no_active_producer(control, Path(plan["source"]))
            if supervisor_v2.attempt_roster(control, plan) != set(plan["affected_cell_ids"]):
                raise ValueError("V2 supervisor completed without all fixed first attempts")
            for worker, identities in enumerate(plan["shards"]):
                path = control / "worker_returns" / f"worker_{worker}.json"
                receipt = recovery.read_json(path)
                if (receipt.get("worker") != worker or receipt.get("status") != "complete"
                        or receipt.get("cell_ids") != identities
                        or complete.get("worker_return_sha256", {}).get(str(worker)) !=
                        recovery.sha256_file(path)):
                    raise ValueError(f"V2 worker {worker} lacks its hashed fixed-shard return")
                for identity in identities:
                    supervisor_v2.verified_refit(control, plan, identity)
            return complete
        if not claim_exists:
            raise RuntimeError("V2 supervisor released its claim without completion")
        if not supervisor.process_exists(pid):
            raise RuntimeError("V2 21-refit supervisor vanished without completion")
        time.sleep(poll_seconds)


def captured_command(capture: Path, command: list[str], cwd: Path,
                     environment: dict[str, str], details: dict[str, Any]) -> None:
    """Capture an actual subprocess exit with write-once launch and return files."""
    capture.mkdir(parents=True, exist_ok=False)
    with (capture / "stdout.log").open("x") as stdout, \
            (capture / "stderr.log").open("x") as stderr:
        child = subprocess.Popen(command, cwd=cwd, env=environment,
                                 stdin=subprocess.DEVNULL, stdout=stdout,
                                 stderr=stderr, close_fds=True)
        recovery.write_new_json(capture / "launch.json",
                                {"launched_utc": recovery.utc_now(), "owner_pid": os.getpid(),
                                 "pid": child.pid, "argv": command, "cwd": str(cwd),
                                 **details})
        returned = child.wait()
    recovery.write_new_json(capture / "return.json",
                            {"returned_utc": recovery.utc_now(), "owner_pid": os.getpid(),
                             "pid": child.pid, "return_code": returned})
    if returned != 0:
        raise RuntimeError(f"captured command returned {returned}: {capture}")


def require_assembled_run(control: Path, plan: dict[str, Any], run: Path,
                          assembly_plan: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Recheck the 1,214 producer map and 411 pending identities before fits."""
    from src.pipelines.extensions.runner import verified_cell

    pinned = recovery.read_json(assembly_plan)
    if recovery.content_sha256({k: v for k, v in pinned.items() if k != "content_sha256"}) != pinned["content_sha256"]:
        raise ValueError("assembly plan content changed")
    lineage = recovery.read_json(run / "recovery_lineage.json")
    if (recovery.content_sha256({k: v for k, v in lineage.items() if k != "content_sha256"})
            != lineage["content_sha256"] or lineage.get("payload") != pinned["payload"]
            or lineage.get("assembly_plan_sha256") != pinned["content_sha256"]
            or pinned["payload"]["destination"] != str(run)
            or pinned["payload"]["pending_cell_ids"] != plan["absent_cell_ids"]
            or pinned["payload"]["producer_counts"] !=
            {"intact_original": 1193, "new_refit": 21, "pending": 411}):
        raise ValueError("assembled recovery lineage differs from fixed producer plan")
    receipt = recovery.read_json(control / "assembly_adapter_receipt.json")
    if (receipt.get("destination") != str(run)
            or receipt.get("assembly_plan_sha256") != pinned["content_sha256"]
            or receipt.get("lineage_sha256") != recovery.sha256_file(run / "recovery_lineage.json")
            or receipt.get("manifest_sha256") != recovery.sha256_file(run / "manifest.json")
            or recovery.sha256_file(run / "manifest.json") != plan["source_manifest_sha256"]):
        raise ValueError("assembly receipt or original manifest changed")
    producers = pinned["payload"]["producers"]
    if len(producers) != 1214:
        raise ValueError("assembled producer map is incomplete")
    for identity, record in producers.items():
        cell_path = run / "cells" / f"{identity}.json"
        if cell_path.is_symlink():
            raise ValueError(f"assembled cell is linked: {identity}")
        if recovery.sha256_file(cell_path) != record["cell_file_sha256"]:
            raise ValueError(f"assembled cell differs from pinned producer: {identity}")
        verified_cell(cell_path)
        for relative, digest in record["trace_sha256"].items():
            if (run / relative).is_symlink() or recovery.sha256_file(run / relative) != digest:
                raise ValueError(f"assembled trace differs from pinned producer: {identity}")
    return recovery.read_json(run / "manifest.json"), pinned


def assigned_pending(manifest: dict[str, Any], pending: list[str]) -> list[list[str]]:
    """Derive exactly six production shards from manifest positions."""
    planned = [entry["cell_id"] for entry in manifest["plan"]]
    if (len(planned) != 1625 or len(set(planned)) != 1625
            or len(pending) != 411 or len(set(pending)) != 411
            or [identity for identity in planned if identity in set(pending)] != pending):
        raise ValueError("411 absent identities differ from frozen manifest order")
    result = [[identity for index, identity in enumerate(planned)
               if index % 6 == worker and identity in set(pending)]
              for worker in range(6)]
    if tuple(map(len, result)) != EXPECTED_ABSENT_BY_WORKER:
        raise ValueError("six continuation shards differ from frozen absent roster")
    return result


def verified_new_cells(run: Path, identities: list[str], jobs: dict[str, Any],
                       cohorts: dict[str, Any], base_seed: int) -> dict[str, Any]:
    """Bind saved continuation cells, traces, seeds and patients to fixed jobs."""
    from src.pipelines.extensions.runner import verified_cell
    from src.pipelines.extensions.verification import verify_cell_identity

    cells: dict[str, Any] = {}
    for identity in identities:
        path = run / "cells" / f"{identity}.json"
        if path.is_symlink():
            raise ValueError(f"continuation cell is linked: {identity}")
        cell = verified_cell(path)
        job = jobs[identity]
        verify_cell_identity(cell, job, cohorts[job.dataset], base_seed)
        if cell["status"] not in recovery.TERMINAL_STATUSES:
            raise ValueError(f"unrecognized continuation outcome: {identity}")
        traces = {str(Path("traces") / identity / trace["filename"]): trace["sha256"]
                  for attempt in cell.get("fit_attempts", [])
                  for trace in attempt.get("traces", {}).values()}
        if any((run / relative).is_symlink() for relative in traces):
            raise ValueError(f"continuation trace is linked: {identity}")
        cells[identity] = {"cell_file_sha256": recovery.sha256_file(path),
                           "cell_content_sha256": cell["cell_content_sha256"],
                           "status": cell["status"], "trace_sha256": traces}
    return cells


def require_exact_cells(run: Path, original: set[str], prior: dict[str, Any]) -> None:
    """Reject concurrent or altered producers between fixed worker launches."""
    actual = {path.stem for path in (run / "cells").glob("*.json")}
    if actual != original | set(prior):
        raise ValueError("recovered run contains an unexpected or missing cell")
    for identity, record in prior.items():
        cell_path = run / "cells" / f"{identity}.json"
        if cell_path.is_symlink() or recovery.sha256_file(cell_path) != record["cell_file_sha256"]:
            raise ValueError(f"prior continuation cell changed: {identity}")
        for relative, digest in record["trace_sha256"].items():
            if (run / relative).is_symlink() or recovery.sha256_file(run / relative) != digest:
                raise ValueError(f"prior continuation trace changed: {identity}")


def run(args: argparse.Namespace) -> None:
    """Wait, assemble and sequentially capture the six fixed continuation shards."""
    if not args.execute:
        raise ValueError("continuation requires explicit --execute")
    version = getattr(args, "supervisor_version", "v1")
    if version not in {"v1", "v2"}:
        raise ValueError("unknown recovery supervisor version")
    control, run_root, assembly_plan, capture_root, git_dir = (
        Path(value).resolve() for value in (args.control, args.recovered_run,
        args.assembly_plan, args.capture_root, args.production_git_dir))
    if (not 1 <= args.poll_seconds <= 300 or capture_root.exists()
            or capture_root.parent != control / "continuation_captures"
            or run_root.exists() or assembly_plan.exists()):
        raise ValueError("continuation requires new fixed APFS run, plan and capture roots")
    if (version == "v2"
            and (capture_root != control / "continuation_captures/sequential-v2"
                 or git_dir != supervisor_v2.MAC_GIT_DIR
                 or (control / "continuation_supervisor_v2.claim").exists())):
        raise ValueError("V2 continuation requires its fresh fixed capture and Mac Git metadata")
    plan = recovery.load_plan(control)
    if plan["workers"] != 6 or len(plan["affected_cell_ids"]) != 21:
        raise ValueError("continuation requires the fixed v3 recovery plan")
    if (version == "v2"
            and (recovery.sha256_file(control / "plan.json") !=
                 supervisor_v2.salvage.PLAN_FILE_SHA256
                 or plan["content_sha256"] !=
                 supervisor_v2.salvage.PLAN_CONTENT_SHA256)):
        raise ValueError("V2 continuation requires the exact fixed recovery plan")
    recovery.require_apfs(run_root)
    recovery.require_free_space(run_root, gib=25)
    recovery.require_free_space(Path.home(), gib=20)
    binding = analysis_binding(plan, git_dir, supervisor_version=version)
    capture_root.parent.mkdir(parents=True, exist_ok=True)
    capture_root.mkdir(exist_ok=False)
    claim_path = control / ("continuation_supervisor_v2.claim" if version == "v2"
                            else "continuation_supervisor.claim")
    recovery.claim(claim_path, {"capture_root": str(capture_root),
                                "plan_sha256": plan["content_sha256"],
                                **({"supervisor_version": version} if version == "v2" else {})})
    start = {"started_utc": recovery.utc_now(), "owner_pid": os.getpid(),
             "control": str(control), "recovered_run": str(run_root),
             "assembly_plan": str(assembly_plan),
             "plan_sha256": plan["content_sha256"],
             "analysis_binding": binding, "production_git_dir": str(git_dir)}
    if version == "v2":
        start.update({"supervisor_version": "v2",
                      "supervisor_source_sha256": binding["v2_supervisor_sha256"],
                      "successor_source_sha256": binding["successor_sha256"],
                      "supervisor_launch_sha256": recovery.sha256_file(
                          control / "captures/sequential-v2.launch.json")})
    recovery.write_new_json(capture_root / "start.json", start)
    try:
        supervisor_complete = wait_for_refits(control, plan, args.poll_seconds, version)
        analysis_binding(plan, git_dir, binding, version)
        if run_root.exists() or assembly_plan.exists():
            raise ValueError("another producer created the recovered run or assembly plan")
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("GIT_")}
        python = plan["python"]
        script = str(recovery.REPO / "scripts/assemble_recovered_extension.py")
        captured_command(capture_root / "assembly_preflight",
                         [python, "-B", script, "preflight", "--control", str(control),
                          "--recovered-run", str(run_root), "--assembly-plan", str(assembly_plan),
                          "--production-git-dir", str(git_dir)], recovery.REPO,
                         environment, {"analysis_binding": binding})
        analysis_binding(plan, git_dir, binding, version)
        captured_command(capture_root / "assembly",
                         [python, "-B", script, "assemble", "--control", str(control),
                          "--assembly-plan", str(assembly_plan),
                          "--production-git-dir", str(git_dir)], recovery.REPO,
                         environment, {"analysis_binding": binding})
        manifest, assembled_plan = require_assembled_run(control, plan, run_root, assembly_plan)
        shards = assigned_pending(manifest, plan["absent_cell_ids"])
        config, cohorts, jobs = adapter.validated_jobs(manifest, Path(plan["sealed"]),
                                                       Path(plan["matched"]))
        original = set(assembled_plan["payload"]["producers"])
        previous: dict[str, Any] = {}
        for worker, identities in enumerate(shards):
            analysis_binding(plan, git_dir, binding, version)
            if (list((run_root / "claims").glob("*.json"))
                    or list((control / "worker_claims").glob("*.json"))
                    or list((control / "cell_claims").glob("*.json"))):
                raise ValueError("another continuation or recovery producer holds a claim")
            recovery.require_free_space(run_root, gib=25)
            recovery.require_free_space(Path.home(), gib=20)
            require_assembled_run(control, plan, run_root, assembly_plan)
            require_exact_cells(run_root, original, previous)
            worker_env = environment.copy()
            worker_env.update({"GIT_DIR": str(git_dir), "GIT_WORK_TREE": plan["sealed"],
                               "GIT_OPTIONAL_LOCKS": "0", "PYTHONNOUSERSITE": "1",
                               "PYTHONDONTWRITEBYTECODE": "1"})
            for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                        "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
                worker_env[key] = "1"
            command = ["/usr/bin/caffeinate", "-dimsu", "/usr/bin/nice", "-n", "10",
                       python, "-B", str(Path(plan["sealed"]) / "scripts/run_extensions.py"),
                       "--matched", plan["matched"], "--output", str(run_root),
                       "--workers", "6", "--worker", str(worker)]
            capture = capture_root / f"worker_{worker}"
            captured_command(capture, command,
                             supervisor_v2.SAFE_CWD if version == "v2" else Path(plan["sealed"]),
                             worker_env,
                             {"analysis_binding": binding, "worker": worker,
                              "expected_cell_ids": identities,
                              "production_runner_sha256": recovery.sha256_file(
                                  Path(plan["sealed"]) / "scripts/run_extensions.py"),
                              "git_environment": {key: worker_env[key] for key in
                                                  ("GIT_DIR", "GIT_WORK_TREE", "GIT_OPTIONAL_LOCKS")},
                              "thread_limit": 1,
                              "assembly_plan_sha256": assembled_plan["content_sha256"]})
            analysis_binding(plan, git_dir, binding, version)
            if (list((run_root / "claims").glob("*.json"))
                    or list((control / "worker_claims").glob("*.json"))
                    or list((control / "cell_claims").glob("*.json"))):
                raise ValueError("producer claim remained after captured worker return")
            require_assembled_run(control, plan, run_root, assembly_plan)
            newly = verified_new_cells(run_root, identities, jobs, cohorts, config["base_seed"])
            require_exact_cells(run_root, original, previous | newly)
            record = {"worker": worker, "plan_sha256": plan["content_sha256"],
                      "assembly_plan_sha256": assembled_plan["content_sha256"],
                      "analysis_binding": binding, "expected_cell_ids": identities,
                      "cell_producers": newly,
                      "status_counts": dict(Counter(row["status"] for row in newly.values())),
                      "launch_sha256": recovery.sha256_file(capture / "launch.json"),
                      "return_sha256": recovery.sha256_file(capture / "return.json"),
                      "stdout_sha256": recovery.sha256_file(capture / "stdout.log"),
                      "stderr_sha256": recovery.sha256_file(capture / "stderr.log"),
                      "verified_utc": recovery.utc_now()}
            recovery.write_new_json(capture / "verified_worker.json", record)
            previous.update(newly)
        require_exact_cells(run_root, original, previous)
        if len(previous) != 411 or len(list((run_root / "cells").glob("*.json"))) != 1625:
            raise ValueError("all six workers returned but the fixed 1,625-cell grid is absent")
        complete = {"completed_utc": recovery.utc_now(),
                    "status": "full_grid_stored_pending_deep_verification",
                    "plan_sha256": plan["content_sha256"],
                    "assembly_plan_sha256": assembled_plan["content_sha256"],
                    "analysis_binding": binding, "stored": 1625,
                    "new_continuation_cells": 411,
                    "verified_worker_sha256": {
                        str(worker): recovery.sha256_file(
                            capture_root / f"worker_{worker}/verified_worker.json")
                        for worker in range(6)}}
        if version == "v2":
            complete.update({"supervisor_version": "v2",
                             "supervisor_source_sha256": binding["v2_supervisor_sha256"],
                             "successor_source_sha256": binding["successor_sha256"],
                             "supervisor_launch_sha256": start["supervisor_launch_sha256"],
                             "supervisor_complete_sha256": recovery.sha256_file(
                                 control / "captures/sequential-v2/complete.json"),
                             "salvage_proof_sha256":
                             supervisor_complete["salvage_proof_sha256"],
                             "v1_failure_preserved": True})
        recovery.write_new_json(capture_root / "complete.json", complete)
        claim_path.unlink()
    except BaseException as exc:
        recovery.write_new_json(capture_root / "failure.json",
                                {"failed_utc": recovery.utc_now(),
                                 "error_type": type(exc).__name__, "error": str(exc),
                                 "claim_retained_for_review": True})
        raise


def main() -> None:
    """Require explicit fixed paths and intent for the long numerical sequence."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("control", "recovered-run", "assembly-plan", "capture-root",
                 "production-git-dir"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--supervisor-version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--execute", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
