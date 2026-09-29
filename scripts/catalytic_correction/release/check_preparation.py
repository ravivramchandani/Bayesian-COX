"""Retain actual cheap preparation-check commands; never invoke real helpers."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("kind", choices=("tests", "lint"))
    parser.add_argument("name")
    args = parser.parse_args()
    own = Path(__file__).absolute().parent
    files = sorted(own.glob("*.py"))
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    if args.kind == "tests":
        command = ["/opt/homebrew/opt/python@3.14/bin/python3.14", "-B", "-m", "unittest", "-v",
                   "test_release_adapters", "test_receiving_adapters", "test_source_capture",
                   "test_transport_delegate", "test_v2_provenance"]
    else:
        command = ["/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/ruff", "check", "--no-cache",
                   "--select", "E,F,I,UP,B", "--ignore", "E501", "--target-version", "py312",
                   *(str(path) for path in files)]
    prefix = own / args.name
    if prefix.parent != own or any(own.glob(prefix.name + ".*")):
        raise ValueError("fresh ordinary check prefix required")
    started = datetime.now(UTC).isoformat()
    result = subprocess.run(command, cwd=own, capture_output=True, check=False)
    for suffix, data in ((".stdout.txt", result.stdout), (".stderr.txt", result.stderr)):
        with prefix.with_name(prefix.name + suffix).open("xb") as stream:
            stream.write(data)
    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    record = {"argv": command, "cwd": str(own), "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(),
              "exit_code": result.returncode, "source_sha256_before": before, "source_sha256_after": after,
              "real_scientific_helpers_or_data_executed": False}
    with prefix.with_name(prefix.name + ".invocation.json").open("x") as stream:
        stream.write(json.dumps(record, sort_keys=True, indent=2) + "\n")
    print(json.dumps({"kind": args.kind, "name": args.name, "exit_code": result.returncode,
                      "source_bytes_unchanged": before == after}, sort_keys=True))


if __name__ == "__main__":
    main()
