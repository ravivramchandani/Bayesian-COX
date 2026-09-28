"""Run exact, paired explainability analysis from immutable cell artefacts.

This script answers research question 3 (RQ3, explanation) from a completed
confirmatory run without refitting any model. For each stored Bayesian cell
it ranks feature groups by the model's own posterior contribution and by
exact linear SHAP (SHapley Additive exPlanations) values of the posterior-mean
risk, and records how well the rankings agree (ADR-024). The fold's stored Cox
coefficients give a secondary SHAP comparison where that Cox cell is
available. The analysis is in
``src.explainability.frozen_cells.analyze_frozen_run``, which verifies the
run's source hashes, subject pairing and stored preprocessing before it
interprets anything.

Reads:
    A completed run directory (``manifest.json``, ``completion.json`` and
    ``cells/``) plus the frozen configuration and raw cohorts in this
    repository.

Writes:
    One new JSON result, by default
    ``reports/explainability/<run name>_explainability_v1.json`` under the
    repository root. The output must lie outside the source run directory and
    must not already exist. The script prints the output path, the evidence
    status, the convergence-gate status and the number of comparisons.

Run it after the confirmatory run has completed (Make target ``explain``).

Example:
    python scripts/run_confirmatory_explainability.py --run-dir reports/confirmatory/<run>
"""

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
    """Parse the command line.

    Returns:
        Parsed command-line option namespace.
    """
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
    """Analyse the run, write the result and print a one-line summary.

    Returns:
        Exit status 0 on success.

    Raises:
        FileNotFoundError: If the run directory does not exist.
        ValueError: If the output path lies inside the source run directory.
        FileExistsError: If the output file already exists.
    """
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
