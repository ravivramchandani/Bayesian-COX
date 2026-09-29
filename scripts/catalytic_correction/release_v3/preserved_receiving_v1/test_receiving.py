"""Invented files/injected dependencies only; no real programme execution."""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import math
import os
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
SPEC = importlib.util.spec_from_file_location("restore_under_test", HERE / "receiving_core.py")
assert SPEC is not None and SPEC.loader is not None
r = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = r
SPEC.loader.exec_module(r)


def put(path, value, *, sealed=True, field="content_sha256"):
    path.parent.mkdir(parents=True, exist_ok=True)
    if sealed:
        value = {**value, field: r.digest(value)}
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")
    return value


def tree(root):
    return {str(path.relative_to(root)): r.binding(path) for path in sorted(root.rglob("*")) if path.is_file()}


def load_source_helpers():
    """Read exact helper sources; execute only stdlib and comparison ASTs."""
    fit = Path(os.environ["REPRO_RESTORE_TEST_FIT_CODE"])
    v1 = Path(os.environ["REPRO_RESTORE_TEST_V1_CODE"])
    spec = importlib.util.spec_from_file_location("restore_test_common", fit / "fit_common.py")
    assert spec is not None and spec.loader is not None
    common = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(common)
    previous = sys.modules.get("_reproduction_bound_common")
    sys.modules["_reproduction_bound_common"] = common
    try:
        spec = importlib.util.spec_from_file_location("restore_test_v1", v1 / "reproduction_core.py")
        assert spec is not None and spec.loader is not None
        rc = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(rc)
    finally:
        if previous is None:
            sys.modules.pop("_reproduction_bound_common", None)
        else:
            sys.modules["_reproduction_bound_common"] = previous
    return common, rc


class ToyNP:
    @staticmethod
    def isclose(left, right, *, rtol, atol):
        return abs(left - right) <= atol + rtol * abs(right)

    @staticmethod
    def array_equal(left, right, *, equal_nan=False):
        if not isinstance(left, list) or not isinstance(right, list):
            return left == right
        if len(left) != len(right):
            return False
        return all(a == b or equal_nan and isinstance(a, float) and isinstance(b, float)
                   and math.isnan(a) and math.isnan(b) for a, b in zip(left, right, strict=True))


class ToyGroup:
    def __init__(self, values):
        self.data_vars, self.values = list(values), values

    def __getitem__(self, key):
        return SimpleNamespace(values=self.values[key])


class ToyAZ:
    reads = []
    closed = []

    @classmethod
    def from_netcdf(cls, name):
        value = json.loads(Path(name).read_text())
        cls.reads.append(name)
        return SimpleNamespace(posterior=ToyGroup(value["posterior"]), sample_stats=ToyGroup(value["sample_stats"]),
                               close=lambda: cls.closed.append(name))


@dataclass
class ToyWitness:
    original_evidence: object
    corrected_seeds: dict
    roles: dict
    model: str = "catalytic_fixed"


class Fixture:
    def __init__(self, root):
        self.base = root
        self.old = Path("/historical/thesis")
        self.source, self.original, self.old_repro = (root / name for name in ("source", "original", "old_repro"))
        self.corrected, self.repro, self.docs = (root / name for name in ("corrected", "repro", "docs"))
        self.code, self.fit, self.preflight, self.witness_root = (root / name for name in ("code", "fit", "preflight", "witness"))
        for path in (self.source, self.original, self.old_repro, self.corrected, self.repro, self.docs,
                     self.code, self.fit, self.preflight, self.witness_root):
            path.mkdir()
        self.common, self.rc = load_source_helpers()
        self.comparators = self.rc.original_comparators(Path(os.environ["REPRO_RESTORE_TEST_ORIGINAL_SOURCE"]), ToyNP, ToyAZ)
        self.ident = "d__s000__r01f01__c__catalytic_fixed"
        self.ids = [f"d__s{i:03d}__r01f01__c__catalytic_fixed" for i in range(92)]
        self.selection = {"schema_version": 1, "status": "reviewed_corrected_reproduction_selection",
            "scope_rule": self.rc.SCOPE_RULE, "original_selected_cells": self.ids,
            "pilot_cells": [self.ident], "selected_cells": self.ids,
            "original_manifest_sha256": self.common.ORIGINAL_MANIFEST_SHA,
            "correction_freeze_sha256": "freeze", "corrected_manifest_sha256": "manifest",
            "definition_content_sha256": "definition", "input_inventory_sha256": "inventory",
            "implementation_source_sha256": r.V1_PINS, "fit_implementation_source_sha256": self.rc.FIT_SOURCE_PINS,
            "comparison_source_sha256": self.rc.COMPARISON_PINS, "recipe_inventory_sha256": "recipes",
            "original_numerical_evidence_sha256": "old_evidence", "execution": {},
            "paths": {key: str(self.old / value) for key, value in {
                "freeze": "docs/freeze.json", "manifest": "corrected/manifest.json", "fit_code": "fit",
                "corrected_run": "corrected", "original_reproduction": "old_repro",
                "original_numerical_evidence": "docs/old.json", "recipe_inventory": "docs/rows.jsonl", "scope_review": "docs/scope.json"}.items()}}
        self.selection_document = put(self.repro / "selection.json", self.selection)
        self.selection = self.selection_document
        self.selection_sha = r.binding(self.repro / "selection.json")["sha256"]
        self.freeze = {"definition_content_sha256": "definition", "input_inventory_sha256": "inventory",
            "preflight_manifest_sha256": "preflight",
            "paths": {key: str(self.old / value) for key, value in {
                "source": "source", "original_run": "original", "matched": "docs/matched.txt", "preflight": "preflight",
                "witness_root": "witness", "inventory": "docs/inventory.json", "contracts": "docs/contracts.py",
                "preflight_core": "docs/pf.py", "reuse_core": "docs/reuse.py"}.items()}}
        self.manifest = {"pilot_cells": [self.ident]}
        self.preflight_document = {"environment_verification": {"status": "ok", "package_count": 259, "lock_sha256": "invented"}}
        put(self.preflight / "manifest.json", self.preflight_document)
        (self.source / "scripts").mkdir()
        (self.source / "scripts/verify_environment.py").write_text("invented checker source; never executed")
        self.original_manifest = {"input_sha256": {"scripts/verify_environment.py": r.binding(self.source / "scripts/verify_environment.py")["sha256"]}}
        self.decision = {"original_cell_id": self.ident, "action": "fit_changed_inputs", "source_evidence": {"finished": True}}
        self.witness = ToyWitness({"finished": True}, {"outer_prior": 12}, {"role": SimpleNamespace(corrected_sha256="corrected")})
        self.entry = {"original_cell_id": self.ident, "model": "catalytic_fixed", "input_witness_sha256": "input"}
        self.inputs = SimpleNamespace(resolutions={}, current=lambda entry: ({}, self.decision, {"status": "complete"}, self.witness))
        self.fit_controller = SimpleNamespace(read_resolution_review=lambda *args: {},
            Controller=lambda *args: self.inputs,
            verify_record=lambda path, *args: r.document(path),
            validate_pilot_review=lambda *args: None)
        self.contracts = SimpleNamespace(classify=lambda witness: {**self.decision, "source_evidence": witness.original_evidence})
        self.inventory = {"entries": [self.entry]}
        self.outcome = {}
        self.rows = []
        self.complete = SimpleNamespace(context=lambda row: None, lookup={})

    def value(self):
        roots = (self.source, self.original, self.old_repro, self.corrected, self.repro, self.docs,
                 self.code, self.fit, self.preflight, self.witness_root)
        return {"schema_version": 1, "status": "corrected_selected_reproduction_receiving_bindings",
            "reproduction_root": str(self.old / "repro"), "reproduction_code": str(self.old / "code"),
            "selection": str(self.old / "repro/selection.json"), "selection_sha256": self.selection_sha,
            "reproduction_source_sha256": r.V1_PINS, "reviews": {},
            "receiving_source_sha256": {name: r.binding(HERE / name)["sha256"] for name in r.OWN_SOURCES},
            "completed_pass": {"path": "passes/complete.json", "sha256": "pass"},
            "path_map": [{"historical": str(self.old / path.name), "restored": str(path), "kind": "directory"} for path in roots],
            "immutable_roots": [{"root": str(path), "artifacts": tree(path)} for path in roots], "immutable_files": []}

    def verifier(self):
        value = self.value()
        resolver = r.Resolver(value, self.base / "fresh")
        common, _ = load_source_helpers()
        common = r.mapped_common(common, resolver)
        common.read_original_manifest = lambda root: self.original_manifest if hasattr(self, "original_manifest") else {}
        common.read_json = lambda path, expected=None, **kwargs: r.document(resolver.resolve(path), None, **kwargs)
        verifier = r.ReceivingVerifier(value=value, resolver=resolver, common=common, rc=self.rc,
            selection=self.selection, freeze=self.freeze, manifest=self.manifest, inventory=self.inventory,
            completion={}, rows=self.rows, numerical={"entries": getattr(self, "numerical", {})}, contracts=self.contracts,
            fit_controller=self.fit_controller, complete=self.complete, pf=SimpleNamespace(), np=ToyNP, comparators=self.comparators)
        return verifier

    def cells(self, left_root, right_root, identity=None):
        identity = identity or self.ident
        paths = []
        for index, root in enumerate((left_root, right_root)):
            trace = root / "traces" / identity / "trace.json"
            put(trace, {"posterior": {"beta": [0.2, 0.3]}, "sample_stats": {"diverging": [0, 0],
                "perf_counter_diff": [index, index + 1]}}, sealed=False)
            (trace.parent / "orphan.log").write_text(f"orphan{index}")
            cell = {"cell_id": identity, "status": "complete", "estimate": 0.15,
                "fit_seconds": float(index), "fit_attempts": [{"traces": {"initial": {"filename": trace.name,
                "sha256": r.binding(trace)["sha256"]}}}]}
            path = root / "cells" / f"{identity}.json"
            put(path, cell, field="cell_content_sha256")
            paths.append(path)
        return paths

    def record(self, status):
        baseline = {"original_cell_id": self.ident, "correction_freeze_sha256": "freeze",
            "definition_content_sha256": "definition", "input_witness_sha256": "input",
            "original_seed_namespace": self.witness.corrected_seeds, "decision": self.decision,
            "source_evidence": self.decision["source_evidence"]}
        path = self.corrected / "cells" / f"{self.ident}.json"
        baseline = put(path, baseline)
        return {"schema_version": 1, "original_cell_id": self.ident, "status": status,
            "selection_sha256": self.selection_sha, "scope_definition_sha256": self.rc.scope_definition(self.selection),
            "corrected_manifest_sha256": "manifest", "correction_freeze_sha256": "freeze",
            "definition_content_sha256": "definition", "input_witness_sha256": "input",
            "current_input_decision": self.decision, "corrected_outcome_path": str(self.old / "corrected/cells" / path.name),
            "corrected_outcome_sha256": r.binding(path)["sha256"], "artifacts": {}, "external_artifacts": {},
            "selected_scope_only": True, "programme_complete": False, "reporting_certified": False, "release_certified": False}, baseline

    def changed(self):
        record, baseline = self.record("new_corrected_numerical_reproduction")
        attempt = self.repro / "attempts" / f"{self.ident}.fresh"
        attempt.mkdir(parents=True)
        left_root = self.corrected / "attempts" / self.ident
        old, new = self.cells(left_root, attempt)
        baseline.update(operation="fit_corrected_inputs", corrected_cell={"path": str(old.relative_to(self.corrected)),
            "sha256": r.binding(old)["sha256"]})
        put(self.corrected / "cells" / f"{self.ident}.json", {key: item for key, item in baseline.items() if key != "content_sha256"})
        request = put(attempt / "request.json", {"original_cell_id": self.ident, "entry": self.entry,
            "source_evidence": self.decision["source_evidence"], "action": self.decision["action"],
            "freeze_path": self.selection["paths"]["freeze"], "freeze_sha256": "freeze",
            "manifest_path": self.selection["paths"]["manifest"], "manifest_sha256": "manifest",
            "attempt_path": str(self.old / "repro/attempts" / attempt.name), "locked_python": "/old/locked/python",
            "implementation_source_sha256": self.rc.FIT_SOURCE_PINS})
        historical = self.old / "repro/attempts" / attempt.name
        (attempt / "stdout.log").write_text("real invented worker log")
        (attempt / "stderr.log").write_text("")
        put(attempt / "invocation.json", {"operation": "isolated_selected_reproduction_child", "exit_code": 0,
            "launch_error": None, "numeric_thread_environment": {name: "1" for name in r.NUMERIC_VARIABLES},
            "argv": [request["locked_python"], "-I", "-B", str(self.old / "fit/fit_child.py"), "--request",
                str(historical / "request.json"), "--request-sha256", r.binding(attempt / "request.json")["sha256"]],
            "stdout": r.binding(attempt / "stdout.log"), "stderr": r.binding(attempt / "stderr.log")})
        self.environment(attempt, request["locked_python"])
        checked = r.seal({"status": "current_complete_inputs_match_corrected_witness", "input_witness_sha256": "input",
            "definition_content_sha256": "definition", "required_role_count": 1, "corrected_role_sha256": {"role": "corrected"},
            "no_generator_model_fit_prediction_or_score_executed": True})
        child = put(attempt / "child_receipt.json", {"status": "original_cell_delegated_with_verified_corrected_inputs",
            "original_cell_id": self.ident, "corrected_manifest_sha256": "manifest", "input_witness_sha256": "input",
            "action": self.decision["action"], "original_seed_namespace": self.witness.corrected_seeds,
            "cell": r.binding(new), "fit_dispatched": True,
            "full_environment_verification": self.preflight_document["environment_verification"],
            "actual_process_runtime_verification": {"locked_interpreter_samefile": True,
                "numeric_thread_environment": {name: "1" for name in r.NUMERIC_VARIABLES}},
            "full_current_execution_input_verification": checked, "scientific_status": "complete"})
        result = self.rc.compare_cells(old, new, left_root, attempt, self.comparators)
        put(attempt / "comparison.json", result)
        record.update(new_numerical_fit_executed=True, child_receipt_path=str((attempt / "child_receipt.json").relative_to(self.repro)),
                      comparison=result, scientific_status=child["scientific_status"])
        return record, baseline, attempt

    def producer(self, route="official_fresh_refit"):
        source_file = self.source / "scripts/reproduce_extensions.py"
        source_file.parent.mkdir(exist_ok=True)
        source_file.write_bytes((Path(os.environ["REPRO_RESTORE_TEST_ORIGINAL_SOURCE"]) / "scripts/reproduce_extensions.py").read_bytes())
        matched = self.docs / "matched.txt"
        matched.write_text("invented matched bytes")
        source_inputs = {"scripts/reproduce_extensions.py": r.binding(source_file)["sha256"]}
        original = {"input_sha256": source_inputs, "matched_sha256": r.binding(matched)["sha256"],
            "plan": [{"cell_id": identity} for identity in self.ids]}
        put(self.docs / "environment.json", self.preflight_document["environment_verification"], sealed=False)
        base = {"source_path": str(self.old / "source"), "git_commit": self.common.ORIGINAL_COMMIT,
            "original_manifest_sha256": self.common.ORIGINAL_MANIFEST_SHA, "source_input_sha256": source_inputs,
            "environment_report_sha256": r.binding(self.docs / "environment.json")["sha256"],
            "exit_code": 0, "owner_finished": True, "numeric_thread_environment": {name: "1" for name in r.NUMERIC_VARIABLES},
            "python_executable": "/gone/old/python", "cwd": str(self.old / "source"), "script_index": 1}
        shared = ["--source", str(self.old / "original"), "--output", str(self.old / "old_repro"), "--matched", str(self.old / "docs/matched.txt")]
        invocation = {**base, "status": "actual_original_numerical_worker_invocation_recorded",
            "original_run": str(self.old / "original"), "reproduction_output": str(self.old / "old_repro"),
            "original_full_budget": True, "actual_numerical_refit_execution": True,
            "cached_comparison_only": False, "numerically_refitted_cell_ids": [self.ident],
            "argv": ["/gone/old/python", "scripts/reproduce_extensions.py", *shared]}
        official = {**base, "status": "actual_official_original_92_comparison_recorded",
            "scientifically_compared_cell_ids": [self.ident], "cached_comparison_only": route == "reviewed_external_prestage",
            "argv": ["/gone/old/python", "scripts/reproduce_extensions.py", *shared]}
        producer = {"route": route, "source_path": str(self.old / "source"), "git_commit": self.common.ORIGINAL_COMMIT,
            "input_sha256": source_inputs,
            "matched_input": {"path": str(self.old / "docs/matched.txt"), "binding": r.binding(matched)},
            "environment_report": {"path": str(self.old / "docs/environment.json"), "binding": r.binding(self.docs / "environment.json")}}
        fake_rc = SimpleNamespace(ORIGINAL_NUMERICAL_PRODUCER_COMMITS=self.rc.ORIGINAL_NUMERICAL_PRODUCER_COMMITS,
            COMPARISON_PINS={"scripts/reproduce_extensions.py": source_inputs["scripts/reproduce_extensions.py"]})
        if route == "reviewed_external_prestage":
            helper = self.docs / "prestage.py"
            helper.write_text("invented prestage helper")
            fake_rc.PRESTAGE_HELPER_SHA = r.binding(helper)["sha256"]
            invocation.update(worker=0, workers=2, argv=["/gone/old/python", str(self.old / "docs/prestage.py"), *shared,
                "--production-code", str(self.old / "source"), "--worker", "0", "--workers", "2"])
            (self.docs / "worker.log").write_text(self.ident + " prestaged_exact\n")
            invocation["stdout"] = {"path": str(self.old / "docs/worker.log"), "binding": r.binding(self.docs / "worker.log")}
            put(self.docs / "helper_review.json", {"status": "actual_prestage_helper_scientific_delegation_reviewed",
                "helper_sha256": fake_rc.PRESTAGE_HELPER_SHA, "original_manifest_sha256": self.common.ORIGINAL_MANIFEST_SHA,
                "production_source_commit": self.common.ORIGINAL_COMMIT,
                "unchanged_run_extension_cell_inputs_seeds_budget_and_guards": True, "issues_official_final_receipts": False})
            producer.update(helper={"path": str(self.old / "docs/prestage.py"), "binding": r.binding(helper)},
                helper_scientific_delegation_review={"path": str(self.old / "docs/helper_review.json"),
                "binding": r.binding(self.docs / "helper_review.json")})
        put(self.docs / "invocation.json", invocation)
        put(self.docs / "official.json", official)
        put(self.docs / "lineage.json", {"status": "original_numerical_execution_input_and_algorithm_lineage_reviewed",
            "original_manifest_sha256": self.common.ORIGINAL_MANIFEST_SHA, "producer_git_commit": self.common.ORIGINAL_COMMIT,
            "producer_input_sha256": source_inputs, "original_input_sha256": source_inputs,
            "invocation_record_sha256": r.binding(self.docs / "invocation.json")["sha256"],
            "official_comparison_record_sha256": r.binding(self.docs / "official.json")["sha256"], "producer_route": route,
            "frozen_primary_scientific_inputs_algorithms_seeds_budgets_and_gates_identical": True})
        for role, name in (("invocation_record", "invocation.json"), ("official_comparison_record", "official.json"),
                           ("scientific_lineage_review", "lineage.json")):
            producer[role] = {"path": str(self.old / "docs" / name), "binding": r.binding(self.docs / name)}
        self.original_manifest = original
        return producer, original, fake_rc

    def terminal(self, *, model="catalytic_fixed", status="input_failure"):
        self.decision.update(action="retain_input_failure")
        self.entry["model"] = model
        record, baseline = self.record("terminal_no_fit_recipe_replay")
        baseline.update(operation="retain_corrected_input_failure")
        attempt = self.repro / "attempts" / f"{self.ident}.terminal"
        attempt.mkdir(parents=True)
        historical = self.old / "repro/attempts" / attempt.name
        request = put(attempt / "request.json", {"original_cell_id": self.ident, "entry": self.entry,
            "attempt_path": str(historical), "selection_path": str(self.old / "repro/selection.json"),
            "selection_sha256": self.selection_sha, "fit_code": str(self.old / "fit"), "locked_python": "/old/python",
            "fit_implementation_source_sha256": self.rc.FIT_SOURCE_PINS,
            "implementation_source_sha256": self.selection["implementation_source_sha256"]})
        (attempt / "stdout.log").write_text("actual invented terminal child")
        (attempt / "stderr.log").write_text("")
        put(attempt / "invocation.json", {"operation": "isolated_selected_reproduction_child", "exit_code": 0,
            "launch_error": None, "numeric_thread_environment": {name: "1" for name in r.NUMERIC_VARIABLES},
            "argv": [request["locked_python"], "-I", "-B", str(self.old / "code/terminal_replay_child.py"),
                "--request", str(historical / "request.json"), "--request-sha256", r.binding(attempt / "request.json")["sha256"]],
            "stdout": r.binding(attempt / "stdout.log"), "stderr": r.binding(attempt / "stderr.log")})
        self.environment(attempt, request["locked_python"])
        names = ["outer", "inner_01", "inner_02", "inner_03"] if model == "catalytic_wme" else ["outer"]
        outcomes, saved_contexts = [], {}
        for name in names:
            row = {"context_id": self.ident + "::" + name, "outer_cell_id": self.ident, "generation_seed": 12}
            self.rows.append(row)
            target = attempt / "contexts" / name
            saved_directory = self.preflight / "contexts" / name
            target.mkdir(parents=True)
            saved_directory.mkdir(parents=True)
            if status == "input_failure":
                saved = {"status": status, "accepted_attempt_index": None, "attempts": [],
                    "input_error": {"type": "builtins.ValueError", "message": "invented input failure"}}
                actual = {**saved, "input_witness_sha256": None}
            else:
                error = {"type": "builtins.ValueError", "message": "invented nonrank guard"}
                draw = {"attempt_index": 0, "seed": 12, "status": "nonrank_error", "error": error,
                    "array_witnesses": None, "constructor_inputs": None, "legacy_metadata": None,
                    "actual_metadata": None, "processor_metadata": {"actual invented training": True}}
                saved = {"status": "nonrank_failure", "accepted_attempt_index": None,
                         "request": {"input_witness_sha256": "input"}, "attempts": [draw]}
                actual = {"status": "nonrank_failure", "accepted_attempt_index": None,
                          "input_witness_sha256": "input", "attempts": [copy.deepcopy(draw)]}
                put(target / "attempt_000/receipt.json", {**draw, "artifacts": {}})
            actual.update(context_id=row["context_id"], preflight_receipt_sha256=name + "_preflight")
            actual = put(target / "actual.json", actual)
            self.complete.lookup[row["context_id"]] = {"receipt_sha256": name + "_preflight"}
            assessment = self.rc.compare_context_history(saved, actual)
            outcomes.append({"context_id": row["context_id"], "status": actual["status"], "assessment": assessment,
                "actual_receipt_path": str((target / "actual.json").relative_to(attempt)),
                "actual_receipt_sha256": r.binding(target / "actual.json")["sha256"]})
            saved_contexts[row["context_id"]] = (saved_directory, saved)
        self.complete.context = lambda row: saved_contexts[row["context_id"]]
        receipt = {"status": "selected_terminal_full_recipe_independently_replayed_without_fit",
            "original_cell_id": self.ident, "selection_sha256": self.selection_sha,
            "scope_definition_sha256": self.rc.scope_definition(self.selection), "corrected_manifest_sha256": "manifest",
            "input_witness_sha256": "input", "contexts": outcomes, "artifacts": tree(attempt),
            "scoped_context_count": len(names), "normal_full_raw_training_preprocessor_fit": True,
            "candidate_adapter_restoration_or_thinning_used": False,
            "no_model_optimizer_mcmc_prediction_or_score_executed": True,
            "new_numerical_fitted_cell_reproduction": False, "all1650_contexts_replayed": False,
            "runtime": {"locked_interpreter_samefile": True, "numeric_thread_environment": {name: "1" for name in r.NUMERIC_VARIABLES}}}
        put(attempt / "receipt.json", receipt)
        record.update(terminal_receipt_path=str((attempt / "receipt.json").relative_to(self.repro)),
            scoped_generator_contexts=[row["context_id"] for row in self.rows], new_numerical_fit_executed=False,
            scientific_status="not_fit_input_failure")
        return record, baseline, attempt, saved_contexts

    def environment(self, attempt, python):
        put(attempt / "environment.stdout.json", self.preflight_document["environment_verification"], sealed=False)
        (attempt / "environment.stderr.log").write_text("")
        put(attempt / "environment_invocation.json", {"operation": "fresh_original_259_package_environment_verification",
            "exit_code": 0, "argv": [python, "-B", str(self.old / "source/scripts/verify_environment.py"),
                "--lock-file", str(self.old / "source/conda-lock.yml"), "--hash-file", str(self.old / "source/conda-lock.yml.sha256")],
            "source_sha256": self.original_manifest["input_sha256"]["scripts/verify_environment.py"],
            "stdout": r.binding(attempt / "environment.stdout.json"), "stderr": r.binding(attempt / "environment.stderr.log")})

    def inherited(self):
        producer, _, _ = self.producer()
        source, refit = self.cells(self.original, self.old_repro)
        comparison = self.rc.compare_cells(source, refit, self.original, self.old_repro, self.comparators)
        official = self.old_repro / "receipts" / f"{self.ident}.json"
        put(official, {"cell_id": self.ident, "status": "scientific_match",
            "source_content_sha256": comparison["left_content_sha256"], "refit_content_sha256": comparison["right_content_sha256"],
            "trace_sample_arrays": "exact; timing/NetCDF metadata excluded"}, sealed=False)
        review_path = self.docs / "execution_review.json"
        review = {"status": "original_numerical_refit_and_trace_comparison_execution_reviewed", "original_cell_id": self.ident,
            "original_manifest_sha256": self.common.ORIGINAL_MANIFEST_SHA, "comparison_source_sha256": self.rc.COMPARISON_PINS,
            "source_cell": r.binding(source), "refit_cell": r.binding(refit), "official_receipt": r.binding(official),
            "original_full_budget": True, "numerical_refit_executed": True, "owner_finished": True,
            "trace_inventory": comparison["trace_inventory"], "producer": producer}
        put(review_path, review)
        self.numerical = {self.ident: {"status": "verified_original_numerical_reproduction_evidence",
            "original_cell_id": self.ident, "owner_finished": True, "official_receipt_path": f"receipts/{self.ident}.json",
            "official_receipt": r.binding(official), "source_cell": r.binding(source), "refit_cell": r.binding(refit),
            "execution_review": {"path": str(self.old / "docs/execution_review.json"), "sha256": r.binding(review_path)["sha256"]},
            "trace_inventory": comparison["trace_inventory"]}}
        self.decision.update(action="reuse_original_outcome")
        record, baseline = self.record("reused_verified_original_numerical_reproduction")
        baseline.update(operation="reuse_original_outcome", original_reference={"sha256": r.binding(source)["sha256"]})
        record.update(comparison=comparison, new_numerical_fit_executed=False,
                      inherited_actual_original_numerical_refit_evidence=True)
        return record, baseline

    def terminal_rank_then_nonrank(self):
        record, baseline, attempt, saved_contexts = self.terminal(status="nonrank_failure")
        actual_path = attempt / "contexts/outer/actual.json"
        actual = r.document(actual_path)
        actual.pop("content_sha256")
        saved_directory, saved = saved_contexts[self.rows[0]["context_id"]]
        arrays = {"synthetic_design": [[1.0], [1.0]], "synthetic_time": [2.0, 3.0], "hazard": 0.25, "time_scale": 4.0}
        def witness(value):
            return {"dtype": "invented_float64", "shape": [] if isinstance(value, float) else [len(value)], "values_sha256": r.digest(value)}
        draw = {"attempt_index": 0, "seed": 12, "status": "frozen_rank_rejected",
            "error": {"type": "builtins.ValueError", "message": "synthetic design is not full column rank"},
            "array_witnesses": {key: witness(value) for key, value in arrays.items()},
            "constructor_inputs": {"independently_retained": True}, "legacy_metadata": None,
            "actual_metadata": {"processor_metadata": {"invented": True}, "processor_origin": "old proposal"},
            "processor_metadata": {"invented": True}}
        after = copy.deepcopy(draw)
        after["actual_metadata"]["processor_origin"] = "new normal full raw"
        nonrank = copy.deepcopy(actual["attempts"][0])
        nonrank.update(attempt_index=1, seed=77)
        saved["attempts"] = [draw, copy.deepcopy(nonrank)]
        actual["attempts"] = [after, nonrank]
        old_receipt = attempt / "contexts/outer/attempt_000/receipt.json"
        old_receipt.unlink()  # invented fixture construction only
        put(saved_directory / "attempt_000/proposal.npz", arrays, sealed=False)
        put(old_receipt.parent / "proposal.npz", arrays, sealed=False)
        put(old_receipt, {**after, "artifacts": {"proposal.npz": r.binding(old_receipt.parent / "proposal.npz")}})
        put(attempt / "contexts/outer/attempt_001/receipt.json", {**nonrank, "artifacts": {}})
        put(actual_path, actual)
        result = r.document(attempt / "receipt.json")
        result.pop("content_sha256")
        result["contexts"][0]["assessment"] = self.rc.compare_context_history(saved, actual)
        result["contexts"][0]["actual_receipt_sha256"] = r.binding(actual_path)["sha256"]
        result["artifacts"] = tree(attempt)
        result["artifacts"].pop("receipt.json")
        put(attempt / "receipt.json", result)
        self.fake_pf = SimpleNamespace(read_arrays=lambda path: json.loads(path.read_text()), array_witness=witness)
        return record, baseline, attempt


class ReceivingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.f = Fixture(self.root)
        ToyAZ.reads, ToyAZ.closed = [], []

    def tearDown(self):
        self.temp.cleanup()

    def producer_result(self, route="official_fresh_refit", mutate=None):
        producer, original, rc = self.f.producer(route)
        if mutate:
            mutate(producer, original, rc)
        value = self.f.value()
        resolver = r.Resolver(value, self.root / "fresh")
        resolver.verify()
        return r.verify_producer(producer, original, self.f.preflight_document["environment_verification"],
            self.f.old / "original", self.f.old / "old_repro", self.f.ident, resolver, self.f.common, rc)

    def test_runtime_accepts_samefile_and_numeric_one(self):
        self.assertTrue(r.runtime(Path(sys.executable), {name: "1" for name in r.NUMERIC_VARIABLES})["locked_interpreter_samefile"])

    def test_runtime_refuses_wrong_interpreter_before_binding_reads(self):
        with patch.object(r, "document", side_effect=AssertionError("should not read")):
            with self.assertRaisesRegex(r.InvalidEvidence, "interpreter"):
                r.verify_receiving(self.root / "missing", "bad", self.root / "out", self.root / "absent")

    def test_runtime_refuses_missing_numeric_variable(self):
        for name in r.NUMERIC_VARIABLES:
            with self.subTest(name=name):
                values = {key: "1" for key in r.NUMERIC_VARIABLES}
                values.pop(name)
                with self.assertRaises(r.InvalidEvidence):
                    r.runtime(Path(sys.executable), values)

    def test_runtime_alias_samefile_allowed_only_for_interpreter(self):
        path = self.root / "python_alias"
        path.symlink_to(sys.executable)
        self.assertTrue(r.runtime(path, {name: "1" for name in r.NUMERIC_VARIABLES})["locked_interpreter_samefile"])
        with self.assertRaises(r.InvalidEvidence):
            r.absolute(path)

    def test_resolver_maps_without_rewriting_original_document(self):
        before = (self.f.repro / "selection.json").read_bytes()
        resolver = r.Resolver(self.f.value(), self.root / "fresh")
        self.assertEqual(resolver.resolve(self.f.old / "repro/selection.json"), self.f.repro / "selection.json")
        self.assertEqual(resolver.historical(self.f.repro / "selection.json"), self.f.old / "repro/selection.json")
        resolver.verify()
        self.assertEqual(before, (self.f.repro / "selection.json").read_bytes())

    def test_resolver_refuses_unknown_historical_file(self):
        resolver = r.Resolver(self.f.value(), self.root / "fresh")
        with self.assertRaises(r.InvalidEvidence):
            resolver.resolve(Path("/unknown/input.json"))

    def test_resolver_rejects_relative_traversal(self):
        for name in ("../cell", "/cell", "", "a/../b", "a//b"):
            with self.subTest(name=name), self.assertRaises(r.InvalidEvidence):
                r.relative(name)

    def test_resolver_missing_pinned_file_rejected(self):
        value = self.f.value()
        (self.f.repro / "selection.json").unlink()
        with self.assertRaises(r.InvalidEvidence):
            r.Resolver(value, self.root / "fresh").verify()

    def test_resolver_extra_orphan_file_rejected(self):
        value = self.f.value()
        (self.f.repro / "unlisted_orphan.bin").write_bytes(b"retained unknown bytes")
        with self.assertRaises(r.InvalidEvidence):
            r.Resolver(value, self.root / "fresh").verify()

    def test_resolver_all_failed_orphan_bytes_are_bound(self):
        (self.f.repro / "attempts/failure.orphan").mkdir(parents=True)
        (self.f.repro / "attempts/failure.orphan/stderr.log").write_text("failed actual fixture")
        value = self.f.value()
        resolver = r.Resolver(value, self.root / "fresh")
        before = resolver.verify()
        (self.f.repro / "attempts/failure.orphan/stderr.log").write_text("altered")
        with self.assertRaises(r.InvalidEvidence):
            resolver.verify()
        self.assertGreater(before["immutable_file_count"], 1)

    def test_resolver_overlap_output_rejected(self):
        with self.assertRaises(r.InvalidEvidence):
            r.Resolver(self.f.value(), self.f.repro / "fresh")

    def test_resolver_duplicate_mapping_rejected(self):
        value = self.f.value()
        value["path_map"].append(value["path_map"][0])
        with self.assertRaises(r.InvalidEvidence):
            r.Resolver(value, self.root / "fresh")

    def test_resolver_inconsistent_nested_mapping_rejected(self):
        value = self.f.value()
        value["path_map"].append({"historical": str(self.f.old / "repro/selection.json"),
            "restored": str(self.f.preflight / "manifest.json"), "kind": "file"})
        with self.assertRaises(r.InvalidEvidence):
            r.Resolver(value, self.root / "fresh")

    def test_resolver_consistent_nested_file_mapping_allowed(self):
        value = self.f.value()
        value["path_map"].append({"historical": str(self.f.old / "repro/selection.json"),
            "restored": str(self.f.repro / "selection.json"), "kind": "file"})
        self.assertEqual(r.Resolver(value, self.root / "fresh").historical(self.f.repro / "selection.json"),
                         self.f.old / "repro/selection.json")

    def test_resolver_receiving_alias_ambiguity_rejected(self):
        value = self.f.value()
        value["path_map"].append({"historical": "/another/repro", "restored": str(self.f.repro), "kind": "directory"})
        with self.assertRaises(r.InvalidEvidence):
            r.Resolver(value, self.root / "fresh")

    def test_resolver_symlink_evidence_rejected(self):
        (self.f.docs / "linked").symlink_to(self.f.repro / "selection.json")
        with self.assertRaises(r.InvalidEvidence):
            self.f.value()

    def test_document_byte_content_and_nan_guards(self):
        path = self.f.docs / "test.json"
        put(path, {"v": 1})
        with self.assertRaises(r.InvalidEvidence):
            r.document(path, "wrong")
        path.write_text('{"v":NaN,"content_sha256":"none"}')
        with self.assertRaises(r.InvalidEvidence):
            r.document(path)

    def test_write_new_never_overwrites(self):
        path = self.f.docs / "new.json"
        r.write_new(path, r.seal({"v": 1}))
        with self.assertRaises(FileExistsError):
            r.write_new(path, r.seal({"v": 2}))

    def test_mapped_common_read_preserves_document(self):
        verifier = self.f.verifier()
        self.assertEqual(verifier.common.read_json(self.f.old / "repro/selection.json"), self.f.selection)
        self.assertEqual(verifier.common.sha(self.f.old / "repro/selection.json"), self.f.selection_sha)

    def test_mapped_common_forbids_restore_writes_and_claims(self):
        verifier = self.f.verifier()
        with self.assertRaises(r.InvalidEvidence):
            verifier.common.write_new(self.f.repro / "illegal.json", r.seal({"x": 1}))
        with self.assertRaises(r.InvalidEvidence):
            verifier.common.Claim(self.f.repro / "claim", "id")
        with self.assertRaises(r.InvalidEvidence):
            verifier.common.verify_original_source(self.f.source, {})

    def test_mapped_original_gates_on_complete_invented1625_1650_metadata(self):
        """Exercise real stdlib gate code only, with invented full metadata."""
        common, _ = load_source_helpers()
        fit_source = Path(os.environ["REPRO_RESTORE_TEST_FIT_CODE"])
        parent = fit_source.parent
        for name in common.OWN_SOURCES:
            (self.f.fit / name).write_bytes((fit_source / name).read_bytes())
        helpers = {
            "contracts.py": parent / "generator_correction_fit_preparation_v1/correction_fit_contracts.py",
            "pf.py": parent / "generator_correction_preflight_runner_v1/preflight_core.py",
            "reuse.py": parent / "generator_correction_reuse_runner_v1/reuse_core.py"}
        for name, path in helpers.items():
            (self.f.docs / name).write_bytes(path.read_bytes())
        ids = self.f.ids + [f"d__extra{i:04d}__r02f02__c__catalytic_fixed" for i in range(1533)]
        original = put(self.f.original / "manifest.json", {
            "code": {"git_commit": common.ORIGINAL_COMMIT, "git_dirty": False},
            "input_sha256": {"conda-lock.yml": "invented_lock"}, "plan": [{"cell_id": identity} for identity in ids],
            "run_config": {"sampling": {"draws": 2000, "tune": 2000, "chains": 4, "target_accept": 0.999,
                "maximum_refits": 2, "cores": 1, "refit_tune_multiplier": 2, "final_noncentered_baseline": True}}},
            field="manifest_content_sha256")
        common.ORIGINAL_MANIFEST_SHA = r.binding(self.f.original / "manifest.json")["sha256"]
        common.ORIGINAL_CONTENT_SHA = original["manifest_content_sha256"]
        manifest = put(self.f.preflight / "manifest.json", {"original_manifest_sha256": common.ORIGINAL_MANIFEST_SHA,
            "environment_verification": {"status": "ok", "package_count": 259, "lock_sha256": "invented_lock"}})
        complete_rows = [{"context_id": f"invented_{index:04d}::outer", "status": "input_failure",
                          "receipt_sha256": f"invented_hash{index}"} for index in range(1650)]
        put(self.f.preflight / "completion.json", {"status": "all_scheduled_contexts_accounted", "scheduled_contexts": 1650,
            "accounted_contexts": 1650, "outcomes": complete_rows, "run_binding_sha256": manifest["content_sha256"]})
        completion_sha = r.binding(self.f.preflight / "completion.json")["sha256"]
        put(self.f.docs / "arithmetic_evidence.json", {"invented": True})
        proof = r.binding(self.f.docs / "arithmetic_evidence.json")
        put(self.f.docs / "accounting.json", {"status": "all_scheduled_arithmetic_outcomes_accounted",
            "preflight_completion_sha256": completion_sha, "proposals_selected_by_optimizer": False,
            "extra_proposals_generated": False, "artifacts": {"arithmetic_evidence.json": proof},
            "context_outcomes": [{"context_id": item["context_id"], "preflight_status": item["status"],
                "preflight_receipt_sha256": item["receipt_sha256"], "evidence_sha256": [proof["sha256"]],
                "kappa_required": False, "status": "preflight_input_failure", "formula_checks": "not_applicable",
                "original_kappa_status": "not_applicable"} for item in complete_rows]})
        put(self.f.docs / "inventory.json", {"definition_content_sha256": "definition", "scheduled_cells": 1625,
            "entries": [{"original_cell_id": identity} for identity in ids], "selection_scope": [],
            "preflight_completion_sha256": completion_sha})
        inventory_sha = r.binding(self.f.docs / "inventory.json")["sha256"]
        freeze = {"status": "reviewed_corrected_fit_freeze", "original_production_commit": common.ORIGINAL_COMMIT,
            "original_manifest_sha256": common.ORIGINAL_MANIFEST_SHA, "definition_content_sha256": "definition",
            "input_inventory_sha256": inventory_sha, "preflight_completion_sha256": completion_sha,
            "preflight_manifest_sha256": r.binding(self.f.preflight / "manifest.json")["sha256"],
            "implementation_source_sha256": {name: r.binding(self.f.fit / name)["sha256"] for name in common.OWN_SOURCES},
            "dependency_source_sha256": {"contracts": common.CONTRACTS_SHA, "preflight_core": common.PREFLIGHT_CORE_SHA,
                                         "reuse_core": common.REUSE_CORE_SHA},
            "paths": self.f.freeze["paths"], "arithmetic_accounting": {"path": str(self.f.old / "docs/accounting.json"),
                "sha256": r.binding(self.f.docs / "accounting.json")["sha256"]},
            "execution": {"fit_workers": 1, "numeric_threads": 1, "original_full_budget": True,
                "pilot_rule": common.PILOT_RULE, "pilot_eligibility": common.PILOT_ELIGIBILITY,
                "original_resolution_policy": "fresh_reviewed_finished_source_snapshot"}}
        freeze["review_bindings"] = {}
        for role in ("method", "arithmetic", "input_witness", "implementation", "freeze"):
            path = self.f.docs / f"review_{role}.json"
            put(path, {"status": "reviewed_for_corrected_fit_execution", "role": role,
                "definition_content_sha256": "definition", "input_inventory_sha256": inventory_sha,
                "execution_definition_sha256": common.execution_definition(freeze)})
            freeze["review_bindings"][role] = {"path": str(self.f.old / "docs" / path.name), "sha256": r.binding(path)["sha256"]}
        put(self.f.docs / "freeze.json", freeze)
        freeze_sha = r.binding(self.f.docs / "freeze.json")["sha256"]
        put(self.f.corrected / "manifest.json", {"status": "corrected_fit_manifest_frozen", "freeze_sha256": freeze_sha,
            "input_inventory_sha256": inventory_sha, "definition_content_sha256": "definition", "pilot_cells": []})
        manifest_sha = r.binding(self.f.corrected / "manifest.json")["sha256"]
        before = tree(self.f.docs)
        resolver = r.Resolver(self.f.value(), self.root / "fresh")
        r.mapped_common(common, resolver)
        actual = common.load_gates(self.f.old / "docs/freeze.json", freeze_sha,
            self.f.old / "corrected/manifest.json", manifest_sha, self.f.old / "fit")
        self.assertEqual(len(actual[2]["entries"]), 1625)
        self.assertEqual(len(actual[3]["outcomes"]), 1650)
        self.assertEqual(tree(self.f.docs), before)

    def test_original_science_and_sample_comparison_reads_invented_samples(self):
        left, right = self.f.cells(self.f.original, self.f.old_repro)
        result = self.f.rc.compare_cells(left, right, self.f.original, self.f.old_repro, self.f.comparators)
        self.assertEqual(result["actual_returned_trace_pairs_compared"], 1)
        self.assertEqual(len(ToyAZ.reads), 2)
        self.assertEqual(ToyAZ.closed, ToyAZ.reads)
        self.assertEqual(len(result["trace_inventory"][0]["unreferenced"]), 1)

    def test_original_sample_value_mismatch_refused_even_when_resealed(self):
        left, right = self.f.cells(self.f.original, self.f.old_repro)
        trace = self.f.old_repro / "traces" / self.f.ident / "trace.json"
        value = json.loads(trace.read_text())
        value["posterior"]["beta"][0] = 0.4
        put(trace, value, sealed=False)
        cell = r.document(right, field="cell_content_sha256")
        cell.pop("cell_content_sha256")
        cell["fit_attempts"][0]["traces"]["initial"]["sha256"] = r.binding(trace)["sha256"]
        put(right, cell, field="cell_content_sha256")
        with self.assertRaisesRegex(ValueError, "sampled values"):
            self.f.rc.compare_cells(left, right, self.f.original, self.f.old_repro, self.f.comparators)
        self.assertEqual(ToyAZ.closed, ToyAZ.reads)

    def test_original_scientific_mismatch_refused(self):
        left, right = self.f.cells(self.f.original, self.f.old_repro)
        cell = r.document(right, field="cell_content_sha256")
        cell.pop("cell_content_sha256")
        cell["estimate"] = 0.9
        put(right, cell, field="cell_content_sha256")
        with self.assertRaisesRegex(ValueError, "scientific number"):
            self.f.rc.compare_cells(left, right, self.f.original, self.f.old_repro, self.f.comparators)

    def test_original_failed_outcome_comparison_is_not_claimed_samples(self):
        paths = []
        for root in (self.f.original, self.f.old_repro):
            path = root / "cells" / f"{self.f.ident}.json"
            put(path, {"cell_id": self.f.ident, "status": "failed", "error": "original failure", "fit_attempts": []}, field="cell_content_sha256")
            paths.append(path)
        result = self.f.rc.compare_cells(*paths, self.f.original, self.f.old_repro, self.f.comparators)
        self.assertEqual(result["sample_array_comparison_scope"], "no_returned_sample_arrays")
        self.assertFalse(result["new_numerical_fit_executed_by_comparison"])

    def test_frozen_original92_union_pilot_scope(self):
        original = {"plan": [{"cell_id": identity} for identity in self.f.ids]}
        pilot = "d__new__r02f02__c__catalytic_fixed"
        original["plan"].append({"cell_id": pilot})
        selection = copy.deepcopy(self.f.selection)
        selection["pilot_cells"] = sorted([self.f.ident, pilot])
        selection["selected_cells"] = sorted(set(self.f.ids + [pilot]))
        self.f.rc.validate_scope(selection, original, {"pilot_cells": selection["pilot_cells"]})
        self.assertEqual(len(selection["selected_cells"]), 93)
        selection["selected_cells"].pop()
        with self.assertRaises(ValueError):
            self.f.rc.validate_scope(selection, original, {"pilot_cells": selection["pilot_cells"]})

    def test_complete_pass_exact_sorted_coverage(self):
        outcomes = [{"original_cell_id": identity, "status": "terminal_no_fit_recipe_replay", "record_sha256": identity} for identity in self.f.ids]
        value = self.f.rc.publication_status(outcomes, self.f.ids)
        value.update(selection_sha256=self.f.selection_sha, scope_definition_sha256=self.f.rc.scope_definition(self.f.selection),
            original_fixed_selected_cells=92, pilot_union_selected_cells=92, correction_freeze_sha256="freeze",
            corrected_manifest_sha256="manifest", original_comparison_source_sha256=self.f.rc.COMPARISON_PINS)
        r.complete_pass(value, self.f.selection, self.f.selection_sha, self.f.rc)
        for mutation in (lambda v: v["outcomes"].reverse(), lambda v: v.update(selection_sha256="different"),
                         lambda v: v["outcomes"][0].update(status="pending_original_numerical_reproduction")):
            broken = copy.deepcopy(value)
            mutation(broken)
            with self.assertRaises(ValueError):
                r.complete_pass(broken, self.f.selection, self.f.selection_sha, self.f.rc)

    def test_record_cannot_promote_retained_failure(self):
        record, _ = self.f.record("retained_reproduction_failure")
        verifier = self.f.verifier()
        with self.assertRaises(r.InvalidEvidence):
            r.verify_record(record, self.f.ident, self.f.selection, self.f.selection_sha,
                self.f.repro, verifier.resolver, verifier.common, self.f.rc)

    def test_actual_official_numerical_producer_and_distinct_comparator(self):
        result = self.producer_result()
        self.assertFalse(result["new_numerical_fit_executed"])
        self.assertEqual(result["route"], "official_fresh_refit")

    def test_actual_prestage_producer_and_cached_official_comparison(self):
        result = self.producer_result("reviewed_external_prestage")
        self.assertEqual(result["route"], "reviewed_external_prestage")

    def test_cached_official_comparison_alone_refused(self):
        def mutate(producer, original, rc):
            invocation = r.document(self.f.docs / "invocation.json")
            invocation.pop("content_sha256")
            invocation.update(cached_comparison_only=True, actual_numerical_refit_execution=False)
            put(self.f.docs / "invocation.json", invocation)
            producer["invocation_record"]["binding"] = r.binding(self.f.docs / "invocation.json")
        with self.assertRaisesRegex(r.InvalidEvidence, "producer proof"):
            self.producer_result(mutate=mutate)

    def test_historical_producer_source_input_tamper_refused(self):
        def mutate(producer, original, rc):
            (self.f.source / "scripts/reproduce_extensions.py").write_text("different source")
        with self.assertRaisesRegex(r.InvalidEvidence, "source/input"):
            self.producer_result(mutate=mutate)

    def test_historical_actual_producer_missing_commit_input_coverage_refused(self):
        with self.assertRaisesRegex(r.InvalidEvidence, "coverage"):
            self.producer_result(mutate=lambda producer, original, rc: producer.update(git_commit="other"))

    def test_wrong_actual_prestage_helper_refused(self):
        with self.assertRaisesRegex(r.InvalidEvidence, "helper pin"):
            self.producer_result("reviewed_external_prestage", mutate=lambda producer, original, rc: setattr(rc, "PRESTAGE_HELPER_SHA", "wrong"))

    def test_wrong_actual_prestage_worker_shard_refused(self):
        def mutate(producer, original, rc):
            invocation = r.document(self.f.docs / "invocation.json")
            invocation.pop("content_sha256")
            invocation["worker"] = 1
            invocation["argv"][invocation["argv"].index("--worker") + 1] = "1"
            put(self.f.docs / "invocation.json", invocation)
            producer["invocation_record"]["binding"] = r.binding(self.f.docs / "invocation.json")
        with self.assertRaisesRegex(r.InvalidEvidence, "shard does not own"):
            self.producer_result("reviewed_external_prestage", mutate=mutate)

    def test_historical_cached_compare_flag_must_match_actual_route(self):
        def mutate(producer, original, rc):
            official = r.document(self.f.docs / "official.json")
            official.pop("content_sha256")
            official["cached_comparison_only"] = False
            put(self.f.docs / "official.json", official)
            producer["official_comparison_record"]["binding"] = r.binding(self.f.docs / "official.json")
        with self.assertRaisesRegex(r.InvalidEvidence, "official comparison"):
            self.producer_result("reviewed_external_prestage", mutate=mutate)

    def test_recorded_argv_duplicate_wrong_relative_source_refused(self):
        base = {"argv": ["python", "scripts/a.py", "--source", "/old/run"], "script_index": 1, "cwd": "/old/code"}
        r.recorded_argv(base, Path("/old/code/scripts/a.py"), (("--source", "/old/run"),))
        for values in (["python", "scripts/other.py", "--source", "/old/run"],
                       ["python", "scripts/a.py", "--source", "/old/run", "--source", "/old/run"],
                       ["python", "scripts/a.py", "--source", "/wrong"]):
            with self.subTest(values=values), self.assertRaises(r.InvalidEvidence):
                r.recorded_argv({**base, "argv": values}, Path("/old/code/scripts/a.py"), (("--source", "/old/run"),))

    def test_changed_actual_execution_and_sample_recomparison(self):
        record, baseline, _ = self.f.changed()
        verifier = self.f.verifier()
        result = verifier.changed(self.f.ident, record, baseline, self.f.entry, self.f.decision, self.f.witness)
        self.assertFalse(result["new_numerical_fit_executed_at_receiving"])
        self.assertTrue(result["historical_new_corrected_numerical_reproduction_preserved"])

    def test_changed_nonzero_actual_child_not_accepted(self):
        record, baseline, attempt = self.f.changed()
        invocation = r.document(attempt / "invocation.json")
        invocation.pop("content_sha256")
        invocation["exit_code"] = 1
        put(attempt / "invocation.json", invocation)
        with self.assertRaisesRegex(r.InvalidEvidence, "child execution"):
            self.f.verifier().changed(self.f.ident, record, baseline, self.f.entry, self.f.decision, self.f.witness)

    def test_changed_extra_budget_or_wrong_seed_request_refused(self):
        record, baseline, attempt = self.f.changed()
        request = r.document(attempt / "request.json")
        request.pop("content_sha256")
        request["entry"]["input_witness_sha256"] = "other"
        put(attempt / "request.json", request)
        with self.assertRaisesRegex(r.InvalidEvidence, "exact original law"):
            self.f.verifier().changed(self.f.ident, record, baseline, self.f.entry, self.f.decision, self.f.witness)

    def test_changed_complete_role_hash_receipt_required(self):
        record, baseline, attempt = self.f.changed()
        child = r.document(attempt / "child_receipt.json")
        child.pop("content_sha256")
        checked = child["full_current_execution_input_verification"]
        checked.pop("content_sha256")
        checked["corrected_role_sha256"]["role"] = "opaque_other"
        child["full_current_execution_input_verification"] = r.seal(checked)
        put(attempt / "child_receipt.json", child)
        with self.assertRaisesRegex(r.InvalidEvidence, "complete execution input"):
            self.f.verifier().changed(self.f.ident, record, baseline, self.f.entry, self.f.decision, self.f.witness)

    def test_changed_sample_array_disagreement_not_hidden_by_receipt(self):
        record, baseline, attempt = self.f.changed()
        value = json.loads((attempt / "traces" / self.f.ident / "trace.json").read_text())
        value["sample_stats"]["diverging"][0] = 1
        put(attempt / "traces" / self.f.ident / "trace.json", value, sealed=False)
        with self.assertRaises(ValueError):
            self.f.verifier().changed(self.f.ident, record, baseline, self.f.entry, self.f.decision, self.f.witness)

    def test_nonpilot_requires_supplied_full_budget_pilot_review(self):
        record, baseline, _ = self.f.changed()
        self.f.manifest["pilot_cells"] = []
        with self.assertRaisesRegex(r.InvalidEvidence, "pilot review"):
            self.f.verifier().changed(self.f.ident, record, baseline, self.f.entry, self.f.decision, self.f.witness)

    def test_terminal_later_acquisition_preserves_exact_pending_decision(self):
        record, baseline = self.f.record("terminal_no_fit_recipe_replay")
        pending = {**self.f.decision, "action": "retain_input_failure", "source_evidence": None}
        self.f.decision.update(action="retain_input_failure")
        self.f.contracts.classify = lambda witness: {**self.f.decision, "source_evidence": witness.original_evidence}
        baseline.update(operation="retain_corrected_input_failure", original_outcome_pending=True,
                        source_evidence=None, decision=pending)
        snapshot = {"source_evidence": self.f.decision["source_evidence"], "decision": self.f.decision,
            "input_witness_sha256": "input", "definition_content_sha256": "definition"}
        snapshot_path = self.f.witness_root / "snapshot.json"
        put(snapshot_path, snapshot)
        bound = {"snapshot_path": "snapshot.json", "snapshot_sha256": r.binding(snapshot_path)["sha256"],
            "current_reviewed_acquisition_decision": self.f.decision}
        self.f.inputs.resolutions[self.f.ident] = bound
        verifier = self.f.verifier()
        verifier.acquisition(bound, self.f.entry, self.f.decision, baseline, self.f.witness)
        broken = {**bound, "snapshot_sha256": "wrong"}
        with self.assertRaises(r.InvalidEvidence):
            verifier.acquisition(broken, self.f.entry, self.f.decision, baseline, self.f.witness)
        self.assertEqual(baseline["decision"], pending)

    def test_inherited_actual_refit_science_and_sample_arrays_recompared(self):
        record, baseline = self.f.inherited()
        result = self.f.verifier().inherited(self.f.ident, record, baseline)
        self.assertFalse(result["new_numerical_fit_executed_at_receiving"])
        self.assertEqual(result["comparison"]["actual_returned_trace_pairs_compared"], 1)

    def test_inherited_pending_original_producer_evidence_blocks(self):
        record, baseline = self.f.inherited()
        self.f.numerical[self.f.ident] = {"status": "pending_original_numerical_reproduction"}
        with self.assertRaisesRegex(r.InvalidEvidence, "pending/unknown"):
            self.f.verifier().inherited(self.f.ident, record, baseline)

    def test_inherited_source_owner_active_blocks(self):
        record, baseline = self.f.inherited()
        (self.f.old_repro / "claims").mkdir()
        (self.f.old_repro / "claims" / f"{self.f.ident}.json").write_text("active invented owner")
        with self.assertRaisesRegex(r.InvalidEvidence, "owner active"):
            self.f.verifier().inherited(self.f.ident, record, baseline)

    def test_terminal_input_failure_evidence_recompared_without_generation(self):
        record, baseline, _, _ = self.f.terminal()
        result = self.f.verifier().terminal(self.f.ident, record, baseline, self.f.entry)
        self.assertFalse(result["new_terminal_recipe_execution_at_receiving"])
        self.assertEqual(result["contexts"][0]["assessment"]["attempts_compared"], 0)

    def test_terminal_wme_all_unreached_inner_contexts_required(self):
        record, baseline, _, _ = self.f.terminal(model="catalytic_wme")
        result = self.f.verifier().terminal(self.f.ident, record, baseline, self.f.entry)
        self.assertEqual(len(result["contexts"]), 4)
        self.f.rows.pop()
        with self.assertRaisesRegex(ValueError, "context coverage"):
            self.f.verifier().terminal(self.f.ident, record, baseline, self.f.entry)

    def test_terminal_actual_nonrank_error_retained_historical_constructor_unavailable(self):
        record, baseline, _, _ = self.f.terminal(status="nonrank_failure")
        result = self.f.verifier().terminal(self.f.ident, record, baseline, self.f.entry)
        self.assertEqual(result["contexts"][0]["assessment"]["nonrank_constructor_identity"], "historically_unavailable")

    def test_terminal_constructor_error_changed_even_when_resealed_blocks(self):
        record, baseline, attempt, _ = self.f.terminal(status="nonrank_failure")
        receipt_path = attempt / "contexts/outer/actual.json"
        actual = r.document(receipt_path)
        actual.pop("content_sha256")
        actual["attempts"][0]["error"]["message"] = "different original exception"
        put(receipt_path, actual)
        terminal = r.document(attempt / "receipt.json")
        terminal.pop("content_sha256")
        terminal["contexts"][0]["actual_receipt_sha256"] = r.binding(receipt_path)["sha256"]
        terminal["artifacts"] = tree(attempt)
        terminal["artifacts"].pop("receipt.json")
        put(attempt / "receipt.json", terminal)
        with self.assertRaisesRegex(ValueError, "nonrank error"):
            self.f.verifier().terminal(self.f.ident, record, baseline, self.f.entry)

    def test_terminal_thin_restore_or_fitted_claim_refused(self):
        record, baseline, attempt, _ = self.f.terminal()
        receipt = r.document(attempt / "receipt.json")
        receipt.pop("content_sha256")
        receipt["candidate_adapter_restoration_or_thinning_used"] = True
        put(attempt / "receipt.json", receipt)
        with self.assertRaisesRegex(r.InvalidEvidence, "scoped no-fit"):
            self.f.verifier().terminal(self.f.ident, record, baseline, self.f.entry)

    def test_terminal_failed_actual_child_is_not_a_completed_route(self):
        record, baseline, attempt, _ = self.f.terminal()
        value = r.document(attempt / "invocation.json")
        value.pop("content_sha256")
        value["exit_code"] = 9
        put(attempt / "invocation.json", value)
        with self.assertRaisesRegex(r.InvalidEvidence, "child execution"):
            self.f.verifier().terminal(self.f.ident, record, baseline, self.f.entry)

    def test_terminal_seed_history_mismatch_is_not_hash_only_acceptance(self):
        record, baseline, _, saved = self.f.terminal(status="nonrank_failure")
        saved[self.f.rows[0]["context_id"]][1]["attempts"][0]["seed"] = 99
        with self.assertRaisesRegex(ValueError, "seed/outcome"):
            self.f.verifier().terminal(self.f.ident, record, baseline, self.f.entry)

    def test_terminal_attempt_receipt_is_separate_from_unsealed_actual_history(self):
        record, baseline, attempt, _ = self.f.terminal(status="nonrank_failure")
        persisted = r.document(attempt / "contexts/outer/attempt_000/receipt.json")
        actual = r.document(attempt / "contexts/outer/actual.json")
        self.assertNotEqual(persisted, actual["attempts"][0])
        self.f.verifier().terminal(self.f.ident, record, baseline, self.f.entry)

    def test_terminal_orphan_attempt_bound_but_does_not_match_recipe(self):
        record, baseline, attempt, _ = self.f.terminal(status="nonrank_failure")
        (attempt / "contexts/outer/attempt_001").mkdir()
        with self.assertRaisesRegex(r.InvalidEvidence, "attempt set"):
            self.f.verifier().terminal(self.f.ident, record, baseline, self.f.entry)

    def test_terminal_rejected_constructor_arrays_checked_without_svd(self):
        record, baseline, _ = self.f.terminal_rank_then_nonrank()
        verifier = self.f.verifier()
        verifier.pf = self.f.fake_pf
        result = verifier.terminal(self.f.ident, record, baseline, self.f.entry)
        self.assertEqual(result["contexts"][0]["assessment"]["attempts_compared"], 2)
        self.assertFalse(result["new_terminal_recipe_execution_at_receiving"])

    def test_terminal_rejected_constructor_values_tampered_and_resealed_blocks(self):
        record, baseline, attempt = self.f.terminal_rank_then_nonrank()
        path = attempt / "contexts/outer/attempt_000/proposal.npz"
        arrays = json.loads(path.read_text())
        arrays["synthetic_time"][0] = 20.0
        put(path, arrays, sealed=False)
        draw_path = path.with_name("receipt.json")
        draw = r.document(draw_path)
        draw.pop("content_sha256")
        draw["artifacts"]["proposal.npz"] = r.binding(path)
        put(draw_path, draw)
        receipt = r.document(attempt / "receipt.json")
        receipt.pop("content_sha256")
        receipt["artifacts"] = tree(attempt)
        receipt["artifacts"].pop("receipt.json")
        put(attempt / "receipt.json", receipt)
        verifier = self.f.verifier()
        verifier.pf = self.f.fake_pf
        with self.assertRaisesRegex(r.InvalidEvidence, "constructor dtype/shape/element"):
            verifier.terminal(self.f.ident, record, baseline, self.f.entry)

    def test_terminal_historic_environment_checker_nonzero_blocks(self):
        record, baseline, attempt, _ = self.f.terminal()
        path = attempt / "environment_invocation.json"
        env = r.document(path)
        env.pop("content_sha256")
        env["exit_code"] = 3
        put(path, env)
        with self.assertRaisesRegex(r.InvalidEvidence, "checker rc0"):
            self.f.verifier().terminal(self.f.ident, record, baseline, self.f.entry)

    def test_full_api_synthetic_capture_outside_restore_and_no_resume(self):
        value = self.f.value()
        put(self.f.repro / "passes/complete.json", {"invented": True})
        value = self.f.value()
        value["completed_pass"]["sha256"] = r.binding(self.f.repro / "passes/complete.json")["sha256"]
        bindings = self.root / "receiving_bindings.json"
        put(bindings, value)
        sha = r.binding(bindings)["sha256"]
        before = tree(self.f.repro)
        output = self.root / "fresh"
        outcomes = [{"original_cell_id": identity, "route": sorted(r.FINAL_STATUSES)[index % 3]}
                    for index, identity in enumerate(self.f.ids)]
        def fake_run(pass_value, owned):
            self.assertTrue(pass_value["invented"])
            for item in outcomes:
                r.write_new(owned / "cells" / f"{item['original_cell_id']}.json", r.seal({**item, "synthetic": True}))
            return outcomes
        fake = SimpleNamespace(root=self.f.repro, selection=self.f.selection, rc=self.f.rc, run=fake_run)
        def dependency(*args):
            return {"environment": {"report": {"status": "ok", "package_count": 259}, "invocation": {"exit_code": 0}}}
        with patch.dict(os.environ, {name: "1" for name in r.NUMERIC_VARIABLES}), patch.object(r, "ReceivingVerifier", return_value=fake):
            receipt = r.verify_receiving(bindings, sha, output, Path(sys.executable), dependencies=dependency)
            with self.assertRaisesRegex(r.InvalidEvidence, "never resumes"):
                r.verify_receiving(bindings, sha, output, Path(sys.executable), dependencies=dependency)
        self.assertEqual(tree(self.f.repro), before)
        self.assertEqual(receipt["status"], "synthetic_receiving_verification_fixture_passed")
        self.assertTrue(receipt["test_only_dependency_injection"])
        self.assertFalse(receipt["new_numerical_fit_executed"])
        self.assertEqual(sum(receipt["selected_route_counts"].values()), 92)
        self.assertEqual(r.document(output / "receipt.json"), receipt)

    def test_full_api_retains_failure_outside_restore_without_success_receipt(self):
        value = self.f.value()
        path = self.root / "receiving_bindings.json"
        put(path, value)
        output = self.root / "fresh"
        before = tree(self.f.repro)
        def broken(*args):
            raise RuntimeError("invented missing proof")
        with patch.dict(os.environ, {name: "1" for name in r.NUMERIC_VARIABLES}):
            with self.assertRaisesRegex(RuntimeError, "missing proof"):
                r.verify_receiving(path, r.binding(path)["sha256"], output, Path(sys.executable), dependencies=broken)
        self.assertEqual(tree(self.f.repro), before)
        self.assertEqual(r.document(output / "failure.json")["status"], "receiving_verification_failed_retained")
        self.assertFalse((output / "receipt.json").exists())

    def test_full_api_self_source_pin_tamper_fails_before_output_creation(self):
        value = self.f.value()
        value["receiving_source_sha256"]["receiving_core.py"] = "wrong"
        path = self.root / "receiving_bindings.json"
        put(path, value)
        output = self.root / "fresh"
        with patch.dict(os.environ, {name: "1" for name in r.NUMERIC_VARIABLES}), self.assertRaisesRegex(r.InvalidEvidence, "helper sources"):
            r.verify_receiving(path, r.binding(path)["sha256"], output, Path(sys.executable), dependencies=lambda *args: {})
        self.assertFalse(output.exists())

    def test_original_numerical_resolution_only_fills_pending(self):
        base = {"entries": {self.f.ident: {"status": "pending_original_numerical_reproduction"}}}
        review = {"status": "reviewed_original_numerical_evidence_resolution", "scope_definition_sha256": self.f.rc.scope_definition(self.f.selection),
            "original_manifest_sha256": self.f.common.ORIGINAL_MANIFEST_SHA,
            "entries": {self.f.ident: {"status": "verified_original_numerical_reproduction_evidence"}}}
        result = r.original_evidence(self.f.selection, base, (self.f.docs / "review.json", review), self.f.common, self.f.rc)
        self.assertEqual(result[self.f.ident]["status"], "verified_original_numerical_reproduction_evidence")
        base["entries"][self.f.ident]["status"] = "verified_original_numerical_reproduction_evidence"
        with self.assertRaises(r.InvalidEvidence):
            r.original_evidence(self.f.selection, base, (self.f.docs / "review.json", review), self.f.common, self.f.rc)

    def test_preparation_ast_no_generator_model_fit_or_scoring_dispatch(self):
        modules = [ast.parse((HERE / name).read_text()) for name in r.OWN_SOURCES]
        forbidden = {"run_extension_cell", "generate_catalytic_data", "original_draw", "replay_recipe", "select_parameters",
                     "fit_model", "minimize", "sample", "predict_survival", "predict_risk", "capture_child", "record"}
        called = {node.func.attr for module in modules for node in ast.walk(module)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)}
        self.assertFalse(called & forbidden)
        for node in ast.walk(modules[0]):
            if isinstance(node, ast.ImportFrom):
                self.assertFalse((node.module or "").startswith("src"))


if __name__ == "__main__":
    unittest.main()
