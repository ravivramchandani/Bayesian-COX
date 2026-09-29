"""Fictional metadata/byte fixtures only; no scientific modules or real inputs."""

from __future__ import annotations

import copy
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1] / "scripts/catalytic_correction"
sys.path.insert(0, str(HERE))

import build_freeze as builder  # noqa: E402 - pure pinned helper

FIT = HERE
COMMON = builder.load_common(FIT)
CONTRACTS = COMMON.module_from_pin(HERE / "correction_fit_contracts.py",
                                  COMMON.CONTRACTS_SHA, "_freeze_builder_contracts_fixture")


def full_fixture() -> dict:
    """Invent exactly1625/1650 identities, with no arrays or cohort membership."""
    config = {"sampling": {"draws": 2000, "tune": 2000, "chains": 4, "target_accept": 0.999,
                          "maximum_refits": 2, "cores": 1, "refit_tune_multiplier": 2,
                          "final_noncentered_baseline": True}}
    models = (["catalytic_fixed"] * 275 + ["catalytic_adaptive"] * 275 + ["catalytic_wme"] * 275 + ["coxph"] * 800)
    entries = [{"original_cell_id": f"fictional_{i:04d}__{model}__full", "model": model} for i, model in enumerate(models)]
    original = {"input_sha256": {"conda-lock.yml": "a" * 64}, "matched_sha256": "b" * 64,
                "run_config": config, "plan": [{"cell_id": row["original_cell_id"]} for row in entries]}
    environment = {"status": "ok", "package_count": 259, "lock_sha256": "a" * 64, "scope": "fictional_fixture_only"}
    definition = {"original_production_commit": COMMON.ORIGINAL_COMMIT, "original_manifest_sha256": COMMON.ORIGINAL_MANIFEST_SHA,
        "original_input_sha256": original["input_sha256"], "matched_sha256": original["matched_sha256"],
        "original_configuration": config, "attempt_cap": 256,
        "retry_seed_rule": "originalseed; deterministic_seed(originalseed,'rank_conditioned_retry',index1..255)",
        "numerical_thread_policy": 1, "environment_verification": environment,
        "candidate_source_sha256": "c" * 64, "correction_config_sha256": "d" * 64, "correction_addendum_sha256": "e" * 64,
        "contracts_sha256": COMMON.CONTRACTS_SHA, "preflight_sources": {"preflight_core.py": COMMON.PREFLIGHT_CORE_SHA},
        "reuse_sources": {"reuse_core.py": COMMON.REUSE_CORE_SHA}, "content_sha256": "f" * 64}
    preflight_manifest = {**{key: definition[key] for key in ("original_manifest_sha256", "original_input_sha256", "matched_sha256",
        "candidate_source_sha256", "correction_config_sha256", "correction_addendum_sha256", "environment_verification")},
        "runner_source_sha256": definition["preflight_sources"], "content_sha256": "1" * 64}
    contexts = [{"context_id": key} for key in sorted(builder.expected_context_ids(entries))]
    completion = {"status": "all_scheduled_contexts_accounted", "scheduled_contexts": 1650, "accounted_contexts": 1650,
                  "outcomes": contexts, "run_binding_sha256": "1" * 64}
    replay = {"status": "all1650_independent_first_draw_contexts_accounted", "scheduled_contexts": 1650,
              "accounted_contexts": 1650, "outcomes": copy.deepcopy(contexts), "definition_content_sha256": "f" * 64}
    inventory = {"status": "complete_input_witness_and_original_acquisition_inventory", "scheduled_cells": 1625,
                 "entries": entries, "definition_content_sha256": "f" * 64,
                 "preflight_completion_sha256": "2" * 64, "replay_completion_sha256": "3" * 64,
                 "arithmetic_selector_sha256": "a" * 64,
                 "selection_scope": [{"original_cell_id": "fictional_pending_largest", "model": "catalytic_fixed",
                    "setting": "clinical", "gene_budget": 0, "n_train": 10, "p": 10},
                    {"original_cell_id": "fictional_ready_smaller", "model": "catalytic_fixed",
                    "setting": "clinical", "gene_budget": 0, "n_train": 9, "p": 10}]}
    binding = {"preflight_completion_sha256": "2" * 64, "replay_completion_sha256": "3" * 64,
               "preflight_manifest_sha256": "4" * 64, "input_inventory_sha256": "5" * 64,
               "paths": {role: "/fictional/" + role for role in builder.PATH_ROLES}, "fit_code": str(FIT),
               "arithmetic_accounting": {"path": "/fictional/arithmetic/accounting.json", "sha256": "6" * 64}}
    selector_entries = []
    for preflight_row, replay_row in zip(completion["outcomes"], replay["outcomes"], strict=True):
        identity, context = preflight_row["context_id"].split("::")
        relative = f"contexts/{identity}/{context}/receipt.json"
        preflight_row.update(receipt_path=relative, receipt_sha256="9" * 64)
        replay_row.update(receipt_path="replay/" + relative, receipt_sha256="9" * 64)
        selector_entries.append({"context_id": preflight_row["context_id"],
            "preflight_receipt_path": relative, "preflight_receipt_sha256": "9" * 64,
            "replay_receipt_path": "replay/" + relative, "replay_receipt_sha256": "9" * 64,
            "arithmetic_executed_or_certified_by_selector": False})
    selector = {"schema_version": 1, "status": "all1650_context_arithmetic_requirements_accounted",
        "definition_content_sha256": "f" * 64, "preflight_completion_sha256": "2" * 64,
        "replay_completion_sha256": "3" * 64, "scheduled_contexts": 1650, "entries": selector_entries,
        "arithmetic_validation_executed": False, "scientific_method_approved": False}
    arithmetic = {"input_inventory_sha256": "5" * 64, "definition_content_sha256": "f" * 64,
                  "selector_sha256": "a" * 64, "scheduled_contexts": 1650}
    return {"original": original, "definition": definition, "inventory": inventory,
            "preflight_manifest": preflight_manifest, "completion": completion, "replay": replay, "binding": binding,
            "selector": selector, "arithmetic": arithmetic}


class FreezeBuilderTests(unittest.TestCase):
    """Exercise authorization and immutable evidence boundaries, never science."""

    def setUp(self):
        self.scientific_modules_before = {
            name for name in sys.modules
            if name == "numpy" or name == "src" or name.startswith("src.")
        }
        self.temporary = tempfile.TemporaryDirectory(prefix="fictional-freeze-", dir=HERE)
        self.root = Path(self.temporary.name)
        self.fixture = full_fixture()

    def tearDown(self):
        try:
            scientific_modules_after = {
                name for name in sys.modules
                if name == "numpy" or name == "src" or name.startswith("src.")
            }
            self.assertEqual(scientific_modules_after, self.scientific_modules_before)
        finally:
            self.temporary.cleanup()

    def test_builder_imports_remain_science_free_in_a_fresh_process(self):
        script = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import build_freeze
build_freeze.load_common(Path(sys.argv[1]))
assert 'numpy' not in sys.modules
assert not any(name == 'src' or name.startswith('src.') for name in sys.modules)
"""
        result = subprocess.run(
            [sys.executable, "-I", "-B", "-c", script, str(HERE)],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def validate(self, value=None):
        value = self.fixture if value is None else value
        builder.validate_scope(COMMON, **{key: value[key] for key in ("original", "definition", "inventory",
                              "preflight_manifest", "completion", "replay", "binding")})

    def proposed(self):
        return builder.proposal(COMMON, self.fixture, "7" * 64)

    def arithmetic_links(self, value=None):
        value = self.fixture if value is None else value
        builder.validate_arithmetic_links(COMMON, **{key: value[key] for key in
            ("arithmetic", "selector", "inventory", "definition", "completion", "replay", "binding")})

    def reviews(self, proposed):
        bindings, values = {}, {}
        for role in builder.REVIEW_ROLES:
            path = self.root / f"fictional_{role}.json"
            value = COMMON.seal({"status": "reviewed_for_corrected_fit_execution", "role": role,
                "scope": "fictional_in_memory_test_not_a_root_review",
                "definition_content_sha256": proposed["freeze_template"]["definition_content_sha256"],
                "input_inventory_sha256": proposed["freeze_template"]["input_inventory_sha256"],
                "execution_definition_sha256": proposed["execution_definition_sha256"]})
            values[str(path)] = value
            bindings[role] = {"path": str(path), "sha256": COMMON.digest(value)}
        return {"status": "root_supplied_corrective_execution_review_bindings", "review_bindings": bindings}, values

    def test_exact_fixed_full_scope_accepts_fictional_metadata(self):
        self.validate()
        self.assertEqual(len(builder.expected_context_ids(self.fixture["inventory"]["entries"])), 1650)

    def test_partial_and_extra_grid_never_form_a_complete_proposal(self):
        for key in ("entries",):
            value = copy.deepcopy(self.fixture)
            value["inventory"][key].pop()
            with self.assertRaises(COMMON.InvalidBinding):
                self.validate(value)
        value = copy.deepcopy(self.fixture)
        value["completion"]["outcomes"].append({"context_id": "extra"})
        with self.assertRaises(COMMON.InvalidBinding):
            self.validate(value)

    def test_duplicate_and_foreign_contexts_refused(self):
        for replacement in (self.fixture["completion"]["outcomes"][1], {"context_id": "fictional_foreign::outer"}):
            value = copy.deepcopy(self.fixture)
            value["completion"]["outcomes"][0] = replacement
            with self.assertRaises(COMMON.InvalidBinding):
                self.validate(value)

    def test_independent_replay_order_and_completion_are_mandatory(self):
        for edit in ("order", "count", "status"):
            value = copy.deepcopy(self.fixture)
            if edit == "order":
                value["replay"]["outcomes"].reverse()
            elif edit == "count":
                value["replay"]["accounted_contexts"] = 1649
            else:
                value["replay"]["status"] = "partial"
            with self.assertRaises(COMMON.InvalidBinding):
                self.validate(value)

    def test_original_full_budget_and_policy_cannot_be_relaxed(self):
        value = copy.deepcopy(self.fixture)
        value["original"]["run_config"]["sampling"]["chains"] = 2
        with self.assertRaises(COMMON.InvalidBinding):
            self.validate(value)
        value = copy.deepcopy(self.fixture)
        value["definition"]["attempt_cap"] = 8
        with self.assertRaises(COMMON.InvalidBinding):
            self.validate(value)

    def test_model_and_dependency_labels_must_match_fixed_source(self):
        value = copy.deepcopy(self.fixture)
        value["inventory"]["entries"][0]["model"] = "coxph"
        with self.assertRaises(COMMON.InvalidBinding):
            self.validate(value)
        value = copy.deepcopy(self.fixture)
        value["definition"]["reuse_sources"]["reuse_core.py"] = "a" * 64
        with self.assertRaises(COMMON.InvalidBinding):
            self.validate(value)

    def test_unapproved_proposal_is_acyclic_and_preserves_pending_largest_pilot(self):
        value = self.proposed()
        self.assertEqual(value["status"], "unapproved_execution_definition_proposal")
        self.assertFalse(value["scientific_method_approved"])
        self.assertNotIn("review_bindings", value["freeze_template"])
        self.assertEqual(value["pilot_cells"], ["fictional_pending_largest"])
        self.assertEqual(value["execution_definition_sha256"], COMMON.execution_definition(value["freeze_template"]))

    def test_five_matching_supplied_reviews_produce_exact_freeze_schema_only(self):
        proposed = self.proposed()
        reviews, values = self.reviews(proposed)
        def read(path, expected):
            return values[str(path)]
        frozen = builder.approved_freeze(COMMON, proposed, reviews, read)
        self.assertEqual(frozen["status"], "reviewed_corrected_fit_freeze")
        self.assertEqual(COMMON.execution_definition(frozen), proposed["execution_definition_sha256"])
        self.assertEqual(set(frozen["review_bindings"]), builder.REVIEW_ROLES)
        self.assertEqual(set(frozen["implementation_source_sha256"]), set(builder.FIT_SOURCES))

    def test_missing_review_does_not_create_its_own_approval(self):
        proposed = self.proposed()
        reviews, values = self.reviews(proposed)
        reviews["review_bindings"].pop("method")
        with self.assertRaises(COMMON.InvalidBinding):
            builder.approved_freeze(COMMON, proposed, reviews, lambda path, expected: values[str(path)])

    def test_stale_review_input_hash_and_unapproved_status_refused(self):
        for field, wrong in (("input_inventory_sha256", "0" * 64), ("execution_definition_sha256", "0" * 64),
                             ("status", "not_reviewed"), ("role", "invented")):
            proposed = self.proposed()
            reviews, values = self.reviews(proposed)
            values[reviews["review_bindings"]["method"]["path"]][field] = wrong
            with self.assertRaises(COMMON.InvalidBinding):
                builder.approved_freeze(COMMON, proposed, reviews, lambda path, expected, values=values: values[str(path)])

    def test_actual_byte_binding_and_race_are_refused(self):
        path = self.root / "fictional.json"
        COMMON.write_new(path, COMMON.seal({"scope": "fictional"}))
        ledger = builder.Evidence(COMMON)
        ledger.read(path, COMMON.sha(path))
        with self.assertRaises(COMMON.InvalidBinding):
            ledger.bind(path, "0" * 64)
        path.write_text('changed fictional bytes')
        with self.assertRaises(COMMON.InvalidBinding):
            ledger.recheck()

    def test_exclusive_output_collision_and_protected_overlap(self):
        inputs = {"binding": {"fit_code": str(self.root / "fit"), "paths": {"witness_root": str(self.root / "witness")},
                              "arithmetic_accounting": {"path": str(self.root / "arithmetic/accounting.json")}}}
        output = self.root / "new-output"
        builder.prepare_destination(COMMON, output, inputs, self.root / "builder")
        output.mkdir()
        with self.assertRaises(COMMON.InvalidBinding):
            builder.prepare_destination(COMMON, output, inputs, self.root / "builder")
        with self.assertRaises(COMMON.InvalidBinding):
            builder.prepare_destination(COMMON, self.root / "fit/new-output", inputs, self.root / "builder")

    def test_unsafe_artifact_and_symlink_cannot_bind(self):
        ledger = builder.Evidence(COMMON)
        path = self.root / "fictional.bin"
        path.write_bytes(b'fictional bytes only')
        linked = self.root / "linked"
        linked.symlink_to(path)
        with self.assertRaises(COMMON.InvalidBinding):
            ledger.bind(linked, COMMON.sha(path))
        with self.assertRaises(COMMON.InvalidBinding):
            ledger.artifacts(self.root, {"../outside": {"sha256": "a" * 64, "bytes": 1}})

    def test_wrong_helper_bytes_and_import_namespace_collision_refused(self):
        with self.assertRaises(ValueError):
            builder.load_common(FIT)
        (self.root / "fit_common.py").write_text('raise AssertionError("must not import")\n')
        with self.assertRaises(ValueError):
            builder.load_common(self.root)

    def test_current_account_inventory_byte_hash_required(self):
        self.arithmetic_links()
        for wrong in (None, "0" * 64):
            value = copy.deepcopy(self.fixture)
            if wrong is None:
                value["arithmetic"].pop("input_inventory_sha256")
            else:
                value["arithmetic"]["input_inventory_sha256"] = wrong
            with self.assertRaises((COMMON.InvalidBinding, KeyError)):
                self.arithmetic_links(value)

    def test_current_account_definition_content_hash_required(self):
        value = copy.deepcopy(self.fixture)
        value["arithmetic"]["definition_content_sha256"] = "0" * 64
        with self.assertRaises(COMMON.InvalidBinding):
            self.arithmetic_links(value)

    def test_current_account_selector_byte_hash_required(self):
        for role in ("arithmetic", "inventory"):
            value = copy.deepcopy(self.fixture)
            field = "selector_sha256" if role == "arithmetic" else "arithmetic_selector_sha256"
            value[role][field] = "0" * 64
            with self.assertRaises(COMMON.InvalidBinding):
                self.arithmetic_links(value)

    def test_account_and_selector_require_exact1650_ordered_coverage(self):
        for edit in ("account_count", "selector_count", "missing", "extra", "reverse"):
            value = copy.deepcopy(self.fixture)
            if edit == "account_count":
                value["arithmetic"]["scheduled_contexts"] = 1649
            elif edit == "selector_count":
                value["selector"]["scheduled_contexts"] = 1649
            elif edit == "missing":
                value["selector"]["entries"].pop()
            elif edit == "extra":
                value["selector"]["entries"].append(value["selector"]["entries"][0])
            else:
                value["selector"]["entries"].reverse()
            with self.assertRaises(COMMON.InvalidBinding):
                self.arithmetic_links(value)

    def test_selector_existing_definition_preflight_replay_and_scope_links(self):
        for field, wrong in (("definition_content_sha256", "0" * 64),
                             ("preflight_completion_sha256", "0" * 64),
                             ("replay_completion_sha256", "0" * 64),
                             ("status", "partial"), ("arithmetic_validation_executed", True),
                             ("scientific_method_approved", True)):
            value = copy.deepcopy(self.fixture)
            value["selector"][field] = wrong
            with self.assertRaises(COMMON.InvalidBinding):
                self.arithmetic_links(value)

    def test_selector_context_paths_and_receipt_hashes_must_match(self):
        for field in ("preflight_receipt_path", "preflight_receipt_sha256", "replay_receipt_path", "replay_receipt_sha256"):
            value = copy.deepcopy(self.fixture)
            value["selector"]["entries"][0][field] = "foreign"
            with self.assertRaises(COMMON.InvalidBinding):
                self.arithmetic_links(value)

    def test_selector_provenance_uses_actual_file_bytes_and_rechecks_races(self):
        path = self.root / "arithmetic_selector.json"
        COMMON.write_new(path, COMMON.seal(self.fixture["selector"]))
        expected = COMMON.sha(path)
        ledger = builder.Evidence(COMMON)
        selector = ledger.read(path, expected)
        self.fixture["inventory"]["arithmetic_selector_sha256"] = expected
        self.fixture["arithmetic"]["selector_sha256"] = expected
        self.fixture["selector"] = selector
        self.arithmetic_links()
        with self.assertRaises(COMMON.InvalidBinding):
            builder.Evidence(COMMON).read(path, "0" * 64)
        path.write_text('stale actual selector bytes')
        with self.assertRaises(COMMON.InvalidBinding):
            ledger.recheck()

    def injected_full_read(self, *, formula_mismatch=False):
        """Inject metadata reads/proof IO; keep real pure contracts/arithmetic guards."""
        fixture = copy.deepcopy(self.fixture)
        binding = fixture["binding"]
        binding.update(schema_version=1, status="prospective_corrective_freeze_input_bindings", definition_sha256="8" * 64)
        binding["paths"].update(reuse_core=str(FIT / "reuse_core.py"))
        fixture["inventory"]["selection_scope"] = []
        documents = {str(self.root / "fictional_bindings.json"): binding,
                     "/fictional/witness_root/definition.json": fixture["definition"],
                     "/fictional/inventory": fixture["inventory"],
                     "/fictional/preflight/manifest.json": fixture["preflight_manifest"],
                     "/fictional/preflight/completion.json": fixture["completion"],
                     "/fictional/witness_root/replay/completion.json": fixture["replay"],
                     "/fictional/witness_root/arithmetic_selector.json": fixture["selector"]}
        fixture["replay"]["artifacts"] = {}
        evidence_sha = "9" * 64
        arithmetic_rows = []
        for preflight, replay in zip(fixture["completion"]["outcomes"], fixture["replay"]["outcomes"], strict=True):
            identity, context = preflight["context_id"].split("::")
            relative = f"contexts/{identity}/{context}/receipt.json"
            preflight.update(receipt_path=relative, receipt_sha256=evidence_sha, receipt_content_sha256="1" * 64,
                             status="accepted_original_first_draw")
            documents["/fictional/preflight/" + relative] = {"content_sha256": "1" * 64, "status": "accepted_original_first_draw",
                "request": {"context_id": preflight["context_id"], "run_binding_sha256": "1" * 64}, "artifacts": {}}
            replay.update(receipt_path="replay/" + relative, receipt_sha256=evidence_sha, receipt_content_sha256="1" * 64)
            documents["/fictional/witness_root/replay/" + relative] = {"content_sha256": "1" * 64,
                "status": "independent_original_first_draw_verified", "context_id": preflight["context_id"],
                "request": {"definition_content_sha256": "f" * 64}, "artifacts": {}}
            arithmetic_rows.append({"context_id": preflight["context_id"], "preflight_status": preflight["status"],
                "preflight_receipt_sha256": evidence_sha, "status": "unchanged_inputs_independently_witnessed",
                "formula_checks": "not_required", "kappa_required": False, "original_kappa_status": "not_required",
                "evidence_sha256": [evidence_sha], "independent_replay_receipt_sha256": evidence_sha})
        arithmetic = {**fixture["arithmetic"], "status": "all_scheduled_arithmetic_outcomes_accounted", "preflight_completion_sha256": "2" * 64,
            "context_outcomes": arithmetic_rows, "artifacts": {"fictional_evidence.json": {"sha256": evidence_sha, "bytes": 1}},
            "proposals_selected_by_optimizer": False, "extra_proposals_generated": False}
        if formula_mismatch:
            arithmetic["context_outcomes"][0]["formula_checks"] = "mismatch"
        documents["/fictional/arithmetic/accounting.json"] = arithmetic
        for row in fixture["inventory"]["entries"]:
            identity, model = row["original_cell_id"], row["model"]
            names = [key.rsplit("::", 1)[1] for key in builder.expected_context_ids([row])]
            generator_contexts = {name: ("accepted", evidence_sha) for name in names}
            roles = {name: CONTRACTS.Comparison(evidence_sha, evidence_sha, evidence_sha, "exact_reconstruction")
                     for name in CONTRACTS.required_roles(model)}
            fit = CONTRACTS.FitWitness(identity, model, "f" * 64, CONTRACTS.seed_ledger(identity), CONTRACTS.seed_ledger(identity),
                                       roles, generator_contexts, None)
            metadata = {"original_cell_id": identity, "model": model, "setting": "clinical", "gene_budget": 0, "n_train": 10, "p": 5}
            row.update(input_witness_path=f"cells/{identity}/input_witness.json", input_witness_sha256=evidence_sha,
                       snapshot_path=f"cells/{identity}/snapshots/pending.json", snapshot_sha256=evidence_sha, selection_scope=metadata)
            documents["/fictional/witness_root/" + row["input_witness_path"]] = {"definition_content_sha256": "f" * 64,
                "fit_witness": asdict(fit), "selection_scope": metadata, "proof_artifacts": {}}
            documents["/fictional/witness_root/" + row["snapshot_path"]] = {"original_cell_id": identity,
                "input_witness_sha256": evidence_sha, "definition_content_sha256": "f" * 64, "artifacts": {}}

        class FictionalEvidence:
            def __init__(self, common):
                self.observed = {}

            def read(self, path, expected):
                self.bind(path, expected)
                return documents[str(path)]

            def bind(self, path, expected):
                self.observed[path] = expected

            def artifacts(self, root, artifacts):
                pass

            def recheck(self):
                pass

        with (patch.object(builder, "Evidence", FictionalEvidence),
              patch.object(COMMON, "read_original_manifest", return_value=fixture["original"]),
              patch.object(COMMON, "module_from_pin", return_value=CONTRACTS),
              patch.object(COMMON, "verify_witness_proofs") as proofs):
            result = builder.read_inputs(self.root / "fictional_bindings.json", "0" * 64, FIT, COMMON)
            self.assertEqual(proofs.call_count, 1625)
            self.assertEqual(result["evidence"].observed[Path("/fictional/witness_root/arithmetic_selector.json")],
                             fixture["inventory"]["arithmetic_selector_sha256"])
            return result

    def test_injected_full_read_keeps_pending_owners_and_complete_arithmetic(self):
        result = self.injected_full_read()
        self.assertEqual(result["inventory"]["selection_scope"], [])
        self.assertEqual(len(result["completion"]["outcomes"]), 1650)

    def test_injected_full_read_formula_mismatch_blocks_before_proposal(self):
        with self.assertRaises(COMMON.InvalidBinding):
            self.injected_full_read(formula_mismatch=True)


if __name__ == "__main__":
    unittest.main()
