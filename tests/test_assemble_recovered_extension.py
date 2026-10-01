"""Producer-proof and destination guards for extension recovery assembly."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import assemble_recovered_extension as adapter
from scripts import recover_extension_run as recovery


def refit_fixture(tmp_path: Path) -> tuple[Path, dict, str, Path, Path, dict]:
    """Create one tiny matched source/refit proof without numerical sampling."""
    control = tmp_path / "control"
    identity = "fixture_cell"
    attempt = control / "refits" / identity / "attempt_001"
    refit_file = attempt / "run" / "cells" / f"{identity}.json"
    source_file = tmp_path / "source" / "cells" / f"{identity}.json"
    source = {"cell_id": identity, "status": "complete", "seed": 17,
              "seconds": 5.0, "cell_content_sha256": "source_content"}
    refit = {**source, "seconds": 6.0, "cell_content_sha256": "refit_content"}
    recovery.write_new_json(source_file, source)
    recovery.write_new_json(refit_file, refit)
    token = "a" * 32
    plan = {"python": "/frozen/bin/python", "sealed": "/frozen", "content_sha256": "plan_hash",
            "shards": [[], [], [], [identity]],
            "controller_sha256": recovery.sha256_file(recovery.REPO / "scripts/recover_extension_run.py"),
            "source_cell_file_sha256": {identity: recovery.sha256_file(source_file)}}
    argv = [plan["python"], str((recovery.REPO / "scripts/recover_extension_run.py").resolve()),
            "child", "--control", str(control), "--cell-id", identity,
            "--run", str(attempt / "run"), "--token", token]
    recovery.write_new_json(attempt / "invocation.json",
                            {"argv": argv, "cwd": plan["sealed"],
                             "plan_sha256": plan["content_sha256"], "token": token,
                             "worker": 3})
    recovery.write_new_json(attempt / "child_start.json", {"cell_id": identity, "pid": 123})
    recovery.write_new_json(attempt / "child_return.json", {"cell_id": identity, "return_code": 0})
    recovery.write_new_json(attempt / "scientific_comparison.json",
                            {"cell_id": identity, "official_non_timing_science": "match",
                             "difference": None, "source_status": "complete", "refit_status": "complete",
                             "source_cell_file_sha256": recovery.sha256_file(source_file),
                             "refit_cell_file_sha256": recovery.sha256_file(refit_file),
                             "source_cell_content_sha256": "source_content",
                             "refit_cell_content_sha256": "refit_content",
                             "refit_trace_sha256": {}})
    (attempt / "child.stdout.log").write_text("saved fixture\n")
    (attempt / "child.stderr.log").write_text("")
    return control, plan, identity, source_file, refit_file, refit


def test_refit_proof_requires_zero_child_return_and_exact_comparison(tmp_path: Path) -> None:
    """A scientific match cannot stand in for a successful captured child."""
    control, plan, identity, source_file, refit_file, refit = refit_fixture(tmp_path)
    proof = adapter.require_refit_proof(control, plan, identity, source_file, refit_file, refit)
    assert proof["child_return_code"] == 0
    assert proof["official_non_timing_science"] == "match"
    return_file = refit_file.parents[2] / "child_return.json"
    return_file.write_text('{"cell_id":"fixture_cell","return_code":1}\n')
    with pytest.raises(ValueError, match="zero-return proof"):
        adapter.require_refit_proof(control, plan, identity, source_file, refit_file, refit)


def test_refit_proof_rejects_changed_comparison_binding(tmp_path: Path) -> None:
    """A comparison receipt must bind the actual source and refit files."""
    control, plan, identity, source_file, refit_file, refit = refit_fixture(tmp_path)
    source_file.write_text('{"cell_id":"fixture_cell","status":"complete","seed":18}\n')
    with pytest.raises(ValueError, match="pinned source"):
        adapter.require_refit_proof(control, plan, identity, source_file, refit_file, refit)


def test_refit_proof_requires_fixed_shard_owner(tmp_path: Path) -> None:
    """A successful child from the wrong worker cannot certify the cell."""
    control, plan, identity, source_file, refit_file, refit = refit_fixture(tmp_path)
    invocation = refit_file.parents[2] / "invocation.json"
    value = recovery.read_json(invocation)
    value["worker"] = 2
    invocation.write_text(json.dumps(value) + "\n")
    with pytest.raises(ValueError, match="zero-return proof"):
        adapter.require_refit_proof(control, plan, identity, source_file, refit_file, refit)


def test_refit_proof_accepts_another_pinned_controller_location(tmp_path: Path) -> None:
    """Mixed capture roots remain valid when both used the pinned controller bytes."""
    control, plan, identity, source_file, refit_file, refit = refit_fixture(tmp_path)
    alternate = tmp_path / "other_checkout" / "scripts" / "recover_extension_run.py"
    alternate.parent.mkdir(parents=True)
    shutil.copyfile(recovery.REPO / "scripts/recover_extension_run.py", alternate)
    invocation_file = refit_file.parents[2] / "invocation.json"
    invocation = recovery.read_json(invocation_file)
    invocation["argv"][1] = str(alternate)
    invocation_file.write_text(json.dumps(invocation) + "\n")
    proof = adapter.require_refit_proof(control, plan, identity, source_file, refit_file, refit)
    assert proof["controller_source_path"] == str(alternate)
    assert proof["controller_source_sha256"] == plan["controller_sha256"]
    alternate.write_text("changed\n")
    with pytest.raises(ValueError, match="pinned source"):
        adapter.require_refit_proof(control, plan, identity, source_file, refit_file, refit)


def test_destination_cannot_overlap_a_producer(tmp_path: Path) -> None:
    """The recovered run must have a separate write-once identity."""
    control, source, sealed = (tmp_path / name for name in ("control", "source", "sealed"))
    with pytest.raises(ValueError, match="overlaps"):
        adapter.validate_destination(source / "new_run", control, source, sealed)


def test_existing_adapter_claim_blocks_preflight(tmp_path: Path) -> None:
    """A stranded assembly claim must halt any subsequent inventory build."""
    control = tmp_path / "control"
    source = tmp_path / "source"
    (control / "assembly_adapter.claim").parent.mkdir(parents=True)
    (control / "assembly_adapter.claim").write_text("{}\n")
    with pytest.raises(ValueError, match="assembly claim"):
        adapter.require_no_active_producer(control, source)


def test_production_root_accepts_scoped_independent_git_metadata(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify frozen files while leaving an inherited Git override out of analysis checks."""
    metadata = tmp_path / "metadata"
    sealed = tmp_path / "sealed"
    metadata.mkdir()
    sealed.mkdir()
    (metadata / "input.txt").write_text("fixed input\n")
    (sealed / "input.txt").write_text("fixed input\n")
    subprocess.run(["git", "init", "-q"], cwd=metadata, check=True)
    subprocess.run(["git", "add", "input.txt"], cwd=metadata, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.org",
                    "commit", "-qm", "frozen fixture"], cwd=metadata, check=True)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=metadata, text=True).strip()
    monkeypatch.setattr(recovery, "SEALED_COMMIT", commit)
    monkeypatch.setenv("GIT_DIR", "/wrong/inherited/git-dir")
    manifest = {"code": {"git_commit": commit},
                "input_sha256": {"input.txt": recovery.sha256_file(sealed / "input.txt")}}
    manifest["manifest_content_sha256"] = recovery.content_sha256(manifest)
    proof = adapter.require_production_root(manifest, sealed, metadata / ".git")
    assert proof["head"] == commit
    assert proof["status_clean"] is True
    assert proof["mode"] == "independent_git_dir"
    assert "GIT_DIR" not in adapter.clean_git_environment()
    alternate_dir = tmp_path / "alternate_git_dir"
    shutil.copytree(metadata / ".git", alternate_dir)
    alternate_proof = adapter.require_production_root(manifest, sealed, alternate_dir)
    assert alternate_proof["head_tree"] == proof["head_tree"]
    assert alternate_proof != proof
    (sealed / "input.txt").write_text("changed\n")
    with pytest.raises(ValueError, match="not clean"):
        adapter.require_production_root(manifest, sealed, metadata / ".git")


def test_analysis_checkout_ignores_inherited_production_git_override(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Published analysis status must come from its own Git directory."""
    analysis = tmp_path / "analysis"
    analysis.mkdir()
    (analysis / "adapter.txt").write_text("committed\n")
    subprocess.run(["git", "init", "-q"], cwd=analysis, check=True)
    subprocess.run(["git", "add", "adapter.txt"], cwd=analysis, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.org",
                    "commit", "-qm", "analysis fixture"], cwd=analysis, check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=analysis, text=True).strip()
    monkeypatch.setattr(adapter, "ANALYSIS_FILES", ("adapter.txt",))
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "wrong_git_dir"))
    monkeypatch.setenv("GIT_WORK_TREE", str(tmp_path / "wrong_work_tree"))
    assert adapter.require_clean_published_adapter(analysis) == head
    extra = analysis / "untracked.py"
    extra.write_text("print('unexpected code')\n")
    with pytest.raises(ValueError, match="not committed clean"):
        adapter.require_clean_published_adapter(analysis)
    extra.unlink()
    (analysis / "adapter.txt").write_text("changed\n")
    with pytest.raises(ValueError, match="not committed clean"):
        adapter.require_clean_published_adapter(analysis)
