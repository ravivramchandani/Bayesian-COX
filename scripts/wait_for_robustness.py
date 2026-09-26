"""Finish a frozen robustness run once its sharded workers have exited."""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
import time
from pathlib import Path


def active_workers(project_root: Path) -> list[int]:
    """Identify live shard workers for exactly the supplied frozen checkout."""
    process_table = subprocess.run(
        ["ps", "-axo", "pid=,args="],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    workers = []
    for line in process_table.splitlines():
        fields = line.strip().split(maxsplit=1)
        if len(fields) != 2:
            continue
        try:
            argv = shlex.split(fields[1])
        except ValueError:
            continue
        if (
            any(Path(token).name == "shard_worker.py" for token in argv)
            and str(project_root) in argv
        ):
            workers.append(int(fields[0]))
    return workers


def main() -> int:
    """Wait without fitting, then invoke the unchanged official resume command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--claims-dir", required=True, type=Path)
    parser.add_argument("--poll-seconds", type=int, default=60)
    args = parser.parse_args()
    root = args.project_root.resolve(strict=True)
    run_dir = args.run_dir.resolve(strict=True)
    claims_dir = args.claims_dir.resolve(strict=True)
    if args.poll_seconds < 1:
        raise ValueError("poll seconds must be positive")
    if not run_dir.is_relative_to(root / "reports/robustness"):
        raise ValueError("run directory must belong to the supplied frozen checkout")
    while workers := active_workers(root):
        print(f"waiting_for_workers={workers}", flush=True)
        time.sleep(args.poll_seconds)
    if (run_dir / "completion.json").exists():
        print("completion already exists; no fitting command launched", flush=True)
        return 0
    # Completed claims remain as provenance. Remove only claims for missing
    # cells after every worker has exited, so the official resume can recover.
    recovered = 0
    for claim in claims_dir.rglob("*.claim"):
        relative = claim.relative_to(claims_dir)
        target = run_dir / str(relative).removesuffix(".claim")
        if not target.is_file():
            claim.unlink()
            recovered += 1
    print(f"stale_missing_cell_claims_released={recovered}", flush=True)
    subprocess.run(
        [sys.executable, "scripts/run_robustness.py", "--mode", "robustness", "--resume"],
        cwd=root,
        check=True,
    )
    completion = json.loads((run_dir / "completion.json").read_text())
    if completion["stored_cells"] != completion["planned_cells_in_this_invocation"]:
        raise RuntimeError("finished robustness run has an incomplete inventory")
    print(f"robustness_execution_complete={completion['stored_cells']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
