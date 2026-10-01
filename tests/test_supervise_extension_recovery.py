"""Guard the unattended recovery wrapper without launching numerical work."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import assemble_recovered_extension as adapter
from scripts import recover_extension_run as recovery
from scripts import supervise_extension_recovery as supervisor

CELL = "metabric_matched__expression__r01f03__bayesian_spike_slab__full"


def prior_capture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, Path, dict]:
    """Build a typed first-attempt capture with the exact planned command."""
    control = tmp_path / "control"
    capture = control / "captures" / "worker00_ramp2"
    git_dir = tmp_path / "frozen" / ".git"
    capture.mkdir(parents=True)
    plan = {"python": "/locked/bin/python", "sealed": "/frozen/source",
            "content_sha256": "plan_hash",
            "shards": [[CELL]]}
    launch = {"wrapper_pid": 1234, "caffeinate_pid": 1235,
              "cwd": str(recovery.REPO),
              "command": supervisor.worker_command(plan, control, 0, 1),
              "git_dir": str(git_dir), "git_work_tree": plan["sealed"]}
    (capture / "launch.json").write_text(json.dumps(launch) + "\n")
    (capture / "capture.py").write_text("# captured source\n")
    wrapper_start = {"wrapper_pid": 1234, "expected_cell_id": CELL}
    (capture / "wrapper_start.json").write_text(json.dumps(wrapper_start) + "\n")
    (capture / "return.json").write_text(json.dumps({"wrapper_pid": 1234,
                                                       "caffeinate_pid": 1235,
                                                       "return_code": 0}) + "\n")
    receipt = {"capture_directory": str(capture), "control": str(control),
               "cell_id": CELL, "control_plan_sha256": plan["content_sha256"],
               "capture_script_sha256": recovery.sha256_file(capture / "capture.py"),
               "launch_sha256": recovery.sha256_file(capture / "launch.json"),
               "wrapper_start_sha256": recovery.sha256_file(capture / "wrapper_start.json")}
    receipt_file = tmp_path / "prior_launch_receipt.json"
    receipt_file.write_text(json.dumps(receipt) + "\n")
    monkeypatch.setattr(supervisor, "PRIOR_LAUNCH_RECEIPT", receipt_file)
    return capture, control, git_dir, plan


def test_prior_capture_requires_exact_dispatch_and_successful_return(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capture, control, git_dir, plan = prior_capture(tmp_path, monkeypatch)
    observed: list[str] = []
    monkeypatch.setattr(supervisor, "require_completed_refit",
                        lambda _control, _plan, identity: observed.append(identity))
    monkeypatch.setattr(supervisor, "require_launch_binding", lambda *_args: {})
    supervisor.wait_for_capture(capture, CELL, control, plan, git_dir, {}, 1)
    assert observed == [CELL]
    returned = recovery.read_json(capture / "return.json")
    returned["return_code"] = 1
    (capture / "return.json").write_text(json.dumps(returned) + "\n")
    with pytest.raises(RuntimeError, match="did not return zero"):
        supervisor.wait_for_capture(capture, CELL, control, plan, git_dir, {}, 1)
    launch = recovery.read_json(capture / "launch.json")
    launch["command"][-2] = "2"
    (capture / "launch.json").write_text(json.dumps(launch) + "\n")
    with pytest.raises(ValueError, match="fixed recovery dispatch"):
        supervisor.wait_for_capture(capture, CELL, control, plan, git_dir, {}, 1)


def test_prior_capture_waits_for_complete_typed_return(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    capture, control, git_dir, plan = prior_capture(tmp_path, monkeypatch)
    (capture / "return.json").write_text("{\n")
    monkeypatch.setattr(supervisor, "process_exists", lambda _pid: True)
    monkeypatch.setattr(supervisor, "require_completed_refit", lambda *_args: {})
    monkeypatch.setattr(supervisor, "require_launch_binding", lambda *_args: {})

    def finish_return(_seconds: int) -> None:
        (capture / "return.json").write_text(json.dumps({"wrapper_pid": 1234,
                                                           "caffeinate_pid": 1235,
                                                           "return_code": 0}) + "\n")

    monkeypatch.setattr(supervisor.time, "sleep", finish_return)
    supervisor.wait_for_capture(capture, CELL, control, plan, git_dir, {}, 1)


def test_active_claim_blocks_worker_before_capture_or_dispatch(tmp_path: Path) -> None:
    control = tmp_path / "control"
    claim_dir = control / "worker_claims"
    claim_dir.mkdir(parents=True)
    (claim_dir / "worker_0.json").write_text("{}\n")
    capture = control / "captures" / "next"
    plan = {"source": str(tmp_path / "source"), "workers": 1, "shards": [[CELL]]}
    with pytest.raises(ValueError, match="active producer claim"):
        supervisor.run_captured_worker(capture, control, plan, tmp_path / "metadata",
                                       {}, 0, 1, CELL)
    assert not capture.exists()


def test_unbounded_worker_call_rejected_before_capture(tmp_path: Path) -> None:
    plan = {"workers": 1, "shards": [[CELL]]}
    capture = tmp_path / "capture"
    with pytest.raises(ValueError, match="only one bounded"):
        supervisor.run_captured_worker(capture, tmp_path, plan, tmp_path / "metadata",
                                       {}, 0, 0, None)
    assert not capture.exists()


def test_wrong_controller_hash_rejected_before_any_fit(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="numerical controller differs"):
        supervisor.require_launch_binding({"controller_sha256": "0" * 64}, tmp_path)


def test_analysis_commit_is_pinned_between_dispatches(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    analysis = tmp_path / "analysis"
    controller = analysis / "scripts" / "recover_extension_run.py"
    controller.parent.mkdir(parents=True)
    controller.write_text("# pinned numerical controller\n")
    source = tmp_path / "source"
    source.mkdir()
    (source / "manifest.json").write_text("{}\n")
    monkeypatch.setattr(recovery, "REPO", analysis)
    monkeypatch.setattr(adapter, "ANALYSIS_FILES", ("scripts/recover_extension_run.py",))
    monkeypatch.setattr(adapter, "require_clean_published_adapter", lambda _root: "first_commit")
    monkeypatch.setattr(adapter, "require_production_root", lambda *_args: {})
    monkeypatch.setattr(recovery, "require_environment", lambda *_args: None)
    plan = {"controller_sha256": recovery.sha256_file(controller),
            "source": str(source), "source_manifest_sha256":
            recovery.sha256_file(source / "manifest.json"),
            "sealed": str(tmp_path / "sealed"), "python": "/locked/bin/python",
            "environment_receipt": str(tmp_path / "environment.json")}
    binding = supervisor.require_launch_binding(plan, tmp_path / "git")
    assert binding["analysis_git_commit"] == "first_commit"
    monkeypatch.setattr(adapter, "require_clean_published_adapter", lambda _root: "later_commit")
    with pytest.raises(ValueError, match="analysis commit or code changed"):
        supervisor.require_launch_binding(plan, tmp_path / "git", binding)
