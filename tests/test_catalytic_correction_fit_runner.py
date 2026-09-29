"""Invented/injected boundary tests; never import src or run scientific work."""

from __future__ import annotations

import copy
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parents[1] / "scripts/catalytic_correction"
sys.path.insert(0, str(HERE))

import fit_common as common  # noqa: E402 - byte-identical CLI support
import fit_controller as controller  # noqa: E402
from fit_child import (  # noqa: E402
    AliasScope,
    GenerationSupply,
    InputBoundaryAbort,
    Observations,
    delegate_cell,
)

CONTRACT_PATH = HERE / "correction_fit_contracts.py"
CORE_PATH = HERE / "preflight_core.py"
CONTRACTS = common.module_from_pin(CONTRACT_PATH, common.CONTRACTS_SHA, "_synthetic_fit_contracts")
CORE = common.module_from_pin(CORE_PATH, common.PREFLIGHT_CORE_SHA, "_synthetic_preflight_core")


class FixtureProcessor:
    """Minimal synthetic transformation; no real preprocessing or decomposition."""

    feature_names = ["x"]
    clinical = SimpleNamespace(required_source_columns=["x"])
    genes: list[str] = []

    def metadata(self) -> dict:
        return {"synthetic_fixture": True, "columns": ["x"]}

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        return frame[["x"]]


def fixture_context(seed: int = 17) -> tuple[pd.DataFrame, FixtureProcessor, dict]:
    """Invent exact tiny array witnesses without calling any original generator."""
    frame = pd.DataFrame({"subject_id": ["fixture1", "fixture2"], "x": [1.0, 2.0]})
    processor = FixtureProcessor()
    real = {"real_design": np.array([[1.0], [2.0]]), "real_time": np.array([1.0, 2.0]),
            "real_event": np.array([1, 0])}
    witness = {"ordered_training_subject_ids": frame.subject_id.tolist(), "original_generation_seed": seed,
               "processor_metadata": processor.metadata(), "processor_metadata_sha256": common.digest(processor.metadata()),
               "feature_names": processor.feature_names, "source_values": CORE.source_frame_witness(frame, ["x"]),
               "real_design": CORE.array_witness(real["real_design"]), "training_time": CORE.array_witness(real["real_time"]),
               "training_event": CORE.array_witness(real["real_event"])}
    row = {"input_witness": witness, "real_arrays": real,
           "proposal_arrays": {"synthetic_design": np.array([[0.5], [2.5]]), "synthetic_time": np.array([0.1, 0.2]),
                               "hazard": np.asarray(2.0), "time_scale": np.asarray(1.0)},
           "legacy_metadata": {"seed": seed, "synthetic_fixture": True}, "accepted_seed": seed,
           "accepted_attempt_index": 0, "receipt_sha256": common.digest({"fixture": "receipt"})}
    return frame, processor, row


def fixture_modules(*, failing_models: bool = False, generation_failure: bool = False) -> tuple:
    """Inject all optimizers, generation, fits and candidate values as fixtures."""
    result = SimpleNamespace(success=True, x=np.array([0.0]), jac=np.array([0.0]), fun=0.0, nit=2,
                             message="synthetic optimizer fixture", status=0)
    counters = {"minimize": 0, "fit": 0, "generation": 0}

    def minimize(*_args, **_kwargs):
        counters["minimize"] += 1
        return result

    catalytic = SimpleNamespace(minimize=minimize, catalytic_kernel=lambda *_args: (0.0, np.array([0.0])),
                                weighted_breslow_objective=lambda *_args: (0.0, np.array([0.0])))
    fitting = SimpleNamespace()

    class FixtureModel:
        def fit(self, *_args, **_kwargs):
            counters["fit"] += 1
            if failing_models:
                raise RuntimeError("synthetic fitting failure")
            return self

    def make_model(*_args, **_kwargs):
        return FixtureModel()

    def generate(*_args, **_kwargs):
        counters["generation"] += 1
        if generation_failure and counters["generation"] == 2:
            raise ValueError("synthetic nonrank inner generation failure")
        return None, {"synthetic_fixture": True}

    def select(key, raw, times, events, specification, budget, *, primary, config, seed):
        if key != "catalytic_wme":
            return {}, {"tuned": False, "candidates": []}
        candidates = [{"tau_multiplier": value} for value in (0.25, 1.0, 4.0)]
        rows = [{"parameters": candidate, "scores": [], "failures": []} for candidate in candidates]
        for fold in [SimpleNamespace(fold=index) for index in range(1, 4)]:
            fitting.generate_catalytic_data(None, None, None, None, seed + fold.fold)
            for ci, row in enumerate(rows):
                try:
                    model = fitting.make_model(key, row["parameters"], None, None, None,
                                               primary=primary, config=config, seed=seed + fold.fold * 3 + ci)
                    model.fit(None, None, None)
                    # These are invented constants, not survival metrics.
                    row["scores"].append(float(ci + fold.fold))
                except Exception as error:
                    row["failures"].append({"fold": fold.fold, "type": type(error).__name__, "message": str(error)})
        if any(len(row["scores"]) != 3 for row in rows):
            raise RuntimeError("no synthetic candidate passed all inner folds")
        return candidates[0], {"tuned": True, "candidates": rows}

    fitting.make_model, fitting.select_parameters, fitting.generate_catalytic_data = make_model, select, generate
    runner = SimpleNamespace(generate_catalytic_data=generate, select_parameters=select)
    return runner, fitting, catalytic, counters, result


class FitRunnerTests(unittest.TestCase):
    """Actual test evidence covers guards and mocks, not scientific integration."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="synthetic-fit-", dir=HERE)
        self.root = Path(self.temporary.name)
        self.svd_guard = patch("numpy.linalg.svd", side_effect=AssertionError("SVD forbidden in fixture tests"))
        self.rank_guard = patch("numpy.linalg.matrix_rank", side_effect=AssertionError("rank decomposition forbidden in fixture tests"))
        self.svd_guard.start()
        self.rank_guard.start()

    def tearDown(self):
        self.rank_guard.stop()
        self.svd_guard.stop()
        self.temporary.cleanup()

    def test_exact_bytes_copy_and_exclusive_collision(self):
        source, target = self.root / "source.json", self.root / "copy.json"
        source.write_bytes(b'{"synthetic":true}\n\n')
        common.copy_new(source, target, common.sha(source))
        self.assertEqual(source.read_bytes(), target.read_bytes())
        with self.assertRaises(common.InvalidBinding):
            common.copy_new(source, target, common.sha(source))

    def test_content_hash_and_nonfinite_refusal(self):
        path = self.root / "receipt.json"
        common.write_new(path, common.seal({"synthetic_fixture": True}))
        self.assertTrue(common.read_json(path)["synthetic_fixture"])
        path.write_text('{"content_sha256":"fake","x":NaN}')
        with self.assertRaises(common.InvalidBinding):
            common.read_json(path)

    def test_symlink_and_parent_traversal_refusal(self):
        source, link = self.root / "file", self.root / "link"
        source.write_bytes(b"fixture")
        link.symlink_to(source)
        with self.assertRaises(common.InvalidBinding):
            common.sha(link)
        with self.assertRaises(common.InvalidBinding):
            common.below(self.root, "../escape")

    def test_claim_collision_and_finally_release(self):
        path = self.root / "claim.json"
        with self.assertRaisesRegex(RuntimeError, "synthetic failure"):
            with common.Claim(path, "fixture"):
                with self.assertRaises(common.InvalidBinding):
                    with common.Claim(path, "fixture"):
                        self.fail("exclusive claim failed")
                raise RuntimeError("synthetic failure")
        self.assertFalse(path.exists())

    def test_source_origin_checks_no_foreign_namespace(self):
        source = self.root / "original"
        (source / "src").mkdir(parents=True)
        path = source / "src/__init__.py"
        path.write_text("# invented fixture\n")
        manifest = {"input_sha256": {"src/__init__.py": common.sha(path)}}
        self.assertEqual(common.verify_src_modules(source, manifest, {"src": SimpleNamespace(__file__=str(path))}),
                         {"src": "src/__init__.py"})
        foreign = self.root / "foreign.py"
        foreign.write_text("# foreign fixture\n")
        with self.assertRaises(common.InvalidBinding):
            common.verify_src_modules(source, manifest, {"src": SimpleNamespace(__file__=str(foreign))})

    def test_generation_exact_first_data_and_legacy(self):
        frame, processor, row = fixture_context()
        calls = []

        def constructor(x, t, hazard):
            calls.append((x, t, hazard))
            return SimpleNamespace(design=x, time=t, hazard=hazard)

        supply = GenerationSupply({"outer": row}, constructor, CORE)
        synthetic, legacy = supply(frame, processor, row["real_arrays"]["real_time"], row["real_arrays"]["real_event"], 17)
        np.testing.assert_array_equal(synthetic.design, row["proposal_arrays"]["synthetic_design"])
        self.assertEqual(legacy, row["legacy_metadata"])
        self.assertEqual(len(calls), 1)
        legacy["seed"] = -1
        self.assertEqual(row["legacy_metadata"]["seed"], 17)
        with self.assertRaises(InputBoundaryAbort):
            supply(frame, processor, row["real_arrays"]["real_time"], row["real_arrays"]["real_event"], 17)

    def test_generation_retries_never_follow_constructor_failure(self):
        frame, processor, row = fixture_context()
        calls = []

        def constructor(*args):
            calls.append(args)
            raise ValueError("synthetic constructor finite guard")

        supply = GenerationSupply({"outer": row}, constructor, CORE)
        with self.assertRaises(InputBoundaryAbort):
            supply(frame, processor, row["real_arrays"]["real_time"], row["real_arrays"]["real_event"], 17)
        self.assertEqual(len(calls), 1)
        self.assertEqual(supply.calls, [])

    def test_generation_exact_training_state_source_ids_and_times(self):
        frame, processor, row = fixture_context()
        supply = GenerationSupply({"outer": row}, lambda *_args: self.fail("invalid input reached constructor"), CORE)
        wrong = frame.copy()
        wrong.loc[0, "subject_id"] = "heldout_fixture"
        with self.assertRaises(InputBoundaryAbort):
            supply.verify_training("outer", wrong, processor, row["real_arrays"]["real_time"], row["real_arrays"]["real_event"])
        wrong = frame.copy()
        wrong.loc[0, "x"] = 0.0
        with self.assertRaises(InputBoundaryAbort):
            supply.verify_training("outer", wrong, processor, row["real_arrays"]["real_time"], row["real_arrays"]["real_event"])
        with self.assertRaises(InputBoundaryAbort):
            supply.verify_training("outer", frame, processor, np.array([1.0, 3.0]), row["real_arrays"]["real_event"])

    def test_generation_seed_collisions_refused(self):
        _, _, row = fixture_context()
        with self.assertRaises(InputBoundaryAbort):
            GenerationSupply({"outer": row, "inner_01": copy.deepcopy(row)}, lambda *_args: None, CORE)

    def test_alias_restoration_on_baseexception(self):
        owner = SimpleNamespace(alias="original")
        with self.assertRaises(SystemExit):
            with AliasScope() as scope:
                scope.set(owner, "alias", "changed")
                with self.assertRaises(InputBoundaryAbort):
                    scope.set(owner, "alias", "again")
                raise SystemExit(4)
        self.assertEqual(owner.alias, "original")

    def test_delegate_restores_every_alias_after_boundary_abort(self):
        runner, fitting, catalytic, _, _ = fixture_modules()
        saved = (runner.generate_catalytic_data, runner.select_parameters, fitting.generate_catalytic_data,
                 fitting.make_model, catalytic.minimize, catalytic.catalytic_kernel, catalytic.weighted_breslow_objective)

        def run(*_args):
            raise InputBoundaryAbort("synthetic unsafe input")

        runner.run_extension_cell = run
        observation = Observations(fitting, catalytic, np)
        with self.assertRaises(InputBoundaryAbort):
            delegate_cell(runner, fitting, catalytic, None, None, {}, {}, {}, self.root,
                          GenerationSupply({}, lambda *_args: None, CORE), observation)
        self.assertEqual(saved, (runner.generate_catalytic_data, runner.select_parameters, fitting.generate_catalytic_data,
                                fitting.make_model, catalytic.minimize, catalytic.catalytic_kernel, catalytic.weighted_breslow_objective))

    def test_delegate_restores_constructed_model_when_fit_is_unreached(self):
        runner, fitting, catalytic, _, _ = fixture_modules()
        observation, created = Observations(fitting, catalytic, np), []

        def run(*_args):
            created.append(fitting.make_model("catalytic_wme", {}, seed=17))
            raise SystemExit("invented interruption before fit")

        runner.run_extension_cell = run
        with self.assertRaises(SystemExit):
            delegate_cell(runner, fitting, catalytic, None, None, {}, {}, {}, self.root,
                          GenerationSupply({}, lambda *_args: None, CORE), observation)
        self.assertNotIn("fit", created[0].__dict__)
        self.assertEqual(observation.model_calls[0]["fit"], "not_invoked")

    def test_interface_contract_constant_surface_matches_prepared_code(self):
        import json
        document = json.loads((HERE / "fit_interface_contract.json").read_text())
        self.assertEqual(document["original_manifest_sha256"], common.ORIGINAL_MANIFEST_SHA)
        self.assertEqual(document["original_manifest_content_sha256"], common.ORIGINAL_CONTENT_SHA)
        self.assertEqual(document["freeze"]["execution"]["pilot_rule"], common.PILOT_RULE)
        self.assertEqual(document["freeze"]["execution"]["pilot_eligibility"], common.PILOT_ELIGIBILITY)
        self.assertEqual(document["inventory"]["required_role_counts"], {"common": len(CONTRACTS.required_roles("coxph")),
                         "fixed_or_adaptive": len(CONTRACTS.required_roles("catalytic_fixed")), "wme": len(CONTRACTS.required_roles("catalytic_wme"))})

    def test_optimizer_observer_preserves_result_and_checked_predicate(self):
        _, fitting, catalytic, counters, result = fixture_modules()
        observation = Observations(fitting, catalytic, np)
        self.assertIs(observation.minimize(None, None, jac=True, method="L-BFGS-B", options={"maxiter": 5000}), result)
        catalytic.catalytic_kernel = lambda *_args: (1.0, np.array([2e-6]))
        observation.kernel_original = catalytic.catalytic_kernel
        observation.kernel(result.x, None)
        self.assertEqual(counters["minimize"], 1)
        self.assertTrue(observation.optimizers[0]["post_optimum_predicate"]["original_reject_predicate"])
        self.assertEqual(observation.optimizers[0]["jac_argument"], True)

    def test_optimizer_preserves_original_nonfinite_score_boundary(self):
        _, fitting, catalytic, _, result = fixture_modules()
        observation = Observations(fitting, catalytic, np)
        observation.minimize(None, None)
        observation.weighted_original = lambda *_args: (0.0, np.array([np.nan]))
        observation.weighted(result.x, None, None, None, None)
        post = observation.optimizers[0]["post_optimum_predicate"]
        self.assertFalse(post["original_reject_predicate"])
        self.assertFalse(post["score_all_finite"])
        self.assertEqual(post["max_absolute_score"], {"nonfinite": "nan"})

    def test_model_fit_failure_and_instance_restoration(self):
        _, fitting, catalytic, counters, _ = fixture_modules(failing_models=True)
        observation = Observations(fitting, catalytic, np)
        model = observation.make_model("catalytic_wme", {"tau_multiplier": 1.0}, seed=123)
        with self.assertRaisesRegex(RuntimeError, "synthetic fitting failure"):
            model.fit(None, None, None)
        self.assertNotIn("fit", model.__dict__)
        self.assertEqual(counters["fit"], 1)
        self.assertEqual(observation.model_calls[0]["fit"], "raised")

    def test_fixed_and_adaptive_kappa_calls_observed_without_additions(self):
        _, fitting, catalytic, counters, _ = fixture_modules()
        observation = Observations(fitting, catalytic, np)
        for key in ("catalytic_fixed", "catalytic_adaptive"):
            model = observation.make_model(key, {}, seed=17)
            original = model.fit

            def fixture_fit(*args, original=original):
                result = observation.minimize(None, None, method="L-BFGS-B", options={"gtol": 1e-8})
                observation.kernel(result.x, None)
                return original(*args)

            fixture_fit(None, None, None)
        self.assertEqual(counters["minimize"], 2)
        self.assertEqual(counters["fit"], 2)
        self.assertEqual(len(observation.optimizers), 2)
        self.assertEqual(observation.data()["additional_optimizer_calls"], 0)

    def test_wme_all_nine_failure_slots_retained_after_original_raise(self):
        _, fitting, catalytic, counters, _ = fixture_modules(failing_models=True)
        observation = Observations(fitting, catalytic, np)
        with AliasScope() as scope:
            scope.set(fitting, "make_model", observation.make_model)
            with self.assertRaisesRegex(RuntimeError, "no synthetic candidate"):
                observation.select("catalytic_wme", None, None, None, {}, 0, primary={}, config={}, seed=17)
        self.assertEqual(counters["fit"], 9)
        self.assertEqual(counters["generation"], 3)
        self.assertEqual(len(observation.model_calls), 9)
        self.assertEqual(len(observation.tuning["candidate_slots"]), 9)
        self.assertTrue(all(row["status"] == "original_candidate_failure" for row in observation.tuning["candidate_slots"]))
        self.assertIsNone(sys.gettrace())

    def test_wme_partial_tuning_exit_records_unvisited_slots(self):
        _, fitting, catalytic, counters, _ = fixture_modules(generation_failure=True)
        observation = Observations(fitting, catalytic, np)
        with AliasScope() as scope:
            scope.set(fitting, "make_model", observation.make_model)
            with self.assertRaisesRegex(ValueError, "nonrank inner generation"):
                observation.select("catalytic_wme", None, None, None, {}, 0, primary={}, config={}, seed=17)
        self.assertEqual(counters["fit"], 3)
        self.assertEqual(counters["generation"], 2)
        self.assertEqual(sum(row["status"] == "score_recorded" for row in observation.tuning["candidate_slots"]), 3)
        self.assertEqual(sum(row["status"] == "not_executed_before_tuning_exit" for row in observation.tuning["candidate_slots"]), 6)
        self.assertIsNone(sys.gettrace())

    def test_cached_wme_selection_is_exact_and_never_retuned(self):
        runner, fitting, catalytic, counters, _ = fixture_modules()
        observation = Observations(fitting, catalytic, np)
        recorded = {"selected_parameters": {"tau_multiplier": 4.0}, "inner_tuning": {"synthetic_fixture": "original_record"},
                    "source_record_sha256": "fixture", "inner_cv_seed": 17}

        def run(*_args):
            return runner.select_parameters("catalytic_wme", None, None, None, {}, 0, primary={}, config={}, seed=17)

        runner.run_extension_cell = run
        selected, tuning = delegate_cell(runner, fitting, catalytic, None, None, {}, {}, {}, self.root,
                                        GenerationSupply({}, lambda *_args: None, CORE), observation, recorded)
        self.assertEqual(selected, recorded["selected_parameters"])
        self.assertEqual(tuning, recorded["inner_tuning"])
        self.assertEqual(counters, {"minimize": 0, "fit": 0, "generation": 0})
        self.assertTrue(observation.tuning["reused"])

    def test_pilot_uses_frozen_dimensions_not_status_or_availability(self):
        scope = [{"original_cell_id": name, "model": "catalytic_fixed", "setting": "clinical", "gene_budget": 0,
                  "n_train": n, "p": p, "status": status} for name, n, p, status in (
                      ("a", 10, 3, "active_original_owner"), ("b", 5, 6, "complete"), ("c", 4, 6, "failed"))]
        self.assertEqual(common.select_pilots(scope), ["a"])
        scope[0]["n_train"] = 0
        with self.assertRaises(common.InvalidBinding):
            common.select_pilots(scope)

    def test_full_budget_guard_retains_four_sequential_chains(self):
        config = {"sampling": {"draws": 2000, "tune": 2000, "chains": 4, "cores": 1, "target_accept": 0.999,
                               "maximum_refits": 2, "refit_tune_multiplier": 2, "final_noncentered_baseline": True}}
        common.validate_budget(config)
        config["sampling"]["chains"] = 2
        with self.assertRaises(common.InvalidBinding):
            common.validate_budget(config)

    def test_child_nonzero_logs_retained_without_success_output(self):
        environment = {key: "1" for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")}

        def failed(_argv, *, stdout, stderr, **_kwargs):
            stdout.write(b"synthetic child stdout\n")
            stderr.write(b"synthetic child error\n")
            return SimpleNamespace(returncode=7)

        with self.assertRaises(common.InvalidBinding):
            controller.capture_child(["invented-child"], self.root, environment, failed)
        invocation = common.read_json(self.root / "invocation.json")
        self.assertEqual(invocation["exit_code"], 7)
        self.assertEqual((self.root / "stderr.log").read_bytes(), b"synthetic child error\n")
        self.assertFalse((self.root / "child_receipt.json").exists())
        with self.assertRaises(FileExistsError):
            controller.capture_child(["invented-child"], self.root, environment, failed)

    def test_child_launch_exception_keeps_actual_failure(self):
        environment = {key: "1" for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")}

        def failed(*_args, **_kwargs):
            raise OSError("invented launch error")

        with self.assertRaises(common.InvalidBinding):
            controller.capture_child(["invented-child"], self.root, environment, failed)
        invocation = common.read_json(self.root / "invocation.json")
        self.assertIsNone(invocation["exit_code"])
        self.assertEqual(invocation["launch_error"]["message"], "invented launch error")

    def _original_fixture(self):
        identity = "gbsg2__clinical__r01f01__coxph__full"
        for name in ("claims", "cells", "traces"):
            (self.root / name).mkdir(exist_ok=True)
        cell = {"cell_id": identity, "status": "failed", "error_type": "RuntimeError", "message": "synthetic original failed outcome"}
        cell["cell_content_sha256"] = common.digest(cell)
        path = self.root / "cells" / f"{identity}.json"
        common.write_new(path, cell)
        evidence = asdict(CONTRACTS.SourceEvidence(identity, common.ORIGINAL_MANIFEST_SHA, common.sha(path), cell["cell_content_sha256"],
                                                  "failed", common.digest({"fixture": "sourceproof"}), {}, {}))
        return identity, evidence

    def test_owner_active_and_missing_evidence_both_wait(self):
        identity, evidence = self._original_fixture()
        claim = self.root / "claims" / f"{identity}.json"
        claim.write_text('{"synthetic_active_owner":true}')
        self.assertIsNone(common.verify_original_outcome(self.root, identity, evidence))
        claim.unlink()
        self.assertIsNone(common.verify_original_outcome(self.root, identity, None))
        self.assertEqual(common.verify_original_outcome(self.root, identity, evidence)["status"], "failed")

    def test_original_orphan_inventory_changed_is_refused(self):
        identity, evidence = self._original_fixture()
        directory = self.root / "traces" / identity
        directory.mkdir()
        (directory / "fixture.nc").write_bytes(b"invented opaque bytes, not NetCDF")
        with self.assertRaises(common.InvalidBinding):
            common.verify_original_outcome(self.root, identity, evidence)
        evidence["unreferenced_trace_sha256"] = {f"traces/{identity}/fixture.nc": common.sha(directory / "fixture.nc")}
        self.assertEqual(common.verify_original_outcome(self.root, identity, evidence)["status"], "failed")

    def _controller_fixture(self, *, changed=False):
        """Build an entirely invented carrier/source proof for controller guards."""
        model = "catalytic_fixed" if changed else "coxph"
        identity = f"gbsg2__clinical__r01f01__{model}__full"
        original, output, inputs = self.root / "original", self.root / "output", self.root / "inputs"
        for directory in (original / "cells", original / "claims", output / "cells", output / "claims",
                          output / "attempts", output / "passes", inputs / "cells" / identity / "roles",
                          inputs / "cells" / identity / "source_snapshots", inputs / "cells" / identity / "snapshots"):
            directory.mkdir(parents=True, exist_ok=True)
        cell = {"cell_id": identity, "status": "failed", "error_type": "RuntimeError", "message": "invented old failure"}
        cell["cell_content_sha256"] = common.digest(cell)
        common.write_new(original / "cells" / f"{identity}.json", cell)
        directory = inputs / "cells" / identity
        source_proof = directory / "source_snapshots/source.json"
        common.write_new(source_proof, common.seal({"synthetic_fixture": True, "cell_sha256": common.sha(original / "cells" / f"{identity}.json")}))
        evidence = CONTRACTS.SourceEvidence(identity, common.ORIGINAL_MANIFEST_SHA, common.sha(original / "cells" / f"{identity}.json"),
                                            cell["cell_content_sha256"], "failed", common.sha(source_proof), {}, {})
        roles, artifacts = {}, {}
        for name in CONTRACTS.required_roles(model):
            old_value = {"synthetic": "same", "role": name}
            new_value = {"synthetic": "changed", "role": name} if changed and name == "outer.synthetic_constructor" else old_value
            old, new = common.digest(old_value), common.digest(new_value)
            proof_path = directory / "roles" / f"{name}.json"
            common.write_new(proof_path, common.seal({"schema_version": 1, "synthetic_fixture": True, "role": name,
                             "original_cell_id": identity, "definition_content_sha256": "d" * 64,
                             "basis": "exact_reconstruction", "original": old_value, "corrected": new_value,
                             "original_sha256": old, "corrected_sha256": new}))
            roles[name] = CONTRACTS.Comparison(old, new, common.sha(proof_path), "exact_reconstruction")
            artifacts[str(proof_path.relative_to(directory))] = common.file_binding(proof_path)
        witness = CONTRACTS.FitWitness(identity, model, "d" * 64, CONTRACTS.seed_ledger(identity), CONTRACTS.seed_ledger(identity),
                                       roles, {"outer": ("accepted", "e" * 64)} if changed else {}, None)
        input_path = directory / "input_witness.json"
        common.write_new(input_path, common.seal({"definition_content_sha256": "d" * 64, "fit_witness": asdict(witness), "proof_artifacts": artifacts}))
        decision = CONTRACTS.classify(CONTRACTS.FitWitness(**{**witness.__dict__, "original_evidence": evidence}))
        snapshot_path = directory / "snapshots/source.json"
        common.write_new(snapshot_path, common.seal({"original_cell_id": identity, "definition_content_sha256": "d" * 64,
                         "input_witness_sha256": common.sha(input_path), "source_evidence": asdict(evidence),
                         "original_claim_active": False, "decision": decision,
                         "artifacts": {str(source_proof.relative_to(directory)): common.file_binding(source_proof)}}))
        entry = {"original_cell_id": identity, "model": model, "input_witness_path": str(input_path.relative_to(inputs)),
                 "input_witness_sha256": common.sha(input_path), "snapshot_path": str(snapshot_path.relative_to(inputs)),
                 "snapshot_sha256": common.sha(snapshot_path)}
        args = SimpleNamespace(output=output, manifest_sha256="a" * 64, freeze_sha256="b" * 64,
                               freeze=self.root / "never_real_freeze", manifest=self.root / "never_real_manifest",
                               phase="pilot", python=Path(sys.executable), limit=None)
        freeze = {"definition_content_sha256": "d" * 64, "paths": {"witness_root": str(inputs), "original_run": str(original)},
                  "implementation_source_sha256": {name: common.sha(HERE / name) for name in common.OWN_SOURCES}}
        manifest = {"pilot_cells": [identity]}
        instance = controller.Controller(args, freeze, manifest, {"entries": [entry]}, {}, CONTRACTS)
        return instance, entry, original, output

    def test_controller_reuses_original_failure_without_fitting(self):
        instance, entry, _, output = self._controller_fixture()
        instance.invoke = lambda *_args, **_kwargs: self.fail("unchanged failure must not be refitted")
        value = instance.record(entry)
        self.assertEqual(value["operation"], "reuse_original_outcome")
        self.assertFalse(value["fit_dispatched"])
        record = common.read_json(output / "cells" / f"{entry['original_cell_id']}.json")
        self.assertEqual(record["scientific_status"], "failed")
        self.assertEqual(record["fit_seconds"], 0.0)
        self.assertEqual(instance.record(entry)["status"], "verified_existing_outcome")

    def test_controller_changed_input_waits_for_current_owner(self):
        instance, entry, original, output = self._controller_fixture(changed=True)
        claim = original / "claims" / f"{entry['original_cell_id']}.json"
        claim.write_text('{"synthetic_active_owner":true}')
        instance.invoke = lambda *_args, **_kwargs: self.fail("active original owner must block changed fitting")
        value = instance.record(entry)
        self.assertEqual(value["status"], "await_original_owner_or_outcome")
        self.assertEqual(list((output / "attempts").iterdir()), [])
        self.assertEqual(list((output / "cells").iterdir()), [])

    def test_controller_failed_owned_child_is_retained_and_not_automatically_retried(self):
        instance, entry, _, output = self._controller_fixture(changed=True)
        calls = []

        def failed(argv, **kwargs):
            calls.append(argv)
            kwargs["stderr"].write(b"invented failed child\n")
            return SimpleNamespace(returncode=17)

        instance.invoke = failed
        with self.assertRaises(common.InvalidBinding):
            instance.record(entry)
        attempt = output / "attempts" / entry["original_cell_id"]
        self.assertEqual(common.read_json(attempt / "invocation.json")["exit_code"], 17)
        self.assertFalse((output / "cells" / f"{entry['original_cell_id']}.json").exists())
        with self.assertRaises(common.InvalidBinding):
            instance.record(entry)
        self.assertEqual(len(calls), 1)

    def test_absent_actual_proof_never_accepts_opaque_complete_role(self):
        row = {"original_sha256": "a" * 64, "corrected_sha256": "a" * 64,
               "proof_receipt_sha256": "b" * 64, "basis": "exact_reconstruction"}
        document = {"fit_witness": {"model": "coxph", "roles": {name: row for name in CONTRACTS.required_roles("coxph")}},
                    "proof_artifacts": {}}
        with self.assertRaises(common.InvalidBinding):
            common.verify_witness_proofs(self.root, document, CONTRACTS)

    def test_actual_runtime_requires_current_interpreter_and_all_numeric_one(self):
        python = Path(sys.executable).resolve(strict=True)
        environment = dict.fromkeys(common.NUMERIC_THREAD_VARIABLES, "1")
        self.assertTrue(common.validate_runtime(python, environment)["locked_interpreter_samefile"])
        with patch.object(Path, "samefile", return_value=False), self.assertRaises(common.InvalidBinding):
            common.validate_runtime(python, environment)
        for name in common.NUMERIC_THREAD_VARIABLES:
            with self.assertRaises(common.InvalidBinding):
                common.validate_runtime(python, {**environment, name: "2"})

    def test_role_proof_bytes_do_not_certify_different_canonical_values(self):
        instance, entry, _, _ = self._controller_fixture()
        path = common.below(instance.paths["witness_root"], entry["input_witness_path"])
        document = common.read_json(path, entry["input_witness_sha256"])
        common.verify_witness_proofs(path.parent, document, CONTRACTS)
        name = next(iter(document["fit_witness"]["roles"]))
        changed = copy.deepcopy(document)
        changed["fit_witness"]["roles"][name]["corrected_sha256"] = "f" * 64
        with self.assertRaises(common.InvalidBinding):
            common.verify_witness_proofs(path.parent, changed, CONTRACTS)

    def test_actual_freeze_missing_never_imports_or_dispatches(self):
        path = self.root / "not-a-freeze.json"
        common.write_new(path, common.seal({"status": "synthetic_only_not_reviewed"}))
        with self.assertRaises(common.InvalidBinding):
            common.load_gates(path, common.sha(path), path, common.sha(path), HERE)

    def test_remaining_pilot_review_refuses_pending_or_unbound_results(self):
        manifest = {"pilot_cells": ["pending"]}
        value = {"status": "full_budget_pilot_reviewed", "corrected_manifest_sha256": "fixture",
                 "approve_remaining_selective_fits": True, "original_full_budget_retained": True,
                 "all_failures_retained_and_reviewed": True, "pilot_outcomes": {}}
        with self.assertRaises(common.InvalidBinding):
            controller.validate_pilot_review(value, manifest, "fixture", self.root)

    def test_arithmetic_unchanged_and_negative_kappa_accounted_without_retry(self):
        fixed = "metabric__clinical__r01f01__catalytic_fixed__full::outer"
        adaptive = "metabric__clinical__r01f01__catalytic_adaptive__full::outer"
        failed = "metabric__clinical__r01f01__catalytic_wme__full::inner_01"
        preflight = [{"context_id": fixed, "status": "accepted_original_first_draw", "receipt_sha256": "a" * 64},
                     {"context_id": adaptive, "status": "accepted_rank_conditioned_redraw", "receipt_sha256": "b" * 64},
                     {"context_id": failed, "status": "exhausted_rank_cap", "receipt_sha256": "c" * 64}]
        common_row = {"evidence_sha256": ["d" * 64]}
        rows = [{**common_row, "context_id": fixed, "preflight_status": preflight[0]["status"], "preflight_receipt_sha256": "a" * 64,
                 "status": "unchanged_inputs_independently_witnessed", "formula_checks": "not_required", "kappa_required": False,
                 "original_kappa_status": "not_required", "independent_replay_receipt_sha256": "d" * 64},
                {**common_row, "context_id": adaptive, "preflight_status": preflight[1]["status"], "preflight_receipt_sha256": "b" * 64,
                 "status": "original_kappa_gate_failed", "formula_checks": "passed", "kappa_required": True,
                 "original_kappa_status": "original_gate_failed", "optimizer_predicate_evidence_sha256": "d" * 64,
                 "adaptive_status": "pending_original_kappa_gate_failure"},
                {**common_row, "context_id": failed, "preflight_status": preflight[2]["status"], "preflight_receipt_sha256": "c" * 64,
                 "status": "preflight_exhausted_rank_cap", "formula_checks": "not_applicable", "kappa_required": False,
                 "original_kappa_status": "not_applicable"}]
        account = {"status": "all_scheduled_arithmetic_outcomes_accounted", "preflight_completion_sha256": "fixture",
                   "proposals_selected_by_optimizer": False, "extra_proposals_generated": False, "context_outcomes": rows,
                   "artifacts": {"synthetic_proof.json": {"sha256": "d" * 64, "bytes": 1}}}
        common.validate_arithmetic(account, {"outcomes": preflight}, "fixture")
        rows[1]["adaptive_status"] = "verified"
        with self.assertRaises(common.InvalidBinding):
            common.validate_arithmetic(account, {"outcomes": preflight}, "fixture")
        rows[1]["adaptive_status"] = "pending_original_kappa_gate_failure"
        rows[1]["formula_checks"] = "mismatch"
        with self.assertRaises(common.InvalidBinding):
            common.validate_arithmetic(account, {"outcomes": preflight}, "fixture")

    def test_execution_review_digest_is_acyclic_and_binds_code_and_input(self):
        freeze = {key: "fixture" for key in ("original_production_commit", "original_manifest_sha256", "definition_content_sha256",
                                             "input_inventory_sha256", "preflight_completion_sha256", "preflight_manifest_sha256",
                                             "implementation_source_sha256", "dependency_source_sha256", "execution")}
        freeze["arithmetic_accounting"] = {"sha256": "a" * 64}
        before = common.execution_definition(freeze)
        freeze["review_bindings"] = {"freeze": {"sha256": "future_review"}}
        freeze["content_sha256"] = "future_freeze"
        self.assertEqual(before, common.execution_definition(freeze))
        freeze["implementation_source_sha256"] = "changed_fixture_source"
        self.assertNotEqual(before, common.execution_definition(freeze))

    def test_tool_imports_do_not_load_project_src_in_a_fresh_process(self):
        script = """
import sys
sys.path.insert(0, sys.argv[1])
import fit_common, fit_controller, fit_child
assert not any(name == 'src' or name.startswith('src.') for name in sys.modules)
"""
        result = subprocess.run([sys.executable, "-I", "-B", "-c", script, str(HERE)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
