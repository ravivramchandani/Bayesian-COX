"""Portable producer-lineage checks for a recovered extension transfer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import assemble_recovered_extension as adapter
from scripts import continue_recovered_extension as continuation
from scripts import recover_extension_run as recovery
from scripts import seal_recovered_extension_lineage as sealer
from scripts.extension_release import recovery_lineage as lineage


def write(path: Path, value: dict) -> None:
    """Write a fixture record at a new path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def fixture_run(root: Path) -> tuple[Path, str]:
    """Build a tiny-byte, full-cardinality recovery with one real trace file."""
    run = root / "run"
    planned = [f"cell_{number:04d}" for number in range(1625)]
    absent = {planned[index] for worker, limit in enumerate(lineage.SHARD_COUNTS)
              for index in range(worker, 1625, 6)[:limit]}
    pending = [identity for identity in planned if identity in absent]
    manifest = {"plan": [{"cell_id": identity} for identity in planned],
                "planned_fits": 1625}
    manifest["manifest_content_sha256"] = lineage.canonical_hash(manifest)
    write(run / "manifest.json", manifest)
    inherited, new = {}, {}
    traced = pending[0]
    for identity in planned:
        cell = {"cell_id": identity, "status": "complete",
                "cell_content_sha256": "a" * 64, "fit_attempts": []}
        traces = {}
        if identity == traced:
            relative = f"traces/{identity}/posterior.nc"
            path = run / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"saved posterior arrays")
            traces = {relative: lineage.digest(path)}
            cell["fit_attempts"] = [{"traces": {"posterior": {
                "filename": "posterior.nc", "sha256": traces[relative]}}}]
        path = run / "cells" / f"{identity}.json"
        write(path, cell)
        record = {"cell_file_sha256": lineage.digest(path),
                  "status": "complete", "trace_sha256": traces}
        if identity in absent:
            new[identity] = {"worker": planned.index(identity) % 6,
                             "cell_content_sha256": "a" * 64, **record}
        else:
            inherited[identity] = {"producer": "new_refit" if len(inherited) < 21 else
                                   "intact_original", **record}
    payload = {"producers": inherited, "pending_cell_ids": pending,
               "producer_counts": {"intact_original": 1193, "new_refit": 21,
                                   "pending": 411},
               "source_manifest_sha256": lineage.digest(run / "manifest.json"),
               "controller_plan_sha256": "b" * 64,
               "source_forensic_sha256": "c" * 64,
               "absent_roster_sha256": "d" * 64}
    base = {"schema_version": 1, "status": "pre_continuation_recovered_extension",
            "assembly_plan_sha256": "e" * 64, "payload": payload}
    base["content_sha256"] = lineage.canonical_hash(base)
    write(run / "recovery_lineage.json", base)
    workers = [{"worker": worker,
                "cell_ids": [identity for index, identity in enumerate(planned)
                             if index % 6 == worker and identity in absent],
                "verified_worker_sha256": "f" * 64,
                "launch_sha256": "1" * 64, "return_sha256": "2" * 64,
                "stdout_sha256": "3" * 64, "stderr_sha256": "4" * 64}
               for worker in range(6)]
    final = {"schema_version": 1, "status": "full_recovered_extension_provenance",
             "manifest_sha256": payload["source_manifest_sha256"],
             "base_lineage_sha256": lineage.digest(run / "recovery_lineage.json"),
             "assembly_plan_sha256": base["assembly_plan_sha256"],
             "controller_plan_sha256": payload["controller_plan_sha256"],
             "source_forensic_sha256": payload["source_forensic_sha256"],
             "absent_roster_sha256": payload["absent_roster_sha256"],
             "continuation_start_sha256": "5" * 64,
             "continuation_complete_sha256": "6" * 64,
             "continuation_analysis_binding": {"analysis_git_commit": "fixed"},
             "producer_counts": lineage.COUNTS,
             "continuation_workers": workers,
             "continuation_producers": new}
    final["content_sha256"] = lineage.canonical_hash(final)
    write(run / "recovery_continuation.json", final)
    return run, traced


def test_full_recovery_lineage_is_portable_and_rejects_changed_cell_or_trace(
        tmp_path: Path) -> None:
    """A receiving copy can validate every producer without old host paths."""
    run, traced = fixture_run(tmp_path)
    first = lineage.verify_recovered_lineage(run)
    assert first["producer_counts"] == lineage.COUNTS
    assert first["stored_cells"] == 1625
    cell_path = run / "cells" / f"{traced}.json"
    original = cell_path.read_bytes()
    cell_path.write_bytes(original + b" ")
    with pytest.raises(ValueError, match="file hash differs"):
        lineage.verify_recovered_lineage(run)
    cell_path.write_bytes(original)
    trace_path = run / "traces" / traced / "posterior.nc"
    trace_path.write_bytes(b"changed posterior arrays")
    with pytest.raises(ValueError, match="file hash differs"):
        lineage.verify_recovered_lineage(run)


def test_recovered_run_requires_final_supplement_and_exact_worker_partition(
        tmp_path: Path) -> None:
    """The base assembly map alone cannot pass the transfer gate."""
    run, _ = fixture_run(tmp_path)
    final_path = run / "recovery_continuation.json"
    final = lineage.read(final_path)
    final_path.unlink()
    with pytest.raises(ValueError, match="missing or linked"):
        lineage.verify_recovered_lineage(run)
    final["continuation_workers"][0]["cell_ids"].reverse()
    final["content_sha256"] = lineage.canonical_hash({
        key: value for key, value in final.items() if key != "content_sha256"})
    write(final_path, final)
    with pytest.raises(ValueError, match="wrong frozen shard"):
        lineage.verify_recovered_lineage(run)


def test_recovery_lineage_rejects_linked_trace_parent(tmp_path: Path) -> None:
    """A receiver cannot follow a linked trace directory outside the release."""
    run, traced = fixture_run(tmp_path)
    trace_dir = run / "traces" / traced
    external = tmp_path / "external"
    trace_dir.rename(external)
    trace_dir.symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="linked recovery path"):
        lineage.verify_recovered_lineage(run)


def test_staging_refuses_assembled_recovery_without_final_lineage(tmp_path: Path) -> None:
    """A recovered run cannot silently use the generic extension release path."""
    run = tmp_path / "run"
    run.mkdir()
    assert lineage.optional_recovered_lineage(run) is None
    write(run / "recovery_lineage.json", {"status": "pre_continuation_recovered_extension"})
    with pytest.raises(ValueError, match="missing or linked"):
        lineage.optional_recovered_lineage(run)


def test_final_seal_requires_six_actual_zero_return_captures(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A worker receipt alone cannot certify an unsuccessful captured process."""
    run, _ = fixture_run(tmp_path)
    control = tmp_path / "control"
    capture = control / "continuation_captures/sequential-v1"
    capture.mkdir(parents=True)
    manifest = lineage.read(run / "manifest.json")
    base = lineage.read(run / "recovery_lineage.json")
    prior = lineage.read(run / "recovery_continuation.json")
    sealed = tmp_path / "sealed"
    runner = sealed / "scripts/run_extensions.py"
    runner.parent.mkdir(parents=True)
    runner.write_text("# fixed fixture runner\n")
    plan = {"content_sha256": "b" * 64,
            "absent_cell_ids": base["payload"]["pending_cell_ids"],
            "sealed": str(sealed), "matched": str(tmp_path / "matched.parquet"),
            "python": "/frozen/bin/python"}
    assembled = {"content_sha256": "e" * 64, "payload": base["payload"]}
    monkeypatch.setattr(recovery, "load_plan", lambda _: plan)
    monkeypatch.setattr(continuation, "require_assembled_run",
                        lambda *_: (manifest, assembled))
    monkeypatch.setattr(adapter, "validated_jobs",
                        lambda *_: ({"base_seed": 17}, {}, {}))

    def verified(_run, identities, _jobs, _cohorts, _seed):
        return {identity: {key: value for key, value in
                           prior["continuation_producers"][identity].items()
                           if key != "worker"} for identity in identities}

    monkeypatch.setattr(continuation, "verified_new_cells", verified)
    binding = {"analysis_git_commit": "fixed"}
    start = {"owner_pid": 2026, "control": str(control), "recovered_run": str(run),
             "assembly_plan": str(control / "assembly_adapter_plan_v1.json"),
             "plan_sha256": plan["content_sha256"], "analysis_binding": binding}
    write(capture / "start.json", start)
    shards = continuation.assigned_pending(manifest, plan["absent_cell_ids"])
    hashes = {}
    for worker, identities in enumerate(shards):
        folder = capture / f"worker_{worker}"
        folder.mkdir()
        (folder / "stdout.log").write_text("captured result\n")
        (folder / "stderr.log").write_text("")
        launch = {"owner_pid": 2026, "pid": 3000 + worker,
                  "worker": worker, "expected_cell_ids": identities,
                  "analysis_binding": binding,
                  "assembly_plan_sha256": assembled["content_sha256"],
                  "argv": ["/usr/bin/caffeinate", "-dimsu", "/usr/bin/nice", "-n", "10",
                           plan["python"], "-B", str(runner), "--matched", plan["matched"],
                           "--output", str(run), "--workers", "6", "--worker", str(worker)],
                  "cwd": str(sealed), "thread_limit": 1,
                  "production_runner_sha256": lineage.digest(runner)}
        returned = {"owner_pid": 2026, "pid": 3000 + worker, "return_code": 0}
        write(folder / "launch.json", launch)
        write(folder / "return.json", returned)
        cells = verified(run, identities, {}, {}, 17)
        receipt = {"worker": worker, "expected_cell_ids": identities,
                   "cell_producers": cells, "plan_sha256": plan["content_sha256"],
                   "assembly_plan_sha256": assembled["content_sha256"],
                   "analysis_binding": binding,
                   "status_counts": {"complete": len(identities)},
                   "launch_sha256": lineage.digest(folder / "launch.json"),
                   "return_sha256": lineage.digest(folder / "return.json"),
                   "stdout_sha256": lineage.digest(folder / "stdout.log"),
                   "stderr_sha256": lineage.digest(folder / "stderr.log")}
        write(folder / "verified_worker.json", receipt)
        hashes[str(worker)] = lineage.digest(folder / "verified_worker.json")
    write(capture / "complete.json", {
        "status": "full_grid_stored_pending_deep_verification",
        "plan_sha256": plan["content_sha256"],
        "assembly_plan_sha256": assembled["content_sha256"],
        "analysis_binding": binding, "stored": 1625,
        "new_continuation_cells": 411, "verified_worker_sha256": hashes})
    sealed_result = sealer.source_lineage(control, run)
    assert len(sealed_result["continuation_producers"]) == 411
    (run / "recovery_continuation.json").unlink()
    assert lineage.verify_recovered_lineage(run, candidate=sealed_result)["stored_cells"] == 1625
    write(run / "recovery_continuation.json", sealed_result)
    assert lineage.verify_recovered_lineage(run)["stored_cells"] == 1625
    bad_return = capture / "worker_3/return.json"
    returned = lineage.read(bad_return)
    returned["return_code"] = 1
    bad_return.write_text(json.dumps(returned) + "\n")
    with pytest.raises(ValueError, match="zero-return proof"):
        sealer.source_lineage(control, run)
