"""Capture only this preparation's stdlib fixtures, scoped lint and syntax checks."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).absolute().parent
LOCKED = Path("/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/python")
NUMERIC = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
SOURCES = ("release_v3_core.py", "stage_corrected_extensions_v3.py", "capture_per_entry_source_v3.py",
           "verify_restored_correction_v3.py", "test_release_v3.py", "run_preparation_checks.py")


def sha(path: Path) -> str:
    """Digest a bounded preparation file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def install(path: Path, value: bytes) -> None:
    """Retain actual check bytes exclusively; never overwrite an earlier attempt."""
    with path.open("xb") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())


def main() -> int:
    """Run only the exact synthetic/lint/syntax command declared here."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("tests", "ruff", "syntax"), required=True)
    parser.add_argument("--prefix", required=True)
    args = parser.parse_args()
    if not LOCKED.samefile(Path(sys.executable)) or any(os.environ.get(name) != "1" for name in NUMERIC):
        raise ValueError("actual locked Python and numeric-five=1 required")
    if Path(args.prefix).name != args.prefix or not args.prefix or ".." in Path(args.prefix).parts:
        raise ValueError("bounded single-component output prefix required")
    if any(ROOT.glob(args.prefix + ".*")):
        raise ValueError("check attempt prefix already exists")
    source_before = {name: sha(ROOT / name) for name in SOURCES}
    started, tick = datetime.now(UTC).isoformat(), time.monotonic()
    if args.phase == "tests":
        argv = [str(LOCKED), "-I", "-B", str(ROOT / "test_release_v3.py")]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, check=False, env=dict(os.environ))
        rc, stdout, stderr = result.returncode, result.stdout, result.stderr
    elif args.phase == "ruff":
        argv = [str(LOCKED), "-I", "-B", "-m", "ruff", "check", "--no-cache", "--select", "E,F,I,UP,B", "--ignore", "E501",
                *(str(ROOT / name) for name in SOURCES)]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, check=False, env=dict(os.environ))
        rc, stdout, stderr = result.returncode, result.stdout, result.stderr
    else:
        argv = [str(LOCKED), "-I", "-B", str(Path(__file__).absolute()), "--phase", "syntax", "--prefix", args.prefix]
        for name in SOURCES:
            path = ROOT / name
            raw = path.read_bytes()
            ast.parse(raw, filename=str(path))
            compile(raw, str(path), "exec", dont_inherit=True)
        rc, stdout, stderr = 0, json.dumps({"parsed_and_compiled_sources": len(SOURCES), "sources_executed": False}).encode() + b"\n", b""
    source_after = {name: sha(ROOT / name) for name in SOURCES}
    paths = {kind: ROOT / (args.prefix + suffix) for kind, suffix in
             (("stdout", ".stdout.log"), ("stderr", ".stderr.log"), ("invocation", ".invocation.json"))}
    install(paths["stdout"], stdout)
    install(paths["stderr"], stderr)
    record = {"schema_version": 1, "status": "bounded_release_v3_preparation_check_invocation", "phase": args.phase,
        "argv": argv, "cwd": str(ROOT), "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(),
        "wall_seconds": time.monotonic() - tick, "exit_code": rc, "source_sha256_before": source_before,
        "source_sha256_after": source_after, "source_unchanged": source_before == source_after,
        "numeric_thread_environment": {name: os.environ[name] for name in NUMERIC},
        "stdout_sha256": sha(paths["stdout"]), "stderr_sha256": sha(paths["stderr"]),
        "actual_science_producer_receiver_or_package_invoked": False, "invented_or_injected_fixture_scope_only": True}
    record["content_sha256"] = hashlib.sha256(json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    install(paths["invocation"], (json.dumps(record, sort_keys=True, indent=2) + "\n").encode())
    print(json.dumps({"phase": args.phase, "exit_code": rc, "source_unchanged": source_before == source_after,
                      "invocation_path": str(paths["invocation"]), "invocation_sha256": sha(paths["invocation"])}), flush=True)
    return rc if source_before == source_after else 1


if __name__ == "__main__":
    raise SystemExit(main())
