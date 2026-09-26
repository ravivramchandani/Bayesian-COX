"""Run the separate 75-cell post-hoc target-acceptance sensitivity in ADR-032."""

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
