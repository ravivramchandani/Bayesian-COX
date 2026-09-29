"""Capture one bounded fictional probe; read-only sealed input byte checks."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).absolute().parent
CARRIER = OUT.parent / "generator_correction_guarded_dispatch_v1"
PREP_SHA = "54b1eaa4b4da20719a63c55c2ad67b91fbd936b650dba16dfa52091ba1b5942b"


def binding(path):
    assert path.is_absolute() and ".." not in path.parts
    assert not any(item.is_symlink() for item in (path, *path.parents))
    assert path.is_file()
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def write(name, value):
    value = {**value, "content_sha256": digest(value)}
    with (OUT / name).open("xb") as stream:
        stream.write((json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())


def source_snapshot():
    assert binding(CARRIER / "preparation_receipt.json")["sha256"] == PREP_SHA
    prep = json.loads((CARRIER / "preparation_receipt.json").read_text())
    assert prep["content_sha256"] == digest({k: v for k, v in prep.items() if k != "content_sha256"})
    assert {path.name for path in CARRIER.iterdir()} == {"preparation_receipt.json", *prep["artifacts"]}
    expected = {str(CARRIER / name): evidence for name, evidence in prep["artifacts"].items()}
    expected[str(CARRIER / "preparation_receipt.json")] = binding(CARRIER / "preparation_receipt.json")
    expected.update(prep["predecessor_sources_byte_identical"])
    for path, evidence in expected.items():
        assert binding(Path(path)) == evidence, f"sealed source changed: {path}"
    expected[str(OUT / "probe_counterexamples.py")] = binding(OUT / "probe_counterexamples.py")
    expected[str(Path(__file__).absolute())] = binding(Path(__file__).absolute())
    return expected


before = source_snapshot()
python = Path(sys.executable).resolve(strict=True)
argv = [str(python), "-I", "-B", str(OUT / "probe_counterexamples.py")]
environment = dict(os.environ)
threads = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
environment.update(dict.fromkeys(threads, "1"))
environment["PYTHONDONTWRITEBYTECODE"] = "1"
started = datetime.now(UTC).isoformat()
with (OUT / "probe.stdout.log").open("xb") as stdout, (OUT / "probe.stderr.log").open("xb") as stderr:
    returned = subprocess.run(argv, cwd=OUT, env=environment, stdout=stdout, stderr=stderr, check=False)
    assert type(returned.returncode) is int
    for stream in (stdout, stderr):
        stream.flush()
        os.fsync(stream.fileno())
after = source_snapshot()
write("probe.invocation.json", {"schema_version": 1, "status": "bounded_fictional_probe_actual_return_captured", "argv": argv,
      "cwd": str(OUT), "requested_interpreter": str(python), "observed_capture_interpreter": sys.executable,
      "numeric_thread_environment": {name: environment[name] for name in threads}, "started_at_utc": started,
      "finished_at_utc": datetime.now(UTC).isoformat(), "exit_code": returned.returncode,
      "raw_stdout": binding(OUT / "probe.stdout.log"), "raw_stderr": binding(OUT / "probe.stderr.log"),
      "source_before": before, "source_after": after, "all_sources_unchanged": before == after,
      "actual_real_controller_or_scientific_dispatch": False})
assert before == after
print(json.dumps({"actual_exit_code": returned.returncode, "all_sources_unchanged": before == after,
                  "captured_source_file_count": len(before)}, sort_keys=True))
if returned.returncode:
    raise SystemExit(returned.returncode)
