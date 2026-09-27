"""Prestage sealed-code selected refits; the official 92-cell verifier runs later.

This external helper does not issue final receipts or alter the production run.
It can overlap deterministic selected refits with the long source grid.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("production-code", "matched", "source", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--worker", type=int, required=True)
    parser.add_argument("--workers", type=int, required=True)
    args = parser.parse_args()
    if not 0 <= args.worker < args.workers:
        raise ValueError("invalid worker shard")
    root = args.production_code.resolve()
    sys.path.insert(0, str(root))

    from scripts.reproduce_extensions import compare_traces, scientific_content
    from src.pipelines.extensions.planning import build_extension_jobs
    from src.pipelines.extensions.runner import (
        load_extension_cohorts,
        run_extension_cell,
        verified_cell,
    )
    from src.pipelines.extensions.verification import assert_scientific_equal
    from src.utils.io import read_mapping, write_json_atomic
    from src.utils.reproducibility import canonical_json_hash, sha256_file

    manifest = read_mapping(args.source / "manifest.json")
    if canonical_json_hash({k: v for k, v in manifest.items() if k != "manifest_content_sha256"}) != manifest["manifest_content_sha256"]:
        raise ValueError("production manifest changed")
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip() != manifest["code"]["git_commit"]:
        raise ValueError("production commit differs from the manifest")
    if sha256_file(args.matched) != manifest["matched_sha256"]:
        raise ValueError("matched data changed")
    for name, digest in manifest["input_sha256"].items():
        if sha256_file(root / name) != digest:
            raise ValueError(f"production source differs: {name}")
    config, primary, specs = (read_mapping(root / p) for p in
                              ("config/extensions.yaml", "config/confirmatory.yaml", "config/datasets.yaml"))
    cohorts = load_extension_cohorts(root, args.matched)
    jobs = build_extension_jobs(cohorts, config)
    if len(jobs) != manifest["planned_fits"]:
        raise ValueError("planned grid differs from manifest")
    selected = [j for j in jobs if j.repeat == j.fold == 1]
    if len(selected) != 92:
        raise ValueError("selected grid differs from frozen 92")
    selected = [j for i, j in enumerate(selected) if i % args.workers == args.worker]
    (args.output / "cells").mkdir(parents=True, exist_ok=True)
    print(f"worker {args.worker}: {len(selected)} selected jobs, sealed commit {manifest['code']['git_commit']}", flush=True)

    while True:
        pending = 0
        progressed = 0
        for job in selected:
            source_path = args.source / "cells" / f"{job.cell_id}.json"
            refit_path = args.output / "cells" / f"{job.cell_id}.json"
            if not source_path.exists():
                pending += 1
                continue
            source = verified_cell(source_path)
            if source["cell_id"] != job.cell_id:
                raise ValueError("source identity differs")
            if refit_path.exists():
                verified_cell(refit_path)
                continue
            key = "metabric" if job.dataset == "metabric_matched" else job.dataset
            refit = run_extension_cell(job, cohorts[job.dataset], specs[key]["primary_features"],
                                       primary, config, args.output)
            write_json_atomic(refit_path, refit, overwrite=False)
            assert_scientific_equal(scientific_content(source), scientific_content(refit), job.cell_id)
            compare_traces(args.source, args.output, source, refit)
            print(job.cell_id, "prestaged_exact", flush=True)
            progressed += 1
        if pending == 0:
            print(f"worker {args.worker}: all {len(selected)} selected refits prestaged", flush=True)
            break
        if progressed == 0:
            print(f"worker {args.worker}: waiting for {pending} source cells", flush=True)
            time.sleep(60)


if __name__ == "__main__":
    main()
