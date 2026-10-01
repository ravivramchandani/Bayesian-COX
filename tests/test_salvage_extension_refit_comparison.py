"""Invented post-fit salvage evidence; no numerical fit or real capture is run."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from scripts import salvage_extension_refit_comparison as salvage
from src.utils.reproducibility import canonical_json_hash


def write(path: Path, value: dict[str, Any]) -> None:
    """Write a small invented receipt in a fresh test directory."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def old_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, dict[str, Any]]:
    """Make an exact-shaped rc1 wrapper with a distinct completed supervisor."""
    control = tmp_path / "control"
    capture = control / "captures/worker00_ramp2"
    capture.mkdir(parents=True)
    repo = tmp_path / "repo"
    published_path = repo / "coordination/recovery/2026-10-01-fourth-extension-recovery-launch.json"
    controller = repo / "scripts/recover_extension_run.py"
    controller.parent.mkdir(parents=True)
    controller.write_text("# invented frozen controller\n", encoding="utf-8")
    helper = capture / "capture.py"
    helper.write_text("# invented capture\n", encoding="utf-8")
    plan = {"python": sys.executable, "sealed": str(tmp_path / "frozen"),
            "controller_sha256": salvage.file_sha(controller),
            "content_sha256": "7" * 64}
    command = ["/usr/bin/caffeinate", "-dimsu", "/usr/bin/nice", "-n", "10",
               plan["python"], "-B", str(controller), "run-worker", "--control", str(control),
               "--worker", "0", "--max-new-cells", "1", "--execute"]
    write(capture / "launch.json", {"command": command, "git_work_tree": plan["sealed"],
                                    "caffeinate_pid": 222})
    write(capture / "wrapper_start.json", {"wrapper_pid": 111,
                                           "expected_cell_id": salvage.IDENTITY})
    write(capture / "return.json", {"wrapper_pid": 111, "caffeinate_pid": 222,
                                    "return_code": 1})
    (capture / "worker.stderr.log").write_text(
        "compare_refit get_arviz_rcfile os.getcwd() FileNotFoundError\n", encoding="utf-8")
    pins = {name: salvage.file_sha(capture / name) for name in salvage.FAILED_CAPTURE_FILES}
    monkeypatch.setattr(salvage, "FAILED_CAPTURE_FILES", pins)
    monkeypatch.setattr(salvage, "PLAN_FILE_SHA256", "8" * 64)
    monkeypatch.setattr(salvage.recovery, "REPO", repo)
    monkeypatch.setattr(salvage, "alive", lambda _: False)
    write(published_path, {"capture_directory": str(capture), "cell_id": salvage.IDENTITY,
                           "control_plan_sha256": salvage.PLAN_FILE_SHA256,
                           "launch_sha256": pins["launch.json"],
                           "wrapper_start_sha256": pins["wrapper_start.json"],
                           "capture_script_sha256": salvage.file_sha(helper)})
    write(control / "sequential_supervisor.claim", {
        "plan_sha256": plan["content_sha256"],
        "capture_root": str(control / "captures/sequential-v1"), "pid": 333})
    write(control / "captures/sequential-v1/failure.json", {
        "error": "prior captured worker did not return zero",
        "supervisor_claim_retained": True})
    return control, plan


def test_binds_exact_old_postfit_failure_and_rejects_relabelled_rc0(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control, plan = old_failure(tmp_path, monkeypatch)
    result = salvage.failure_capture(control, plan)
    assert result["return.json"] == salvage.FAILED_CAPTURE_FILES["return.json"]
    assert result["v1_supervisor_claim"] == salvage.file_sha(control / "sequential_supervisor.claim")
    return_path = control / "captures/worker00_ramp2/return.json"
    returned = json.loads(return_path.read_text())
    returned["return_code"] = 0
    write(return_path, returned)
    monkeypatch.setattr(salvage, "FAILED_CAPTURE_FILES", {
        **salvage.FAILED_CAPTURE_FILES, "return.json": salvage.file_sha(return_path)})
    with pytest.raises(ValueError, match="exact rc1 capture"):
        salvage.failure_capture(control, plan)


def invented_salvage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[SimpleNamespace, Path, Path]:
    """Prepare the capture orchestration with a fake zero-cost comparison child."""
    control = tmp_path / "control"
    (control / "captures").mkdir(parents=True)
    git_dir = tmp_path / "gitdir"
    git_dir.mkdir()
    source = tmp_path / "source"
    source.mkdir()
    cell_path = control / "refits" / salvage.IDENTITY / "attempt_001/run/cells" / f"{salvage.IDENTITY}.json"
    value = {"cell_id": salvage.IDENTITY, "status": "failed_diagnostics", "fit_attempts": []}
    value["cell_content_sha256"] = canonical_json_hash(value)
    write(cell_path, value)
    plan = {"python": sys.executable, "content_sha256": salvage.PLAN_CONTENT_SHA256,
            "source": str(source)}
    prior = {"old_failed_capture_sha256": {"return.json": "a" * 64},
             "completed_child_sha256": {"cell": salvage.file_sha(cell_path)}}
    monkeypatch.setattr(salvage, "preflight", lambda *_: (plan, prior))
    monkeypatch.setattr(salvage, "failure_capture", lambda *_: prior["old_failed_capture_sha256"])

    def completed(_control: Path, _plan: dict[str, Any], *, comparison_exists: bool = False
                  ) -> tuple[Path, dict[str, str]]:
        assert comparison_exists is True
        return cell_path, prior["completed_child_sha256"]

    monkeypatch.setattr(salvage, "completed_child", completed)
    monkeypatch.setattr(salvage.adapter, "require_refit_proof",
                        lambda *_: {"official_non_timing_science": "match", "child_return_code": 0})
    monkeypatch.setattr(salvage.recovery, "require_apfs", lambda _: None)
    monkeypatch.setattr(salvage, "SAFE_CWD", tmp_path)
    monkeypatch.chdir(tmp_path)
    args = SimpleNamespace(execute=True, control=control,
                           capture_root=control / "captures/no-fit-salvage-r01f03-v1",
                           production_git_dir=git_dir)
    return args, control, cell_path


def test_captured_salvage_records_new_comparison_without_fit(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args, control, cell_path = invented_salvage(tmp_path, monkeypatch)

    def fake_child(command: list[str], cwd: Path, _environment: dict[str, str],
                   stdout: Any, _stderr: Any) -> tuple[int, int]:
        assert command[4] == "compare-child" and "run-worker" not in command
        assert cwd == tmp_path
        write(cell_path.parents[2] / "scientific_comparison.json",
              {"cell_id": salvage.IDENTITY, "official_non_timing_science": "match"})
        stdout.write("scientific_match\n")
        return 444, 0

    monkeypatch.setattr(salvage, "launch_child", fake_child)
    result = salvage.salvage(args)
    capture = args.capture_root
    assert result["status"] == "fourth_refit_postfit_comparison_salvaged"
    assert result["old_wrapper_return_code"] == 1
    assert result["saved_fit_child_return_code"] == 0
    assert result["new_fits_executed"] == 0
    assert salvage.recovery.read_json(capture / "return.json")["return_code"] == 0
    assert salvage.recovery.read_json(capture / "complete.json")["new_fits_executed"] == 0
    assert not (control / "no_fit_salvage.claim").exists()
    assert salvage.recovery.read_json(capture / "proof.json")["content_sha256"] == \
        salvage.recovery.content_sha256({key: value for key, value in result.items()
                                         if key != "content_sha256"})


def test_failed_comparison_retains_new_claim_and_does_not_issue_proof(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    args, control, _ = invented_salvage(tmp_path, monkeypatch)
    monkeypatch.setattr(salvage, "launch_child", lambda *_: (555, 1))
    with pytest.raises(ValueError, match="did not return zero"):
        salvage.salvage(args)
    assert (control / "no_fit_salvage.claim").is_file()
    assert salvage.recovery.read_json(args.capture_root / "failure.json")["claim_retained_for_review"] is True
    assert not (args.capture_root / "proof.json").exists()
    assert not (args.capture_root / "complete.json").exists()


def test_child_command_can_only_compare(tmp_path: Path) -> None:
    plan = {"python": sys.executable}
    command = salvage.child_command(plan, tmp_path / "control", tmp_path / "capture", "a" * 32)
    assert command[1:5] == ["-I", "-B", str(Path(salvage.__file__).resolve()), "compare-child"]
    assert "run-worker" not in command and "child" not in command


def test_compare_child_binds_exact_frozen_module(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    control = tmp_path / "control"
    capture = control / "captures/no-fit-salvage-r01f03-v1"
    capture.mkdir(parents=True)
    sealed = tmp_path / "sealed"
    script = sealed / "scripts/reproduce_extensions.py"
    script.parent.mkdir(parents=True)
    script.write_text("def scientific_content(value):\n    return {'frozen': value}\n", encoding="utf-8")
    source = tmp_path / "source"
    write(source / "manifest.json", {"input_sha256": {
        "scripts/reproduce_extensions.py": salvage.file_sha(script)}})
    write(control / "no_fit_salvage.claim", {"capture_root": str(capture),
                                             "token": "a" * 32, "parent_pid": 777})
    plan = {"content_sha256": salvage.PLAN_CONTENT_SHA256,
            "python": sys.executable, "sealed": str(sealed), "source": str(source)}
    monkeypatch.setattr(salvage, "SAFE_CWD", tmp_path)
    monkeypatch.setattr(salvage.os, "getppid", lambda: 777)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(salvage.recovery, "load_plan", lambda _: plan)
    foreign = ModuleType("scripts.reproduce_extensions")
    foreign.scientific_content = lambda value: {"wrong": value}
    monkeypatch.setitem(sys.modules, "scripts.reproduce_extensions", foreign)

    def exact_comparison(_control: Path, _plan: dict[str, Any], _identity: str,
                         _run: Path) -> dict[str, str]:
        from scripts.reproduce_extensions import scientific_content

        assert scientific_content(3) == {"frozen": 3}
        assert Path(sys.modules["scripts.reproduce_extensions"].__file__) == script
        return {"official_non_timing_science": "match"}

    monkeypatch.setattr(salvage.recovery, "compare_refit", exact_comparison)
    salvage.compare_child(SimpleNamespace(control=control, capture_root=capture, token="a" * 32))
