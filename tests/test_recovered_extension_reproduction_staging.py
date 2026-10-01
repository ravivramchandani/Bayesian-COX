"""Invented 89-stage fixtures; no production source, cohort, or fit is touched."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import arviz as az
import numpy as np
import pytest

from scripts import stage_recovered_extension_reproduction as stage
from src.utils.reproducibility import canonical_json_hash


def write(path: Path, value: dict[str, Any]) -> None:
    """Write one invented JSON artifact with deterministic bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")


def cell(path: Path, identity: str, trace_sha: str | None, *, seconds: float) -> None:
    """Build a real verified_cell-compatible but invented cell record."""
    traces = ({"posterior": {"filename": "attempt_1_posterior.nc", "sha256": trace_sha}}
              if trace_sha is not None else {})
    value = {"cell_id": identity, "status": "complete", "seconds": seconds,
             "fit_attempts": [{"traces": traces}]}
    value["cell_content_sha256"] = canonical_json_hash(value)
    write(path, value)


def trace(path: Path, beta: float) -> str:
    """Create an actual tiny sampled-array file for the frozen comparator."""
    path.parent.mkdir(parents=True, exist_ok=True)
    idata = az.from_dict(posterior={"beta": np.array([[[beta, beta + 1]]])},
                         sample_stats={"lp": np.array([[[-2.0, -1.0]]])})
    idata.to_netcdf(str(path))
    idata.close()
    return stage.digest(path)


class InventedStage:
    """Three intact refits and one trace-affected selected identity."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.root = tmp_path
        self.original = tmp_path / "original"
        self.run = tmp_path / "recovered"
        self.prestage = tmp_path / "prestage"
        self.code = tmp_path / "code"
        self.destination = tmp_path / "staged"
        self.receipt = tmp_path / "stage_receipt.json"
        self.matched = tmp_path / "matched.parquet"
        self.ids = [f"invented_{index}__r01f01__ridge__full" for index in range(4)]
        self.affected = self.ids[-1]
        for root in (self.original, self.run, self.prestage, self.code):
            root.mkdir()
        self.matched.write_bytes(b"invented matched input")
        manifest = {"plan": [{"cell_id": identity} for identity in self.ids],
                    "matched_sha256": stage.digest(self.matched),
                    "code": {"git_commit": stage.recovery.SEALED_COMMIT, "git_dirty": False},
                    "input_sha256": {}, "run_config": {}}
        manifest["manifest_content_sha256"] = stage.lineage.canonical_hash(manifest)
        write(self.run / "manifest.json", manifest)
        shutil.copyfile(self.run / "manifest.json", self.original / "manifest.json")
        self.manifest_sha = stage.digest(self.run / "manifest.json")
        monkeypatch.setattr(stage.lineage, "INTERRUPTED_MANIFEST_SHA256", self.manifest_sha)
        monkeypatch.setattr(stage, "PLANNED", 4)
        monkeypatch.setattr(stage, "SELECTED", 4)
        monkeypatch.setattr(stage, "REUSED", 3)
        monkeypatch.setattr(stage, "TRACES", 3)
        monkeypatch.setattr(stage, "AFFECTED", frozenset({self.affected}))
        monkeypatch.setattr(stage.recovery, "require_apfs", lambda _: None)
        monkeypatch.setattr(stage.recovery, "require_free_space", lambda *_args, **_kwargs: None)
        monkeypatch.setattr(stage.assembly, "require_production_root",
                            lambda *_args, **_kwargs: {"head": stage.recovery.SEALED_COMMIT})
        monkeypatch.setattr(stage, "require_frozen_comparison", lambda *_args: None)
        jobs = {identity: SimpleNamespace(cell_id=identity, repeat=1, fold=1)
                for identity in self.ids}
        monkeypatch.setattr(stage.assembly, "validated_jobs",
                            lambda *_args: ({}, {}, jobs))
        producers = {}
        for index, identity in enumerate(self.ids[:-1]):
            relative = f"traces/{identity}/attempt_1_posterior.nc"
            source_trace = trace(self.run / relative, float(index))
            (self.original / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.run / relative, self.original / relative)
            refit_trace = trace(self.prestage / relative, float(index))
            source_cell = self.run / "cells" / f"{identity}.json"
            cell(source_cell, identity, source_trace, seconds=1)
            target = self.original / "cells" / f"{identity}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_cell, target)
            cell(self.prestage / "cells" / f"{identity}.json", identity,
                 refit_trace, seconds=2)
            producers[identity] = {"producer": "intact_original",
                                   "cell_file_sha256": stage.digest(source_cell),
                                   "trace_sha256": {relative: source_trace}}
        cell(self.run / "cells" / f"{self.affected}.json", self.affected, None, seconds=3)
        cell(self.prestage / "cells" / f"{self.affected}.json", self.affected, None, seconds=4)
        (self.prestage / "traces" / self.affected).mkdir(parents=True)
        producers[self.affected] = {"producer": "new_refit"}
        write(self.run / "recovery_lineage.json", {"payload": {"producers": producers}})
        write(self.run / "recovery_continuation.json", {"invented": True})
        self.proof = {"status": "recovered_lineage_verified", "stored_cells": 4,
                      "manifest_sha256": self.manifest_sha,
                      "base_lineage_sha256": stage.digest(self.run / "recovery_lineage.json"),
                      "final_lineage_sha256": stage.digest(self.run / "recovery_continuation.json")}
        monkeypatch.setattr(stage.lineage, "verify_recovered_lineage", lambda _: self.proof)
        verification = {"planned": 4, "stored": 4, "verification": "deep"}
        write(self.run / "verification.json", verification)
        aggregates = {}
        for name in ("paired_families.json", "decision_curves.json", "rq2_effects.json"):
            write(self.run / name, {"invented": name})
            aggregates[name] = stage.digest(self.run / name)
        completion = {**verification, "manifest_sha256": self.manifest_sha,
                      "production_code_commit": stage.recovery.SEALED_COMMIT,
                      "cell_sha256": {f"cells/{identity}.json":
                                      stage.digest(self.run / "cells" / f"{identity}.json")
                                      for identity in self.ids},
                      "aggregate_sha256": aggregates}
        completion["completion_content_sha256"] = stage.lineage.canonical_hash(completion)
        write(self.run / "completion.json", completion)

    def args(self) -> SimpleNamespace:
        """Return a CLI-shaped namespace without invoking a shell."""
        return SimpleNamespace(recovered_run=self.run, original_run=self.original,
                               prestage=self.prestage, matched=self.matched,
                               frozen_code=self.code, destination=self.destination,
                               receipt=self.receipt, production_git_dir=None)


def test_stages_only_verified_intact_refits_and_seals_provenance(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = InventedStage(tmp_path, monkeypatch)
    original_refit_hashes = {path.relative_to(fixture.prestage).as_posix(): stage.digest(path)
                             for path in fixture.prestage.rglob("*") if path.is_file()}
    result = stage.stage(fixture.args())
    files = {path.relative_to(fixture.destination).as_posix()
             for path in fixture.destination.rglob("*") if path.is_file()}
    assert len([name for name in files if name.startswith("cells/")]) == 3
    assert len([name for name in files if name.startswith("traces/")]) == 3
    assert "rebind_stage.json" in files and not any(name.startswith("receipts/") for name in files)
    assert result["pending_fresh_refit_ids"] == [fixture.affected]
    assert result["fresh_fits_executed"] == result["official_reproduction_receipts_issued"] == 0
    provenance = stage.lineage.read(fixture.destination / "rebind_stage.json")
    assert provenance["content_sha256"] == stage.lineage.canonical_hash({
        key: value for key, value in provenance.items() if key != "content_sha256"})
    assert result["staged_provenance_sha256"] == stage.digest(fixture.destination / "rebind_stage.json")
    assert stage.digest(fixture.receipt) != result["staged_provenance_sha256"]
    assert original_refit_hashes == {path.relative_to(fixture.prestage).as_posix(): stage.digest(path)
                                     for path in fixture.prestage.rglob("*") if path.is_file()}


@pytest.mark.parametrize("change, expected", [
    ("wrong_producer", "selected recovered producers"),
    ("changed_original_cell", "intact selected source bytes"),
    ("sampled_array", "refit sampled values differ"),
    ("extra_refit_file", "staging tree has missing or extra"),
    ("missing_deep", "missing or linked recovery file"),
])
def test_rejects_wrong_source_refit_or_incomplete_evidence(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str, expected: str) -> None:
    fixture = InventedStage(tmp_path, monkeypatch)
    identity = fixture.ids[0]
    if change == "wrong_producer":
        base = json.loads((fixture.run / "recovery_lineage.json").read_text())
        base["payload"]["producers"][identity]["producer"] = "new_refit"
        write(fixture.run / "recovery_lineage.json", base)
        fixture.proof["base_lineage_sha256"] = stage.digest(fixture.run / "recovery_lineage.json")
    elif change == "changed_original_cell":
        old = fixture.original / "cells" / f"{identity}.json"
        old.write_text(old.read_text() + " ", encoding="utf-8")
    elif change == "sampled_array":
        relative = f"traces/{identity}/attempt_1_posterior.nc"
        changed_sha = trace(fixture.prestage / relative, 100.0)
        path = fixture.prestage / "cells" / f"{identity}.json"
        value = json.loads(path.read_text())
        value["fit_attempts"][0]["traces"]["posterior"]["sha256"] = changed_sha
        value["cell_content_sha256"] = canonical_json_hash({key: item for key, item in value.items()
                                                              if key != "cell_content_sha256"})
        write(path, value)
    elif change == "extra_refit_file":
        (fixture.prestage / "unexpected.txt").write_text("unexpected", encoding="utf-8")
    elif change == "missing_deep":
        (fixture.run / "completion.json").unlink()
    with pytest.raises(ValueError, match=expected):
        stage.stage(fixture.args())
    assert not fixture.destination.exists() and not fixture.receipt.exists()


def test_rejects_existing_destination_or_linked_input(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fixture = InventedStage(tmp_path, monkeypatch)
    fixture.destination.mkdir()
    with pytest.raises(ValueError, match="fresh destination"):
        stage.stage(fixture.args())
    fixture.destination.rmdir()
    linked = fixture.prestage / "traces" / fixture.ids[0] / "attempt_1_posterior.nc"
    linked.unlink()
    linked.symlink_to(fixture.run / "traces" / fixture.ids[0] / linked.name)
    with pytest.raises(ValueError, match="linked path"):
        stage.stage(fixture.args())
    assert not fixture.destination.exists() and not fixture.receipt.exists()
