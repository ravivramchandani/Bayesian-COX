"""Seal 411 continuation producers after captured workers actually finish."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import assemble_recovered_extension as adapter
from scripts import continue_recovered_extension as continuation
from scripts import recover_extension_run as recovery
from scripts.extension_release.recovery_lineage import verify_recovered_lineage


def source_lineage(control: Path, run: Path) -> dict[str, Any]:
    """Reconstruct the final lineage from six real worker exits and saved cells."""
    plan = recovery.load_plan(control)
    assembly_path = control / "assembly_adapter_plan_v1.json"
    capture = control / "continuation_captures/sequential-v1"
    if (not (capture / "complete.json").is_file() or (capture / "failure.json").exists()
            or (control / "continuation_supervisor.claim").exists()
            or list((run / "claims").glob("*.json"))
            or list((control / "worker_claims").glob("*.json"))
            or list((control / "cell_claims").glob("*.json"))):
        raise ValueError("continuation is incomplete or a producer claim remains")
    manifest, assembled = continuation.require_assembled_run(control, plan, run, assembly_path)
    start, complete = (recovery.read_json(capture / name) for name in
                       ("start.json", "complete.json"))
    binding = start["analysis_binding"]
    if (start.get("control") != str(control)
            or start.get("recovered_run") != str(run)
            or start.get("assembly_plan") != str(assembly_path)
            or start.get("plan_sha256") != plan["content_sha256"]
            or complete.get("status") != "full_grid_stored_pending_deep_verification"
            or complete.get("plan_sha256") != plan["content_sha256"]
            or complete.get("assembly_plan_sha256") != assembled["content_sha256"]
            or complete.get("analysis_binding") != binding
            or complete.get("stored") != 1625
            or complete.get("new_continuation_cells") != 411):
        raise ValueError("continuation start or completion differs from fixed plan")
    shards = continuation.assigned_pending(manifest, plan["absent_cell_ids"])
    config, cohorts, jobs = adapter.validated_jobs(manifest, Path(plan["sealed"]),
                                                   Path(plan["matched"]))
    worker_records = []
    new_producers: dict[str, dict[str, Any]] = {}
    for worker, identities in enumerate(shards):
        folder = capture / f"worker_{worker}"
        launch, returned, verified = (recovery.read_json(folder / name) for name in
                                      ("launch.json", "return.json", "verified_worker.json"))
        actual = continuation.verified_new_cells(run, identities, jobs, cohorts,
                                                 config["base_seed"])
        receipt_hash = recovery.sha256_file(folder / "verified_worker.json")
        runner = Path(plan["sealed"]) / "scripts/run_extensions.py"
        expected_argv = ["/usr/bin/caffeinate", "-dimsu", "/usr/bin/nice", "-n", "10",
                         plan["python"], "-B", str(runner), "--matched", plan["matched"],
                         "--output", str(run), "--workers", "6", "--worker", str(worker)]
        if (not isinstance(start.get("owner_pid"), int)
                or launch.get("owner_pid") != start["owner_pid"]
                or returned.get("owner_pid") != start["owner_pid"]
                or returned.get("pid") != launch.get("pid")
                or returned.get("return_code") != 0
                or launch.get("worker") != worker
                or launch.get("expected_cell_ids") != identities
                or launch.get("analysis_binding") != binding
                or launch.get("assembly_plan_sha256") != assembled["content_sha256"]
                or launch.get("argv") != expected_argv
                or launch.get("cwd") != plan["sealed"]
                or launch.get("thread_limit") != 1
                or launch.get("production_runner_sha256") != recovery.sha256_file(runner)
                or verified.get("worker") != worker
                or verified.get("expected_cell_ids") != identities
                or verified.get("cell_producers") != actual
                or verified.get("plan_sha256") != plan["content_sha256"]
                or verified.get("assembly_plan_sha256") != assembled["content_sha256"]
                or verified.get("analysis_binding") != binding
                or verified.get("status_counts") !=
                dict(Counter(record["status"] for record in actual.values()))
                or verified.get("launch_sha256") != recovery.sha256_file(folder / "launch.json")
                or verified.get("return_sha256") != recovery.sha256_file(folder / "return.json")
                or verified.get("stdout_sha256") != recovery.sha256_file(folder / "stdout.log")
                or verified.get("stderr_sha256") != recovery.sha256_file(folder / "stderr.log")
                or complete.get("verified_worker_sha256", {}).get(str(worker)) != receipt_hash):
            raise ValueError(f"continuation worker {worker} lacks bound zero-return proof")
        for identity, record in actual.items():
            new_producers[identity] = {"worker": worker, **record}
        worker_records.append({"worker": worker, "cell_ids": identities,
                               "verified_worker_sha256": receipt_hash,
                               "launch_sha256": verified["launch_sha256"],
                               "return_sha256": verified["return_sha256"],
                               "stdout_sha256": verified["stdout_sha256"],
                               "stderr_sha256": verified["stderr_sha256"]})
    original = set(assembled["payload"]["producers"])
    continuation.require_exact_cells(run, original, {
        identity: {k: record[k] for k in ("cell_file_sha256", "trace_sha256")}
        for identity, record in new_producers.items()})
    result = {"schema_version": 1,
              "status": "full_recovered_extension_provenance",
              "manifest_sha256": recovery.sha256_file(run / "manifest.json"),
              "base_lineage_sha256": recovery.sha256_file(run / "recovery_lineage.json"),
              "assembly_plan_sha256": assembled["content_sha256"],
              "controller_plan_sha256": plan["content_sha256"],
              "source_forensic_sha256": assembled["payload"]["source_forensic_sha256"],
              "absent_roster_sha256": assembled["payload"]["absent_roster_sha256"],
              "continuation_start_sha256": recovery.sha256_file(capture / "start.json"),
              "continuation_complete_sha256": recovery.sha256_file(capture / "complete.json"),
              "continuation_analysis_binding": binding,
              "producer_counts": {"intact_original": 1193, "new_refit": 21,
                                  "new_continuation": 411},
              "continuation_workers": worker_records,
              "continuation_producers": new_producers}
    result["content_sha256"] = recovery.content_sha256(result)
    return result


def main() -> None:
    """Write a new supplement only after the complete source proof passes."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--control", type=Path, required=True)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--verify-only", action="store_true",
                        help="recompute actual producer proof without writing")
    args = parser.parse_args()
    control, run = args.control.resolve(), args.run.resolve()
    target = run / "recovery_continuation.json"
    result = source_lineage(control, run)
    if args.verify_only:
        if recovery.read_json(target) != result:
            raise ValueError("stored final lineage differs from actual source proof")
        print(json.dumps(verify_recovered_lineage(run), sort_keys=True))
        return
    if target.exists() or target.is_symlink():
        raise FileExistsError(target)
    verify_recovered_lineage(run, candidate=result)
    recovery.write_new_json(target, result)
    print(verify_recovered_lineage(run))


if __name__ == "__main__":
    main()
