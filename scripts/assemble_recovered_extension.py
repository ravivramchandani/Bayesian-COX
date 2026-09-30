"""Assemble a separate extension run after all 21 trace-recovery refits pass.

The ``assemble`` command in ``recover_extension_run.py`` is retired: its
identity-verifier import is unavailable in frozen production commit 119476f.
This adapter leaves that active numerical controller byte-pinned and uses the
current, independently pinned verifier against the sealed production root.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts import recover_extension_run as recovery

ANALYSIS_FILES = (
    "scripts/assemble_recovered_extension.py",
    "scripts/recover_extension_run.py",
    "scripts/reproduce_extensions.py",
    "src/data/cohorts.py",
    "src/data/survival_folds.py",
    "src/pipelines/confirmatory/options.py",
    "src/pipelines/extensions/planning.py",
    "src/pipelines/extensions/runner.py",
    "src/pipelines/extensions/verification.py",
    "src/pipelines/robustness/conditions.py",
    "src/utils/reproducibility.py",
)
PROVENANCE_STATUS = "pre_continuation_recovered_extension"


def require_clean_published_adapter(root: Path) -> str:
    """Require the analysis files and adapter to be tracked and unchanged."""
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
    for name in ANALYSIS_FILES:
        subprocess.run(["git", "ls-files", "--error-unmatch", name], cwd=root,
                       capture_output=True, text=True, check=True)
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--", *ANALYSIS_FILES],
                                    cwd=root, text=True)
    if dirty:
        raise ValueError("assembly adapter or identity-verification input is not committed clean")
    return head


def validate_destination(destination: Path, control: Path, source: Path, sealed: Path) -> None:
    """Require a new APFS run root outside every existing producer tree."""
    destination = destination.resolve()
    if destination.exists():
        raise ValueError("recovered destination already exists")
    for root in (control, source, sealed, recovery.REPO):
        root = root.resolve()
        if destination == root or root in destination.parents or destination in root.parents:
            raise ValueError("recovered destination overlaps a controller, producer or code root")
    recovery.require_apfs(destination)
    recovery.require_free_space(destination, gib=15)


def require_production_root(manifest: dict[str, Any], sealed: Path) -> None:
    """Recheck every manifest-bound production input in clean 119476f."""
    recovery.require_sealed_checkout(sealed)
    if manifest["code"]["git_commit"] != recovery.SEALED_COMMIT:
        raise ValueError("extension source was not produced by frozen 119476f")
    if recovery.content_sha256({k: v for k, v in manifest.items() if k != "manifest_content_sha256"}) != manifest["manifest_content_sha256"]:
        raise ValueError("source manifest content hash changed")
    for name, digest in manifest["input_sha256"].items():
        if recovery.sha256_file(sealed / name) != digest:
            raise ValueError(f"frozen production input changed: {name}")


def require_no_active_producer(control: Path, source: Path) -> None:
    """Block assembly while an original or refit owner still holds a claim."""
    for directory in (source / "claims", control / "worker_claims", control / "cell_claims"):
        if list(directory.glob("*.json")):
            raise ValueError(f"active producer claim remains: {directory}")
    if (control / "assembly.claim").exists() or (control / "assembly_adapter.claim").exists():
        raise ValueError("an assembly claim already exists")


def validated_jobs(manifest: dict[str, Any], sealed: Path, matched: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Rebuild all 1,625 jobs and memberships from the sealed data inputs."""
    from src.pipelines.extensions.planning import build_extension_jobs
    from src.pipelines.extensions.runner import load_extension_cohorts
    from src.utils.io import read_mapping
    from src.utils.reproducibility import canonical_json_hash

    config = read_mapping(sealed / "config/extensions.yaml")
    if config != manifest["run_config"]:
        raise ValueError("sealed extension configuration differs from source manifest")
    cohorts = load_extension_cohorts(sealed, matched)
    jobs = build_extension_jobs(cohorts, config)
    rebuilt = [{"cell_id": job.cell_id,
                "train_sha256": canonical_json_hash(cohorts[job.dataset].subject_id.iloc[job.train].tolist()),
                "validation_sha256": canonical_json_hash(cohorts[job.dataset].subject_id.iloc[job.validation].tolist()),
                "censoring_cutoff": job.censoring_cutoff} for job in jobs]
    if len(jobs) != 1625 or rebuilt != manifest["plan"]:
        raise ValueError("independent current verifier's job plan differs from sealed manifest")
    return config, cohorts, {job.cell_id: job for job in jobs}


def require_refit_proof(control: Path, plan: dict[str, Any], identity: str,
                        source_file: Path, refit_file: Path,
                        refit_cell: dict[str, Any]) -> dict[str, Any]:
    """Bind a refit to its actual successful child and official comparison."""
    from scripts.reproduce_extensions import scientific_content
    from src.pipelines.extensions.verification import assert_scientific_equal

    attempt = refit_file.parents[2]
    if attempt != control / "refits" / identity / "attempt_001":
        raise ValueError("refit producer is not the fixed first-attempt run")
    if (attempt / "child_execution.claim").exists():
        raise ValueError(f"unresolved child execution claim remains: {identity}")
    invocation = recovery.read_json(attempt / "invocation.json")
    child_start = recovery.read_json(attempt / "child_start.json")
    child_return = recovery.read_json(attempt / "child_return.json")
    comparison = recovery.read_json(attempt / "scientific_comparison.json")
    token = invocation.get("token")
    owners = [worker for worker, shard in enumerate(plan["shards"]) if identity in shard]
    if len(owners) != 1 or recovery.sha256_file(source_file) != plan["source_cell_file_sha256"][identity]:
        raise ValueError(f"refit differs from its pinned source or fixed shard: {identity}")
    expected_argv = [plan["python"], str((recovery.REPO / "scripts/recover_extension_run.py").resolve()),
                     "child", "--control", str(control), "--cell-id", identity, "--run",
                     str(attempt / "run"), "--token", token]
    if (not isinstance(token, str) or len(token) != 32
            or invocation.get("argv") != expected_argv
            or invocation.get("cwd") != plan["sealed"]
            or invocation.get("plan_sha256") != plan["content_sha256"]
            or invocation.get("worker") != owners[0]
            or child_start.get("cell_id") != identity or not isinstance(child_start.get("pid"), int)
            or child_return.get("cell_id") != identity or child_return.get("return_code") != 0):
        raise ValueError(f"refit lacks exact invocation and zero-return proof: {identity}")
    source_cell = recovery.read_json(source_file)
    expected_refit_traces = {f"{number}/{role}/{trace['filename']}": trace["sha256"]
                             for number, fit in enumerate(refit_cell.get("fit_attempts", []), 1)
                             for role, trace in fit.get("traces", {}).items()}
    if (comparison.get("cell_id") != identity
            or comparison.get("official_non_timing_science") != "match"
            or comparison.get("difference") is not None
            or comparison.get("source_status") != source_cell["status"]
            or comparison.get("refit_status") != refit_cell["status"]
            or comparison.get("source_cell_file_sha256") != recovery.sha256_file(source_file)
            or comparison.get("refit_cell_file_sha256") != recovery.sha256_file(refit_file)
            or comparison.get("source_cell_content_sha256") != source_cell["cell_content_sha256"]
            or comparison.get("refit_cell_content_sha256") != refit_cell["cell_content_sha256"]
            or comparison.get("refit_trace_sha256") != expected_refit_traces):
        raise ValueError(f"refit comparison receipt differs from its scientific files: {identity}")
    assert_scientific_equal(scientific_content(source_cell), scientific_content(refit_cell), identity)
    return {"invocation_sha256": recovery.sha256_file(attempt / "invocation.json"),
            "child_start_sha256": recovery.sha256_file(attempt / "child_start.json"),
            "child_return_sha256": recovery.sha256_file(attempt / "child_return.json"),
            "comparison_sha256": recovery.sha256_file(attempt / "scientific_comparison.json"),
            "child_stdout_sha256": recovery.sha256_file(attempt / "child.stdout.log"),
            "child_stderr_sha256": recovery.sha256_file(attempt / "child.stderr.log"),
            "child_return_code": 0,
            "official_non_timing_science": "match",
            "original_posterior_array_equality": "unavailable: original trace bytes missing"}


def build_inventory(control: Path, destination: Path) -> dict[str, Any]:
    """Audit all producers and return a deterministic assembly payload."""
    plan = recovery.load_plan(control)
    source, matched, sealed = (Path(plan[name]) for name in ("source", "matched", "sealed"))
    validate_destination(destination, control, source, sealed)
    require_no_active_producer(control, source)
    manifest, affected, missing, files = recovery.require_roster(source, matched, trace_hashes=True)
    if (affected != plan["affected_cell_ids"] or missing != plan["absent_cell_ids"]
            or recovery.sha256_file(source / "manifest.json") != plan["source_manifest_sha256"]):
        raise ValueError("original source roster differs from prepared v3 plan")
    require_production_root(manifest, sealed)
    head = require_clean_published_adapter(recovery.REPO)
    if recovery.sha256_file(recovery.REPO / "scripts/reproduce_extensions.py") != recovery.sha256_file(sealed / "scripts/reproduce_extensions.py"):
        raise ValueError("official scientific comparator differs from sealed production code")
    config, cohorts, jobs = validated_jobs(manifest, sealed, matched)
    from src.pipelines.extensions.runner import verified_cell
    from src.pipelines.extensions.verification import verify_cell_identity

    worker_returns: dict[str, str] = {}
    for worker, identities in enumerate(plan["shards"]):
        receipt_path = control / "worker_returns" / f"worker_{worker}.json"
        receipt = recovery.read_json(receipt_path)
        if receipt.get("worker") != worker or receipt.get("status") != "complete" or receipt.get("cell_ids") != identities:
            raise ValueError(f"refit worker {worker} did not complete its exact fixed shard")
        worker_returns[str(worker)] = recovery.sha256_file(receipt_path)
    producers: dict[str, dict[str, Any]] = {}
    affected_set = set(affected)
    for entry in manifest["plan"]:
        identity = entry["cell_id"]
        if identity not in files:
            continue
        refit = identity in affected_set
        producer_run = control / "refits" / identity / "attempt_001/run" if refit else source
        producer_file = producer_run / "cells" / f"{identity}.json"
        cell = verified_cell(producer_file)
        job = jobs[identity]
        verify_cell_identity(cell, job, cohorts[job.dataset], config["base_seed"])
        if cell["status"] not in recovery.TERMINAL_STATUSES:
            raise ValueError(f"unrecognized recovered outcome: {identity}")
        proof = require_refit_proof(control, plan, identity, files[identity], producer_file, cell) if refit else None
        traces = {str(Path("traces") / identity / trace["filename"]): trace["sha256"]
                  for attempt in cell.get("fit_attempts", [])
                  for trace in attempt.get("traces", {}).values()}
        producers[identity] = {"producer": "new_refit" if refit else "intact_original",
                               "producer_run": str(producer_run),
                               "producer_cell_path": str(producer_file),
                               "cell_file_sha256": recovery.sha256_file(producer_file),
                               "original_cell_file_sha256": recovery.sha256_file(files[identity]),
                               "status": cell["status"], "trace_sha256": traces,
                               "proof": proof}
    if len(producers) != 1214 or sum(value["producer"] == "new_refit" for value in producers.values()) != 21:
        raise ValueError("assembled producer map does not cover exactly 1,193 + 21 cells")
    analysis_hashes = {name: recovery.sha256_file(recovery.REPO / name) for name in ANALYSIS_FILES}
    return {"schema_version": 1, "status": PROVENANCE_STATUS,
            "source_manifest_sha256": plan["source_manifest_sha256"],
            "source_run": str(source), "sealed_production_root": str(sealed),
            "sealed_production_commit": recovery.SEALED_COMMIT,
            "matched_sha256": manifest["matched_sha256"],
            "controller_plan_sha256": plan["content_sha256"],
            "controller_sha256": plan["controller_sha256"],
            "adapter_sha256": analysis_hashes["scripts/assemble_recovered_extension.py"],
            "analysis_git_commit": head, "analysis_code_sha256": analysis_hashes,
            "source_forensic_sha256": plan["forensic_sha256"],
            "absent_roster_sha256": plan["absent_roster_sha256"],
            "destination": str(destination), "pending_cell_ids": missing,
            "worker_return_sha256": worker_returns,
            "producer_counts": {"intact_original": 1193, "new_refit": 21, "pending": 411},
            "producers": producers,
            "original_posterior_array_equality": "unavailable for 21 missing-trace source cells"}


def preflight(args: argparse.Namespace) -> None:
    """Seal a complete write-once assembly plan without copying results."""
    control, destination, output = (Path(value).resolve() for value in
                                    (args.control, args.recovered_run, args.assembly_plan))
    if output.exists():
        raise ValueError("assembly plan already exists")
    if output.parent != control:
        raise ValueError("assembly plan must reside in the fixed controller root")
    inventory = build_inventory(control, destination)
    plan = {"created_utc": recovery.utc_now(), "payload": inventory}
    plan["content_sha256"] = recovery.content_sha256(plan)
    recovery.write_new_json(output, plan)
    print(json.dumps({"assembly_plan": str(output), "content_sha256": plan["content_sha256"],
                      "stored": 1214, "pending": 411, "status": "ready_to_assemble"}, sort_keys=True))


def assemble(args: argparse.Namespace) -> None:
    """Copy each verified producer once, then atomically reveal the new run."""
    control, plan_path = Path(args.control).resolve(), Path(args.assembly_plan).resolve()
    if plan_path.parent != control:
        raise ValueError("assembly plan is outside its fixed controller root")
    plan = recovery.read_json(plan_path)
    if recovery.content_sha256({k: v for k, v in plan.items() if k != "content_sha256"}) != plan["content_sha256"]:
        raise ValueError("assembly plan content changed")
    pinned = plan["payload"]
    destination = Path(pinned["destination"])
    current = build_inventory(control, destination)
    if current != pinned:
        raise ValueError("producer inventory changed after assembly preflight")
    staging = destination.with_name(destination.name + ".assembly-pending")
    if staging.exists():
        raise ValueError("prior assembly staging exists; inspect before retry")
    claim_path = control / "assembly_adapter.claim"
    recovery.claim(claim_path, {"adapter_sha256": pinned["adapter_sha256"],
                                "assembly_plan_sha256": plan["content_sha256"],
                                "destination": str(destination)})
    staging.mkdir(parents=True, exist_ok=False)
    source = Path(pinned["source_run"])
    recovery.copy_verified_file(source / "manifest.json", staging / "manifest.json",
                                pinned["source_manifest_sha256"])
    for identity, producer in pinned["producers"].items():
        source_file = Path(producer["producer_cell_path"])
        recovery.copy_verified_file(source_file, staging / "cells" / f"{identity}.json",
                                    producer["cell_file_sha256"])
        producer_run = Path(producer["producer_run"])
        for relative, digest in producer["trace_sha256"].items():
            recovery.copy_verified_file(producer_run / relative, staging / relative, digest)
    lineage = {"schema_version": 1, "status": PROVENANCE_STATUS,
               "assembled_utc": recovery.utc_now(), "assembly_plan_sha256": plan["content_sha256"],
               "assembly_adapter_sha256": pinned["adapter_sha256"], "payload": pinned}
    lineage["content_sha256"] = recovery.content_sha256(lineage)
    recovery.write_new_json(staging / "recovery_lineage.json", lineage)
    if len(list((staging / "cells").glob("*.json"))) != 1214:
        raise ValueError("staged extension run lacks 1,214 saved cells")
    os.rename(staging, destination)
    recovery.write_new_json(control / "assembly_adapter_receipt.json",
                            {"recorded_at_utc": recovery.utc_now(), "destination": str(destination),
                             "assembly_plan_sha256": plan["content_sha256"],
                             "manifest_sha256": recovery.sha256_file(destination / "manifest.json"),
                             "lineage_sha256": recovery.sha256_file(destination / "recovery_lineage.json"),
                             "stored": 1214, "pending": 411})
    claim_path.unlink()
    print(json.dumps({"recovered_run": str(destination), "stored": 1214,
                      "pending": 411, "status": "ready_for_sealed_continuation"}, sort_keys=True))


def inspect(args: argparse.Namespace) -> None:
    """Report fixed target progress without starting work or writing files."""
    control = Path(args.control).resolve()
    plan = recovery.load_plan(control)
    completed = []
    for identity in plan["affected_cell_ids"]:
        attempt = control / "refits" / identity / "attempt_001"
        if (attempt / "scientific_comparison.json").is_file():
            comparison = recovery.read_json(attempt / "scientific_comparison.json")
            if comparison.get("official_non_timing_science") == "match":
                completed.append(identity)
    print(json.dumps({"control": str(control), "complete_comparisons": len(completed),
                      "remaining_refits": 21 - len(completed), "ready_to_preflight": len(completed) == 21},
                     sort_keys=True))


def main() -> None:
    """Expose read-only inspection and separate preflight/assembly phases."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("inspect", help="read-only 21-refit progress")
    p.add_argument("--control", required=True)
    p = commands.add_parser("preflight", help="seal full producer inventory without copying")
    for name in ("control", "recovered-run", "assembly-plan"):
        p.add_argument("--" + name, required=True)
    p = commands.add_parser("assemble", help="copy pinned producers into a new APFS run")
    for name in ("control", "assembly-plan"):
        p.add_argument("--" + name, required=True)
    args = parser.parse_args()
    {"inspect": inspect, "preflight": preflight, "assemble": assemble}[args.command](args)


if __name__ == "__main__":
    main()
