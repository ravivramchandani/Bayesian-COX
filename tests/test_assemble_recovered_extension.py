"""Producer-proof and destination guards for extension recovery assembly."""

from __future__ import annotations

import json
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
