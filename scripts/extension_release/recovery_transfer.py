"""Carry captured recovery proofs with a restored extension run."""

from __future__ import annotations

import hashlib
import json
import shutil
import tarfile
from collections import Counter
from pathlib import Path
from typing import Any

if __package__:
    from .recovery_lineage import canonical_hash, digest, read, verify_recovered_lineage
else:
    from recovery_lineage import canonical_hash, digest, read, verify_recovered_lineage

REFIT_FILES = ("invocation.json", "child_start.json", "child_return.json",
               "scientific_comparison.json", "child.stdout.log", "child.stderr.log")
CONTINUATION_FILES = ("launch.json", "return.json", "verified_worker.json",
                      "stdout.log", "stderr.log")
FORENSIC_NAME = "2026-09-30-host-interruption-trace-inventory.json"
ABSENT_NAME = "2026-09-30-original-extension-absent-roster.json"


def source_files(control: Path, run: Path, rosters: Path) -> dict[str, Path]:
    """List only the fixed proof files needed by a receiving verifier."""
    plan = read(control / "plan.json")
    source = Path(plan["source"])
    code = rosters.parents[1]
    base = read(run / "recovery_lineage.json")["payload"]
    mapping = {
        "control/plan.json": control / "plan.json",
        "control/assembly_plan.json": control / "assembly_adapter_plan_v1.json",
        "control/assembly_receipt.json": control / "assembly_adapter_receipt.json",
        "rosters/trace_inventory.json": rosters / FORENSIC_NAME,
        "rosters/absent_roster.json": rosters / ABSENT_NAME,
        "supervisor/start.json": control / "captures/sequential-v1/start.json",
        "supervisor/complete.json": control / "captures/sequential-v1/complete.json",
        "continuation/start.json": control / "continuation_captures/sequential-v1/start.json",
        "continuation/complete.json": control / "continuation_captures/sequential-v1/complete.json",
    }
    for relative in base["analysis_code_sha256"]:
        mapping[f"code/{relative}"] = code / relative
    for name in ("supervise_extension_recovery.py", "continue_recovered_extension.py"):
        mapping[f"code/scripts/{name}"] = code / "scripts" / name
    for worker in range(6):
        mapping[f"control/worker_returns/worker_{worker}.json"] = (
            control / "worker_returns" / f"worker_{worker}.json")
        capture = control / "continuation_captures/sequential-v1" / f"worker_{worker}"
        for name in CONTINUATION_FILES:
            mapping[f"continuation/worker_{worker}/{name}"] = capture / name
    for identity in plan["affected_cell_ids"]:
        mapping[f"original_cells/{identity}.json"] = source / "cells" / f"{identity}.json"
        attempt = control / "refits" / identity / "attempt_001"
        for name in REFIT_FILES:
            mapping[f"refits/{identity}/{name}"] = attempt / name
    return mapping


def stage_recovery_bundle(control: Path, run: Path, destination: Path,
                          rosters: Path) -> dict[str, Any]:
    """Copy exact source proofs into a new bundle, then reverify the copy."""
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    destination.mkdir(parents=True, exist_ok=False)
    members = {}
    for relative, source in sorted(source_files(control, run, rosters).items()):
        expected = digest(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if digest(target) != expected:
            raise ValueError(f"copied recovery proof changed: {relative}")
        members[relative] = expected
    base = {"schema_version": 1, "status": "captured_recovery_proofs",
            "run_manifest_sha256": digest(run / "manifest.json"),
            "base_lineage_sha256": digest(run / "recovery_lineage.json"),
            "final_lineage_sha256": digest(run / "recovery_continuation.json"),
            "members": members}
    base["content_sha256"] = canonical_hash(base)
    inventory = destination / "inventory.json"
    with inventory.open("x", encoding="utf-8") as stream:
        json.dump(base, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
    return verify_recovery_bundle(run, destination, rosters)


def require_bundle_inventory(run: Path, bundle: Path) -> dict[str, Any]:
    """Check every proof byte and reject missing, additional or linked files."""
    if bundle.is_symlink() or not bundle.is_dir():
        raise ValueError("missing or linked recovery proof bundle")
    inventory = read(bundle / "inventory.json")
    if (canonical_hash({key: value for key, value in inventory.items()
                        if key != "content_sha256"}) != inventory.get("content_sha256")
            or inventory.get("schema_version") != 1
            or inventory.get("status") != "captured_recovery_proofs"
            or inventory.get("run_manifest_sha256") != digest(run / "manifest.json")
            or inventory.get("base_lineage_sha256") != digest(run / "recovery_lineage.json")
            or inventory.get("final_lineage_sha256") != digest(run / "recovery_continuation.json")
            or not isinstance(inventory.get("members"), dict)):
        raise ValueError("recovery proof inventory binding differs")
    actual: set[str] = set()
    for path in bundle.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"linked recovery bundle path: {path}")
        if path.is_file():
            actual.add(path.relative_to(bundle).as_posix())
        elif not path.is_dir():
            raise ValueError(f"unsupported recovery bundle entry: {path}")
    if actual != set(inventory["members"]) | {"inventory.json"}:
        raise ValueError("recovery proof bundle has missing or extra files")
    for relative, expected in inventory["members"].items():
        if (not isinstance(relative, str) or Path(relative).is_absolute()
                or any(part in {"", ".", ".."} for part in Path(relative).parts)
                or "\\" in relative or digest(bundle / relative) != expected):
            raise ValueError(f"recovery proof member differs: {relative}")
    return inventory


def scientific_content(value: Any) -> Any:
    """Apply the frozen non-timing comparison field exclusion."""
    if isinstance(value, dict):
        ignored = {"seconds", "total_seconds", "fit_seconds", "cell_content_sha256",
                   "traces", "traceback"}
        return {key: scientific_content(item) for key, item in value.items()
                if key not in ignored}
    if isinstance(value, list):
        return [scientific_content(item) for item in value]
    return value


def verify_recovery_bundle(run: Path, bundle: Path,
                           rosters: Path | None = None) -> dict[str, Any]:
    """Recheck captured returns and source/refit comparisons after relocation."""
    lineage = verify_recovered_lineage(run)
    inventory = require_bundle_inventory(run, bundle)
    base = read(run / "recovery_lineage.json")["payload"]
    final = read(run / "recovery_continuation.json")
    plan = read(bundle / "control/plan.json")
    assembly = read(bundle / "control/assembly_plan.json")
    receipt = read(bundle / "control/assembly_receipt.json")
    if (canonical_hash({key: value for key, value in plan.items()
                        if key != "content_sha256"}) != plan.get("content_sha256")
            or plan["content_sha256"] != final["controller_plan_sha256"]
            or plan["source_manifest_sha256"] != lineage["manifest_sha256"]
            or len(plan["affected_cell_ids"]) != 21
            or len(plan["absent_cell_ids"]) != 411
            or plan["absent_cell_ids"] != base["pending_cell_ids"]
            or canonical_hash({key: value for key, value in assembly.items()
                               if key != "content_sha256"}) != assembly.get("content_sha256")
            or assembly.get("content_sha256") != final["assembly_plan_sha256"]
            or assembly.get("payload") != base
            or receipt.get("assembly_plan_sha256") != assembly["content_sha256"]
            or receipt.get("manifest_sha256") != lineage["manifest_sha256"]
            or receipt.get("lineage_sha256") != lineage["base_lineage_sha256"]):
        raise ValueError("recovery control or assembly proof differs")
    shards = plan.get("shards")
    if (not isinstance(shards, list) or len(shards) != 6
            or [identity for shard in shards for identity in shard] !=
            [identity for shard in shards for identity in shard if identity in plan["affected_cell_ids"]]
            or len({identity for shard in shards for identity in shard}) != 21
            or set(identity for shard in shards for identity in shard) !=
            set(plan["affected_cell_ids"])):
        raise ValueError("21-refit shard partition differs")
    for source_name, bundle_name, key in (
        (FORENSIC_NAME, "trace_inventory.json", "forensic_sha256"),
        (ABSENT_NAME, "absent_roster.json", "absent_roster_sha256"),
    ):
        if (digest(bundle / "rosters" / bundle_name) != plan[key]
                or (rosters is not None and digest(rosters / source_name) != plan[key])):
            raise ValueError("recovery roster differs from committed analysis code")
    absent = read(bundle / "rosters/absent_roster.json")
    if absent.get("absent_cell_ids") != plan["absent_cell_ids"]:
        raise ValueError("recovery absent roster differs from plan")
    supervisor = read(bundle / "supervisor/complete.json")
    supervisor_start = read(bundle / "supervisor/start.json")
    code_hashes = dict(base["analysis_code_sha256"])
    code_hashes.update({
        "scripts/supervise_extension_recovery.py":
            supervisor_start["analysis_binding"]["supervisor_sha256"],
        "scripts/continue_recovered_extension.py":
            final["continuation_analysis_binding"]["successor_sha256"],
    })
    if (code_hashes.get("scripts/recover_extension_run.py") != plan["controller_sha256"]
            or code_hashes.get("scripts/assemble_recovered_extension.py") !=
            base["adapter_sha256"]):
        raise ValueError("recovery analysis code bindings differ from controller")
    if any(digest(bundle / "code" / name) != expected
           for name, expected in code_hashes.items()):
        raise ValueError("recovery source code differs from captured bindings")
    if (supervisor_start.get("plan_sha256") != plan["content_sha256"]
            or not isinstance(supervisor_start.get("owner_pid"), int)
            or supervisor.get("analysis_binding") != supervisor_start.get("analysis_binding")
            or supervisor.get("plan_sha256") != plan["content_sha256"]
            or supervisor.get("verified_refits") != 21
            or supervisor.get("complete_workers") != 6):
        raise ValueError("21-refit supervisor completion differs")
    for worker, identities in enumerate(plan["shards"]):
        worker_path = bundle / "control/worker_returns" / f"worker_{worker}.json"
        worker_receipt = read(worker_path)
        if (digest(worker_path) != base["worker_return_sha256"][str(worker)]
                or worker_receipt.get("worker") != worker
                or worker_receipt.get("status") != "complete"
                or worker_receipt.get("cell_ids") != identities):
            raise ValueError(f"refit shard {worker} return differs")
    from src.pipelines.extensions.verification import assert_scientific_equal

    if (set(plan["affected_cell_ids"]) !=
            {identity for identity, record in base["producers"].items()
             if record["producer"] == "new_refit"}):
        raise ValueError("21 affected producers differ from fixed plan")
    for identity in plan["affected_cell_ids"]:
        producer = base["producers"][identity]
        old_path = bundle / "original_cells" / f"{identity}.json"
        new_path = run / "cells" / f"{identity}.json"
        old, new = read(old_path), read(new_path)
        proof = producer["proof"]
        folder = bundle / "refits" / identity
        bindings = {"invocation.json": "invocation_sha256",
                    "child_start.json": "child_start_sha256",
                    "child_return.json": "child_return_sha256",
                    "scientific_comparison.json": "comparison_sha256",
                    "child.stdout.log": "child_stdout_sha256",
                    "child.stderr.log": "child_stderr_sha256"}
        if (digest(old_path) != producer["original_cell_file_sha256"]
                or digest(old_path) != plan["source_cell_file_sha256"][identity]
                or digest(new_path) != producer["cell_file_sha256"]
                or any(digest(folder / name) != proof[key] for name, key in bindings.items())):
            raise ValueError(f"refit source or captured proof changed: {identity}")
        invocation = read(folder / "invocation.json")
        child_start = read(folder / "child_start.json")
        child_return = read(folder / "child_return.json")
        comparison = read(folder / "scientific_comparison.json")
        argv = invocation.get("argv")
        token = invocation.get("token")
        owner = next((worker for worker, shard in enumerate(shards)
                      if identity in shard), None)
        expected_argv = [plan["python"], proof["controller_source_path"],
                         "child", "--control", supervisor_start["control"],
                         "--cell-id", identity, "--run", producer["producer_run"],
                         "--token", token]
        expected_traces = {f"{number}/{role}/{trace['filename']}": trace["sha256"]
                           for number, fit in enumerate(new.get("fit_attempts", []), 1)
                           for role, trace in fit.get("traces", {}).items()}
        if (not isinstance(token, str) or len(token) != 32
                or argv != expected_argv
                or proof.get("controller_source_sha256") != plan["controller_sha256"]
                or invocation.get("plan_sha256") != plan["content_sha256"]
                or invocation.get("cwd") != plan["sealed"]
                or invocation.get("worker") != owner
                or not isinstance(child_start.get("pid"), int)
                or child_start.get("cell_id") != identity
                or child_return.get("cell_id") != identity
                or child_return.get("return_code") != 0
                or proof["child_return_code"] != 0
                or comparison.get("official_non_timing_science") != "match"
                or comparison.get("cell_id") != identity
                or comparison.get("difference") is not None
                or comparison.get("source_cell_file_sha256") != digest(old_path)
                or comparison.get("refit_cell_file_sha256") != digest(new_path)
                or comparison.get("source_cell_content_sha256") != old["cell_content_sha256"]
                or comparison.get("refit_cell_content_sha256") != new["cell_content_sha256"]
                or comparison.get("source_status") != old["status"]
                or comparison.get("refit_status") != new["status"]
                or comparison.get("refit_trace_sha256") != expected_traces
                or proof.get("original_posterior_array_equality") !=
                "unavailable: original trace bytes missing"):
            raise ValueError(f"refit non-timing comparison proof differs: {identity}")
        assert_scientific_equal(scientific_content(old), scientific_content(new), identity)
    start = read(bundle / "continuation/start.json")
    complete = read(bundle / "continuation/complete.json")
    if (digest(bundle / "continuation/start.json") != final["continuation_start_sha256"]
            or digest(bundle / "continuation/complete.json") !=
            final["continuation_complete_sha256"]
            or start.get("analysis_binding") != final["continuation_analysis_binding"]
            or start.get("control") != supervisor_start["control"]
            or start.get("recovered_run") != base["destination"]
            or start.get("assembly_plan") !=
            str(Path(supervisor_start["control"]) / "assembly_adapter_plan_v1.json")
            or start.get("plan_sha256") != plan["content_sha256"]
            or complete.get("status") != "full_grid_stored_pending_deep_verification"
            or complete.get("stored") != 1625
            or complete.get("new_continuation_cells") != 411
            or complete.get("assembly_plan_sha256") != assembly["content_sha256"]
            or complete.get("analysis_binding") != final["continuation_analysis_binding"]
            or complete.get("plan_sha256") != plan["content_sha256"]):
        raise ValueError("continuation start or completion proof differs")
    manifest = read(run / "manifest.json")
    for worker, record in enumerate(final["continuation_workers"]):
        folder = bundle / "continuation" / f"worker_{worker}"
        launch = read(folder / "launch.json")
        returned = read(folder / "return.json")
        verified = read(folder / "verified_worker.json")
        subset = {identity: {key: value for key, value in
                             final["continuation_producers"][identity].items()
                             if key != "worker"} for identity in record["cell_ids"]}
        expected_argv = ["/usr/bin/caffeinate", "-dimsu", "/usr/bin/nice", "-n", "10",
                         plan["python"], "-B",
                         str(Path(plan["sealed"]) / "scripts/run_extensions.py"),
                         "--matched", plan["matched"], "--output", base["destination"],
                         "--workers", "6", "--worker", str(worker)]
        if (digest(folder / "verified_worker.json") != record["verified_worker_sha256"]
                or digest(folder / "launch.json") != record["launch_sha256"]
                or digest(folder / "return.json") != record["return_sha256"]
                or digest(folder / "stdout.log") != record["stdout_sha256"]
                or digest(folder / "stderr.log") != record["stderr_sha256"]
                or complete.get("verified_worker_sha256", {}).get(str(worker)) !=
                record["verified_worker_sha256"]
                or launch.get("worker") != worker
                or launch.get("argv") != expected_argv
                or launch.get("cwd") != plan["sealed"]
                or launch.get("thread_limit") != 1
                or launch.get("production_runner_sha256") !=
                manifest["input_sha256"]["scripts/run_extensions.py"]
                or launch.get("expected_cell_ids") != record["cell_ids"]
                or launch.get("analysis_binding") != final["continuation_analysis_binding"]
                or launch.get("assembly_plan_sha256") != assembly["content_sha256"]
                or launch.get("owner_pid") != start["owner_pid"]
                or returned.get("pid") != launch.get("pid")
                or returned.get("owner_pid") != start["owner_pid"]
                or returned.get("return_code") != 0
                or verified.get("cell_producers") != subset
                or verified.get("worker") != worker
                or verified.get("analysis_binding") != final["continuation_analysis_binding"]
                or verified.get("plan_sha256") != plan["content_sha256"]
                or verified.get("assembly_plan_sha256") != assembly["content_sha256"]
                or verified.get("launch_sha256") != record["launch_sha256"]
                or verified.get("return_sha256") != record["return_sha256"]
                or verified.get("stdout_sha256") != record["stdout_sha256"]
                or verified.get("stderr_sha256") != record["stderr_sha256"]
                or verified.get("expected_cell_ids") != record["cell_ids"]
                or verified.get("status_counts") !=
                dict(Counter(value["status"] for value in subset.values()))):
            raise ValueError(f"continuation worker {worker} captured proof differs")
    return {"status": "captured_recovery_transfer_verified",
            "bundle_inventory_sha256": digest(bundle / "inventory.json"),
            "bundle_content_sha256": inventory["content_sha256"],
            "base_lineage_sha256": lineage["base_lineage_sha256"],
            "final_lineage_sha256": lineage["final_lineage_sha256"],
            "affected_refits": 21, "continuation_workers": 6,
            "continuation_cells": 411, "stored_cells": 1625}


def verify_recovery_code_archive(archive_path: Path, bundle: Path,
                                 expected_commit: str) -> dict[str, Any]:
    """Bind the shipped Git archive to each frozen recovery source proof."""
    required = {path.relative_to(bundle / "code").as_posix(): path
                for path in (bundle / "code").rglob("*") if path.is_file()}
    required.update({
        f"coordination/recovery/{source}": bundle / "rosters" / target
        for source, target in ((FORENSIC_NAME, "trace_inventory.json"),
                               (ABSENT_NAME, "absent_roster.json"))})
    with tarfile.open(archive_path, "r:gz") as archive:
        if archive.pax_headers.get("comment") != expected_commit:
            raise ValueError("recovery code archive commit differs")
        for name, target in required.items():
            member = archive.getmember(name)
            if not member.isfile():
                raise ValueError(f"recovery source archive member is not a file: {name}")
            stream = archive.extractfile(member)
            if stream is None:
                raise ValueError(f"recovery source archive member is missing: {name}")
            value = hashlib.sha256()
            with stream:
                while block := stream.read(1024 * 1024):
                    value.update(block)
            if value.hexdigest() != digest(target):
                raise ValueError(f"recovery source archive differs from captured proof: {name}")
    return {"status": "recovery_code_archive_verified", "git_commit": expected_commit,
            "archive_sha256": digest(archive_path), "bound_sources": len(required)}
