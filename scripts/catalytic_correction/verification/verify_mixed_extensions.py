"""Separately certify mixed original/corrected evidence; never fit or refit."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

# -I omits this directory. Verify the exact preparation receipt before loading
# any helper. A receipt records preparation/testing, never method approval.
if __name__ == "__main__":
    _initial = argparse.ArgumentParser(add_help=False)
    _initial.add_argument("--preparation-receipt", type=Path, required=True)
    _initial.add_argument("--preparation-receipt-sha256", required=True)
    _args, _remaining = _initial.parse_known_args()
    if hashlib.sha256(_args.preparation_receipt.read_bytes()).hexdigest() != _args.preparation_receipt_sha256:
        raise RuntimeError("preparation receipt bytes differ")
    _receipt = json.loads(_args.preparation_receipt.read_text())
    _own = Path(__file__).absolute().parent
    for _name, _expected in _receipt["implementation_source_sha256"].items():
        if Path(_name).name != _name or hashlib.sha256((_own / _name).read_bytes()).hexdigest() != _expected:
            raise RuntimeError("verification implementation byte pin differs")
    sys.path.insert(0, str(_own))

from bound_lineage import BoundLineage  # noqa: E402 - byte-verified bootstrap
from frozen_backend import FrozenBackend  # noqa: E402
from mixed_analysis import execute_verified  # noqa: E402
from verification_gates import Gates, complete_output_inventory  # noqa: E402
from verification_io import (  # noqa: E402
    Claim,
    Pins,
    canonical,
    child,
    inventory,
    require,
    safe,
    seal,
    sha,
    write_bytes_new,
    write_new,
)


def actual_environment(gates: Gates, output: Path, *, replay_prefix: Path | None = None,
                       invoke: Any = subprocess.run) -> dict[str, Any]:
    """Capture the original259-package checker, with no scientific calculation.

    Fresh replay logs are outside the immutable restored payload. Nonzero exit
    evidence is retained and cannot authorize subsequent scientific imports.
    """
    production = gates.roots["production"]
    script, lock, hash_file = production / "scripts/verify_environment.py", production / "conda-lock.yml", production / "conda-lock.yml.sha256"
    gates.pins.bind(script, gates.original["input_sha256"]["scripts/verify_environment.py"])
    gates.pins.bind(lock, gates.original["input_sha256"]["conda-lock.yml"])
    require(hash_file.read_text().split()[0] == sha(lock), "lock hash-file text differs")
    gates.pins.bind(hash_file, sha(hash_file))
    argv = [sys.executable, "-B", str(script), "--lock-file", str(lock), "--hash-file", str(hash_file)]
    started, tick = datetime.now(UTC).isoformat(), time.monotonic()
    result = invoke(argv, capture_output=True, check=False)
    def destination(name: str) -> Path:
        return output / name if replay_prefix is None else replay_prefix.with_name(replay_prefix.name + "." + name)
    stdout_path, stderr_path = destination("environment.stdout.json"), destination("environment.stderr.log")
    write_bytes_new(stdout_path, result.stdout)
    write_bytes_new(stderr_path, result.stderr)
    invocation = seal({"operation": "fresh_original_259_package_environment_verification", "argv": argv,
                       "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(),
                       "wall_seconds": time.monotonic() - tick, "exit_code": result.returncode,
                       "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path), "checker_sha256": sha(script)})
    write_new(destination("environment_invocation.json"), invocation)
    require(result.returncode == 0, "actual environment checker failed; retained diagnostics require review")
    report = json.loads(result.stdout)
    require(report == gates.preflight_manifest["environment_verification"] == gates.documents["definition"]["environment_verification"]
            and report["status"] == "ok" and report["package_count"] == 259, "exact frozen full environment differs")
    return report


def prepare_output(output: Path, gates: Gates, invocation: dict[str, Any], *, replay: bool) -> None:
    """Refuse incomplete grid before this call; preserve failed attempts on disk."""
    safe(output)
    roots = list(gates.roots.values()) + list(gates.files.values())
    require(output.parent.is_dir() and all(not output.is_relative_to(root) and not root.is_relative_to(output) for root in roots),
            "verification output overlaps immutable input roots")
    if replay:
        require(output.is_dir() and (output / "completion.json").is_file(), "replay needs a completed existing verifier payload")
        return
    require(not output.exists(), "choose a new write-once verification destination")
    output.mkdir()
    for name in ("cells", "lineage", "checks", "checks/original", "checks/corrected", "aggregates"):
        (output / name).mkdir()
    write_new(output / "invocation.json", seal(invocation))


def main() -> None:
    """Run only after complete real prerequisites, or deeply replay restored bytes."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("preparation-receipt", "input-bindings", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("preparation-receipt-sha256", "input-bindings-sha256"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--verify-existing", action="store_true")
    parser.add_argument("--replay-prefix", type=Path)
    args = parser.parse_args()
    numeric = {name: os.environ.get(name) for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                                     "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")}
    require(all(value == "1" for value in numeric.values()), "direct verification requires all five numeric thread variables equal one")
    require(args.verify_existing == (args.replay_prefix is not None), "fresh replay needs an exclusive external metadata prefix")
    pins = Pins()
    preparation = pins.json(safe(args.preparation_receipt), args.preparation_receipt_sha256)
    own = Path(__file__).absolute().parent
    implementation = preparation["implementation_source_sha256"]
    for name, expected in implementation.items():
        pins.bind(child(own, name), expected)
    bindings = pins.json(safe(args.input_bindings), args.input_bindings_sha256)
    require(bindings["verification_preparation_receipt_sha256"] == args.preparation_receipt_sha256,
            "invocation binds a different tested verification preparation")
    gates = Gates(bindings, pins)
    source_pins = json.loads((own / "source_pins.json").read_text())
    pins.bind(own / "source_pins.json", preparation["source_pins_sha256"])
    started, tick = datetime.now(UTC).isoformat(), time.monotonic()
    require(not args.output.is_relative_to(own) and not own.is_relative_to(args.output), "output overlaps immutable preparation")
    invocation = {"operation": "mixed_extensions_deep_verification", "argv": sys.argv,
                  "started_at_utc": started, "input_bindings_sha256": args.input_bindings_sha256,
                  "preparation_receipt_sha256": args.preparation_receipt_sha256,
                  "actual_input_locations": bindings, "verify_existing": args.verify_existing,
                  "actual_numeric_thread_environment": numeric,
                  "scientific_method_approval_conferred": False}
    if args.replay_prefix is not None:
        prefix = safe(args.replay_prefix)
        require(prefix.parent.is_dir() and all(not prefix.is_relative_to(root) for root in [args.output, *gates.roots.values()]),
                "fresh replay metadata must be outside restored/source/baseline roots")
        require(not any(prefix.parent.glob(prefix.name + ".*")) and not prefix.exists(), "fresh replay prefix collision")
    prepare_output(safe(args.output), gates, invocation, replay=args.verify_existing)
    # Environment receipts and output preparation contain no cohort/fit work.
    # Fresh completed replay never modifies the existing immutable output.
    claim = (args.replay_prefix.with_name(args.replay_prefix.name + ".claim.json") if args.verify_existing
             else args.output / "verification.claim.json")
    with Claim(claim, canonical(gates.summary())):
        environment = actual_environment(gates, args.output, replay_prefix=args.replay_prefix)
        science = FrozenBackend(gates.roots["production"], gates.roots["analysis"], gates.roots["matched"], gates.original,
                                source_pins, pins)
        lineage = BoundLineage(gates, science, pins, environment)
        completion = execute_verified(gates, science, lineage, args.output, pins, implementation, replay=args.verify_existing)
    corrected_checks = [Path(name).stem for name in completion["check_sha256"] if name.startswith("checks/corrected/")]
    expected, directories = complete_output_inventory(args.output, [job.cell_id for job in science.jobs], corrected_checks)
    inventory(args.output, expected, directories)
    # Recheck ownership/scope after all expensive diagnostic/scoring work.
    Gates(bindings, pins)
    pins.recheck()
    summary = {"status": completion["status"], "verified_logical_cells": completion["verified_logical_cells"],
               "original_status_counts": completion["original_status_counts"], "mixed_view_status_counts": completion["mixed_view_status_counts"],
               "operation_counts": completion["operation_counts"], "programme_complete": False,
               "pending_gates": completion["pending_gates"], "verify_existing": args.verify_existing}
    if args.verify_existing:
        write_new(args.replay_prefix.with_name(args.replay_prefix.name + ".receipt.json"), seal({
            **invocation, "finished_at_utc": datetime.now(UTC).isoformat(), "wall_seconds": time.monotonic() - tick,
            "status": "actual_deep_restored_evidence_replay_completed", "existing_completion_sha256": sha(args.output / "completion.json"),
            "summary": summary, "scientific_files_reproduced_exactly": True,
            "fresh_root_only_replay_receipt": True, "cli_exit_code_claim": "caller_must_capture_actual_rc0"}))
    print(json.dumps(summary, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
