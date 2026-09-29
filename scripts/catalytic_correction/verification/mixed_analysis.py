"""Deep mixed-grid analysis adapter with injectable science/input implementations."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from bound_lineage import verify_observations
from mixed_lineage import lineage_envelope, resolve_record, source_evidence, traces
from science_verification import (
    comparison_counts,
    original_comparison,
    verify_science_cell,
)
from verification_gates import ORIGINAL_MANIFEST
from verification_io import (
    Pins,
    canonical,
    checkpoint,
    child,
    read,
    require,
    seal,
    sha,
    write_new,
)

PENDING = ["corrected_rendering_and_visual_qa", "corrected_selected_reproduction",
           "corrected_reporting_sidecar_and_final_claim_review", "corrected_private_package_fresh_restore_replay"]


def verify_runtime_metadata(runtime: dict[str, Any], interpreter: dict[str, Any], request: dict[str, Any],
                            argv: list[str], original_environment: dict[str, Any], numeric: dict[str, Any]) -> None:
    """Bind historical child runtime paths as metadata for portable replay."""
    require(runtime["locked_interpreter_samefile"] is True and interpreter["locked_interpreter_samefile"] is True
            and runtime["requested_locked_python"] == request["locked_python"] == argv[0]
            and runtime["observed_executable"] == interpreter["observed_executable"]
            and all(Path(value).is_absolute() and ".." not in Path(value).parts for value in (
                runtime["requested_locked_python"], runtime["observed_executable"]))
            and runtime["numeric_thread_environment"] == numeric
            and set(numeric) == {"OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"}
            and all(value == "1" for value in numeric.values())
            and interpreter["status"] == "exact_lock_versions_match"
            and interpreter["observed_python"] == original_environment["python"]
            and interpreter["observed_dependencies"] == original_environment["dependencies"]
            and interpreter["observed_dependency_set_sha256"] == original_environment["dependency_set_sha256"]
            == canonical(interpreter["observed_dependencies"])
            and interpreter["frozen_environment_sha256"] == canonical(original_environment),
            "actual child interpreter/runtime differs; historical paths are compared as metadata, not reopened")


def document(path: Path, value: dict[str, Any], *, replay: bool, sealed: bool = True) -> str:
    """Publish or exactly replay an unchanged deterministic scientific document."""
    desired = seal(value) if sealed else value
    if replay or path.exists():
        observed = read(path) if sealed else json.loads(path.read_text())
        require(observed == desired, "existing scientific document differs: " + path.name)
    elif sealed:
        checkpoint(path, value)
    else:
        write_new(path, desired)
    return sha(path)


def verify_child(record: dict[str, Any], resolved: dict[str, Any], input_proof: dict[str, Any],
                 gates: Any, pins: Pins) -> dict[str, Any]:
    """Require actual rc0 and exact child/log/trace inventory, never leftovers alone."""
    root, identity = gates.roots["corrected_run"], record["original_cell_id"]
    child_receipt = pins.json(child(root, record["child_receipt_path"]), record["artifacts"][record["child_receipt_path"]]["sha256"])
    invocation = pins.json(child(root, record["invocation_path"]), record["artifacts"][record["invocation_path"]]["sha256"])
    observed = pins.json(child(root, record["observations_path"]), record["artifacts"][record["observations_path"]]["sha256"])
    expected_parent = f"attempts/{identity}"
    require(record["child_receipt_path"] == expected_parent + "/child_receipt.json"
            and record["invocation_path"] == expected_parent + "/invocation.json"
            and record["observations_path"] == expected_parent + "/observations.json", "child artifact paths differ")
    actual_files = set()
    attempt = child(root, expected_parent)
    for path in attempt.rglob("*"):
        from verification_io import safe
        safe(path)
        require(path.is_file() or path.is_dir(), "child namespace node differs")
        if path.is_file():
            actual_files.add(str(path.relative_to(root)))
    require(actual_files == set(record["artifacts"]), "child inventory drops partial/log/orphan files")
    cell = resolved["cell"]
    require(invocation["operation"] == "isolated_original_cell_child" and invocation["exit_code"] == 0
            and invocation["launch_error"] is None and invocation["wall_seconds"] == record["child_wall_seconds"]
            and set(invocation["numeric_thread_environment"]) == {"OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                                                               "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"}
            and all(value == "1" for value in invocation["numeric_thread_environment"].values()),
            "actual successful original-cell child invocation required")
    for name in ("stdout", "stderr"):
        filename = "stdout.log" if name == "stdout" else "stderr.log"
        require(invocation[name] == record["artifacts"][expected_parent + "/" + filename], "actual child log binding differs")
    request_path = attempt / "request.json"
    request = pins.json(request_path, record["artifacts"][expected_parent + "/request.json"]["sha256"])
    argv = invocation["argv"]
    require(len(argv) == 8 and argv[1:3] == ["-I", "-B"] and Path(argv[3]).name == "fit_child.py"
            and argv[4] == "--request" and Path(argv[5]).name == "request.json" and argv[6] == "--request-sha256"
            and argv[7] == record["artifacts"][expected_parent + "/request.json"]["sha256"],
            "original child invocation argv differs")
    require(request["original_cell_id"] == identity and request["freeze_sha256"] == gates.hashes["freeze"]
            and request["manifest_sha256"] == gates.hashes["manifest"]
            and request["action"] == input_proof["decision"]["action"]
            and request["source_evidence"] == record["source_evidence"]
            and request["implementation_source_sha256"] == gates.documents["freeze"]["implementation_source_sha256"],
            "actual child request binds different reviewed inputs")
    require(child_receipt["status"] == "original_cell_delegated_with_verified_corrected_inputs"
            and child_receipt["original_cell_id"] == identity
            and child_receipt["corrected_manifest_sha256"] == gates.hashes["manifest"]
            and child_receipt["scientific_status"] == cell["status"]
            and child_receipt["action"] == input_proof["decision"]["action"]
            and child_receipt["input_witness_sha256"] == record["input_witness_sha256"]
            and child_receipt["original_seed_namespace"] == input_proof["ledger"]
            and child_receipt["cell"] == record["artifacts"][record["corrected_cell"]["path"]]
            and child_receipt["observations"] == record["artifacts"][record["observations_path"]]
            and child_receipt["full_environment_verification"] == gates.preflight_manifest["environment_verification"],
            "actual child receipt differs from raw outcome/input/source evidence")
    runtime = child_receipt["actual_process_runtime_verification"]
    interpreter = child_receipt["supplemental_interpreter_version_verification"]
    verify_runtime_metadata(runtime, interpreter, request, argv, gates.original["environment"], invocation["numeric_thread_environment"])
    inputs = child_receipt["full_current_execution_input_verification"]
    require(inputs["status"] == "current_complete_inputs_match_corrected_witness"
            and inputs["input_witness_sha256"] == record["input_witness_sha256"]
            and inputs["definition_content_sha256"] == gates.documents["definition"]["content_sha256"]
            and inputs["required_role_count"] == input_proof["summary"]["role_count"]
            and inputs["corrected_role_sha256"] == {name: value["corrected_sha256"] for name, value in
                input_proof["witness"]["fit_witness"]["roles"].items()}
            and inputs["content_sha256"] == canonical({key: value for key, value in inputs.items() if key != "content_sha256"}),
            "execution did not bind every corrected input role")
    environment_invocation = pins.json(attempt / "environment_invocation.json",
                                       record["artifacts"][expected_parent + "/environment_invocation.json"]["sha256"])
    require(environment_invocation["operation"] == "fresh_original_259_package_environment_verification"
            and environment_invocation["exit_code"] == 0
            and environment_invocation["source_sha256"] == gates.original["input_sha256"]["scripts/verify_environment.py"]
            and environment_invocation["stdout"] == record["artifacts"][expected_parent + "/environment.stdout.json"]
            and environment_invocation["stderr"] == record["artifacts"][expected_parent + "/environment.stderr.log"],
            "child actual full environment verification missing/different")
    require(json.loads((attempt / "environment.stdout.json").read_text()) == gates.preflight_manifest["environment_verification"],
            "child stored complete environment report differs")
    return verify_observations(observed, cell, input_proof["decision"], input_proof["contexts"],
                               input_proof["ledger"], input_proof["candidates"])


def execute_verified(gates: Any, science: Any, input_backend: Any, output: Path, pins: Pins,
                     implementation: dict[str, Any], *, replay: bool = False) -> dict[str, Any]:
    """Deep-check all original/new outcomes and delegate only the frozen reducers.

    This seam is exercised with fictional injected implementations in synthetic
    tests. Production calls use the explicitly pinned concrete implementations.
    No function samples, refits, generates proposals or chooses a new estimand.
    """
    jobs, roots = science.jobs, gates.roots
    ids = [job.cell_id for job in jobs]
    require(ids == [entry["original_cell_id"] for entry in gates.documents["inventory"]["entries"]], "whole mixed grid ordering differs")
    source_summary = gates.summary()
    manifest = {"schema_version": 1, "evidence_status": "post_hoc_rank_conditioned_correction_after_original_failures_known",
                "status": "mixed_verification_input_manifest", "source_bindings": source_summary,
                "implementation_source_sha256": implementation, "planned_fits": len(ids),
                "plan": science.manifest["plan"], "run_config": science.config,
                "original_production_commit": "119476fef55b1eeb690527f234c1423440720d45",
                "analysis_source_commit": "8551d326b02bfe88915cfd9eb50c6ca8e5690e3a"}
    manifest_sha = document(output / "manifest.json", manifest, replay=replay)
    cells, comparisons, cell_hashes, lineage_hashes, check_hashes, pilot_entries = [], [], {}, {}, {}, []
    for job, entry in zip(jobs, gates.documents["inventory"]["entries"], strict=True):
        identity = job.cell_id
        record_path = roots["corrected_run"] / "cells" / f"{identity}.json"
        record_digest = sha(record_path)
        record = pins.json(record_path, record_digest)
        original_path = roots["original_run"] / "cells" / f"{identity}.json"
        original_digest = sha(original_path)
        original = pins.json(original_path, original_digest, field="cell_content_sha256")
        proof = input_backend.verify(job, entry, record)
        pilot_entries.append({"decision": proof["decision"], "selection_scope": proof["summary"].get("selection_scope"),
                              "generator_contexts": proof["summary"].get("generator_contexts")})
        original_references, original_orphans = source_evidence(original, roots["original_run"], proof["original_source_evidence"], ORIGINAL_MANIFEST, pins)
        original_report = verify_science_cell(original, job, trace_root=roots["original_run"], referenced=original_references,
            orphaned=original_orphans, config=science.config, backend=science, pins=pins)
        original_report_sha = document(output / "checks/original" / f"{identity}.json", original_report, replay=replay)
        check_hashes[f"checks/original/{identity}.json"] = original_report_sha
        resolved = resolve_record(record=record, original=original, decision=proof["decision"],
            manifest_sha=gates.hashes["manifest"], freeze_sha=gates.hashes["freeze"],
            definition_sha=gates.documents["definition"]["content_sha256"], input_witness_sha=entry["input_witness_sha256"],
            original_root=roots["original_run"], corrected_root=roots["corrected_run"], pins=pins,
            terminal_header=proof["terminal_header"])
        corrected_report_sha = None
        if record["operation"] == "fit_corrected_inputs":
            require(identity in gates.documents["manifest"]["pilot_cells"] or gates.pilot_review is not None,
                    "nonpilot changed fit has no actual existing scale-up review")
            observations = verify_child(record, resolved, proof, gates, pins)
            reference, orphan = traces(resolved["cell"], resolved["trace_root"], pins)
            checked = verify_science_cell(resolved["cell"], job, trace_root=resolved["trace_root"], referenced=reference,
                orphaned=orphan, config=science.config, backend=science, pins=pins)
            corrected_report_sha = document(output / "checks/corrected" / f"{identity}.json", {**checked,
                "execution_observation_checks": observations}, replay=replay)
            check_hashes[f"checks/corrected/{identity}.json"] = corrected_report_sha
        elif resolved["derived_analysis_view"]:
            science.identity(resolved["cell"], job)
        cell = resolved["cell"]
        cell_hashes[f"cells/{identity}.json"] = document(output / "cells" / f"{identity}.json", cell, replay=replay, sealed=False)
        envelope = lineage_envelope(record, resolved, proof["summary"], original_report_sha, corrected_report_sha,
            {"original_cell_sha256": original_digest, "corrected_envelope_sha256": record_digest,
             "corrected_raw_cell_sha256": record.get("corrected_cell", {}).get("sha256"),
             "input_witness_sha256": entry["input_witness_sha256"]})
        lineage_hashes[f"lineage/{identity}.json"] = document(output / "lineage" / f"{identity}.json",
            {key: value for key, value in envelope.items() if key != "content_sha256"}, replay=replay)
        comparisons.append(original_comparison(original, cell, record["operation"], proof["decision"]["changed_roles"]))
        cells.append(cell)
        print(json.dumps({"stage": "mixed_deep_verification", "original_cell_id": identity,
                          "checked": len(cells), "scheduled": len(ids), "operation": record["operation"],
                          "status": cell["status"]}, sort_keys=True), flush=True)
    input_backend.validate_pilot_scope(pilot_entries)
    references = science.references(roots["primary"], roots["sampler"], roots["robustness"])
    reference_sha = document(output / "reference_verification.json", references["summary"], replay=replay)
    aggregates = science.aggregate(cells, references)
    aggregate_hashes = {"aggregates/" + name: document(output / "aggregates" / name, value, replay=replay, sealed=False)
                        for name, value in aggregates.items()}
    require(set(aggregate_hashes) == {"aggregates/paired_families.json", "aggregates/rq2_effects.json", "aggregates/decision_curves.json"},
            "frozen aggregate output scope differs")
    accounting_sha = document(output / "comparison_accounting.json", {"schema_version": 1,
        "counts": comparison_counts(comparisons), "cells": comparisons,
        "by_dataset_setting_model": [{"dataset": dataset, "setting": setting, "model": model,
            "scope": "all_planned_conditions_for_this_dataset_setting_model",
            "original": dict(Counter(row["original_status"] for row in comparisons if row["original_cell_id"] in selected)),
            "corrected_view": dict(Counter(row["corrected_view_status"] for row in comparisons if row["original_cell_id"] in selected))}
            for (dataset, setting, model), selected in sorted(group_ids(cells).items())],
        "by_dataset_setting_model_condition": [{"dataset": dataset, "setting": setting, "model": model, "condition": condition,
            "original": dict(Counter(row["original_status"] for row in comparisons if
                (row["dataset"], row["setting"], row["model"], row["condition"]) == (dataset, setting, model, condition))),
            "corrected_view": dict(Counter(row["corrected_view_status"] for row in comparisons if
                (row["dataset"], row["setting"], row["model"], row["condition"]) == (dataset, setting, model, condition)))}
            for dataset, setting, model, condition in sorted({(cell["dataset"], cell["setting"], cell["model_key"], cell["condition"]) for cell in cells})],
        "all_original_findings_retained_separately": True,
        "unchanged_primary_negative_findings": references["summary"]}, replay=replay)
    render_sha = document(output / "render_input.json", {"schema_version": 1,
        "status": "verified_mixed_render_input_ready; rendering_and_visual_qa_pending",
        "renderer_logical_source": "analysis855/scripts/render_extensions.py",
        "renderer_source_sha256": science.source_pins["files"]["analysis"]["scripts/render_extensions.py"],
        "cell_sha256": cell_hashes, "aggregate_sha256": aggregate_hashes,
        "lineage_sha256": lineage_hashes, "mixed_manifest_sha256": manifest_sha,
        "adapter_policy": "renderer_reads_verified_compatible_cells; no_trace_copy_or_original_certificate",
        "evidence_status": "post_hoc_rank_conditioned_correction_after_original_failures_known",
        "pending_gates": PENDING}, replay=replay)
    pins.recheck()
    science.verify_module_origins()
    completion = {"schema_version": 1, "status": "mixed_original_corrected_grid_deep_verified_and_frozen_analysis_recomputed",
        "evidence_status": "post_hoc_rank_conditioned_correction_after_original_failures_known",
        "planned_logical_cells": len(ids), "verified_logical_cells": len(cells),
        "source_bindings": source_summary, "manifest_sha256": manifest_sha,
        "cell_sha256": cell_hashes, "aggregate_sha256": aggregate_hashes, "lineage_sha256": lineage_hashes,
        "check_sha256": check_hashes, "reference_verification_sha256": reference_sha,
        "comparison_accounting_sha256": accounting_sha, "render_input_sha256": render_sha,
        "original_status_counts": comparison_counts(comparisons)["original_status_counts"],
        "mixed_view_status_counts": comparison_counts(comparisons)["corrected_status_counts"],
        "operation_counts": comparison_counts(comparisons)["operation_counts"],
        "initial_invocation_metadata_sha256": {name: sha(output / name) for name in (
            "invocation.json", "environment.stdout.json", "environment.stderr.log", "environment_invocation.json")},
        "own_mixed_lineage_certificate": True, "original855_certificate_inherited": False,
        "original_and_primary_negative_findings_preserved": True,
        "stored_diagnostics_recomputed_and_complete_forecasts_rescored": True,
        "reference_verification_scope": "delegated_existing_frozen_baseline_verifiers",
        "new_generator_svd_optimizer_mcmc_or_fit_invoked": False,
        "new_estimand_multiplicity_or_diagnostic_gate": False,
        "scientific_method_approval_conferred_by_verifier": False,
        "programme_complete": False, "reporting_visual_qa_certified": False,
        "selected_reproduction_certified": False, "release_restore_certified": False, "pending_gates": PENDING}
    document(output / "completion.json", completion, replay=replay)
    # Inputs are rechecked after completion publication too: cleanup/inventory
    # failures cannot yield a successful CLI claim merely because bytes exist.
    pins.recheck()
    return completion


def group_ids(cells: list[dict[str, Any]]) -> dict[tuple[str, str, str], set[str]]:
    """Partition complete scope for factual status accounting only."""
    groups: dict[tuple[str, str, str], set[str]] = {}
    for cell in cells:
        groups.setdefault((cell["dataset"], cell["setting"], cell["model_key"]), set()).add(cell["cell_id"])
    return groups
