"""Carry captured recovery proofs with a restored extension run."""

from __future__ import annotations

import hashlib
import json
import re
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
V2_SUPERVISOR_PUBLISHED = "2026-10-01-sequential-recovery-v2-launch.json"
V2_CONTINUATION_PUBLISHED = "2026-10-01-recovered-extension-continuation-v2-launch.json"
V2_INCIDENT_PUBLISHED = "2026-10-01-fourth-refit-postfit-salvage.json"
V2_FIRST_FOUR = frozenset({
    "metabric_matched__expression__r01f03__bayesian_spike_slab__full",
    "metabric_matched__expression__r01f05__bayesian_horseshoe__full",
    "metabric_matched__expression__r01f01__bayesian_horseshoe__full",
    "metabric_matched__expression__r01f01__pv_horseshoe__full",
})
V1_INCIDENT_FILES = {
    "fourth_child_return": "refits/{identity}/attempt_001/child_return.json",
    "fourth_wrapper_return": "captures/worker00_ramp2/return.json",
    "fourth_wrapper_stderr": "captures/worker00_ramp2/worker.stderr.log",
    "v1_supervisor_claim": "sequential_supervisor.claim",
    "v1_supervisor_failure": "captures/sequential-v1/failure.json",
    "v1_successor_claim": "continuation_supervisor.claim",
    "v1_successor_failure": "continuation_captures/sequential-v1/failure.json",
    "v1_post_successor_claim": "post_successor_stage.claim",
    "v1_post_successor_failure": "post_successor_captures/sequential-v1/failure.json",
}
V2_SALVAGE_FILES = ("start.json", "launch.json", "return.json", "proof.json",
                    "complete.json", "stdout.log", "stderr.log")
V2_DISPATCH_FILES = ("launch.json", "return.json", "worker.stdout.log",
                     "worker.stderr.log")


def recovery_version(final: dict[str, Any]) -> str:
    """Select the portable proof contract from the sealed final lineage."""
    version = final.get("supervisor_version", "v1")
    if version not in {"v1", "v2"}:
        raise ValueError("unknown recovered supervisor version")
    if version == "v2" and not isinstance(final.get("v2_source_sha256"), dict):
        raise ValueError("V2 final lineage lacks its source proof map")
    return version


def v2_dispatches(plan: dict[str, Any]) -> list[tuple[str, int, str | None]]:
    """Derive the 17 cell and six terminal captures from the frozen shards."""
    result = []
    number = 0
    for worker, identities in enumerate(plan["shards"]):
        for identity in identities:
            if identity in V2_FIRST_FOUR:
                continue
            number += 1
            result.append((f"{number:02d}_worker{worker}_cell", worker, identity))
        number += 1
        result.append((f"{number:02d}_worker{worker}_final", worker, None))
    if (len(result) != 23 or sum(identity is not None for _, _, identity in result) != 17
            or set(plan["affected_cell_ids"]) & V2_FIRST_FOUR != V2_FIRST_FOUR):
        raise ValueError("V2 dispatch roster differs from four plus seventeen refits")
    return result


def require_v2_capture_tree(control: Path, plan: dict[str, Any]) -> None:
    """Do not silently omit an extra or failed bounded producer capture."""
    root = control / "captures/sequential-v2"
    expected = {"start.json", "complete.json"}
    for folder, _, identity in v2_dispatches(plan):
        expected.update(f"{folder}/{name}" for name in V2_DISPATCH_FILES)
        name = "verified_refit.json" if identity is not None else "verified_worker.json"
        expected.add(f"{folder}/{name}")
    if root.is_symlink() or not root.is_dir():
        raise ValueError("V2 supervisor capture is missing or linked")
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError(f"linked V2 supervisor capture: {path}")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
        elif not path.is_dir():
            raise ValueError(f"unsupported V2 supervisor capture entry: {path}")
    if actual != expected:
        raise ValueError("V2 supervisor capture has missing or extra producer files")


def source_files(control: Path, run: Path, rosters: Path) -> dict[str, Path]:
    """List only the fixed proof files needed by a receiving verifier."""
    plan = read(control / "plan.json")
    source = Path(plan["source"])
    code = rosters.parents[1]
    base = read(run / "recovery_lineage.json")["payload"]
    version = recovery_version(read(run / "recovery_continuation.json"))
    supervisor_capture = control / "captures" / f"sequential-{version}"
    continuation_capture = control / "continuation_captures" / f"sequential-{version}"
    published_name = (V2_SUPERVISOR_PUBLISHED if version == "v2" else
                      "2026-10-01-sequential-recovery-supervisor-launch.json")
    mapping = {
        "control/plan.json": control / "plan.json",
        "control/assembly_plan.json": control / f"assembly_adapter_plan_{version}.json",
        "control/assembly_receipt.json": control / "assembly_adapter_receipt.json",
        "rosters/trace_inventory.json": rosters / FORENSIC_NAME,
        "rosters/absent_roster.json": rosters / ABSENT_NAME,
        "supervisor/launch.json": control / "captures" / f"sequential-{version}.launch.json",
        "supervisor/published_launch.json": (
            code / "coordination/recovery" / published_name),
        "supervisor/start.json": supervisor_capture / "start.json",
        "supervisor/complete.json": supervisor_capture / "complete.json",
        "continuation/start.json": continuation_capture / "start.json",
        "continuation/complete.json": continuation_capture / "complete.json",
    }
    for relative in base["analysis_code_sha256"]:
        mapping[f"code/{relative}"] = code / relative
    for name in ("supervise_extension_recovery.py", "continue_recovered_extension.py"):
        mapping[f"code/scripts/{name}"] = code / "scripts" / name
    for worker in range(6):
        mapping[f"control/worker_returns/worker_{worker}.json"] = (
            control / "worker_returns" / f"worker_{worker}.json")
        capture = continuation_capture / f"worker_{worker}"
        for name in CONTINUATION_FILES:
            mapping[f"continuation/worker_{worker}/{name}"] = capture / name
    for identity in plan["affected_cell_ids"]:
        mapping[f"original_cells/{identity}.json"] = source / "cells" / f"{identity}.json"
        attempt = control / "refits" / identity / "attempt_001"
        for name in REFIT_FILES:
            mapping[f"refits/{identity}/{name}"] = attempt / name
    if version == "v2":
        mapping.update({
            "supervisor/claim_at_launch.json":
                control / "captures/sequential-v2.claim-at-launch.json",
            "continuation/claim_at_launch.json":
                control / "continuation_captures/sequential-v2.claim-at-launch.json",
            "continuation/launch.json":
                control / "continuation_captures/sequential-v2.launch.json",
            "continuation/published_launch.json":
                code / "coordination/recovery" / V2_CONTINUATION_PUBLISHED,
            "incident/record.json": code / "coordination/recovery" / V2_INCIDENT_PUBLISHED,
            "incident/fourth_launch.json": control / "captures/worker00_ramp2/launch.json",
            "incident/fourth_wrapper_start.json":
                control / "captures/worker00_ramp2/wrapper_start.json",
            "incident/fourth_capture.py": control / "captures/worker00_ramp2/capture.py",
            "incident/published_fourth_launch.json":
                code / "coordination/recovery/"
                "2026-10-01-fourth-extension-recovery-launch.json",
        })
        for name, relative in V1_INCIDENT_FILES.items():
            mapping[f"incident/{name}"] = control / relative.format(
                identity="metabric_matched__expression__r01f03__bayesian_spike_slab__full")
        salvage = control / "captures/no-fit-salvage-r01f03-v1"
        for name in V2_SALVAGE_FILES:
            mapping[f"salvage/{name}"] = salvage / name
        for name in ("supervise_extension_recovery_v2.py",
                     "salvage_extension_refit_comparison.py"):
            mapping[f"code/scripts/{name}"] = code / "scripts" / name
        for folder, _, identity in v2_dispatches(plan):
            capture = supervisor_capture / folder
            for name in V2_DISPATCH_FILES:
                mapping[f"supervisor/dispatches/{folder}/{name}"] = capture / name
            verified = "verified_refit.json" if identity is not None else "verified_worker.json"
            mapping[f"supervisor/dispatches/{folder}/{verified}"] = capture / verified
    return mapping


def stage_recovery_bundle(control: Path, run: Path, destination: Path,
                          rosters: Path) -> dict[str, Any]:
    """Copy exact source proofs into a new bundle, then reverify the copy."""
    version = recovery_version(read(run / "recovery_continuation.json"))
    mapping = source_files(control, run, rosters)
    if version == "v2":
        require_v2_capture_tree(control, read(control / "plan.json"))
    if destination.exists() or destination.is_symlink():
        raise FileExistsError(destination)
    destination.mkdir(parents=True, exist_ok=False)
    members = {}
    for relative, source in sorted(mapping.items()):
        expected = digest(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if digest(target) != expected:
            raise ValueError(f"copied recovery proof changed: {relative}")
        members[relative] = expected
    base = {"schema_version": 2 if version == "v2" else 1,
            "status": "captured_recovery_proofs",
            "run_manifest_sha256": digest(run / "manifest.json"),
            "base_lineage_sha256": digest(run / "recovery_lineage.json"),
            "final_lineage_sha256": digest(run / "recovery_continuation.json"),
            "members": members}
    if version == "v2":
        base["supervisor_version"] = "v2"
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
    version = recovery_version(read(run / "recovery_continuation.json"))
    if (canonical_hash({key: value for key, value in inventory.items()
                        if key != "content_sha256"}) != inventory.get("content_sha256")
            or inventory.get("schema_version") != (2 if version == "v2" else 1)
            or inventory.get("supervisor_version") !=
            ("v2" if version == "v2" else None)
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
    expected_members = set(source_files(bundle / "control", run, bundle / "rosters"))
    if set(inventory["members"]) != expected_members:
        raise ValueError("recovery proof bundle member roster differs")
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


def verify_v2_dispatches(run: Path, bundle: Path, plan: dict[str, Any],
                         base: dict[str, Any], start: dict[str, Any],
                         published: dict[str, Any], salvage_sha: str) -> None:
    """Recheck every bounded V2 invocation and its independent result receipt."""
    binding = start["analysis_binding"]
    control = start["control"]
    expected_command = [
        "/usr/bin/caffeinate", "-dimsu", "/usr/bin/nice", "-n", "10",
        plan["python"], "-B",
        str(Path(published["runtime_checkout"]) / "scripts/recover_extension_run.py"),
        "run-worker", "--control", control, "--worker", None,
        "--max-new-cells", "1", "--execute",
    ]
    git_environment = {"GIT_DIR": start["production_git_dir"],
                       "GIT_WORK_TREE": plan["sealed"], "GIT_OPTIONAL_LOCKS": "0"}
    for folder_name, worker, identity in v2_dispatches(plan):
        folder = bundle / "supervisor/dispatches" / folder_name
        launch, returned = read(folder / "launch.json"), read(folder / "return.json")
        command = expected_command.copy()
        command[12] = str(worker)
        if (launch.get("command") != command or launch.get("cwd") != "/private/tmp"
                or launch.get("worker") != worker
                or launch.get("expected_cell") != identity
                or launch.get("owner_pid") != start["owner_pid"]
                or launch.get("plan_sha256") != plan["content_sha256"]
                or launch.get("analysis_binding") != binding
                or launch.get("salvage_proof_sha256") != salvage_sha
                or launch.get("git_environment") != git_environment
                or launch.get("thread_limit") != 1
                or type(returned.get("pid")) is not int or returned["pid"] <= 0
                or returned.get("owner_pid") != start["owner_pid"]
                or returned.get("return_code") != 0):
            raise ValueError(f"V2 bounded dispatch differs: {folder_name}")
        verified_name = "verified_refit.json" if identity is not None else "verified_worker.json"
        verified = read(folder / verified_name)
        if (verified.get("analysis_binding") != binding
                or verified.get("launch_sha256") != digest(folder / "launch.json")
                or verified.get("return_sha256") != digest(folder / "return.json")):
            raise ValueError(f"V2 dispatch verification differs: {folder_name}")
        if identity is None:
            expected = base["worker_return_sha256"][str(worker)]
            if (verified.get("worker") != worker
                    or verified.get("worker_return_sha256") != expected):
                raise ValueError(f"V2 terminal worker differs: {folder_name}")
        else:
            producer = base["producers"][identity]
            cell_path = run / "cells" / f"{identity}.json"
            trace_hashes = {trace["filename"]: trace["sha256"]
                            for fit in read(cell_path).get("fit_attempts", [])
                            for trace in fit.get("traces", {}).values()}
            if (verified.get("cell_id") != identity
                    or verified.get("proof") != {
                        "official_refit_proof": producer["proof"],
                        "cell_file_sha256": digest(cell_path),
                        "trace_sha256": trace_hashes}):
                raise ValueError(f"V2 verified refit differs: {folder_name}")


def verify_v2_source_proofs(run: Path, bundle: Path, plan: dict[str, Any],
                            base: dict[str, Any], final: dict[str, Any]) -> None:
    """Bind the V2 supervisor, old failure, no-fit salvage, and successor."""
    supervisor_start = read(bundle / "supervisor/start.json")
    supervisor_complete = read(bundle / "supervisor/complete.json")
    supervisor_launch = read(bundle / "supervisor/launch.json")
    supervisor_published = read(bundle / "supervisor/published_launch.json")
    successor_start = read(bundle / "continuation/start.json")
    successor_complete = read(bundle / "continuation/complete.json")
    successor_launch = read(bundle / "continuation/launch.json")
    successor_published = read(bundle / "continuation/published_launch.json")
    incident = read(bundle / "incident/record.json")
    salvage = read(bundle / "salvage/proof.json")
    salvage_complete = read(bundle / "salvage/complete.json")
    supervisor_binding = supervisor_start["analysis_binding"]
    successor_binding = successor_start["analysis_binding"]
    if (supervisor_binding.get("analysis_code_sha256") != base["analysis_code_sha256"]
            or successor_binding.get("analysis_code_sha256") != base["analysis_code_sha256"]
            or any(successor_binding.get(key) != supervisor_binding.get(key)
                   for key in ("supervisor_sha256", "v2_supervisor_sha256",
                               "salvage_script_sha256"))):
        raise ValueError("V2 analysis source binding differs across supervisors")
    source_hashes = {
        "supervisor_launch_sha256": digest(bundle / "supervisor/launch.json"),
        "supervisor_start_sha256": digest(bundle / "supervisor/start.json"),
        "supervisor_complete_sha256": digest(bundle / "supervisor/complete.json"),
        "supervisor_published_launch_sha256": digest(bundle / "supervisor/published_launch.json"),
        "supervisor_claim_at_launch_sha256": digest(bundle / "supervisor/claim_at_launch.json"),
        "successor_launch_sha256": digest(bundle / "continuation/launch.json"),
        "successor_published_launch_sha256": digest(bundle / "continuation/published_launch.json"),
        "successor_claim_at_launch_sha256": digest(bundle / "continuation/claim_at_launch.json"),
        "incident_sha256": digest(bundle / "incident/record.json"),
        "salvage_proof_sha256": digest(bundle / "salvage/proof.json"),
        "salvage_complete_sha256": digest(bundle / "salvage/complete.json"),
    }
    if final["v2_source_sha256"] != source_hashes:
        raise ValueError("V2 final source hash map differs from captured proof")
    control = supervisor_start["control"]
    supervisor_capture = str(Path(control) / "captures/sequential-v2")
    successor_capture = str(Path(control) / "continuation_captures/sequential-v2")
    supervisor_command = [
        plan["python"], "-I", "-B",
        str(Path(supervisor_published["runtime_checkout"]) /
            "scripts/supervise_extension_recovery_v2.py"),
        "--control", control, "--capture-root", supervisor_capture,
        "--production-git-dir", supervisor_start["production_git_dir"], "--execute",
    ]
    successor_command = [
        plan["python"], "-I", "-B",
        str(Path(successor_published["runtime_checkout"]) /
            "scripts/continue_recovered_extension.py"),
        "--supervisor-version", "v2", "--control", control,
        "--recovered-run", base["destination"], "--assembly-plan",
        str(Path(control) / "assembly_adapter_plan_v2.json"),
        "--capture-root", successor_capture, "--production-git-dir",
        successor_start["production_git_dir"], "--poll-seconds", "60", "--execute",
    ]
    supervisor_claim = read(bundle / "supervisor/claim_at_launch.json")
    successor_claim = read(bundle / "continuation/claim_at_launch.json")
    if (supervisor_launch.get("argv") != supervisor_command
            or supervisor_launch.get("cwd") != "/private/tmp"
            or supervisor_launch.get("control") != control
            or supervisor_launch.get("capture_root") != supervisor_capture
            or supervisor_launch.get("production_git_dir") !=
            supervisor_start["production_git_dir"]
            or supervisor_launch.get("pid") != supervisor_start["owner_pid"]
            or supervisor_launch.get("plan_file_sha256") != digest(bundle / "control/plan.json")
            or supervisor_launch.get("analysis_git_commit") !=
            supervisor_binding["analysis_git_commit"]
            or supervisor_launch.get("v2_supervisor_sha256") !=
            supervisor_binding["v2_supervisor_sha256"]
            or supervisor_launch.get("salvage_proof_sha256") !=
            source_hashes["salvage_proof_sha256"]
            or supervisor_start.get("stable_worker_cwd") != "/private/tmp"
            or supervisor_start.get("initial_refit_ids") != sorted(V2_FIRST_FOUR)
            or supervisor_start.get("remaining_refits") != 17
            or supervisor_start.get("production_git_dir") !=
            supervisor_published.get("independent_frozen_git_dir")
            or supervisor_complete.get("initial_verified_refits") != 4
            or supervisor_complete.get("new_refits") != 17
            or supervisor_complete.get("salvage_proof_sha256") !=
            source_hashes["salvage_proof_sha256"]
            or supervisor_complete.get("v1_failure_preserved") is not True
            or supervisor_complete.get("worker_return_sha256") != base["worker_return_sha256"]
            or supervisor_claim.get("pid") != supervisor_start["owner_pid"]
            or supervisor_claim.get("plan_sha256") != plan["content_sha256"]
            or supervisor_claim.get("capture_root") != supervisor_capture
            or supervisor_claim.get("analysis_binding") != supervisor_binding
            or supervisor_claim.get("salvage_proof_sha256") !=
            source_hashes["salvage_proof_sha256"]):
        raise ValueError("V2 supervisor launch, claim or completion differs")
    if (supervisor_published.get("schema_version") != 1
            or supervisor_published.get("launch_sha256") != source_hashes["supervisor_launch_sha256"]
            or supervisor_published.get("start_sha256") != source_hashes["supervisor_start_sha256"]
            or supervisor_published.get("v2_claim_sha256") !=
            source_hashes["supervisor_claim_at_launch_sha256"]
            or supervisor_published.get("v2_supervisor_source_sha256") !=
            supervisor_binding["v2_supervisor_sha256"]
            or supervisor_published.get("analysis_git_commit") !=
            supervisor_binding["analysis_git_commit"]
            or supervisor_published.get("control") != control
            or supervisor_published.get("fixed_plan_file_sha256") !=
            digest(bundle / "control/plan.json")
            or supervisor_published.get("fixed_plan_content_sha256") != plan["content_sha256"]
            or supervisor_published.get("supervisor_pid_at_checkpoint") !=
            supervisor_start["owner_pid"]
            or supervisor_published.get("stable_parent_and_worker_cwd") != "/private/tmp"
            or supervisor_published.get("salvage_proof_sha256") !=
            source_hashes["salvage_proof_sha256"]
            or supervisor_published.get("v1_failure_and_claims_preserved") is not True
            or supervisor_published.get("worker0_terminal_return_sha256") !=
            digest(bundle / "supervisor/dispatches/01_worker0_final/return.json")
            or supervisor_published.get("worker0_terminal_verification_sha256") !=
            digest(bundle / "supervisor/dispatches/01_worker0_final/verified_worker.json")
            or supervisor_published.get("worker1_fit_launch_sha256") !=
            digest(bundle / "supervisor/dispatches/02_worker1_cell/launch.json")
            or supervisor_published.get("worker1_cell_id") !=
            read(bundle / "supervisor/dispatches/02_worker1_cell/launch.json")[
                "expected_cell"]):
        raise ValueError("published V2 supervisor checkpoint differs")
    if (successor_launch.get("argv") != successor_command
            or successor_launch.get("cwd") != "/private/tmp"
            or successor_launch.get("control") != control
            or successor_launch.get("capture_root") != successor_capture
            or successor_launch.get("recovered_run") != base["destination"]
            or successor_launch.get("assembly_plan") !=
            str(Path(control) / "assembly_adapter_plan_v2.json")
            or successor_launch.get("production_git_dir") != successor_start["production_git_dir"]
            or successor_launch.get("pid") != successor_start["owner_pid"]
            or successor_launch.get("plan_file_sha256") != digest(bundle / "control/plan.json")
            or successor_launch.get("analysis_git_commit") !=
            successor_binding["analysis_git_commit"]
            or successor_launch.get("successor_sha256") != successor_binding["successor_sha256"]
            or successor_launch.get("supervisor_launch_sha256") !=
            source_hashes["supervisor_launch_sha256"]
            or successor_claim.get("pid") != successor_start["owner_pid"]
            or successor_claim.get("plan_sha256") != plan["content_sha256"]
            or successor_claim.get("capture_root") != successor_capture
            or successor_claim.get("supervisor_version") != "v2"):
        raise ValueError("V2 continuation launch or claim differs")
    if (successor_published.get("schema_version") != 1
            or successor_published.get("successor_launch_sha256") !=
            source_hashes["successor_launch_sha256"]
            or successor_published.get("successor_start_sha256") !=
            digest(bundle / "continuation/start.json")
            or successor_published.get("successor_claim_sha256_at_checkpoint") !=
            source_hashes["successor_claim_at_launch_sha256"]
            or successor_published.get("successor_source_sha256") !=
            successor_binding["successor_sha256"]
            or successor_published.get("analysis_git_commit") !=
            successor_binding["analysis_git_commit"]
            or successor_published.get("supervisor_launch_sha256") !=
            source_hashes["supervisor_launch_sha256"]
            or successor_published.get("supervisor_published_launch_sha256") !=
            source_hashes["supervisor_published_launch_sha256"]
            or successor_published.get("fixed_plan_file_sha256") !=
            digest(bundle / "control/plan.json")
            or successor_published.get("fixed_plan_content_sha256") != plan["content_sha256"]
            or successor_published.get("control") != control
            or successor_published.get("recovered_run") != base["destination"]
            or successor_published.get("assembly_plan") != successor_start["assembly_plan"]
            or successor_published.get("successor_pid_at_checkpoint") !=
            successor_start["owner_pid"]
            or successor_published.get("v1_failed_chain_preserved") is not True
            or successor_start.get("supervisor_version") != "v2"
            or successor_complete.get("supervisor_version") != "v2"
            or successor_binding.get("supervisor_version") != "v2"
            or successor_start.get("supervisor_launch_sha256") !=
            source_hashes["supervisor_launch_sha256"]
            or successor_start.get("supervisor_source_sha256") !=
            supervisor_binding["v2_supervisor_sha256"]
            or successor_start.get("successor_source_sha256") !=
            successor_binding["successor_sha256"]
            or successor_complete.get("supervisor_source_sha256") !=
            supervisor_binding["v2_supervisor_sha256"]
            or successor_complete.get("successor_source_sha256") !=
            successor_binding["successor_sha256"]
            or successor_complete.get("supervisor_launch_sha256") !=
            source_hashes["supervisor_launch_sha256"]
            or successor_complete.get("supervisor_complete_sha256") !=
            source_hashes["supervisor_complete_sha256"]
            or successor_complete.get("salvage_proof_sha256") !=
            source_hashes["salvage_proof_sha256"]
            or successor_complete.get("v1_failure_preserved") is not True):
        raise ValueError("published V2 continuation checkpoint differs")
    verify_v2_salvage(bundle, plan, base, incident, salvage, salvage_complete,
                      supervisor_start, source_hashes)
    verify_v2_dispatches(run, bundle, plan, base, supervisor_start,
                         supervisor_published, source_hashes["salvage_proof_sha256"])


def verify_v2_salvage(bundle: Path, plan: dict[str, Any], base: dict[str, Any],
                      incident: dict[str, Any], salvage: dict[str, Any],
                      complete: dict[str, Any], supervisor_start: dict[str, Any],
                      source_hashes: dict[str, str]) -> None:
    """Keep the failed V1 return and separate zero-fit comparison auditable."""
    identity = "metabric_matched__expression__r01f03__bayesian_spike_slab__full"
    old_hashes = {name: digest(bundle / "incident" / name) for name in V1_INCIDENT_FILES}
    fourth = base["producers"][identity]
    old_failure = {name: digest(bundle / "incident" / filename) for name, filename in (
        ("capture.py", "fourth_capture.py"), ("launch.json", "fourth_launch.json"),
        ("wrapper_start.json", "fourth_wrapper_start.json"),
        ("return.json", "fourth_wrapper_return"),
        ("worker.stderr.log", "fourth_wrapper_stderr"),
        ("published_launch", "published_fourth_launch.json"),
        ("v1_supervisor_claim", "v1_supervisor_claim"),
        ("v1_supervisor_failure", "v1_supervisor_failure"))}
    saved_child = salvage.get("saved_child_sha256", {})
    if (incident.get("schema_version") != 1 or incident.get("control") !=
            supervisor_start["control"]
            or incident.get("plan_file_sha256") != digest(bundle / "control/plan.json")
            or incident.get("plan_content_sha256") != plan["content_sha256"]
            or incident.get("failed_v1_evidence_sha256") != old_hashes
            or incident.get("separate_salvage", {}).get("proof_sha256") !=
            source_hashes["salvage_proof_sha256"]
            or incident.get("separate_salvage", {}).get("complete_sha256") !=
            source_hashes["salvage_complete_sha256"]
            or incident.get("separate_salvage", {}).get("new_fits_executed") != 0
            or incident.get("separate_salvage", {}).get("old_wrapper_return_remains") != 1
            or complete.get("proof_sha256") != source_hashes["salvage_proof_sha256"]
            or complete.get("plan_content_sha256") != plan["content_sha256"]
            or complete.get("new_fits_executed") != 0
            or salvage.get("content_sha256") != canonical_hash({
                key: value for key, value in salvage.items() if key != "content_sha256"})
            or salvage.get("status") != "fourth_refit_postfit_comparison_salvaged"
            or salvage.get("cell_id") != identity
            or salvage.get("plan_file_sha256") != digest(bundle / "control/plan.json")
            or salvage.get("plan_content_sha256") != plan["content_sha256"]
            or salvage.get("old_wrapper_return_code") != 1
            or salvage.get("saved_fit_child_return_code") != 0
            or salvage.get("new_comparison_child_return_code") != 0
            or salvage.get("new_fits_executed") != 0
            or salvage.get("old_failure_preserved") is not True
            or salvage.get("official_refit_proof") != fourth["proof"]
            or salvage.get("scientific_comparison_sha256") !=
            fourth["proof"]["comparison_sha256"]
            or salvage.get("old_failed_capture_sha256") != old_failure
            or supervisor_start.get("salvage_evidence", {}).get(
                "salvage_proof_sha256") != source_hashes["salvage_proof_sha256"]
            or supervisor_start["salvage_evidence"].get("old_failed_capture_sha256") !=
            old_failure
            or supervisor_start["salvage_evidence"].get("fourth_refit", {}).get(
                "official_refit_proof") != fourth["proof"]
            or saved_child.get("cell") != fourth["cell_file_sha256"]
            or saved_child.get("source_cell") != fourth["original_cell_file_sha256"]
            or saved_child.get("child_return.json") != old_hashes["fourth_child_return"]):
        raise ValueError("V1 failure or no-fit salvage proof differs")
    for name, key in (("launch.json", "launch_sha256"), ("return.json", "return_sha256"),
                      ("stdout.log", "stdout_sha256"), ("stderr.log", "stderr_sha256")):
        if salvage.get(key) != digest(bundle / "salvage" / name):
            raise ValueError(f"no-fit salvage captured {name} differs")
    old_return = read(bundle / "incident/fourth_wrapper_return")
    child_return = read(bundle / "incident/fourth_child_return")
    old_claim = read(bundle / "incident/v1_supervisor_claim")
    old_failure_receipt = read(bundle / "incident/v1_supervisor_failure")
    salvage_start = read(bundle / "salvage/start.json")
    salvage_launch = read(bundle / "salvage/launch.json")
    salvage_return = read(bundle / "salvage/return.json")
    command = salvage_launch.get("command")
    token = command[10] if isinstance(command, list) and len(command) == 11 else None
    script = Path(command[3]) if isinstance(command, list) and len(command) == 11 else None
    expected_command = ([plan["python"], "-I", "-B", str(script), "compare-child",
                         "--control", supervisor_start["control"], "--capture-root",
                         str(Path(supervisor_start["control"]) /
                             "captures/no-fit-salvage-r01f03-v1"), "--token", token]
                        if script is not None else None)
    if (old_return.get("return_code") != 1 or child_return.get("return_code") != 0
            or old_claim.get("plan_sha256") != plan["content_sha256"]
            or old_failure_receipt.get("supervisor_claim_retained") is not True
            or script is None or not script.is_absolute()
            or script.name != "salvage_extension_refit_comparison.py"
            or not isinstance(token, str) or re.fullmatch(r"[0-9a-f]{32}", token) is None
            or command != expected_command
            or salvage_start.get("identity") != identity
            or salvage_start.get("no_fit_comparison_only") is not True
            or salvage_start.get("stable_cwd") != "/private/tmp"
            or salvage_start.get("plan_content_sha256") != plan["content_sha256"]
            or salvage_start.get("plan_file_sha256") !=
            digest(bundle / "control/plan.json")
            or salvage_start.get("prior", {}).get("old_failed_capture_sha256") != old_failure
            or salvage_start.get("prior", {}).get("completed_child_sha256") != saved_child
            or salvage_launch.get("script_sha256") !=
            digest(bundle / "code/scripts/salvage_extension_refit_comparison.py")
            or salvage_launch.get("cwd") != "/private/tmp"
            or salvage_launch.get("owner_pid") != salvage_start.get("owner_pid")
            or salvage_return.get("owner_pid") != salvage_start.get("owner_pid")
            or salvage_return.get("return_code") != 0):
        raise ValueError("preserved V1 and no-fit child return differs")


def verify_recovery_bundle(run: Path, bundle: Path,
                           rosters: Path | None = None) -> dict[str, Any]:
    """Recheck captured returns and source/refit comparisons after relocation."""
    lineage = verify_recovered_lineage(run)
    inventory = require_bundle_inventory(run, bundle)
    base = read(run / "recovery_lineage.json")["payload"]
    final = read(run / "recovery_continuation.json")
    version = recovery_version(final)
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
    supervisor_launch = read(bundle / "supervisor/launch.json")
    published_launch = read(bundle / "supervisor/published_launch.json")
    code_hashes = dict(base["analysis_code_sha256"])
    code_hashes.update({
        "scripts/supervise_extension_recovery.py":
            supervisor_start["analysis_binding"]["supervisor_sha256"],
        "scripts/continue_recovered_extension.py":
            final["continuation_analysis_binding"]["successor_sha256"],
    })
    if version == "v2":
        code_hashes.update({
            "scripts/supervise_extension_recovery_v2.py":
                supervisor_start["analysis_binding"]["v2_supervisor_sha256"],
            "scripts/salvage_extension_refit_comparison.py":
                supervisor_start["analysis_binding"]["salvage_script_sha256"],
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
    if version == "v1":
        expected_supervisor_argv = [
            plan["python"], "-B",
            str(Path(supervisor_launch["cwd"]) / "scripts/supervise_extension_recovery.py"),
            "--control", supervisor_start["control"],
            "--capture-root", str(Path(supervisor_start["control"]) / "captures/sequential-v1"),
            "--production-git-dir", supervisor_start["production_git_dir"],
            "--wait-capture", supervisor_start["wait_capture"], "--execute",
        ]
        if (supervisor_launch.get("pid") != supervisor_start["owner_pid"]
                or supervisor_launch.get("analysis_git_commit") !=
                supervisor_start["analysis_binding"]["analysis_git_commit"]
                or supervisor_launch.get("supervisor_sha256") !=
                supervisor_start["analysis_binding"]["supervisor_sha256"]
                or supervisor_launch.get("plan_file_sha256") != digest(bundle / "control/plan.json")
                or supervisor_launch.get("prior_capture") != supervisor_start["wait_capture"]
                or supervisor_launch.get("argv") != expected_supervisor_argv
                or published_launch.get("supervisor_launch_sha256") !=
                digest(bundle / "supervisor/launch.json")
                or published_launch.get("supervisor_start_sha256") !=
                digest(bundle / "supervisor/start.json")
                or published_launch.get("fixed_plan_file_sha256") != digest(bundle / "control/plan.json")
                or published_launch.get("fixed_plan_content_sha256") != plan["content_sha256"]
                or published_launch.get("supervisor_pid_at_checkpoint") != supervisor_start["owner_pid"]
                or published_launch.get("supervisor_source_sha256") !=
                supervisor_start["analysis_binding"]["supervisor_sha256"]
                or published_launch.get("supervisor_analysis_commit") !=
                supervisor_start["analysis_binding"]["analysis_git_commit"]
                or published_launch.get("supervisor_runtime_checkout") != supervisor_launch["cwd"]
                or published_launch.get("prior_worker_capture") != supervisor_start["wait_capture"]
                or published_launch.get("control") != supervisor_start["control"]):
            raise ValueError("captured supervisor launch or published attestation differs")
    else:
        verify_v2_source_proofs(run, bundle, plan, base, final)
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
            str(Path(supervisor_start["control"]) / f"assembly_adapter_plan_{version}.json")
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
                or launch.get("cwd") != ("/private/tmp" if version == "v2"
                                         else plan["sealed"])
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
    inventory = read(bundle / "inventory.json")
    if canonical_hash({key: value for key, value in inventory.items()
                       if key != "content_sha256"}) != inventory.get("content_sha256"):
        raise ValueError("recovery code archive inventory differs")
    if inventory.get("schema_version") == 2 and inventory.get("supervisor_version") == "v2":
        version = "v2"
    elif inventory.get("schema_version") == 1 and "supervisor_version" not in inventory:
        version = "v1"
    else:
        raise ValueError("recovery code archive version differs")
    if (bundle / "supervisor/claim_at_launch.json").is_file() != (version == "v2"):
        raise ValueError("recovery code archive claim roster differs")
    if version == "v2":
        required.update({
            f"coordination/recovery/{V2_SUPERVISOR_PUBLISHED}":
                bundle / "supervisor/published_launch.json",
            f"coordination/recovery/{V2_CONTINUATION_PUBLISHED}":
                bundle / "continuation/published_launch.json",
            f"coordination/recovery/{V2_INCIDENT_PUBLISHED}":
                bundle / "incident/record.json",
            "coordination/recovery/2026-10-01-fourth-extension-recovery-launch.json":
                bundle / "incident/published_fourth_launch.json",
            "coordination/recovery/2026-10-01-v2-supervisor-claim-at-launch.json":
                bundle / "supervisor/claim_at_launch.json",
            "coordination/recovery/2026-10-01-v2-continuation-claim-at-launch.json":
                bundle / "continuation/claim_at_launch.json",
        })
    else:
        required["coordination/recovery/2026-10-01-sequential-recovery-supervisor-launch.json"] = (
            bundle / "supervisor/published_launch.json")
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
