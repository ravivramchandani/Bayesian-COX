#!/usr/bin/env python3
"""Assemble only complete, verified extension evidence for private transfer."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from archive_common import atomic_new_directory


def commit(root: Path) -> str:
    """Require an exact clean code checkout before archiving it."""
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        raise ValueError(f"code checkout is not clean: {root}")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"missing or linked source file: {source}")
    shutil.copy2(source, target)


def copy_tree(source: Path, target: Path) -> None:
    if source.is_symlink() or not source.is_dir() or any(p.is_symlink() for p in source.rglob("*")):
        raise ValueError(f"missing or linked source tree: {source}")
    shutil.copytree(source, target)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("production-code", "analysis-code", "matched", "matched-manifest", "raw-source",
                 "source-report", "run", "reproduction", "rendered", "qa-dir", "worker-logs",
                 "prestage-helper", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    production, analysis = args.production_code.resolve(), args.analysis_code.resolve()
    sys.path.insert(0, str(analysis))
    from src.pipelines.extensions.runner import verified_cell
    from src.utils.io import read_mapping, write_json_atomic
    from src.utils.reproducibility import canonical_json_hash, sha256_file

    out = args.output.absolute()
    if out.exists() or out.is_symlink():
        raise FileExistsError(out)
    production_commit, analysis_commit = commit(production), commit(analysis)
    manifest = read_mapping(args.run / "manifest.json")
    completion = read_mapping(args.run / "completion.json")
    verification = read_mapping(args.run / "verification.json")
    if manifest["code"]["git_commit"] != production_commit:
        raise ValueError("production checkout differs from the fitted commit")
    if canonical_json_hash({k: v for k, v in manifest.items() if k != "manifest_content_sha256"}) != manifest["manifest_content_sha256"]:
        raise ValueError("fitted manifest content changed")
    if canonical_json_hash({k: v for k, v in completion.items() if k != "completion_content_sha256"}) != completion["completion_content_sha256"]:
        raise ValueError("completion content changed")
    if manifest["planned_fits"] != 1625 or completion["planned"] != 1625:
        raise ValueError("planned grid is not the specified 1,625 cells")
    if completion["stored"] != 1625 or verification != {k: completion[k] for k in verification} or verification["verification"] != "deep":
        raise ValueError("complete deep verification is absent or differs")
    if completion["manifest_sha256"] != sha256_file(args.run / "manifest.json"):
        raise ValueError("completion refers to another run manifest")
    if sha256_file(args.matched) != manifest["matched_sha256"]:
        raise ValueError("matched data differs from production")
    for name, expected in manifest["input_sha256"].items():
        if sha256_file(production / name) != expected:
            raise ValueError(f"production input differs: {name}")
        if name not in completion["analysis_only_sha256"] and sha256_file(analysis / name) != expected:
            raise ValueError(f"analysis checkout differs in production input: {name}")
    for name, expected in completion["analysis_only_sha256"].items():
        if sha256_file(analysis / name) != expected:
            raise ValueError(f"analysis-only code changed: {name}")
    planned_ids = {row["cell_id"] for row in manifest["plan"]}
    cell_paths = {p.stem: p for p in (args.run / "cells").glob("*.json")}
    if set(cell_paths) != planned_ids or len(planned_ids) != 1625 or len(cell_paths) != 1625:
        raise ValueError("production cell inventory differs from plan")
    if {f"cells/{p.name}": sha256_file(p) for p in cell_paths.values()} != completion["cell_sha256"]:
        raise ValueError("production cell hashes differ from completion")
    for name, expected in completion["aggregate_sha256"].items():
        if sha256_file(args.run / name) != expected:
            raise ValueError(f"aggregate changed: {name}")
    selected_ids = {identity for identity in planned_ids if "__r01f01__" in identity}
    if len(selected_ids) != 92:
        raise ValueError("selected reproduction grid differs")
    receipts = {p.stem: p for p in (args.reproduction / "receipts").glob("*.json")}
    refits = {p.stem: p for p in (args.reproduction / "cells").glob("*.json")}
    if set(receipts) != selected_ids or set(refits) != selected_ids:
        raise ValueError("92 exact reproduction receipts and cells are required")
    for identity in selected_ids:
        receipt = read_mapping(receipts[identity])
        if (receipt["status"] != "scientific_match" or receipt["cell_id"] != identity
                or receipt["source_content_sha256"] != read_mapping(cell_paths[identity])["cell_content_sha256"]
                or receipt["refit_content_sha256"] != read_mapping(refits[identity])["cell_content_sha256"]
                or receipt["trace_sample_arrays"] != "exact; timing/NetCDF metadata excluded"):
            raise ValueError(f"reproduction receipt differs: {identity}")
    lineage = read_mapping(args.rendered / "lineage.json")
    qa = read_mapping(args.qa_dir / "visual_qa_receipt.json")
    if (len(lineage["figures"]) != 32 or len(lineage["tables"]) != 6
            or lineage["source_completion_sha256"] != sha256_file(args.run / "completion.json")
            or qa["visual_qa_status"] != "passed"
            or qa["source_lineage_sha256"] != sha256_file(args.rendered / "lineage.json")
            or qa["source_run_completion_sha256"] != sha256_file(args.run / "completion.json")):
        raise ValueError("complete visual-QA-backed render is absent")
    for figure in lineage["figures"]:
        for extension in ("pdf", "png"):
            if sha256_file(args.rendered / f"{figure['name']}.{extension}") != figure[f"{extension}_sha256"]:
                raise ValueError(f"figure changed: {figure['name']}")
    for table in lineage["tables"]:
        if sha256_file(args.rendered / f"{table['name']}.csv") != table["csv_sha256"]:
            raise ValueError(f"table changed: {table['name']}")
    report = read_mapping(args.source_report)
    source_files = {row["name"]: row for row in report["data_files"]}
    if "LICENSE" not in source_files or {p.name for p in args.raw_source.iterdir()} != set(source_files):
        raise ValueError("METABRIC source/license inventory differs")
    for name, row in source_files.items():
        if sha256_file(args.raw_source / name) != row["downloaded_sha256"]:
            raise ValueError(f"METABRIC measured source changed: {name}")

    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".extension-stage-", dir=out.parent))
    try:
        for root, name in ((production, "production"), (analysis, "analysis")):
            target = stage / "code" / f"{name}.tar.gz"
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "archive", "--format=tar.gz", f"--output={target}", "HEAD"],
                           cwd=root, check=True)
        copy_file(args.matched, stage / "data/matched_metabric.parquet")
        copy_file(args.matched_manifest, stage / "data/matched_metabric_manifest.json")
        copy_tree(args.raw_source, stage / "data/metabric_raw")
        copy_file(args.source_report, stage / "data/metabric_source_report.json")
        copy_tree(args.run, stage / "evidence/run")
        copy_tree(args.reproduction, stage / "evidence/reproduction")
        copy_tree(args.rendered, stage / "rendered")
        copy_tree(args.qa_dir, stage / "visual_qa")
        copy_tree(args.worker_logs, stage / "execution/worker_logs")
        copy_file(args.prestage_helper, stage / "execution/prestage_refits.py")
        if sha256_file(stage / "data/matched_metabric.parquet") != manifest["matched_sha256"]:
            raise ValueError("staged matched data changed")
        for identity in planned_ids:
            if sha256_file(stage / "evidence/run/cells" / f"{identity}.json") != completion["cell_sha256"][f"cells/{identity}.json"]:
                raise ValueError(f"staged production cell changed: {identity}")
            verified_cell(stage / "evidence/run/cells" / f"{identity}.json")
        for identity in selected_ids:
            verified_cell(stage / "evidence/reproduction/cells" / f"{identity}.json")
        stage_record = {"evidence_status": "post_hoc_extension_verified_transfer",
                        "production_code_commit": production_commit, "analysis_code_commit": analysis_commit,
                        "production_manifest_sha256": sha256_file(stage / "evidence/run/manifest.json"),
                        "production_completion_sha256": sha256_file(stage / "evidence/run/completion.json"),
                        "reproduction_receipts": 92, "figure_pairs": 32, "tables": 6,
                        "visual_qa_receipt_sha256": sha256_file(stage / "visual_qa/visual_qa_receipt.json"),
                        "metabric_source_report_sha256": sha256_file(stage / "data/metabric_source_report.json")}
        write_json_atomic(stage / "release_stage.json", stage_record, overwrite=False)
        atomic_new_directory(stage, out)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(json.dumps({"staged": str(out), **stage_record}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
