"""After the fixed successor finishes, seal its lineage and stage replay only.

This captured watcher never starts an extension worker, correction inventory,
arithmetic, or corrected fit. A failed gate retains its claim for review.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import assemble_recovered_extension as adapter
from scripts import continue_recovered_extension as successor
from scripts import recover_extension_run as recovery
from scripts import supervise_extension_recovery as supervisor

PINS = {
    "definition": "47df1918083e0b2ab23c5e7bec98bd3dc5a576226425ce5c3730a6501b8b2b49",
    "source_manifest": "a3b859fff4973223ba8c55372c922edb98ec9d9066dbe26b0430d85ec00a8343",
    "replay_completion": "95d6e1628c44f69f83f6aadee2ed6eb58107de2a332ed98a6e1f14b8fa5432ee",
    "preflight_manifest": "9b3533aa97ad88038e635c4e2cbbe3cc3b001c7e270a21307d8df69b57f6f5be",
    "preflight_completion": "f914c34e18d5c63ecc8a0dfa21988e022bb86d08c535f04799e9518857dece62",
    "contexts": "979efa26eba81652f151438e637eaf0899b1d875b69dd5c2305764ff66546fb7",
    "recovered_run_manifest": "83b9049fb6aaaadab576b34de0741e4f510344dcefba9f96198d15b5ab4f49b9",
    "recovery_lineage_verifier": "3af38987fa7e7d90af066e89af34084ba698f09a40378abcc6be6829633814a1",
}
PUBLISHED_SUCCESSOR = (recovery.REPO / "coordination/recovery/"
                       "2026-10-01-recovered-extension-continuation-launch.json")


def ordinary_absolute_path(value: str) -> Path:
    """Preserve lexical path safety checks before any path is resolved."""
    path = Path(value)
    if (not path.is_absolute() or ".." in path.parts
            or any(part.is_symlink() for part in (path, *path.parents))):
        raise ValueError(f"watcher requires an absolute link-free path: {path}")
    return path


def require_hashes(args: argparse.Namespace, plan: dict[str, Any]) -> None:
    """Bind the watcher to one fixed plan and the audited V3 replay bytes."""
    for name in ("plan_file_sha256", "plan_content_sha256", "successor_launch_sha256",
                 "successor_start_sha256"):
        if re.fullmatch(r"[0-9a-f]{64}", getattr(args, name)) is None:
            raise ValueError(f"invalid explicit SHA-256: {name}")
    if (recovery.sha256_file(args.control / "plan.json") != args.plan_file_sha256
            or plan["content_sha256"] != args.plan_content_sha256
            or plan["source_manifest_sha256"] != PINS["recovered_run_manifest"]):
        raise ValueError("fixed recovery plan differs from explicit pins")
    published = recovery.read_json(PUBLISHED_SUCCESSOR)
    if (published.get("fixed_plan_file_sha256") != args.plan_file_sha256
            or published.get("fixed_plan_content_sha256") != args.plan_content_sha256
            or published.get("successor_launch_sha256") != args.successor_launch_sha256
            or published.get("successor_start_sha256") != args.successor_start_sha256
            or published.get("control") != str(args.control)
            or published.get("recovered_run") != str(args.recovered_run)):
        raise ValueError("explicit successor pins differ from published launch")
    anchors = {
        "definition": args.source_replay / "definition.json",
        "source_manifest": args.source_replay / "manifest.json",
        "replay_completion": args.source_replay / "replay/completion.json",
        "preflight_manifest": args.preflight_output / "manifest.json",
        "preflight_completion": args.preflight_output / "completion.json",
        "contexts": args.contexts,
        "recovery_lineage_verifier": recovery.REPO / "scripts/extension_release/recovery_lineage.py",
    }
    for name, path in anchors.items():
        if not path.is_file() or path.is_symlink() or recovery.sha256_file(path) != PINS[name]:
            raise ValueError(f"V3/preflight anchor differs: {name}")


def require_clean_checkout(commit: str) -> None:
    """Use only this committed, clean watcher and its reviewed adapters."""
    if adapter.require_clean_published_adapter(recovery.REPO) != commit:
        raise ValueError("watcher checkout commit differs from explicit pin")
    subprocess.run(["git", "ls-files", "--error-unmatch", "scripts/post_successor_replay_stage.py"],
                   cwd=recovery.REPO, env=adapter.clean_git_environment(),
                   capture_output=True, text=True, check=True, timeout=30)


def require_successor_start(args: argparse.Namespace, plan: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Bind the genuine detached launch, start, process and pinned runtime code."""
    capture = args.control / "continuation_captures/sequential-v1"
    launch_path = args.control / "continuation_captures/sequential-v1.launch.json"
    start_path = capture / "start.json"
    if (recovery.sha256_file(launch_path) != args.successor_launch_sha256
            or recovery.sha256_file(start_path) != args.successor_start_sha256):
        raise ValueError("successor launch/start bytes differ from explicit pins")
    launch, start = recovery.read_json(launch_path), recovery.read_json(start_path)
    published = recovery.read_json(PUBLISHED_SUCCESSOR)
    pid = launch.get("pid")
    runtime = Path(launch.get("cwd", "/"))
    script = runtime / "scripts/continue_recovered_extension.py"
    expected_argv = [plan["python"], "-B", str(script), "--control", str(args.control),
                     "--recovered-run", str(args.recovered_run), "--assembly-plan",
                     str(args.control / "assembly_adapter_plan_v1.json"), "--capture-root",
                     str(capture), "--production-git-dir", start["production_git_dir"],
                     "--execute"]
    if (not isinstance(pid, int) or pid <= 0 or start.get("owner_pid") != pid
            or launch.get("argv") != expected_argv
            or launch.get("plan_file_sha256") != args.plan_file_sha256
            or launch.get("analysis_git_commit") != start["analysis_binding"]["analysis_git_commit"]
            or launch.get("successor_sha256") != start["analysis_binding"]["successor_sha256"]
            or launch.get("successor_sha256") != recovery.sha256_file(script)
            or launch.get("successor_sha256") != published["successor_source_sha256"]
            or launch.get("analysis_git_commit") != published["successor_analysis_commit"]
            or start.get("plan_sha256") != plan["content_sha256"]
            or start.get("control") != str(args.control)
            or start.get("recovered_run") != str(args.recovered_run)
            or start.get("assembly_plan") != str(args.control / "assembly_adapter_plan_v1.json")
            or start.get("production_git_dir") != launch["argv"][-2]):
        raise ValueError("successor process or source differs from captured launch")
    if adapter.require_clean_published_adapter(runtime) != launch["analysis_git_commit"]:
        raise ValueError("pinned successor runtime checkout changed")
    return launch, start


def wait_for_successor(args: argparse.Namespace, plan: dict[str, Any],
                       launch: dict[str, Any], start: dict[str, Any]) -> dict[str, Any]:
    """Wait for the real complete receipt and released producer claim."""
    capture = args.control / "continuation_captures/sequential-v1"
    claim = args.control / "continuation_supervisor.claim"
    while True:
        if (capture / "failure.json").exists():
            raise RuntimeError("successor failed; inspect its retained failure and claim")
        complete = successor.read_ready_json(capture / "complete.json")
        if complete is not None:
            if (complete.get("status") != "full_grid_stored_pending_deep_verification"
                    or complete.get("plan_sha256") != plan["content_sha256"]
                    or complete.get("analysis_binding") != start["analysis_binding"]
                    or complete.get("stored") != 1625
                    or complete.get("new_continuation_cells") != 411
                    or set(complete.get("verified_worker_sha256", {})) !=
                    {str(worker) for worker in range(6)}):
                raise ValueError("successor completion differs from captured plan")
            if not claim.exists():
                return complete
            if not supervisor.process_exists(launch["pid"]):
                raise RuntimeError("successor left a producer claim after completion")
        elif not supervisor.process_exists(launch["pid"]):
            raise RuntimeError("successor vanished without a complete or failure receipt")
        time.sleep(args.poll_seconds)


def captured_command(folder: Path, command: list[str], binding: dict[str, Any]) -> None:
    """Keep the exact child invocation, log bytes and actual return code."""
    folder.mkdir(exist_ok=False)
    environment = {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
    environment.update({"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"})
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        environment[key] = "1"
    with (folder / "stdout.log").open("x") as stdout, (folder / "stderr.log").open("x") as stderr:
        child = subprocess.Popen(command, cwd=recovery.REPO, env=environment,
                                 stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                                 close_fds=True)
        recovery.write_new_json(folder / "launch.json", {"launched_utc": recovery.utc_now(),
                                "owner_pid": os.getpid(), "pid": child.pid, "argv": command,
                                "cwd": str(recovery.REPO), **binding})
        return_code = child.wait()
    recovery.write_new_json(folder / "return.json", {"returned_utc": recovery.utc_now(),
                            "owner_pid": os.getpid(), "pid": child.pid,
                            "return_code": return_code,
                            "stdout_sha256": recovery.sha256_file(folder / "stdout.log"),
                            "stderr_sha256": recovery.sha256_file(folder / "stderr.log")})
    if return_code != 0:
        raise RuntimeError(f"captured {folder.name} returned {return_code}")


def stage_command(args: argparse.Namespace, lineage_sha256: str) -> list[str]:
    """Pass the audited replay, preflight and recovered-run byte pins."""
    command = [args.python, "-B", str(recovery.REPO / "scripts/catalytic_correction/"
                                     "stage_replay_for_recovered_run.py")]
    paths = {"source-replay": args.source_replay, "destination": args.destination,
             "recovered-run": args.recovered_run, "preflight-output": args.preflight_output,
             "contexts": args.contexts}
    hashes = {**PINS, "recovery_continuation": lineage_sha256}
    for name, path in paths.items():
        command.extend((f"--{name}", str(path)))
    for name, digest in hashes.items():
        command.extend((f"--{name.replace('_', '-')}-sha256", digest))
    return command


def run(args: argparse.Namespace) -> None:
    """Stop after a sealed final lineage and copied first-draw replay."""
    if not args.execute or not 1 <= args.poll_seconds <= 300:
        raise ValueError("watcher requires --execute and a 1–300 second poll interval")
    for name in ("control", "recovered_run", "capture_root", "source_replay",
                 "preflight_output", "contexts", "destination"):
        setattr(args, name, ordinary_absolute_path(getattr(args, name)))
    if (args.capture_root.exists() or args.capture_root.parent !=
            args.control / "post_successor_captures" or args.destination.exists()):
        raise ValueError("fresh fixed capture and destination roots required")
    plan = recovery.load_plan(args.control)
    if args.python != plan["python"]:
        raise ValueError("watcher interpreter differs from fixed recovery plan")
    require_hashes(args, plan)
    require_clean_checkout(args.checkout_commit)
    launch, start = require_successor_start(args, plan)
    recovery.require_apfs(args.destination)
    recovery.require_free_space(args.destination, gib=10)
    args.capture_root.parent.mkdir(parents=True, exist_ok=True)
    args.capture_root.mkdir(exist_ok=False)
    claim = args.control / "post_successor_stage.claim"
    recovery.claim(claim, {"capture_root": str(args.capture_root),
                           "plan_sha256": plan["content_sha256"]})
    try:
        recovery.write_new_json(args.capture_root / "start.json", {
            "started_utc": recovery.utc_now(), "owner_pid": os.getpid(),
            "checkout_commit": args.checkout_commit, "plan_file_sha256": args.plan_file_sha256,
            "plan_content_sha256": args.plan_content_sha256,
            "successor_launch_sha256": args.successor_launch_sha256,
            "successor_start_sha256": args.successor_start_sha256,
            "source_replay": str(args.source_replay), "preflight_output": str(args.preflight_output),
            "contexts": str(args.contexts), "destination": str(args.destination),
            "recovered_run": str(args.recovered_run), "v3_preflight_pins": PINS})
        wait_for_successor(args, plan, launch, start)
        require_clean_checkout(args.checkout_commit)
        require_hashes(args, plan)
        require_successor_start(args, plan)
        captured_command(args.capture_root / "seal_lineage",
                         [args.python, "-B", str(recovery.REPO / "scripts/seal_recovered_extension_lineage.py"),
                          "--control", str(args.control), "--run", str(args.recovered_run)],
                         {"plan_sha256": plan["content_sha256"],
                          "successor_complete_sha256": recovery.sha256_file(
                              args.control / "continuation_captures/sequential-v1/complete.json")})
        lineage_path = args.recovered_run / "recovery_continuation.json"
        lineage_sha256 = recovery.sha256_file(lineage_path)
        require_clean_checkout(args.checkout_commit)
        require_hashes(args, plan)
        captured_command(args.capture_root / "stage_replay", stage_command(args, lineage_sha256),
                         {"plan_sha256": plan["content_sha256"],
                          "recovery_continuation_sha256": lineage_sha256})
        receipt = args.destination.with_name(args.destination.name + ".replay-stage.json")
        staged = recovery.read_json(receipt)
        if (staged.get("status") != "complete_first_draw_replay_staged_for_recovered_run"
                or staged.get("staged_contexts") != 1650
                or staged.get("staged_files") != 6603
                or staged.get("recovery_continuation_sha256") != lineage_sha256):
            raise ValueError("stage receipt differs from captured recovered lineage")
        recovery.write_new_json(args.capture_root / "complete.json", {
            "completed_utc": recovery.utc_now(),
            "status": "final_lineage_sealed_and_first_draw_replay_staged_no_fit",
            "plan_sha256": plan["content_sha256"],
            "successor_complete_sha256": recovery.sha256_file(
                args.control / "continuation_captures/sequential-v1/complete.json"),
            "recovery_continuation_sha256": lineage_sha256,
            "stage_receipt_sha256": recovery.sha256_file(receipt),
            "staged_manifest_sha256": recovery.sha256_file(args.destination / "manifest.json"),
            "corrected_fits_executed": False})
        claim.unlink()
    except BaseException as exc:
        recovery.write_new_json(args.capture_root / "failure.json", {
            "failed_utc": recovery.utc_now(), "error_type": type(exc).__name__,
            "error": str(exc), "claim_retained_for_review": True})
        raise


def main() -> None:
    """Accept only explicit fixed evidence paths and process pins."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("control", "recovered-run", "capture-root", "source-replay",
                 "preflight-output", "contexts", "destination", "python"):
        parser.add_argument(f"--{name}", required=True)
    for name in ("plan-file-sha256", "plan-content-sha256", "successor-launch-sha256",
                 "successor-start-sha256", "checkout-commit"):
        parser.add_argument(f"--{name}", required=True)
    parser.add_argument("--poll-seconds", type=int, default=60)
    parser.add_argument("--execute", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()
