"""Verify preserved extension visual-QA evidence using supplied portable paths."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ATTESTATION = "I examined every rendered PDF page at full size and the indexed contact sheets."
COHORT_SETTINGS = (
    ("gbsg2", "clinical"), ("metabric", "clinical"),
    ("metabric_matched", "clinical"), ("metabric_matched", "expression"),
    ("whas500", "clinical"),
)
FAMILIES = (
    "calibrated_vs_adr032_horseshoe", "catalytic_vs_original_priors",
    "expression_increment", "penalized_vs_original_priors",
)
TABLE_SOURCES = (
    ("fold_metrics", ["cells/*.json"]),
    ("decision_curve_points", ["decision_curves.json"]),
    ("decision_curve_support", ["decision_curves.json"]),
    ("decision_curve_unavailable", ["decision_curves.json"]),
    ("paired_families", ["paired_families.json"]),
    ("rq2_effects", ["rq2_effects.json"]),
)


def expected_names() -> list[str]:
    """Return the fixed figure order used by the retained QA helper."""
    names = [f"{dataset}_{setting}_{kind}" for dataset, setting in COHORT_SETTINGS
             for kind in ("ibs", "calibration")]
    names += [f"decision_{dataset}__{setting}__h{h}" for dataset, setting in COHORT_SETTINGS
              for h in (1, 2, 3)]
    names += [f"paired_{family}" for family in FAMILIES]
    return names + [f"rq2_{dataset}" for dataset in ("gbsg2", "whas500", "metabric")]


def _directory(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        raise ValueError(f"missing or linked directory: {path}")


def _digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"missing or linked regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _read(path: Path) -> dict[str, Any]:
    _digest(path)
    def nonfinite(value: str) -> None:
        raise ValueError(f"non-finite JSON value: {value}")
    value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique_object,
                       parse_constant=nonfinite)
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON mapping: {path}")
    return value


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _ordered(records: Any, names: list[str], label: str) -> list[dict[str, Any]]:
    _require(isinstance(records, list) and all(isinstance(row, dict) for row in records),
             f"invalid {label} rows")
    _require([row.get("name") for row in records] == names, f"{label} inventory/order differs")
    return records


def verify_visual_transfer(qa_dir: Path, rendered: Path, run: Path, *,
                           qa_helper: Path, renderer: Path) -> dict[str, Any]:
    """Bind a preserved passed review to all transferred QA and render bytes.

    This uses supplied paths only. Absolute paths retained inside the inventory
    describe the original review host and are never opened or rewritten.
    No PDF is rendered and no new visual inspection is claimed.
    """
    for root in (qa_dir, rendered, run, qa_dir / "page_renders", qa_dir / "contact_sheets"):
        _directory(root)
    artifacts: dict[str, str] = {}
    def digest(path: Path, key: str) -> str:
        value = _digest(path)
        artifacts[key] = value
        return value

    inventory = _read(qa_dir / "qa_inventory.json")
    review = _read(qa_dir / "review.json")
    receipt = _read(qa_dir / "visual_qa_receipt.json")
    lineage = _read(rendered / "lineage.json")
    manifest, completion = (_read(run / f"{name}.json") for name in ("manifest", "completion"))
    for label, record in (("inventory", inventory), ("review", review), ("receipt", receipt)):
        _require(type(record.get("schema_version")) is int and record["schema_version"] == 1,
                 f"unsupported {label} schema")
    _require(receipt.get("visual_qa_status") == "passed" and receipt.get("test_only") is False
             and manifest.get("test_only", False) is False, "passed production visual QA is absent")
    _require(manifest.get("evidence_status") == completion.get("evidence_status") == "post_hoc_extension"
             and manifest.get("planned_fits") == completion.get("planned") == completion.get("stored") == 1625
             and completion.get("verification") == "deep", "complete post-hoc source marker is absent")
    _require(inventory.get("status") == "automated_checks_passed_visual_review_pending",
             "automated QA checks did not pass")
    _require(lineage.get("evidence_status") == "post_hoc_extension"
             and lineage.get("actual_visual_review") == "pending; creation does not constitute QA",
             "render lineage does not preserve separate visual review")

    bindings = (
        ("run_manifest_sha256", run / "manifest.json", "run/manifest.json"),
        ("run_completion_sha256", run / "completion.json", "run/completion.json"),
        ("lineage_sha256", rendered / "lineage.json", "rendered/lineage.json"),
        ("qa_helper_sha256", qa_helper, "code/qa_helper.py"),
        ("renderer_sha256", renderer, "code/renderer.py"),
    )
    for field, path, key in bindings:
        _require(inventory.get(field) == digest(path, key), f"QA source binding differs: {field}")
    _require(lineage.get("source_manifest_sha256") == inventory["run_manifest_sha256"]
             and completion.get("manifest_sha256") == inventory["run_manifest_sha256"]
             and lineage.get("source_completion_sha256") == inventory["run_completion_sha256"]
             and lineage.get("renderer_sha256") == inventory["renderer_sha256"],
             "lineage source binding differs")
    inventory_hash = digest(qa_dir / "qa_inventory.json", "visual_qa/qa_inventory.json")
    review_hash = digest(qa_dir / "review.json", "visual_qa/review.json")
    receipt_hash = digest(qa_dir / "visual_qa_receipt.json", "visual_qa/visual_qa_receipt.json")
    _require(review.get("inventory_sha256") == receipt.get("inventory_sha256") == inventory_hash
             and receipt.get("review_sha256") == review_hash, "receipt/review hash binding differs")
    _require(receipt.get("source_lineage_sha256") == inventory["lineage_sha256"]
             and receipt.get("source_run_completion_sha256") == inventory["run_completion_sha256"],
             "receipt source binding differs")
    reviewer = review.get("reviewer_name")
    _require(isinstance(reviewer, str) and bool(reviewer.strip())
             and receipt.get("reviewer_name") == reviewer.strip()
             and review.get("attestation") == receipt.get("attestation") == ATTESTATION,
             "named exact visual-review attestation is absent")
    try:
        timestamp = datetime.fromisoformat(review["reviewed_at_utc"].replace("Z", "+00:00"))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ValueError("invalid review timestamp") from exc
    _require(timestamp.tzinfo is not None and timestamp.utcoffset() is not None
             and receipt.get("reviewed_at_utc") == timestamp.isoformat(),
             "review timestamp is unbound or lacks a timezone")

    names = expected_names()
    figures = _ordered(inventory.get("figures"), names, "QA figure")
    rendered_figures = _ordered(lineage.get("figures"), names, "rendered figure")
    verdicts = _ordered(review.get("figures"), names, "review figure")
    _require(receipt.get("figures") == verdicts and all(row.get("verdict") == "pass" for row in verdicts),
             "all 32 explicit bound pass verdicts are required")
    _require(inventory.get("figure_count") == receipt.get("figure_count") == 32,
             "figure count differs")
    pages = [f"{index:02d}_{name}.png" for index, name in enumerate(names, 1)]
    _require({p.name for p in (qa_dir / "page_renders").iterdir()} == set(pages),
             "page-render file inventory differs")
    for extension in ("pdf", "png"):
        _require({p.stem for p in rendered.glob(f"*.{extension}")} == set(names),
                 f"rendered {extension} file inventory differs")
    for index, (check, figure) in enumerate(zip(figures, rendered_figures, strict=True), 1):
        name = check["name"]
        _require(check.get("source_files") == figure.get("source_files")
                 and isinstance(check.get("source_files"), list) and bool(check["source_files"])
                 and figure.get("visual_review") == "pending", f"figure lineage differs: {name}")
        for extension in ("pdf", "png"):
            field, filename = f"{extension}_sha256", f"{name}.{extension}"
            _require(check.get(field) == figure.get(field) == digest(rendered / filename, f"rendered/{filename}"),
                     f"reviewed {extension} changed: {name}")
        relative = f"page_renders/{index:02d}_{name}.png"
        _require(check.get("page_render") == relative, f"page-render path differs: {name}")
        _require(check.get("page_render_sha256") == digest(qa_dir / relative, f"visual_qa/{relative}"),
                 f"reviewed page render changed: {name}")

    table_names = [name for name, _ in TABLE_SOURCES]
    tables = _ordered(inventory.get("tables"), table_names, "QA table")
    _ordered(lineage.get("tables"), table_names, "rendered table")
    _require(tables == lineage["tables"] and inventory.get("table_count") == receipt.get("table_count") == 6,
             "QA table lineage/count differs")
    _require(receipt.get("tables") == [{"name": row["name"], "csv_sha256": row.get("csv_sha256")} for row in tables],
             "receipt table hashes differ")
    _require({p.stem for p in rendered.glob("*.csv")} == set(table_names), "CSV file inventory differs")
    for table, (name, sources) in zip(tables, TABLE_SOURCES, strict=True):
        _require(table.get("source_files") == sources, f"table source lineage differs: {name}")
        _require(table.get("csv_sha256") == digest(rendered / f"{name}.csv", f"rendered/{name}.csv"),
                 f"reviewed table changed: {name}")

    sheets = inventory.get("contact_sheets")
    relatives = [f"contact_sheets/sheet_{index:02d}.png" for index in range(1, 5)]
    _require(isinstance(sheets, list) and all(isinstance(sheet, dict) for sheet in sheets)
             and [sheet.get("file") for sheet in sheets] == relatives, "four indexed contact sheets are required")
    _require({p.name for p in (qa_dir / "contact_sheets").iterdir()} == {Path(p).name for p in relatives},
             "contact-sheet file inventory differs")
    for sheet, relative in zip(sheets, relatives, strict=True):
        _require(sheet.get("sha256") == digest(qa_dir / relative, f"visual_qa/{relative}"),
                 f"reviewed contact sheet changed: {relative}")
    return {"status": "preserved_visual_qa_transfer_verified",
            "visual_review": "preserved original receipt; no new visual review claimed",
            "visual_qa_receipt_sha256": receipt_hash, "qa_inventory_sha256": inventory_hash,
            "review_sha256": review_hash, "figure_count": 32, "table_count": 6,
            "page_render_count": 32, "contact_sheet_count": 4,
            "artifact_sha256": artifacts}
