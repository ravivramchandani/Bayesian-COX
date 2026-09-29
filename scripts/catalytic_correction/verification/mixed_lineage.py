"""Read-only mixed-outcome resolution; scientific work is an injected callback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from science_verification import STATUSES
from verification_io import Pins, canonical, child, require, seal

FIT_ACTIONS = {"fit_changed_inputs", "fit_changed_inputs_reuse_tuning", "retune_then_fit_changed_inputs"}
OPERATIONS = {"reuse_original_outcome", "fit_corrected_inputs", "retain_corrected_input_failure"}
EVIDENCE = "post_hoc_rank_conditioned_correction_after_original_failures_known"


def traces(cell: dict[str, Any], root: Path, pins: Pins) -> tuple[dict[str, str], dict[str, str]]:
    """Bind all reference/orphan bytes; no available failed-chain file is dropped."""
    identity = cell["cell_id"]
    referenced: dict[str, str] = {}
    for attempt in cell.get("fit_attempts", []):
        for trace in attempt.get("traces", {}).values():
            filename = trace["filename"]
            require(Path(filename).name == filename, "trace basename differs")
            name = f"traces/{identity}/{filename}"
            require(name not in referenced, "trace has duplicate owners")
            referenced[name] = trace["sha256"]
            pins.bind(child(root, name), trace["sha256"])
    orphaned = {}
    directory = child(root, f"traces/{identity}")
    if directory.exists():
        from verification_io import safe, sha
        for path in directory.rglob("*"):
            safe(path)
            require(path.is_file() or path.is_dir(), "trace namespace has an unsafe node")
            if path.is_file():
                name = str(path.relative_to(root))
                if name not in referenced:
                    digest = sha(path)
                    pins.bind(path, digest)
                    orphaned[name] = digest
    return referenced, orphaned


def source_evidence(cell: dict[str, Any], root: Path, evidence: dict[str, Any],
                    manifest_sha: str, pins: Pins) -> tuple[dict[str, str], dict[str, str]]:
    """Require fresh immutable original source proof for every resolved outcome."""
    require(not child(root, f"claims/{cell['cell_id']}.json").exists(), "original owner still active")
    require(evidence["original_cell_id"] == cell["cell_id"]
            and evidence["original_manifest_sha256"] == manifest_sha
            and evidence["cell_content_sha256"] == cell["cell_content_sha256"]
            and evidence["status"] == cell["status"], "original source proof identity differs")
    pins.bind(child(root, f"cells/{cell['cell_id']}.json"), evidence["cell_byte_sha256"])
    reference, orphan = traces(cell, root, pins)
    require(reference == evidence["referenced_trace_sha256"]
            and orphan == evidence["unreferenced_trace_sha256"], "source proof drops changed/reference/orphan traces")
    return reference, orphan


def resolve_record(*, record: dict[str, Any], original: dict[str, Any], decision: dict[str, Any],
                   manifest_sha: str, freeze_sha: str, definition_sha: str, input_witness_sha: str,
                   original_root: Path, corrected_root: Path, pins: Pins,
                   terminal_header: dict[str, Any]) -> dict[str, Any]:
    """Resolve one exact outcome without copying or changing an original cell.

    A terminal input error creates only an explicitly derived reducer view:
    it is not a newly executed fit, accepted metric or fabricated diagnostic.
    """
    identity = original["cell_id"]
    require(record["original_cell_id"] == decision["original_cell_id"] == identity
            and record["corrected_manifest_sha256"] == manifest_sha
            and record["correction_freeze_sha256"] == freeze_sha
            and record["definition_content_sha256"] == definition_sha
            and record["input_witness_sha256"] == input_witness_sha
            and record["evidence_status"] == EVIDENCE
            and record["decision"] == decision
            and record["operation"] in OPERATIONS, "mixed outcome/freeze/input decision binding differs")
    require(record["source_evidence"] == decision["source_evidence"], "recorded source evidence differs from its original decision")
    require(record["source_evidence"] is not None or record["operation"] == "retain_corrected_input_failure",
            "reused/new fit has no finished original source evidence")
    pins.artifacts(corrected_root, record["artifacts"])
    operation, action = record["operation"], decision["action"]
    result: dict[str, Any] = {"operation": operation, "original_cell_id": identity,
        "original_raw_record_preserved": True, "scientific_status": record["scientific_status"]}
    if operation == "reuse_original_outcome":
        reference = record["original_reference"]
        require(action == "reuse_original_outcome" and not record["fit_dispatched"]
                and not record["newly_executed_fit"] and record["fit_seconds"] == 0
                and reference == {"logical_root": "original_extension_run", "path": f"cells/{identity}.json",
                                  "sha256": record["source_evidence"]["cell_byte_sha256"],
                                  "cell_content_sha256": original["cell_content_sha256"]}
                and record["scientific_status"] == original["status"], "reused outcome is not exact original success/failure")
        return {**result, "cell": original, "trace_root": original_root, "derived_analysis_view": False}
    if operation == "retain_corrected_input_failure":
        require(action == "retain_input_failure" and not record["fit_dispatched"]
                and not record["newly_executed_fit"] and record["fit_seconds"] == 0
                and record["scientific_status"] == "not_fit_input_failure"
                and record["original_reference"] is None
                and record["failure_contexts"] == decision["generator_failures"]
                and bool(record["failure_contexts"]), "terminal input failure fabricates execution")
        view = {**terminal_header, "cell_id": identity, "evidence_status": "post_hoc_extension",
                "status": "failed", "seconds": 0.0, "error_type": "CorrectiveInputFailure",
                "message": "No corrected fit: frozen corrective generator input failed; see mixed lineage",
                "fit_attempts": [], "fit_checks": [], "derived_corrective_input_failure_view": True,
                "corrective_failure_contexts": record["failure_contexts"]}
        view["cell_content_sha256"] = canonical(view)
        return {**result, "cell": view, "trace_root": None, "derived_analysis_view": True}
    require(action in FIT_ACTIONS and record["fit_dispatched"] is True and record["newly_executed_fit"] is True
            and record["child_exit_code"] == 0 and record["scientific_status"] in STATUSES,
            "changed fit lacks actual successful child invocation")
    reference = record["corrected_cell"]
    require(reference["logical_root"] == "corrected_fit_run"
            and reference["path"] == f"attempts/{identity}/cells/{identity}.json", "corrected raw cell path differs")
    path = child(corrected_root, reference["path"])
    cell = pins.json(path, reference["sha256"], field="cell_content_sha256")
    require(cell["cell_id"] == identity and cell["cell_content_sha256"] == reference["cell_content_sha256"]
            and cell["status"] == record["scientific_status"] and cell["seconds"] == record["fit_seconds"],
            "new raw outcome differs from its correction envelope")
    require(reference["path"] in record["artifacts"]
            and record["artifacts"][reference["path"]]["sha256"] == reference["sha256"],
            "raw cell is absent from full child inventory")
    return {**result, "cell": cell, "trace_root": child(corrected_root, f"attempts/{identity}"),
            "derived_analysis_view": False}


def lineage_envelope(record: dict[str, Any], resolved: dict[str, Any], input_report: dict[str, Any],
                     original_report_sha: str, corrected_report_sha: str | None,
                     raw_bindings: dict[str, Any]) -> dict[str, Any]:
    """Keep compatible reducer cells separate from truthful correction lineage."""
    return seal({"schema_version": 1, "original_cell_id": record["original_cell_id"],
        "evidence_status": EVIDENCE, "operation": record["operation"],
        "corrected_outcome_status": record["scientific_status"], "analysis_status": resolved["cell"]["status"],
        "derived_analysis_view": resolved["derived_analysis_view"], "raw_bindings": raw_bindings,
        "input_verification": input_report, "original_science_report_sha256": original_report_sha,
        "corrected_science_report_sha256": corrected_report_sha,
        "original_record_preserved": True, "new_fit_refit_or_generation_by_verifier": False})
