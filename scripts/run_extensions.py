"""Execute disjoint shards of the separately frozen post-hoc extension grid."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipelines.extensions.runner import execute_extension_worker


def main() -> None:
    """Run or strictly resume one shard without changing scientific settings."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--matched", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--worker", type=int, default=0)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    execute_extension_worker(Path(__file__).resolve().parents[1], args.matched, args.output, args.worker, args.workers)


if __name__ == "__main__":
    main()
