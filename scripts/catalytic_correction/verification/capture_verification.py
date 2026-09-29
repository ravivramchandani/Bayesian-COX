"""Capture genuine verifier rc0; failures retain exact logs and actual exit code."""

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

if __name__ == "__main__":
    _bootstrap = argparse.ArgumentParser(add_help=False)
    _bootstrap.add_argument("--preparation-receipt", type=Path, required=True)
    _bootstrap.add_argument("--preparation-receipt-sha256", required=True)
    _initial, _unknown = _bootstrap.parse_known_args()
    if hashlib.sha256(_initial.preparation_receipt.read_bytes()).hexdigest() != _initial.preparation_receipt_sha256:
        raise RuntimeError("preparation receipt bytes differ")
    _document = json.loads(_initial.preparation_receipt.read_text())
    _own = Path(__file__).absolute().parent
    for _name, _expected in _document["implementation_source_sha256"].items():
        if Path(_name).name != _name or hashlib.sha256((_own / _name).read_bytes()).hexdigest() != _expected:
            raise RuntimeError("verification implementation bytes differ")
    sys.path.insert(0, str(_own))

from verification_io import (  # noqa: E402
    Pins,
    read,
    require,
    safe,
    seal,
    sha,
    write_bytes_new,
    write_new,
)


def capture(argv: list[str], prefix: Path, output: Path, pins: Pins,
            invoke: Any = subprocess.run) -> dict[str, Any]:
    """Injectable capture; mocked tests never launch science or datasets."""
    safe(prefix)
    require(prefix.parent.is_dir() and not prefix.is_relative_to(output)
            and not prefix.exists() and not any(prefix.parent.glob(prefix.name + ".*")), "capture prefix missing/colliding/inside output")
    started, tick = datetime.now(UTC).isoformat(), time.monotonic()
    rc, error, stdout, stderr = None, None, b"", b""
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        environment[name] = "1"
    try:
        result = invoke(argv, capture_output=True, check=False, env=environment)
        rc, stdout, stderr = result.returncode, result.stdout, result.stderr
    except BaseException as caught:
        error = {"type": f"{type(caught).__module__}.{type(caught).__qualname__}", "message": str(caught)}
    stdout_path, stderr_path = (prefix.with_name(prefix.name + suffix) for suffix in (".stdout.log", ".stderr.log"))
    write_bytes_new(stdout_path, stdout)
    write_bytes_new(stderr_path, stderr)
    attempt = seal({"operation": "actual_mixed_verifier_child_capture", "argv": argv, "exit_code": rc, "launch_error": error,
        "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(), "wall_seconds": time.monotonic() - tick,
        "stdout_sha256": sha(stdout_path), "stderr_sha256": sha(stderr_path),
        "stdout_path": str(stdout_path), "stderr_path": str(stderr_path),
        "implementation_source_sha256": {str(path): digest for path, digest in pins.files.items()},
        "diagnostic_only_until_genuine_rc0_and_exact_completion": True})
    write_new(prefix.with_name(prefix.name + ".attempt.json"), attempt)
    require(rc == 0 and error is None, "verifier failed; actual exit/logs retained, no success receipt")
    completion = read(output / "completion.json")
    summary = json.loads(stdout.decode().splitlines()[-1])
    require(summary["status"] == completion["status"]
            == "mixed_original_corrected_grid_deep_verified_and_frozen_analysis_recomputed"
            and summary["verified_logical_cells"] == completion["verified_logical_cells"] == 1625
            and summary["programme_complete"] is False, "actual rc0 stdout/completion differs")
    pins.recheck()
    receipt = seal({"schema_version": 1, "status": "mixed_verification_actual_rc0_captured", "exit_code": rc,
                    "completion_sha256": sha(output / "completion.json"), "stdout_sha256": sha(stdout_path),
                    "stderr_sha256": sha(stderr_path), "stdout_path": str(stdout_path), "stderr_path": str(stderr_path),
                    "invocation_attempt_sha256": sha(prefix.with_name(prefix.name + ".attempt.json")),
                    "artifacts": {path.name: {"sha256": sha(path), "bytes": path.stat().st_size}
                                  for path in (stdout_path, stderr_path, prefix.with_name(prefix.name + ".attempt.json"))},
                    "summary": summary, "programme_complete": False,
                    "method_rendering_reproduction_or_release_approval_conferred": False})
    write_new(prefix.with_name(prefix.name + ".receipt.json"), receipt)
    # No unknown/pending publication files can be tolerated as success.
    require({path.name for path in prefix.parent.glob(prefix.name + ".*")} == {prefix.name + suffix for suffix in
        (".stdout.log", ".stderr.log", ".attempt.json", ".receipt.json")}
        and not any(prefix.parent.glob(".verification-pending-" + prefix.name + ".*")), "capture inventory differs")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("preparation-receipt", "input-bindings", "output", "capture-prefix"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("preparation-receipt-sha256", "input-bindings-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    pins = Pins()
    receipt = pins.json(safe(args.preparation_receipt), args.preparation_receipt_sha256)
    own = Path(__file__).absolute().parent
    for name, digest in receipt["implementation_source_sha256"].items():
        pins.bind(own / name, digest)
    bindings = pins.json(safe(args.input_bindings), args.input_bindings_sha256)
    prefix = safe(args.capture_prefix)
    require(all(not prefix.is_relative_to(safe(Path(value))) for value in bindings["roots"].values())
            and not prefix.is_relative_to(own), "capture logs must be outside immutable inputs/preparation")
    argv = [sys.executable, "-I", "-B", str(own / "verify_mixed_extensions.py"),
            "--preparation-receipt", str(args.preparation_receipt), "--preparation-receipt-sha256", args.preparation_receipt_sha256,
            "--input-bindings", str(args.input_bindings), "--input-bindings-sha256", args.input_bindings_sha256,
            "--output", str(args.output)]
    summary = capture(argv, prefix, safe(args.output), pins)
    print(json.dumps({"status": summary["status"], "receipt_sha256": sha(prefix.with_name(prefix.name + ".receipt.json")),
                      "programme_complete": False}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
