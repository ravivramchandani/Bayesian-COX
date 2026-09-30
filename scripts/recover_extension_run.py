"""Recover trace-incomplete extension cells in a separate, auditable run."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import secrets
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SEALED_COMMIT = "119476fef55b1eeb690527f234c1423440720d45"
TERMINAL_STATUSES = {"complete", "failed", "failed_diagnostics"}
REPO = Path(__file__).resolve().parents[1]
FORENSIC = REPO / "coordination/recovery/2026-09-30-host-interruption-trace-inventory.json"
ABSENT = REPO / "coordination/recovery/2026-09-30-original-extension-absent-roster.json"


def utc_now() -> str:
    """Return a timezone-qualified UTC timestamp for an actual event."""
    return datetime.now(UTC).isoformat()


def sha256_file(path: Path) -> str:
    """Hash an existing file without loading large NetCDF traces into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def content_sha256(value: Any) -> str:
    """Use the frozen project's canonical JSON hash encoding."""
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON mapping, rejecting a partial or wrong-type receipt."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON mapping: {path}")
    return value


def write_new_json(path: Path, value: dict[str, Any]) -> None:
    """Create one immutable receipt, refusing any pre-existing path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def claim(path: Path, value: dict[str, Any]) -> None:
    """Acquire one exclusive producer claim, including its observed process."""
    write_new_json(path, {**value, "pid": os.getpid(), "started_utc": utc_now()})


def require_apfs(path: Path) -> None:
    """Require macOS APFS semantics for write-once claims and assembly."""
    ancestor = path.resolve()
    while not ancestor.exists():
        ancestor = ancestor.parent
    device = subprocess.check_output(["df", "-P", str(ancestor)], text=True).splitlines()[-1].split()[0]
    info = plistlib.loads(subprocess.check_output(["diskutil", "info", "-plist", device]))
    if info.get("FilesystemType", "").lower() != "apfs":
        raise ValueError(f"recovery root must be APFS, not {info.get('FilesystemName')}: {path}")


def require_free_space(path: Path, gib: int = 10) -> None:
    """Stop before a fit or assembly when APFS headroom is too small."""
    ancestor = path.resolve()
    while not ancestor.exists():
        ancestor = ancestor.parent
    if shutil.disk_usage(ancestor).free < gib * 1024 ** 3:
        raise ValueError(f"recovery requires at least {gib} GiB free: {path}")


def require_sealed_checkout(sealed: Path) -> None:
    """Reject changed production code before any recovered fit is dispatched."""
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=sealed, text=True).strip()
    dirty = subprocess.check_output(["git", "status", "--porcelain", "--untracked-files=all"],
                                    cwd=sealed, text=True)
    if commit != SEALED_COMMIT or dirty:
        raise ValueError("frozen production checkout is not clean at 119476f")


def require_environment(python: Path, sealed: Path, receipt: Path) -> None:
    """Bind the actual frozen interpreter to its zero-return verification."""
    record = read_json(receipt)
    verification = record.get("verification", {})
    if (record.get("status") != "verified" or verification.get("return_code") != 0
            or Path(verification.get("cwd", "/")).resolve() != sealed.resolve()
            or not verification.get("command")
            or Path(verification["command"][0]).resolve() != python.resolve()):
        raise ValueError("frozen environment receipt does not bind this interpreter/check-out")
    if not python.is_file():
        raise FileNotFoundError(python)


def require_roster(source: Path, matched: Path, *, trace_hashes: bool) -> tuple[dict[str, Any], list[str], list[str], dict[str, Path]]:
    """Rebuild the disjoint 1,193/21/411 partition from frozen evidence."""
    forensic, absent = read_json(FORENSIC), read_json(ABSENT)
    if content_sha256({k: v for k, v in absent.items() if k != "content_sha256"}) != absent["content_sha256"]:
        raise ValueError("411-cell frozen roster content changed")
    manifest_path = source / "manifest.json"
    manifest = read_json(manifest_path)
    digest = sha256_file(manifest_path)
    if digest != forensic["original_run_manifest_sha256"] or digest != absent["original_run_manifest_sha256"]:
        raise ValueError("source manifest differs from both frozen recovery rosters")
    if manifest["code"]["git_commit"] != SEALED_COMMIT or manifest["code"]["git_dirty"]:
        raise ValueError("source manifest is not the sealed production run")
    if sha256_file(matched) != manifest["matched_sha256"]:
        raise ValueError("matched METABRIC parquet differs from sealed manifest")
    planned = [entry["cell_id"] for entry in manifest["plan"]]
    if len(planned) != 1625 or len(set(planned)) != 1625:
        raise ValueError("invalid extension plan cardinality")
    files = {path.stem: path for path in (source / "cells").glob("*.json")}
    if len(files) != 1214 or not set(files) <= set(planned):
        raise ValueError("original stored-cell roster changed")
    if content_sha256({identity: sha256_file(path) for identity, path in sorted(files.items())}) != absent["source_stored_cell_file_sha256"]:
        raise ValueError("original stored-cell file hashes changed")
    missing = [identity for identity in planned if identity not in files]
    if missing != absent["absent_cell_ids"] or len(missing) != 411 or absent["absent_count"] != 411:
        raise ValueError("411 absent positions differ from frozen manifest-order roster")
    affected = {entry["cell_id"] for entry in forensic["missing_traces"]}
    if len(affected) != 21 or forensic["affected_cell_count"] != 21 or not affected <= set(files):
        raise ValueError("21-cell trace-incomplete roster changed")
    expected_missing = {(entry["cell_id"], entry["attempt"], entry["trace_role"],
                         entry["filename"], entry["expected_sha256"])
                        for entry in forensic["missing_traces"]}
    observed_missing: set[tuple[str, int, str, str, str]] = set()
    for identity, path in files.items():
        cell = read_json(path)
        if cell.get("cell_id") != identity or cell.get("status") not in TERMINAL_STATUSES:
            raise ValueError(f"invalid original cell identity/status: {identity}")
        if content_sha256({k: v for k, v in cell.items() if k != "cell_content_sha256"}) != cell["cell_content_sha256"]:
            raise ValueError(f"changed original cell JSON: {identity}")
        for attempt_no, attempt in enumerate(cell.get("fit_attempts", []), 1):
            for role, trace in attempt.get("traces", {}).items():
                trace_path = source / "traces" / identity / trace["filename"]
                if not trace_path.is_file():
                    observed_missing.add((identity, attempt_no, role, trace["filename"], trace["sha256"]))
                elif trace_hashes and sha256_file(trace_path) != trace["sha256"]:
                    raise ValueError(f"original trace hash changed: {trace_path}")
    if observed_missing != expected_missing or len(observed_missing) != 34 or forensic["missing_trace_count"] != 34:
        raise ValueError("missing posterior trace evidence differs from frozen forensic roster")
    return manifest, [identity for identity in planned if identity in affected], missing, files


def assign_shards(affected: list[str], files: dict[str, Path], workers: int) -> list[list[str]]:
    """Balance the fixed 21 IDs by historical time without selecting outcomes."""
    if not 1 <= workers <= 6:
        raise ValueError("recovery permits one through six workers")
    seconds = {identity: float(read_json(files[identity])["seconds"]) for identity in affected}
    shards: list[list[str]] = [[] for _ in range(workers)]
    totals = [0.0] * workers
    position = {identity: index for index, identity in enumerate(affected)}
    for identity in sorted(affected, key=lambda name: (-seconds[name], position[name])):
        worker = min(range(workers), key=lambda number: (totals[number], number))
        shards[worker].append(identity)
        totals[worker] += seconds[identity]
    for shard in shards:
        shard.sort(key=position.__getitem__)
    return shards


def probe_manifest(python: Path, sealed: Path, matched: Path, output: Path,
                   original: dict[str, Any]) -> None:
    """Build a fresh no-fit manifest and require exact source-manifest equality."""
    code = ("from pathlib import Path\n"
            "from src.pipelines.extensions.runner import initialize_extension_run\n"
            f"initialize_extension_run(Path({str(sealed)!r}), Path({str(matched)!r}), "
            f"Path({str(output)!r}))\n")
    result = subprocess.run([str(python), "-c", code], cwd=sealed, text=True,
                            capture_output=True, check=False)
    write_new_json(output.parent / "manifest_probe_return.json",
                   {"argv": [str(python), "-c", "initialize_extension_run"],
                    "return_code": result.returncode, "stdout": result.stdout,
                    "stderr": result.stderr, "recorded_at_utc": utc_now()})
    if result.returncode != 0 or read_json(output / "manifest.json") != original:
        raise ValueError("fresh no-fit manifest probe differs from original")


def prepare(args: argparse.Namespace) -> None:
    """Seal a no-launch plan after complete source, environment and claim audit."""
    source, matched, sealed, control = (Path(getattr(args, name)).resolve() for name in
                                        ("source", "matched", "sealed", "control"))
    # The frozen manifest records the invoked interpreter's basename. Resolving
    # the conda `python` symlink to `python3.11` changes that scientific binding.
    python = Path(args.python).absolute()
    receipt = Path(args.environment_receipt).resolve()
    for root in (source, sealed):
        if root == control or root in control.parents or control in root.parents:
            raise ValueError("control root overlaps original run or production checkout")
    require_apfs(control)
    require_free_space(control)
    require_sealed_checkout(sealed)
    require_environment(python, sealed, receipt)
    if any((source / "claims").glob("*.json")):
        raise ValueError("original run still has producer claims")
    manifest, affected, missing, files = require_roster(source, matched, trace_hashes=True)
    control.mkdir(parents=True, exist_ok=False)
    probe_manifest(python, sealed, matched, control / "manifest_probe", manifest)
    shards = assign_shards(affected, files, args.workers)
    with (control / "dry_run_claims").open("x", encoding="utf-8") as handle:
        handle.write("21 distinct claims and duplicate exclusions tested\n")
    test_dir = control / "claim_probe"
    test_dir.mkdir()
    for identity in affected:
        marker = test_dir / (identity + ".json")
        claim(marker, {"cell_id": identity, "dry_run": True})
        try:
            claim(marker, {"cell_id": identity, "dry_run": True})
        except FileExistsError:
            pass
        else:
            raise RuntimeError("exclusive claim dry-run failed")
        marker.unlink()
    test_dir.rmdir()
    plan = {"schema_version": 1, "status": "no_launch_prepared", "prepared_utc": utc_now(),
            "source": str(source), "sealed": str(sealed), "matched": str(matched),
            "python": str(python), "environment_receipt": str(receipt),
            "environment_receipt_sha256": sha256_file(receipt),
            "source_manifest_sha256": sha256_file(source / "manifest.json"),
            "forensic_sha256": sha256_file(FORENSIC), "absent_roster_sha256": sha256_file(ABSENT),
            "manifest_probe_sha256": sha256_file(control / "manifest_probe/manifest.json"),
            "controller_sha256": sha256_file(Path(__file__)),
            "affected_cell_ids": affected, "absent_cell_ids": missing,
            "source_cell_file_sha256": {identity: sha256_file(files[identity]) for identity in affected},
            "shards": shards, "workers": args.workers,
            "pilot_cell_id": "metabric_matched__expression__r02f05__bayesian_horseshoe__full",
            "pilot_used_as_recovered_cell": False,
            "recovered_run_started": False}
    plan["content_sha256"] = content_sha256(plan)
    write_new_json(control / "plan.json", plan)
    print(json.dumps({"plan": str(control / "plan.json"), "affected": len(affected),
                      "absent": len(missing), "workers": len(shards),
                      "status": "no_launch_prepared"}, sort_keys=True))


def load_plan(control: Path) -> dict[str, Any]:
    """Verify the sealed no-launch plan and its referenced frozen rosters."""
    plan = read_json(control / "plan.json")
    if content_sha256({k: v for k, v in plan.items() if k != "content_sha256"}) != plan["content_sha256"]:
        raise ValueError("recovery plan content changed")
    if sha256_file(Path(__file__)) != plan["controller_sha256"]:
        raise ValueError("recovery controller changed after the no-launch plan was sealed")
    if (sha256_file(FORENSIC) != plan["forensic_sha256"]
            or sha256_file(ABSENT) != plan["absent_roster_sha256"]
            or sha256_file(Path(plan["environment_receipt"])) != plan["environment_receipt_sha256"]):
        raise ValueError("frozen recovery evidence or environment receipt changed")
    if sorted(identity for shard in plan["shards"] for identity in shard) != sorted(plan["affected_cell_ids"]):
        raise ValueError("recovery shards omit or duplicate a target")
    return plan


def child(args: argparse.Namespace) -> None:
    """Execute exactly one fixed cell with the original sealed fit functions."""
    control = Path(args.control).resolve()
    plan = load_plan(control)
    identity = args.cell_id
    if identity not in plan["affected_cell_ids"]:
        raise ValueError("child cell is not in fixed recovery roster")
    sealed, matched = Path(plan["sealed"]), Path(plan["matched"])
    run = Path(args.run).resolve()
    if run != (control / "refits" / identity / "attempt_001" / "run").resolve():
        raise ValueError("child run path is not the sole planned first attempt")
    if run.exists():
        raise ValueError("child refuses to reuse an existing numerical run directory")
    assigned = [index for index, shard in enumerate(plan["shards"]) if identity in shard]
    if len(assigned) != 1:
        raise ValueError("cell has no unique planned worker")
    worker = assigned[0]
    worker_claim = read_json(control / "worker_claims" / f"worker_{worker}.json")
    cell_claim = read_json(control / "cell_claims" / f"{identity}.json")
    invocation = read_json(run.parent / "invocation.json")
    expected_argv = [plan["python"], str(Path(__file__).resolve()), "child", "--control",
                     str(control), "--cell-id", identity, "--run", str(run), "--token", args.token]
    if (worker_claim["worker"] != worker or worker_claim["plan_sha256"] != plan["content_sha256"]
            or cell_claim["worker"] != worker or cell_claim["cell_id"] != identity
            or worker_claim["pid"] != cell_claim["pid"]
            or cell_claim["token"] != args.token
            or invocation["argv"] != expected_argv or invocation["token"] != args.token
            or invocation["plan_sha256"] != plan["content_sha256"]):
        raise ValueError("child lacks its active exclusive producer/invocation binding")
    os.kill(worker_claim["pid"], 0)
    child_claim = run.parent / "child_execution.claim"
    claim(child_claim, {"cell_id": identity, "worker": worker,
                        "plan_sha256": plan["content_sha256"], "token": args.token})
    completed = False
    try:
        _execute_child_fit(plan, identity, sealed, matched, run)
        completed = True
    finally:
        if completed:
            child_claim.unlink()


def _execute_child_fit(plan: dict[str, Any], identity: str, sealed: Path,
                       matched: Path, run: Path) -> None:
    """Run one target only after the caller has acquired its child claim."""
    require_sealed_checkout(sealed)
    if sha256_file(matched) != read_json(Path(plan["source"]) / "manifest.json")["matched_sha256"]:
        raise ValueError("matched data changed before fit")
    sys.path.insert(0, str(sealed))
    from src.pipelines.extensions.runner import initialize_extension_run, run_extension_cell
    from src.utils.io import read_mapping

    config, jobs, cohorts = initialize_extension_run(sealed, matched, run)
    if read_json(run / "manifest.json") != read_json(Path(plan["source"]) / "manifest.json"):
        raise ValueError("refit manifest differs from exact original")
    selected = [job for job in jobs if job.cell_id == identity]
    if len(selected) != 1:
        raise ValueError("target cell absent or duplicated in sealed plan")
    job = selected[0]
    primary = read_mapping(sealed / "config/confirmatory.yaml")
    datasets = read_mapping(sealed / "config/datasets.yaml")
    key = "metabric" if job.dataset == "metabric_matched" else job.dataset
    cell = run_extension_cell(job, cohorts[job.dataset], datasets[key]["primary_features"],
                              primary, config, run)
    if cell["status"] not in TERMINAL_STATUSES:
        raise ValueError("refit returned an unrecognized outcome status")
    write_new_json(run / "cells" / f"{identity}.json", cell)
    print(json.dumps({"cell_id": identity, "status": cell["status"],
                      "cell_content_sha256": cell["cell_content_sha256"]}, sort_keys=True), flush=True)


def compare_refit(control: Path, plan: dict[str, Any], identity: str, run: Path) -> dict[str, Any]:
    """Compare official non-timing science, retaining failures as outcomes."""
    sealed = Path(plan["sealed"])
    sys.path.insert(0, str(sealed))
    from scripts.reproduce_extensions import scientific_content
    from src.pipelines.extensions.runner import verified_cell
    from src.pipelines.extensions.verification import assert_scientific_equal

    source_path = Path(plan["source"]) / "cells" / f"{identity}.json"
    if sha256_file(source_path) != plan["source_cell_file_sha256"][identity]:
        raise ValueError("original target cell file changed after roster freeze")
    source = read_json(source_path)
    refit = verified_cell(run / "cells" / f"{identity}.json")
    error = None
    try:
        assert_scientific_equal(scientific_content(source), scientific_content(refit), identity)
    except ValueError as exc:
        error = str(exc)
    receipt = {"cell_id": identity, "recorded_at_utc": utc_now(),
               "source_cell_file_sha256": sha256_file(source_path),
               "refit_cell_file_sha256": sha256_file(run / "cells" / f"{identity}.json"),
               "source_status": source["status"], "refit_status": refit["status"],
               "source_cell_content_sha256": source["cell_content_sha256"],
               "refit_cell_content_sha256": refit["cell_content_sha256"],
               "refit_trace_sha256": {f"{index}/{role}/{trace['filename']}": trace["sha256"]
                                      for index, attempt in enumerate(refit.get("fit_attempts", []), 1)
                                      for role, trace in attempt.get("traces", {}).items()},
               "official_non_timing_science": "match" if error is None else "mismatch",
               "difference": error,
               "original_posterior_array_equality": "unavailable: original trace bytes missing"}
    write_new_json(run.parent / "scientific_comparison.json", receipt)
    if error is not None:
        raise ValueError(f"scientific mismatch for {identity}: {error}")
    return receipt


def run_worker(args: argparse.Namespace) -> None:
    """Run only one fixed shard, with typed child returns and exclusive claims."""
    if not args.execute:
        raise ValueError("numerical dispatch requires explicit --execute")
    control = Path(args.control).resolve()
    plan = load_plan(control)
    worker = args.worker
    if not 0 <= worker < plan["workers"]:
        raise ValueError("invalid recovery worker")
    if args.max_new_cells < 0:
        raise ValueError("max-new-cells must be nonnegative")
    require_apfs(control)
    require_free_space(control)
    require_sealed_checkout(Path(plan["sealed"]))
    require_environment(Path(plan["python"]), Path(plan["sealed"]), Path(plan["environment_receipt"]))
    source = Path(plan["source"])
    if any((source / "claims").glob("*.json")):
        raise ValueError("original run acquired an active producer claim")
    if sha256_file(source / "manifest.json") != plan["source_manifest_sha256"]:
        raise ValueError("original manifest changed")
    worker_claim = control / "worker_claims" / f"worker_{worker}.json"
    claim(worker_claim, {"worker": worker, "plan_sha256": plan["content_sha256"]})
    completed: list[str] = []
    new_cells = 0
    try:
        for identity in plan["shards"][worker]:
            attempt = control / "refits" / identity / "attempt_001"
            if attempt.exists():
                receipt = read_json(attempt / "scientific_comparison.json")
                child_return = read_json(attempt / "child_return.json")
                if (receipt["official_non_timing_science"] != "match" or child_return["return_code"] != 0
                        or receipt["refit_cell_file_sha256"] != sha256_file(attempt / "run/cells" / f"{identity}.json")):
                    raise ValueError(f"prior refit comparison failed: {identity}")
                completed.append(identity)
                continue
            require_free_space(control)
            cell_claim = control / "cell_claims" / f"{identity}.json"
            token = secrets.token_hex(16)
            claim(cell_claim, {"cell_id": identity, "worker": worker, "token": token})
            try:
                attempt.mkdir(parents=True, exist_ok=False)
                run = attempt / "run"
                command = [plan["python"], str(Path(__file__).resolve()), "child", "--control",
                           str(control), "--cell-id", identity, "--run", str(run), "--token", token]
                write_new_json(attempt / "invocation.json",
                               {"argv": command, "cwd": plan["sealed"], "started_utc": utc_now(),
                                "plan_sha256": plan["content_sha256"], "worker": worker,
                                "token": token})
                environment = os.environ.copy()
                environment.update({key: "1" for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                               "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")})
                environment["PYTHONNOUSERSITE"] = "1"
                with (attempt / "child.stdout.log").open("x") as stdout, (attempt / "child.stderr.log").open("x") as stderr:
                    process = subprocess.Popen(command, cwd=plan["sealed"], env=environment,
                                               stdout=stdout, stderr=stderr)
                    write_new_json(attempt / "child_start.json",
                                   {"pid": process.pid, "started_utc": utc_now(), "cell_id": identity})
                    result = process.wait()
                write_new_json(attempt / "child_return.json",
                               {"return_code": result, "returned_utc": utc_now(), "cell_id": identity})
                if result != 0:
                    raise RuntimeError(f"sealed refit child returned {result} for {identity}")
                compare_refit(control, plan, identity, run)
                completed.append(identity)
                new_cells += 1
            finally:
                cell_claim.unlink()
            if args.max_new_cells and new_cells >= args.max_new_cells:
                print(json.dumps({"worker": worker, "new_cells": new_cells,
                                  "status": "partial_ramp_stop"}, sort_keys=True))
                return
        write_new_json(control / "worker_returns" / f"worker_{worker}.json",
                       {"worker": worker, "cell_ids": completed, "status": "complete",
                        "returned_utc": utc_now()})
    finally:
        worker_claim.unlink()


def copy_verified_file(source: Path, destination: Path, digest: str) -> None:
    """Copy a producer file into a new lineage and confirm exact bytes."""
    if sha256_file(source) != digest:
        raise ValueError(f"producer file hash changed: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("xb") as target, source.open("rb") as original:
        shutil.copyfileobj(original, target, length=1024 * 1024)
        target.flush()
        os.fsync(target.fileno())
    if sha256_file(destination) != digest:
        raise ValueError(f"copied file hash differs: {destination}")


def assemble(args: argparse.Namespace) -> None:
    """Assemble 1,214 independently verified cells in a distinct run root."""
    control, destination = Path(args.control).resolve(), Path(args.recovered_run).resolve()
    plan = load_plan(control)
    source = Path(plan["source"])
    if destination.exists() or destination == source or source in destination.parents:
        raise ValueError("recovered run must be a new root outside the original")
    forbidden = (control, Path(plan["sealed"]), REPO)
    if any(destination == root or root in destination.parents or destination in root.parents
           for root in forbidden):
        raise ValueError("recovered run must be outside controller, sealed and publishing checkouts")
    require_apfs(destination)
    require_free_space(destination)
    if list((control / "worker_claims").glob("*.json")) or list((control / "cell_claims").glob("*.json")):
        raise ValueError("a recovery producer still has an active claim")
    manifest, affected, missing, files = require_roster(source, Path(plan["matched"]), trace_hashes=True)
    if affected != plan["affected_cell_ids"] or missing != plan["absent_cell_ids"]:
        raise ValueError("source roster differs from prepared plan")
    for worker, identities in enumerate(plan["shards"]):
        receipt = read_json(control / "worker_returns" / f"worker_{worker}.json")
        if receipt["status"] != "complete" or receipt["cell_ids"] != identities:
            raise ValueError("refit worker did not complete its fixed shard")
    sealed = Path(plan["sealed"])
    sys.path.insert(0, str(sealed))
    from scripts.reproduce_extensions import scientific_content
    from src.pipelines.extensions.planning import build_extension_jobs
    from src.pipelines.extensions.runner import load_extension_cohorts, verified_cell
    from src.pipelines.extensions.verification import assert_scientific_equal, verify_cell_identity
    from src.utils.io import read_mapping
    from src.utils.reproducibility import canonical_json_hash

    config = read_mapping(sealed / "config/extensions.yaml")
    cohorts = load_extension_cohorts(sealed, Path(plan["matched"]))
    jobs = build_extension_jobs(cohorts, config)
    indexed_jobs = {job.cell_id: job for job in jobs}
    rebuilt_plan = [{"cell_id": job.cell_id,
                     "train_sha256": canonical_json_hash(cohorts[job.dataset].subject_id.iloc[job.train].tolist()),
                     "validation_sha256": canonical_json_hash(cohorts[job.dataset].subject_id.iloc[job.validation].tolist()),
                     "censoring_cutoff": job.censoring_cutoff} for job in jobs]
    if rebuilt_plan != manifest["plan"]:
        raise ValueError("sealed independent job identities differ from original manifest plan")

    producers: dict[str, dict[str, Any]] = {}
    for identity in affected:
        attempt = control / "refits" / identity / "attempt_001"
        run = attempt / "run"
        comparison = read_json(attempt / "scientific_comparison.json")
        refit = verified_cell(run / "cells" / f"{identity}.json")
        source_cell = read_json(files[identity])
        verify_cell_identity(refit, indexed_jobs[identity], cohorts[indexed_jobs[identity].dataset],
                             config["base_seed"])
        assert_scientific_equal(scientific_content(source_cell), scientific_content(refit), identity)
        if (comparison["official_non_timing_science"] != "match"
                or comparison["refit_cell_file_sha256"] != sha256_file(run / "cells" / f"{identity}.json")):
            raise ValueError(f"refit receipt or scientific record changed: {identity}")
        child_return = read_json(attempt / "child_return.json")
        if child_return["return_code"] != 0 or child_return["cell_id"] != identity:
            raise ValueError(f"refit child has no successful captured return: {identity}")
    claim_path = control / "assembly.claim"
    claim(claim_path, {"destination": str(destination), "plan_sha256": plan["content_sha256"]})
    staging = destination.with_name(destination.name + ".assembly-pending")
    try:
        staging.mkdir(parents=True, exist_ok=False)
        copy_verified_file(source / "manifest.json", staging / "manifest.json",
                           plan["source_manifest_sha256"])
        for identity in (entry["cell_id"] for entry in manifest["plan"] if entry["cell_id"] in files):
            refit = identity in affected
            producer_run = control / "refits" / identity / "attempt_001/run" if refit else source
            producer_cell = producer_run / "cells" / f"{identity}.json"
            cell = verified_cell(producer_cell)
            job = indexed_jobs[identity]
            verify_cell_identity(cell, job, cohorts[job.dataset], config["base_seed"])
            cell_digest = sha256_file(producer_cell)
            copy_verified_file(producer_cell, staging / "cells" / producer_cell.name, cell_digest)
            trace_hashes: dict[str, str] = {}
            for attempt_no, attempt in enumerate(cell.get("fit_attempts", []), 1):
                for role, trace in attempt.get("traces", {}).items():
                    relative = Path("traces") / identity / trace["filename"]
                    copy_verified_file(producer_run / relative, staging / relative, trace["sha256"])
                    trace_hashes[f"{attempt_no}/{role}/{trace['filename']}"] = trace["sha256"]
            comparison_path = control / "refits" / identity / "attempt_001/scientific_comparison.json"
            return_path = control / "refits" / identity / "attempt_001/child_return.json"
            producers[identity] = {"producer": "new_refit" if refit else "intact_original",
                                   "producer_run": str(producer_run),
                                   "producer_cell_path": str(producer_cell),
                                   "cell_file_sha256": cell_digest, "trace_sha256": trace_hashes,
                                   "original_cell_file_sha256": sha256_file(files[identity]),
                                   "scientific_comparison_receipt_sha256": sha256_file(comparison_path) if refit else None,
                                   "child_return_receipt_sha256": sha256_file(return_path) if refit else None,
                                   "reason": "missing_original_trace" if refit else "strictly_verified_original"}
        lineage = {"schema_version": 1, "status": "pre_continuation_recovered_extension",
                   "recorded_at_utc": utc_now(), "source_manifest_sha256": plan["source_manifest_sha256"],
                   "plan_sha256": plan["content_sha256"], "forensic_sha256": plan["forensic_sha256"],
                   "absent_roster_sha256": plan["absent_roster_sha256"],
                   "producer_counts": {"intact_original": 1193, "new_refit": 21, "pending": 411},
                   "original_missing_posterior_arrays": "unavailable for equality comparison",
                   "pending_cell_ids": missing, "producers": producers}
        lineage["content_sha256"] = content_sha256(lineage)
        write_new_json(staging / "recovery_lineage.json", lineage)
        if len(list((staging / "cells").glob("*.json"))) != 1214 or len(producers) != 1214:
            raise ValueError("assembled 1,214-cell producer map is incomplete")
        os.rename(staging, destination)
        write_new_json(control / "assembly_receipt.json",
                       {"recorded_at_utc": utc_now(), "destination": str(destination),
                        "manifest_sha256": sha256_file(destination / "manifest.json"),
                        "lineage_sha256": sha256_file(destination / "recovery_lineage.json"),
                        "producer_counts": lineage["producer_counts"]})
        print(json.dumps({"recovered_run": str(destination), "stored": 1214,
                          "pending": 411, "status": "ready_for_sealed_continuation"}, sort_keys=True))
    finally:
        claim_path.unlink()


def main() -> None:
    """Expose separate dry-run, refit, and assembly stages with no implicit fit."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("prepare", help="audit and seal a no-launch 21+411 plan")
    for name in ("source", "matched", "sealed", "control", "python", "environment-receipt"):
        p.add_argument("--" + name, required=True)
    p.add_argument("--workers", type=int, default=6)
    p = commands.add_parser("run-worker", help="execute one fixed refit shard")
    p.add_argument("--control", required=True)
    p.add_argument("--worker", type=int, required=True)
    p.add_argument("--execute", action="store_true")
    p.add_argument("--max-new-cells", type=int, default=0,
                   help="stop after this many new fits for a monitored ramp; zero runs the shard")
    p = commands.add_parser("child", help=argparse.SUPPRESS)
    for name in ("control", "cell-id", "run", "token"):
        p.add_argument("--" + name, required=True)
    p = commands.add_parser("assemble", help="assemble a new 1,214-cell root after all comparisons pass")
    p.add_argument("--control", required=True)
    p.add_argument("--recovered-run", required=True)
    args = parser.parse_args()
    {"prepare": prepare, "run-worker": run_worker, "child": child, "assemble": assemble}[args.command](args)


if __name__ == "__main__":
    main()
