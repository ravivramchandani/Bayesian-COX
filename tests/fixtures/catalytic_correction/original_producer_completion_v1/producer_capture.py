"""Narrow stdlib process capture for a later root-selected original refit.

Importing this module cannot import science or launch a process. This adapter
does not issue scientific lineage, original owner or numerical-resolution
reviews. Its default execution route is the unchanged original119 script.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

IO_SHA = "389c09c0b4f151adf754d20b3c21b2cdd0fa6809bcc4cd78dda470739d2ea3b8"
_io_path = Path(__file__).absolute().with_name("verification_io.py")
if hashlib.sha256(_io_path.read_bytes()).hexdigest() != IO_SHA:
    raise RuntimeError("unchanged atomic IO source differs")
_spec = importlib.util.spec_from_file_location("_original_capture_io", _io_path)
if _spec is None or _spec.loader is None:
    raise RuntimeError("atomic IO loader unavailable")
io = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(io)

NUMERIC = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
OWN = ("producer_capture.py", "capture_original_producer.py", "verification_io.py")
SCOPE_RULE = "sorted_unique(original_plan_repeat1_fold1_92_union_frozen_full_budget_pilots)"


@dataclass(frozen=True)
class Policy:
    """Immutable production constants; fictional overrides are test-only."""

    commit: str = "119476fef55b1eeb690527f234c1423440720d45"
    manifest_sha: str = "83b9049fb6aaaadab576b34de0741e4f510344dcefba9f96198d15b5ab4f49b9"
    manifest_content_sha: str = "4577c615486ee871d508837aa812f59539b59338c63834716453a8b03ea394a3"
    official_script_sha: str = "1c16387ecf8cafb01488840229f51f727dbe741614c9c91996c98a1a53781428"


def binding(path: Path) -> dict[str, Any]:
    """Bind regular bytes without interpreting an array or trace container."""
    return {"sha256": io.sha(path), "bytes": path.stat().st_size}


def raw_json(path: Path, expected: str, pins: Any) -> dict[str, Any]:
    """Read finite raw legacy JSON, preserving the separate byte binding."""
    pins.bind(path, expected)
    def nonfinite(value: str) -> None:
        raise io.VerificationFailure("nonfinite JSON " + value)
    value = json.loads(path.read_text(encoding="utf-8"), parse_constant=nonfinite)
    io.require(isinstance(value, dict), "JSON mapping required")
    pins.bind(path, expected)
    return value


def bound_record(item: dict[str, Any], pins: Any, *, raw: bool = False,
                 field: str = "content_sha256") -> tuple[Path, dict[str, Any]]:
    """A supplied binding is checked against bytes, not accepted on trust."""
    io.require(set(item) == {"path", "sha256"}, "explicit path/byte SHA carrier required")
    path = io.safe(Path(item["path"]))
    value = raw_json(path, item["sha256"], pins) if raw else pins.json(path, item["sha256"], field=field)
    return path, value


def no_overlap(path: Path, roots: list[Path]) -> None:
    """Protect both immutable evidence and new-stage paths before creation."""
    io.safe(path)
    for root in roots:
        io.safe(root)
        io.require(not path.is_relative_to(root) and not root.is_relative_to(path), "output overlaps evidence or another stage")


def runtime(python: Path, environment: dict[str, str]) -> dict[str, Any]:
    """Allow only the actual interpreter alias; reject other linked roles."""
    io.require(python.is_absolute() and python.is_file() and python.samefile(Path(sys.executable)),
               "requested Python must be the current locked interpreter")
    actual = io.safe(python.resolve(strict=True))
    observed = {name: environment.get(name) for name in NUMERIC}
    io.require(observed == dict.fromkeys(NUMERIC, "1"), "all five numeric variables must already equal1")
    return {"requested_python": str(python), "python_executable": str(actual),
            "observed_executable": sys.executable, "locked_interpreter_samefile": True,
            "numeric_thread_environment": observed}


def original_selected(plan: list[dict[str, Any]]) -> list[str]:
    """Preserve original plan order for the official script's shard index."""
    io.require(isinstance(plan, list) and len(plan) == 1625, "original full1625 plan required")
    identities = [row["cell_id"] for row in plan]
    io.require(len(set(identities)) == len(identities), "duplicate original identities")
    selected = []
    for identity in identities:
        match = re.fullmatch(r"[a-z0-9_.]+__[a-z0-9_.]+__r(\d{2})f(\d{2})__[a-z0-9_.]+__[a-z0-9_.]+", identity)
        io.require(match is not None, "original identity grammar differs")
        if tuple(map(int, match.groups())) == (1, 1):
            selected.append(identity)
    io.require(len(selected) == 92, "fixed original92 selection differs")
    return selected


def git_state(source: Path, commit: str, invoke: Any) -> dict[str, Any]:
    """Require the actual clean original checkout before and after dispatch."""
    executable = shutil.which("git")
    io.require(executable is not None, "Git required")
    observed = {}
    for label, options in (("commit", ["rev-parse", "HEAD"]), ("porcelain", ["status", "--porcelain"])):
        argv = [executable, *options]
        result = invoke(argv, cwd=source, capture_output=True, text=True, check=False)
        io.require(type(result.returncode) is int and result.returncode == 0, "actual Git verification failed")
        observed[label] = result.stdout.strip() if label == "commit" else result.stdout
    io.require(observed == {"commit": commit, "porcelain": ""}, "source must remain clean original119")
    return observed


def run_captured(argv: list[str], cwd: Path, output: Path, name: str,
                 environment: dict[str, str], invoke: Any, *, test_only: bool,
                 operation: str, pins: Any) -> dict[str, Any]:
    """Capture genuine bytes/rc with bounded RAM; keep nonzero/launch errors."""
    stdout, stderr = output / (name + ".stdout.txt"), output / (name + ".stderr.log")
    started, clock = datetime.now(UTC).isoformat(), time.monotonic()
    code, error = None, None
    # Exclusive raw files are intentionally retained if killed mid-execution.
    # Only finished, fsynced, closed logs may be bound by a final record.
    with stdout.open("xb") as out, stderr.open("xb") as err:
        try:
            result = invoke(argv, cwd=cwd, stdout=out, stderr=err, env=environment, check=False)
            code = result.returncode
        except OSError as failure:
            error = {"type": type(failure).__name__, "message": str(failure)}
        finally:
            for stream in (out, err):
                stream.flush()
                os.fsync(stream.fileno())
    attempt = io.seal({"status": "actual_process_attempt_recorded" if not test_only else "synthetic_process_attempt_recorded",
        "operation": operation, "argv": argv, "cwd": str(cwd), "script_index": 3,
        "entrypoint": {"path": argv[3], "binding": binding(Path(argv[3]))},
        "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(),
        "wall_seconds": time.monotonic() - clock, "exit_code": code, "launch_error": error,
        "numeric_thread_environment": {key: environment.get(key) for key in NUMERIC},
        "stdout": {"path": str(stdout), "binding": binding(stdout)},
        "stderr": {"path": str(stderr), "binding": binding(stderr)},
        "test_only_dependency_injection": test_only})
    path = output / (name + ".attempt.json")
    io.write_new(path, attempt)
    pins.bind(path, io.sha(path))
    pins.bind(stdout, io.sha(stdout))
    pins.bind(stderr, io.sha(stderr))
    io.require(type(code) is int and code == 0 and error is None, "actual child failed; retained raw logs/rc without completion proof")
    return attempt


def output_inventory(root: Path, identity: str, pins: Any) -> dict[str, Any]:
    """Bind one actual cell/receipt and all retained trace files, without parsing traces."""
    artifacts, directories = {}, []
    for path in sorted(root.rglob("*")):
        io.safe(path)
        name = str(path.relative_to(root))
        if path.is_dir():
            io.require(name in {"cells", "receipts", "traces", "traces/" + identity}, "unexpected output directory")
            directories.append(name)
        elif path.is_file():
            io.require(name in {f"cells/{identity}.json", f"receipts/{identity}.json"}
                       or (path.parent == root / "traces" / identity and path.name.endswith(".nc")
                           and not path.name.startswith(".")), "unexpected/partial output file")
            artifacts[name] = binding(path)
            pins.bind(path, artifacts[name]["sha256"], size=artifacts[name]["bytes"])
        else:
            io.require(False, "unrecognized output node")
    io.require({f"cells/{identity}.json", f"receipts/{identity}.json"} <= set(artifacts), "official cell/receipt absent")
    return {"artifacts": artifacts, "directories": directories,
            "trace_containers_parsed_by_adapter": False}


def capture(request_path: Path, request_sha: str, python: Path, preparation: dict[str, Any],
            *, dependencies: dict[str, Any] | None = None, test_only: bool = False) -> dict[str, Any]:
    """Dispatch only a root-selected official original shard, never a broad rerun.

    Fictional dependency injection is rejected in the production API and cannot
    be requested by the CLI. Injection writes only synthetic statuses.
    """
    dependencies = {} if dependencies is None else dependencies
    io.require(not dependencies or test_only, "dependency injection requires explicit fictional test mode")
    invoke = dependencies.get("invoke", subprocess.run)
    policy = dependencies.get("policy", Policy())
    io.require(test_only or invoke is subprocess.run, "genuine default subprocess required")
    environment = dict(dependencies.get("environment", os.environ))
    observed_runtime = runtime(python, environment)
    python = Path(observed_runtime["python_executable"])
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    pins = io.Pins()
    request_path = io.safe(request_path)
    request = pins.json(request_path, request_sha)
    io.require(request["schema_version"] == 1 and request["status"] == "root_selected_original_producer_completion_request"
               and request["test_only"] is False and request["route"] == "official_fresh_refit",
               "explicit original official route required")
    source, original_run = (io.safe(Path(request[name])) for name in ("source", "original_run"))
    io.require(source.is_dir() and original_run.is_dir(), "source/original run missing")
    manifest_path = original_run / "manifest.json"
    original = pins.json(manifest_path, policy.manifest_sha, field="manifest_content_sha256")
    io.require(original["manifest_content_sha256"] == policy.manifest_content_sha
               and original["code"]["git_commit"] == policy.commit and original["code"]["git_dirty"] is False,
               "exact original manifest/source identity required")
    selected = original_selected(original["plan"])
    selection_path, selection = bound_record(request["selected_reproduction_selection"], pins)
    io.require(selection["status"] == "reviewed_corrected_reproduction_selection" and selection["schema_version"] == 1
               and selection["original_manifest_sha256"] == policy.manifest_sha and selection["scope_rule"] == SCOPE_RULE
               and selection["original_selected_cells"] == sorted(selected)
               and selection["selected_cells"] == sorted(set(selected) | set(selection["pilot_cells"])),
               "actual prospective ADR041 selected union required")
    choice_path, choice = bound_record(request["root_missing_producer_choice"], pins)
    chosen = choice["selected_missing_producer_cell_ids"]
    io.require(choice["status"] == "root_selected_missing_original_producer_proofs"
               and choice["selection_sha256"] == request["selected_reproduction_selection"]["sha256"]
               and choice["original_manifest_sha256"] == policy.manifest_sha
               and choice["reason"] == "existing_actual_numerical_producer_proof_genuinely_unavailable"
               and choice["source_score_selection"] is False and choice["automatic_all92_rerun"] is False
               and isinstance(chosen, list) and chosen == sorted(set(chosen)) and chosen
               and set(chosen) <= set(selected), "root-selected missing original proof list required")
    identity = request["original_cell_id"]
    io.require(identity in chosen and identity in selection["selected_cells"], "identity not root-selected original92 missing proof")
    worker = selected.index(identity)
    io.require(request["workers"] == 92 and type(request["workers"]) is int
               and type(request["worker"]) is int and request["worker"] == worker,
               "official fixed92 plan-order shard differs")
    source_cell = original_run / "cells" / (identity + ".json")
    source_value = pins.json(source_cell, io.sha(source_cell), field="cell_content_sha256")
    io.require(source_value["cell_id"] == identity and source_value["status"] in {"complete", "failed", "failed_diagnostics"},
               "original terminal source cell required")
    io.require(not io.safe(original_run / "claims" / (identity + ".json")).exists(), "original source owner still active")
    for name, expected in original["input_sha256"].items():
        pins.bind(io.child(source, name), expected)
    script = source / "scripts/reproduce_extensions.py"
    io.require(original["input_sha256"]["scripts/reproduce_extensions.py"] == policy.official_script_sha,
               "unchanged119 official reproduction script required")
    matched = io.safe(Path(request["matched"]))
    pins.bind(matched, original["matched_sha256"])
    environment_path, expected_environment = bound_record(request["expected_environment_report"], pins, raw=True)
    io.require(expected_environment["status"] == "ok" and type(expected_environment["package_count"]) is int
               and expected_environment["package_count"] == 259
               and expected_environment["lock_sha256"] == original["input_sha256"]["conda-lock.yml"]
               and expected_environment["python"] == "3.11.15", "bound exact full259 locked report required")
    hash_file = source / "conda-lock.yml.sha256"
    pins.bind(hash_file, request["lock_hash_file_sha256"])
    hash_parts = hash_file.read_text().strip().split()
    io.require(hash_parts == [original["input_sha256"]["conda-lock.yml"], "conda-lock.yml"], "lock hash-file contents differ")
    own = Path(__file__).absolute().parent
    io.require(set(preparation["implementation_source_sha256"]) == set(OWN), "capture implementation pin surface differs")
    for name, expected in preparation["implementation_source_sha256"].items():
        pins.bind(own / name, expected)
    output, capture_root = (io.safe(Path(request[name])) for name in ("reproduction_output", "capture_output"))
    io.require(selection["paths"]["original_reproduction"] == str(output),
               "v1 fixed original_reproduction must be the actual fresh invocation output; copying cannot preserve this proof")
    immutable = [source, original_run, matched, request_path, selection_path, choice_path, environment_path, own]
    for path, other in ((output, capture_root), (capture_root, output)):
        no_overlap(path, [*immutable, other])
        io.require(path.parent.is_dir() and not path.exists(), "fresh absent output with existing parent required; no resume")
    before_git = git_state(source, policy.commit, invoke)
    pins.recheck()
    # Reserve only after all read-only prerequisite checks. Never delete a failed
    # or partial owned output. A second capture must use new root-reviewed paths.
    capture_root.mkdir(exist_ok=False)
    output.mkdir(exist_ok=False)
    io.write_new(capture_root / "owner_started.json", io.seal({"status": "original_producer_capture_owner_started",
        "pid": os.getpid(), "host": socket.gethostname(), "original_cell_id": identity,
        "request_sha256": request_sha, "runtime": observed_runtime, "source_before": before_git,
        "fresh_output_exclusively_created": True, "started_at_utc": datetime.now(UTC).isoformat(),
        "test_only_dependency_injection": test_only}))
    checker = source / "scripts/verify_environment.py"
    checker_argv = [str(python), "-I", "-B", str(checker), "--lock-file", str(source / "conda-lock.yml"),
                    "--hash-file", str(hash_file)]
    run_captured(checker_argv, source, capture_root, "environment", environment, invoke,
                 test_only=test_only, operation="fresh_original_full259_environment_check", pins=pins)
    actual_environment = raw_json(capture_root / "environment.stdout.txt", io.sha(capture_root / "environment.stdout.txt"), pins)
    io.require(actual_environment == expected_environment, "fresh full259 report differs; no numerical child launched")
    io.require(not any(output.iterdir()), "reserved output no longer empty; numerical refit refused")
    pins.recheck()
    io.require(not (original_run / "claims" / (identity + ".json")).exists(), "original source owner became active")
    argv = [str(python), "-I", "-B", str(script), "--source", str(original_run), "--output", str(output),
            "--matched", str(matched), "--workers", "92", "--worker", str(worker)]
    numerical_attempt = run_captured(argv, source, capture_root, "numerical", environment, invoke,
        test_only=test_only, operation="unchanged119_original_official_fresh_refit_and_comparison", pins=pins)
    stdout = (capture_root / "numerical.stdout.txt").read_text(encoding="utf-8")
    events = [line for line in stdout.splitlines() if line.endswith(" scientific_match")]
    io.require(events == [identity + " scientific_match"], "actual official stdout selected completion differs")
    refit_path = output / "cells" / (identity + ".json")
    refit = pins.json(refit_path, io.sha(refit_path), field="cell_content_sha256")
    io.require(refit["cell_id"] == identity and refit["status"] in {"complete", "failed", "failed_diagnostics"},
               "original refit terminal identity/status differs")
    official_path = output / "receipts" / (identity + ".json")
    official = raw_json(official_path, io.sha(official_path), pins)
    io.require(official == {"cell_id": identity, "status": "scientific_match",
        "source_content_sha256": source_value["cell_content_sha256"], "refit_content_sha256": refit["cell_content_sha256"],
        "trace_sample_arrays": "exact; timing/NetCDF metadata excluded"}, "original official five-field receipt differs")
    inventory = output_inventory(output, identity, pins)
    after_git = git_state(source, policy.commit, invoke)
    io.require(after_git == before_git and not (original_run / "claims" / (identity + ".json")).exists(),
               "original source/owner changed during execution")
    pins.recheck()
    io.write_new(capture_root / "output_inventory.json", io.seal({"status": "captured_original_refit_artifact_inventory",
        "original_cell_id": identity, "output": str(output), **inventory,
        "actual_semantic_comparison_owner": "unchanged_original_script", "adapter_ran_scientific_checker": False,
        "test_only_dependency_injection": test_only}))
    common = {"source_path": str(source), "git_commit": policy.commit, "original_manifest_sha256": policy.manifest_sha,
        "original_run": str(original_run), "reproduction_output": str(output), "source_input_sha256": original["input_sha256"],
        "environment_report_sha256": io.sha(capture_root / "environment.stdout.txt"), "original_full_budget": True,
        "exit_code": numerical_attempt["exit_code"], "owner_finished": True, "cached_comparison_only": False,
        "numeric_thread_environment": observed_runtime["numeric_thread_environment"], "python_executable": str(python),
        "argv": argv, "cwd": str(source), "script_index": 3, "workers": 92, "worker": worker,
        "actual_attempt_record_sha256": io.sha(capture_root / "numerical.attempt.json"),
        "stdout": numerical_attempt["stdout"], "stderr": numerical_attempt["stderr"],
        "fresh_output_reserved_empty_before_numerical_dispatch": True, "test_only_dependency_injection": test_only}
    invocation = io.seal({**common, "status": "actual_original_numerical_worker_invocation_recorded" if not test_only
        else "synthetic_original_numerical_worker_invocation_fixture", "actual_numerical_refit_execution": not test_only,
        "numerically_refitted_cell_ids": [identity]})
    comparison = io.seal({**common, "status": "actual_official_original_92_comparison_recorded" if not test_only
        else "synthetic_official_original_comparison_fixture", "scientifically_compared_cell_ids": [identity],
        "same_actual_fresh_official_process_also_executed_refit": not test_only,
        "official_receipt": {"path": str(official_path), "binding": binding(official_path)}})
    io.write_new(capture_root / "invocation_record.json", invocation)
    io.write_new(capture_root / "official_comparison_record.json", comparison)
    producer = {"route": "official_fresh_refit", "source_path": str(source), "git_commit": policy.commit,
        "input_sha256": original["input_sha256"], "matched_input": {"path": str(matched), "binding": binding(matched)}}
    for role, name in (("environment_report", "environment.stdout.txt"), ("invocation_record", "invocation_record.json"),
                       ("official_comparison_record", "official_comparison_record.json")):
        path = capture_root / name
        producer[role] = {"path": str(path), "binding": binding(path)}
    io.write_new(capture_root / "producer_pending_review.json", io.seal({"status": "original_numerical_producer_capture_pending_root_reviews",
        "original_cell_id": identity, "producer_partial": producer, "scientific_lineage_review": None,
        "original_owner_execution_review": None, "original_numerical_resolution_review": None,
        "source_cell": binding(source_cell), "refit_cell": binding(refit_path), "official_receipt": binding(official_path),
        "test_only_dependency_injection": test_only}))
    files = {str(path.relative_to(capture_root)): binding(path) for path in sorted(capture_root.iterdir()) if path.is_file()}
    expected = {"owner_started.json", "environment.stdout.txt", "environment.stderr.log", "environment.attempt.json",
        "numerical.stdout.txt", "numerical.stderr.log", "numerical.attempt.json", "output_inventory.json",
        "invocation_record.json", "official_comparison_record.json", "producer_pending_review.json"}
    io.inventory(capture_root, expected, set())
    pins.recheck()
    receipt = io.seal({"status": "original_missing_producer_execution_captured_root_review_pending" if not test_only
        else "synthetic_original_producer_completion_fixture_passed", "original_cell_id": identity,
        "request_sha256": request_sha, "selection_sha256": request["selected_reproduction_selection"]["sha256"],
        "root_missing_producer_choice_sha256": request["root_missing_producer_choice"]["sha256"],
        "route": "official_fresh_refit", "scheduled_original_cells": 1, "captured_original_cells": 1,
        "worker": worker, "workers": 92, "runtime": observed_runtime, "artifacts": files,
        "scientific_lineage_review_created": False, "original_owner_execution_review_created": False,
        "original_numerical_resolution_review_created": False, "whole92_numerical_rerun_claimed": False,
        "programme_complete": False, "release_certified": False, "test_only_dependency_injection": test_only})
    io.write_new(capture_root / "capture_receipt.json", receipt)
    io.inventory(capture_root, expected | {"capture_receipt.json"}, set())
    io.require({name: binding(capture_root / name) for name in files} == files, "capture evidence changed during publication")
    pins.recheck()
    return {"status": receipt["status"], "original_cell_id": identity, "scheduled_original_cells": 1,
            "capture_receipt_path": str(capture_root / "capture_receipt.json"),
            "capture_receipt_sha256": io.sha(capture_root / "capture_receipt.json"),
            "scientific_reviews_still_pending": True, "programme_complete": False,
            "test_only_dependency_injection": test_only}
