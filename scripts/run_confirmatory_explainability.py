"""Run exact, paired explainability analysis from immutable cell artifacts."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.explainability.frozen_cells import (
    ExplanationProtocol,
    analyze_frozen_run,
    write_explainability_result,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Pure post-hoc analysis of frozen confirmatory cells. Models are never "
            "refitted and source hashes must match."
        )
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        type=Path,
        help="completed run directory containing manifest.json, completion.json and cells",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=(
            "new JSON result path; defaults to reports/explainability/ beside the "
            "source run and refuses to overwrite"
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    if not run_dir.is_dir():
        raise FileNotFoundError(f"confirmatory run directory is missing: {run_dir}")
    output = (
        args.output.resolve()
        if args.output is not None
        else PROJECT_ROOT
        / "reports"
        / "explainability"
        / f"{run_dir.name}_explainability_v1.json"
    )
    if run_dir == output or run_dir in output.parents:
        raise ValueError(
            "explainability output must be outside the immutable source run directory"
        )

    result = analyze_frozen_run(
        run_dir,
        PROJECT_ROOT,
        protocol=ExplanationProtocol(),
    )
    write_explainability_result(output, result)
    relative = os.path.relpath(output, PROJECT_ROOT)
    summary = result["convergence"]["summary"]
    print(
        f"explainability_artifact={relative} evidence={result['evidence_status']} "
        f"convergence={summary['status']} comparisons={len(result['comparisons'])}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
