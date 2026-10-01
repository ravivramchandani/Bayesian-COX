"""Invented post-successor receipts; no numerical worker or correction fit runs."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import post_successor_replay_stage as watcher
from scripts import recover_extension_run as recovery


def write(path: Path, value: dict) -> str:
    """Create one fixture receipt and return its actual byte hash."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return recovery.sha256_file(path)


def fixture_successor(tmp_path: Path) -> tuple[SimpleNamespace, dict, dict, dict]:
    """Build a real hashed launch/start pair for an invented fixed successor."""
    control = tmp_path / "control"
    runtime = tmp_path / "runtime"
    script = runtime / "scripts/continue_recovered_extension.py"
    script.parent.mkdir(parents=True)
    script.write_text("# invented successor\n", encoding="utf-8")
    run = tmp_path / "recovered"
    capture = control / "continuation_captures/sequential-v1"
    plan = {"python": "/locked/python", "content_sha256": "1" * 64}
    binding = {"analysis_git_commit": "a" * 40,
               "successor_sha256": recovery.sha256_file(script)}
    start = {"owner_pid": 1234, "analysis_binding": binding,
             "production_git_dir": str(tmp_path / "frozen/.git"),
             "plan_sha256": plan["content_sha256"], "control": str(control),
             "recovered_run": str(run),
             "assembly_plan": str(control / "assembly_adapter_plan_v1.json")}
    argv = [plan["python"], "-B", str(script), "--control", str(control),
            "--recovered-run", str(run), "--assembly-plan",
            str(control / "assembly_adapter_plan_v1.json"), "--capture-root",
            str(capture), "--production-git-dir", start["production_git_dir"], "--execute"]
    launch = {"pid": 1234, "cwd": str(runtime), "argv": argv,
              "plan_file_sha256": "2" * 64,
              "analysis_git_commit": binding["analysis_git_commit"],
              "successor_sha256": binding["successor_sha256"]}
    start_sha = write(capture / "start.json", start)
    launch_sha = write(control / "continuation_captures/sequential-v1.launch.json", launch)
    args = SimpleNamespace(control=control, recovered_run=run,
                           plan_file_sha256=launch["plan_file_sha256"],
                           plan_content_sha256=plan["content_sha256"],
                           successor_launch_sha256=launch_sha,
                           successor_start_sha256=start_sha, poll_seconds=1)
    return args, plan, launch, start


def test_successor_start_requires_exact_receipts_and_pinned_runtime(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args, plan, launch, start = fixture_successor(tmp_path)
    published = tmp_path / "published.json"
    write(published, {"successor_source_sha256": launch["successor_sha256"],
                      "successor_analysis_commit": launch["analysis_git_commit"]})
    monkeypatch.setattr(watcher, "PUBLISHED_SUCCESSOR", published)
    monkeypatch.setattr(watcher.adapter, "require_clean_published_adapter",
                        lambda _: launch["analysis_git_commit"])
    assert watcher.require_successor_start(args, plan) == (launch, start)
    path = args.control / "continuation_captures/sequential-v1.launch.json"
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="explicit pins"):
        watcher.require_successor_start(args, plan)


def test_published_plan_and_launch_are_required(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args, plan, _, _ = fixture_successor(tmp_path)
    plan["source_manifest_sha256"] = watcher.PINS["recovered_run_manifest"]
    args.plan_file_sha256 = write(args.control / "plan.json", plan)
    published = tmp_path / "published.json"
    write(published, {"fixed_plan_file_sha256": args.plan_file_sha256,
                      "fixed_plan_content_sha256": args.plan_content_sha256,
                      "successor_launch_sha256": "0" * 64,
                      "successor_start_sha256": args.successor_start_sha256,
                      "control": str(args.control), "recovered_run": str(args.recovered_run)})
    monkeypatch.setattr(watcher, "PUBLISHED_SUCCESSOR", published)
    with pytest.raises(ValueError, match="published launch"):
        watcher.require_hashes(args, plan)


def test_successor_waits_for_released_claim_then_accepts_exact_completion(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args, plan, launch, start = fixture_successor(tmp_path)
    capture = args.control / "continuation_captures/sequential-v1"
    claim = args.control / "continuation_supervisor.claim"
    claim.write_text("owned\n")
    complete = {"status": "full_grid_stored_pending_deep_verification",
                "plan_sha256": plan["content_sha256"],
                "analysis_binding": start["analysis_binding"],
                "stored": 1625, "new_continuation_cells": 411,
                "verified_worker_sha256": {str(worker): "f" * 64 for worker in range(6)}}
    write(capture / "complete.json", complete)
    monkeypatch.setattr(watcher.supervisor, "process_exists", lambda _: True)
    monkeypatch.setattr(watcher.time, "sleep", lambda _: claim.unlink())
    assert watcher.wait_for_successor(args, plan, launch, start) == complete
    write(capture / "failure.json", {"error": "invented"})
    with pytest.raises(RuntimeError, match="successor failed"):
        watcher.wait_for_successor(args, plan, launch, start)


def test_successor_vanish_or_retained_claim_fails(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args, plan, launch, start = fixture_successor(tmp_path)
    monkeypatch.setattr(watcher.supervisor, "process_exists", lambda _: False)
    with pytest.raises(RuntimeError, match="vanished"):
        watcher.wait_for_successor(args, plan, launch, start)
    capture = args.control / "continuation_captures/sequential-v1"
    write(capture / "complete.json", {"status": "full_grid_stored_pending_deep_verification",
              "plan_sha256": plan["content_sha256"], "analysis_binding": start["analysis_binding"],
              "stored": 1625, "new_continuation_cells": 411,
              "verified_worker_sha256": {str(worker): "f" * 64 for worker in range(6)}})
    (args.control / "continuation_supervisor.claim").write_text("owned\n")
    with pytest.raises(RuntimeError, match="left a producer claim"):
        watcher.wait_for_successor(args, plan, launch, start)


def test_stage_command_has_only_sealed_replay_adapter_and_exact_pins(tmp_path: Path) -> None:
    args = SimpleNamespace(python=sys.executable, source_replay=tmp_path / "v3",
                           destination=tmp_path / "staged", recovered_run=tmp_path / "run",
                           preflight_output=tmp_path / "preflight",
                           contexts=tmp_path / "contexts.jsonl")
    command = watcher.stage_command(args, "b" * 64)
    assert command[:2] == [sys.executable, "-B"]
    assert command[2].endswith("/stage_replay_for_recovered_run.py")
    assert "run_reuse.py" not in " ".join(command)
    assert command[command.index("--recovery-continuation-sha256") + 1] == "b" * 64
    for name, digest in watcher.PINS.items():
        assert command[command.index(f"--{name.replace('_', '-')}-sha256") + 1] == digest


def test_captured_child_records_its_real_exit(tmp_path: Path) -> None:
    original_repo = recovery.REPO
    recovery.REPO = tmp_path
    try:
        watcher.captured_command(tmp_path / "good", [sys.executable, "-c", "print('ready')"],
                                 {"kind": "invented"})
        assert recovery.read_json(tmp_path / "good/return.json")["return_code"] == 0
        assert recovery.read_json(tmp_path / "good/launch.json")["kind"] == "invented"
        with pytest.raises(RuntimeError, match="returned 7"):
            watcher.captured_command(tmp_path / "bad",
                                     [sys.executable, "-c", "raise SystemExit(7)"], {})
        assert recovery.read_json(tmp_path / "bad/return.json")["return_code"] == 7
    finally:
        recovery.REPO = original_repo


def test_watcher_rejects_linked_or_parent_paths_before_resolving(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(target, target_is_directory=True)
    assert watcher.ordinary_absolute_path(str(target)) == target
    for value in (str(alias), str(alias / "future"), str(tmp_path / "x/../target"),
                  "relative/path"):
        with pytest.raises(ValueError, match="absolute link-free path"):
            watcher.ordinary_absolute_path(value)


@pytest.mark.parametrize("fail_stage", [False, True])
def test_watcher_rechecks_successor_then_retains_failed_claim(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_stage: bool) -> None:
    control = tmp_path / "control"
    control.mkdir()
    write(control / "continuation_captures/sequential-v1/complete.json", {"complete": True})
    run = tmp_path / "recovered"
    capture = control / "post_successor_captures/sequential-v1"
    destination = tmp_path / "staged"
    args = SimpleNamespace(execute=True, poll_seconds=1, control=control,
                           recovered_run=run, capture_root=capture,
                           source_replay=tmp_path / "source", preflight_output=tmp_path / "preflight",
                           contexts=tmp_path / "contexts.jsonl", destination=destination,
                           python=sys.executable, checkout_commit="a" * 40,
                           plan_file_sha256="b" * 64, plan_content_sha256="c" * 64,
                           successor_launch_sha256="d" * 64, successor_start_sha256="e" * 64)
    plan = {"python": sys.executable, "content_sha256": "c" * 64}
    calls: list[str] = []
    monkeypatch.setattr(watcher.recovery, "load_plan", lambda _: plan)
    monkeypatch.setattr(watcher.recovery, "require_apfs", lambda _: None)
    monkeypatch.setattr(watcher.recovery, "require_free_space", lambda _, gib: None)
    monkeypatch.setattr(watcher, "require_hashes", lambda *_: calls.append("hashes"))
    monkeypatch.setattr(watcher, "require_clean_checkout", lambda _: calls.append("checkout"))

    def successor_start(*_: object) -> tuple[dict, dict]:
        calls.append("successor_start")
        return {"pid": 1234}, {"analysis_binding": {}}

    monkeypatch.setattr(watcher, "require_successor_start", successor_start)
    monkeypatch.setattr(watcher, "wait_for_successor", lambda *_: calls.append("wait"))

    def capture_child(folder: Path, command: list[str], _: dict) -> None:
        calls.append(folder.name)
        assert "run_reuse.py" not in " ".join(command)
        if folder.name == "seal_lineage":
            write(run / "recovery_continuation.json", {"sealed": True})
        elif fail_stage:
            raise RuntimeError("invented stage failure")
        else:
            (destination / "manifest.json").parent.mkdir()
            write(destination / "manifest.json", {"staged": True})
            write(destination.with_name(destination.name + ".replay-stage.json"), {
                "status": "complete_first_draw_replay_staged_for_recovered_run",
                "staged_contexts": 1650, "staged_files": 6603,
                "recovery_continuation_sha256": recovery.sha256_file(
                    run / "recovery_continuation.json")})

    monkeypatch.setattr(watcher, "captured_command", capture_child)
    if fail_stage:
        with pytest.raises(RuntimeError, match="invented stage failure"):
            watcher.run(args)
        assert (control / "post_successor_stage.claim").is_file()
        assert recovery.read_json(capture / "failure.json")["claim_retained_for_review"] is True
    else:
        watcher.run(args)
        assert not (control / "post_successor_stage.claim").exists()
        assert recovery.read_json(capture / "complete.json")["corrected_fits_executed"] is False
    assert calls[:7] == ["hashes", "checkout", "successor_start", "wait",
                         "checkout", "hashes", "successor_start"]
    assert calls[7:] == ["seal_lineage", "checkout", "hashes", "stage_replay"]


def fixture_v2_successor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                         ) -> tuple[SimpleNamespace, dict, dict, dict, Path]:
    """Make an invented V2 launch with actual hashes and a separate claim."""
    control = tmp_path / "control"
    runtime = tmp_path / "runtime"
    script = runtime / "scripts/continue_recovered_extension.py"
    script.parent.mkdir(parents=True)
    script.write_text("# invented V2 successor\n", encoding="utf-8")
    capture = control / "continuation_captures/sequential-v2"
    run = tmp_path / "recovered"
    git_dir = tmp_path / "frozen-git/.git"
    monkeypatch.setattr(watcher.supervisor_v2, "MAC_GIT_DIR", git_dir)
    supervisor_launch_sha = write(control / "captures/sequential-v2.launch.json",
                                  {"invented": "supervisor launch"})
    supervisor_source_sha = "e" * 64
    supervisor_published = tmp_path / "supervisor-published.json"
    supervisor_published_sha = write(supervisor_published, {
        "v2_supervisor_source_sha256": supervisor_source_sha})
    monkeypatch.setattr(watcher, "PUBLISHED_SUPERVISOR_V2", supervisor_published)
    plan = {"python": sys.executable, "content_sha256": "1" * 64,
            "source_manifest_sha256": watcher.PINS["recovered_run_manifest"]}
    plan_sha = write(control / "plan.json", plan)
    binding = {"analysis_git_commit": "a" * 40,
               "successor_sha256": recovery.sha256_file(script),
               "supervisor_version": "v2", "v2_supervisor_sha256": supervisor_source_sha}
    start = {"owner_pid": 4567, "analysis_binding": binding,
             "production_git_dir": str(git_dir), "plan_sha256": plan["content_sha256"],
             "control": str(control), "recovered_run": str(run),
             "assembly_plan": str(control / "assembly_adapter_plan_v2.json"),
             "supervisor_version": "v2", "successor_source_sha256": binding["successor_sha256"],
             "supervisor_source_sha256": supervisor_source_sha,
             "supervisor_launch_sha256": supervisor_launch_sha}
    start_sha = write(capture / "start.json", start)
    argv = [plan["python"], "-I", "-B", str(script), "--supervisor-version", "v2",
            "--control", str(control), "--recovered-run", str(run),
            "--assembly-plan", start["assembly_plan"], "--capture-root", str(capture),
            "--production-git-dir", str(git_dir), "--poll-seconds", "60", "--execute"]
    launch = {"pid": 4567, "cwd": str(watcher.supervisor_v2.SAFE_CWD), "argv": argv,
              "control": str(control), "recovered_run": str(run),
              "assembly_plan": start["assembly_plan"], "capture_root": str(capture),
              "production_git_dir": str(git_dir), "plan_file_sha256": plan_sha,
              "analysis_git_commit": binding["analysis_git_commit"],
              "successor_sha256": binding["successor_sha256"],
              "supervisor_launch_sha256": supervisor_launch_sha}
    launch_sha = write(control / "continuation_captures/sequential-v2.launch.json", launch)
    claim = {"pid": 4567, "capture_root": str(capture),
             "plan_sha256": plan["content_sha256"], "supervisor_version": "v2"}
    claim_path = control / "continuation_supervisor_v2.claim"
    claim_sha = write(claim_path, claim)
    write(control / "continuation_captures/sequential-v2.claim-at-launch.json", claim)
    published = tmp_path / "successor-published.json"
    write(published, {"schema_version": 1, "control": str(control),
                      "recovered_run": str(run), "assembly_plan": start["assembly_plan"],
                      "runtime_checkout": str(runtime),
                      "fixed_plan_file_sha256": plan_sha,
                      "fixed_plan_content_sha256": plan["content_sha256"],
                      "successor_launch_sha256": launch_sha,
                      "successor_start_sha256": start_sha,
                      "successor_source_sha256": binding["successor_sha256"],
                      "analysis_git_commit": binding["analysis_git_commit"],
                      "successor_pid_at_checkpoint": 4567,
                      "successor_claim_sha256_at_checkpoint": claim_sha,
                      "supervisor_launch_sha256": supervisor_launch_sha,
                      "supervisor_published_launch_sha256": supervisor_published_sha,
                      "v1_failed_chain_preserved": True})
    monkeypatch.setattr(watcher, "PUBLISHED_SUCCESSOR_V2", published)
    args = SimpleNamespace(supervisor_version="v2", control=control, recovered_run=run,
                           plan_file_sha256=plan_sha,
                           plan_content_sha256=plan["content_sha256"],
                           successor_launch_sha256=launch_sha,
                           successor_start_sha256=start_sha, poll_seconds=1)
    return args, plan, launch, start, claim_path


def test_v2_start_is_bound_to_published_launch_and_clean_runtime(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args, plan, launch, start, _ = fixture_v2_successor(tmp_path, monkeypatch)
    monkeypatch.setattr(watcher.adapter, "require_clean_published_adapter",
                        lambda _: launch["analysis_git_commit"])
    assert watcher.require_successor_start(args, plan) == (launch, start)
    published = recovery.read_json(watcher.PUBLISHED_SUCCESSOR_V2)
    published["v1_failed_chain_preserved"] = False
    write(watcher.PUBLISHED_SUCCESSOR_V2, published)
    with pytest.raises(ValueError, match="preserved V1 chain"):
        watcher.require_hashes(args, plan)
    published["v1_failed_chain_preserved"] = True
    write(watcher.PUBLISHED_SUCCESSOR_V2, published)
    start["supervisor_launch_sha256"] = "0" * 64
    write(args.control / "continuation_captures/sequential-v2/start.json", start)
    with pytest.raises(ValueError, match="explicit pins"):
        watcher.require_successor_start(args, plan)


def test_v2_wait_requires_hashed_zero_returns_and_released_claim(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args, plan, launch, start, claim = fixture_v2_successor(tmp_path, monkeypatch)
    capture = args.control / "continuation_captures/sequential-v2"
    supervisor_complete = write(args.control / "captures/sequential-v2/complete.json",
                                {"verified_refits": 21})
    salvage_sha = write(args.control / "captures/no-fit-salvage-r01f03-v1/proof.json",
                        {"new_fits_executed": 0})
    workers = {}
    for worker in range(6):
        folder = capture / f"worker_{worker}"
        workers[str(worker)] = write(folder / "verified_worker.json", {"worker": worker})
        write(folder / "return.json", {"return_code": 0})
    complete = {"status": "full_grid_stored_pending_deep_verification",
                "plan_sha256": plan["content_sha256"], "analysis_binding": start["analysis_binding"],
                "stored": 1625, "new_continuation_cells": 411,
                "verified_worker_sha256": workers, "supervisor_version": "v2",
                "supervisor_source_sha256": start["supervisor_source_sha256"],
                "successor_source_sha256": start["successor_source_sha256"],
                "supervisor_launch_sha256": start["supervisor_launch_sha256"],
                "supervisor_complete_sha256": supervisor_complete,
                "salvage_proof_sha256": salvage_sha, "v1_failure_preserved": True}
    write(capture / "complete.json", complete)
    monkeypatch.setattr(watcher.supervisor, "process_exists", lambda _: True)
    monkeypatch.setattr(watcher.time, "sleep", lambda _: claim.unlink())
    assert watcher.wait_for_successor(args, plan, launch, start) == complete
    write(capture / "worker_5/return.json", {"return_code": 1})
    with pytest.raises(ValueError, match="lacks zero return"):
        watcher.wait_for_successor(args, plan, launch, start)


@pytest.mark.parametrize("fail_stage", [False, True])
def test_v2_watcher_seals_only_after_history_and_keeps_v1_claim(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fail_stage: bool) -> None:
    control = tmp_path / "control"
    control.mkdir()
    run = tmp_path / "recovered"
    capture = control / "post_successor_captures/sequential-v2"
    successor_complete_sha = write(
        control / "continuation_captures/sequential-v2/complete.json", {"complete": True})
    old_claim = control / "post_successor_stage.claim"
    old_sha = write(old_claim, {"old_failure": True})
    destination = tmp_path / "staged"
    args = SimpleNamespace(execute=True, supervisor_version="v2", poll_seconds=1,
                           control=control, recovered_run=run, capture_root=capture,
                           source_replay=tmp_path / "source", preflight_output=tmp_path / "preflight",
                           contexts=tmp_path / "contexts.jsonl", destination=destination,
                           python=sys.executable, checkout_commit="a" * 40,
                           plan_file_sha256="b" * 64, plan_content_sha256="c" * 64,
                           successor_launch_sha256="d" * 64, successor_start_sha256="e" * 64)
    plan = {"python": sys.executable, "content_sha256": "c" * 64}
    historical = {"salvage_proof_sha256": "f" * 64,
                  "preserved_v1_sha256": {"old_claim": old_sha}}
    calls: list[str] = []
    monkeypatch.setattr(watcher.recovery, "load_plan", lambda _: plan)
    monkeypatch.setattr(watcher.recovery, "require_apfs", lambda _: None)
    monkeypatch.setattr(watcher.recovery, "require_free_space", lambda _, gib: None)
    monkeypatch.setattr(watcher, "require_hashes", lambda *_: calls.append("hashes"))
    monkeypatch.setattr(watcher, "require_clean_checkout", lambda _: calls.append("checkout"))
    monkeypatch.setattr(watcher, "require_v2_history", lambda *_: (calls.append("history"), historical)[1])

    def successor_start(*_: object) -> tuple[dict, dict]:
        calls.append("successor_start")
        return {"pid": 4567}, {"analysis_binding": {}}

    monkeypatch.setattr(watcher, "require_successor_start", successor_start)
    monkeypatch.setattr(watcher, "wait_for_successor", lambda *_: calls.append("wait"))

    def capture_child(folder: Path, command: list[str], _: dict, cwd: Path) -> None:
        calls.append(folder.name)
        assert cwd == watcher.supervisor_v2.SAFE_CWD
        assert "run_reuse.py" not in " ".join(command)
        if folder.name == "seal_lineage":
            assert command[-2:] == ["--supervisor-version", "v2"]
            write(run / "recovery_continuation.json", {
                "supervisor_version": "v2",
                "continuation_complete_sha256": successor_complete_sha,
                "v2_source_sha256": {"salvage_proof_sha256": historical["salvage_proof_sha256"]}})
        elif fail_stage:
            raise RuntimeError("invented V2 stage failure")
        else:
            write(destination / "manifest.json", {"staged": True})
            write(destination.with_name(destination.name + ".replay-stage.json"), {
                "status": "complete_first_draw_replay_staged_for_recovered_run",
                "staged_contexts": 1650, "staged_files": 6603,
                "recovery_continuation_sha256": recovery.sha256_file(
                    run / "recovery_continuation.json")})

    monkeypatch.setattr(watcher, "captured_command", capture_child)
    if fail_stage:
        with pytest.raises(RuntimeError, match="invented V2 stage failure"):
            watcher.run(args)
        assert (control / "post_successor_stage_v2.claim").is_file()
        assert recovery.read_json(capture / "failure.json")["claim_retained_for_review"] is True
    else:
        watcher.run(args)
        assert not (control / "post_successor_stage_v2.claim").exists()
        assert recovery.read_json(capture / "complete.json")["supervisor_version"] == "v2"
    assert recovery.sha256_file(old_claim) == old_sha
    assert calls.index("history") < calls.index("wait") < calls.index("seal_lineage")
