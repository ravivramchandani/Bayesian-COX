"""Genuine source mixed-verifier capture, with explicit fictional-test refusal.

The child is the unchanged sealed verification-v2 CLI. This stdlib wrapper
cannot fit, generate proposals, render, approve science, or resume reproduction.
The actual deep verifier is invoked only when root later runs this pinned CLI.
"""

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
    _parser = argparse.ArgumentParser(add_help=False)
    _parser.add_argument("--preparation-receipt", type=Path, required=True)
    _parser.add_argument("--preparation-receipt-sha256", required=True)
    _initial, _unknown = _parser.parse_known_args()
    if hashlib.sha256(_initial.preparation_receipt.read_bytes()).hexdigest() != _initial.preparation_receipt_sha256:
        raise RuntimeError("release-v2 preparation receipt differs")
    _prep = json.loads(_initial.preparation_receipt.read_text())
    _own = Path(__file__).absolute().parent
    for _name, _digest in _prep["implementation_source_sha256"].items():
        if Path(_name).name != _name or hashlib.sha256((_own / _name).read_bytes()).hexdigest() != _digest:
            raise RuntimeError("release-v2 implementation differs")
    sys.path.insert(0, str(_own))

import release_core as core  # noqa: E402

OWN = {"capture_corrected_source.py", "capture_mixed_source.py", "release_core.py",
       "stage_corrected_extensions.py", "verification_io.py", "verify_restored_correction.py"}
VERIFIER_NAMES = {"bound_lineage.py", "capture_verification.py", "mixed_analysis.py", "mixed_lineage.py",
                  "science_verification.py", "render_verified_mix.py", "frozen_backend.py",
                  "verification_gates.py", "verification_io.py", "verify_mixed_extensions.py"}


def capture(argv: list[str], prefix: Path, output: Path, pins: core.Pins, *,
            source_inputs: dict[str, str], producer: dict[str, Any], runtime: dict[str, Any],
            invoke: Any = subprocess.run, test_only: bool = False) -> dict[str, Any]:
    """Only tests may inject; their attempt and receipt never have production status."""
    core.require(invoke is subprocess.run or test_only, "injection requires explicit fictional test mode")
    core.safe(prefix)
    core.no_overlap(prefix, [output])
    core.require(output.parent.is_dir() and not output.exists(), "fresh absent initial mixed output required; no cached/resume capture")
    core.require(prefix.parent.is_dir() and not prefix.exists() and not any(prefix.parent.glob(prefix.name + ".*")),
                 "exclusive external capture prefix required")
    core.require(argv[:3] == [runtime["python_executable"], "-I", "-B"] and len(argv) == 14
                 and runtime["locked_interpreter_samefile"] is True
                 and runtime["numeric_thread_environment"] == dict.fromkeys(core.NUMERIC, "1"),
                 "exact isolated actual interpreter/argv/numeric runtime required")
    for path, digest in source_inputs.items():
        pins.bind(core.safe(Path(path)), digest)
    for path, digest in producer["implementation_source_sha256"].items():
        pins.bind(core.safe(Path(path)), digest)
    pins.bind(Path(producer["preparation_receipt"]["historical_path"]), producer["preparation_receipt"]["sha256"])
    pins.recheck()
    started, tick = datetime.now(UTC).isoformat(), time.monotonic()
    rc, error, stdout, stderr = None, None, b"", b""
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for name in core.NUMERIC:
        environment[name] = "1"
    injected = test_only or invoke is not subprocess.run
    try:
        result = invoke(argv, capture_output=True, check=False, env=environment)
        rc, stdout, stderr = result.returncode, result.stdout, result.stderr
    except BaseException as caught:
        error = {"type": f"{type(caught).__module__}.{type(caught).__qualname__}", "message": str(caught)}
    core.require(isinstance(stdout, bytes) and isinstance(stderr, bytes), "exact raw child bytes required")
    paths = {kind: prefix.with_name(prefix.name + suffix) for kind, suffix in
             (("stdout", ".stdout.log"), ("stderr", ".stderr.log"), ("attempt", ".attempt.json"), ("receipt", ".receipt.json"))}
    core.write_bytes_new(paths["stdout"], stdout)
    core.write_bytes_new(paths["stderr"], stderr)
    common = {"capture_producer": producer, "runtime": runtime,
              "numeric_thread_environment": {name: environment[name] for name in core.NUMERIC},
              "test_only_dependency_injection": injected}
    attempt = core.seal({"operation": core.MIXED_CAPTURE_OPERATION if not injected else "synthetic_mixed_verifier_capture_fixture",
        "argv": argv, "entrypoint": {"historical_path": argv[3], "sha256": source_inputs[argv[3]]},
        "exit_code": rc, "launch_error": error, "started_at_utc": started,
        "finished_at_utc": datetime.now(UTC).isoformat(), "wall_seconds": time.monotonic() - tick,
        "stdout_sha256": core.sha(paths["stdout"]), "stderr_sha256": core.sha(paths["stderr"]),
        "stdout_path": str(paths["stdout"]), "stderr_path": str(paths["stderr"]),
        "implementation_source_sha256": source_inputs, "diagnostic_only_until_genuine_rc0_and_exact_completion": True, **common})
    core.write_new(paths["attempt"], attempt)
    core.require(type(rc) is int and rc == 0 and error is None, "actual verifier failed; raw logs/rc retained without success receipt")
    completion = core.document(output / "completion.json", pins)
    lines = stdout.splitlines()
    core.require(bool(lines), "actual child summary absent")
    summary = core.strict_json(lines[-1])
    core.require(summary["status"] == completion["status"] == core.MIXED_STATUS
                 and summary["verified_logical_cells"] == completion["verified_logical_cells"] == 1625
                 and summary["programme_complete"] is False and summary["verify_existing"] is False,
                 "actual rc0 initial deep-verification summary/completion differs")
    pins.recheck()
    receipt = core.seal({"schema_version": 1,
        "status": "mixed_verification_actual_rc0_captured" if not injected else "synthetic_mixed_verifier_capture_fixture_passed",
        "exit_code": rc, "completion_sha256": core.sha(output / "completion.json"),
        "stdout_sha256": core.sha(paths["stdout"]), "stderr_sha256": core.sha(paths["stderr"]),
        "stdout_path": str(paths["stdout"]), "stderr_path": str(paths["stderr"]),
        "invocation_attempt_sha256": core.sha(paths["attempt"]),
        "artifacts": {path.name: {"sha256": core.sha(path), "bytes": path.stat().st_size}
                      for kind, path in paths.items() if kind != "receipt"},
        "summary": summary, "programme_complete": False,
        "method_rendering_reproduction_or_release_approval_conferred": False, **common})
    core.write_new(paths["receipt"], receipt)
    core.require({path.name for path in prefix.parent.glob(prefix.name + ".*")} == {path.name for path in paths.values()}
                 and not any(prefix.parent.glob(".verification-pending-" + prefix.name + ".*")), "capture inventory/residue differs")
    pins.recheck()
    return {"status": receipt["status"], "receipt_path": str(paths["receipt"]),
            "receipt_sha256": core.sha(paths["receipt"]), "programme_complete": False,
            "test_only_dependency_injection": injected}


def prepare(preparation_path: Path, preparation_sha: str, verifier_path: Path, verifier_sha: str,
            bindings_path: Path, bindings_sha: str, output: Path, prefix: Path, python: Path,
            *, pins: core.Pins | None = None) -> tuple[list[str], core.Pins, dict[str, Any]]:
    """Read-only stdlib source/runtime/path checks before any child or destination."""
    python = core.runtime(python)
    pins = core.Pins() if pins is None else pins
    own = Path(__file__).absolute().parent
    core.require(preparation_path == own / "preparation_receipt.json", "actual retained producer preparation required")
    preparation = core.load_preparation(own, preparation_sha, pins)
    core.require(set(preparation["implementation_source_sha256"]) == OWN, "exact release-v2 source surface required")
    sources = core.document(own / "source_pins.json", pins, preparation["source_pins_sha256"], field=None)
    core.require(verifier_sha == sources["mixed_verifier_preparation_sha256"], "unchanged reviewed verifier-v2 preparation required")
    verifier_path = core.safe(verifier_path)
    core.require(verifier_path.name == "preparation_receipt.json", "explicit original verifier preparation receipt required")
    verifier_root = verifier_path.parent
    verifier = core.load_preparation(verifier_root, verifier_sha, pins)
    core.require(set(verifier["implementation_source_sha256"]) == VERIFIER_NAMES, "all ten original verifier implementations required")
    bindings = core.document(core.safe(bindings_path), pins, bindings_sha)
    core.require(set(bindings["roots"]) == core.ROOTS and set(bindings["files"]) == core.FILES
                 and set(bindings["review_paths"]) == core.REVIEWS, "exact scientific binding roles required")
    immutable = [own, verifier_root, bindings_path, *(core.safe(Path(path)) for path in bindings["roots"].values()),
                 *(core.safe(Path(item["path"])) for item in bindings["files"].values()),
                 *(core.safe(Path(path)) for path in bindings["review_paths"].values())]
    for role in ("resolution_review", "pilot_review"):
        if bindings.get(role) is not None:
            immutable.append(core.safe(Path(bindings[role]["path"])))
    core.no_overlap(output, [*immutable, prefix])
    core.no_overlap(prefix, [*immutable, output])
    core.require(output.parent.is_dir() and not output.exists() and prefix.parent.is_dir()
                 and not prefix.exists() and not any(prefix.parent.glob(prefix.name + ".*")),
                 "new initial verification output and exclusive external prefix required; no resume/replay")
    script = verifier_root / "verify_mixed_extensions.py"
    argv = [str(python), "-I", "-B", str(script), "--preparation-receipt", str(verifier_path),
            "--preparation-receipt-sha256", verifier_sha, "--input-bindings", str(bindings_path),
            "--input-bindings-sha256", bindings_sha, "--output", str(output)]
    source_inputs = {str(verifier_root / name): digest for name, digest in verifier["implementation_source_sha256"].items()}
    source_inputs[str(verifier_path)] = verifier_sha
    source_inputs[str(bindings_path)] = bindings_sha
    producer = {"entrypoint": {"historical_path": str(own / "capture_mixed_source.py"),
                               "sha256": preparation["implementation_source_sha256"]["capture_mixed_source.py"]},
                "preparation_receipt": {"historical_path": str(preparation_path), "sha256": preparation_sha},
                "implementation_source_sha256": {str(own / name): digest for name, digest in preparation["implementation_source_sha256"].items()}}
    runtime = {"python_executable": str(python), "observed_executable": sys.executable,
               "locked_interpreter_samefile": True, "numeric_thread_environment": {name: os.environ[name] for name in core.NUMERIC}}
    pins.recheck()
    return argv, pins, {"source_inputs": source_inputs, "producer": producer, "runtime": runtime}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("preparation-receipt", "verification-preparation", "input-bindings", "output", "capture-prefix", "python"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("preparation-receipt-sha256", "verification-preparation-sha256", "input-bindings-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    argv, pins, metadata = prepare(args.preparation_receipt, args.preparation_receipt_sha256,
        args.verification_preparation, args.verification_preparation_sha256, args.input_bindings,
        args.input_bindings_sha256, args.output, args.capture_prefix, args.python)
    result = capture(argv, args.capture_prefix, args.output, pins, **metadata)
    print(json.dumps(result, sort_keys=True, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
