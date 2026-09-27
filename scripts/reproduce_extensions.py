"""Refit the frozen 92-cell extension selection and compare scientific content."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import arviz as az
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipelines.extensions.planning import build_extension_jobs
from src.pipelines.extensions.runner import (
    load_extension_cohorts,
    run_extension_cell,
    verified_cell,
)
from src.pipelines.extensions.verification import assert_scientific_equal, verify_extension_run
from src.utils.io import read_mapping, write_json_atomic


def scientific_content(value: Any) -> Any:
    """Remove only timing, file-container hashes and non-scientific tracebacks."""
    if isinstance(value, dict):
        ignored = {"seconds", "total_seconds", "fit_seconds", "cell_content_sha256", "traces", "traceback"}
        return {k: scientific_content(v) for k, v in value.items() if k not in ignored}
    if isinstance(value, list):
        return [scientific_content(v) for v in value]
    return value


def compare_traces(source: Path, refit: Path, left: dict, right: dict) -> None:
    """Compare actual sampled values independently of NetCDF metadata/clock fields."""
    for a, b in zip(left.get("fit_attempts", []), right.get("fit_attempts", []), strict=True):
        if set(a.get("traces", {})) != set(b.get("traces", {})):
            raise ValueError("refit trace groups differ")
        for label, trace in a.get("traces", {}).items():
            old = az.from_netcdf(str(source / "traces" / left["cell_id"] / trace["filename"]))
            new = az.from_netcdf(str(refit / "traces" / right["cell_id"] / b["traces"][label]["filename"]))
            try:
                for group in ("posterior", "sample_stats"):
                    before, after = getattr(old, group), getattr(new, group)
                    if set(before.data_vars) != set(after.data_vars):
                        raise ValueError("refit trace variables differ")
                    for variable in before.data_vars:
                        if variable in {"perf_counter_start", "perf_counter_diff", "process_time_diff"}:
                            continue
                        if not np.array_equal(before[variable].values, after[variable].values, equal_nan=True):
                            raise ValueError(f"refit sampled values differ at {label}/{group}/{variable}")
            finally:
                old.close()
                new.close()


def main() -> None:
    """Resume fixed selected refits without promoting selected checks to all-cell reproduction."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("matched", "source", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--worker", type=int, default=0)
    parser.add_argument("--workers", type=int, default=1)
    args = parser.parse_args()
    if not 0 <= args.worker < args.workers:
        raise ValueError("invalid reproduction shard")
    root = Path(__file__).resolve().parents[1]
    config, primary, specs = (read_mapping(root / p) for p in
                              ("config/extensions.yaml", "config/confirmatory.yaml", "config/datasets.yaml"))
    cohorts = load_extension_cohorts(root, args.matched)
    verify_extension_run(root, args.matched, args.source, deep=False)
    selected = [j for j in build_extension_jobs(cohorts, config) if j.repeat == j.fold == 1]
    if len(selected) != 92:
        raise ValueError("selected reproduction grid differs from 92 frozen cells")
    for i, job in enumerate(selected):
        if i % args.workers != args.worker:
            continue
        receipt = args.output / "receipts" / f"{job.cell_id}.json"
        source = verified_cell(args.source / "cells" / f"{job.cell_id}.json")
        path = args.output / "cells" / f"{job.cell_id}.json"
        if receipt.exists():
            cached = read_mapping(receipt)
            current = verified_cell(path)
            if cached["source_content_sha256"] != source["cell_content_sha256"] or cached["refit_content_sha256"] != current["cell_content_sha256"]:
                raise ValueError("selected reproduction checkpoint refers to changed cells")
            continue
        if path.exists():
            refit = verified_cell(path)
        else:
            key = "metabric" if job.dataset == "metabric_matched" else job.dataset
            refit = run_extension_cell(job, cohorts[job.dataset], specs[key]["primary_features"], primary, config, args.output)
            write_json_atomic(path, refit, overwrite=False)
        assert_scientific_equal(scientific_content(source), scientific_content(refit), job.cell_id)
        compare_traces(args.source, args.output, source, refit)
        write_json_atomic(receipt, {"cell_id": job.cell_id, "status": "scientific_match",
                                    "source_content_sha256": source["cell_content_sha256"],
                                    "refit_content_sha256": refit["cell_content_sha256"],
                                    "trace_sample_arrays": "exact; timing/NetCDF metadata excluded"}, overwrite=False)
        print(job.cell_id, "scientific_match", flush=True)


if __name__ == "__main__":
    main()
