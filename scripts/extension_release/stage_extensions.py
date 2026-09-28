#!/usr/bin/env python3
"""Assemble only complete, verified extension evidence for private transfer."""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import tempfile
from functools import partial
from pathlib import Path

from archive_common import atomic_new_directory
from audit_support import stage_audit_support
from failure_transfer import verify_failure_transfer
from qa_transfer import verify_visual_transfer


def commit(root: Path) -> str:
    """Require an exact clean code checkout before archiving it."""
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True).strip():
        raise ValueError(f"code checkout is not clean: {root}")
    return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()


def copy_file(source: Path | str, target: Path | str, *, clone: bool = False) -> str:
    """Copy a regular file, optionally requiring native independent APFS cloning."""
    source, target = Path(source), Path(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink() or not source.is_file():
        raise ValueError(f"missing or linked source file: {source}")
    if clone:
        if sys.platform != "darwin":
            raise ValueError("strict clone staging requires macOS clonefile")
        libc = ctypes.CDLL(None, use_errno=True)
        clonefile = libc.clonefile
        clonefile.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_int]
        clonefile.restype = ctypes.c_int
        if clonefile(os.fsencode(source), os.fsencode(target), 0):
            code = ctypes.get_errno()
            raise OSError(code, os.strerror(code), str(target))
    else:
        shutil.copy2(source, target)
    return str(target)


def copy_tree(source: Path, target: Path, *, clone: bool = False) -> None:
    """Copy a link-free tree using the same checked regular-file operation."""
    if source.is_symlink() or not source.is_dir() or any(p.is_symlink() for p in source.rglob("*")):
        raise ValueError(f"missing or linked source tree: {source}")
    shutil.copytree(source, target, copy_function=partial(copy_file, clone=clone))


def verify_source_inputs(production: Path, manifest: dict, matched: Path,
                         matched_manifest: Path, raw_source: Path, source_report: Path,
                         *, analysis: Path | None = None) -> dict[str, str]:
    """Bind transferred preparation and measured sources to the original freeze."""
    from src.utils.io import read_mapping
    from src.utils.reproducibility import canonical_json_hash, sha256_file

    freeze = read_mapping(production / "coordination/extension_protocol_freeze.json")
    if (canonical_json_hash({k: v for k, v in freeze.items() if k != "content_sha256"}) != freeze["content_sha256"]
            or manifest["freeze_sha256"] != freeze["content_sha256"]):
        raise ValueError("source evidence refers to another extension freeze")
    for name, expected in freeze["sha256"].items():
        for root in {production, analysis} - {None}:
            if sha256_file(root / name) != expected:
                raise ValueError(f"frozen extension input changed: {root}/{name}")
    paths = {
        "data/metabric_source_report.json": (source_report, "coordination/extension_sources/metabric_source_report.json"),
        "data/matched_metabric_manifest.json": (matched_manifest, "coordination/extension_sources/matched_metabric_manifest.json"),
    }
    hashes = {}
    for target, (source, name) in paths.items():
        expected = freeze["sha256"][name]
        if sha256_file(source) != expected:
            raise ValueError(f"supplied source evidence differs from freeze: {name}")
        hashes[target] = expected
    preparation = read_mapping(matched_manifest)
    hashes["data/matched_metabric.parquet"] = sha256_file(matched)
    if hashes["data/matched_metabric.parquet"] != preparation["matched_sha256"] or preparation["matched_sha256"] != manifest["matched_sha256"]:
        raise ValueError("matched data differs from frozen preparation")
    if preparation["clinical_sha256"] != manifest["input_sha256"]["data/raw/metabric.csv"]:
        raise ValueError("matched preparation refers to another clinical source")
    if preparation["known_pairs_sha256"] != freeze["sha256"]["tests/fixtures/extensions/metabric_known_accession_pairs.csv"]:
        raise ValueError("matched preparation refers to another known-pair audit")
    report = read_mapping(source_report)
    source_files = {row["name"]: row for row in report["data_files"]}
    if (len(source_files) != len(report["data_files"]) or "LICENSE" not in source_files
            or {p.name for p in raw_source.iterdir()} != set(source_files)):
        raise ValueError("METABRIC source/license inventory differs")
    for name, expected in preparation["source_sha256"].items():
        if source_files[name]["downloaded_sha256"] != expected:
            raise ValueError(f"matched preparation and source report disagree: {name}")
    for name, row in source_files.items():
        path = raw_source / name
        if path.is_symlink() or not path.is_file() or sha256_file(path) != row["downloaded_sha256"]:
            raise ValueError(f"METABRIC measured source changed: {name}")
        hashes[f"data/metabric_raw/{name}"] = row["downloaded_sha256"]
    return hashes


def main() -> None:
    """Verify the finished extension run and copy only its verified evidence into a new ``--output`` directory.

    Before copying, it checks:

    - the run manifest and completion record, including their content hashes;
    - the 1,625 planned cells and their stored hashes;
    - the aggregate files;
    - the 92 selected reproduction refits and their receipts;
    - the rendered bundle (32 figures, 6 tables).

    It then records both code commits and key source, review and audit hashes.
    The package inventory later hashes every staged member.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("production-code", "analysis-code", "matched", "matched-manifest", "raw-source",
                 "source-report", "run", "reproduction", "rendered", "qa-dir", "worker-logs",
                 "prestage-helper", "coordinator-helper", "reference-root", "preparation-dir",
                 "failure-audit", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--validation-logs", type=Path, help="completed current-integration logs, kept separate from frozen preparation")
    parser.add_argument("--clone-staging", action="store_true", help="require APFS copy-on-write staging; never silently fall back to full copies")
    args = parser.parse_args()
    copy_payload = partial(copy_file, clone=args.clone_staging)
    copy_directory = partial(copy_tree, clone=args.clone_staging)
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
    source_hashes = verify_source_inputs(production, manifest, args.matched, args.matched_manifest,
                                       args.raw_source, args.source_report, analysis=analysis)
    failure_audit = verify_failure_transfer(args.run, args.failure_audit,
                                            Path(__file__).with_name("audit_rank_failures.py"))
    visual_transfer = verify_visual_transfer(args.qa_dir, args.rendered, args.run,
                                            qa_helper=analysis / "scripts/extension_release/extension_pdf_qa.py",
                                            renderer=analysis / "scripts/render_extensions.py")

    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".extension-stage-", dir=out.parent))
    try:
        for root, name in ((production, "production"), (analysis, "analysis")):
            target = stage / "code" / f"{name}.tar.gz"
            target.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(["git", "archive", "--format=tar.gz", f"--output={target}", "HEAD"],
                           cwd=root, check=True)
        copy_payload(args.matched, stage / "data/matched_metabric.parquet")
        copy_payload(args.matched_manifest, stage / "data/matched_metabric_manifest.json")
        copy_directory(args.raw_source, stage / "data/metabric_raw")
        copy_payload(args.source_report, stage / "data/metabric_source_report.json")
        copy_directory(args.run, stage / "evidence/run")
        copy_directory(args.reproduction, stage / "evidence/reproduction")
        copy_directory(args.rendered, stage / "rendered")
        copy_directory(args.qa_dir, stage / "visual_qa")
        copy_directory(args.failure_audit, stage / "failure_provenance")
        copy_directory(args.worker_logs, stage / "execution/worker_logs")
        copy_payload(args.prestage_helper, stage / "execution/prestage_refits.py")
        copy_payload(args.coordinator_helper, stage / "execution/coordinate_after_fits.py")
        transfer_tools = ("stage_extensions.py", "audit_support.py", "verify_restored_science.py",
                          "archive_common.py", "audit_rank_failures.py", "failure_transfer.py", "qa_transfer.py",
                          "audit_support_selftest.py", "selftest_rank_failures.py")
        for name in transfer_tools:
            copy_payload(Path(__file__).with_name(name), stage / "execution" / name)
        audit = stage_audit_support(production, args.reference_root, args.preparation_dir, stage / "audit")
        if args.validation_logs:
            copy_directory(args.validation_logs, stage / "execution/current_integration_validation")
        for name, expected in source_hashes.items():
            if sha256_file(stage / name) != expected:
                raise ValueError(f"staged frozen source evidence changed: {name}")
        for identity in planned_ids:
            if sha256_file(stage / "evidence/run/cells" / f"{identity}.json") != completion["cell_sha256"][f"cells/{identity}.json"]:
                raise ValueError(f"staged production cell changed: {identity}")
            verified_cell(stage / "evidence/run/cells" / f"{identity}.json")
        for identity in selected_ids:
            verified_cell(stage / "evidence/reproduction/cells" / f"{identity}.json")
        if verify_failure_transfer(stage / "evidence/run", stage / "failure_provenance",
                                   stage / "execution/audit_rank_failures.py") != failure_audit:
            raise ValueError("staged supplemental failure provenance differs")
        if verify_visual_transfer(stage / "visual_qa", stage / "rendered", stage / "evidence/run",
                                  qa_helper=analysis / "scripts/extension_release/extension_pdf_qa.py",
                                  renderer=analysis / "scripts/render_extensions.py") != visual_transfer:
            raise ValueError("staged visual-review evidence differs")
        stage_record = {"evidence_status": "post_hoc_extension_verified_transfer",
                        "production_code_commit": production_commit, "analysis_code_commit": analysis_commit,
                        "production_manifest_sha256": sha256_file(stage / "evidence/run/manifest.json"),
                        "production_completion_sha256": sha256_file(stage / "evidence/run/completion.json"),
                        "reproduction_receipts": 92, "figure_pairs": 32, "tables": 6,
                        "visual_qa_receipt_sha256": sha256_file(stage / "visual_qa/visual_qa_receipt.json"),
                        "metabric_source_report_sha256": sha256_file(stage / "data/metabric_source_report.json"),
                        "frozen_source_sha256": source_hashes, "audit_support": audit,
                        "failure_provenance": failure_audit,
                        "visual_qa_transfer": visual_transfer,
                        "staging_copy_mode": "strict_native_clonefile" if args.clone_staging else "copy2",
                        "transfer_tool_sha256": {name: sha256_file(stage / "execution" / name)
                                                 for name in transfer_tools}}
        write_json_atomic(stage / "release_stage.json", stage_record, overwrite=False)
        atomic_new_directory(stage, out)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    print(json.dumps({"staged": str(out), **stage_record}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
