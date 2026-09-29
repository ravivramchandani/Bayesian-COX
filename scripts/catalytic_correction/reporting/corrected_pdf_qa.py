"""Prepare corrected32-page QA; only an actual named root review can pass it."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    import hashlib
    _initial = argparse.ArgumentParser(add_help=False)
    _initial.add_argument("--request", type=Path, required=True)
    _initial.add_argument("--request-sha256", required=True)
    _args, _remaining = _initial.parse_known_args()
    if hashlib.sha256(_args.request.read_bytes()).hexdigest() != _args.request_sha256:
        raise RuntimeError("request byte pin differs")
    _request = json.loads(_args.request.read_text())
    _receipt_path = Path(_request["preparation_receipt"]["path"])
    if hashlib.sha256(_receipt_path.read_bytes()).hexdigest() != _request["preparation_receipt"]["sha256"]:
        raise RuntimeError("preparation receipt byte pin differs")
    _receipt = json.loads(_receipt_path.read_text())
    _own = Path(__file__).absolute().parent
    _required_implementation = {"support_core.py", "reporting.py", "corrected_pdf_qa.py",
                                "generate_corrected_reporting.py", "summarize_corrected_claims.py",
                                "replay_corrected_reporting.py"}
    if set(_receipt["implementation_source_sha256"]) != _required_implementation:
        raise RuntimeError("reporting/QA implementation scope differs")
    for _name, _digest in _receipt["implementation_source_sha256"].items():
        if Path(_name).name != _name or hashlib.sha256((_own / _name).read_bytes()).hexdigest() != _digest:
            raise RuntimeError("reporting/QA source bytes differ")
    sys.path.insert(0, str(_own))

import support_core as core  # noqa: E402


def render_state(request: dict[str, Any], mixed: dict[str, Any], deps: dict[str, Any],
                 snapshot: core.Snapshot) -> dict[str, Any]:
    """Bind both unchanged render lineages and all32 figure/six table bytes."""
    root = core.safe(Path(request["roots"]["rendered"]))
    lineage = snapshot.read("rendered/lineage.json", root / "lineage.json")
    correction = snapshot.read("rendered/mixed_correction_lineage.json", root / "mixed_correction_lineage.json", field="content_sha256")
    renderer = core.safe(Path(request["files"]["renderer"]["path"]))
    adapter = core.safe(Path(request["files"]["renderer_adapter"]["path"]))
    snapshot.capture("inputs/renderer", renderer, core.RENDERER_SHA)
    snapshot.capture("inputs/renderer_adapter", adapter, core.RENDER_ADAPTER_SHA)
    core.require(request["files"]["renderer"]["sha256"] == core.RENDERER_SHA
                 and request["files"]["renderer_adapter"]["sha256"] == core.RENDER_ADAPTER_SHA, "reviewed presentation source differs")
    completion_sha = mixed["completion_sha256"]
    capture_sha = request["files"]["source_capture"]["sha256"]
    original_sha = snapshot.bindings["rendered/lineage.json"]["sha256"]
    core.require(lineage["source_completion_sha256"] == completion_sha
                 and lineage["source_manifest_sha256"] == mixed["completion"]["manifest_sha256"]
                 and lineage["renderer_sha256"] == core.RENDERER_SHA
                 and lineage["evidence_status"] == "post_hoc_extension"
                 and lineage["actual_visual_review"] == "pending; creation does not constitute QA",
                 "original renderer lineage does not preserve separate actual review")
    core.require(correction["evidence_status"] == core.EVIDENCE and correction["mixed_completion_sha256"] == completion_sha
                 and correction["actual_verifier_capture_sha256"] == capture_sha
                 and correction["original_renderer_sha256"] == core.RENDERER_SHA
                 and correction["adapter_sha256"] == core.RENDER_ADAPTER_SHA
                 and correction["original_renderer_lineage_sha256"] == original_sha
                 and correction["actual_visual_review"] == "pending; rendering is not QA"
                 and correction["programme_complete"] is False, "mixed correction lineage differs")
    names, tables = deps["roster"].expected_names(), deps["roster"].TABLE_SOURCES
    core.require([row["name"] for row in lineage["figures"]] == names and len(names) == 32
                 and [row["name"] for row in lineage["tables"]] == [name for name, _ in tables], "frozen render roster differs")
    wanted = {name + suffix for name in names for suffix in (".pdf", ".png")} | {
        name + ".csv" for name, _ in tables} | {"lineage.json", "mixed_correction_lineage.json"}
    core.require({p.name for p in root.iterdir()} == wanted, "exact72-file corrected render inventory differs")
    source_map = {**mixed["completion"]["cell_sha256"], **mixed["completion"]["aggregate_sha256"]}
    aggregate_map = {name: "aggregates/" + name for name in ("paired_families.json", "rq2_effects.json", "decision_curves.json")}
    core.require(correction["aggregate_source_mapping"] == aggregate_map, "mixed render aggregate namespace differs")
    for row in lineage["figures"]:
        name = row["name"]
        expected = deps["reporting"].inventory_path  # Path safety remains delegated below.
        if name.startswith("decision_"):
            sources = ["decision_curves.json"]
        elif name.startswith("paired_"):
            sources = ["paired_families.json"]
        elif name.startswith("rq2_"):
            sources = ["rq2_effects.json"]
        else:
            dataset, setting = next((d, s) for d, s in deps["roster"].COHORT_SETTINGS
                                    if name in (f"{d}_{s}_ibs", f"{d}_{s}_calibration"))
            sources = sorted(path for path in mixed["completion"]["cell_sha256"]
                             if Path(path).stem.startswith(dataset + "__" + setting + "__") and Path(path).stem.endswith("__full"))
        core.require(row["source_files"] == sources and bool(sources) and row["visual_review"] == "pending", "figure sources/review differ")
        for source in sources:
            core.require(aggregate_map.get(source, source) in source_map, "figure source absent from mixed certificate")
            expected(mixed["root"], aggregate_map.get(source, source))
        for extension in ("pdf", "png"):
            snapshot.capture("rendered/" + name + "." + extension, root / (name + "." + extension), row[extension + "_sha256"])
    for row, (name, sources) in zip(lineage["tables"], tables, strict=True):
        core.require(row["source_files"] == sources, "table logical source list differs")
        snapshot.capture("rendered/" + name + ".csv", root / (name + ".csv"), row["csv_sha256"])
    source_bindings = {"mixed_completion_sha256": completion_sha, "original_renderer_lineage_sha256": original_sha,
        "mixed_correction_lineage_sha256": snapshot.bindings["rendered/mixed_correction_lineage.json"]["sha256"],
        "renderer_sha256": core.RENDERER_SHA, "renderer_adapter_sha256": core.RENDER_ADAPTER_SHA,
        "actual_verifier_capture_sha256": capture_sha,
        "qa_helper_sha256": core.sha_bytes(Path(__file__).read_bytes())}
    return {"root": root, "lineage": lineage, "correction": correction, "names": names,
            "tables": tables, "source_bindings": source_bindings}


def review_rows(review: dict[str, Any], names: list[str], inventory_sha: str) -> tuple[str, str, list[dict[str, Any]]]:
    """Require an actual named root attestation and every explicit pass/fail verdict."""
    core.require(review["inventory_sha256"] == inventory_sha and review.get("reviewer_role") == "root"
                 and isinstance(review.get("reviewer_name"), str) and bool(review["reviewer_name"].strip())
                 and review["attestation"] == "I examined every rendered PDF page at full size and the indexed contact sheets.",
                 "actual named root full-page/contact review is required")
    stamp = core.timestamp(review["reviewed_at_utc"])
    rows = review["figures"]
    core.require(isinstance(rows, list) and [row["name"] for row in rows] == names, "all32 review verdicts required in order")
    for row in rows:
        core.require(row["verdict"] in {"pass", "fail"}, "pending or absent visual verdict")
        core.require(row["verdict"] != "fail" or isinstance(row.get("issue"), str) and bool(row["issue"].strip()),
                     "failed figure requires an explicit issue")
    return review["reviewer_name"].strip(), stamp, rows


def preserved_inventory(qa: Path, state: dict[str, Any], snapshot: core.Snapshot) -> dict[str, Any]:
    """Verify prepared pages/contacts/table bytes; never render or inspect visually."""
    inventory = snapshot.read("qa/qa_inventory.json", qa / "qa_inventory.json", field="content_sha256")
    snapshot.read("qa/review_template.json", qa / "review_template.json", field="content_sha256")
    core.require(inventory["status"] == "corrected_automated_checks_passed_visual_review_pending"
                 and inventory["source_bindings"] == state["source_bindings"]
                 and inventory["figure_count"] == 32 and inventory["table_count"] == 6
                 and inventory["tables"] == state["lineage"]["tables"], "prepared corrected QA lineage differs")
    names = state["names"]
    core.require([row["name"] for row in inventory["figures"]] == names, "QA32-page roster differs")
    pages = []
    for index, (check, figure) in enumerate(zip(inventory["figures"], state["lineage"]["figures"], strict=True), 1):
        core.require(all(check[key] == figure[key] for key in ("name", "source_files", "pdf_sha256", "png_sha256")), "QA figure lineage differs")
        relative = f"page_renders/{index:02d}_{check['name']}.png"
        core.require(check["page_render"] == relative, "full-page render path differs")
        snapshot.capture("qa/" + relative, core.child(qa, relative), check["page_render_sha256"])
        pages.append(Path(relative).name)
    core.require({p.name for p in (qa / "page_renders").iterdir()} == set(pages), "full-page render inventory differs")
    sheets = [f"contact_sheets/sheet_{index:02d}.png" for index in range(1, 5)]
    core.require([row["file"] for row in inventory["contact_sheets"]] == sheets, "four indexed contact sheets required")
    for row in inventory["contact_sheets"]:
        snapshot.capture("qa/" + row["file"], core.child(qa, row["file"]), row["sha256"])
    core.require({p.name for p in (qa / "contact_sheets").iterdir()} == {Path(name).name for name in sheets}, "contact-sheet inventory differs")
    return inventory


def verify_visual(request: dict[str, Any], mixed: dict[str, Any], deps: dict[str, Any], snapshot: core.Snapshot) -> dict[str, Any]:
    """Preserve a passed actual review on source or restore; no new inspection claim."""
    state = render_state(request, mixed, deps, snapshot)
    qa = core.safe(Path(request["roots"]["qa"]))
    inventory = preserved_inventory(qa, state, snapshot)
    core.require(inventory["test_only"] is False, "synthetic QA cannot certify production")
    review = snapshot.read("qa/review.json", qa / "review.json", field="content_sha256")
    receipt = snapshot.read("qa/visual_qa_receipt.json", qa / "visual_qa_receipt.json", field="content_sha256")
    reviewer, stamp, rows = review_rows(review, state["names"], snapshot.bindings["qa/qa_inventory.json"]["sha256"])
    core.require(receipt["visual_qa_status"] == "passed" and receipt["test_only"] is False
                 and receipt["source_bindings"] == state["source_bindings"]
                 and receipt["inventory_sha256"] == review["inventory_sha256"]
                 and receipt["review_sha256"] == snapshot.bindings["qa/review.json"]["sha256"]
                 and receipt["reviewer_name"] == reviewer and receipt["reviewed_at_utc"] == stamp
                 and receipt["reviewer_role"] == "root" and receipt["attestation"] == review["attestation"]
                 and receipt["figures"] == rows and all(row["verdict"] == "pass" for row in rows)
                 and receipt["figure_count"] == 32 and receipt["table_count"] == 6
                 and receipt["tables"] == [{"name": row["name"], "csv_sha256": row["csv_sha256"]} for row in inventory["tables"]],
                 "passed source-bound named root visual review missing")
    allowed = {"qa_inventory.json", "review_template.json", "review.json", "visual_qa_receipt.json", "page_renders", "contact_sheets"}
    core.require({p.name for p in qa.iterdir()} == allowed, "QA root inventory has missing/foreign files")
    return {"status": "preserved_corrected_visual_qa_transfer_verified",
            "visual_qa_receipt_sha256": snapshot.bindings["qa/visual_qa_receipt.json"]["sha256"],
            "source_bindings": state["source_bindings"], "figure_count": 32, "table_count": 6,
            "page_render_count": 32, "contact_sheet_count": 4,
            "actual_visual_review_preserved": True, "new_visual_approval_conferred": False}


def prepare(request: dict[str, Any], output: Path, mixed: dict[str, Any], deps: dict[str, Any],
            snapshot: core.Snapshot, *, dpi: int = 130, invoke: Any = subprocess.run) -> dict[str, Any]:
    """Create only automated32-page/four-contact evidence and a blank review form."""
    core.require(type(dpi) is int and 72 <= dpi <= 300, "DPI must be72..300")
    state = render_state(request, mixed, deps, snapshot)
    core.require(Path(request["roots"]["qa"]).absolute() == output.absolute(), "explicit new QA role differs from output")
    immutable = [Path(value) for name, value in request["roots"].items() if name != "qa"] + [Path(__file__).absolute().parent]
    snapshot.recheck()
    core.new_directory(output, immutable)
    (output / "page_renders").mkdir()
    records, qa = [], deps["qa"]
    for index, figure in enumerate(state["lineage"]["figures"], 1):
        name = figure["name"]
        pdf, png = state["root"] / (name + ".pdf"), state["root"] / (name + ".png")
        metadata = qa.poppler_metadata(pdf)
        raster = qa.png_metadata(png, metadata["boxes_pt"]["CropBox"])
        relative = f"page_renders/{index:02d}_{name}.png"
        invoke(("pdftoppm", "-f", "1", "-l", "1", "-r", str(dpi), "-png", "-singlefile", str(pdf),
                str(output / relative[:-4])), check=True, capture_output=True, text=True)
        records.append({"name": name, "pdf_sha256": figure["pdf_sha256"], "png_sha256": figure["png_sha256"],
                        "pdf": metadata, "png": raster, "page_render": relative,
                        "page_render_sha256": core.sha_bytes((output / relative).read_bytes()),
                        "page_render_size": qa.png_metadata(output / relative), "source_files": figure["source_files"]})
    sheets = qa.contact_sheets(output, records)
    core.require(len(records) == 32 and len(sheets) == 4, "automated render scope differs")
    inventory = core.seal({"schema_version": 1, "status": "corrected_automated_checks_passed_visual_review_pending",
        "source_bindings": state["source_bindings"], "dpi": dpi, "figure_count": 32, "table_count": 6,
        "figures": records, "tables": state["lineage"]["tables"], "contact_sheets": sheets,
        "test_only": request["test_only"], "actual_visual_review": "pending; automated checks are not visual inspection"})
    snapshot.recheck()
    core.write_new(output / "qa_inventory.json", inventory)
    template = core.seal({"schema_version": 1, "inventory_sha256": core.sha_bytes((output / "qa_inventory.json").read_bytes()),
        "reviewer_name": "", "reviewer_role": "root", "reviewed_at_utc": "", "attestation": "",
        "figures": [{"name": name, "verdict": "pending", "issue": ""} for name in state["names"]]})
    core.write_new(output / "review_template.json", template)
    snapshot.recheck()
    return {"status": inventory["status"], "figure_count": 32, "contact_sheet_count": 4,
            "visual_qa_passed": False, "actual_named_root_review": "pending"}


def issue_receipt(request: dict[str, Any], mixed: dict[str, Any], deps: dict[str, Any], snapshot: core.Snapshot) -> dict[str, Any]:
    """Issue a receipt from the supplied actual completed review; never create verdicts."""
    state = render_state(request, mixed, deps, snapshot)
    qa = core.safe(Path(request["roots"]["qa"]))
    inventory = preserved_inventory(qa, state, snapshot)
    core.require({p.name for p in qa.iterdir()} == {"qa_inventory.json", "review_template.json", "page_renders", "contact_sheets"},
                 "choose untouched QA evidence before receipt publication")
    review = core.supplied(request, "review", snapshot)
    reviewer, stamp, rows = review_rows(review, state["names"], snapshot.bindings["qa/qa_inventory.json"]["sha256"])
    status = "passed" if all(row["verdict"] == "pass" for row in rows) else "failed"
    if inventory["test_only"]:
        status = "synthetic_test_only_" + status
    receipt = core.seal({"schema_version": 1, "visual_qa_status": status, "reviewer_name": reviewer, "reviewer_role": "root",
        "reviewed_at_utc": stamp, "attestation": review["attestation"],
        "inventory_sha256": snapshot.bindings["qa/qa_inventory.json"]["sha256"],
        "review_sha256": request["files"]["review"]["sha256"], "source_bindings": state["source_bindings"],
        "figure_count": 32, "table_count": 6, "figures": rows,
        "tables": [{"name": row["name"], "csv_sha256": row["csv_sha256"]} for row in inventory["tables"]],
        "test_only": inventory["test_only"], "programme_complete": False})
    snapshot.recheck()
    core.write_bytes_new(qa / "review.json", Path(request["files"]["review"]["path"]).read_bytes())
    core.write_new(qa / "visual_qa_receipt.json", receipt)
    snapshot.recheck()
    return receipt


def main() -> None:
    """Explicit prepare/receipt/verify; actual rc0 capture remains external."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("prepare", "receipt", "verify"))
    for name in ("request", "python"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dpi", type=int, default=130)
    args = parser.parse_args()
    core.runtime(args.python)
    snapshot = core.Snapshot()
    request = snapshot.read("invocation/request.json", args.request, args.request_sha256, field="content_sha256")
    core.require(request["status"] == "corrected_visual_qa_inputs_bound" and request["test_only"] is False, "production QA request required")
    core.bind_preparation(request, snapshot)
    deps = core.dependencies(snapshot, qa_render=args.operation == "prepare")
    mixed = core.load_mixed(request, snapshot, deps["reporting"])
    if args.operation == "prepare":
        core.require(args.output is not None, "new QA output required")
        result = prepare(request, args.output, mixed, deps, snapshot, dpi=args.dpi)
    elif args.operation == "receipt":
        result = issue_receipt(request, mixed, deps, snapshot)
    else:
        result = verify_visual(request, mixed, deps, snapshot)
    snapshot.recheck()
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
