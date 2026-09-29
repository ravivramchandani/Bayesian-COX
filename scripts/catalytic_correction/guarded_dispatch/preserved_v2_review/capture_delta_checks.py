"""Genuine bounded fictional captures and exact source/AST preservation checks."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).absolute().parent
CARRIER = OUT.parent / "generator_correction_guarded_dispatch_v2"
PREP_SHA = "46a95785348e9f54379178caaf728fd863cccef3d133b2f5a3c8116aa5d9e9cc"


def binding(path):
    assert path.is_absolute() and ".." not in path.parts
    assert not any(item.is_symlink() for item in (path, *path.parents))
    assert path.is_file()
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def sealed_read(path, expected):
    assert binding(path)["sha256"] == expected
    value = json.loads(path.read_text())
    assert value["content_sha256"] == digest({k: v for k, v in value.items() if k != "content_sha256"})
    return value


def write(name, value):
    assert "content_sha256" not in value
    with (OUT / name).open("xb") as stream:
        stream.write((json.dumps({**value, "content_sha256": digest(value)}, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())


def snapshot():
    prep = sealed_read(CARRIER / "preparation_receipt.json", PREP_SHA)
    expected = {str(CARRIER / name): evidence for name, evidence in prep["artifacts"].items()}
    expected[str(CARRIER / "preparation_receipt.json")] = binding(CARRIER / "preparation_receipt.json")
    assert {str(path) for path in CARRIER.rglob("*") if path.is_file()} == set(expected)
    assert sorted(str(path.relative_to(CARRIER)) for path in CARRIER.rglob("*") if path.is_dir()) == prep["artifact_directories"]
    assert len(expected) == 79
    assert prep["original20_sources_before"] == prep["original20_sources_after"]
    expected.update(prep["original20_sources_after"])
    for subdir, source_root, receipt_name, receipt_sha in (
        ("preserved_v1", OUT.parent / "generator_correction_guarded_dispatch_v1", "preparation_receipt.json", "54b1eaa4b4da20719a63c55c2ad67b91fbd936b650dba16dfa52091ba1b5942b"),
        ("preserved_v1_review", OUT.parent / "generator_correction_guarded_dispatch_independent_review_v1", "receipt.json", "2834ceca014e412bead8b8b4366883b7870641e925e5cc849b03d450fbe81153"),
    ):
        receipt = sealed_read(source_root / receipt_name, receipt_sha)
        files = {str(source_root / name): value for name, value in receipt["artifacts"].items()}
        files[str(source_root / receipt_name)] = binding(source_root / receipt_name)
        assert {str(path) for path in source_root.rglob("*") if path.is_file()} == set(files)
        for path, evidence in files.items():
            assert binding(CARRIER / subdir / Path(path).relative_to(source_root)) == evidence
        expected.update(files)
    contract = Path("/Users/macuser/bayes-cox-runs/ravi-main-integration-20260929/scripts/catalytic_correction/correction_fit_contracts.py")
    expected[str(contract)] = binding(contract)
    assert expected[str(contract)]["sha256"] == "83cb84002cd9dc447f70d9346baaba16197fa04d5a43e8b2fb500c2ce38f7fef"
    expected[str(OUT / "probe_reuse_consistency.py")] = binding(OUT / "probe_reuse_consistency.py")
    expected[str(Path(__file__).absolute())] = binding(Path(__file__).absolute())
    for path, evidence in expected.items():
        assert binding(Path(path)) == evidence, f"sealed input changed: {path}"
    return expected


def asts(path, methods=False):
    tree = ast.parse(path.read_text())
    if methods:
        nodes = [node for cls in tree.body if isinstance(cls, ast.ClassDef) and cls.name == "GuardTests"
                 for node in cls.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")]
    else:
        nodes = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))]
    return {node.name: hashlib.sha256(ast.dump(node, include_attributes=False).encode()).hexdigest() for node in nodes}


before = snapshot()
prep = sealed_read(CARRIER / "preparation_receipt.json", PREP_SHA)
old_methods = asts(CARRIER / "preserved_v1/test_guarded_dispatch.py", True)
new_methods = asts(CARRIER / "test_guarded_dispatch.py", True)
assert old_methods == new_methods == prep["original23_method_ASTs"] and len(new_methods) == 23
old_core, new_core = asts(CARRIER / "preserved_v1/guard_fit_dispatch.py"), asts(CARRIER / "guard_fit_dispatch.py")
changed_core = sorted(name for name in old_core if old_core[name] != new_core[name])
assert changed_core == ["dispatch", "validate_account_snapshot", "verify_guarded_dispatch_proof"]
old_capture, new_capture = asts(CARRIER / "preserved_v1/capture_guarded_dispatch.py"), asts(CARRIER / "capture_guarded_dispatch.py")
assert [name for name in old_capture if old_capture[name] != new_capture[name]] == ["launch"]
assert binding(CARRIER / "verify_guarded_dispatch_proof.py") == binding(CARRIER / "preserved_v1/verify_guarded_dispatch_proof.py")
write("delta_ast_and_initial_inventory.json", {"schema_version": 1, "status": "v2_bounded_delta_and_preservation_verified", "source_before": before,
      "original23_methods_unchanged": True, "original23_method_ASTs": new_methods, "changed_original_core_nodes": changed_core,
      "new_core_nodes": sorted(set(new_core) - set(old_core)), "changed_original_capture_nodes": ["launch"],
      "readonly_cli_byte_unchanged": True, "v1_all41_and_review_all11_exact": True, "source20_current_exact": True})
python = Path(sys.executable).resolve(strict=True)
environment = dict(os.environ)
threads = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
environment.update(dict.fromkeys(threads, "1"))
environment["PYTHONDONTWRITEBYTECODE"] = "1"
for label, argv in (
    ("unit", [str(python), "-I", "-B", "-m", "unittest", "discover", "-s", str(CARRIER), "-p", "test_guarded_dispatch*.py", "-v"]),
    ("reuse_probe", [str(python), "-I", "-B", str(OUT / "probe_reuse_consistency.py")]),
):
    start = snapshot()
    started = datetime.now(UTC).isoformat()
    with (OUT / f"{label}.stdout.log").open("xb") as stdout, (OUT / f"{label}.stderr.log").open("xb") as stderr:
        returned = subprocess.run(argv, cwd=OUT, env=environment, stdout=stdout, stderr=stderr, check=False)
        assert type(returned.returncode) is int
        for stream in (stdout, stderr):
            stream.flush()
            os.fsync(stream.fileno())
    finish = snapshot()
    write(f"{label}.invocation.json", {"schema_version": 1, "status": "bounded_fictional_delta_check_actual_return_captured", "argv": argv,
          "cwd": str(OUT), "requested_interpreter": str(python), "observed_capture_interpreter": sys.executable,
          "numeric_thread_environment": {key: environment[key] for key in threads}, "started_at_utc": started,
          "finished_at_utc": datetime.now(UTC).isoformat(), "exit_code": returned.returncode,
          "raw_stdout": binding(OUT / f"{label}.stdout.log"), "raw_stderr": binding(OUT / f"{label}.stderr.log"),
          "source_before": start, "source_after": finish, "all_sources_unchanged": start == finish,
          "actual_real_controller_scientific_or_checker_dispatch": False})
    assert start == finish == before
    print(json.dumps({"label": label, "actual_exit_code": returned.returncode, "source_files_unchanged": len(finish)}, sort_keys=True))
    if returned.returncode:
        raise SystemExit(returned.returncode)
