"""Safety gates for the separate extension trace-recovery controller."""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

from scripts import recover_extension_run as recovery


def test_fixed_shards_cover_all_targets_once_in_manifest_order(tmp_path: Path) -> None:
    """Historical runtime balancing must not select or duplicate a target."""
    names = [f"cell_{index}" for index in range(5)]
    files = {}
    for index, identity in enumerate(names):
        path = tmp_path / f"{identity}.json"
        path.write_text(json.dumps({"seconds": [5, 40, 10, 20, 15][index]}))
        files[identity] = path
    shards = recovery.assign_shards(names, files, 3)
    assert sorted(identity for shard in shards for identity in shard) == names
    assert shards == recovery.assign_shards(names, files, 3)
    assert all(shard == sorted(shard, key=names.index) for shard in shards)


def test_numerical_worker_requires_explicit_execute_flag() -> None:
    """A dry command cannot acquire claims or launch a refit."""
    with pytest.raises(ValueError, match="explicit --execute"):
        recovery.run_worker(Namespace(execute=False, control="/nonexistent", worker=0,
                                      max_new_cells=0))


def test_direct_child_cannot_fit_without_live_worker_claim(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Knowing a target ID alone must not bypass its exclusive producer."""
    identity = "cell_0"
    control = tmp_path / "control"
    run = control / "refits" / identity / "attempt_001" / "run"
    plan = {"affected_cell_ids": [identity], "shards": [[identity]],
            "sealed": str(tmp_path / "sealed"), "matched": str(tmp_path / "matched")}
    monkeypatch.setattr(recovery, "load_plan", lambda _path: plan)

    def forbidden_fit(*_args: object) -> None:
        raise AssertionError("fit executed without a producer claim")

    monkeypatch.setattr(recovery, "_execute_child_fit", forbidden_fit)
    with pytest.raises(FileNotFoundError):
        recovery.child(Namespace(control=str(control), cell_id=identity,
                                 run=str(run), token="unowned"))


def test_plan_rejects_controller_mutation(tmp_path: Path) -> None:
    """The controller cannot change after a no-launch plan was sealed."""
    plan = {"controller_sha256": "0" * 64}
    plan["content_sha256"] = recovery.content_sha256(plan)
    recovery.write_new_json(tmp_path / "plan.json", plan)
    with pytest.raises(ValueError, match="controller changed"):
        recovery.load_plan(tmp_path)
