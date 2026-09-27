"""Independently verify and aggregate the complete post-hoc extension grid."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipelines.extensions.analysis import curves_from_cells, extension_families
from src.pipelines.extensions.rq2 import rq2_effects
from src.pipelines.extensions.runner import load_extension_cohorts
from src.pipelines.extensions.verification import verify_extension_run
from src.rendering.verification import verify_frozen_run, verify_robustness_run
from src.utils.io import json_safe, read_mapping, write_json_atomic
from src.utils.posthoc_evidence import verify_posthoc_run
from src.utils.reproducibility import canonical_json_hash, sha256_file


def write_once_or_same(path: Path, result: dict) -> None:
    """Resume an interrupted finalization only when the result is identical."""
    result = json_safe(result)
    if path.exists():
        if read_mapping(path) != result:
            raise ValueError(f"previous finalized result differs: {path}")
    else:
        write_json_atomic(path, result, overwrite=False)


def main() -> None:
    """Verify all sources before calculating separately labelled extension evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("matched", "run", "primary", "sampler", "robustness"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--production-code", type=Path, help="sealed checkout recorded in the fit manifest")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pinned = read_mapping(root / "coordination/extension_sources/baseline_sources.json")
    for key, path in (("primary", args.primary), ("sampler_adr032", args.sampler), ("robustness", args.robustness)):
        for name in ("manifest", "completion"):
            if sha256_file(path / f"{name}.json") != pinned[key][f"{name}_sha256"]:
                raise ValueError(f"baseline evidence changed: {key}/{name}")
    original = verify_frozen_run(args.primary)
    sampler = verify_posthoc_run(args.sampler, args.primary)
    robustness, _ = verify_robustness_run(args.robustness, original)
    cells, verification = verify_extension_run(root, args.matched, args.run, deep=True,
                                               production_root=args.production_code)
    write_once_or_same(args.run / "verification.json", verification)
    references = [c for _, c in original.cells if c["model_key"] != "bayesian_horseshoe"] + sampler["cells"]
    original_horseshoe = [{**c, "model_key": "bayesian_horseshoe_original"} for _, c in original.cells if c["model_key"] == "bayesian_horseshoe"]
    config = read_mapping(root / "config/extensions.yaml")
    outputs = {
        "paired_families.json": extension_families(cells, references),
        "decision_curves.json": curves_from_cells(cells + references + original_horseshoe, config,
                                                   pd.read_csv(root / "tests/fixtures/extensions/metabric_known_accession_pairs.csv")),
        "rq2_effects.json": rq2_effects(cells, robustness["cells"], load_extension_cohorts(root, args.matched)),
    }
    for name, result in outputs.items():
        write_once_or_same(args.run / name, result)
    completion = {"evidence_status": "post_hoc_extension", **verification,
                   "cell_sha256": {str(p.relative_to(args.run)): sha256_file(p) for p in sorted((args.run / "cells").glob("*.json"))},
                   "aggregate_sha256": {name: sha256_file(args.run / name) for name in outputs},
                   "manifest_sha256": sha256_file(args.run / "manifest.json"),
                   "selected_reproduction_status": "pending", "render_status": "pending"}
    completion["completion_content_sha256"] = canonical_json_hash(completion)
    write_once_or_same(args.run / "completion.json", completion)
    print(verification)


if __name__ == "__main__":
    main()
