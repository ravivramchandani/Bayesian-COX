"""Resume exactly 17 fixed extension refits after the fourth no-fit salvage.

The failed V1 supervisor and its worker return remain immutable evidence.
This successor requires the separate zero-fit comparison proof, then invokes
the frozen numerical controller one missing cell at a time from a stable Mac
working directory. It never selects a new scientific identity or retries an
existing first attempt.
"""

from __future__ import annotations

import argparse
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import recover_extension_run as recovery
from scripts import salvage_extension_refit_comparison as salvage
from scripts import supervise_extension_recovery as v1

FIRST_FOUR = frozenset({
    "metabric_matched__expression__r01f03__bayesian_spike_slab__full",
    "metabric_matched__expression__r01f05__bayesian_horseshoe__full",
    "metabric_matched__expression__r01f01__bayesian_horseshoe__full",
    "metabric_matched__expression__r01f01__pv_horseshoe__full",
})
SAFE_CWD = Path("/private/tmp")
MAC_GIT_DIR = Path("/Users/macuser/bayes-cox-runs/frozen-git-metadata-119476f-v2/.git")
CAPTURE_NAME = "sequential-v2"
CLAIM_NAME = "sequential_supervisor_v2.claim"
TRACE_NAME = re.compile(r"attempt_[1-9][0-9]*_(posterior|prior)\.nc\Z")


def require(condition: bool, message: str) -> None:
    """Reject changed or incomplete evidence before any numerical dispatch."""
    if not condition:
        raise ValueError(message)


def file_sha(path: Path) -> str:
    """Hash only a regular, link-free file."""
    return salvage.file_sha(path)


def analysis_binding(plan: dict[str, Any], git_dir: Path,
                     expected: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pin the clean analysis commit and both supervisor sources."""
    value = v1.require_launch_binding(plan, git_dir)
    subprocess.run(["git", "ls-files", "--error-unmatch",
                    "scripts/supervise_extension_recovery_v2.py"], cwd=recovery.REPO,
                   env={key: item for key, item in os.environ.items()
                        if not key.startswith("GIT_")},
                   capture_output=True, text=True, check=True, timeout=30)
    result = {**value, "v2_supervisor_sha256": file_sha(Path(__file__)),
              "salvage_script_sha256": file_sha(Path(salvage.__file__))}
    if expected is not None:
        require(result == expected, "V2 analysis commit or source changed during dispatch")
    return result


def attempt_roster(control: Path, plan: dict[str, Any]) -> set[str]:
    """Permit only first attempts for identities in the fixed 21-cell plan."""
    root = salvage.checked(control / "refits")
    require(root.is_dir(), "fixed refit directory is absent")
    allowed = set(plan["affected_cell_ids"])
    found: set[str] = set()
    for row in root.iterdir():
        require(not row.is_symlink() and row.is_dir() and row.name in allowed,
                f"unexpected refit producer: {row}")
        children = list(row.iterdir())
        require(len(children) == 1 and children[0].name == "attempt_001"
                and not children[0].is_symlink() and children[0].is_dir(),
                f"unexpected refit attempt: {row}")
        found.add(row.name)
    return found


def verified_refit(control: Path, plan: dict[str, Any], identity: str) -> dict[str, Any]:
    """Rehash the official first-child proof, cell, and every saved trace."""
    from src.pipelines.extensions.runner import verified_cell

    proof = v1.require_completed_refit(control, plan, identity)
    attempt = control / "refits" / identity / "attempt_001"
    cell_file = attempt / "run/cells" / f"{identity}.json"
    cell = verified_cell(cell_file)
    traces: dict[str, str] = {}
    for fit in cell.get("fit_attempts", []):
        for trace in fit.get("traces", {}).values():
            name = trace.get("filename")
            require(isinstance(name, str) and TRACE_NAME.fullmatch(name) is not None
                    and name not in traces, f"invalid saved trace: {identity}")
            path = attempt / "run/traces" / identity / name
            digest = file_sha(path)
            require(digest == trace.get("sha256"), f"saved refit trace changed: {identity}")
            traces[name] = digest
    return {"official_refit_proof": proof, "cell_file_sha256": file_sha(cell_file),
            "trace_sha256": traces}


def require_salvage(control: Path, plan: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the fourth-refit proof without rewriting the failed V1 claim."""
    capture = salvage.checked(control / "captures/no-fit-salvage-r01f03-v1")
    require(not (control / "no_fit_salvage.claim").exists(),
            "no-fit salvage claim remains")
    start = recovery.read_json(capture / "start.json")
    launch = recovery.read_json(capture / "launch.json")
    returned = recovery.read_json(capture / "return.json")
    proof = recovery.read_json(capture / "proof.json")
    complete = recovery.read_json(capture / "complete.json")
    command = launch.get("command")
    token = command[-1] if isinstance(command, list) and command else None
    prior_script = (Path(command[3]) if isinstance(command, list) and len(command) == 11
                    and isinstance(command[3], str) else None)
    expected_command = ([plan["python"], "-I", "-B", str(prior_script), "compare-child",
                         "--control", str(control), "--capture-root", str(capture),
                         "--token", token] if prior_script is not None else None)
    require(isinstance(token, str) and salvage.TOKEN.fullmatch(token) is not None
            and command == expected_command
            and launch.get("cwd") == str(SAFE_CWD)
            and launch.get("script_sha256") == file_sha(prior_script)
            == file_sha(Path(salvage.__file__))
            and returned.get("return_code") == 0
            and start.get("stable_cwd") == str(SAFE_CWD)
            and start.get("identity") == salvage.IDENTITY
            and start.get("no_fit_comparison_only") is True,
            "no-fit salvage launch or return differs")
    require(complete.get("proof_sha256") == file_sha(capture / "proof.json")
            and complete.get("plan_content_sha256") == salvage.PLAN_CONTENT_SHA256
            and complete.get("new_fits_executed") == 0
            and proof.get("content_sha256") ==
            recovery.content_sha256({key: value for key, value in proof.items()
                                     if key != "content_sha256"})
            and proof.get("status") == "fourth_refit_postfit_comparison_salvaged"
            and proof.get("cell_id") == salvage.IDENTITY
            and proof.get("plan_file_sha256") == salvage.PLAN_FILE_SHA256
            and proof.get("plan_content_sha256") == salvage.PLAN_CONTENT_SHA256
            and proof.get("old_wrapper_return_code") == 1
            and proof.get("saved_fit_child_return_code") == 0
            and proof.get("new_comparison_child_return_code") == 0
            and proof.get("new_fits_executed") == 0
            and proof.get("old_failure_preserved") is True,
            "no-fit salvage proof or completion differs")
    hashes = {"launch_sha256": "launch.json", "return_sha256": "return.json",
              "stdout_sha256": "stdout.log", "stderr_sha256": "stderr.log"}
    require(all(proof.get(key) == file_sha(capture / name)
                for key, name in hashes.items()), "no-fit salvage capture changed")
    old = salvage.failure_capture(control, plan)
    cell_path, child = salvage.completed_child(control, plan, comparison_exists=True)
    fourth = verified_refit(control, plan, salvage.IDENTITY)
    require(proof.get("old_failed_capture_sha256") == old
            and proof.get("saved_child_sha256") == child
            and proof.get("official_refit_proof") == fourth["official_refit_proof"]
            and proof.get("scientific_comparison_sha256") ==
            file_sha(cell_path.parents[2] / "scientific_comparison.json")
            and start.get("prior", {}).get("old_failed_capture_sha256") == old
            and start.get("prior", {}).get("completed_child_sha256") == child,
            "no-fit salvage does not bind the old failure and saved fit")
    return {"salvage_complete_sha256": file_sha(capture / "complete.json"),
            "salvage_proof_sha256": file_sha(capture / "proof.json"),
            "old_failed_capture_sha256": old,
            "saved_child_sha256": child,
            "fourth_refit": fourth}


def launch_worker(command: list[str], cwd: Path, environment: dict[str, str],
                  stdout: Any, stderr: Any) -> tuple[int, int]:
    """Run the fixed controller once and capture its real exit."""
    child = subprocess.Popen(command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                             stdout=stdout, stderr=stderr, close_fds=True)
    return child.pid, child.wait()


def run_captured_worker(capture: Path, control: Path, plan: dict[str, Any],
                        git_dir: Path, binding: dict[str, Any], salvage_proof: dict[str, Any],
                        worker: int, expected_cell: str | None,
                        prior: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Execute one missing fit or a terminal worker receipt with strict deltas."""
    require(0 <= worker < 6
            and (expected_cell is None or expected_cell in plan["shards"][worker]),
            "V2 dispatch differs from a fixed worker shard")
    before = attempt_roster(control, plan)
    require(before == set(prior), "V2 prior attempt roster changed")
    if expected_cell is not None:
        require(expected_cell not in before, "V2 refuses to rerun a first attempt")
        first_missing = next((identity for identity in plan["shards"][worker]
                              if identity not in before), None)
        require(expected_cell == first_missing, "V2 target is not the next fixed shard cell")
    else:
        require(set(plan["shards"][worker]) <= before,
                "V2 terminal worker still has a missing cell")
    v1.require_idle(control, plan)
    analysis_binding(plan, git_dir, binding)
    require(require_salvage(control, plan) == salvage_proof,
            "salvage evidence changed before V2 dispatch")
    prior_now = {identity: verified_refit(control, plan, identity) for identity in prior}
    require(prior_now == prior, "prior refit evidence changed before V2 dispatch")
    capture.mkdir(parents=True, exist_ok=False)
    command = v1.worker_command(plan, control, worker, 1)
    environment = os.environ.copy()
    environment.update({key: "1" for key in salvage.THREADS})
    environment.update({"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1",
                        "GIT_DIR": str(git_dir), "GIT_WORK_TREE": plan["sealed"],
                        "GIT_OPTIONAL_LOCKS": "0"})
    git_environment = {key: environment[key] for key in
                       ("GIT_DIR", "GIT_WORK_TREE", "GIT_OPTIONAL_LOCKS")}
    with (capture / "worker.stdout.log").open("x") as stdout, \
            (capture / "worker.stderr.log").open("x") as stderr:
        recovery.write_new_json(capture / "launch.json",
                                {"launched_utc": recovery.utc_now(), "owner_pid": os.getpid(),
                                 "command": command, "cwd": str(SAFE_CWD),
                                 "worker": worker, "expected_cell": expected_cell,
                                 "plan_sha256": plan["content_sha256"],
                                 "analysis_binding": binding,
                                 "salvage_proof_sha256": salvage_proof["salvage_proof_sha256"],
                                 "git_environment": git_environment, "thread_limit": 1})
        pid, returned = launch_worker(command, SAFE_CWD, environment, stdout, stderr)
    recovery.write_new_json(capture / "return.json",
                            {"returned_utc": recovery.utc_now(), "owner_pid": os.getpid(),
                             "pid": pid, "return_code": returned})
    require(returned == 0, f"V2 captured worker {worker} returned {returned}")
    recorded = recovery.read_json(capture / "launch.json")
    require(recorded.get("command") == command and recorded.get("cwd") == str(SAFE_CWD)
            and recorded.get("git_environment") == git_environment
            and recorded.get("analysis_binding") == binding,
            "V2 launch metadata changed")
    analysis_binding(plan, git_dir, binding)
    require(require_salvage(control, plan) == salvage_proof,
            "salvage evidence changed during V2 dispatch")
    v1.require_idle(control, plan)
    after = attempt_roster(control, plan)
    expected_after = before | ({expected_cell} if expected_cell is not None else set())
    require(after == expected_after, "V2 controller created an unexpected attempt")
    unchanged = {identity: verified_refit(control, plan, identity) for identity in prior}
    require(unchanged == prior, "prior refit evidence changed during V2 dispatch")
    if expected_cell is not None:
        current = verified_refit(control, plan, expected_cell)
        recovery.write_new_json(capture / "verified_refit.json",
                                {"cell_id": expected_cell, "proof": current,
                                 "analysis_binding": binding,
                                 "launch_sha256": file_sha(capture / "launch.json"),
                                 "return_sha256": file_sha(capture / "return.json"),
                                 "verified_utc": recovery.utc_now()})
        return {expected_cell: current}
    receipt_path = control / "worker_returns" / f"worker_{worker}.json"
    receipt = recovery.read_json(receipt_path)
    require(receipt.get("worker") == worker and receipt.get("status") == "complete"
            and receipt.get("cell_ids") == plan["shards"][worker],
            "V2 terminal worker receipt differs from its fixed shard")
    recovery.write_new_json(capture / "verified_worker.json",
                            {"worker": worker, "analysis_binding": binding,
                             "worker_return_sha256": file_sha(receipt_path),
                             "launch_sha256": file_sha(capture / "launch.json"),
                             "return_sha256": file_sha(capture / "return.json"),
                             "verified_utc": recovery.utc_now()})
    return {}


def run(args: argparse.Namespace) -> dict[str, Any]:
    """Preserve V1 and sequentially complete the remaining fixed 17 refits."""
    require(args.execute is True, "V2 numerical supervision requires --execute")
    control = salvage.checked(args.control)
    git_dir = salvage.checked(args.production_git_dir)
    capture_root = salvage.checked(args.capture_root, exists=False)
    require(git_dir == MAC_GIT_DIR, "V2 requires the verified local Mac frozen Git metadata")
    require(capture_root == control / "captures" / CAPTURE_NAME
            and not capture_root.exists() and not (control / CLAIM_NAME).exists(),
            "V2 requires a fresh fixed capture and claim")
    salvage.checked(SAFE_CWD)
    require(SAFE_CWD.is_dir() and stat.S_ISDIR(SAFE_CWD.lstat().st_mode),
            "stable Mac working directory is unavailable")
    recovery.require_apfs(SAFE_CWD)
    recovery.require_apfs(control)
    os.chdir(SAFE_CWD)
    require(os.getcwd() == str(SAFE_CWD), "cannot enter stable Mac working directory")
    require(file_sha(control / "plan.json") == salvage.PLAN_FILE_SHA256,
            "V2 fixed recovery plan file changed")
    plan = recovery.load_plan(control)
    require(plan["content_sha256"] == salvage.PLAN_CONTENT_SHA256
            and plan["workers"] == 6 and len(plan["affected_cell_ids"]) == 21
            and set(plan["affected_cell_ids"]) ==
            {identity for shard in plan["shards"] for identity in shard},
            "V2 plan differs from the fixed 21-cell six-shard plan")
    require(not any((control / "worker_returns").glob("*.json")),
            "V2 found an unexpected preexisting terminal worker return")
    initial = attempt_roster(control, plan)
    require(initial == FIRST_FOUR, "V2 requires exactly the four proven first attempts")
    v1.require_idle(control, plan)
    binding = analysis_binding(plan, git_dir)
    salvage_proof = require_salvage(control, plan)
    prior = {identity: verified_refit(control, plan, identity) for identity in sorted(initial)}
    require(prior[salvage.IDENTITY] == salvage_proof["fourth_refit"],
            "salvaged fourth refit differs from initial evidence")
    claim_path = control / CLAIM_NAME
    recovery.claim(claim_path, {"capture_root": str(capture_root),
                                "plan_sha256": plan["content_sha256"],
                                "analysis_binding": binding,
                                "salvage_proof_sha256": salvage_proof["salvage_proof_sha256"]})
    try:
        capture_root.mkdir(parents=True, exist_ok=False)
        recovery.write_new_json(capture_root / "start.json",
                                {"started_utc": recovery.utc_now(), "owner_pid": os.getpid(),
                                 "control": str(control), "plan_sha256": plan["content_sha256"],
                                 "analysis_binding": binding,
                                 "production_git_dir": str(git_dir),
                                 "stable_worker_cwd": str(SAFE_CWD),
                                 "salvage_evidence": salvage_proof,
                                 "initial_refit_ids": sorted(initial),
                                 "remaining_refits": 17})
        sequence = 0
        fitted = 0
        for worker, identities in enumerate(plan["shards"]):
            for identity in identities:
                if identity in prior:
                    require(verified_refit(control, plan, identity) == prior[identity],
                            "existing first attempt changed before V2 skip")
                    continue
                sequence += 1
                new = run_captured_worker(
                    capture_root / f"{sequence:02d}_worker{worker}_cell",
                    control, plan, git_dir, binding, salvage_proof, worker, identity, prior)
                require(set(new) == {identity}, "V2 bounded dispatch returned a wrong identity")
                prior.update(new)
                fitted += 1
            sequence += 1
            run_captured_worker(capture_root / f"{sequence:02d}_worker{worker}_final",
                                control, plan, git_dir, binding, salvage_proof, worker, None, prior)
        require(fitted == 17 and set(prior) == set(plan["affected_cell_ids"])
                and attempt_roster(control, plan) == set(prior),
                "V2 did not complete exactly 17 new fixed refits")
        analysis_binding(plan, git_dir, binding)
        require(require_salvage(control, plan) == salvage_proof,
                "salvage evidence changed before V2 completion")
        v1.require_idle(control, plan)
        require({identity: verified_refit(control, plan, identity)
                 for identity in prior} == prior, "V2 final refit evidence changed")
        returns = {}
        for worker, identities in enumerate(plan["shards"]):
            path = control / "worker_returns" / f"worker_{worker}.json"
            receipt = recovery.read_json(path)
            require(receipt.get("worker") == worker and receipt.get("status") == "complete"
                    and receipt.get("cell_ids") == identities,
                    "V2 final worker return differs from fixed shard")
            returns[str(worker)] = file_sha(path)
        complete = {"completed_utc": recovery.utc_now(),
                    "plan_sha256": plan["content_sha256"],
                    "analysis_binding": binding,
                    "salvage_proof_sha256": salvage_proof["salvage_proof_sha256"],
                    "initial_verified_refits": 4, "new_refits": 17,
                    "verified_refits": 21, "complete_workers": 6,
                    "worker_return_sha256": returns,
                    "v1_failure_preserved": True}
        recovery.write_new_json(capture_root / "complete.json", complete)
        claim_path.unlink()
        return complete
    except BaseException as exc:
        if capture_root.is_dir() and not (capture_root / "failure.json").exists():
            recovery.write_new_json(capture_root / "failure.json",
                                    {"failed_utc": recovery.utc_now(),
                                     "error_type": type(exc).__name__, "error": str(exc),
                                     "v2_claim_retained_for_review": claim_path.exists()})
        raise


def main() -> int:
    """Require explicit paths and execution intent for V2 recovery."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--capture-root", type=Path, required=True)
    parser.add_argument("--production-git-dir", type=Path, required=True)
    parser.add_argument("--execute", action="store_true")
    result = run(parser.parse_args())
    print({"status": "v2_complete", "new_refits": result["new_refits"],
           "verified_refits": result["verified_refits"]}, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
