"""Portable producer-lineage checks for a recovered extension transfer."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from scripts import assemble_recovered_extension as adapter
from scripts import continue_recovered_extension as continuation
from scripts import recover_extension_run as recovery
from scripts import seal_recovered_extension_lineage as sealer
from scripts.extension_release import recovery_lineage as lineage
from scripts.extension_release import recovery_transfer as transfer


def write(path: Path, value: dict) -> None:
    """Write a fixture record at a new path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def fixture_run(root: Path, *, v2: bool = False) -> tuple[Path, str]:
    """Build a tiny-byte, full-cardinality recovery with one real trace file."""
    run = root / "run"
    planned = [f"cell_{number:04d}" for number in range(1625)]
    absent_indexes = {index for worker, limit in enumerate(lineage.SHARD_COUNTS)
                      for index in range(worker, 1625, 6)[:limit]}
    if v2:
        inherited_indexes = (index for index in range(1625) if index not in absent_indexes)
        for identity in sorted(transfer.V2_FIRST_FOUR):
            planned[next(inherited_indexes)] = identity
    absent = {planned[index] for index in absent_indexes}
    pending = [identity for identity in planned if identity in absent]
    manifest = {"plan": [{"cell_id": identity} for identity in planned],
                "planned_fits": 1625,
                "input_sha256": {"scripts/run_extensions.py": "7" * 64}}
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


def test_interrupted_manifest_cannot_hide_recovery_by_deleting_markers(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Known interrupted evidence cannot silently take the generic stage path."""
    run = tmp_path / "run"
    write(run / "manifest.json", {"status": "interrupted fixture"})
    monkeypatch.setattr(lineage, "INTERRUPTED_MANIFEST_SHA256",
                        lineage.digest(run / "manifest.json"))
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


def bundle_fixture(root: Path, *, v2: bool = False) -> tuple[Path, Path, Path, Path]:
    """Make complete small-byte proof files for all fixed producer identities."""
    run, _ = fixture_run(root, v2=v2)
    control, rosters = root / "control", root / "coordination/recovery"
    source = root / "original"
    base = lineage.read(run / "recovery_lineage.json")
    final = lineage.read(run / "recovery_continuation.json")
    affected = [identity for identity, row in base["payload"]["producers"].items()
                if row["producer"] == "new_refit"]
    pending = base["payload"]["pending_cell_ids"]
    write(rosters / transfer.FORENSIC_NAME, {"affected_cell_ids": affected})
    write(rosters / transfer.ABSENT_NAME, {"absent_cell_ids": pending})
    code = root / "scripts"
    code.mkdir()
    for relative in (*adapter.ANALYSIS_FILES,
                     "scripts/supervise_extension_recovery.py",
                     "scripts/continue_recovered_extension.py"):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# fixture {relative}\n")
    analysis_hashes = {relative: lineage.digest(root / relative)
                       for relative in adapter.ANALYSIS_FILES}
    old_hashes = {}
    for identity in affected:
        old_path = source / "cells" / f"{identity}.json"
        write(old_path, lineage.read(run / "cells" / f"{identity}.json"))
        old_hashes[identity] = lineage.digest(old_path)
    if v2:
        remaining = [identity for identity in affected if identity not in transfer.V2_FIRST_FOUR]
        fourth = "metabric_matched__expression__r01f03__bayesian_spike_slab__full"
        shards = [[fourth], remaining[:1], remaining[1:5],
                  ["metabric_matched__expression__r01f05__bayesian_horseshoe__full",
                   *remaining[5:8]],
                  ["metabric_matched__expression__r01f01__bayesian_horseshoe__full",
                   *remaining[8:12]],
                  ["metabric_matched__expression__r01f01__pv_horseshoe__full",
                   *remaining[12:]]]
    else:
        shards = [affected[worker::6] for worker in range(6)]
    plan = {"source": str(source), "source_manifest_sha256":
            lineage.digest(run / "manifest.json"),
            "affected_cell_ids": affected, "absent_cell_ids": pending,
            "shards": shards, "source_cell_file_sha256": old_hashes,
            "sealed": "/sealed", "matched": "/matched.parquet",
            "python": "/locked/python",
            "controller_sha256": lineage.digest(code / "recover_extension_run.py"),
            "forensic_sha256": lineage.digest(rosters / transfer.FORENSIC_NAME),
            "absent_roster_sha256": lineage.digest(rosters / transfer.ABSENT_NAME)}
    plan["content_sha256"] = lineage.canonical_hash(plan)
    write(control / "plan.json", plan)
    for identity in affected:
        folder = control / "refits" / identity / "attempt_001"
        old = lineage.read(source / "cells" / f"{identity}.json")
        new = lineage.read(run / "cells" / f"{identity}.json")
        token = "a" * 32
        owner = next(worker for worker, shard in enumerate(shards) if identity in shard)
        write(folder / "invocation.json", {
            "argv": [plan["python"], "/sealed/recover_extension_run.py", "child",
                     "--control", str(control), "--cell-id", identity, "--run",
                     str(folder / "run"), "--token", token],
            "token": token, "cwd": plan["sealed"], "worker": owner,
            "plan_sha256": plan["content_sha256"]})
        write(folder / "child_start.json", {"cell_id": identity, "pid": 100})
        write(folder / "child_return.json", {"cell_id": identity, "return_code": 0})
        write(folder / "scientific_comparison.json", {
            "cell_id": identity, "official_non_timing_science": "match",
            "difference": None, "refit_trace_sha256": {},
            "source_cell_file_sha256": old_hashes[identity],
            "refit_cell_file_sha256": lineage.digest(run / "cells" / f"{identity}.json"),
            "source_cell_content_sha256": old["cell_content_sha256"],
            "refit_cell_content_sha256": new["cell_content_sha256"],
            "source_status": old["status"], "refit_status": new["status"]})
        (folder / "child.stdout.log").write_text("captured refit\n")
        (folder / "child.stderr.log").write_text("")
        base["payload"]["producers"][identity].update({
            "original_cell_file_sha256": old_hashes[identity],
            "producer_run": str(folder / "run"),
            "proof": {"controller_source_path": "/sealed/recover_extension_run.py",
                      "controller_source_sha256": plan["controller_sha256"],
                      "child_return_code": 0,
                      "original_posterior_array_equality":
                      "unavailable: original trace bytes missing",
                      **{key: lineage.digest(folder / name) for name, key in {
                          "invocation.json": "invocation_sha256",
                          "child_start.json": "child_start_sha256",
                          "child_return.json": "child_return_sha256",
                          "scientific_comparison.json": "comparison_sha256",
                          "child.stdout.log": "child_stdout_sha256",
                          "child.stderr.log": "child_stderr_sha256"}.items()}}})
    base["payload"].update({"controller_plan_sha256": plan["content_sha256"],
                            "source_forensic_sha256": plan["forensic_sha256"],
                            "absent_roster_sha256": plan["absent_roster_sha256"],
                            "destination": str(run),
                            "adapter_sha256": lineage.digest(code / "assemble_recovered_extension.py"),
                            "analysis_code_sha256": analysis_hashes})
    return_hashes = {}
    for worker, identities in enumerate(shards):
        path = control / "worker_returns" / f"worker_{worker}.json"
        write(path, {"worker": worker, "status": "complete", "cell_ids": identities})
        return_hashes[str(worker)] = lineage.digest(path)
    base["payload"]["worker_return_sha256"] = return_hashes
    assembly = {"payload": base["payload"]}
    assembly["content_sha256"] = lineage.canonical_hash(assembly)
    base["assembly_plan_sha256"] = assembly["content_sha256"]
    base["content_sha256"] = lineage.canonical_hash({
        key: value for key, value in base.items() if key != "content_sha256"})
    write(run / "recovery_lineage.json", base)
    write(control / "assembly_adapter_plan_v1.json", assembly)
    write(control / "assembly_adapter_receipt.json", {
        "assembly_plan_sha256": assembly["content_sha256"],
        "manifest_sha256": lineage.digest(run / "manifest.json"),
        "lineage_sha256": lineage.digest(run / "recovery_lineage.json")})
    supervisor_start = {
        "plan_sha256": plan["content_sha256"], "owner_pid": 100,
        "control": str(control),
        "production_git_dir": "/frozen/.git",
        "wait_capture": str(control / "captures/fourth"),
        "analysis_binding": {"analysis_git_commit": "supervisor fixture",
                             "supervisor_sha256": lineage.digest(
                                 code / "supervise_extension_recovery.py")}}
    write(control / "captures/sequential-v1/start.json", supervisor_start)
    supervisor_launch = {
        "pid": 100, "cwd": "/runtime", "prior_capture": supervisor_start["wait_capture"],
        "analysis_git_commit": supervisor_start["analysis_binding"]["analysis_git_commit"],
        "supervisor_sha256": supervisor_start["analysis_binding"]["supervisor_sha256"],
        "plan_file_sha256": lineage.digest(control / "plan.json"),
        "argv": [plan["python"], "-B", "/runtime/scripts/supervise_extension_recovery.py",
                 "--control", str(control), "--capture-root",
                 str(control / "captures/sequential-v1"), "--production-git-dir",
                 supervisor_start["production_git_dir"], "--wait-capture",
                 supervisor_start["wait_capture"], "--execute"]}
    write(control / "captures/sequential-v1.launch.json", supervisor_launch)
    write(rosters / "2026-10-01-sequential-recovery-supervisor-launch.json", {
        "supervisor_launch_sha256": lineage.digest(control / "captures/sequential-v1.launch.json"),
        "supervisor_start_sha256": lineage.digest(control / "captures/sequential-v1/start.json"),
        "fixed_plan_file_sha256": lineage.digest(control / "plan.json"),
        "fixed_plan_content_sha256": plan["content_sha256"],
        "supervisor_pid_at_checkpoint": supervisor_start["owner_pid"],
        "supervisor_source_sha256": supervisor_start["analysis_binding"]["supervisor_sha256"],
        "supervisor_analysis_commit": supervisor_start["analysis_binding"]["analysis_git_commit"],
        "supervisor_runtime_checkout": supervisor_launch["cwd"],
        "prior_worker_capture": supervisor_start["wait_capture"],
        "control": str(control)})
    write(control / "captures/sequential-v1/complete.json", {
        "plan_sha256": plan["content_sha256"],
        "analysis_binding": {"analysis_git_commit": "supervisor fixture",
                             "supervisor_sha256": lineage.digest(
                                 code / "supervise_extension_recovery.py")},
        "verified_refits": 21, "complete_workers": 6})
    capture = control / "continuation_captures/sequential-v1"
    binding = {"analysis_git_commit": "fixture",
               "successor_sha256": lineage.digest(code / "continue_recovered_extension.py")}
    write(capture / "start.json", {"analysis_binding": binding,
                                    "plan_sha256": plan["content_sha256"],
                                    "owner_pid": 200, "control": str(control),
                                    "recovered_run": str(run),
                                    "assembly_plan": str(
                                        control / "assembly_adapter_plan_v1.json")})
    hashes = {}
    for worker, record in enumerate(final["continuation_workers"]):
        folder = capture / f"worker_{worker}"
        identities = record["cell_ids"]
        subset = {identity: {key: value for key, value in
                             final["continuation_producers"][identity].items()
                             if key != "worker"} for identity in identities}
        write(folder / "launch.json", {"worker": worker,
                                       "expected_cell_ids": identities,
                                       "analysis_binding": binding,
                                       "assembly_plan_sha256": assembly["content_sha256"],
                                       "owner_pid": 200, "pid": 300 + worker,
                                       "cwd": plan["sealed"], "thread_limit": 1,
                                       "production_runner_sha256": "7" * 64,
                                       "argv": ["/usr/bin/caffeinate", "-dimsu",
                                                "/usr/bin/nice", "-n", "10",
                                                plan["python"], "-B",
                                                "/sealed/scripts/run_extensions.py",
                                                "--matched", plan["matched"],
                                                "--output", str(run), "--workers", "6",
                                                "--worker", str(worker)]})
        write(folder / "return.json", {"owner_pid": 200, "pid": 300 + worker,
                                       "return_code": 0})
        (folder / "stdout.log").write_text("captured continuation\n")
        (folder / "stderr.log").write_text("")
        write(folder / "verified_worker.json", {
            "worker": worker, "cell_producers": subset,
            "expected_cell_ids": identities,
            "analysis_binding": binding, "plan_sha256": plan["content_sha256"],
            "assembly_plan_sha256": assembly["content_sha256"],
            "launch_sha256": lineage.digest(folder / "launch.json"),
            "return_sha256": lineage.digest(folder / "return.json"),
            "stdout_sha256": lineage.digest(folder / "stdout.log"),
            "stderr_sha256": lineage.digest(folder / "stderr.log"),
            "status_counts": {"complete": len(identities)}})
        record.update({"verified_worker_sha256": lineage.digest(folder / "verified_worker.json"),
                       "launch_sha256": lineage.digest(folder / "launch.json"),
                       "return_sha256": lineage.digest(folder / "return.json"),
                       "stdout_sha256": lineage.digest(folder / "stdout.log"),
                       "stderr_sha256": lineage.digest(folder / "stderr.log")})
        hashes[str(worker)] = record["verified_worker_sha256"]
    write(capture / "complete.json", {
        "status": "full_grid_stored_pending_deep_verification",
        "stored": 1625, "new_continuation_cells": 411,
        "plan_sha256": plan["content_sha256"], "analysis_binding": binding,
        "assembly_plan_sha256": assembly["content_sha256"],
        "verified_worker_sha256": hashes})
    final.update({"base_lineage_sha256": lineage.digest(run / "recovery_lineage.json"),
                  "assembly_plan_sha256": assembly["content_sha256"],
                  "controller_plan_sha256": plan["content_sha256"],
                  "source_forensic_sha256": plan["forensic_sha256"],
                  "absent_roster_sha256": plan["absent_roster_sha256"],
                  "continuation_start_sha256": lineage.digest(capture / "start.json"),
                  "continuation_complete_sha256": lineage.digest(capture / "complete.json"),
                  "continuation_analysis_binding": binding})
    final["content_sha256"] = lineage.canonical_hash({
        key: value for key, value in final.items() if key != "content_sha256"})
    write(run / "recovery_continuation.json", final)
    if v2:
        upgrade_v2_bundle_fixture(run, control, rosters, root, base, final, plan, assembly)
    return run, control, rosters, root / "bundle"


def upgrade_v2_bundle_fixture(run: Path, control: Path, rosters: Path, root: Path,
                              base: dict, final: dict, plan: dict, assembly: dict) -> None:
    """Add an invented complete V2 chain with all 23 bounded dispatch receipts."""
    fourth = "metabric_matched__expression__r01f03__bayesian_spike_slab__full"
    first_four = transfer.V2_FIRST_FOUR
    for name in ("supervise_extension_recovery_v2.py",
                 "salvage_extension_refit_comparison.py"):
        (root / "scripts" / name).write_text(f"# invented fixture {name}\n")
    shutil.copy2(control / "assembly_adapter_plan_v1.json",
                 control / "assembly_adapter_plan_v2.json")
    binding = {"analysis_git_commit": "fixture-v2", "analysis_code_sha256":
               base["payload"]["analysis_code_sha256"],
               "supervisor_sha256": lineage.digest(root / "scripts/supervise_extension_recovery.py"),
               "v2_supervisor_sha256": lineage.digest(
                   root / "scripts/supervise_extension_recovery_v2.py"),
               "salvage_script_sha256": lineage.digest(
                   root / "scripts/salvage_extension_refit_comparison.py")}
    old_capture = control / "captures/worker00_ramp2"
    write(old_capture / "launch.json", {"command": ["old", "wrapper"]})
    write(old_capture / "wrapper_start.json", {"expected_cell_id": fourth})
    write(old_capture / "return.json", {"return_code": 1})
    (old_capture / "worker.stderr.log").write_text("post-fit cwd FileNotFoundError\n")
    (old_capture / "capture.py").write_text("# invented failed wrapper\n")
    write(rosters / "2026-10-01-fourth-extension-recovery-launch.json",
          {"capture_directory": str(old_capture), "cell_id": fourth})
    for name, relative in transfer.V1_INCIDENT_FILES.items():
        path = control / relative.format(identity=fourth)
        if name == "fourth_child_return":
            continue
        if name == "fourth_wrapper_return" or name == "fourth_wrapper_stderr":
            continue
        write(path, {"plan_sha256": plan["content_sha256"],
                     "supervisor_claim_retained": True, "historical_name": name})
    old_hashes = {name: lineage.digest(control / relative.format(identity=fourth))
                  for name, relative in transfer.V1_INCIDENT_FILES.items()}
    old_failure = {name: lineage.digest(path) for name, path in {
        "capture.py": old_capture / "capture.py",
        "launch.json": old_capture / "launch.json",
        "wrapper_start.json": old_capture / "wrapper_start.json",
        "return.json": old_capture / "return.json",
        "worker.stderr.log": old_capture / "worker.stderr.log",
        "published_launch": rosters / "2026-10-01-fourth-extension-recovery-launch.json",
        "v1_supervisor_claim": control / "sequential_supervisor.claim",
        "v1_supervisor_failure": control / "captures/sequential-v1/failure.json",
    }.items()}
    salvage_capture = control / "captures/no-fit-salvage-r01f03-v1"
    fourth_producer = base["payload"]["producers"][fourth]
    refit = control / "refits" / fourth / "attempt_001"
    saved_child = {"cell": fourth_producer["cell_file_sha256"],
                   "source_cell": fourth_producer["original_cell_file_sha256"],
                   "child_return.json": old_hashes["fourth_child_return"],
                   "child_start.json": lineage.digest(refit / "child_start.json"),
                   "invocation": lineage.digest(refit / "invocation.json"),
                   "child_stdout": lineage.digest(refit / "child.stdout.log"),
                   "child_stderr": lineage.digest(refit / "child.stderr.log"),
                   "run_manifest": lineage.digest(run / "manifest.json")}
    write(salvage_capture / "start.json", {
        "identity": fourth, "no_fit_comparison_only": True, "owner_pid": 90,
        "stable_cwd": "/private/tmp", "plan_content_sha256": plan["content_sha256"],
        "plan_file_sha256": lineage.digest(control / "plan.json"),
        "prior": {"old_failed_capture_sha256": old_failure,
                  "completed_child_sha256": saved_child}})
    write(salvage_capture / "launch.json", {
        "command": [plan["python"], "-I", "-B",
                    "/runtime/salvage/scripts/salvage_extension_refit_comparison.py",
                    "compare-child", "--control", str(control), "--capture-root",
                    str(salvage_capture), "--token", "a" * 32],
        "cwd": "/private/tmp", "owner_pid": 90,
        "script_sha256": binding["salvage_script_sha256"]})
    write(salvage_capture / "return.json", {"return_code": 0, "owner_pid": 90})
    (salvage_capture / "stdout.log").write_text("official match, zero fits\n")
    (salvage_capture / "stderr.log").write_text("")
    salvage = {"schema_version": 1,
               "status": "fourth_refit_postfit_comparison_salvaged",
               "cell_id": fourth, "plan_file_sha256": lineage.digest(control / "plan.json"),
               "plan_content_sha256": plan["content_sha256"],
               "old_wrapper_return_code": 1, "saved_fit_child_return_code": 0,
               "new_comparison_child_return_code": 0, "new_fits_executed": 0,
               "old_failure_preserved": True, "old_failed_capture_sha256": old_failure,
               "saved_child_sha256": saved_child,
               "official_refit_proof": fourth_producer["proof"],
               "scientific_comparison_sha256": fourth_producer["proof"]["comparison_sha256"],
               **{key: lineage.digest(salvage_capture / name) for name, key in (
                   ("launch.json", "launch_sha256"), ("return.json", "return_sha256"),
                   ("stdout.log", "stdout_sha256"), ("stderr.log", "stderr_sha256"))}}
    salvage["content_sha256"] = lineage.canonical_hash(salvage)
    write(salvage_capture / "proof.json", salvage)
    write(salvage_capture / "complete.json", {
        "proof_sha256": lineage.digest(salvage_capture / "proof.json"),
        "plan_content_sha256": plan["content_sha256"], "new_fits_executed": 0})
    write(rosters / transfer.V2_INCIDENT_PUBLISHED, {
        "schema_version": 1, "control": str(control),
        "plan_file_sha256": lineage.digest(control / "plan.json"),
        "plan_content_sha256": plan["content_sha256"],
        "failed_v1_evidence_sha256": old_hashes,
        "separate_salvage": {
            "proof_sha256": lineage.digest(salvage_capture / "proof.json"),
            "complete_sha256": lineage.digest(salvage_capture / "complete.json"),
            "new_fits_executed": 0, "old_wrapper_return_remains": 1}})
    salvage_evidence = {"salvage_proof_sha256": lineage.digest(salvage_capture / "proof.json"),
                        "salvage_complete_sha256": lineage.digest(
                            salvage_capture / "complete.json"),
                        "old_failed_capture_sha256": old_failure,
                        "saved_child_sha256": saved_child,
                        "fourth_refit": {
                            "cell_file_sha256": fourth_producer["cell_file_sha256"],
                            "official_refit_proof": fourth_producer["proof"],
                            "trace_sha256": {}}}
    supervisor_capture = control / "captures/sequential-v2"
    supervisor_start = {
        "owner_pid": 100, "control": str(control), "plan_sha256": plan["content_sha256"],
        "analysis_binding": binding, "production_git_dir": "/frozen/.git",
        "stable_worker_cwd": "/private/tmp", "salvage_evidence": salvage_evidence,
        "initial_refit_ids": sorted(first_four), "remaining_refits": 17}
    write(supervisor_capture / "start.json", supervisor_start)
    write(control / "captures/sequential-v2.claim-at-launch.json", {
        "pid": 100, "capture_root": str(supervisor_capture),
        "plan_sha256": plan["content_sha256"], "analysis_binding": binding,
        "salvage_proof_sha256": salvage_evidence["salvage_proof_sha256"]})
    shutil.copy2(control / "captures/sequential-v2.claim-at-launch.json",
                 rosters / "2026-10-01-v2-supervisor-claim-at-launch.json")
    supervisor_launch = {
        "argv": [plan["python"], "-I", "-B",
                 "/runtime/v2/scripts/supervise_extension_recovery_v2.py",
                 "--control", str(control), "--capture-root", str(supervisor_capture),
                 "--production-git-dir", "/frozen/.git", "--execute"],
        "cwd": "/private/tmp", "control": str(control),
        "capture_root": str(supervisor_capture), "production_git_dir": "/frozen/.git",
        "pid": 100, "plan_file_sha256": lineage.digest(control / "plan.json"),
        "analysis_git_commit": binding["analysis_git_commit"],
        "v2_supervisor_sha256": binding["v2_supervisor_sha256"],
        "salvage_proof_sha256": salvage_evidence["salvage_proof_sha256"]}
    write(control / "captures/sequential-v2.launch.json", supervisor_launch)
    git_environment = {"GIT_DIR": "/frozen/.git", "GIT_WORK_TREE": plan["sealed"],
                       "GIT_OPTIONAL_LOCKS": "0"}
    for number, (name, worker, identity) in enumerate(transfer.v2_dispatches(plan), 1):
        capture = supervisor_capture / name
        write(capture / "launch.json", {
            "command": ["/usr/bin/caffeinate", "-dimsu", "/usr/bin/nice", "-n", "10",
                        plan["python"], "-B", "/runtime/v2/scripts/recover_extension_run.py",
                        "run-worker", "--control", str(control), "--worker", str(worker),
                        "--max-new-cells", "1", "--execute"],
            "cwd": "/private/tmp", "worker": worker, "expected_cell": identity,
            "owner_pid": 100, "plan_sha256": plan["content_sha256"],
            "analysis_binding": binding,
            "salvage_proof_sha256": salvage_evidence["salvage_proof_sha256"],
            "git_environment": git_environment, "thread_limit": 1})
        write(capture / "return.json", {"pid": 1000 + number, "owner_pid": 100,
                                         "return_code": 0})
        (capture / "worker.stdout.log").write_text("bounded dispatch\n")
        (capture / "worker.stderr.log").write_text("")
        verified = {"analysis_binding": binding,
                    "launch_sha256": lineage.digest(capture / "launch.json"),
                    "return_sha256": lineage.digest(capture / "return.json")}
        if identity is None:
            verified.update({"worker": worker, "worker_return_sha256":
                             base["payload"]["worker_return_sha256"][str(worker)]})
            write(capture / "verified_worker.json", verified)
        else:
            verified.update({"cell_id": identity, "proof": {
                "official_refit_proof": base["payload"]["producers"][identity]["proof"],
                "cell_file_sha256": lineage.digest(run / "cells" / f"{identity}.json"),
                "trace_sha256": {}}})
            write(capture / "verified_refit.json", verified)
    write(supervisor_capture / "complete.json", {
        "analysis_binding": binding, "plan_sha256": plan["content_sha256"],
        "salvage_proof_sha256": salvage_evidence["salvage_proof_sha256"],
        "initial_verified_refits": 4, "new_refits": 17, "verified_refits": 21,
        "complete_workers": 6, "worker_return_sha256":
        base["payload"]["worker_return_sha256"], "v1_failure_preserved": True})
    write(rosters / transfer.V2_SUPERVISOR_PUBLISHED, {
        "schema_version": 1, "runtime_checkout": "/runtime/v2", "control": str(control),
        "fixed_plan_file_sha256": lineage.digest(control / "plan.json"),
        "fixed_plan_content_sha256": plan["content_sha256"],
        "launch_sha256": lineage.digest(control / "captures/sequential-v2.launch.json"),
        "start_sha256": lineage.digest(supervisor_capture / "start.json"),
        "v2_claim_sha256": lineage.digest(
            control / "captures/sequential-v2.claim-at-launch.json"),
        "v2_supervisor_source_sha256": binding["v2_supervisor_sha256"],
        "analysis_git_commit": binding["analysis_git_commit"],
        "supervisor_pid_at_checkpoint": 100,
        "independent_frozen_git_dir": "/frozen/.git",
        "stable_parent_and_worker_cwd": "/private/tmp",
        "salvage_proof_sha256": salvage_evidence["salvage_proof_sha256"],
        "v1_failure_and_claims_preserved": True,
        "worker0_terminal_return_sha256": lineage.digest(
            supervisor_capture / "01_worker0_final/return.json"),
        "worker0_terminal_verification_sha256": lineage.digest(
            supervisor_capture / "01_worker0_final/verified_worker.json"),
        "worker1_cell_id": plan["shards"][1][0],
        "worker1_fit_launch_sha256": lineage.digest(
            supervisor_capture / "02_worker1_cell/launch.json")})
    v1_capture = control / "continuation_captures/sequential-v1"
    successor_capture = control / "continuation_captures/sequential-v2"
    shutil.copytree(v1_capture, successor_capture)
    successor_binding = {**binding, "analysis_git_commit": "fixture-successor-v2",
                         "successor_sha256": lineage.digest(
                             root / "scripts/continue_recovered_extension.py"),
                         "supervisor_version": "v2"}
    successor_start = {"analysis_binding": successor_binding,
                       "plan_sha256": plan["content_sha256"], "owner_pid": 200,
                       "control": str(control), "recovered_run": str(run),
                       "assembly_plan": str(control / "assembly_adapter_plan_v2.json"),
                       "production_git_dir": "/frozen/.git", "supervisor_version": "v2",
                       "supervisor_source_sha256": binding["v2_supervisor_sha256"],
                       "successor_source_sha256": successor_binding["successor_sha256"],
                       "supervisor_launch_sha256": lineage.digest(
                           control / "captures/sequential-v2.launch.json")}
    write(successor_capture / "start.json", successor_start)
    worker_hashes = {}
    for worker, record in enumerate(final["continuation_workers"]):
        folder = successor_capture / f"worker_{worker}"
        launch = lineage.read(folder / "launch.json")
        launch["analysis_binding"] = successor_binding
        launch["cwd"] = "/private/tmp"
        write(folder / "launch.json", launch)
        verified = lineage.read(folder / "verified_worker.json")
        verified.update({"analysis_binding": successor_binding,
                         "launch_sha256": lineage.digest(folder / "launch.json")})
        write(folder / "verified_worker.json", verified)
        record["launch_sha256"] = lineage.digest(folder / "launch.json")
        record["verified_worker_sha256"] = lineage.digest(folder / "verified_worker.json")
        worker_hashes[str(worker)] = record["verified_worker_sha256"]
    write(successor_capture / "complete.json", {
        "status": "full_grid_stored_pending_deep_verification", "stored": 1625,
        "new_continuation_cells": 411, "plan_sha256": plan["content_sha256"],
        "analysis_binding": successor_binding,
        "assembly_plan_sha256": assembly["content_sha256"],
        "verified_worker_sha256": worker_hashes, "supervisor_version": "v2",
        "supervisor_source_sha256": binding["v2_supervisor_sha256"],
        "successor_source_sha256": successor_binding["successor_sha256"],
        "supervisor_launch_sha256": successor_start["supervisor_launch_sha256"],
        "supervisor_complete_sha256": lineage.digest(supervisor_capture / "complete.json"),
        "salvage_proof_sha256": salvage_evidence["salvage_proof_sha256"],
        "v1_failure_preserved": True})
    write(control / "continuation_captures/sequential-v2.claim-at-launch.json", {
        "pid": 200, "capture_root": str(successor_capture),
        "plan_sha256": plan["content_sha256"], "supervisor_version": "v2"})
    shutil.copy2(control / "continuation_captures/sequential-v2.claim-at-launch.json",
                 rosters / "2026-10-01-v2-continuation-claim-at-launch.json")
    write(control / "continuation_captures/sequential-v2.launch.json", {
        "argv": [plan["python"], "-I", "-B",
                 "/runtime/successor/scripts/continue_recovered_extension.py",
                 "--supervisor-version", "v2", "--control", str(control),
                 "--recovered-run", str(run), "--assembly-plan",
                 str(control / "assembly_adapter_plan_v2.json"),
                 "--capture-root", str(successor_capture), "--production-git-dir",
                 "/frozen/.git", "--poll-seconds", "60", "--execute"],
        "cwd": "/private/tmp", "control": str(control),
        "capture_root": str(successor_capture), "recovered_run": str(run),
        "assembly_plan": str(control / "assembly_adapter_plan_v2.json"),
        "production_git_dir": "/frozen/.git", "pid": 200,
        "plan_file_sha256": lineage.digest(control / "plan.json"),
        "analysis_git_commit": successor_binding["analysis_git_commit"],
        "successor_sha256": successor_binding["successor_sha256"],
        "supervisor_launch_sha256": successor_start["supervisor_launch_sha256"]})
    write(rosters / transfer.V2_CONTINUATION_PUBLISHED, {
        "schema_version": 1, "runtime_checkout": "/runtime/successor",
        "successor_launch_sha256": lineage.digest(
            control / "continuation_captures/sequential-v2.launch.json"),
        "successor_start_sha256": lineage.digest(successor_capture / "start.json"),
        "successor_claim_sha256_at_checkpoint": lineage.digest(
            control / "continuation_captures/sequential-v2.claim-at-launch.json"),
        "successor_source_sha256": successor_binding["successor_sha256"],
        "analysis_git_commit": successor_binding["analysis_git_commit"],
        "supervisor_launch_sha256": successor_start["supervisor_launch_sha256"],
        "supervisor_published_launch_sha256": lineage.digest(
            rosters / transfer.V2_SUPERVISOR_PUBLISHED),
        "fixed_plan_file_sha256": lineage.digest(control / "plan.json"),
        "fixed_plan_content_sha256": plan["content_sha256"],
        "control": str(control), "recovered_run": str(run),
        "assembly_plan": str(control / "assembly_adapter_plan_v2.json"),
        "successor_pid_at_checkpoint": 200, "v1_failed_chain_preserved": True})
    final.update({
        "supervisor_version": "v2",
        "continuation_start_sha256": lineage.digest(successor_capture / "start.json"),
        "continuation_complete_sha256": lineage.digest(successor_capture / "complete.json"),
        "continuation_analysis_binding": successor_binding,
        "v2_source_sha256": {
            "supervisor_launch_sha256": lineage.digest(
                control / "captures/sequential-v2.launch.json"),
            "supervisor_start_sha256": lineage.digest(supervisor_capture / "start.json"),
            "supervisor_complete_sha256": lineage.digest(supervisor_capture / "complete.json"),
            "supervisor_published_launch_sha256": lineage.digest(
                rosters / transfer.V2_SUPERVISOR_PUBLISHED),
            "supervisor_claim_at_launch_sha256": lineage.digest(
                control / "captures/sequential-v2.claim-at-launch.json"),
            "successor_launch_sha256": lineage.digest(
                control / "continuation_captures/sequential-v2.launch.json"),
            "successor_published_launch_sha256": lineage.digest(
                rosters / transfer.V2_CONTINUATION_PUBLISHED),
            "successor_claim_at_launch_sha256": lineage.digest(
                control / "continuation_captures/sequential-v2.claim-at-launch.json"),
            "incident_sha256": lineage.digest(rosters / transfer.V2_INCIDENT_PUBLISHED),
            "salvage_proof_sha256": lineage.digest(salvage_capture / "proof.json"),
            "salvage_complete_sha256": lineage.digest(salvage_capture / "complete.json"),
        }})
    final["content_sha256"] = lineage.canonical_hash({
        key: value for key, value in final.items() if key != "content_sha256"})
    write(run / "recovery_continuation.json", final)


def test_captured_recovery_bundle_survives_relocation_and_rejects_nonzero_return(
        tmp_path: Path) -> None:
    """The receiving proof checks real copied returns, not just shaped hashes."""
    run, control, rosters, bundle = bundle_fixture(tmp_path)
    source_result = transfer.stage_recovery_bundle(control, run, bundle, rosters)
    assert source_result["affected_refits"] == 21
    assert source_result["continuation_cells"] == 411
    received = tmp_path / "received"
    shutil.copytree(run, received / "run")
    shutil.copytree(bundle, received / "recovery")
    assert transfer.verify_recovery_bundle(received / "run", received / "recovery",
                                           rosters) == source_result
    worker_return = received / "recovery/continuation/worker_2/return.json"
    changed = transfer.read(worker_return)
    changed["return_code"] = 1
    write(worker_return, changed)
    with pytest.raises(ValueError, match="recovery proof member differs"):
        transfer.verify_recovery_bundle(received / "run", received / "recovery", rosters)


def test_captured_recovery_bundle_rejects_missing_refit_comparison(tmp_path: Path) -> None:
    """The 21 preserved old/new comparisons are mandatory receiving evidence."""
    run, control, rosters, bundle = bundle_fixture(tmp_path)
    transfer.stage_recovery_bundle(control, run, bundle, rosters)
    first = next((bundle / "refits").iterdir())
    (first / "scientific_comparison.json").unlink()
    with pytest.raises(ValueError, match="missing or extra files"):
        transfer.verify_recovery_bundle(run, bundle, rosters)


def test_captured_supervisor_launch_rejects_resealed_semantic_change(tmp_path: Path) -> None:
    """Inventory hashes cannot substitute for the captured launch attestation."""
    run, control, rosters, bundle = bundle_fixture(tmp_path)
    transfer.stage_recovery_bundle(control, run, bundle, rosters)
    launch_path = bundle / "supervisor/launch.json"
    changed = transfer.read(launch_path)
    changed["pid"] += 1
    write(launch_path, changed)
    inventory_path = bundle / "inventory.json"
    inventory = transfer.read(inventory_path)
    inventory["members"]["supervisor/launch.json"] = lineage.digest(launch_path)
    inventory["content_sha256"] = lineage.canonical_hash({
        key: value for key, value in inventory.items() if key != "content_sha256"})
    write(inventory_path, inventory)
    with pytest.raises(ValueError, match="captured supervisor launch"):
        transfer.verify_recovery_bundle(run, bundle, rosters)


def test_recovery_code_archive_binds_captured_sources(tmp_path: Path) -> None:
    """The shipped Git source must contain the exact captured producer code."""
    run, control, rosters, bundle = bundle_fixture(tmp_path)
    transfer.stage_recovery_bundle(control, run, bundle, rosters)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "scripts", "src", "coordination/recovery"],
                   cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.org",
                    "commit", "-qm", "recovery fixture code"], cwd=tmp_path, check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                   cwd=tmp_path, text=True).strip()
    archive = tmp_path / "recovery-code.tar.gz"
    subprocess.run(["git", "archive", "--format=tar.gz", f"--output={archive}", "HEAD"],
                   cwd=tmp_path, check=True)
    result = transfer.verify_recovery_code_archive(archive, bundle, head)
    assert result["bound_sources"] == len(adapter.ANALYSIS_FILES) + 5
    (bundle / "code/scripts/continue_recovered_extension.py").write_text("# changed\n")
    with pytest.raises(ValueError, match="differs from captured proof"):
        transfer.verify_recovery_code_archive(archive, bundle, head)


def test_v2_recovery_bundle_carries_full_supervisor_and_salvage_chain(
        tmp_path: Path) -> None:
    """A receiving host can validate all 23 V2 dispatches and old V1 evidence."""
    run, control, rosters, bundle = bundle_fixture(tmp_path, v2=True)
    result = transfer.stage_recovery_bundle(control, run, bundle, rosters)
    assert result["affected_refits"] == 21
    assert transfer.read(bundle / "inventory.json")["supervisor_version"] == "v2"
    assert len(list((bundle / "supervisor/dispatches").iterdir())) == 23
    received = tmp_path / "received-v2"
    shutil.copytree(run, received / "run")
    shutil.copytree(bundle, received / "proofs")
    assert transfer.verify_recovery_bundle(received / "run", received / "proofs") == result


def test_v2_resealed_dispatch_change_fails_semantic_gate(tmp_path: Path) -> None:
    """Rehashing an invented nonzero child exit cannot turn it into a verified fit."""
    run, control, rosters, bundle = bundle_fixture(tmp_path, v2=True)
    transfer.stage_recovery_bundle(control, run, bundle, rosters)
    target = bundle / "supervisor/dispatches/02_worker1_cell/return.json"
    changed = transfer.read(target)
    changed["return_code"] = 1
    write(target, changed)
    inventory_path = bundle / "inventory.json"
    inventory = transfer.read(inventory_path)
    inventory["members"][target.relative_to(bundle).as_posix()] = lineage.digest(target)
    inventory["content_sha256"] = lineage.canonical_hash({
        key: value for key, value in inventory.items() if key != "content_sha256"})
    write(inventory_path, inventory)
    with pytest.raises(ValueError, match="V2 bounded dispatch differs"):
        transfer.verify_recovery_bundle(run, bundle, rosters)


def test_v2_resealed_salvage_start_change_fails_semantic_gate(tmp_path: Path) -> None:
    """A resealed inventory cannot turn the separate comparison into a fit."""
    run, control, rosters, bundle = bundle_fixture(tmp_path, v2=True)
    transfer.stage_recovery_bundle(control, run, bundle, rosters)
    target = bundle / "salvage/start.json"
    changed = transfer.read(target)
    changed["no_fit_comparison_only"] = False
    write(target, changed)
    inventory_path = bundle / "inventory.json"
    inventory = transfer.read(inventory_path)
    inventory["members"][target.relative_to(bundle).as_posix()] = lineage.digest(target)
    inventory["content_sha256"] = lineage.canonical_hash({
        key: value for key, value in inventory.items() if key != "content_sha256"})
    write(inventory_path, inventory)
    with pytest.raises(ValueError, match="preserved V1 and no-fit child return differs"):
        transfer.verify_recovery_bundle(run, bundle, rosters)


def test_v2_source_rejects_unmapped_dispatch_before_copy(tmp_path: Path) -> None:
    """A source with a hidden extra producer cannot be presented as 23 captures."""
    run, control, rosters, bundle = bundle_fixture(tmp_path, v2=True)
    write(control / "captures/sequential-v2/24_worker5_cell/launch.json",
          {"unexpected": "fit"})
    with pytest.raises(ValueError, match="missing or extra producer files"):
        transfer.stage_recovery_bundle(control, run, bundle, rosters)
    assert not bundle.exists()


def test_v2_archive_binds_published_claim_snapshots(tmp_path: Path) -> None:
    """The immutable source archive must contain both exact V2 claim copies."""
    run, control, rosters, bundle = bundle_fixture(tmp_path, v2=True)
    transfer.stage_recovery_bundle(control, run, bundle, rosters)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "scripts", "src", "coordination/recovery"],
                   cwd=tmp_path, check=True)
    subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.org",
                    "commit", "-qm", "V2 fixture code"], cwd=tmp_path, check=True)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                   cwd=tmp_path, text=True).strip()
    archive = tmp_path / "v2-code.tar.gz"
    subprocess.run(["git", "archive", "--format=tar.gz", f"--output={archive}", "HEAD"],
                   cwd=tmp_path, check=True)
    assert transfer.verify_recovery_code_archive(archive, bundle, head)["bound_sources"] == (
        len(adapter.ANALYSIS_FILES) + 12)
    (bundle / "supervisor/claim_at_launch.json").write_text("{}\n")
    with pytest.raises(ValueError, match="differs from captured proof"):
        transfer.verify_recovery_code_archive(archive, bundle, head)
