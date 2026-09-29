"""Synthetic small-record tests; no scientific package, cohort or fit imports."""

from __future__ import annotations

import copy
import unittest
from dataclasses import replace

from scripts.catalytic_correction.correction_fit_contracts import (
    FULL_BUDGET,
    ORIGINAL_MANIFEST_SHA256,
    Comparison,
    FitWitness,
    SourceEvidence,
    TuningUse,
    classify,
    digest,
    pilot_dispatch_contract,
    required_roles,
    resolve_wme_tuning,
    reuse_envelope,
    seed_ledger,
    summarize_pilot,
)


def fixture(model: str = "catalytic_fixed", status: str = "complete") -> FitWitness:
    """Build explicitly fabricated comparison records, not scientific evidence."""
    identity = f"fixture__clinical__r01f01__{model}__full"
    contexts = {"outer": ("accepted", digest("fixture outer receipt"))}
    if model == "catalytic_wme":
        contexts |= {f"inner_{f:02}": ("accepted", digest(f"fixture inner {f}")) for f in range(1, 4)}
    return FitWitness(
        identity, model, digest("fixture correction freeze"), seed_ledger(identity), seed_ledger(identity),
        {r: Comparison(digest(r), digest(r), digest(f"fixture proof {r}"), "exact_reconstruction")
         for r in required_roles(model)}, contexts,
        SourceEvidence(identity, ORIGINAL_MANIFEST_SHA256, digest("fixture cell bytes"),
                       digest("fixture cell content"), status, digest("fixture verification"),
                       {"attempt1_posterior.nc": digest("fixture trace")},
                       {"unused_prior.nc": digest("fixture orphan")},
                       digest("fixture recorded tuning") if model == "catalytic_wme" else None),
    )


def changed(witness: FitWitness, role: str) -> FitWitness:
    """Change one supplied scientific role while retaining its proof record."""
    roles = dict(witness.roles)
    roles[role] = replace(roles[role], corrected_sha256=digest(f"fixture changed {role}"))
    return replace(witness, roles=roles)


def pilot_fixture() -> tuple[dict, dict, dict]:
    """Construct fabricated root-review bindings for pure dispatch validation."""
    witness = changed(fixture(), "outer.synthetic_constructor")
    decision = classify(witness)
    freeze = {f"{r}_sha256": digest(f"fixture {r}") for r in
              ("addendum", "code", "inputs", "preflight", "reuse_inventory", "implementation_review",
               "method_review", "changed_input_arithmetic_review")}
    freeze |= {"freeze_sha256": digest("fixture final freeze"),
               "specification_sha256": witness.correction_specification_sha256,
               "preflight_coverage": {"outer": 825, "inner": 825, "logical_grid": 1625},
               "frozen_at_utc": "2026-09-29T10:00:00Z", "first_corrected_score_at_utc": None}
    specification = {"freeze_sha256": freeze["freeze_sha256"],
                     "specified_at_utc": "2026-09-29T09:00:00Z", "review_sha256": digest("fixture review"),
                     "cell_ids": [witness.original_cell_id]}
    return freeze, specification, decision


class ContractsTests(unittest.TestCase):
    """Validate planning boundaries using fabricated finite hashes and scores."""

    def test_success_and_both_failure_kinds_reuse_without_new_fit(self) -> None:
        for status in ("complete", "failed", "failed_diagnostics"):
            with self.subTest(status=status):
                decision = classify(fixture(status=status))
                self.assertEqual(decision["action"], "reuse_original_outcome")
                envelope = reuse_envelope(decision, digest("fixture corrected manifest"))
                self.assertEqual(envelope["status"], status)
                self.assertEqual(envelope["fit_execution"], "not_run_reused_reference")
                self.assertEqual(envelope["original_evidence"]["unreferenced_trace_sha256"],
                                 {"unused_prior.nc": digest("fixture orphan")})

    def test_one_changed_input_requires_fit(self) -> None:
        for role in required_roles("catalytic_fixed"):
            with self.subTest(role=role):
                decision = classify(changed(fixture(), role))
                self.assertEqual(decision["action"], "fit_changed_inputs")
                with self.assertRaisesRegex(ValueError, "not exact reuse"):
                    reuse_envelope(decision, digest("fixture new manifest"))

    def test_missing_or_partial_proof_is_unresolved(self) -> None:
        witness = fixture()
        for field in ("original_sha256", "corrected_sha256", "proof_receipt_sha256"):
            roles = dict(witness.roles)
            roles["encoded_training"] = replace(roles["encoded_training"], **{field: None})
            with self.subTest(field=field):
                self.assertEqual(classify(replace(witness, roles=roles))["action"], "unresolved")
        roles = dict(witness.roles)
        del roles["feature_spec_and_gene_budget"]
        self.assertEqual(classify(replace(witness, roles=roles))["action"], "unresolved")

    def test_absent_original_waits_if_identical_but_changed_can_be_scheduled(self) -> None:
        witness = replace(fixture(), original_evidence=None)
        self.assertEqual(classify(witness)["action"], "await_original_outcome")
        decision = classify(changed(witness, "outer.synthetic_constructor"))
        self.assertEqual(decision["action"], "fit_changed_inputs")
        self.assertFalse(decision["original_outcome_available"])

    def test_bad_digest_foreign_outcome_and_changed_seed_refuse(self) -> None:
        witness = fixture()
        bad = replace(witness.original_evidence, original_cell_id="another cell")
        with self.assertRaisesRegex(ValueError, "another cell"):
            classify(replace(witness, original_evidence=bad))
        bad = replace(witness.original_evidence, original_manifest_sha256=digest("foreign manifest"))
        with self.assertRaisesRegex(ValueError, "foreign original manifest"):
            classify(replace(witness, original_evidence=bad))
        seeds = copy.deepcopy(witness.corrected_seeds)
        seeds["evaluation"] += 1
        with self.assertRaisesRegex(ValueError, "seed identity"):
            classify(replace(witness, corrected_seeds=seeds))
        roles = dict(witness.roles)
        roles["model_sources"] = replace(roles["model_sources"], original_sha256="invalid")
        with self.assertRaisesRegex(ValueError, "invalid SHA"):
            classify(replace(witness, roles=roles))

    def test_original_known_seed_fixture_and_new_id_namespace(self) -> None:
        identity = "gbsg2__clinical__r01f01__catalytic_fixed__full"
        ledger = seed_ledger(identity)
        self.assertEqual(ledger["cell"], 1914013249)
        self.assertEqual(ledger["outer_prior"], 1163959806)
        self.assertEqual(ledger["inner_cv"], 1583840389)
        self.assertEqual(ledger["outer_fit_attempts"], [801924248, 1712746067, 977176231])
        self.assertEqual(ledger["evaluation"], ledger["cell"])
        self.assertNotEqual(ledger, seed_ledger(f"corrected__{identity}"))

    def test_wme_inner_change_retunes_outer_only_preserves_recorded_tuning(self) -> None:
        witness = fixture("catalytic_wme", "failed")
        decision = classify(changed(witness, "outer.synthetic_constructor"))
        self.assertEqual(decision["action"], "fit_changed_inputs_reuse_tuning")
        self.assertEqual(decision["tuning_record_reused_sha256"], witness.original_evidence.wme_tuning_record_sha256)
        for role in ("inner.2.synthetic_constructor", "inner.3.encoded_training_and_validation", "environment"):
            with self.subTest(role=role):
                self.assertEqual(classify(changed(witness, role))["action"], "retune_then_fit_changed_inputs")
        source = replace(witness.original_evidence, wme_tuning_record_sha256=None)
        self.assertEqual(classify(changed(replace(witness, original_evidence=source),
                                          "outer.synthetic_constructor"))["action"],
                         "retune_then_fit_changed_inputs")

    def test_every_wme_inner_is_required_for_reuse(self) -> None:
        witness = fixture("catalytic_wme")
        contexts = dict(witness.generator_contexts)
        del contexts["inner_03"]
        self.assertEqual(classify(replace(witness, generator_contexts=contexts))["action"], "unresolved")
        roles = dict(witness.roles)
        del roles["inner.1.candidate_model_fit_evaluation_inputs"]
        self.assertEqual(classify(replace(witness, roles=roles))["action"], "unresolved")

    def test_terminal_input_failures_are_retained_without_fits(self) -> None:
        for state in ("exhausted_rank_cap", "nonrank_failure", "input_failure"):
            with self.subTest(state=state):
                witness = fixture("catalytic_wme")
                contexts = dict(witness.generator_contexts)
                contexts["inner_02"] = (state, digest(f"fixture {state} actual receipt"))
                decision = classify(replace(witness, generator_contexts=contexts, original_evidence=None))
                self.assertEqual(decision["action"], "retain_input_failure")
                self.assertFalse(decision["fit_dispatched"])
                self.assertEqual(decision["generator_failures"], {"inner_02": state})

    def test_wme_all_folds_candidate_failures_and_stable_ties(self) -> None:
        witness = fixture("catalytic_wme")
        designs = {f: digest(f"fixture shared design {f}") for f in range(1, 4)}
        seeds = witness.original_seeds["inner_fit"]
        uses = [TuningUse(f, c, designs[f], seeds[f"{f}:{c}"], "scored", 0.25,
                         digest(f"fixture score record {f}:{c}")) for f in range(1, 4) for c in range(3)]
        self.assertEqual(resolve_wme_tuning(witness.original_cell_id, designs, uses)["selected_index"], 0)
        uses[0] = replace(uses[0], state="failed", score=None)
        self.assertEqual(resolve_wme_tuning(witness.original_cell_id, designs, uses)["selected_index"], 1)
        self.assertEqual(resolve_wme_tuning(witness.original_cell_id, designs, uses[:-1])["status"], "pending")
        failed = [replace(use, state="failed", score=None) for use in uses]
        self.assertEqual(resolve_wme_tuning(witness.original_cell_id, designs, failed)["status"],
                         "failed_no_eligible_candidate")
        uses[1] = replace(uses[1], state="not_executed", score=None)
        self.assertEqual(resolve_wme_tuning(witness.original_cell_id, designs, uses)["status"], "blocked_execution")

    def test_wme_design_seed_collision_or_nonfinite_score_refuse(self) -> None:
        witness = fixture("catalytic_wme")
        designs = {f: digest(f"fixture design {f}") for f in range(1, 4)}
        seed = witness.original_seeds["inner_fit"]["1:0"]
        use = TuningUse(1, 0, designs[1], seed, "scored", 0.2, digest("fixture actual record"))
        for bad in (replace(use, synthetic_sha256=digest("another design")),
                    replace(use, seed=seed + 1), replace(use, score=float("nan"))):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    resolve_wme_tuning(witness.original_cell_id, designs, [bad])
        with self.assertRaisesRegex(ValueError, "duplicate WME"):
            resolve_wme_tuning(witness.original_cell_id, designs, [use, use])

    def test_pilot_requires_full_budget_bound_freeze_and_changed_jobs(self) -> None:
        freeze, spec, decision = pilot_fixture()
        plan = pilot_dispatch_contract(freeze, spec, [decision], FULL_BUDGET)
        self.assertEqual(plan["fits_launched"], 0)
        reduced = dict(FULL_BUDGET, draws=100)
        with self.assertRaisesRegex(ValueError, "budget"):
            pilot_dispatch_contract(freeze, spec, [decision], reduced)
        with self.assertRaisesRegex(ValueError, "preflight accounting"):
            pilot_dispatch_contract(dict(freeze, preflight_coverage={"outer": 824, "inner": 825,
                                                                     "logical_grid": 1625}),
                                    spec, [decision], FULL_BUDGET)
        late_spec = dict(spec, specified_at_utc="2026-09-29T11:00:00Z")
        with self.assertRaisesRegex(ValueError, "after freeze"):
            pilot_dispatch_contract(freeze, late_spec, [decision], FULL_BUDGET)
        with self.assertRaisesRegex(ValueError, "already has corrected scores"):
            pilot_dispatch_contract(dict(freeze, first_corrected_score_at_utc="2026-09-29T10:30:00Z"),
                                    spec, [decision], FULL_BUDGET)
        reuse = classify(fixture())
        with self.assertRaisesRegex(ValueError, "reused, unresolved"):
            pilot_dispatch_contract(freeze, spec, [reuse], FULL_BUDGET)

    def test_pilot_retains_failed_timing_and_cannot_approve_remaining_grid(self) -> None:
        freeze, spec, decision = pilot_fixture()
        plan = pilot_dispatch_contract(freeze, spec, [decision], FULL_BUDGET)
        row = {"original_cell_id": spec["cell_ids"][0], "freeze_sha256": plan["freeze_sha256"],
               "sampling_sha256": plan["sampling_sha256"], "status": "failed_diagnostics",
               "full_budget_verified": True, "result_evidence_sha256": digest("fixture failed result"),
               "execution_receipt_sha256": digest("fixture actual process"),
               "independent_verification_sha256": digest("fixture actual verification"),
               "started_at_utc": "2026-09-29T10:30:00Z", "finished_at_utc": "2026-09-29T10:31:00Z",
               "score_started_at_utc": None, "wall_seconds": 60.0}
        result = summarize_pilot(plan, [row])
        self.assertEqual(result["failed_cells"], spec["cell_ids"])
        self.assertEqual(result["measured_wall_seconds_including_failures"], 60.0)
        self.assertFalse(result["remaining_grid_launch_approved"])
        with self.assertRaisesRegex(ValueError, "accounting incomplete"):
            summarize_pilot(plan, [])
        with self.assertRaisesRegex(ValueError, "before correction freeze"):
            summarize_pilot(plan, [dict(row, started_at_utc="2026-09-29T09:30:00Z")])

    def test_tampered_decision_or_accepted_pilot_missing_gates_refuse(self) -> None:
        freeze, spec, decision = pilot_fixture()
        with self.assertRaisesRegex(ValueError, "changed decision"):
            pilot_dispatch_contract(freeze, spec, [dict(decision, action="reuse_original_outcome")], FULL_BUDGET)
        plan = pilot_dispatch_contract(freeze, spec, [decision], FULL_BUDGET)
        row = {"original_cell_id": spec["cell_ids"][0], "freeze_sha256": plan["freeze_sha256"],
               "sampling_sha256": plan["sampling_sha256"], "status": "complete", "full_budget_verified": True,
               "result_evidence_sha256": digest("fixture result"), "execution_receipt_sha256": digest("fixture process"),
               "independent_verification_sha256": digest("fixture verification"),
               "started_at_utc": "2026-09-29T10:30:00Z", "finished_at_utc": "2026-09-29T10:31:00Z",
               "score_started_at_utc": "2026-09-29T10:30:30Z", "wall_seconds": 60,
               "unchanged_acceptance_gates_passed": False}
        with self.assertRaisesRegex(ValueError, "bypasses gates"):
            summarize_pilot(plan, [row])


if __name__ == "__main__":
    unittest.main()
