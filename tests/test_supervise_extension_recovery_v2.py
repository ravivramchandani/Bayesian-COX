"""Invented V2 recovery evidence; tests never dispatch a numerical model."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from scripts import salvage_extension_refit_comparison as salvage
from scripts import supervise_extension_recovery_v2 as v2


def write(path: Path, value: dict[str, Any]) -> None:
    """Write a small invented receipt under a temporary test root."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def invented_salvage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                     ) -> tuple[Path, dict[str, Any], Path]:
    """Build a sealed zero-fit proof independent of any real scientific output."""
    control = tmp_path / "control"
    capture = control / "captures/no-fit-salvage-r01f03-v1"
    capture.mkdir(parents=True)
    plan = {"python": sys.executable, "content_sha256": salvage.PLAN_CONTENT_SHA256}
    cell_path = control / "refits" / salvage.IDENTITY / "attempt_001/run/cells" / \
        f"{salvage.IDENTITY}.json"
    cell_path.parent.mkdir(parents=True)
    cell_path.write_text("{}\n", encoding="utf-8")
    comparison = cell_path.parents[2] / "scientific_comparison.json"
    write(comparison, {"official_non_timing_science": "match"})
    old, child = {"old_failure": "a" * 64}, {"child_return": "b" * 64}
    fourth = {"official_refit_proof": {"child_return_code": 0},
              "cell_file_sha256": "c" * 64, "trace_sha256": {}}
    monkeypatch.setattr(v2.salvage, "failure_capture", lambda *_: old)
    monkeypatch.setattr(v2.salvage, "completed_child",
                        lambda *_args, **_kwargs: (cell_path, child))
    monkeypatch.setattr(v2, "verified_refit", lambda *_: fourth)
    monkeypatch.setattr(v2, "SAFE_CWD", tmp_path)
    write(capture / "start.json", {
        "stable_cwd": str(tmp_path), "identity": salvage.IDENTITY,
        "no_fit_comparison_only": True,
        "prior": {"old_failed_capture_sha256": old, "completed_child_sha256": child}})
    token = "d" * 32
    write(capture / "launch.json", {
        "command": salvage.child_command(plan, control, capture, token),
        "cwd": str(tmp_path), "script_sha256": v2.file_sha(Path(salvage.__file__))})
    write(capture / "return.json", {"return_code": 0})
    (capture / "stdout.log").write_text("match\n", encoding="utf-8")
    (capture / "stderr.log").write_text("", encoding="utf-8")
    proof = {"status": "fourth_refit_postfit_comparison_salvaged",
             "cell_id": salvage.IDENTITY,
             "plan_file_sha256": salvage.PLAN_FILE_SHA256,
             "plan_content_sha256": salvage.PLAN_CONTENT_SHA256,
             "old_wrapper_return_code": 1,
             "saved_fit_child_return_code": 0,
             "new_comparison_child_return_code": 0,
             "new_fits_executed": 0, "old_failure_preserved": True,
             "old_failed_capture_sha256": old, "saved_child_sha256": child,
             "official_refit_proof": fourth["official_refit_proof"],
             "scientific_comparison_sha256": v2.file_sha(comparison),
             **{key: v2.file_sha(capture / name) for key, name in
                {"launch_sha256": "launch.json", "return_sha256": "return.json",
                 "stdout_sha256": "stdout.log", "stderr_sha256": "stderr.log"}.items()}}
    proof["content_sha256"] = v2.recovery.content_sha256(proof)
    write(capture / "proof.json", proof)
    write(capture / "complete.json", {
        "proof_sha256": v2.file_sha(capture / "proof.json"),
        "plan_content_sha256": salvage.PLAN_CONTENT_SHA256, "new_fits_executed": 0})
    return control, plan, capture


def test_salvage_gate_requires_exact_separate_zero_fit_proof(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control, plan, capture = invented_salvage(tmp_path, monkeypatch)
    bound = v2.require_salvage(control, plan)
    assert bound["salvage_proof_sha256"] == v2.file_sha(capture / "proof.json")
    complete = v2.recovery.read_json(capture / "complete.json")
    complete["new_fits_executed"] = 1
    write(capture / "complete.json", complete)
    with pytest.raises(ValueError, match="proof or completion differs"):
        v2.require_salvage(control, plan)
    complete["new_fits_executed"] = 0
    write(capture / "complete.json", complete)
    monkeypatch.setattr(v2.salvage, "failure_capture", lambda *_: {"changed": "failure"})
    with pytest.raises(ValueError, match="old failure and saved fit"):
        v2.require_salvage(control, plan)


def test_exact_initial_attempt_roster_rejects_extra_or_second_attempt(
        tmp_path: Path) -> None:
    control = tmp_path / "control"
    plan = {"affected_cell_ids": [salvage.IDENTITY, "new"]}
    (control / "refits" / salvage.IDENTITY / "attempt_001").mkdir(parents=True)
    assert v2.attempt_roster(control, plan) == {salvage.IDENTITY}
    (control / "refits" / salvage.IDENTITY / "attempt_002").mkdir()
    with pytest.raises(ValueError, match="unexpected refit attempt"):
        v2.attempt_roster(control, plan)


def test_v2_binding_pins_its_own_source_across_dispatch(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(v2.v1, "require_launch_binding",
                        lambda *_: {"analysis_git_commit": "a" * 40})
    commands: list[list[str]] = []
    monkeypatch.setattr(v2.subprocess, "run",
                        lambda command, **_kwargs: commands.append(command))
    binding = v2.analysis_binding({}, tmp_path)
    assert binding["v2_supervisor_sha256"] == v2.file_sha(Path(v2.__file__))
    assert binding["salvage_script_sha256"] == v2.file_sha(Path(salvage.__file__))
    assert "scripts/supervise_extension_recovery_v2.py" in commands[0]
    v2.analysis_binding({}, tmp_path, binding)
    with pytest.raises(ValueError, match="source changed"):
        v2.analysis_binding({}, tmp_path, {**binding, "v2_supervisor_sha256": "0" * 64})


def worker_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch
                   ) -> tuple[Path, Path, Path, dict[str, Any], dict[str, Any]]:
    """Set up an empty fixed shard with all expensive guards replaced by stubs."""
    control = tmp_path / "control"
    (control / "refits").mkdir(parents=True)
    capture = control / "captures/sequential-v2/01_worker0_cell"
    capture.parent.mkdir(parents=True)
    git_dir = tmp_path / "git/.git"
    git_dir.mkdir(parents=True)
    plan = {"workers": 6, "python": sys.executable, "sealed": str(tmp_path / "sealed"),
            "content_sha256": salvage.PLAN_CONTENT_SHA256,
            "affected_cell_ids": ["expected", "wrong"],
            "shards": [["expected", "wrong"], [], [], [], [], []]}
    binding = {"analysis_git_commit": "a" * 40, "v2_supervisor_sha256": "b" * 64}
    monkeypatch.setattr(v2, "SAFE_CWD", tmp_path)
    monkeypatch.setattr(v2.v1, "require_idle", lambda *_: None)
    monkeypatch.setattr(v2, "analysis_binding", lambda *_args: binding)
    monkeypatch.setattr(v2, "require_salvage", lambda *_: {"salvage_proof_sha256": "c" * 64})
    return control, capture, git_dir, plan, binding


def test_v2_worker_captures_stable_cwd_and_rejects_nonzero_return(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control, capture, git_dir, plan, binding = worker_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(v2, "launch_worker", lambda *_: (777, 1))
    with pytest.raises(ValueError, match="returned 1"):
        v2.run_captured_worker(capture, control, plan, git_dir, binding,
                               {"salvage_proof_sha256": "c" * 64}, 0, "expected", {})
    launch = v2.recovery.read_json(capture / "launch.json")
    assert launch["cwd"] == str(tmp_path)
    assert launch["git_environment"] == {
        "GIT_DIR": str(git_dir), "GIT_WORK_TREE": plan["sealed"], "GIT_OPTIONAL_LOCKS": "0"}
    assert "run-worker" in launch["command"] and launch["expected_cell"] == "expected"
    assert v2.recovery.read_json(capture / "return.json")["return_code"] == 1
    assert not (capture / "verified_refit.json").exists()


def test_v2_worker_rejects_unexpected_attempt_after_zero_return(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control, capture, git_dir, plan, binding = worker_fixture(tmp_path, monkeypatch)

    def wrong_child(*_args: Any) -> tuple[int, int]:
        (control / "refits/wrong/attempt_001").mkdir(parents=True)
        return 778, 0

    monkeypatch.setattr(v2, "launch_worker", wrong_child)
    with pytest.raises(ValueError, match="unexpected attempt"):
        v2.run_captured_worker(capture, control, plan, git_dir, binding,
                               {"salvage_proof_sha256": "c" * 64}, 0, "expected", {})
    assert not (capture / "verified_refit.json").exists()


def test_v2_supervisor_skips_four_and_dispatches_exactly_seventeen_invented_cells(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control = tmp_path / "control"
    (control / "captures").mkdir(parents=True)
    (control / "refits").mkdir()
    (control / "worker_returns").mkdir()
    for identity in v2.FIRST_FOUR:
        (control / "refits" / identity / "attempt_001").mkdir(parents=True)
    old_claim = control / "sequential_supervisor.claim"
    write(old_claim, {"old_failure_preserved": True})
    git_dir = tmp_path / "git/.git"
    git_dir.mkdir(parents=True)
    monkeypatch.setattr(v2, "MAC_GIT_DIR", git_dir)
    fresh = [f"new_{number:02d}" for number in range(17)]
    existing = sorted(v2.FIRST_FOUR - {salvage.IDENTITY})
    shards = [[salvage.IDENTITY, *fresh[:2]], fresh[2:5], fresh[5:8],
              [existing[0], *fresh[8:11]], [existing[1], *fresh[11:14]],
              [existing[2], *fresh[14:]]]
    plan = {"workers": 6, "affected_cell_ids": [row for shard in shards for row in shard],
            "shards": shards, "content_sha256": salvage.PLAN_CONTENT_SHA256}
    write(control / "plan.json", {"invented": True})
    monkeypatch.setattr(v2.recovery, "load_plan", lambda _: plan)
    monkeypatch.setattr(v2.recovery, "require_apfs", lambda _: None)
    monkeypatch.setattr(v2.v1, "require_idle", lambda *_: None)
    monkeypatch.setattr(v2, "SAFE_CWD", tmp_path)
    monkeypatch.chdir(tmp_path)
    real_file_sha = v2.file_sha
    monkeypatch.setattr(v2, "file_sha", lambda path: (
        salvage.PLAN_FILE_SHA256 if path.name == "plan.json" else real_file_sha(path)))
    binding = {"analysis_git_commit": "a" * 40, "v2_supervisor_sha256": "b" * 64}
    monkeypatch.setattr(v2, "analysis_binding", lambda *_args: binding)
    proof = {"salvage_proof_sha256": "c" * 64,
             "fourth_refit": {"identity": salvage.IDENTITY}}
    monkeypatch.setattr(v2, "require_salvage", lambda *_: proof)
    monkeypatch.setattr(v2, "verified_refit", lambda _control, _plan, identity:
                        {"identity": identity})
    proof["fourth_refit"] = {"identity": salvage.IDENTITY}
    called: list[tuple[int, str | None]] = []

    def fake_worker(capture: Path, _control: Path, _plan: dict[str, Any],
                    _git_dir: Path, _binding: dict[str, Any], _salvage: dict[str, Any],
                    worker: int, expected_cell: str | None,
                    _prior: dict[str, dict[str, Any]]) -> dict[str, Any]:
        capture.mkdir()
        called.append((worker, expected_cell))
        if expected_cell is not None:
            (control / "refits" / expected_cell / "attempt_001").mkdir(parents=True)
            return {expected_cell: {"identity": expected_cell}}
        write(control / "worker_returns" / f"worker_{worker}.json",
              {"worker": worker, "status": "complete", "cell_ids": plan["shards"][worker]})
        return {}

    monkeypatch.setattr(v2, "run_captured_worker", fake_worker)
    args = SimpleNamespace(
        execute=True, control=control,
        capture_root=control / "captures/sequential-v2", production_git_dir=git_dir)
    extra = control / "refits" / fresh[0] / "attempt_001"
    extra.mkdir(parents=True)
    with pytest.raises(ValueError, match="exactly the four"):
        v2.run(args)
    assert not args.capture_root.exists() and not (control / v2.CLAIM_NAME).exists()
    extra.rmdir()
    extra.parent.rmdir()
    result = v2.run(args)
    assert result["new_refits"] == 17 and result["verified_refits"] == 21
    assert len([identity for _, identity in called if identity is not None]) == 17
    assert len([identity for _, identity in called if identity is None]) == 6
    assert old_claim.is_file()
    assert not (control / v2.CLAIM_NAME).exists()
    assert (control / "captures/sequential-v2/complete.json").is_file()
