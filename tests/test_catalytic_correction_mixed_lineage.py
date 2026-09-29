"""Fictional small receipts exercise lineage, lifecycle and telemetry refusals."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

VERIFICATION = Path(__file__).resolve().parents[1] / "scripts/catalytic_correction/verification"
sys.path.insert(0, str(VERIFICATION))

from bound_lineage import telemetry_number, verify_observations  # noqa: E402
from mixed_analysis import document, execute_verified  # noqa: E402
from mixed_lineage import EVIDENCE, resolve_record, source_evidence  # noqa: E402
from verification_gates import (  # noqa: E402 - byte-identical flat CLI imports
    ORIGINAL_COMMIT,
    ORIGINAL_MANIFEST,
    unique_ids,
    validate_documents,
)
from verification_io import Pins, VerificationFailure, canonical, seal, sha, write_new  # noqa: E402

from tests.test_catalytic_correction_science_verification import Backend, cell  # noqa: E402


def evidence(value, path):
    return {"original_cell_id": value["cell_id"], "original_manifest_sha256": ORIGINAL_MANIFEST,
            "cell_byte_sha256": sha(path), "cell_content_sha256": value["cell_content_sha256"], "status": value["status"],
            "verification_receipt_sha256": "e" * 64, "referenced_trace_sha256": {}, "unreferenced_trace_sha256": {},
            "wme_tuning_record_sha256": None}


class LineageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fictional_mixed_lineage_")
        self.root = Path(self.temp.name).resolve()
        self.original, self.corrected = self.root / "original", self.root / "corrected"
        for root in (self.original, self.corrected):
            root.mkdir()
            (root / "cells").mkdir()
            (root / "claims").mkdir()
        self.value = cell(status="failed")
        self.value.update(dataset="toy", setting="clinical", condition="full", seconds=1.0)
        self.value["cell_content_sha256"] = canonical({k: v for k, v in self.value.items() if k != "cell_content_sha256"})
        self.path = self.original / "cells" / (self.value["cell_id"] + ".json")
        write_new(self.path, self.value)
        self.evidence = evidence(self.value, self.path)
        self.pins = Pins()
        self.decision = {"original_cell_id": self.value["cell_id"], "action": "reuse_original_outcome",
                         "source_evidence": self.evidence, "generator_failures": []}
        self.record = {"original_cell_id": self.value["cell_id"], "corrected_manifest_sha256": "m" * 64,
                       "correction_freeze_sha256": "f" * 64, "definition_content_sha256": "d" * 64,
                       "input_witness_sha256": "i" * 64, "evidence_status": EVIDENCE, "decision": self.decision,
                       "source_evidence": self.evidence, "operation": "reuse_original_outcome", "scientific_status": "failed",
                       "fit_dispatched": False, "newly_executed_fit": False, "fit_seconds": 0.0, "artifacts": {},
                       "original_reference": {"logical_root": "original_extension_run", "path": f"cells/{self.value['cell_id']}.json",
                                              "sha256": sha(self.path), "cell_content_sha256": self.value["cell_content_sha256"]}}

    def tearDown(self):
        self.temp.cleanup()

    def resolve(self):
        return resolve_record(record=self.record, original=self.value, decision=self.decision,
            manifest_sha="m" * 64, freeze_sha="f" * 64, definition_sha="d" * 64, input_witness_sha="i" * 64,
            original_root=self.original, corrected_root=self.corrected, pins=self.pins,
            terminal_header={"model_key": "ridge", "dataset": "toy", "setting": "clinical", "events_train": 3})

    def test_original_failed_outcome_reused_exactly(self):
        resolved = self.resolve()
        self.assertIs(resolved["cell"], self.value)
        self.assertFalse(resolved["derived_analysis_view"])
        self.assertEqual(source_evidence(self.value, self.original, self.evidence, ORIGINAL_MANIFEST, self.pins), ({}, {}))

    def test_source_changed_bytes_or_active_claim_refused(self):
        claim = self.original / "claims" / (self.value["cell_id"] + ".json")
        claim.write_bytes(b"fictional active owner")
        with self.assertRaisesRegex(VerificationFailure, "owner"):
            source_evidence(self.value, self.original, self.evidence, ORIGINAL_MANIFEST, self.pins)
        claim.unlink()
        self.path.write_bytes(self.path.read_bytes() + b" ")
        with self.assertRaisesRegex(VerificationFailure, "byte binding"):
            source_evidence(self.value, self.original, self.evidence, ORIGINAL_MANIFEST, self.pins)

    def test_reuse_cannot_be_called_new_fit_or_change_status(self):
        for field, value in (("scientific_status", "complete"), ("fit_dispatched", True), ("fit_seconds", 1.0)):
            original = self.record[field]
            self.record[field] = value
            with self.assertRaises(VerificationFailure):
                self.resolve()
            self.record[field] = original

    def test_terminal_pending_origin_view_has_no_scientific_fit_claim(self):
        self.decision.update(action="retain_input_failure", source_evidence=None,
                             generator_failures=[{"context": "outer", "status": "exhausted_rank_cap"}])
        self.record.update(operation="retain_corrected_input_failure", scientific_status="not_fit_input_failure",
                           source_evidence=None, original_reference=None, failure_contexts=self.decision["generator_failures"])
        result = self.resolve()
        self.assertTrue(result["derived_analysis_view"])
        self.assertEqual(result["cell"]["status"], "failed")
        self.assertEqual(result["cell"]["fit_attempts"], [])
        self.assertNotIn("metrics", result["cell"])
        self.assertNotIn("predictions", result["cell"])
        self.assertEqual(self.value["status"], "failed")

    def test_changed_fit_needs_actual_raw_record_byte_binding(self):
        self.decision["action"] = "fit_changed_inputs"
        self.record.update(operation="fit_corrected_inputs", scientific_status="complete", fit_dispatched=True,
                           newly_executed_fit=True, child_exit_code=0)
        new = cell()
        new["seconds"] = 2.0
        new["cell_content_sha256"] = canonical({k: v for k, v in new.items() if k != "cell_content_sha256"})
        relative = f"attempts/{new['cell_id']}/cells/{new['cell_id']}.json"
        path = self.corrected / relative
        path.parent.mkdir(parents=True)
        write_new(path, new)
        self.record.update(fit_seconds=2.0, corrected_cell={"logical_root": "corrected_fit_run", "path": relative,
            "sha256": sha(path), "cell_content_sha256": new["cell_content_sha256"]},
            artifacts={relative: {"sha256": sha(path), "bytes": path.stat().st_size}})
        self.assertEqual(self.resolve()["cell"]["status"], "complete")
        self.record["child_exit_code"] = 1
        with self.assertRaisesRegex(VerificationFailure, "successful child"):
            self.resolve()

    def test_metadata_and_definition_mismatch_refused(self):
        self.record["evidence_status"] = "primary"
        with self.assertRaisesRegex(VerificationFailure, "binding"):
            self.resolve()


class GateTests(unittest.TestCase):
    def fixture(self):
        definition = seal({"original_production_commit": ORIGINAL_COMMIT, "original_manifest_sha256": ORIGINAL_MANIFEST,
                           "attempt_cap": 256, "retry_seed_rule": "originalseed; deterministic_seed(originalseed,'rank_conditioned_retry',index1..255)",
                           "numerical_thread_policy": 1})
        freeze = {"status": "reviewed_corrected_fit_freeze", "original_production_commit": ORIGINAL_COMMIT,
                  "original_manifest_sha256": ORIGINAL_MANIFEST, "definition_content_sha256": definition["content_sha256"],
                  "input_inventory_sha256": "i" * 64,
                  "review_bindings": {name: {} for name in ("method", "arithmetic", "input_witness", "implementation", "freeze")},
                  "execution": {"fit_workers": 1, "numeric_threads": 1, "original_full_budget": True,
                     "pilot_rule": "each(model,setting,gene_budget):max(n_train*p),then_lexicographic_original_cell_id",
                     "pilot_eligibility": "changed_accepted_training_inputs_complete_role_and_arithmetic_accounting;original_owner_is_launch_barrier_only",
                     "original_resolution_policy": "fresh_reviewed_finished_source_snapshot"}}
        manifest = {"status": "corrected_fit_manifest_frozen", "freeze_sha256": "f" * 64,
                    "definition_content_sha256": definition["content_sha256"], "input_inventory_sha256": "i" * 64}
        inventory = {"status": "complete_input_witness_and_original_acquisition_inventory", "definition_content_sha256": definition["content_sha256"],
                     "scheduled_cells": 2, "entries": [{"original_cell_id": "a"}, {"original_cell_id": "b"}]}
        return freeze, definition, inventory, manifest

    def check(self, values):
        validate_documents(*values, "f" * 64, "i" * 64, expected_count=2)

    def test_complete_fixture_and_duplicate_partial_scope(self):
        values = self.fixture()
        self.check(values)
        values[2]["entries"] = [{"original_cell_id": "a"}] * 2
        with self.assertRaisesRegex(VerificationFailure, "whole"):
            self.check(values)
        values[2]["entries"].pop()
        with self.assertRaisesRegex(VerificationFailure, "whole"):
            self.check(values)

    def test_unreviewed_method_or_changed_cap_refused(self):
        values = self.fixture()
        values[0]["review_bindings"].pop("method")
        with self.assertRaisesRegex(VerificationFailure, "review"):
            self.check(values)
        values = self.fixture()
        values[1]["attempt_cap"] = 255
        with self.assertRaisesRegex(VerificationFailure, "cap"):
            self.check(values)

    def test_exact_scope_order_is_required(self):
        unique_ids([{"id": "a"}, {"id": "b"}], "id", ["a", "b"], "toy")
        with self.assertRaises(VerificationFailure):
            unique_ids([{"id": "b"}, {"id": "a"}], "id", ["a", "b"], "toy")


class TelemetryTests(unittest.TestCase):
    def fixture(self):
        value = {"cell_id": "toy", "model_key": "catalytic_wme", "status": "failed"}
        ledger = {"inner_fit": {f"{f}:{c}": 10 * f + c for f in range(1, 4) for c in range(3)},
                  "outer_fit_attempts": [100, 101, 102]}
        candidates = [{"tau_multiplier": v} for v in (0.25, 1.0, 4.0)]
        slots = [{"fold": f, "candidate_index_zero_based": c, "status": "not_executed_before_tuning_exit"}
                 for f in range(1, 4) for c in range(3)]
        telemetry = {"additional_optimizer_calls": 0, "proposal_selection_by_optimizer": False,
                     "original_predicates_and_selection_unchanged": True, "model_calls": [], "optimizer_calls": [],
                     "inner_tuning": {"reused": False, "invoked": True, "candidate_slots": slots, "rows": []}}
        observed = {"original_cell_id": "toy", "all_bound_generator_contexts": [], "generation_calls": [], "telemetry": telemetry}
        return observed, value, {"action": "retune_then_fit_changed_inputs"}, {}, ledger, candidates

    def test_nine_slots_retain_unvisited_vs_real_failed_candidate(self):
        args = self.fixture()
        report = verify_observations(*args)
        self.assertEqual(report["retained_wme_slots"], 9)
        args[0]["telemetry"]["inner_tuning"]["candidate_slots"].pop()
        with self.assertRaisesRegex(VerificationFailure, "nine-slot"):
            verify_observations(*args)

    def test_wrong_fit_seed_and_duplicate_generation_call_refused(self):
        args = self.fixture()
        args[0]["telemetry"]["model_calls"] = [{"index": 0, "model": "catalytic_wme", "scope": "inner",
            "fold": 1, "candidate_index_zero_based": 0, "parameters": {"tau_multiplier": 0.25}, "seed": 999}]
        with self.assertRaisesRegex(VerificationFailure, "seed"):
            verify_observations(*args)
        args = self.fixture()
        args[0]["generation_calls"] = [{"context": "outer"}] * 2
        with self.assertRaisesRegex(VerificationFailure, "duplicated"):
            verify_observations(*args)

    def test_original_nan_predicate_is_preserved_not_strengthened(self):
        args = self.fixture()
        args[0]["telemetry"]["model_calls"] = [{"index": 0, "model": "catalytic_wme", "scope": "inner",
            "fold": 1, "candidate_index_zero_based": 0, "parameters": {"tau_multiplier": 0.25}, "seed": 10}]
        args[0]["telemetry"]["optimizer_calls"] = [{"index": 0, "model_call_index": 0, "success": True, "x_finite": True,
            "post_optimum_predicate": {"kind": "wme", "max_absolute_score": {"nonfinite": "nan"},
                "value_finite": False, "tolerance": 1e-4, "original_reject_predicate": False}}]
        verify_observations(*args)
        args[0]["telemetry"]["optimizer_calls"][0]["post_optimum_predicate"]["original_reject_predicate"] = True
        with self.assertRaisesRegex(VerificationFailure, "predicate"):
            verify_observations(*args)
        with self.assertRaises(VerificationFailure):
            telemetry_number({"nonfinite": "invented"})

    def test_failed_cached_wme_tuning_never_reexecuted(self):
        args = self.fixture()
        args[1].update(selected_parameters=args[5][0], inner_tuning={"tuned": True})
        args[2].update(action="fit_changed_inputs_reuse_tuning", tuning_record_reused_sha256="t" * 64)
        args[0]["telemetry"]["inner_tuning"] = {"reused": True, "invoked": False, "candidate_slots": [],
            "source_record_sha256": "t" * 64, "selected_parameters": args[1]["selected_parameters"], "inner_tuning": args[1]["inner_tuning"]}
        verify_observations(*args)
        args[0]["telemetry"]["inner_tuning"]["invoked"] = True
        with self.assertRaisesRegex(VerificationFailure, "cached"):
            verify_observations(*args)


class AnalysisAdapterTests(unittest.TestCase):
    def test_fictional_reuse_terminal_grid_and_relocated_exact_replay(self):
        with tempfile.TemporaryDirectory(prefix="fictional_analysis_adapter_") as directory:
            root = Path(directory).resolve()
            original, corrected, output = root / "original", root / "corrected", root / "verified"
            for path in (original, corrected):
                (path / "cells").mkdir(parents=True)
                (path / "claims").mkdir()
            for name in ("cells", "lineage", "checks/original", "checks/corrected", "aggregates"):
                (output / name).mkdir(parents=True, exist_ok=True)
            for name in ("invocation.json", "environment.stdout.json", "environment.stderr.log", "environment_invocation.json"):
                write_new(output / name, seal({"synthetic_only": True}))
            values = [cell(), cell(model="lasso", status="failed")]
            entries, records, proofs = [], {}, {}
            for i, value in enumerate(values):
                identity = value["cell_id"]
                value.update(dataset="toy", setting="clinical", condition="full", seconds=1.0)
                value["cell_content_sha256"] = canonical({k: v for k, v in value.items() if k != "cell_content_sha256"})
                old_path = original / "cells" / (identity + ".json")
                write_new(old_path, value)
                old_evidence = evidence(value, old_path)
                terminal = i == 1
                decision = {"original_cell_id": identity, "action": "retain_input_failure" if terminal else "reuse_original_outcome",
                            "source_evidence": old_evidence, "generator_failures": ["terminal"] if terminal else [], "changed_roles": ["outer"] if terminal else []}
                record = {"original_cell_id": identity, "corrected_manifest_sha256": "m" * 64, "correction_freeze_sha256": "f" * 64,
                          "definition_content_sha256": "d" * 64, "input_witness_sha256": "i" * 64, "evidence_status": EVIDENCE,
                          "source_evidence": old_evidence, "decision": decision,
                          "operation": "retain_corrected_input_failure" if terminal else "reuse_original_outcome",
                          "scientific_status": "not_fit_input_failure" if terminal else value["status"],
                          "fit_dispatched": False, "newly_executed_fit": False, "fit_seconds": 0.0, "artifacts": {},
                          "original_reference": None if terminal else {"logical_root": "original_extension_run", "path": f"cells/{identity}.json",
                              "sha256": sha(old_path), "cell_content_sha256": value["cell_content_sha256"]}}
                if terminal:
                    record["failure_contexts"] = ["terminal"]
                write_new(corrected / "cells" / (identity + ".json"), seal(record))
                entries.append({"original_cell_id": identity, "input_witness_sha256": "i" * 64})
                records[identity] = record
                proofs[identity] = {"decision": decision, "original_source_evidence": old_evidence,
                    "terminal_header": {k: v for k, v in value.items() if k not in {"cell_content_sha256", "status"}},
                    "summary": {"synthetic_exact_roles": True}}
            science = Backend()
            science.jobs = [SimpleNamespace(cell_id=value["cell_id"]) for value in values]
            science.manifest = {"plan": [{"cell_id": value["cell_id"]} for value in values]}
            science.config = {"sampling": {"draws": 2000, "tune": 2000, "chains": 4, "target_accept": 0.999}}
            science.source_pins = {"files": {"analysis": {"scripts/render_extensions.py": "r" * 64}}}
            science.references = lambda *args: {"summary": {"primary_negative_finding_preserved": True}}
            science.aggregate = lambda *args: {name: {"fictional_reducer": name} for name in
                ("paired_families.json", "rq2_effects.json", "decision_curves.json")}
            science.verify_module_origins = lambda: None
            gate = SimpleNamespace(roots={"original_run": original, "corrected_run": corrected, "primary": root / "primary",
                "sampler": root / "sampler", "robustness": root / "robust"}, hashes={"freeze": "f" * 64, "manifest": "m" * 64},
                documents={"inventory": {"entries": entries}, "definition": {"content_sha256": "d" * 64}},
                summary=lambda: {"stable_logical_binding": "fixture"})
            input_backend = SimpleNamespace(verify=lambda job, entry, record: proofs[job.cell_id], validate_pilot_scope=lambda entries: None)
            completion = execute_verified(gate, science, input_backend, output, Pins(), {"toy": "v" * 64})
            self.assertEqual(completion["verified_logical_cells"], 2)
            self.assertFalse(completion["programme_complete"])
            self.assertEqual(completion["original_status_counts"], {"complete": 1, "failed": 1})
            self.assertEqual(science.scored, 1)
            import shutil
            relocated = root / "restored"
            shutil.copytree(root / "original", relocated / "original")
            shutil.copytree(root / "corrected", relocated / "corrected")
            shutil.copytree(output, relocated / "verified")
            gate.roots.update(original_run=relocated / "original", corrected_run=relocated / "corrected")
            replay = execute_verified(gate, science, input_backend, relocated / "verified", Pins(), {"toy": "v" * 64}, replay=True)
            self.assertEqual(replay, completion)
            self.assertEqual(sha(output / "completion.json"), sha(relocated / "verified/completion.json"))
            with self.assertRaisesRegex(VerificationFailure, "existing scientific"):
                document(relocated / "verified/comparison_accounting.json", {"wrong": True}, replay=True)


if __name__ == "__main__":
    unittest.main()
