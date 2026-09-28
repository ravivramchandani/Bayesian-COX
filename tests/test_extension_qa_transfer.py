"""Hash-binding unit fixtures only; these are not rendered thesis evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import runpy
from pathlib import Path

import pytest

source = Path(__file__).with_name("qa_transfer.py")
if not source.is_file():
    source = Path(__file__).resolve().parents[1] / "scripts/extension_release/qa_transfer.py"
module = runpy.run_path(str(source))
ATTESTATION, TABLE_SOURCES = module["ATTESTATION"], module["TABLE_SOURCES"]
expected_names, verify_visual_transfer = module["expected_names"], module["verify_visual_transfer"]


def digest(path: Path) -> str:
    """Return the SHA-256 of a file."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    """Write indented, key-sorted JSON to ``path``."""
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


@pytest.fixture
def evidence(tmp_path):
    """Build a small, self-consistent set of run, rendered and visual-QA files with matching hashes."""
    run, rendered, qa = (tmp_path / name for name in ("run", "rendered", "qa"))
    for root in (run, rendered, qa):
        root.mkdir()
    for name in ("page_renders", "contact_sheets"):
        (qa / name).mkdir()
    helper, renderer = tmp_path / "helper.py", tmp_path / "renderer.py"
    helper.write_text("# unit fixture helper\n")
    renderer.write_text("# unit fixture renderer\n")
    write(run / "manifest.json", {"planned_fits": 1625, "evidence_status": "post_hoc_extension"})
    write(run / "completion.json", {"planned": 1625, "stored": 1625, "verification": "deep",
                                   "evidence_status": "post_hoc_extension", "manifest_sha256": digest(run / "manifest.json")})
    figures, checks = [], []
    for index, name in enumerate(expected_names(), 1):
        for suffix in ("pdf", "png"):
            (rendered / f"{name}.{suffix}").write_bytes(f"unit fixture {name}.{suffix}".encode())
        page = f"page_renders/{index:02d}_{name}.png"
        (qa / page).write_bytes(f"unit fixture {page}".encode())
        figure = {"name": name, "pdf_sha256": digest(rendered / f"{name}.pdf"),
                  "png_sha256": digest(rendered / f"{name}.png"), "source_files": ["paired_families.json"],
                  "visual_review": "pending"}
        figures.append(figure)
        checks.append({k: v for k, v in figure.items() if k != "visual_review"} | {
            "page_render": page, "page_render_sha256": digest(qa / page),
            "pdf": {"pages": 1}, "png": {"width": 1000, "height": 800},
            "page_render_size": {"width": 1300, "height": 1040}})
    tables = []
    for name, sources in TABLE_SOURCES:
        (rendered / f"{name}.csv").write_text("unit_fixture\n1\n")
        tables.append({"name": name, "source_files": sources, "csv_sha256": digest(rendered / f"{name}.csv")})
    lineage = {"evidence_status": "post_hoc_extension", "actual_visual_review": "pending; creation does not constitute QA",
               "source_manifest_sha256": digest(run / "manifest.json"),
               "source_completion_sha256": digest(run / "completion.json"), "renderer_sha256": digest(renderer),
               "figures": figures, "tables": tables}
    write(rendered / "lineage.json", lineage)
    sheets = []
    for index in range(1, 5):
        relative = f"contact_sheets/sheet_{index:02d}.png"
        (qa / relative).write_bytes(f"unit fixture {relative}".encode())
        sheets.append({"file": relative, "sha256": digest(qa / relative)})
    inventory = {"schema_version": 1, "status": "automated_checks_passed_visual_review_pending",
                 "run": "/original-host/nonexistent/run", "rendered": "/original-host/nonexistent/rendered",
                 "renderer": "/original-host/nonexistent/renderer.py", "qa_helper_sha256": digest(helper),
                 "run_manifest_sha256": digest(run / "manifest.json"),
                 "run_completion_sha256": digest(run / "completion.json"),
                 "lineage_sha256": digest(rendered / "lineage.json"), "renderer_sha256": digest(renderer),
                 "dpi": 130, "figure_count": 32, "figures": checks, "table_count": 6,
                 "tables": tables, "contact_sheets": sheets}
    write(qa / "qa_inventory.json", inventory)
    review = {"schema_version": 1, "inventory_sha256": digest(qa / "qa_inventory.json"),
              "reviewer_name": " Unit fixture reviewer ", "reviewed_at_utc": "2026-09-28T03:00:00Z",
              "attestation": ATTESTATION,
              "figures": [{"name": name, "verdict": "pass", "issue": ""} for name in expected_names()]}
    write(qa / "review.json", review)
    receipt = {"schema_version": 1, "visual_qa_status": "passed", "test_only": False,
               "inventory_sha256": digest(qa / "qa_inventory.json"), "review_sha256": digest(qa / "review.json"),
               "reviewer_name": "Unit fixture reviewer", "reviewed_at_utc": "2026-09-28T03:00:00+00:00",
               "attestation": ATTESTATION, "figure_count": 32, "figures": review["figures"], "table_count": 6,
               "tables": [{"name": t["name"], "csv_sha256": t["csv_sha256"]} for t in tables],
               "source_lineage_sha256": inventory["lineage_sha256"],
               "source_run_completion_sha256": inventory["run_completion_sha256"]}
    write(qa / "visual_qa_receipt.json", receipt)
    return {"qa": qa, "rendered": rendered, "run": run, "helper": helper, "renderer": renderer}


def verify(evidence):
    """Run the transfer verifier on the fixture's evidence."""
    return verify_visual_transfer(evidence["qa"], evidence["rendered"], evidence["run"],
                                  qa_helper=evidence["helper"], renderer=evidence["renderer"])


def mutate(evidence, filename, change, *, rebind=False):
    """Edit one QA JSON file in place.

    With ``rebind=True``, also recompute the review and receipt hashes, so the
    edit is consistently rehashed and rebound. This tests that the deeper checks still
    catch it.
    """
    qa = evidence["qa"]
    value = json.loads((qa / filename).read_text())
    change(value)
    write(qa / filename, value)
    if not rebind:
        return
    review = json.loads((qa / "review.json").read_text())
    review["inventory_sha256"] = digest(qa / "qa_inventory.json")
    write(qa / "review.json", review)
    receipt = json.loads((qa / "visual_qa_receipt.json").read_text())
    receipt["inventory_sha256"] = digest(qa / "qa_inventory.json")
    receipt["review_sha256"] = digest(qa / "review.json")
    write(qa / "visual_qa_receipt.json", receipt)


def test_relocated_paths_pass_without_opening_original_host(evidence):
    """Evidence moved to new paths still verifies, without reading anything on the original machine."""
    result = verify(evidence)
    assert result["status"] == "preserved_visual_qa_transfer_verified"
    assert (result["figure_count"], result["table_count"], result["page_render_count"], result["contact_sheet_count"]) == (32, 6, 32, 4)
    assert result["visual_review"] == "preserved original receipt; no new visual review claimed"


def test_repeated_validation_is_read_only_and_reproducible(evidence):
    """Running the verifier twice changes no file and gives the same result."""
    parent = evidence["qa"].parent
    before = {str(p.relative_to(parent)): digest(p) for p in parent.rglob("*") if p.is_file()}
    first, second = verify(evidence), verify(evidence)
    after = {str(p.relative_to(parent)): digest(p) for p in parent.rglob("*") if p.is_file()}
    assert first == second
    assert before == after


@pytest.mark.parametrize("filename", ["qa_inventory.json", "review.json", "visual_qa_receipt.json"])
def test_missing_bound_record_is_rejected(evidence, filename):
    """Missing a hash-bound record is rejected."""
    (evidence["qa"] / filename).unlink()
    with pytest.raises(ValueError, match="missing or linked regular file"):
        verify(evidence)


@pytest.mark.parametrize("filename", ["qa_inventory.json", "review.json"])
def test_record_edit_after_receipt_is_rejected(evidence, filename):
    """A record edited after the receipt was issued is rejected."""
    mutate(evidence, filename, lambda value: value.update(unbound_note="changed"))
    with pytest.raises(ValueError, match="hash binding differs"):
        verify(evidence)


@pytest.mark.parametrize("key", ["helper", "renderer"])
def test_code_binding_rejects_changed_helper_or_renderer(evidence, key):
    """A changed QA helper or renderer script breaks the code binding."""
    evidence[key].write_text("# changed code\n")
    with pytest.raises(ValueError, match="QA source binding differs"):
        verify(evidence)


@pytest.mark.parametrize("kind", ["page", "sheet", "pdf", "png", "csv"])
def test_changed_reviewed_artifact_is_rejected(evidence, kind):
    """Changing a reviewed figure or table is rejected."""
    name = expected_names()[0]
    paths = {"page": evidence["qa"] / f"page_renders/01_{name}.png",
             "sheet": evidence["qa"] / "contact_sheets/sheet_01.png",
             "pdf": evidence["rendered"] / f"{name}.pdf", "png": evidence["rendered"] / f"{name}.png",
             "csv": evidence["rendered"] / "fold_metrics.csv"}
    paths[kind].write_bytes(b"changed artifact")
    with pytest.raises(ValueError, match="changed"):
        verify(evidence)


@pytest.mark.parametrize("kind", ["page", "sheet"])
def test_missing_or_extra_review_image_is_rejected(evidence, kind):
    """A missing or unexpected review image is rejected."""
    directory = evidence["qa"] / ("page_renders" if kind == "page" else "contact_sheets")
    next(directory.iterdir()).unlink()
    (directory / "extra.png").write_bytes(b"extra")
    with pytest.raises(ValueError, match="file inventory differs"):
        verify(evidence)


def test_rehashed_inventory_cannot_omit_contact_sheet(evidence):
    """A rehashed inventory still cannot drop the contact sheet."""
    mutate(evidence, "qa_inventory.json", lambda value: value["contact_sheets"].pop(), rebind=True)
    with pytest.raises(ValueError, match="four indexed contact sheets"):
        verify(evidence)


def test_rehashed_inventory_cannot_escape_page_render_directory(evidence):
    """A rehashed inventory cannot point outside the page-render directory."""
    mutate(evidence, "qa_inventory.json", lambda value: value["figures"][0].update(page_render="../escaped.png"), rebind=True)
    with pytest.raises(ValueError, match="page-render path differs"):
        verify(evidence)


def test_rehashed_inventory_cannot_duplicate_figure(evidence):
    """A rehashed inventory cannot list the same figure twice."""
    def duplicate(value):
        """Replace the second figure entry with a copy of the first."""
        value["figures"][1] = copy.deepcopy(value["figures"][0])
    mutate(evidence, "qa_inventory.json", duplicate, rebind=True)
    with pytest.raises(ValueError, match="inventory/order differs"):
        verify(evidence)


@pytest.mark.parametrize("verdict", ["pending", "fail"])
def test_consistently_rebound_nonpass_verdict_is_rejected(evidence, verdict):
    """A review verdict other than pass is rejected, even when every hash binding is refreshed."""
    mutate(evidence, "review.json", lambda value: value["figures"][0].update(verdict=verdict, issue="fixture issue"), rebind=True)
    review = json.loads((evidence["qa"] / "review.json").read_text())
    mutate(evidence, "visual_qa_receipt.json", lambda value: value.update(figures=review["figures"]))
    with pytest.raises(ValueError, match="explicit bound pass verdicts"):
        verify(evidence)


@pytest.mark.parametrize("change", [
    {"reviewer_name": ""}, {"attestation": "I looked at a contact sheet."},
    {"reviewed_at_utc": "2026-09-28T03:00:00"},
])
def test_rebound_missing_attestation_or_aware_timestamp_is_rejected(evidence, change):
    """A review missing its attestation or timestamp time zone is rejected after rehashing."""
    mutate(evidence, "review.json", lambda value: value.update(change), rebind=True)
    receipt_change = {key: value for key, value in change.items()}
    mutate(evidence, "visual_qa_receipt.json", lambda value: value.update(receipt_change))
    with pytest.raises(ValueError, match="attestation|timezone"):
        verify(evidence)


@pytest.mark.parametrize("value", [True, None])
def test_test_only_or_missing_classification_is_rejected(evidence, value):
    """A receipt marked test-only, or missing that classification, is rejected."""
    def change(receipt):
        """Remove the ``test_only`` field, or set it to the parametrised value."""
        if value is None:
            receipt.pop("test_only")
        else:
            receipt["test_only"] = value
    mutate(evidence, "visual_qa_receipt.json", change)
    with pytest.raises(ValueError, match="production visual QA"):
        verify(evidence)


def test_receipt_cannot_omit_one_verdict(evidence):
    """A receipt missing any single figure verdict is rejected."""
    mutate(evidence, "visual_qa_receipt.json", lambda value: value["figures"].pop())
    with pytest.raises(ValueError, match="explicit bound pass verdicts"):
        verify(evidence)


def test_contact_sheet_symlink_is_rejected(evidence):
    """A contact sheet that is a symbolic link is rejected."""
    sheet = evidence["qa"] / "contact_sheets/sheet_01.png"
    copy = evidence["qa"] / "copied_sheet.png"
    copy.write_bytes(sheet.read_bytes())
    sheet.unlink()
    sheet.symlink_to(copy)
    with pytest.raises(ValueError, match="linked regular file"):
        verify(evidence)


def test_rehashed_inventory_cannot_remove_table(evidence):
    """A rehashed inventory cannot drop a table."""
    mutate(evidence, "qa_inventory.json", lambda value: value["tables"].pop(), rebind=True)
    with pytest.raises(ValueError, match="inventory/order differs"):
        verify(evidence)


def test_receipt_table_hash_must_match_retained_inventory(evidence):
    """The receipt's table hash must match the retained inventory."""
    mutate(evidence, "visual_qa_receipt.json", lambda value: value["tables"][0].update(csv_sha256="0" * 64))
    with pytest.raises(ValueError, match="receipt table hashes differ"):
        verify(evidence)


def test_source_completion_changes_are_rejected(evidence):
    """Any change to the source run's completion record is rejected."""
    value = json.loads((evidence["run"] / "completion.json").read_text())
    write(evidence["run"] / "completion.json", value | {"extra": "changed"})
    with pytest.raises(ValueError, match="QA source binding differs"):
        verify(evidence)
