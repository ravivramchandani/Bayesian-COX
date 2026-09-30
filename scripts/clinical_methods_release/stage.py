"""Stage only a scientifically verified and visually reviewed focused study."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.clinical_methods_release.common import (
    archive_commit,
    clean_commit,
    copy_directory,
    copy_regular,
    inventory,
    read_json,
    sha256_file,
    write_json_new,
)
from scripts.clinical_methods_release.qa import verify_seal
from scripts.clinical_methods_release.render import checked_analysis
from scripts.clinical_methods_release.render import render as render_focused
from scripts.extension_release.archive_common import atomic_new_directory
from scripts.finalize_clinical_methods import finalize, selected_ids
from scripts.verify_clinical_methods_subset import verify_subset

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = "post_hoc_clinical_methods_subset"


def _same_files(left: Path, right: Path) -> None:
    """Require two bounded output trees to contain identical file bytes."""
    if inventory(left) != inventory(right):
        raise ValueError(f"recomputed scientific output differs: {left} vs {right}")


def stage_release(
    *, production: Path, analysis_code: Path, run: Path, reproduction: Path,
    primary: Path, sampler: Path, verification: Path, analysed: Path,
    rendered: Path, qa_dir: Path, output: Path, matched: Path | None = None,
) -> dict:
    """Recheck the science, then copy exactly the selected cells and QA evidence."""
    for name in ("production", "analysis_code", "run", "reproduction", "primary", "sampler",
                 "verification", "analysed", "rendered", "qa_dir"):
        value = locals()[name]
        if value.is_symlink():
            raise ValueError(f"linked source is not allowed: {name}")
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    destination = output.resolve()
    for name in ("production", "analysis_code", "run", "reproduction", "primary", "sampler",
                 "analysed", "rendered", "qa_dir"):
        source = locals()[name].resolve()
        if destination.is_relative_to(source):
            raise ValueError(f"release output is inside preserved input root: {name}")
    if analysis_code.resolve() != ROOT.resolve():
        raise ValueError("run stage.py from the supplied analysis-code checkout")
    analysis_commit = clean_commit(analysis_code)
    production_commit = clean_commit(production)
    report = read_json(verification)
    if (report.get("verification_status") != "passed"
            or report.get("verifier_committed") is not True
            or report.get("full_extension_grid_verified") is not False
            or report.get("production_code_commit") != production_commit
            or report.get("analysis_code_commit") != analysis_commit
            or report.get("verifier_sha256") != sha256_file(ROOT / "scripts/verify_clinical_methods_subset.py")
            or report.get("verified_cells") != 225 or report.get("refits_compared") != 9):
        raise ValueError("passing committed focused subset verification is absent")
    if report.get("matched_source_file_verified") is not (matched is not None):
        raise ValueError("stage must repeat the verifier's optional matched-source check")
    repeated = verify_subset(production, matched, run, reproduction)
    if repeated != report:
        raise ValueError("focused source verification report differs from independent replay")
    completion, family, _ = checked_analysis(analysed)
    if (completion.get("source_verification_sha256") != sha256_file(verification)
            or completion.get("source_manifest_sha256") != sha256_file(run / "manifest.json")
            or completion.get("scope_freeze_sha256") != report["scope_freeze_sha256"]
            or family.get("family_complete") != completion.get("family_complete")):
        raise ValueError("focused analysis completion does not bind verification")
    qa = verify_seal(analysed, rendered, qa_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="clinical-science-replay-", dir=output.parent) as temporary:
        repeated_analysis = Path(temporary) / "analysis"
        finalize(run, verification, primary, sampler, repeated_analysis)
        _same_files(analysed, repeated_analysis)
        repeated_rendered = Path(temporary) / "rendered"
        render_focused(repeated_analysis, repeated_rendered)
        for name in ("paired_contrasts", "cell_metrics", "diagnostic_coverage",
                     "original_horseshoe_context"):
            if sha256_file(rendered / f"{name}.csv") != sha256_file(repeated_rendered / f"{name}.csv"):
                raise ValueError(f"focused table differs from saved analysis: {name}")
        for name in ("paired_gbsg2", "paired_whas500", "paired_metabric", "diagnostic_coverage"):
            if sha256_file(rendered / f"{name}.png") != sha256_file(repeated_rendered / f"{name}.png"):
                raise ValueError(f"focused figure differs from saved analysis: {name}")
    expected = selected_ids()
    if set(report.get("cells", {})) != expected:
        raise ValueError("focused source roster differs from fixed 225 cells")
    selected_refits = {identity for identity in expected if "__r01f01__" in identity}
    if set(report.get("selected_refits", {})) != selected_refits:
        raise ValueError("focused reproduction roster differs from nine")

    stage = Path(tempfile.mkdtemp(prefix=".clinical-stage-", dir=output.parent))
    try:
        study = {
            "scope_freeze.json": "coordination/clinical_methods_scope_freeze.json",
            "roster.json": "coordination/clinical_methods_roster.json",
            "addendum.md": "docs/protocol_addendum_clinical_methods.md",
            "baseline_sources.json": "coordination/extension_sources/baseline_sources.json",
            "baseline_evidence.json": "coordination/clinical_methods_baseline_evidence.json",
            "extension_protocol_freeze.json": "coordination/extension_protocol_freeze.json",
        }
        for target, source in study.items():
            copy_regular(ROOT / source, stage / "study" / target)
        copy_regular(ROOT / "scripts/clinical_methods_release/CLAIM_REVIEW.md",
                     stage / "study/CLAIM_REVIEW.md")
        copy_regular(run / "manifest.json", stage / "evidence/run/manifest.json")
        for identity, source_record in sorted(report["cells"].items()):
            path = run / "cells" / f"{identity}.json"
            if copy_regular(path, stage / "evidence/run/cells" / path.name) != source_record["file_sha256"]:
                raise ValueError(f"selected source changed during staging: {identity}")
        for identity, refit_record in sorted(report["selected_refits"].items()):
            path = reproduction / "cells" / f"{identity}.json"
            if copy_regular(path, stage / "evidence/reproduction/cells" / path.name) != refit_record["refit_file_sha256"]:
                raise ValueError(f"selected refit changed during staging: {identity}")
            if refit_record["original_receipt"] == "verified":
                receipt = reproduction / "receipts" / f"{identity}.json"
                copy_regular(receipt, stage / "evidence/reproduction/receipts" / receipt.name)
        (stage / "evidence/reproduction/receipts").mkdir(parents=True, exist_ok=True)
        copy_regular(verification, stage / "verified/subset_verification.json")
        copy_directory(analysed, stage / "verified/analysis")
        copy_directory(rendered, stage / "rendered")
        copy_directory(qa_dir, stage / "visual_qa")
        archive_commit(production, stage / "code/production.tar.gz", production_commit)
        archive_commit(analysis_code, stage / "code/analysis.tar.gz", analysis_commit)
        if sha256_file(stage / "study/scope_freeze.json") != report["scope_freeze_sha256"]:
            raise ValueError("staged focused scope differs")
        if verify_seal(stage / "verified/analysis", stage / "rendered", stage / "visual_qa") != qa:
            raise ValueError("staged visual review differs")
        record = {"schema_version": 1, "evidence_status": EVIDENCE,
                  "release_state": "scientifically_verified_and_visually_reviewed_unpublished",
                  "full_extension_grid_verified": False,
                  "production_code_commit": production_commit, "analysis_code_commit": analysis_commit,
                  "source_manifest_sha256": sha256_file(stage / "evidence/run/manifest.json"),
                  "scope_freeze_sha256": sha256_file(stage / "study/scope_freeze.json"),
                  "verification_sha256": sha256_file(stage / "verified/subset_verification.json"),
                  "analysis_completion_sha256": sha256_file(stage / "verified/analysis/completion.json"),
                  "visual_qa_receipt_sha256": sha256_file(stage / "visual_qa/visual_qa_receipt.json"),
                  "selected_source_cells": 225, "selected_refits": 9,
                  "family_complete": completion["family_complete"],
                  "baseline_dependency": "existing private confirmatory and programme releases",
                  "member_sha256": inventory(stage)}
        write_json_new(stage / "release_stage.json", record)
        atomic_new_directory(stage, output)
        return record
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def main() -> None:
    """Stage a new, unpublished clinical subset transfer tree."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("production-code", "analysis-code", "run", "reproduction", "primary",
                 "sampler", "verification", "analysed", "rendered", "qa-dir", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--matched", type=Path,
                        help="optional original matched parquet only if source verification used it")
    args = parser.parse_args()
    record = stage_release(
        production=args.production_code.resolve(), analysis_code=args.analysis_code.resolve(),
        run=args.run.resolve(), reproduction=args.reproduction.resolve(),
        primary=args.primary.resolve(), sampler=args.sampler.resolve(),
        verification=args.verification.resolve(), analysed=args.analysed.resolve(),
        rendered=args.rendered.resolve(), qa_dir=args.qa_dir.resolve(), output=args.output.absolute(),
        matched=args.matched.resolve() if args.matched else None,
    )
    print(json.dumps({"staged": str(args.output), "members": len(record["member_sha256"]),
                      "family_complete": record["family_complete"]}, sort_keys=True))


if __name__ == "__main__":
    main()
