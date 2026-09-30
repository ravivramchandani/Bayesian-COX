"""Prepare and seal an actual visual and claim review of focused-study figures."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.clinical_methods_release.common import inventory as tree_inventory
from scripts.clinical_methods_release.common import read_json, sha256_file, write_json_new

FIGURES = ("paired_gbsg2", "paired_whas500", "paired_metabric", "diagnostic_coverage")
TABLES = ("paired_contrasts", "cell_metrics", "diagnostic_coverage", "original_horseshoe_context")
CLAIM_CHECKS = (
    "post_hoc_outcome_aware_scope",
    "three_distinct_internal_validation_cohorts_and_endpoints",
    "bayesian_pwe_vs_penalised_cox_architecture_confounding",
    "all_failures_and_diagnostic_attrition_visible",
    "twenty_five_pairs_and_twenty_seven_holm_gate",
    "metabric_known_same_individual_accession_exposure",
    "no_decision_curve_or_clinical_utility_claim",
    "no_q1_acceptance_or_checklist_compliance_claim",
    "baseline_diagnostics_no_raw_trace_recalculation",
)
ATTESTATION = "I inspected every full-size PDF page and checked each required claim limitation."


def verify_lineage(analysis: Path, rendered: Path) -> dict:
    """Verify fixed figure inventory and exact input/output bindings."""
    completion = read_json(analysis / "completion.json")
    lineage = read_json(rendered / "lineage.json")
    if (lineage.get("schema_version") != 1
            or lineage.get("evidence_status") != "post_hoc_clinical_methods_subset"
            or lineage.get("source_completion_sha256") != sha256_file(analysis / "completion.json")
            or lineage.get("source_aggregates_sha256") != completion.get("aggregate_sha256")
            or lineage.get("renderer_sha256") != sha256_file(Path(__file__).with_name("render.py"))
            or lineage.get("visual_review") != "pending"):
        raise ValueError("focused render lineage differs from completed analysis")
    if [row.get("name") for row in lineage.get("figures", [])] != list(FIGURES):
        raise ValueError("focused figure roster/order differs")
    for name, digest in completion.get("aggregate_sha256", {}).items():
        if sha256_file(analysis / name) != digest:
            raise ValueError(f"completed analysis aggregate changed: {name}")
    for row in lineage["figures"]:
        for suffix in ("pdf", "png"):
            if row.get(f"{suffix}_sha256") != sha256_file(rendered / f"{row['name']}.{suffix}"):
                raise ValueError(f"rendered figure changed: {row['name']}.{suffix}")
    tables = lineage.get("tables")
    if not isinstance(tables, list) or [row.get("name") for row in tables] != list(TABLES):
        raise ValueError("focused rendered table roster/order differs")
    for row in tables:
        if row.get("csv_sha256") != sha256_file(rendered / f"{row['name']}.csv"):
            raise ValueError(f"rendered table changed: {row['name']}")
    expected = ({"lineage.json"}
                | {f"{name}.{suffix}" for name in FIGURES for suffix in ("pdf", "png")}
                | {f"{row['name']}.csv" for row in tables})
    actual = {p.name for p in rendered.iterdir()}
    if actual != expected:
        raise ValueError("rendered output has missing or extra files")
    return lineage


def _one_page_pdf(path: Path) -> None:
    """Check that Poppler sees exactly one nonempty PDF page."""
    info = subprocess.run(["pdfinfo", str(path)], text=True, capture_output=True, check=True).stdout
    pages = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
    size = re.search(r"^Page size:\s+([\d.]+) x ([\d.]+) pts", info, re.MULTILINE)
    if not pages or int(pages.group(1)) != 1 or not size:
        raise ValueError(f"expected one inspectable PDF page: {path}")
    if min(float(size.group(1)), float(size.group(2))) < 100:
        raise ValueError(f"implausibly small PDF page: {path}")


def prepare(analysis: Path, rendered: Path, output: Path) -> dict:
    """Render all PDF pages for a later named human inspection."""
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    lineage = verify_lineage(analysis, rendered)
    output.mkdir(parents=True)
    pages = output / "page_renders"
    pages.mkdir()
    records = []
    for name in FIGURES:
        pdf = rendered / f"{name}.pdf"
        _one_page_pdf(pdf)
        target = pages / name
        subprocess.run(["pdftoppm", "-f", "1", "-singlefile", "-png", "-r", "130",
                        str(pdf), str(target)], check=True, capture_output=True)
        png = target.with_suffix(".png")
        with Image.open(png) as image:
            width, height = image.size
            if width < 300 or height < 200:
                raise ValueError(f"PDF page render is too small: {name}")
        records.append({"name": name, "pdf_sha256": sha256_file(pdf),
                        "page_png_sha256": sha256_file(png), "page_size_px": [width, height]})
    thumbs = []
    for name in FIGURES:
        with Image.open(pages / f"{name}.png") as original:
            thumb = original.convert("RGB")
            thumb.thumbnail((700, 550))
            thumbs.append((name, thumb.copy()))
    sheet = Image.new("RGB", (1460, 1240), "white")
    draw = ImageDraw.Draw(sheet)
    for index, (name, thumb) in enumerate(thumbs):
        left = 20 + (index % 2) * 720
        top = 30 + (index // 2) * 610
        draw.text((left, top), name, fill="black")
        sheet.paste(thumb, (left, top + 25))
    sheet_path = output / "contact_sheet.png"
    sheet.save(sheet_path)
    inventory = {"schema_version": 1, "status": "automated_checks_passed_visual_review_pending",
                 "source_lineage_sha256": sha256_file(rendered / "lineage.json"),
                 "source_completion_sha256": sha256_file(analysis / "completion.json"),
                 "figures": records, "contact_sheet_sha256": sha256_file(sheet_path),
                 "lineage_figures": [row["name"] for row in lineage["figures"]]}
    write_json_new(output / "qa_inventory.json", inventory)
    template = {"reviewer": "", "reviewed_at": "", "attestation": ATTESTATION,
                "inventory_sha256": sha256_file(output / "qa_inventory.json"),
                "figure_verdicts": {name: "pending" for name in FIGURES},
                "claim_checks": {name: "pending" for name in CLAIM_CHECKS},
                "issues": []}
    write_json_new(output / "review_template.json", template)
    return inventory


def seal(analysis: Path, rendered: Path, qa_dir: Path) -> dict:
    """Seal a separately completed truthful inspection; never infer a pass."""
    verify_lineage(analysis, rendered)
    inventory = read_json(qa_dir / "qa_inventory.json")
    review = read_json(qa_dir / "review.json")
    if (inventory.get("status") != "automated_checks_passed_visual_review_pending"
            or inventory.get("source_lineage_sha256") != sha256_file(rendered / "lineage.json")
            or inventory.get("source_completion_sha256") != sha256_file(analysis / "completion.json")
            or review.get("inventory_sha256") != sha256_file(qa_dir / "qa_inventory.json")):
        raise ValueError("visual review source bindings differ")
    if [row.get("name") for row in inventory.get("figures", [])] != list(FIGURES):
        raise ValueError("visual review figure roster differs")
    for row in inventory["figures"]:
        name = row["name"]
        if (row.get("pdf_sha256") != sha256_file(rendered / f"{name}.pdf")
                or row.get("page_png_sha256") != sha256_file(qa_dir / "page_renders" / f"{name}.png")):
            raise ValueError(f"visual review page changed: {name}")
    if inventory.get("contact_sheet_sha256") != sha256_file(qa_dir / "contact_sheet.png"):
        raise ValueError("visual review contact sheet changed")
    if not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip():
        raise ValueError("named reviewer required")
    try:
        reviewed_at = datetime.fromisoformat(review["reviewed_at"])
    except (TypeError, ValueError) as error:
        raise ValueError("timezone-aware review time required") from error
    if reviewed_at.tzinfo is None or review.get("attestation") != ATTESTATION:
        raise ValueError("complete review attestation required")
    if review.get("figure_verdicts") != dict.fromkeys(FIGURES, "pass"):
        raise ValueError("every full-size figure needs an explicit pass")
    if review.get("claim_checks") != dict.fromkeys(CLAIM_CHECKS, "pass"):
        raise ValueError("each required claim limitation needs explicit review")
    if review.get("issues") != []:
        raise ValueError("unresolved review issues remain")
    receipt = {"schema_version": 1, "visual_qa_status": "passed",
               "claim_review_status": "passed_required_boundaries",
               "inventory_sha256": sha256_file(qa_dir / "qa_inventory.json"),
               "review_sha256": sha256_file(qa_dir / "review.json"),
               "source_lineage_sha256": sha256_file(rendered / "lineage.json"),
               "source_completion_sha256": sha256_file(analysis / "completion.json"),
               "figure_count": len(FIGURES), "claim_check_count": len(CLAIM_CHECKS)}
    write_json_new(qa_dir / "visual_qa_receipt.json", receipt)
    return receipt


def verify_seal(analysis: Path, rendered: Path, qa_dir: Path) -> dict:
    """Verify copied QA bytes and the original review without rewriting it."""
    verify_lineage(analysis, rendered)
    receipt = read_json(qa_dir / "visual_qa_receipt.json")
    if (receipt.get("visual_qa_status") != "passed"
            or receipt.get("claim_review_status") != "passed_required_boundaries"
            or receipt.get("figure_count") != len(FIGURES)
            or receipt.get("claim_check_count") != len(CLAIM_CHECKS)
            or receipt.get("inventory_sha256") != sha256_file(qa_dir / "qa_inventory.json")
            or receipt.get("review_sha256") != sha256_file(qa_dir / "review.json")
            or receipt.get("source_lineage_sha256") != sha256_file(rendered / "lineage.json")
            or receipt.get("source_completion_sha256") != sha256_file(analysis / "completion.json")):
        raise ValueError("visual QA receipt differs")
    inventory = read_json(qa_dir / "qa_inventory.json")
    review = read_json(qa_dir / "review.json")
    if (review.get("inventory_sha256") != receipt["inventory_sha256"]
            or review.get("attestation") != ATTESTATION
            or review.get("figure_verdicts") != dict.fromkeys(FIGURES, "pass")
            or review.get("claim_checks") != dict.fromkeys(CLAIM_CHECKS, "pass")
            or review.get("issues") != []):
        raise ValueError("original review form differs")
    try:
        reviewed_at = datetime.fromisoformat(review["reviewed_at"])
    except (TypeError, ValueError) as error:
        raise ValueError("invalid original review time") from error
    if reviewed_at.tzinfo is None or not review.get("reviewer", "").strip():
        raise ValueError("original review identity incomplete")
    if (inventory.get("status") != "automated_checks_passed_visual_review_pending"
            or [row.get("name") for row in inventory.get("figures", [])] != list(FIGURES)
            or inventory.get("source_lineage_sha256") != sha256_file(rendered / "lineage.json")
            or inventory.get("source_completion_sha256") != sha256_file(analysis / "completion.json")
            or inventory.get("contact_sheet_sha256") != sha256_file(qa_dir / "contact_sheet.png")):
        raise ValueError("visual inventory differs")
    for row in inventory["figures"]:
        name = row["name"]
        if (row.get("pdf_sha256") != sha256_file(rendered / f"{name}.pdf")
                or row.get("page_png_sha256") != sha256_file(qa_dir / "page_renders" / f"{name}.png")):
            raise ValueError(f"original page render differs: {name}")
    expected = ({"contact_sheet.png", "qa_inventory.json", "review_template.json",
                 "review.json", "visual_qa_receipt.json"}
                | {f"page_renders/{name}.png" for name in FIGURES})
    actual = set(tree_inventory(qa_dir))
    if actual != expected:
        raise ValueError("visual QA tree has missing or extra files")
    return receipt


def main() -> None:
    """Prepare page images or seal a named, explicit review."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "seal", "verify"))
    for name in ("analysis", "rendered", "qa-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.action == "prepare":
        result = prepare(args.analysis, args.rendered, args.qa_dir)
    elif args.action == "seal":
        result = seal(args.analysis, args.rendered, args.qa_dir)
    else:
        result = verify_seal(args.analysis, args.rendered, args.qa_dir)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    # Running as a file from the repo root is supported by normal Python's cwd.
    main()
