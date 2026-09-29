"""Account every correction input, validating arithmetic on changed proposals.

Run only after complete preflight, independent first-draw replay and input
inventory. Original kappa gate failures remain terminal optimizer evidence;
formula mismatches and missing proof remain unresolved. No proposal is drawn.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

if __package__:
    from . import bound_arithmetic as bound
    from . import independent_arithmetic as arithmetic
    from . import kappa_observation as observation
    from . import preflight_core as pf
else:
    import bound_arithmetic as bound
    import independent_arithmetic as arithmetic
    import kappa_observation as observation
    import preflight_core as pf

OWN_SOURCES = ("run_arithmetic.py", "bound_arithmetic.py", "independent_arithmetic.py",
               "kappa_observation.py", "preflight_core.py")
TERMINAL = {"terminal_input_failure": "preflight_input_failure",
            "terminal_rank_exhaustion": "preflight_exhausted_rank_cap",
            "terminal_nonrank_error": "preflight_nonrank_failure"}
TERMINAL_PREFLIGHT = {"terminal_input_failure": "input_failure",
                     "terminal_rank_exhaustion": "exhausted_rank_cap",
                     "terminal_nonrank_error": "nonrank_failure"}


def source_bindings() -> dict[str, str]:
    """Bind every executed local arithmetic/support source."""
    return {name: bound.file_hash(Path(__file__).with_name(name)) for name in OWN_SOURCES}


def verify_current_interpreter(interpreter: Path) -> None:
    """Require the arithmetic process itself to use the requested interpreter."""
    arithmetic.require(interpreter.is_absolute() and interpreter.is_file(), "explicit existing locked interpreter required")
    arithmetic.require(interpreter.samefile(Path(sys.executable)),
                       "arithmetic controller interpreter differs from requested locked Python")


def copy_evidence(source: Path, destination: Path, expected_sha: str) -> dict[str, Any]:
    """Keep an exact evidence copy; refuse different bytes on resume."""
    arithmetic.require(bound.file_hash(source) == expected_sha, "source evidence bytes differ")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        arithmetic.require(not destination.is_symlink() and bound.file_hash(destination) == expected_sha,
                           "copied evidence bytes differ")
    else:
        pf.publish_new(destination, lambda stream: stream.write(source.read_bytes()))
    arithmetic.require(bound.file_hash(source) == bound.file_hash(destination) == expected_sha,
                       "evidence changed during copy")
    return pf.artifact_binding(destination)


def calculate_context(inputs: arithmetic.Inputs, source: Path, *, kappa_required: bool,
                      adaptive_required: bool) -> dict[str, Any]:
    """Check base formulas, then one original kappa call when required.

    Every reference comes from the pinned original function definitions. A
    successful base comparison is retained when the original kappa guard
    rejects; adaptive optimum checks are explicitly pending in that case.
    """
    started = time.monotonic()
    reference = arithmetic.load_original_functions(source)
    units = arithmetic.validate_training_units(inputs)
    arithmetic.require(all(row["passed"] for row in units), "training-unit arithmetic differs")
    base = arithmetic.validate_arithmetic(inputs, reference)
    arithmetic.require(base["status"] == "arithmetic_passed", "base arithmetic formula mismatch")
    result: dict[str, Any] = {"status": "arithmetic_verified", "formula_checks": "passed",
        "training_unit_checks": units, "base_arithmetic": base,
        "kappa_required": kappa_required, "original_kappa_status": "not_required",
        "adaptive_status": "not_required", "new_proposals_generated": False,
        "optimizer_invoked": kappa_required}
    if kappa_required:
        enabled = arithmetic.load_original_functions(source, optimizer_enabled=True)
        telemetry: dict[str, Any] = {}
        try:
            kappa, beta = observation.observed_kappa(enabled, inputs, telemetry)
        except Exception as error:
            if not observation.is_original_kappa_gate_failure(error, enabled, telemetry):
                raise
            result.update(status="original_kappa_gate_failed", original_kappa_status="original_gate_failed",
                          adaptive_status="pending_original_kappa_gate_failure" if adaptive_required else "not_required",
                          original_exception={"type": type(error).__name__, "message": str(error)},
                          optimizer_predicate_evidence=telemetry)
        else:
            full = arithmetic.validate_arithmetic(inputs, reference, kappa=float(kappa), beta_hat=beta)
            arithmetic.require(full["status"] == "arithmetic_passed"
                               and full["adaptive_status"] == "checked_supplied_kappa",
                               "checked-optimum arithmetic formula mismatch")
            result.update(original_kappa_status="passed", kappa=float(kappa), beta_hat=beta.tolist(),
                          optimum_arithmetic=full, optimizer_predicate_evidence=telemetry,
                          adaptive_status="checked_supplied_kappa" if adaptive_required else "not_required")
    result["wall_seconds"] = time.monotonic() - started
    return result


def validate_plan(selector: dict[str, Any], completion: dict[str, Any], replay: dict[str, Any],
                  inventory: dict[str, Any], definition: dict[str, Any], *, expected: int = 1650) -> list[dict[str, Any]]:
    """Refuse partial, foreign or duplicate input accounting before optimization."""
    arithmetic.require(selector["status"] == "all1650_context_arithmetic_requirements_accounted"
                       and selector["scheduled_contexts"] == expected
                       and selector["arithmetic_validation_executed"] is False
                       and selector["scientific_method_approved"] is False,
                       "complete independent arithmetic selector required")
    rows, outcomes = selector["entries"], completion["outcomes"]
    identities = [row["context_id"] for row in rows]
    arithmetic.require(len(rows) == len(set(identities)) == expected
                       and identities == [row["context_id"] for row in outcomes]
                       and identities == [row["context_id"] for row in replay["outcomes"]]
                       and completion["scheduled_contexts"] == completion["accounted_contexts"] == expected
                       and replay["scheduled_contexts"] == replay["accounted_contexts"] == expected,
                       "complete ordered context coverage differs")
    if expected == 1650:
        outer = [identity for identity in identities if identity.endswith("::outer")]
        inner = [identity for identity in identities if not identity.endswith("::outer")]
        arithmetic.require(len(outer) == len(inner) == 825
                           and all("__catalytic_wme__" in identity for identity in inner)
                           and all(f"{bound.context_parts(identity)[0]}::inner_{fold:02d}" in identities
                                   for identity in inner for fold in range(1, 4)),
                           "complete825 outer and825 WME inner triplets required")
    arithmetic.require(selector["definition_content_sha256"] == definition["content_sha256"]
                       == replay["definition_content_sha256"] == inventory["definition_content_sha256"],
                       "scientific input definition differs")
    arithmetic.require(completion["status"] == "all_scheduled_contexts_accounted"
                       and replay["status"] == "all1650_independent_first_draw_contexts_accounted"
                       and replay["no_fit_optimizer_mcmc_prediction_or_score_run"] is True,
                       "preflight/replay completion status differs")
    by_identity = {row["context_id"]: row for row in outcomes}
    replay_by_identity = {row["context_id"]: row for row in replay["outcomes"]}
    for row in rows:
        identity = row["context_id"]
        outcome, replay_row = by_identity[identity], replay_by_identity[identity]
        arithmetic.require(row["preflight_receipt_sha256"] == outcome["receipt_sha256"]
                           and row["preflight_receipt_path"] == outcome["receipt_path"]
                           and row["replay_receipt_sha256"] == replay_row["receipt_sha256"]
                           and row["replay_receipt_path"] == replay_row["receipt_path"]
                           and row["arithmetic_executed_or_certified_by_selector"] is False,
                           "selector receipt or scope binding differs")
        status = row["status"]
        arithmetic.require(status in {"changed_accepted_inputs", "unchanged_first_draw", *TERMINAL},
                           "unknown arithmetic requirement status")
        needs_kappa = status == "changed_accepted_inputs" and row["model"] in {"catalytic_fixed", "catalytic_adaptive"}
        expected_checks = (["q_and_gradient", "tau_scaled_identity", "weighted_merged_breslow"]
                           + (["original_kappa_and_adaptive_prior_terms"] if needs_kappa else [])) if status == "changed_accepted_inputs" else []
        arithmetic.require(type(row["requires_kappa_check"]) is bool
                           and row["requires_kappa_check"] == needs_kappa
                           and row["required_checks"] == expected_checks, "required arithmetic checks differ")
        arithmetic.require(row["model"] in {"catalytic_fixed", "catalytic_adaptive", "catalytic_wme"}
                           and f"__{row['model']}__" in identity
                           and row["context"] == bound.context_parts(identity)[1], "arithmetic model/context identity differs")
        if status in {"changed_accepted_inputs", "unchanged_first_draw"}:
            arithmetic.require(outcome["status"] in bound.ACCEPTED
                               and row["original_constructor_array_witnesses"] is not None
                               and row["accepted_constructor_array_witnesses"] is not None,
                               "accepted input constructor witnesses missing")
            arithmetic.require(set(row["original_constructor_array_witnesses"]) ==
                               set(row["accepted_constructor_array_witnesses"]) ==
                               {"synthetic_design", "synthetic_time", "hazard", "time_scale"},
                               "complete constructor array keys required")
            changed = sorted(key for key in row["original_constructor_array_witnesses"]
                             if row["original_constructor_array_witnesses"][key] != row["accepted_constructor_array_witnesses"][key])
            arithmetic.require(changed == row["changed_logical_arrays"]
                               and bool(changed) == (status == "changed_accepted_inputs")
                               and (row["accepted_attempt_index"] == 0) == (status == "unchanged_first_draw"),
                               "changed versus unchanged constructor accounting differs")
        else:
            arithmetic.require(row["accepted_attempt_index"] is None
                               and outcome["status"] == TERMINAL_PREFLIGHT[status]
                               and not row["changed_logical_arrays"], "terminal preflight classification differs")
    return rows


def verify_selector_context(row: dict[str, Any], preflight: dict[str, Any], replay: dict[str, Any]) -> None:
    """Bind selector facts to the actual small preflight and replay receipts."""
    identity = row["context_id"]
    arithmetic.require(preflight["request"]["context_id"] == replay["request"]["context_id"] == identity
                       and replay["context_id"] == identity
                       and replay["request"]["preflight_receipt_sha256"] == row["preflight_receipt_sha256"]
                       and replay["status"] == "independent_original_first_draw_verified",
                       "actual independent context receipt identity differs")
    original = replay["original_replay"]
    accepted = preflight["accepted_attempt_index"]
    arithmetic.require(accepted == row["accepted_attempt_index"], "selector accepted attempt differs from actual receipt")
    arithmetic.require(original.get("array_witnesses") == row["original_constructor_array_witnesses"],
                       "selector original arrays differ from actual independent replay")
    if preflight["attempts"]:
        first = preflight["attempts"][0]
        arithmetic.require(original["status"] == first["status"]
                           and original.get("array_witnesses") == first.get("array_witnesses")
                           and original["seed"] == first["seed"]
                           and original.get("legacy_metadata") == first.get("legacy_metadata"),
                           "actual independent first proposal differs from preflight")
    if accepted is not None:
        arithmetic.require(type(accepted) is int and 0 <= accepted < len(preflight["attempts"]),
                           "actual accepted proposal index invalid")
        first, proposal = preflight["attempts"][0], preflight["attempts"][accepted]
        arithmetic.require(preflight["status"] in bound.ACCEPTED
                           and proposal["status"] == "accepted_original_constructor"
                           and proposal["array_witnesses"] == row["accepted_constructor_array_witnesses"]
                           and original["array_witnesses"] == first["array_witnesses"]
                           and original["status"] == first["status"]
                           and original["seed"] == first["seed"]
                           and original.get("legacy_metadata") == first.get("legacy_metadata")
                           and replay["assessment"]["status"] == "exact_normal_import_first_proposal_identity"
                           and replay["assessment"]["full_constructor_identity_witnessed"] is True
                           and replay["assessment"]["constructor_result"] == first["status"],
                           "actual accepted/first-draw constructor proof differs")
        arithmetic.require((accepted == 0) == (preflight["status"] == "accepted_original_first_draw")
                           == (row["status"] == "unchanged_first_draw"),
                           "actual accepted first/redraw classification differs")
    else:
        arithmetic.require(row["status"] in TERMINAL_PREFLIGHT
                           and preflight["status"] == TERMINAL_PREFLIGHT[row["status"]]
                           and row["accepted_constructor_array_witnesses"] is None,
                           "actual terminal constructor receipt differs")
        expected_assessment = ("exact_original_input_failure" if preflight["status"] == "input_failure" else
                               "exact_original_nonrank_error" if preflight["attempts"][0]["status"] == "nonrank_error" else
                               "exact_normal_import_first_proposal_identity")
        arithmetic.require(replay["assessment"]["status"] == expected_assessment,
                           "actual terminal independent replay assessment differs")
        if preflight["status"] == "input_failure":
            error = preflight["input_error"]
            arithmetic.require(original["status"] == "input_failure"
                               and all(original["error"][key] == error[key] for key in ("type", "message"))
                               and replay["assessment"]["generator_called"] is False
                               and replay["assessment"]["full_constructor_identity_witnessed"] is False,
                               "actual terminal independent input failure differs")
        elif first["status"] == "nonrank_error":
            arithmetic.require(all(original["error"][key] == first["error"][key] for key in ("type", "message"))
                               and replay["assessment"]["generator_called"] is True
                               and replay["assessment"]["full_constructor_identity_witnessed"] is False,
                               "actual terminal independent nonrank failure differs")
        else:
            arithmetic.require(replay["assessment"]["generator_called"] is True
                               and replay["assessment"]["full_constructor_identity_witnessed"] is True
                               and replay["assessment"]["constructor_result"] == first["status"],
                               "actual terminal independent constructor identity differs")


def validate_context_record(record: dict[str, Any], row: dict[str, Any]) -> None:
    """Validate completed checkpoint semantics without repeating an optimizer."""
    required = row["requires_kappa_check"]
    arithmetic.require(record["kappa_required"] is required, "recorded kappa requirement differs")
    if row["status"] == "unchanged_first_draw":
        arithmetic.require(record["status"] == "unchanged_inputs_independently_witnessed"
                           and record["formula_checks"] == record["original_kappa_status"] == "not_required",
                           "unchanged arithmetic checkpoint differs")
        return
    if row["status"] in TERMINAL:
        arithmetic.require(record["status"] == TERMINAL[row["status"]]
                           and record["formula_checks"] == record["original_kappa_status"] == "not_applicable",
                           "terminal arithmetic checkpoint differs")
        return
    arithmetic.require(record["status"] in {"arithmetic_verified", "original_kappa_gate_failed"}
                       and record["formula_checks"] == "passed", "changed arithmetic checkpoint is incomplete")

    def checked(result: dict[str, Any], count: int) -> bool:
        checks = result["checks"]
        return (result["status"] == "arithmetic_passed" and result["check_count"] == len(checks) == count
                and len({check["check"] for check in checks}) == count
                and all(check["passed"] is True for check in checks)
                and result["optimizer_invoked"] is False and result["rank_check_invoked"] is False
                and result["new_proposals_generated"] is False)

    arithmetic.require(checked(record["base_arithmetic"], 56)
                       and record["base_arithmetic"]["adaptive_status"] == "pending_kappa_evidence"
                       and len(record["training_unit_checks"]) == 2
                       and all(check["passed"] is True for check in record["training_unit_checks"]),
                       "base arithmetic checkpoint checks missing or failed")
    if not required:
        arithmetic.require(record["status"] == "arithmetic_verified"
                           and record["original_kappa_status"] == record["adaptive_status"] == "not_required"
                           and record["optimizer_invoked"] is False,
                           "non-Bayesian arithmetic checkpoint differs")
        return
    telemetry = record["optimizer_predicate_evidence"]
    arithmetic.require(telemetry["optimizer_calls"] == 1 and telemetry["optimizer_returned"] is True
                       and telemetry["post_optimization_kernel_observed"] is True
                       and telemetry["additional_optimizer_or_kernel_calls"] is False
                       and telemetry["method"] == "L-BFGS-B" and telemetry["jacobian_argument"] is True
                       and telemetry["options"] == {"gtol": 1e-8, "ftol": 1e-14, "maxiter": 5000, "maxls": 50}
                       and telemetry["post_score_threshold"] == 1e-6 and record["optimizer_invoked"] is True,
                       "original optimizer checkpoint telemetry incomplete")
    rejected = not telemetry["success"] or not telemetry["post_kernel_value_finite"] or telemetry["post_score_threshold_rejected"]
    arithmetic.require(type(telemetry["original_gate_rejected"]) is bool
                       and telemetry["original_gate_rejected"] == rejected, "original guard predicate checkpoint differs")
    if telemetry["maximum_absolute_post_score"] is not None:
        arithmetic.require(telemetry["post_score_threshold_rejected"] ==
                           (telemetry["maximum_absolute_post_score"] > 1e-6), "original score threshold checkpoint differs")
    if record["status"] == "original_kappa_gate_failed":
        arithmetic.require(rejected and record["original_kappa_status"] == "original_gate_failed"
                           and record["original_exception"] == {"type": "RuntimeError",
                               "message": "catalytic kappa optimizer failed: " + telemetry["message"]}
                           and "optimum_arithmetic" not in record
                           and record["adaptive_status"] == ("pending_original_kappa_gate_failure"
                               if row["model"] == "catalytic_adaptive" else "not_required"),
                           "original gate-failure checkpoint is not genuine terminal evidence")
    else:
        arithmetic.require(not rejected and record["original_kappa_status"] == "passed"
                           and checked(record["optimum_arithmetic"], 83)
                           and record["optimum_arithmetic"]["adaptive_status"] == "checked_supplied_kappa"
                           and record["adaptive_status"] == ("checked_supplied_kappa"
                               if row["model"] == "catalytic_adaptive" else "not_required"),
                           "required checked-optimum arithmetic checkpoint missing or failed")


def run(args: argparse.Namespace, *, expected_contexts: int = 1650,
        expected_cells: int = 1625) -> dict[str, Any]:
    """Execute a serial immutable pass; smaller counts are synthetic tests only.

    The production CLI fixes the full1650/1625 counts and offers no reduction.
    """
    verify_current_interpreter(args.python)
    sources = source_bindings()
    completion_path = args.preflight_root / "completion.json"
    replay_path = args.witness_root / "replay/completion.json"
    selector_path = args.witness_root / "arithmetic_selector.json"
    definition_path = args.witness_root / "definition.json"
    documents = {"completion": bound.read_sealed(completion_path, args.completion_sha256),
        "replay": bound.read_sealed(replay_path, args.replay_sha256),
        "selector": bound.read_sealed(selector_path, args.selector_sha256),
        "definition": bound.read_sealed(definition_path, args.definition_sha256),
        "inventory": bound.read_sealed(args.inventory, args.inventory_sha256)}
    completion, replay, selector, definition, inventory = (documents[name] for name in
        ("completion", "replay", "selector", "definition", "inventory"))
    preflight_manifest = bound.read_sealed(args.preflight_root / "manifest.json")
    arithmetic.require(preflight_manifest["content_sha256"] == completion["run_binding_sha256"]
                       and preflight_manifest["original_input_sha256"] == definition["original_input_sha256"]
                       and definition["original_production_commit"] == arithmetic.ORIGINAL_COMMIT,
                       "original source and preflight definition bindings differ")
    for relative, digest in definition["original_input_sha256"].items():
        arithmetic.require(bound.file_hash(bound.safe_path(args.source_checkout, relative)) == digest,
                           "original source/data/lock input bytes differ")
    arithmetic.require(selector["preflight_completion_sha256"] == inventory["preflight_completion_sha256"]
                       == args.completion_sha256
                       and selector["replay_completion_sha256"] == inventory["replay_completion_sha256"] == args.replay_sha256
                       and inventory["arithmetic_selector_sha256"] == args.selector_sha256,
                       "actual selector and complete input inventory hashes differ")
    arithmetic.require(inventory["scheduled_cells"] == len(inventory["entries"]) == expected_cells
                       and len({row["original_cell_id"] for row in inventory["entries"]}) == expected_cells,
                       "complete1625 input inventory required")
    rows = validate_plan(selector, completion, replay, inventory, definition, expected=expected_contexts)
    context_pins = []
    complete_contexts = {row["context_id"]: row for row in completion["outcomes"]}
    replay_contexts = {row["context_id"]: row for row in replay["outcomes"]}
    for row in rows:
        preflight_path = bound.safe_path(args.preflight_root, row["preflight_receipt_path"])
        replay_context_path = bound.safe_path(args.witness_root, row["replay_receipt_path"])
        preflight_record = bound.read_sealed(preflight_path, row["preflight_receipt_sha256"])
        replay_record = bound.read_sealed(replay_context_path, row["replay_receipt_sha256"])
        verify_selector_context(row, preflight_record, replay_record)
        arithmetic.require(preflight_record["status"] == complete_contexts[row["context_id"]]["status"]
                           and preflight_record["content_sha256"] == complete_contexts[row["context_id"]]["receipt_content_sha256"]
                           and replay_record["content_sha256"] == replay_contexts[row["context_id"]]["receipt_content_sha256"],
                           "actual context completion content/status differs")
        arithmetic.require(replay_record["request"]["definition_content_sha256"] == definition["content_sha256"]
                           and preflight_record["request"]["run_binding_sha256"] == completion["run_binding_sha256"],
                           "context scientific definition or preflight run differs")
        context_pins.extend(((preflight_path, row["preflight_receipt_sha256"]),
                             (replay_context_path, row["replay_receipt_sha256"])))
    original_sources = {arithmetic.SOURCE_RELATIVE: arithmetic.ORIGINAL_CATALYTIC_SHA256,
                        **bound.ADDITIONAL_ORIGINAL_SOURCES}
    for relative, digest in original_sources.items():
        arithmetic.require(bound.file_hash(bound.safe_path(args.source_checkout, relative)) == digest,
                           "original initialization/arithmetic source differs")
    environment = subprocess.run([str(args.python), "-B", str(args.source_checkout / "scripts/verify_environment.py"),
        "--lock-file", str(args.source_checkout / "conda-lock.yml"), "--hash-file", str(args.source_checkout / "conda-lock.yml.sha256")],
        capture_output=True, text=True, check=True)
    environment_report = json.loads(environment.stdout)
    arithmetic.require(environment_report == definition["environment_verification"]
                       and environment_report["package_count"] == 259 and environment_report["status"] == "ok",
                       "fresh exact locked arithmetic environment differs")
    manifest = bound.sealed({"schema_version": 1, "kind": "changed_input_arithmetic_accounting",
        "implementation_sources": sources, "original_arithmetic_sources": original_sources,
        "preflight_completion_sha256": args.completion_sha256, "replay_completion_sha256": args.replay_sha256,
        "selector_sha256": args.selector_sha256, "definition_sha256": args.definition_sha256,
        "definition_content_sha256": definition["content_sha256"], "input_inventory_sha256": args.inventory_sha256,
        "scheduled_contexts": expected_contexts, "environment_verification": environment_report,
        "numeric_threads": 1, "workers": 1, "new_proposals_generated": False,
        "paths": {"preflight": str(args.preflight_root), "witness": str(args.witness_root),
                  "inventory": str(args.inventory), "original_source": str(args.source_checkout)}})
    arithmetic.require(args.output.is_absolute() and ".." not in args.output.parts
                       and not any(path.is_symlink() for path in (args.output, *args.output.parents)), "unsafe arithmetic output")
    for path in (args.preflight_root, args.witness_root, args.source_checkout, Path(__file__).parent):
        arithmetic.require(not args.output.is_relative_to(path) and not path.is_relative_to(args.output),
                           "arithmetic output overlaps immutable input/source")
    args.output.mkdir(exist_ok=True)
    manifest_path = args.output / "manifest.json"
    if manifest_path.exists():
        arithmetic.require(bound.read_sealed(manifest_path) == manifest, "arithmetic resume binding differs")
    else:
        arithmetic.require(not any(args.output.iterdir()), "unbound existing arithmetic output")
        bound.publish_new(manifest_path, manifest)
    arithmetic.require(not (args.output / "failure.json").exists(), "prior unresolved arithmetic attempt requires separate reviewed recovery")
    allowed = {"manifest.json", "contexts", "evidence", "selection.json", "controller.claim.json", "accounting.json", "abandoned_claims"}
    arithmetic.require(not ({path.name for path in args.output.iterdir()} - allowed), "unbound arithmetic output entry")
    selection_rows = [{"context_id": row["context_id"], "context_receipt_sha256": row["preflight_receipt_sha256"],
                       "kappa_required": row["requires_kappa_check"],
                       "adaptive_required": row["requires_kappa_check"] and row["model"] == "catalytic_adaptive"}
                      for row in rows if row["status"] == "changed_accepted_inputs"]
    selection = bound.sealed({"schema_version": 1, "kind": "root_requested_arithmetic_contexts",
        "preflight_completion_sha256": args.completion_sha256, "run_binding_sha256": completion["run_binding_sha256"],
        "contexts": selection_rows, "complete_selector_sha256": args.selector_sha256})
    selection_path = args.output / "selection.json"
    if selection_path.exists():
        arithmetic.require(bound.read_sealed(selection_path) == selection, "changed arithmetic selection differs")
    else:
        bound.publish_new(selection_path, selection)
    snapshot = None if not selection_rows else bound.Snapshot(args.preflight_root, args.completion_sha256,
        selection_path, bound.file_hash(selection_path), expected_contexts=expected_contexts)
    selected = {} if snapshot is None else {item[0]["context_id"]: item for item in snapshot.selected}
    artifacts: dict[str, Any] = {}
    outcomes = []
    inputs_bound = [(completion_path, args.completion_sha256), (replay_path, args.replay_sha256),
                    (selector_path, args.selector_sha256), (definition_path, args.definition_sha256),
                    (args.inventory, args.inventory_sha256)]
    with pf.Claim(args.output / "controller.claim.json", manifest["content_sha256"], recover_stale=args.recover_stale_claims):
        for ordinal, (path, digest) in enumerate(inputs_bound):
            name = f"evidence/input_{ordinal:02d}.json"
            artifacts[name] = copy_evidence(path, args.output / name, digest)
        for row in rows:
            identity = row["context_id"]
            name = "contexts/" + bound.context_output_name(identity)
            record_path = args.output / name
            evidence = []
            for role, root, relative, digest in (
                ("preflight", args.preflight_root, row["preflight_receipt_path"], row["preflight_receipt_sha256"]),
                ("replay", args.witness_root, row["replay_receipt_path"], row["replay_receipt_sha256"])):
                target = f"evidence/{role}_{bound.context_output_name(identity)}"
                artifacts[target] = copy_evidence(bound.safe_path(root, relative), args.output / target, digest)
                evidence.append(digest)
            request = {"context_id": identity, "arithmetic_manifest_content_sha256": manifest["content_sha256"],
                       "selector_entry_sha256": bound.canonical_hash(row)}
            inputs, lineage = None, None
            if row["status"] == "changed_accepted_inputs":
                inputs, lineage = snapshot.load(selected[identity])
            if record_path.exists():
                record = bound.read_sealed(record_path)
                arithmetic.require(record["request"] == request, "arithmetic context resume differs")
                arithmetic.require(record["evidence_sha256"] == evidence, "arithmetic context evidence differs")
                if lineage is not None:
                    arithmetic.require(record["accepted_input_lineage"] == lineage,
                                       "resumed arithmetic accepted-array lineage differs")
            else:
                record_path.parent.mkdir(exist_ok=True)
                try:
                    if row["status"] == "changed_accepted_inputs":
                        result = calculate_context(inputs, args.source_checkout,
                            kappa_required=row["requires_kappa_check"], adaptive_required=row["model"] == "catalytic_adaptive")
                        result["accepted_input_lineage"] = lineage
                    elif row["status"] == "unchanged_first_draw":
                        result = {"status": "unchanged_inputs_independently_witnessed", "formula_checks": "not_required",
                                  "kappa_required": False, "original_kappa_status": "not_required"}
                    else:
                        result = {"status": TERMINAL[row["status"]], "formula_checks": "not_applicable",
                                  "kappa_required": False, "original_kappa_status": "not_applicable"}
                    record = bound.sealed({"schema_version": 1, "request": request, **result,
                        "preflight_status": next(item["status"] for item in completion["outcomes"] if item["context_id"] == identity),
                        "preflight_receipt_sha256": row["preflight_receipt_sha256"],
                        "independent_replay_receipt_sha256": row["replay_receipt_sha256"],
                        "evidence_sha256": evidence, "finished_at_utc": datetime.now(UTC).isoformat()})
                    bound.publish_new(record_path, record)
                except Exception as error:
                    bound.publish_new(args.output / "failure.json", bound.sealed({"status": "unresolved_arithmetic_attempt",
                        "context_id": identity, "request": request, "exception_type": type(error).__name__, "message": str(error),
                        "proposals_selected_by_optimizer": False, "extra_proposals_generated": False}))
                    raise
            validate_context_record(record, row)
            artifacts[name] = pf.artifact_binding(record_path)
            outcome = {key: record[key] for key in ("preflight_status", "preflight_receipt_sha256", "status",
                "formula_checks", "kappa_required", "original_kappa_status", "independent_replay_receipt_sha256")}
            outcome.update(context_id=identity, evidence_sha256=[*evidence, artifacts[name]["sha256"]])
            if "adaptive_status" in record:
                outcome["adaptive_status"] = record["adaptive_status"]
            if record["status"] == "original_kappa_gate_failed":
                outcome["optimizer_predicate_evidence_sha256"] = artifacts[name]["sha256"]
            outcomes.append(outcome)
            print(json.dumps({"context_id": identity, "status": record["status"], "accounted": len(outcomes)}), flush=True)
            del inputs, record
        if snapshot is not None:
            snapshot.recheck()
        arithmetic.require(source_bindings() == sources, "arithmetic sources changed during execution")
        arithmetic.require(all(bound.file_hash(path) == digest for path, digest in inputs_bound), "bound input evidence changed")
        arithmetic.require(all(bound.file_hash(path) == digest for path, digest in context_pins),
                           "actual preflight/replay context evidence changed")
        for relative, digest in original_sources.items():
            arithmetic.require(bound.file_hash(args.source_checkout / relative) == digest, "original arithmetic source changed")
        for relative, digest in definition["original_input_sha256"].items():
            arithmetic.require(bound.file_hash(args.source_checkout / relative) == digest,
                               "original source/data/lock input changed during arithmetic")
        abandoned = args.output / "abandoned_claims"
        if abandoned.exists():
            for path in abandoned.iterdir():
                claim = bound.read_sealed(path)
                arithmetic.require(path.name == claim["nonce"] + ".json"
                                   and claim["run_binding_sha256"] == manifest["content_sha256"],
                                   "unbound abandoned arithmetic claim")
                artifacts[str(path.relative_to(args.output))] = pf.artifact_binding(path)
        pf.verify_artifacts(args.output, {"artifacts": artifacts})
        expected_files = {"manifest.json", "selection.json", "controller.claim.json", *artifacts}
        if (args.output / "accounting.json").exists():
            expected_files.add("accounting.json")
        actual_files = {str(path.relative_to(args.output)) for path in args.output.rglob("*") if path.is_file()}
        expected_directories = {"evidence"}
        if rows:
            expected_directories.add("contexts")
        if abandoned.exists():
            expected_directories.add("abandoned_claims")
        arithmetic.require(actual_files == expected_files
                           and all(not path.is_symlink() for path in args.output.rglob("*"))
                           and {str(path.relative_to(args.output)) for path in args.output.rglob("*") if path.is_dir()} ==
                           expected_directories, "unexpected arithmetic output inventory")
        accounted = bound.sealed({"schema_version": 1, "status": "all_scheduled_arithmetic_outcomes_accounted",
            "preflight_completion_sha256": args.completion_sha256, "input_inventory_sha256": args.inventory_sha256,
            "definition_content_sha256": definition["content_sha256"], "selector_sha256": args.selector_sha256,
            "scheduled_contexts": expected_contexts, "context_outcomes": outcomes,
            "outcome_counts": dict(Counter(row["status"] for row in outcomes)), "artifacts": artifacts,
            "proposals_selected_by_optimizer": False, "extra_proposals_generated": False,
            "adaptive_optimum_not_claimed_for_original_gate_failures": True,
            "scientific_method_approved": False, "corrected_fit_freeze_created": False})
        target = args.output / "accounting.json"
        if target.exists():
            arithmetic.require(bound.read_sealed(target) == accounted, "completed arithmetic accounting differs")
        else:
            bound.publish_new(target, accounted)
    return accounted


def main() -> int:
    """Refuse missing evidence; exit zero only for complete actual accounting."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-checkout", "preflight-root", "witness-root", "inventory", "python", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("completion", "replay", "selector", "definition", "inventory"):
        parser.add_argument("--" + name + "-sha256", required=True)
    parser.add_argument("--recover-stale-claims", action="store_true")
    args = parser.parse_args()
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        arithmetic.require(os.environ.get(name) == "1", "one numeric thread must be configured before Python")
    try:
        result = run(args)
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": result["status"], "outcome_counts": result["outcome_counts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
