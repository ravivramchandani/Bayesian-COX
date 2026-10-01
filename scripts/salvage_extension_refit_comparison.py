"""Complete one interrupted fourth-refit comparison without fitting again.

The original numerical child returned zero. Its worker failed after the fit,
before writing the official scientific-comparison receipt, when ArviZ called
``os.getcwd()`` from a vanished working directory. This command preserves that
failure and runs only the frozen ``compare_refit`` function in a new captured
process with a stable local working directory. It cannot dispatch a model fit.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import assemble_recovered_extension as adapter
from scripts import recover_extension_run as recovery

IDENTITY = "metabric_matched__expression__r01f03__bayesian_spike_slab__full"
PLAN_FILE_SHA256 = "ae8643f0d379acfab8298090b29e37005579efd5c224ef7be80bfe1713027694"
PLAN_CONTENT_SHA256 = "862a771296fe0e6dc4e5befab39655b67491e3241dad6de1384c6c77eb19236a"
FAILED_CAPTURE_FILES = {
    "launch.json": "54d726cc8928f46c5f6160c2fddafef036d3afcef06347c14fc9dfdd461820a6",
    "wrapper_start.json": "4b171f8547538c0b7f5e60657c7705af0401141918bdd3071c9de7fff6375c7a",
    "return.json": "a75fc02bfc47401fe2fc5873d4f880667581d947b7d6880493a0a87ee2e416bd",
    "worker.stderr.log": "45a2733e233a0b74e41ebd9f942e91fec09bb599695705fca36897dbbc2bdc89",
}
CHILD_FILES = {
    "child_start.json": "a384f1929a07e6f0c531aa25f5397cb7917c32662122ff3821259d91fe722988",
    "child_return.json": "c1eeeec2724ea62ae80eb08f4ddf8f5ac3b3d23ddd7fe3f86a37a39ec22314f3",
}
SAFE_CWD = Path("/private/tmp")
THREADS = ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "VECLIB_MAXIMUM_THREADS",
           "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS")
TOKEN = re.compile(r"[0-9a-f]{32}\Z")


def require(condition: bool, message: str) -> None:
    """Reject incomplete evidence before creating a new comparison capture."""
    if not condition:
        raise ValueError(message)


def checked(path: Path, *, exists: bool = True) -> Path:
    """Require absolute, link-free paths and ordinary existing ancestors."""
    require(path.is_absolute() and ".." not in path.parts, f"unsafe salvage path: {path}")
    require(not any(item.is_symlink() for item in (path, *path.parents)), f"linked salvage path: {path}")
    if exists:
        require(path.exists(), f"missing salvage path: {path}")
    return path


def file_sha(path: Path) -> str:
    """Hash a regular captured file without following a symbolic link."""
    checked(path)
    require(stat.S_ISREG(path.lstat().st_mode), f"nonregular salvage file: {path}")
    return recovery.sha256_file(path)


def alive(pid: Any) -> bool:
    """Fail closed if a historical owner PID is still allocated."""
    require(type(pid) is int and pid > 0, "historical owner PID is invalid")
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def failure_capture(control: Path, plan: dict[str, Any]) -> dict[str, str]:
    """Bind the exact old rc1 failure and its retained supervisor claim."""
    capture = checked(control / "captures/worker00_ramp2")
    hashes = {name: file_sha(capture / name) for name in FAILED_CAPTURE_FILES}
    require(hashes == FAILED_CAPTURE_FILES, "fourth-refit failed capture bytes changed")
    launch = recovery.read_json(capture / "launch.json")
    started = recovery.read_json(capture / "wrapper_start.json")
    returned = recovery.read_json(capture / "return.json")
    expected_command = ["/usr/bin/caffeinate", "-dimsu", "/usr/bin/nice", "-n", "10",
                        plan["python"], "-B", str(Path(launch["command"][7])),
                        "run-worker", "--control", str(control), "--worker", "0",
                        "--max-new-cells", "1", "--execute"]
    require(launch.get("command") == expected_command
            and file_sha(Path(launch["command"][7])) == plan["controller_sha256"]
            and launch.get("git_work_tree") == plan["sealed"]
            and launch.get("caffeinate_pid") == returned.get("caffeinate_pid")
            and started.get("wrapper_pid") == returned.get("wrapper_pid")
            and started.get("expected_cell_id") == IDENTITY
            and returned.get("return_code") == 1
            and not alive(returned["wrapper_pid"])
            and not alive(returned["caffeinate_pid"]),
            "fourth-refit wrapper did not finish with its exact rc1 capture")
    stderr = (capture / "worker.stderr.log").read_text(encoding="utf-8")
    require(all(text in stderr for text in ("compare_refit", "get_arviz_rcfile",
                                            "os.getcwd()", "FileNotFoundError")),
            "recorded wrapper failure was not the post-fit cwd error")
    published = recovery.read_json(recovery.REPO / "coordination/recovery/"
                                   "2026-10-01-fourth-extension-recovery-launch.json")
    require(published.get("capture_directory") == str(capture)
            and published.get("cell_id") == IDENTITY
            and published.get("control_plan_sha256") == PLAN_FILE_SHA256
            and published.get("launch_sha256") == hashes["launch.json"]
            and published.get("wrapper_start_sha256") == hashes["wrapper_start.json"]
            and published.get("capture_script_sha256") == file_sha(capture / "capture.py"),
            "published fourth-refit launch differs from retained capture")
    claim = recovery.read_json(control / "sequential_supervisor.claim")
    failure = recovery.read_json(control / "captures/sequential-v1/failure.json")
    require(claim.get("plan_sha256") == plan["content_sha256"]
            and claim.get("capture_root") == str(control / "captures/sequential-v1")
            and not alive(claim.get("pid"))
            and failure.get("error") == "prior captured worker did not return zero"
            and failure.get("supervisor_claim_retained") is True,
            "retained v1 supervisor claim lacks a finished failure")
    hashes["capture.py"] = file_sha(capture / "capture.py")
    hashes["published_launch"] = file_sha(recovery.REPO / "coordination/recovery/"
                                           "2026-10-01-fourth-extension-recovery-launch.json")
    hashes["v1_supervisor_claim"] = file_sha(control / "sequential_supervisor.claim")
    hashes["v1_supervisor_failure"] = file_sha(control / "captures/sequential-v1/failure.json")
    return hashes


def completed_child(control: Path, plan: dict[str, Any], *, comparison_exists: bool = False) -> tuple[Path, dict[str, str]]:
    """Verify a saved zero-return child, never infer success from trace presence."""
    from src.pipelines.extensions.runner import verified_cell

    attempt = checked(control / "refits" / IDENTITY / "attempt_001")
    run = checked(attempt / "run")
    require((attempt / "scientific_comparison.json").exists() == comparison_exists
            and not (attempt / "child_execution.claim").exists(),
            "fourth refit comparison state or child claim differs")
    hashes = {name: file_sha(attempt / name) for name in CHILD_FILES}
    require(hashes == CHILD_FILES, "fourth-refit child return bytes changed")
    start, returned = (recovery.read_json(attempt / name) for name in CHILD_FILES)
    invocation = recovery.read_json(attempt / "invocation.json")
    token = invocation.get("token")
    require(start.get("cell_id") == returned.get("cell_id") == IDENTITY
            and returned.get("return_code") == 0 and not alive(start.get("pid"))
            and isinstance(token, str) and TOKEN.fullmatch(token) is not None
            and invocation.get("plan_sha256") == plan["content_sha256"]
            and invocation.get("worker") == 0
            and invocation.get("cwd") == plan["sealed"],
            "fourth-refit child lacks exact finished first-attempt proof")
    expected_argv = [plan["python"], invocation["argv"][1], "child", "--control",
                     str(control), "--cell-id", IDENTITY, "--run", str(run), "--token", token]
    require(invocation.get("argv") == expected_argv
            and file_sha(Path(expected_argv[1])) == plan["controller_sha256"],
            "fourth-refit child command or controller changed")
    source_cell = Path(plan["source"]) / "cells" / f"{IDENTITY}.json"
    require(file_sha(source_cell) == plan["source_cell_file_sha256"][IDENTITY],
            "fourth original source cell changed")
    cell_path = run / "cells" / f"{IDENTITY}.json"
    cell = verified_cell(cell_path)
    require(cell.get("cell_id") == IDENTITY and cell.get("status") in recovery.TERMINAL_STATUSES,
            "fourth saved refit is not a terminal cell")
    files = {"cell": file_sha(cell_path), "source_cell": file_sha(source_cell),
             "invocation": file_sha(attempt / "invocation.json"),
             "run_manifest": file_sha(run / "manifest.json"),
             "child_stdout": file_sha(attempt / "child.stdout.log"),
             "child_stderr": file_sha(attempt / "child.stderr.log"), **hashes}
    require(files["run_manifest"] == plan["source_manifest_sha256"],
            "fourth refit used a different frozen manifest")
    traces = {}
    for fit in cell.get("fit_attempts", []):
        for trace in fit.get("traces", {}).values():
            name = trace["filename"]
            require(isinstance(name, str) and re.fullmatch(r"attempt_[1-9][0-9]*_(posterior|prior)\.nc", name)
                    is not None, "unsafe fourth-refit trace filename")
            path = run / "traces" / IDENTITY / name
            require(file_sha(path) == trace["sha256"] and name not in traces,
                    "fourth saved refit trace differs")
            traces[name] = trace["sha256"]
    require(len(traces) == 3, "fourth refit lacks three complete saved attempts")
    files.update({f"trace/{name}": digest for name, digest in traces.items()})
    return cell_path, files


def preflight(control: Path, git_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Check frozen controller, old failure, source and first child before writes."""
    require(file_sha(control / "plan.json") == PLAN_FILE_SHA256,
            "fixed v3 recovery plan file changed")
    plan = recovery.load_plan(control)
    require(plan["content_sha256"] == PLAN_CONTENT_SHA256
            and IDENTITY in plan["shards"][0] and plan["workers"] == 6,
            "fourth identity differs from fixed v3 recovery shard")
    adapter.require_no_active_producer(control, Path(plan["source"]))
    require(not (control / "no_fit_salvage.claim").exists(), "another salvage claim exists")
    manifest = recovery.read_json(Path(plan["source"]) / "manifest.json")
    require(file_sha(Path(plan["source"]) / "manifest.json") == plan["source_manifest_sha256"],
            "original frozen manifest changed")
    production = adapter.require_production_root(manifest, Path(plan["sealed"]), git_dir)
    recovery.require_environment(Path(plan["python"]), Path(plan["sealed"]),
                                 Path(plan["environment_receipt"]))
    analysis_commit = adapter.require_clean_published_adapter(recovery.REPO)
    subprocess.run(["git", "ls-files", "--error-unmatch",
                    "scripts/salvage_extension_refit_comparison.py"], cwd=recovery.REPO,
                   env=adapter.clean_git_environment(), capture_output=True, text=True,
                   check=True, timeout=30)
    old = failure_capture(control, plan)
    cell_path, child = completed_child(control, plan)
    return plan, {"analysis_commit": analysis_commit, "production_attestation": production,
                  "old_failed_capture_sha256": old, "completed_child_sha256": child,
                  "refit_cell_path": str(cell_path)}


def child_command(plan: dict[str, Any], control: Path, capture: Path, token: str) -> list[str]:
    """Construct the only allowed no-fit comparison command."""
    return [plan["python"], "-I", "-B", str(Path(__file__).resolve()), "compare-child",
            "--control", str(control), "--capture-root", str(capture), "--token", token]


def compare_child(args: argparse.Namespace) -> None:
    """Write only the frozen comparison after verifying its live parent claim."""
    control, capture = checked(args.control), checked(args.capture_root)
    claim = recovery.read_json(control / "no_fit_salvage.claim")
    require(claim.get("capture_root") == str(capture)
            and claim.get("token") == args.token
            and claim.get("parent_pid") == os.getppid()
            and os.getcwd() == str(SAFE_CWD), "unowned or unsafe no-fit comparison child")
    plan = recovery.load_plan(control)
    require(plan["content_sha256"] == PLAN_CONTENT_SHA256
            and Path(sys.executable).samefile(Path(plan["python"])),
            "no-fit child interpreter or plan differs")
    sealed = Path(plan["sealed"])
    manifest = recovery.read_json(Path(plan["source"]) / "manifest.json")
    script = sealed / "scripts/reproduce_extensions.py"
    require(file_sha(script) == manifest["input_sha256"]["scripts/reproduce_extensions.py"],
            "frozen scientific comparison source changed")
    specification = importlib.util.spec_from_file_location("scripts.reproduce_extensions", script)
    require(specification is not None and specification.loader is not None,
            "frozen reproduction script cannot be loaded")
    reproduce_extensions = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = reproduce_extensions
    specification.loader.exec_module(reproduce_extensions)
    require(Path(reproduce_extensions.__file__).resolve() == script.resolve(),
            "comparison imported a nonfrozen reproduction script")
    attempt = control / "refits" / IDENTITY / "attempt_001"
    require(not (attempt / "scientific_comparison.json").exists(),
            "fourth scientific comparison already exists")
    result = recovery.compare_refit(control, plan, IDENTITY, attempt / "run")
    print(json.dumps({"cell_id": IDENTITY, "status": result["official_non_timing_science"],
                      "fits_executed": 0}, sort_keys=True), flush=True)


def launch_child(command: list[str], cwd: Path, environment: dict[str, str],
                 stdout: Any, stderr: Any) -> tuple[int, int]:
    """Wait for a separate interpreter and return its actual PID and exit code."""
    child = subprocess.Popen(command, cwd=cwd, env=environment, stdin=subprocess.DEVNULL,
                             stdout=stdout, stderr=stderr, close_fds=True)
    return child.pid, child.wait()


def salvage(args: argparse.Namespace) -> dict[str, Any]:
    """Create a distinct captured comparison and proof, leaving old claims intact."""
    require(args.execute is True, "no-fit salvage requires explicit --execute")
    control, git_dir = (checked(path) for path in (args.control, args.production_git_dir))
    capture = checked(args.capture_root, exists=False)
    require(capture.parent == control / "captures" and capture.name == "no-fit-salvage-r01f03-v1"
            and not capture.exists(), "salvage capture root must be fresh and fixed")
    checked(SAFE_CWD)
    require(SAFE_CWD.is_dir() and stat.S_ISDIR(SAFE_CWD.lstat().st_mode),
            "stable comparison cwd is unavailable")
    recovery.require_apfs(SAFE_CWD)
    os.chdir(SAFE_CWD)
    require(os.getcwd() == str(SAFE_CWD), "stable comparison cwd cannot be entered")
    plan, prior = preflight(control, git_dir)
    token = os.urandom(16).hex()
    command = child_command(plan, control, capture, token)
    claim_path = control / "no_fit_salvage.claim"
    recovery.claim(claim_path, {"parent_pid": os.getpid(), "capture_root": str(capture),
                                "token": token, "plan_sha256": plan["content_sha256"]})
    try:
        capture.mkdir(parents=True, exist_ok=False)
        recovery.write_new_json(capture / "start.json",
                                {"started_utc": recovery.utc_now(), "owner_pid": os.getpid(),
                                 "identity": IDENTITY, "plan_file_sha256": PLAN_FILE_SHA256,
                                 "plan_content_sha256": PLAN_CONTENT_SHA256,
                                 "prior": prior, "stable_cwd": str(SAFE_CWD),
                                 "no_fit_comparison_only": True})
        environment = os.environ.copy()
        environment.update({key: "1" for key in THREADS})
        environment["PYTHONNOUSERSITE"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        with (capture / "stdout.log").open("x") as stdout, (capture / "stderr.log").open("x") as stderr:
            recovery.write_new_json(capture / "launch.json",
                                    {"launched_utc": recovery.utc_now(), "owner_pid": os.getpid(),
                                     "command": command, "cwd": str(SAFE_CWD),
                                     "script_sha256": file_sha(Path(__file__)),
                                     "numeric_threads": {key: environment[key] for key in THREADS}})
            pid, returned = launch_child(command, SAFE_CWD, environment, stdout, stderr)
        recovery.write_new_json(capture / "return.json",
                                {"returned_utc": recovery.utc_now(), "owner_pid": os.getpid(),
                                 "child_pid": pid, "return_code": returned})
        require(returned == 0, "no-fit comparison child did not return zero")
        old_now = failure_capture(control, plan)
        cell_path, child_now = completed_child(control, plan, comparison_exists=True)
        require(old_now == prior["old_failed_capture_sha256"]
                and child_now == prior["completed_child_sha256"],
                "old failure or saved fit changed during comparison")
        from src.pipelines.extensions.runner import verified_cell

        proof = adapter.require_refit_proof(
            control, plan, IDENTITY, Path(plan["source"]) / "cells" / f"{IDENTITY}.json",
            cell_path, verified_cell(cell_path))
        result = {"schema_version": 1, "status": "fourth_refit_postfit_comparison_salvaged",
                  "cell_id": IDENTITY, "plan_file_sha256": PLAN_FILE_SHA256,
                  "plan_content_sha256": PLAN_CONTENT_SHA256,
                  "old_wrapper_return_code": 1, "saved_fit_child_return_code": 0,
                  "new_comparison_child_return_code": 0,
                  "new_fits_executed": 0, "old_failure_preserved": True,
                  "old_failed_capture_sha256": old_now,
                  "saved_child_sha256": child_now,
                  "scientific_comparison_sha256": file_sha(cell_path.parents[2] /
                                                           "scientific_comparison.json"),
                  "official_refit_proof": proof,
                  "launch_sha256": file_sha(capture / "launch.json"),
                  "return_sha256": file_sha(capture / "return.json"),
                  "stdout_sha256": file_sha(capture / "stdout.log"),
                  "stderr_sha256": file_sha(capture / "stderr.log")}
        result["content_sha256"] = recovery.content_sha256(result)
        recovery.write_new_json(capture / "proof.json", result)
        claim_path.unlink()
        recovery.write_new_json(capture / "complete.json",
                                {"completed_utc": recovery.utc_now(),
                                 "proof_sha256": file_sha(capture / "proof.json"),
                                 "plan_content_sha256": PLAN_CONTENT_SHA256,
                                 "new_fits_executed": 0})
        return result
    except BaseException as exc:
        if capture.is_dir() and not (capture / "failure.json").exists():
            recovery.write_new_json(capture / "failure.json",
                                    {"failed_utc": recovery.utc_now(), "error_type": type(exc).__name__,
                                     "error": str(exc),
                                     "claim_retained_for_review": claim_path.exists()})
        raise


def main() -> int:
    """Expose only the captured salvage and its claim-bound comparison child."""
    parser = argparse.ArgumentParser(description=__doc__)
    command = parser.add_subparsers(dest="command", required=True)
    parent = command.add_parser("salvage")
    parent.add_argument("--control", type=Path, required=True)
    parent.add_argument("--capture-root", type=Path, required=True)
    parent.add_argument("--production-git-dir", type=Path, required=True)
    parent.add_argument("--execute", action="store_true")
    child = command.add_parser("compare-child")
    child.add_argument("--control", type=Path, required=True)
    child.add_argument("--capture-root", type=Path, required=True)
    child.add_argument("--token", required=True)
    args = parser.parse_args()
    if args.command == "salvage":
        result = salvage(args)
        print(json.dumps({"status": result["status"], "cell_id": IDENTITY,
                          "new_fits_executed": 0}, sort_keys=True))
    else:
        compare_child(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
