"""Reuse frozen descriptive scope/math on the true mixed certificate and own QA."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import corrected_pdf_qa as visual
import support_core as core


def baseline_inputs(request: dict[str, Any], snapshot: core.Snapshot, deps: dict[str, Any]) -> tuple[Any, dict[str, Any]]:
    """Bind unchanged baseline negatives before calling its pinned fact routine."""
    reporting, claims = deps["reporting"], deps["claims"]
    primary = reporting.primary_refs(core.safe(Path(request["roots"]["primary"])), snapshot)
    roots = {}
    for name, (manifest_sha, completion_sha) in claims.BASELINE_PINS.items():
        root = core.safe(Path(request["roots"][name]))
        roots[name] = root
        snapshot.read("baseline/" + name + "/manifest.json", root / "manifest.json", manifest_sha)
        completion = snapshot.read("baseline/" + name + "/completion.json", root / "completion.json", completion_sha,
                                   field="completion_content_sha256")
        for relative, digest in sorted(completion["aggregate_sha256"].items()):
            snapshot.read("baseline/" + name + "/" + relative, core.child(root, relative), digest)
        if name == "primary":
            core.require(completion["status_counts"] == {"complete": 430, "failed_diagnostics": 20}, "primary negative findings changed")
    explanation_path = core.safe(Path(request["files"]["explanation"]["path"]))
    core.require(request["files"]["explanation"]["sha256"] == claims.EXPLANATION_SHA256, "frozen RQ3 explanation differs")
    snapshot.read("baseline/explanation.json", explanation_path, claims.EXPLANATION_SHA256)
    args = SimpleNamespace(**roots, explanation=explanation_path)
    result = claims.unchanged_baseline(args)
    core.require(result["primary_status_counts"] == {"complete": 430, "failed_diagnostics": 20}, "primary status promoted")
    snapshot.recheck()
    return primary, result


def prerequisite_state(request: dict[str, Any], snapshot: core.Snapshot, deps: dict[str, Any]) -> dict[str, Any]:
    """Require whole mixed data, selected proof and actual passed visual evidence."""
    core.require(request["schema_version"] == 1 and request["test_only"] is False
                 and request["status"] in {"corrected_reporting_source_inputs_bound", "corrected_reporting_read_only_replay_request"},
                 "bound actual corrected reporting inputs required")
    mixed = core.load_mixed(request, snapshot, deps["reporting"])
    reproduction = core.validate_reproduction(request, mixed, snapshot)
    qa = visual.verify_visual(request, mixed, deps, snapshot)
    primary, baseline = baseline_inputs(request, snapshot, deps)
    source_bindings = {"mixed_completion_sha256": mixed["completion_sha256"],
        "selection_sha256": reproduction["selection_sha256"], "selected_pass_sha256": reproduction["selected_pass_sha256"],
        "visual_qa_receipt_sha256": qa["visual_qa_receipt_sha256"],
        "mixed_correction_lineage_sha256": qa["source_bindings"]["mixed_correction_lineage_sha256"]}
    for name, digest in source_bindings.items():
        core.require(request[name] == digest, "current reporting prerequisite digest differs: " + name)
    return {"mixed": mixed, "reproduction": reproduction, "visual": qa, "primary": primary,
            "baseline": baseline, "source_bindings": source_bindings}


def build(state: dict[str, Any], deps: dict[str, Any], snapshot: core.Snapshot) -> tuple[dict[str, Any], dict[str, bytes]]:
    """Produce exactly1625 ratios/123 descriptive rows with frozen complete-pair CIs."""
    frozen, claims = deps["reporting"], deps["claims"]
    mixed = state["mixed"]
    refs = {identity: frozen.CellRef("mixed", ref.relative, ref.record) for identity, ref in mixed["refs"].items()}
    families = mixed["aggregates"]["paired_families.json"]
    summary = claims.summarize_families(families)
    report = frozen.build_report(refs, state["primary"], deps["scope"], families, summary,
                                 deps["interval"].nadeau_bengio_paired_effect)
    report.update(evidence_status=core.EVIDENCE, report_kind="corrected_mixed_descriptive_reporting_sidecar",
                  source_bindings=state["source_bindings"], original_primary_negative_findings_preserved=True,
                  original_vs_corrected_accounting=mixed["accounting"], selected_reproduction=state["reproduction"],
                  unchanged_baseline=state["baseline"], new_inferential_promotion=False,
                  completion_scope="descriptive reporting only; private package/fresh deep restore/publication remain unassessed")
    report["formal_clinical_prior_family"]["logical_source"] = "mixed/aggregates/paired_families.json"
    output = {"dimension_ratios.csv": frozen.csv_bytes(report["dimension_ratios"], frozen.DIMENSION_FIELDS),
              "descriptive_catalytic_pairs.csv": frozen.csv_bytes(report["descriptive_catalytic_pairs"], frozen.COMPARISON_FIELDS),
              "report.json": core.json_bytes(report)}
    lineage = core.seal({"schema_version": 1, "evidence_status": core.EVIDENCE,
        "source_roles": snapshot.portable(), "source_binding_sha256": core.canonical(snapshot.portable()),
        "source_bindings": state["source_bindings"], "scope_sha256": core.DEPENDENCY_PINS["scope.json"],
        "interval_source_sha256": core.DEPENDENCY_PINS["frozen_repeated_cv.py"],
        "frozen_reporting_helper_sha256": core.DEPENDENCY_PINS["frozen_reporting.py"],
        "logical_cell_roles": {"mixed": "mixed_verified/cells", "primary": "previously_released_primary/cells"},
        "artifacts_sha256": {name: core.sha_bytes(raw) for name, raw in sorted(output.items())},
        "new_estimand_test_family_or_gate": False,
        "policy": "portable logical byte roles; relocated request paths are invocation metadata only"})
    output["lineage.json"] = core.json_bytes(lineage)
    return report, output


def artifact_bindings(artifacts: dict[str, bytes]) -> dict[str, Any]:
    """Return exact four deterministic-artifact byte and length pins."""
    core.require(set(artifacts) == core.ARTIFACTS, "reporting artifact scope differs")
    return {name: {"sha256": core.sha_bytes(raw), "bytes": len(raw)} for name, raw in sorted(artifacts.items())}


def publish(output: Path, artifacts: dict[str, bytes], receipt: dict[str, Any], immutable: list[Path]) -> None:
    """Write one new five-file output; no final receipt precedes complete artifacts."""
    core.new_directory(output, immutable)
    for name, raw in sorted(artifacts.items()):
        core.write_bytes_new(output / name, raw)
        core.require((output / name).read_bytes() == raw, "new reporting byte-roundtrip differs")
    core.write_new(output / "receipt.json", receipt)
    core.require({p.name for p in output.iterdir()} == core.ARTIFACTS | {"receipt.json"}, "five-file reporting inventory differs")


def verify_existing(root: Path, artifacts: dict[str, bytes], state: dict[str, Any], helper_sha: str,
                    snapshot: core.Snapshot) -> dict[str, Any]:
    """Recompute and compare all four bytes, preserving the actual generation receipt."""
    root = core.safe(root)
    core.require(root.is_dir() and {p.name for p in root.iterdir()} == core.ARTIFACTS | {"receipt.json"}, "existing exact five-file sidecar required")
    for name, raw in sorted(artifacts.items()):
        observed = snapshot.capture("invocation/preserved_sidecar/" + name, root / name, core.sha_bytes(raw))
        core.require(observed == raw, "deterministic sidecar differs: " + name)
    raw = snapshot.capture("invocation/preserved_sidecar/receipt.json", root / "receipt.json")
    receipt = core.strict_json(raw)
    core.content(receipt)
    core.require(receipt["status"] == "corrected_reporting_sidecar_generated" and receipt["operation"] == "generate"
                 and receipt["source_bindings"] == state["source_bindings"]
                 and receipt["artifacts"] == artifact_bindings(artifacts)
                 and receipt["source_binding_sha256"] == core.canonical(snapshot.portable())
                 and receipt["helper_sha256"] == helper_sha and receipt["scientific_completion_certified"] is False
                 and receipt["test_only"] is False, "original corrected generation receipt differs")
    return {"status": "corrected_reporting_source_replay_verified", "source_bindings": state["source_bindings"],
            "sidecar_receipt_sha256": core.sha_bytes(raw), "deterministic_artifacts_compared": 4,
            "deterministic_bytes_reproduced_exactly": True, "no_new_fit_generator_optimizer_or_inference": True,
            "scientific_completion_certified": False, "programme_complete": False}


def claim_summary(state: dict[str, Any], deps: dict[str, Any]) -> dict[str, Any]:
    """Reuse frozen factual claim reducers, retaining all original negatives separately."""
    claims, mixed = deps["claims"], state["mixed"]
    return {"schema_version": 1, "status": "corrected_factual_claim_inputs_verified", "evidence_status": core.EVIDENCE,
        "source_bindings": state["source_bindings"], "overall_programme_completion": "not_assessed; root-owned private fresh restore/publication pending",
        "original_primary_negative_findings_preserved": True, "new_inferential_promotion": False,
        "cell_accounting": claims.summarize_cells(mixed["cells"]),
        "original_status_counts": mixed["completion"]["original_status_counts"],
        "mixed_view_status_counts": mixed["completion"]["mixed_view_status_counts"],
        "operation_counts": mixed["completion"]["operation_counts"],
        "original_vs_corrected_accounting": mixed["accounting"],
        "comparison_families": claims.summarize_families(mixed["aggregates"]["paired_families.json"]),
        "rq2": claims.summarize_rq2(mixed["aggregates"]["rq2_effects.json"]),
        "decision_curves": claims.summarize_dca(mixed["aggregates"]["decision_curves.json"]),
        "selected_reproduction": state["reproduction"], "preserved_visual_qa": state["visual"],
        "unchanged_baseline": state["baseline"], "no_new_fit_generator_optimizer_or_inference": True,
        "interpretation": "factual stored coverage and original claims only; no new significance or programme certificate"}
