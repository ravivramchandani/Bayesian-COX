"""Run the remaining fixed trace-recovery refits one at a time with receipts.

This operational wrapper never selects a scientific cell. It follows the
sealed controller's six shards and stops at the first failed evidence gate.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import assemble_recovered_extension as adapter
from scripts import recover_extension_run as recovery

PRIOR_LAUNCH_RECEIPT = (recovery.REPO / "coordination/recovery/"
                        "2026-10-01-fourth-extension-recovery-launch.json")


def process_exists(pid: int) -> bool:
    """Check whether the captured owner process is still present."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def worker_command(plan: dict[str, Any], control: Path, worker: int,
                   max_new_cells: int) -> list[str]:
    """Build only the published fixed-controller worker invocation."""
    return ["/usr/bin/caffeinate", "-dimsu", "/usr/bin/nice", "-n", "10",
            plan["python"], "-B", str(recovery.REPO / "scripts/recover_extension_run.py"),
            "run-worker", "--control", str(control), "--worker", str(worker),
            "--max-new-cells", str(max_new_cells), "--execute"]


def wait_for_capture(capture: Path, expected_cell: str, control: Path,
                     plan: dict[str, Any], git_dir: Path, binding: dict[str, Any],
                     poll_seconds: int) -> None:
    """Wait for a pre-existing first attempt without taking over its claim."""
    launch = recovery.read_json(capture / "launch.json")
    pid = launch.get("wrapper_pid")
    if not isinstance(pid, int) or pid <= 0 or launch.get("cwd") != str(recovery.REPO):
        raise ValueError("prior capture does not bind the expected owner and checkout")
    if (launch.get("command") != worker_command(plan, control, 0, 1)
            or launch.get("git_dir") != str(git_dir)
            or launch.get("git_work_tree") != plan["sealed"]
            or expected_cell not in plan["shards"][0]):
        raise ValueError("prior capture does not bind the fixed recovery dispatch")
    launch_receipt = recovery.read_json(PRIOR_LAUNCH_RECEIPT)
    wrapper_start = recovery.read_json(capture / "wrapper_start.json")
    if (launch_receipt.get("capture_directory") != str(capture)
            or launch_receipt.get("control") != str(control)
            or launch_receipt.get("cell_id") != expected_cell
            or launch_receipt.get("control_plan_sha256") != recovery.sha256_file(control / "plan.json")
            or recovery.sha256_file(capture / "capture.py") != launch_receipt.get("capture_script_sha256")
            or recovery.sha256_file(capture / "launch.json") != launch_receipt.get("launch_sha256")
            or recovery.sha256_file(capture / "wrapper_start.json") != launch_receipt.get("wrapper_start_sha256")
            or wrapper_start.get("wrapper_pid") != pid
            or wrapper_start.get("expected_cell_id") != expected_cell):
        raise ValueError("prior capture differs from its published launch receipt")
    return_path = capture / "return.json"
    while True:
        try:
            returned = recovery.read_json(return_path) if return_path.is_file() else None
        except (json.JSONDecodeError, UnicodeDecodeError):
            returned = None
        if returned is not None:
            break
        if not process_exists(pid):
            if not return_path.is_file():
                raise RuntimeError("prior capture owner vanished without a typed return")
            returned = recovery.read_json(return_path)
            break
        time.sleep(poll_seconds)
    if (returned.get("wrapper_pid") != pid
            or returned.get("caffeinate_pid") != launch.get("caffeinate_pid")
            or returned.get("return_code") != 0):
        raise RuntimeError("prior captured worker did not return zero")
    require_launch_binding(plan, git_dir, binding)
    require_completed_refit(control, plan, expected_cell)


def require_completed_refit(control: Path, plan: dict[str, Any], identity: str) -> dict[str, Any]:
    """Rehash every new trace and bind the cell to its first child and comparison."""
    from src.pipelines.extensions.runner import verified_cell

    attempt = control / "refits" / identity / "attempt_001"
    refit_file = attempt / "run" / "cells" / f"{identity}.json"
    source_file = Path(plan["source"]) / "cells" / f"{identity}.json"
    cell = verified_cell(refit_file)
    return adapter.require_refit_proof(control, plan, identity, source_file, refit_file, cell)


def require_idle(control: Path, plan: dict[str, Any]) -> None:
    """Reject any concurrent source, refit or assembly producer before launch."""
    adapter.require_no_active_producer(control, Path(plan["source"]))
    recovery.require_free_space(control, gib=15)


def require_launch_binding(plan: dict[str, Any], git_dir: Path,
                           expected: dict[str, Any] | None = None) -> dict[str, Any]:
    """Verify clean analysis code and the frozen production tree before fitting."""
    controller = recovery.REPO / "scripts/recover_extension_run.py"
    if recovery.sha256_file(controller) != plan["controller_sha256"]:
        raise ValueError("numerical controller differs from sealed plan")
    head = adapter.require_clean_published_adapter(recovery.REPO)
    source = Path(plan["source"])
    manifest = recovery.read_json(source / "manifest.json")
    if recovery.sha256_file(source / "manifest.json") != plan["source_manifest_sha256"]:
        raise ValueError("original extension manifest changed")
    adapter.require_production_root(manifest, Path(plan["sealed"]), git_dir)
    recovery.require_environment(Path(plan["python"]), Path(plan["sealed"]),
                                 Path(plan["environment_receipt"]))
    binding = {"analysis_git_commit": head,
               "supervisor_sha256": recovery.sha256_file(Path(__file__)),
               "analysis_code_sha256": {name: recovery.sha256_file(recovery.REPO / name)
                                        for name in adapter.ANALYSIS_FILES}}
    if expected is not None and binding != expected:
        raise ValueError("supervisor analysis commit or code changed during recovery")
    return binding


def run_captured_worker(capture: Path, control: Path, plan: dict[str, Any],
                        git_dir: Path, binding: dict[str, Any], worker: int, max_new_cells: int,
                        expected_cell: str | None) -> None:
    """Launch exactly one fixed controller call and save its real process exit."""
    if (max_new_cells != 1 or not 0 <= worker < plan["workers"]
            or expected_cell is not None and expected_cell not in plan["shards"][worker]):
        raise ValueError("supervisor permits only one bounded fixed-shard worker call")
    require_idle(control, plan)
    require_launch_binding(plan, git_dir, binding)
    prior_proofs = ({identity: require_completed_refit(control, plan, identity)
                     for identity in plan["shards"][worker]}
                    if expected_cell is None else None)
    capture.mkdir(parents=True, exist_ok=False)
    command = worker_command(plan, control, worker, max_new_cells)
    environment = os.environ.copy()
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
                "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
        environment[key] = "1"
    environment.update({"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
                        "GIT_DIR": str(git_dir), "GIT_WORK_TREE": plan["sealed"],
                        "GIT_OPTIONAL_LOCKS": "0"})
    with (capture / "worker.stdout.log").open("x") as stdout, \
            (capture / "worker.stderr.log").open("x") as stderr:
        child = subprocess.Popen(command, cwd=recovery.REPO, env=environment,
                                 stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                 close_fds=True)
        recovery.write_new_json(capture / "launch.json",
                                {"timestamp_utc": recovery.utc_now(), "owner_pid": os.getpid(),
                                 "caffeinate_pid": child.pid, "command": command,
                                 "cwd": str(recovery.REPO), "worker": worker,
                                 "expected_cell": expected_cell,
                                 "controller_sha256": plan["controller_sha256"],
                                 "plan_sha256": plan["content_sha256"],
                                 "analysis_binding": binding,
                                 "git_dir": str(git_dir), "git_work_tree": plan["sealed"]})
        result = child.wait()
    recovery.write_new_json(capture / "return.json",
                            {"timestamp_utc": recovery.utc_now(), "owner_pid": os.getpid(),
                             "caffeinate_pid": child.pid, "return_code": result})
    if result != 0:
        raise RuntimeError(f"captured worker {worker} returned {result}")
    require_launch_binding(plan, git_dir, binding)
    if expected_cell is not None:
        proof = require_completed_refit(control, plan, expected_cell)
        recovery.write_new_json(capture / "verified_refit.json",
                                {"cell_id": expected_cell, "proof": proof,
                                 "analysis_binding": binding,
                                 "verified_utc": recovery.utc_now()})
    else:
        if ({identity: require_completed_refit(control, plan, identity)
             for identity in plan["shards"][worker]} != prior_proofs):
            raise ValueError(f"worker {worker} attempts changed during terminal receipt")
        receipt_path = control / "worker_returns" / f"worker_{worker}.json"
        receipt = recovery.read_json(receipt_path)
        if (receipt.get("worker") != worker or receipt.get("status") != "complete"
                or receipt.get("cell_ids") != plan["shards"][worker]):
            raise ValueError(f"worker {worker} lacks its complete fixed-shard receipt")
        recovery.write_new_json(capture / "verified_worker.json",
                                {"worker": worker, "analysis_binding": binding,
                                 "worker_return_sha256":
                                 recovery.sha256_file(receipt_path),
                                 "verified_utc": recovery.utc_now()})


def run(args: argparse.Namespace) -> None:
    """Resume after the active capture and finish all fixed refit shards."""
    if not args.execute:
        raise ValueError("numerical supervision requires explicit --execute")
    control = Path(args.control).resolve()
    capture_root = Path(args.capture_root).resolve()
    git_dir = Path(args.production_git_dir).resolve()
    prior_capture = Path(args.wait_capture).resolve()
    plan = recovery.load_plan(control)
    if capture_root.exists() or capture_root.parent != control / "captures":
        raise ValueError("supervisor capture root must be new under fixed control/captures")
    if not 1 <= args.poll_seconds <= 300:
        raise ValueError("poll interval must be between 1 and 300 seconds")
    if plan["workers"] != 6 or len(plan["affected_cell_ids"]) != 21:
        raise ValueError("supervisor requires the fixed six-shard 21-cell plan")
    recovery.require_apfs(control)
    binding = require_launch_binding(plan, git_dir)
    capture_root.mkdir(parents=True, exist_ok=False)
    claim_path = control / "sequential_supervisor.claim"
    recovery.claim(claim_path, {"capture_root": str(capture_root),
                                "plan_sha256": plan["content_sha256"]})
    recovery.write_new_json(capture_root / "start.json",
                            {"started_utc": recovery.utc_now(), "owner_pid": os.getpid(),
                             "control": str(control), "plan_sha256": plan["content_sha256"],
                             "analysis_binding": binding,
                             "production_git_dir": str(git_dir),
                             "wait_capture": str(prior_capture)})
    try:
        wait_for_capture(prior_capture,
                         "metabric_matched__expression__r01f03__bayesian_spike_slab__full",
                         control, plan, git_dir, binding, args.poll_seconds)
        sequence = 0
        for worker, identities in enumerate(plan["shards"]):
            for identity in identities:
                attempt = control / "refits" / identity / "attempt_001"
                if attempt.exists():
                    require_completed_refit(control, plan, identity)
                    continue
                sequence += 1
                run_captured_worker(capture_root / f"{sequence:02d}_worker{worker}_cell",
                                    control, plan, git_dir, binding, worker, 1, identity)
            receipt_path = control / "worker_returns" / f"worker_{worker}.json"
            if receipt_path.exists():
                receipt = recovery.read_json(receipt_path)
                if (receipt.get("worker") != worker or receipt.get("status") != "complete"
                        or receipt.get("cell_ids") != identities):
                    raise ValueError(f"worker {worker} has a mismatched terminal receipt")
            else:
                sequence += 1
                run_captured_worker(capture_root / f"{sequence:02d}_worker{worker}_final",
                                    control, plan, git_dir, binding, worker, 1, None)
        require_idle(control, plan)
        recovery.write_new_json(capture_root / "complete.json",
                                {"completed_utc": recovery.utc_now(),
                                 "plan_sha256": plan["content_sha256"],
                                 "analysis_binding": binding,
                                 "verified_refits": len(plan["affected_cell_ids"]),
                                 "complete_workers": plan["workers"]})
        claim_path.unlink()
    except BaseException as exc:
        recovery.write_new_json(capture_root / "failure.json",
                                {"failed_utc": recovery.utc_now(), "error_type":
                                 type(exc).__name__, "error": str(exc),
                                 "supervisor_claim_retained": True})
        raise


def main() -> None:
    """Require explicit paths and execution intent for unattended refits."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("control", "capture-root", "production-git-dir", "wait-capture"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--execute", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
