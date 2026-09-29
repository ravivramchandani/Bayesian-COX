"""Capture bounded real stdlib unit/Ruff/compile checks; never numerical helpers."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def bind(path: Path) -> dict[str, object]:
    data = path.read_bytes()
    return {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--mode", choices=("unit", "ruff", "compile"), required=True)
    args = parser.parse_args()
    root = Path(__file__).absolute().parent
    if not args.label.replace("_", "").isalnum():
        raise ValueError("simple unique label required")
    files = sorted(path for path in root.glob("*.py"))
    start = {path.name: bind(path) for path in files}
    if args.mode == "unit":
        argv = [sys.executable, "-I", "-B", "-m", "unittest", "discover", "-s", str(root), "-p", "test_guarded_dispatch.py", "-v"]
    elif args.mode == "ruff":
        argv = [sys.executable, "-I", "-B", "-m", "ruff", "check", "--no-cache", "--select", "E,F,I,UP,B", "--ignore", "E501", *map(str, files)]
    else:
        script = "import ast,pathlib; paths=" + repr([str(path) for path in files]) + "; [(ast.parse(pathlib.Path(p).read_text(),filename=p),compile(pathlib.Path(p).read_text(),p,'exec')) for p in paths]; print('AST/compile passed:',len(paths))"
        ast.parse(script)
        argv = [sys.executable, "-I", "-B", "-c", script]
    started = datetime.now(UTC).isoformat()
    out, err = root / f"{args.label}.stdout.log", root / f"{args.label}.stderr.log"
    with out.open("xb") as stdout, err.open("xb") as stderr:
        result = subprocess.run(argv, cwd=root, env=dict(os.environ), stdout=stdout, stderr=stderr, check=False)
        for stream in (stdout, stderr):
            stream.flush()
            os.fsync(stream.fileno())
    finish = {path.name: bind(path) for path in files}
    receipt = {"schema_version": 1, "status": "bounded_preparation_check_return_captured", "mode": args.mode,
               "argv": argv, "cwd": str(root), "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(),
               "exit_code": result.returncode, "source_start": start, "source_finish": finish,
               "source_unchanged": start == finish, "raw_stdout": bind(out), "raw_stderr": bind(err),
               "actual_numerical_or_guarded_controller_dispatch": False}
    with (root / f"{args.label}.invocation.json").open("x") as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps({"label": args.label, "exit_code": result.returncode, "source_unchanged": start == finish}, sort_keys=True))
    if result.returncode != 0 or start != finish:
        raise SystemExit(result.returncode if result.returncode else 1)


if __name__ == "__main__":
    main()
