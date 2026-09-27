"""Independent, write-once PDF inspection for the 32 extension figures.

This helper never marks visual QA passed during preparation. A separate,
explicitly completed named review form is needed to issue a receipt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps

COHORT_SETTINGS = (
    ("gbsg2", "clinical"),
    ("metabric", "clinical"),
    ("metabric_matched", "clinical"),
    ("metabric_matched", "expression"),
    ("whas500", "clinical"),
)
FAMILIES = (
    "calibrated_vs_adr032_horseshoe",
    "catalytic_vs_original_priors",
    "expression_increment",
    "penalized_vs_original_priors",
)
RQ2_DATASETS = ("gbsg2", "whas500", "metabric")
TABLE_SOURCES = (
    ("fold_metrics", ["cells/*.json"]),
    ("decision_curve_points", ["decision_curves.json"]),
    ("decision_curve_support", ["decision_curves.json"]),
    ("decision_curve_unavailable", ["decision_curves.json"]),
    ("paired_families", ["paired_families.json"]),
    ("rq2_effects", ["rq2_effects.json"]),
)
ATTESTATION = "I examined every rendered PDF page at full size and the indexed contact sheets."
BOX_PATTERN = re.compile(
    r"^Page\s+1\s+(MediaBox|CropBox|BleedBox|TrimBox|ArtBox):\s+"
    r"([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)$"
)
FONT_TAIL = re.compile(r"\s+(yes|no)\s+(yes|no)\s+(yes|no)\s+(\d+)\s+(\d+)\s*$")


def digest(path: Path) -> str:
    """Return SHA-256 for an existing regular file."""
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"missing or linked regular file: {path}")
    sha = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            sha.update(block)
    return sha.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    """Read a JSON mapping."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"expected JSON object: {path}")
    return data


def write_once(path: Path, value: dict[str, Any]) -> None:
    """Publish complete JSON by hard-linking a fsynced temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, sort_keys=True, indent=2, ensure_ascii=True, allow_nan=False).encode() + b"\n"
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".qa-", delete=False) as temp:
        temp_path = Path(temp.name)
        temp.write(payload)
        temp.flush()
        os.fsync(temp.fileno())
    try:
        os.link(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def expected_names() -> list[str]:
    """Mirror only the renderer's frozen figure loops, independently of lineage."""
    names = []
    for dataset, setting in COHORT_SETTINGS:
        names.extend((f"{dataset}_{setting}_ibs", f"{dataset}_{setting}_calibration"))
    for dataset, setting in COHORT_SETTINGS:
        names.extend(f"decision_{dataset}__{setting}__h{h}" for h in (1, 2, 3))
    names.extend(f"paired_{family}" for family in FAMILIES)
    names.extend(f"rq2_{dataset}" for dataset in RQ2_DATASETS)
    assert len(names) == 32 and len(set(names)) == 32
    return names


def listed_sources(run: Path, name: str) -> list[str]:
    """Independently establish the source filenames implied by a figure."""
    if name.startswith("decision_"):
        return ["decision_curves.json"]
    if name.startswith("paired_"):
        return ["paired_families.json"]
    if name.startswith("rq2_"):
        return ["rq2_effects.json"]
    for dataset, setting in COHORT_SETTINGS:
        if name in (f"{dataset}_{setting}_ibs", f"{dataset}_{setting}_calibration"):
            prefix = f"{dataset}__{setting}__"
            return [f"cells/{p.name}" for p in sorted((run / "cells").glob("*.json"))
                    if p.stem.startswith(prefix) and p.stem.endswith("__full")]
    raise ValueError(f"unexpected figure name: {name}")


def verify_lineage(run: Path, rendered: Path, renderer: Path) -> tuple[dict[str, Any], list[str]]:
    """Check exact output inventory, inherited source hashes, and figure lineage."""
    lineage = read_json(rendered / "lineage.json")
    completion = read_json(run / "completion.json")
    manifest = read_json(run / "manifest.json")
    if (manifest.get("planned_fits") != 1625 or completion.get("planned") != 1625
            or completion.get("stored") != 1625 or completion.get("verification") != "deep"
            or len(completion.get("cell_sha256", {})) != 1625
            or completion.get("manifest_sha256") != digest(run / "manifest.json")):
        raise ValueError("source run lacks the complete, deeply verified 1,625-fit grid")
    if not manifest.get("test_only") and (manifest.get("evidence_status") != "post_hoc_extension"
                                           or completion.get("evidence_status") != "post_hoc_extension"):
        raise ValueError("source run does not identify post-hoc extension evidence")
    expected = expected_names()
    figures = lineage.get("figures")
    if not isinstance(figures, list) or [f.get("name") for f in figures] != expected:
        # Figure order is the renderer's loop order, so it is part of the inventory.
        raise ValueError("lineage figure inventory/order differs from renderer's expected 32")
    if lineage.get("evidence_status") != "post_hoc_extension":
        raise ValueError("lineage evidence status is not post-hoc extension")
    if (lineage.get("actual_visual_review") != "pending; creation does not constitute QA"
            and (not manifest.get("test_only") or lineage.get("actual_visual_review") != "pending")):
        raise ValueError("renderer must leave actual visual review pending")
    for key, source in (("source_manifest_sha256", run / "manifest.json"),
                        ("source_completion_sha256", run / "completion.json"),
                        ("renderer_sha256", renderer)):
        if lineage.get(key) != digest(source):
            raise ValueError(f"lineage source hash mismatch: {key}")
    for suffix in ("pdf", "png"):
        found = {p.stem for p in rendered.glob(f"*.{suffix}")}
        if found != set(expected):
            raise ValueError(f"{suffix} inventory mismatch: missing={sorted(set(expected)-found)}, "
                             f"unexpected={sorted(found-set(expected))}")
    tables = lineage.get("tables")
    if not isinstance(tables, list) or [t.get("name") for t in tables] != [name for name, _ in TABLE_SOURCES]:
        raise ValueError("lineage CSV inventory/order differs from renderer's expected six")
    found_tables = {p.stem for p in rendered.glob("*.csv")}
    expected_tables = {name for name, _ in TABLE_SOURCES}
    if found_tables != expected_tables:
        raise ValueError(f"CSV inventory mismatch: missing={sorted(expected_tables-found_tables)}, "
                         f"unexpected={sorted(found_tables-expected_tables)}")
    source_hashes = {**completion.get("cell_sha256", {}), **completion.get("aggregate_sha256", {})}
    for source, expected_hash in source_hashes.items():
        path = (run / source).resolve()
        if not path.is_relative_to(run.resolve()) or digest(path) != expected_hash:
            raise ValueError(f"source hash mismatch: {source}")
    for record in figures:
        name = record["name"]
        sources = listed_sources(run, name)
        if not sources or record.get("source_files") != sources:
            raise ValueError(f"figure source list differs: {name}")
        for source in sources:
            path = (run / source).resolve()
            if not path.is_relative_to(run.resolve()) or source not in source_hashes:
                raise ValueError(f"untracked source: {source}")
        for suffix in ("pdf", "png"):
            path = rendered / f"{name}.{suffix}"
            if digest(path) != record.get(f"{suffix}_sha256"):
                raise ValueError(f"lineage {suffix} hash mismatch: {name}")
        if record.get("visual_review") != "pending":
            raise ValueError(f"renderer unexpectedly asserts visual review: {name}")
    for record, (name, sources) in zip(tables, TABLE_SOURCES, strict=True):
        if record.get("source_files") != sources:
            raise ValueError(f"CSV source list differs: {name}")
        if name == "fold_metrics":
            if len(completion["cell_sha256"]) != len(list((run / "cells").glob("*.json"))):
                raise ValueError("fold metrics CSV source glob differs from pinned cell inventory")
        elif sources[0] not in source_hashes:
            raise ValueError(f"untracked CSV source: {name}")
        if digest(rendered / f"{name}.csv") != record.get("csv_sha256"):
            raise ValueError(f"lineage CSV hash mismatch: {name}")
    return lineage, expected


def poppler_metadata(pdf: Path) -> dict[str, Any]:
    """Require one valid page with embedded fonts and return its Poppler metadata."""
    info = subprocess.run(("pdfinfo", "-f", "1", "-l", "1", "-box", str(pdf)),
                          capture_output=True, text=True, check=True).stdout
    pages = re.search(r"^Pages:\s+(\d+)\s*$", info, re.MULTILINE)
    if not pages or int(pages.group(1)) != 1:
        raise ValueError(f"figure PDF does not have exactly one page: {pdf}")
    if not re.search(r"^Encrypted:\s+no\s*$", info, re.MULTILINE):
        raise ValueError(f"figure PDF is encrypted: {pdf}")
    boxes = {}
    for line in info.splitlines():
        match = BOX_PATTERN.match(line)
        if match:
            box = [float(match.group(i)) for i in range(2, 6)]
            if not all(map(math.isfinite, box)) or box[2] <= box[0] or box[3] <= box[1]:
                raise ValueError(f"invalid {match.group(1)}: {pdf}")
            boxes[match.group(1)] = box
    if set(boxes) != {"MediaBox", "CropBox", "BleedBox", "TrimBox", "ArtBox"}:
        raise ValueError(f"incomplete PDF boxes: {pdf}")
    media, crop = boxes["MediaBox"], boxes["CropBox"]
    if any((crop[0] < media[0]-0.01, crop[1] < media[1]-0.01,
            crop[2] > media[2]+0.01, crop[3] > media[3]+0.01)):
        raise ValueError(f"crop outside media box: {pdf}")
    output = subprocess.run(("pdffonts", str(pdf)), capture_output=True, text=True, check=True).stdout
    fonts = []
    for line in output.splitlines()[2:]:
        tail = FONT_TAIL.search(line)
        if not tail:
            raise ValueError(f"unparseable pdffonts row: {pdf}: {line}")
        fonts.append({"name_and_type": line[:tail.start()].strip(), "embedded": tail.group(1) == "yes",
                      "subset": tail.group(2) == "yes", "unicode": tail.group(3) == "yes"})
    if not fonts or any(not font["embedded"] for font in fonts):
        raise ValueError(f"PDF has missing or unembedded fonts: {pdf}")
    return {"pages": 1, "boxes_pt": boxes, "fonts": fonts}


def png_metadata(path: Path, crop: list[float] | None = None) -> dict[str, int]:
    """Check that a plot raster is readable, nonempty, and sized like its PDF."""
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        width, height = image.size
        if width < 300 or height < 200:
            raise ValueError(f"raster unexpectedly small: {path}: {image.size}")
        greyscale = image.convert("L")
        if greyscale.getextrema()[0] >= 250:
            raise ValueError(f"raster appears blank: {path}")
    if crop is not None:
        pdf_ratio = (crop[2]-crop[0]) / (crop[3]-crop[1])
        if abs(width / height - pdf_ratio) / pdf_ratio > 0.03:
            raise ValueError(f"PDF/PNG aspect ratios disagree: {path}")
    return {"width_px": width, "height_px": height}


def font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Use a stable local font with a basic fallback."""
    for path in ("/System/Library/Fonts/Supplemental/Arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def contact_sheets(qa_dir: Path, checks: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Make eight-figure indexed PNG sheets for a human's visual inspection."""
    sheets = []
    title_font, label_font, small_font = font(22), font(17), font(13)
    for offset in range(0, len(checks), 8):
        subset = checks[offset:offset+8]
        canvas = Image.new("RGB", (1680, 2280), "white")
        draw = ImageDraw.Draw(canvas)
        number = offset // 8 + 1
        draw.text((28, 18), f"Extension PDF visual review - sheet {number}/4", font=title_font, fill="black")
        draw.text((28, 53), "Open each numbered page render at full size; contact sheets are an index.",
                  font=small_font, fill="#444444")
        for index, check in enumerate(subset):
            row, col = divmod(index, 2)
            x, y = 20 + col * 830, 90 + row * 545
            draw.rectangle((x, y, x+812, y+530), outline="#999999", width=2)
            label = f"{offset+index+1:02d}  {check['name']}"
            draw.text((x+12, y+10), label, font=label_font, fill="black")
            image_path = qa_dir / check["page_render"]
            with Image.open(image_path) as source:
                thumb = ImageOps.contain(source.convert("RGB"), (786, 455), Image.Resampling.LANCZOS)
            canvas.paste(thumb, (x + (812-thumb.width)//2, y+45+(455-thumb.height)//2))
            draw.text((x+12, y+505), f"PDF SHA-256 {check['pdf_sha256'][:16]}",
                      font=small_font, fill="#444444")
        relative = f"contact_sheets/sheet_{number:02d}.png"
        path = qa_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(path)
        sheets.append({"file": relative, "sha256": digest(path)})
    return sheets


def prepare(args: argparse.Namespace) -> None:
    """Inspect final figures and create a pending review template."""
    run, rendered, renderer, qa_dir = (p.resolve() for p in (args.run, args.rendered, args.renderer, args.qa_dir))
    if qa_dir.exists():
        raise FileExistsError(f"choose a new QA directory: {qa_dir}")
    lineage, names = verify_lineage(run, rendered, renderer)
    qa_dir.mkdir(parents=True)
    (qa_dir / "page_renders").mkdir()
    records = []
    for index, name in enumerate(names, 1):
        pdf, png = rendered / f"{name}.pdf", rendered / f"{name}.png"
        metadata = poppler_metadata(pdf)
        raster = png_metadata(png, metadata["boxes_pt"]["CropBox"])
        relative = f"page_renders/{index:02d}_{name}.png"
        prefix = qa_dir / relative[:-4]
        subprocess.run(("pdftoppm", "-f", "1", "-l", "1", "-r", str(args.dpi),
                        "-png", "-singlefile", str(pdf), str(prefix)), check=True,
                       capture_output=True, text=True)
        page_render = qa_dir / relative
        render_size = png_metadata(page_render)
        records.append({"name": name, "pdf_sha256": digest(pdf), "png_sha256": digest(png),
                        "pdf": metadata, "png": raster, "page_render": relative,
                        "page_render_sha256": digest(page_render), "page_render_size": render_size,
                        "source_files": lineage["figures"][index-1]["source_files"]})
    sheets = contact_sheets(qa_dir, records)
    inventory = {"schema_version": 1, "status": "automated_checks_passed_visual_review_pending",
                 "run": str(run), "rendered": str(rendered), "renderer": str(renderer),
                 "qa_helper_sha256": digest(Path(__file__)),
                 "run_manifest_sha256": digest(run / "manifest.json"),
                 "run_completion_sha256": digest(run / "completion.json"),
                 "lineage_sha256": digest(rendered / "lineage.json"),
                 "renderer_sha256": digest(renderer),
                 "dpi": args.dpi, "figure_count": len(records),
                 "table_count": len(lineage["tables"]), "tables": lineage["tables"],
                 "figures": records, "contact_sheets": sheets}
    write_once(qa_dir / "qa_inventory.json", inventory)
    review_template = {"schema_version": 1, "inventory_sha256": digest(qa_dir / "qa_inventory.json"),
                       "reviewer_name": "", "reviewed_at_utc": "", "attestation": "",
                       "figures": [{"name": name, "verdict": "pending", "issue": ""} for name in names]}
    write_once(qa_dir / "review_template.json", review_template)
    print(f"Automated checks passed for {len(records)} figure pairs. Visual QA is pending: {qa_dir}")


def receipt(args: argparse.Namespace) -> None:
    """Write a receipt only from an explicit, complete named visual review."""
    qa_dir = args.qa_dir.resolve()
    inventory_path = qa_dir / "qa_inventory.json"
    inventory = read_json(inventory_path)
    review = read_json(args.review.resolve())
    if inventory.get("qa_helper_sha256") != digest(Path(__file__)):
        raise ValueError("QA helper changed since automated inspection")
    if review.get("inventory_sha256") != digest(inventory_path):
        raise ValueError("review is not bound to this exact QA inventory")
    if (inventory.get("figure_count") != 32 or len(inventory.get("figures", [])) != 32
            or inventory.get("table_count") != 6 or len(inventory.get("tables", [])) != 6):
        raise ValueError("QA inventory is incomplete")
    if inventory.get("status") != "automated_checks_passed_visual_review_pending":
        raise ValueError("automated inspection did not pass")
    run, rendered, renderer = (Path(inventory[k]) for k in ("run", "rendered", "renderer"))
    verify_lineage(run, rendered, renderer)
    for key, source in (("run_manifest_sha256", run / "manifest.json"),
                        ("run_completion_sha256", run / "completion.json"),
                        ("lineage_sha256", rendered / "lineage.json"),
                        ("renderer_sha256", renderer)):
        if inventory[key] != digest(source):
            raise ValueError(f"QA source changed: {key}")
    for check in inventory["figures"]:
        name = check["name"]
        for key, path in (("pdf_sha256", rendered / f"{name}.pdf"),
                          ("png_sha256", rendered / f"{name}.png"),
                          ("page_render_sha256", qa_dir / check["page_render"])):
            if check[key] != digest(path):
                raise ValueError(f"QA input changed: {name}/{key}")
    for table in inventory["tables"]:
        if table["csv_sha256"] != digest(rendered / f"{table['name']}.csv"):
            raise ValueError(f"QA input changed: {table['name']}.csv")
    for sheet in inventory["contact_sheets"]:
        if sheet["sha256"] != digest(qa_dir / sheet["file"]):
            raise ValueError(f"contact sheet changed: {sheet['file']}")
    reviewer = review.get("reviewer_name")
    if not isinstance(reviewer, str) or not reviewer.strip() or review.get("attestation") != ATTESTATION:
        raise ValueError("a named reviewer and exact visual-review attestation are required")
    try:
        reviewed_at = datetime.fromisoformat(review["reviewed_at_utc"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("a valid timezone-aware review timestamp is required") from exc
    if reviewed_at.tzinfo is None or reviewed_at.utcoffset() is None:
        raise ValueError("review timestamp needs a timezone")
    rows = review.get("figures")
    if not isinstance(rows, list) or [r.get("name") for r in rows] != [f["name"] for f in inventory["figures"]]:
        raise ValueError("review must address all 32 figures in inventory order")
    for row in rows:
        if row.get("verdict") not in {"pass", "fail"}:
            raise ValueError(f"figure has no explicit verdict: {row['name']}")
        if row["verdict"] == "fail" and not str(row.get("issue", "")).strip():
            raise ValueError(f"failed figure needs an issue: {row['name']}")
    status = "passed" if all(row["verdict"] == "pass" for row in rows) else "failed"
    test_only = read_json(run / "manifest.json").get("test_only") is True
    if test_only:
        status = f"synthetic_test_only_{status}"
    result = {"schema_version": 1, "visual_qa_status": status, "reviewer_name": reviewer.strip(),
              "reviewed_at_utc": reviewed_at.isoformat(), "attestation": ATTESTATION,
              "inventory_sha256": digest(inventory_path), "review_sha256": digest(args.review.resolve()),
              "figure_count": 32, "figures": rows, "table_count": 6,
              "tables": [{"name": t["name"], "csv_sha256": t["csv_sha256"]} for t in inventory["tables"]],
              "test_only": test_only,
              "source_lineage_sha256": inventory["lineage_sha256"],
              "source_run_completion_sha256": inventory["run_completion_sha256"]}
    output = qa_dir / "visual_qa_receipt.json"
    write_once(output, result)
    print(f"Write-once visual QA receipt: {output} ({status})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare", help="check 32 figure pairs and build review images")
    for name in ("run", "rendered", "renderer", "qa-dir"):
        prep.add_argument(f"--{name}", type=Path, required=True)
    prep.add_argument("--dpi", type=int, default=130)
    review = commands.add_parser("receipt", help="issue receipt from fully completed review form")
    review.add_argument("--qa-dir", type=Path, required=True)
    review.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        if not 72 <= args.dpi <= 300:
            parser.error("--dpi must be 72 to 300")
        prepare(args)
    else:
        receipt(args)


if __name__ == "__main__":
    main()
