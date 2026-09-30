"""Scientifically replay a freshly restored, bounded clinical methods release."""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.clinical_methods_release.common import (
    clean_commit,
    inventory,
    read_json,
    sha256_file,
    write_json_new,
)
from scripts.clinical_methods_release.qa import verify_seal
from scripts.clinical_methods_release.render import checked_analysis
from scripts.clinical_methods_release.render import render as render_focused
from scripts.finalize_clinical_methods import finalize
from scripts.verify_clinical_methods_subset import verify_subset

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = "post_hoc_clinical_methods_subset"


def _archive_commit(path: Path, expected: str) -> None:
    """Require the Git archive's source-commit marker to match its pinned checkout."""
    sha256_file(path)
    with tarfile.open(path, "r:gz") as archive:
        if archive.pax_headers.get("comment") != expected:
            raise ValueError(f"archived code commit differs: {path}")


def _same_science(left: dict, right: dict) -> None:
    """Compare the saved source receipt with a new subset-only replay."""
    original, replayed = dict(left), dict(right)
    # The focused clinical plan does not need the expression Parquet on a
    # receiving Mac. Its original hash remains pinned in the full manifest.
    original.pop("matched_source_file_verified", None)
    replayed.pop("matched_source_file_verified", None)
    if original != replayed:
        raise ValueError("restored subset scientific verification differs from source")


def verify_restored(
    *, restored: Path, production: Path, analysis_code: Path,
    primary: Path, sampler: Path, report_path: Path,
) -> dict:
    """Check exact payload bytes, replay saved science and write an external receipt."""
    if report_path.exists() or report_path.is_symlink():
        raise FileExistsError(report_path)
    if report_path.resolve().is_relative_to(restored.resolve()):
        raise ValueError("new replay receipt must be outside immutable restored evidence")
    for name, source in (("production", production), ("analysis_code", analysis_code),
                         ("primary", primary), ("sampler", sampler),
                         ("programme", sampler.parent)):
        if report_path.resolve().is_relative_to(source.resolve()):
            raise ValueError(f"new replay receipt must be outside preserved input: {name}")
    if analysis_code.resolve() != ROOT.resolve():
        raise ValueError("run verify_restored.py from the supplied analysis checkout")
    stage = read_json(restored / "release_stage.json")
    if (stage.get("schema_version") != 1 or stage.get("evidence_status") != EVIDENCE
            or stage.get("release_state") != "scientifically_verified_and_visually_reviewed_unpublished"
            or stage.get("full_extension_grid_verified") is not False
            or stage.get("selected_source_cells") != 225 or stage.get("selected_refits") != 9):
        raise ValueError("focused release stage marker differs")
    if inventory(restored, exclude=frozenset({"release_stage.json"})) != stage.get("member_sha256"):
        raise ValueError("restored focused member inventory differs")
    if (clean_commit(production) != stage["production_code_commit"]
            or clean_commit(analysis_code) != stage["analysis_code_commit"]):
        raise ValueError("restored replay checkouts differ from staged code")
    for name, commit in (("production", stage["production_code_commit"]),
                         ("analysis", stage["analysis_code_commit"])):
        _archive_commit(restored / "code" / f"{name}.tar.gz", commit)
    source_paths = {
        "scope_freeze.json": "coordination/clinical_methods_scope_freeze.json",
        "roster.json": "coordination/clinical_methods_roster.json",
        "addendum.md": "docs/protocol_addendum_clinical_methods.md",
        "baseline_sources.json": "coordination/extension_sources/baseline_sources.json",
        "baseline_evidence.json": "coordination/clinical_methods_baseline_evidence.json",
        "extension_protocol_freeze.json": "coordination/extension_protocol_freeze.json",
        "CLAIM_REVIEW.md": "scripts/clinical_methods_release/CLAIM_REVIEW.md",
    }
    for staged, source in source_paths.items():
        if sha256_file(restored / "study" / staged) != sha256_file(analysis_code / source):
            raise ValueError(f"restored study definition differs from analysed code: {staged}")
    if (sha256_file(restored / "evidence/run/manifest.json") != stage["source_manifest_sha256"]
            or sha256_file(restored / "study/scope_freeze.json") != stage["scope_freeze_sha256"]
            or sha256_file(restored / "verified/subset_verification.json") != stage["verification_sha256"]
            or sha256_file(restored / "verified/analysis/completion.json") != stage["analysis_completion_sha256"]
            or sha256_file(restored / "visual_qa/visual_qa_receipt.json") != stage["visual_qa_receipt_sha256"]):
        raise ValueError("restored focused source binding differs")
    source_receipt = read_json(restored / "verified/subset_verification.json")
    replayed_receipt = verify_subset(production, None, restored / "evidence/run",
                                    restored / "evidence/reproduction", strict_inventory=True)
    _same_science(source_receipt, replayed_receipt)
    completion, family, _ = checked_analysis(restored / "verified/analysis")
    if completion["family_complete"] != stage["family_complete"]:
        raise ValueError("restored formal inference gate differs")
    if family["expected_contrasts"] != 27:
        raise ValueError("restored comparison family differs")
    qa = verify_seal(restored / "verified/analysis", restored / "rendered", restored / "visual_qa")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="clinical-restored-science-", dir=report_path.parent) as temporary:
        repeated_analysis = Path(temporary) / "analysis"
        finalize(restored / "evidence/run", restored / "verified/subset_verification.json",
                 primary, sampler, repeated_analysis)
        if inventory(repeated_analysis) != inventory(restored / "verified/analysis"):
            raise ValueError("restored focused analysis differs from independent recomputation")
        repeated_rendered = Path(temporary) / "rendered"
        render_focused(repeated_analysis, repeated_rendered)
        for name in ("paired_contrasts", "cell_metrics", "diagnostic_coverage",
                     "original_horseshoe_context"):
            if sha256_file(repeated_rendered / f"{name}.csv") != sha256_file(restored / "rendered" / f"{name}.csv"):
                raise ValueError(f"restored focused table differs from regenerated analysis: {name}")
    receipt = {"schema_version": 1, "status": "restored_science_verified",
               "evidence_status": EVIDENCE, "verified_utc": datetime.now(UTC).isoformat(),
               "release_stage_sha256": sha256_file(restored / "release_stage.json"),
               "source_manifest_sha256": stage["source_manifest_sha256"],
               "scope_freeze_sha256": stage["scope_freeze_sha256"],
               "analysis_completion_sha256": stage["analysis_completion_sha256"],
               "production_code_commit": stage["production_code_commit"],
               "analysis_code_commit": stage["analysis_code_commit"],
               "selected_source_cells_rescored": replayed_receipt["rescored_cells"],
               "selected_source_cells_checked": replayed_receipt["verified_cells"],
               "selected_refits_compared": replayed_receipt["refits_compared"],
               "family_complete": completion["family_complete"],
               "visual_qa_receipt_sha256": stage["visual_qa_receipt_sha256"],
               "visual_review": "original named review preserved; no new visual inspection claimed",
               "claim_review_status": qa["claim_review_status"],
               "full_extension_grid_verified": False,
               "verifier_sha256": sha256_file(Path(__file__))}
    write_json_new(report_path, receipt)
    return receipt


def main() -> None:
    """Run from a fresh clone in the exact locked environment."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("restored", "production-code", "analysis-code", "primary", "sampler", "report"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    result = verify_restored(
        restored=args.restored.resolve(), production=args.production_code.resolve(),
        analysis_code=args.analysis_code.resolve(), primary=args.primary.resolve(),
        sampler=args.sampler.resolve(), report_path=args.report.absolute(),
    )
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
