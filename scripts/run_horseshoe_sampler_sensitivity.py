"""Run the separate 75-cell post-hoc target-acceptance sensitivity in ADR-032.

In the confirmatory run, 20 of the 75 horseshoe cells failed the
zero-divergence gate, leaving four of the nine primary prior contrasts without
inference. This sensitivity refits all 75 horseshoe cells, not only the
failures, with the frozen folds, seeds, model, priors, remedy ladder and
diagnostic gate. The only change is a target acceptance of 0.999 on every fit
attempt. The nine contrasts are then re-estimated against the unchanged
confirmatory normal and spike-and-slab cells (INV-009). The work is done by
``src.pipelines.posthoc_sampler.execute_sampler_sensitivity``.

Reads:
    ``--run-dir``, the completed 450-cell confirmatory run. Its evidence, the
    frozen study inputs and the live protocol are verified before any fit.

Writes:
    A new directory ``<output-root>/horseshoe_ta0999_posthoc_<hash>/`` with
    ``manifest.json``, one ``bayesian_horseshoe.json`` per fold under
    ``cells/``, ``inference.json`` and ``completion.json``. Every record is
    labelled ``posthoc_sampler_sensitivity`` and never replaces a confirmatory
    cell. ``--resume`` continues an interrupted run only if its code, inputs
    and environment are unchanged; ``--workers`` sets the number of fitting
    processes.

Render the result with ``scripts/render_horseshoe_sensitivity.py``.

Example:
    python scripts/run_horseshoe_sampler_sensitivity.py \
        --run-dir reports/confirmatory/<run> --output-root reports/posthoc --workers 4
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipelines.posthoc_sampler import execute_sampler_sensitivity


def main() -> int:
    """Parse execution controls and run the fixed sensitivity."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    run_dir = execute_sampler_sensitivity(
        PROJECT_ROOT,
        args.run_dir.resolve(),
        args.output_root.resolve(),
        workers=args.workers,
        resume=args.resume,
    )
    print(f"posthoc_sampler_sensitivity={run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
