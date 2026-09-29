"""Independent arithmetic coverage and unchanged original optimizer failures."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pytest

from scripts.catalytic_correction import run_arithmetic as cli
from scripts.catalytic_correction.independent_arithmetic import ArithmeticFailure
from tests.test_catalytic_correction_arithmetic import balanced, original_source_fixture
from tests.test_catalytic_correction_bound_arithmetic import create_fixture, write


@pytest.fixture
def source(tmp_path):
    return original_source_fixture(tmp_path)


def solver_result(success=True, coefficient=0.0):
    return SimpleNamespace(success=success, x=np.array([coefficient]),
                           jac=np.zeros(1), fun=1.0, nit=2, message="CONVERGENCE")


def test_checked_fixed_and_adaptive_use_one_original_call_each(source):
    solver = Mock(return_value=solver_result())
    with patch("scipy.optimize.minimize", solver):
        fixed = cli.calculate_context(balanced(), source, kappa_required=True, adaptive_required=False)
        adaptive = cli.calculate_context(balanced(), source, kappa_required=True, adaptive_required=True)
    assert solver.call_count == 2
    assert fixed["status"] == adaptive["status"] == "arithmetic_verified"
    assert fixed["original_kappa_status"] == adaptive["original_kappa_status"] == "passed"
    assert fixed["adaptive_status"] == "not_required"
    assert adaptive["adaptive_status"] == "checked_supplied_kappa"
    assert adaptive["optimum_arithmetic"]["check_count"] == 83


def test_actual_original_gate_failure_keeps_base_checks_and_pending_adaptive(source):
    solver = Mock(return_value=solver_result(coefficient=0.2))
    with patch("scipy.optimize.minimize", solver):
        result = cli.calculate_context(balanced(), source, kappa_required=True, adaptive_required=True)
    assert solver.call_count == 1
    assert result["status"] == "original_kappa_gate_failed"
    assert result["formula_checks"] == "passed"
    assert result["base_arithmetic"]["check_count"] == 56
    assert result["adaptive_status"] == "pending_original_kappa_gate_failure"
    assert result["optimizer_predicate_evidence"]["post_score_threshold_rejected"] is True
    assert "optimum_arithmetic" not in result


def test_weighted_context_does_not_enable_any_optimizer(source):
    with patch("scipy.optimize.minimize", side_effect=AssertionError("unexpected solver")):
        result = cli.calculate_context(balanced(), source, kappa_required=False, adaptive_required=False)
    assert result["status"] == "arithmetic_verified"
    assert result["original_kappa_status"] == "not_required"
    assert result["optimizer_invoked"] is False


def test_formula_error_is_not_optimizer_attrition(source):
    original = cli.arithmetic.independent_catalytic

    def wrong(*args, **kwargs):
        value, gradient = original(*args, **kwargs)
        return value + 0.1, gradient

    solver = Mock(side_effect=AssertionError("optimizer must not run after formula mismatch"))
    with patch.object(cli.arithmetic, "independent_catalytic", wrong), patch("scipy.optimize.minimize", solver):
        with pytest.raises(ArithmeticFailure, match="formula mismatch"):
            cli.calculate_context(balanced(), source, kappa_required=True, adaptive_required=True)
    assert solver.call_count == 0


def test_same_message_from_solver_is_unresolved_without_guard_evidence(source):
    with patch("scipy.optimize.minimize", side_effect=RuntimeError("catalytic kappa optimizer failed: CONVERGENCE")):
        with pytest.raises(RuntimeError):
            cli.calculate_context(balanced(), source, kappa_required=True, adaptive_required=True)


def plan_fixture():
    identities = ["metabric__clinical__r01f01__catalytic_fixed__full::outer",
                  "metabric__clinical__r01f01__catalytic_wme__full::inner_01"]
    arrays = {name: {"values_sha256": "a" * 64} for name in ("synthetic_design", "synthetic_time", "hazard", "time_scale")}
    rows, outcomes, replays = [], [], []
    for ordinal, identity in enumerate(identities):
        model = "catalytic_fixed" if ordinal == 0 else "catalytic_wme"
        before, after = copy.deepcopy(arrays), copy.deepcopy(arrays)
        if ordinal == 0:
            after["synthetic_design"]["values_sha256"] = "b" * 64
        row = {"context_id": identity, "model": model, "context": "outer" if ordinal == 0 else "inner_01",
            "status": "changed_accepted_inputs" if ordinal == 0 else "unchanged_first_draw",
            "original_constructor_array_witnesses": before, "accepted_constructor_array_witnesses": after,
            "accepted_attempt_index": 1 if ordinal == 0 else 0,
            "changed_logical_arrays": ["synthetic_design"] if ordinal == 0 else [],
            "requires_kappa_check": ordinal == 0,
            "required_checks": ["q_and_gradient", "tau_scaled_identity", "weighted_merged_breslow",
                                "original_kappa_and_adaptive_prior_terms"] if ordinal == 0 else [],
            "preflight_receipt_sha256": str(ordinal) * 64, "preflight_receipt_path": f"contexts/{ordinal}/receipt.json",
            "replay_receipt_sha256": "c" * 64, "replay_receipt_path": f"replay/{ordinal}/receipt.json",
            "arithmetic_executed_or_certified_by_selector": False}
        rows.append(row)
        outcomes.append({"context_id": identity, "receipt_sha256": row["preflight_receipt_sha256"],
                         "receipt_path": row["preflight_receipt_path"],
                         "status": "accepted_rank_conditioned_redraw" if ordinal == 0 else "accepted_original_first_draw"})
        replays.append({"context_id": identity, "receipt_sha256": row["replay_receipt_sha256"],
                        "receipt_path": row["replay_receipt_path"]})
    selector = {"status": "all1650_context_arithmetic_requirements_accounted", "scheduled_contexts": 2,
                "entries": rows, "arithmetic_validation_executed": False, "scientific_method_approved": False,
                "definition_content_sha256": "d" * 64}
    completion = {"status": "all_scheduled_contexts_accounted", "scheduled_contexts": 2, "accounted_contexts": 2, "outcomes": outcomes}
    replay = {"status": "all1650_independent_first_draw_contexts_accounted", "scheduled_contexts": 2,
              "accounted_contexts": 2, "outcomes": replays, "no_fit_optimizer_mcmc_prediction_or_score_run": True,
              "definition_content_sha256": "d" * 64}
    return selector, completion, replay, {"definition_content_sha256": "d" * 64}, {"content_sha256": "d" * 64}


def test_plan_preserves_changed_and_unchanged_with_exact_coverage():
    documents = plan_fixture()
    assert len(cli.validate_plan(*documents, expected=2)) == 2
    documents[0]["entries"].append(copy.deepcopy(documents[0]["entries"][0]))
    with pytest.raises(ArithmeticFailure, match="coverage"):
        cli.validate_plan(*documents, expected=2)


@pytest.mark.parametrize("field,value", [("requires_kappa_check", False), ("required_checks", []),
                                          ("changed_logical_arrays", []), ("accepted_attempt_index", 0),
                                          ("model", "catalytic_wme")])
def test_plan_rejects_omitted_or_foreign_changed_input_requirements(field, value):
    documents = plan_fixture()
    documents[0]["entries"][0][field] = value
    with pytest.raises(ArithmeticFailure):
        cli.validate_plan(*documents, expected=2)


def test_terminal_label_cannot_replace_an_accepted_proposal():
    documents = plan_fixture()
    row = documents[0]["entries"][0]
    row.update(status="terminal_input_failure", accepted_attempt_index=None, requires_kappa_check=False,
               required_checks=[], changed_logical_arrays=[])
    with pytest.raises(ArithmeticFailure, match="terminal preflight"):
        cli.validate_plan(*documents, expected=2)


def test_exact_copy_refuses_changed_source_and_changed_resumed_evidence(tmp_path):
    source = tmp_path / "source.json"
    source.write_text("original bytes")
    digest = cli.bound.file_hash(source)
    copied = tmp_path / "evidence/copy.json"
    cli.copy_evidence(source, copied, digest)
    copied.write_text("changed bytes")
    with pytest.raises(ArithmeticFailure, match="copied evidence"):
        cli.copy_evidence(source, copied, digest)


def accounting_fixture(base, source):
    """Two invented contexts with an injected environment, no actual cohorts."""
    root = base / "preflight"
    _, completion_sha, _ = create_fixture(root)
    complete = cli.bound.read_sealed(root / "completion.json")
    witness = base / "witness"
    witness.mkdir()
    environment = {"status": "ok", "package_count": 259, "synthetic_fixture": True}
    pins = {cli.arithmetic.SOURCE_RELATIVE: cli.arithmetic.ORIGINAL_CATALYTIC_SHA256,
            **cli.bound.ADDITIONAL_ORIGINAL_SOURCES}
    definition_sha = write(witness / "definition.json", {"original_input_sha256": pins,
        "original_production_commit": cli.arithmetic.ORIGINAL_COMMIT, "environment_verification": environment})
    definition = cli.bound.read_sealed(witness / "definition.json")
    run_manifest_sha = write(root / "manifest.json", {"original_input_sha256": pins})
    preflight_manifest = cli.bound.read_sealed(root / "manifest.json")
    complete.pop("content_sha256")
    complete["run_binding_sha256"] = preflight_manifest["content_sha256"]
    # Update all fictional request bindings consistently before any execution.
    for item in complete["outcomes"]:
        folder = root / item["receipt_path"]
        receipt = cli.bound.read_sealed(folder)
        receipt.pop("content_sha256")
        receipt["request"]["run_binding_sha256"] = preflight_manifest["content_sha256"]
        inputs_record = cli.bound.read_sealed(folder.parent / "input.json")
        inputs_record.pop("content_sha256")
        inputs_record["request"] = receipt["request"]
        write(folder.parent / "input.json", inputs_record)
        receipt["artifacts"]["input.json"] = cli.pf.artifact_binding(folder.parent / "input.json")
        for ordinal, attempt in enumerate(receipt["attempts"]):
            attempt.pop("content_sha256")
            attempt["request"] = receipt["request"]
            attempt.setdefault("legacy_metadata", None)
            path = folder.parent / f"attempt_{ordinal:03d}/receipt.json"
            write(path, attempt)
            receipt["attempts"][ordinal] = cli.bound.read_sealed(path)
            receipt["artifacts"][f"attempt_{ordinal:03d}/receipt.json"] = cli.pf.artifact_binding(path)
        item["receipt_sha256"] = write(folder, receipt)
        item["receipt_content_sha256"] = cli.bound.read_sealed(folder)["content_sha256"]
    completion_sha = write(root / "completion.json", complete)
    entries, replay_rows = [], []
    for item in complete["outcomes"]:
        identity = item["context_id"]
        receipt = cli.bound.read_sealed(root / item["receipt_path"])
        old = receipt["attempts"][0]["array_witnesses"]
        accepted = receipt["attempts"][receipt["accepted_attempt_index"]]["array_witnesses"]
        changed = sorted(key for key in old if old[key] != accepted[key])
        replay_name = f"replay/contexts/{cli.bound.context_output_name(identity)}"
        first = receipt["attempts"][0]
        replay_sha = write(witness / replay_name, {"context_id": identity,
            "status": "independent_original_first_draw_verified",
            "request": {"context_id": identity, "preflight_receipt_sha256": item["receipt_sha256"],
                        "definition_content_sha256": definition["content_sha256"]},
            "original_replay": {"status": first["status"], "array_witnesses": old,
                                "seed": first["seed"], "legacy_metadata": first.get("legacy_metadata")},
            "assessment": {"status": "exact_normal_import_first_proposal_identity",
                           "full_constructor_identity_witnessed": True,
                           "constructor_result": first["status"]}, "synthetic_fixture": True})
        entries.append({"context_id": identity, "model": "catalytic_wme", "context": cli.bound.context_parts(identity)[1],
            "status": "changed_accepted_inputs" if changed else "unchanged_first_draw", "requires_kappa_check": False,
            "original_constructor_array_witnesses": old, "accepted_constructor_array_witnesses": accepted,
            "accepted_attempt_index": receipt["accepted_attempt_index"], "changed_logical_arrays": changed,
            "required_checks": ["q_and_gradient", "tau_scaled_identity", "weighted_merged_breslow"] if changed else [],
            "preflight_receipt_path": item["receipt_path"], "preflight_receipt_sha256": item["receipt_sha256"],
            "replay_receipt_path": replay_name, "replay_receipt_sha256": replay_sha,
            "arithmetic_executed_or_certified_by_selector": False})
        replay_rows.append({"context_id": identity, "receipt_path": replay_name, "receipt_sha256": replay_sha,
                            "receipt_content_sha256": cli.bound.read_sealed(witness / replay_name)["content_sha256"]})
    replay_sha = write(witness / "replay/completion.json", {"status": "all1650_independent_first_draw_contexts_accounted",
        "definition_content_sha256": definition["content_sha256"], "scheduled_contexts": 2, "accounted_contexts": 2,
        "outcomes": replay_rows, "no_fit_optimizer_mcmc_prediction_or_score_run": True})
    selector_sha = write(witness / "arithmetic_selector.json", {"status": "all1650_context_arithmetic_requirements_accounted",
        "scheduled_contexts": 2, "definition_content_sha256": definition["content_sha256"],
        "preflight_completion_sha256": completion_sha, "replay_completion_sha256": replay_sha,
        "entries": entries, "arithmetic_validation_executed": False, "scientific_method_approved": False})
    inventory_path = witness / "inventory.json"
    inventory_sha = write(inventory_path, {"scheduled_cells": 1, "entries": [{"original_cell_id": "fictional"}],
        "definition_content_sha256": definition["content_sha256"], "preflight_completion_sha256": completion_sha,
        "replay_completion_sha256": replay_sha, "arithmetic_selector_sha256": selector_sha})
    assert run_manifest_sha
    args = argparse.Namespace(source_checkout=source, preflight_root=root, witness_root=witness,
        inventory=inventory_path, inventory_sha256=inventory_sha, completion_sha256=completion_sha,
        replay_sha256=replay_sha, selector_sha256=selector_sha, definition_sha256=definition_sha,
        python=Path(sys.executable).resolve(), output=base / "output", recover_stale_claims=False)
    return args, environment


def test_complete_immutable_accounting_resume_and_extra_file_refusal(tmp_path):
    source = original_source_fixture(tmp_path / "source")
    args, environment = accounting_fixture(tmp_path, source)
    injected_environment = SimpleNamespace(stdout=json.dumps(environment))
    original_calculation = cli.calculate_context
    with patch.object(cli.subprocess, "run", return_value=injected_environment), \
            patch.object(cli, "calculate_context", wraps=original_calculation) as calculation:
        first = cli.run(args, expected_contexts=2, expected_cells=1)
        second = cli.run(args, expected_contexts=2, expected_cells=1)
        assert first == second
        assert calculation.call_count == 1
        assert first["outcome_counts"] == {"unchanged_inputs_independently_witnessed": 1, "arithmetic_verified": 1}
        (args.output / "contexts/unbound.json").write_text("{}")
        with pytest.raises(ArithmeticFailure, match="unexpected arithmetic output"):
            cli.run(args, expected_contexts=2, expected_cells=1)


def test_production_run_refuses_reduced_fixture_before_output(tmp_path):
    source = original_source_fixture(tmp_path / "source")
    args, _ = accounting_fixture(tmp_path, source)
    with pytest.raises(ArithmeticFailure, match="complete1625"):
        cli.run(args)
    assert not args.output.exists()


def test_wrong_controller_interpreter_is_rejected_before_loading_evidence(tmp_path):
    alternate = tmp_path / "other-python"
    alternate.write_bytes(b"invented executable")
    args = SimpleNamespace(python=alternate)
    with patch.object(cli, "source_bindings", side_effect=AssertionError("must reject before any input/source load")):
        with pytest.raises(ArithmeticFailure, match="controller interpreter differs"):
            cli.run(args)
    alias = tmp_path / "same-python"
    alias.symlink_to(sys.executable)
    cli.verify_current_interpreter(alias)


@pytest.mark.parametrize("mutation", ["redraw_as_unchanged", "original_witness", "accepted_witness"])
def test_actual_receipts_reject_selector_witness_substitution_before_calculation(tmp_path, mutation):
    source = original_source_fixture(tmp_path / "source")
    args, _ = accounting_fixture(tmp_path, source)
    selector = cli.bound.read_sealed(args.witness_root / "arithmetic_selector.json")
    selector.pop("content_sha256")
    row = selector["entries"][1]
    if mutation == "redraw_as_unchanged":
        row.update(status="unchanged_first_draw", accepted_attempt_index=0, changed_logical_arrays=[], required_checks=[])
        row["accepted_constructor_array_witnesses"] = copy.deepcopy(row["original_constructor_array_witnesses"])
    else:
        key = "original_constructor_array_witnesses" if mutation == "original_witness" else "accepted_constructor_array_witnesses"
        row[key]["synthetic_design"]["values_sha256"] = "e" * 64
    args.selector_sha256 = write(args.witness_root / "arithmetic_selector.json", selector)
    inventory = cli.bound.read_sealed(args.inventory)
    inventory.pop("content_sha256")
    inventory["arithmetic_selector_sha256"] = args.selector_sha256
    args.inventory_sha256 = write(args.inventory, inventory)
    with patch.object(cli, "calculate_context", side_effect=AssertionError("incorrect scope must not calculate")), \
            patch.object(cli.subprocess, "run", side_effect=AssertionError("must reject before checker/solver")):
        with pytest.raises(ArithmeticFailure):
            cli.run(args, expected_contexts=2, expected_cells=1)
    assert not args.output.exists()


@pytest.mark.parametrize("mutation", ["omit_kappa", "incomplete_optimum", "changed_threshold"])
def test_malformed_completed_kappa_checkpoint_cannot_resume_as_verified(source, mutation):
    with patch("scipy.optimize.minimize", return_value=solver_result()):
        record = cli.calculate_context(balanced(), source, kappa_required=True, adaptive_required=True)
    row = {"status": "changed_accepted_inputs", "model": "catalytic_adaptive", "requires_kappa_check": True}
    cli.validate_context_record(record, row)
    if mutation == "omit_kappa":
        record["kappa_required"] = False
    elif mutation == "incomplete_optimum":
        record["optimum_arithmetic"]["check_count"] = 82
    else:
        record["optimizer_predicate_evidence"]["post_score_threshold"] = 1e-4
    with pytest.raises(ArithmeticFailure):
        cli.validate_context_record(record, row)


def terminal_fixture(status):
    """Invent terminal receipts; no generators, ranks or optimizers are called."""
    identity, digest = "fictional::outer", "a" * 64
    error = {"type": "ValueError", "message": "invented terminal failure"}
    first_status = "nonrank_error" if status == "nonrank_failure" else "frozen_rank_rejected"
    first = {"status": first_status, "seed": 17, "legacy_metadata": None,
             "array_witnesses": None if first_status == "nonrank_error" else {"invented": True}, "error": error}
    original = ({"status": "input_failure", "error": copy.deepcopy(error)} if status == "input_failure"
                else {**copy.deepcopy(first)})
    assessment = ({"status": "exact_original_input_failure", "generator_called": False,
                   "full_constructor_identity_witnessed": False} if status == "input_failure" else
                  {"status": "exact_original_nonrank_error", "generator_called": True,
                   "full_constructor_identity_witnessed": False} if status == "nonrank_failure" else
                  {"status": "exact_normal_import_first_proposal_identity", "generator_called": True,
                   "full_constructor_identity_witnessed": True, "constructor_result": first_status})
    preflight = {"request": {"context_id": identity}, "accepted_attempt_index": None,
                 "status": status, "attempts": [] if status == "input_failure" else [first], "input_error": error}
    replay = {"request": {"context_id": identity, "preflight_receipt_sha256": digest}, "context_id": identity,
              "status": "independent_original_first_draw_verified", "original_replay": original, "assessment": assessment}
    row = {"context_id": identity, "preflight_receipt_sha256": digest, "accepted_attempt_index": None,
           "original_constructor_array_witnesses": original.get("array_witnesses"),
           "accepted_constructor_array_witnesses": None,
           "status": next(key for key, value in cli.TERMINAL_PREFLIGHT.items() if value == status)}
    cli.verify_selector_context(row, preflight, replay)
    return row, preflight, replay


@pytest.mark.parametrize("status,mutation", [
    ("input_failure", "status"), ("input_failure", "error_type"), ("input_failure", "error_message"),
    ("nonrank_failure", "error_type"), ("nonrank_failure", "error_message"),
    ("exhausted_rank_cap", "constructor_identity"), ("exhausted_rank_cap", "constructor_result")])
def test_terminal_replay_labels_cannot_substitute_actual_exception_or_constructor(status, mutation):
    row, preflight, replay = terminal_fixture(status)
    if mutation == "status":
        replay["original_replay"]["status"] = "invented_other_status"
    elif mutation.startswith("error_"):
        replay["original_replay"]["error"][mutation.removeprefix("error_")] = "invented altered failure"
    elif mutation == "constructor_identity":
        replay["assessment"]["full_constructor_identity_witnessed"] = False
    else:
        replay["assessment"]["constructor_result"] = "accepted_original_constructor"
    with pytest.raises(ArithmeticFailure):
        cli.verify_selector_context(row, preflight, replay)
