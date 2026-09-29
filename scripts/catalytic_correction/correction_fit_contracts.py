"""Pure selective-fit contracts; no data loading, hashing of files or fitting.

Callers supply evidence digests established by separate actual reconstruction
and verification. These functions validate their structure and relationships;
they cannot establish that supplied digests describe the actual scientific
inputs. No function dispatches a fit or approves a correction specification.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Literal

CATALYTIC_MODELS = ("catalytic_fixed", "catalytic_adaptive", "catalytic_wme")
OUTCOME_STATUSES = ("complete", "failed", "failed_diagnostics")
GENERATOR_STATUSES = ("accepted", "exhausted_rank_cap", "nonrank_failure", "input_failure")
ORIGINAL_MANIFEST_SHA256 = "83b9049fb6aaaadab576b34de0741e4f510344dcefba9f96198d15b5ab4f49b9"
FULL_BUDGET = {
    "draws": 2000, "tune": 2000, "chains": 4, "cores": 1,
    "target_accept": 0.999, "maximum_refits": 2, "refit_tune_multiplier": 2,
    "final_noncentered_baseline": True,
    "diagnostic_gate": "unchanged_ADR027_all_parameters",
    "catalytic_prior_predictive": "likelihood_free_joint_prior_nuts_with_same_gate",
}
COMMON_ROLES = (
    "job_and_censoring", "ordered_raw_training", "ordered_raw_validation",
    "feature_spec_and_gene_budget", "training_outcomes", "validation_outcomes",
    "preprocessing_state", "encoded_training", "encoded_validation",
    "model_sources", "model_configuration", "fit_sources", "fit_configuration",
    "evaluation_sources", "evaluation_configuration", "environment", "seed_ledger",
    "candidate_configuration", "unchanged_execution_dependencies",
)
INNER_ROLES = (
    "memberships_and_raw_values", "training_and_validation_outcomes",
    "preprocessing_state", "encoded_training_and_validation",
    "synthetic_constructor", "legacy_metadata_or_absence",
    "candidate_model_fit_evaluation_inputs",
)


def require(condition: bool, message: str) -> None:
    """Reject an invalid supplied contract without taking external action."""
    if not condition:
        raise ValueError(message)


def digest(value: Any) -> str:
    """SHA-256 of finite canonical JSON; this does not hash scientific files."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def check_digest(value: str) -> None:
    """Require a lowercase 64-character SHA-256 string."""
    require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            "invalid SHA-256 digest")


def deterministic_seed(base_seed: int, *parts: object) -> int:
    """Copy the pinned original SHA-256 derivation, with no package imports."""
    payload = "|".join([str(base_seed), *(str(part) for part in parts)])
    return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:4], "big") % (2**31 - 1)


def seed_ledger(original_cell_id: str, base_seed: int = 260817) -> dict[str, Any]:
    """Describe unchanged cell, proposal, fit, tuning and evaluation seeds.

    A new corrected run identifier must never replace ``original_cell_id`` in
    the seed namespace. Retry proposal seeds belong to separate generator
    attempt receipts and never change these original seeds.
    """
    require(isinstance(original_cell_id, str) and bool(original_cell_id), "missing original cell ID")
    require(type(base_seed) is int and base_seed >= 0, "invalid base seed")
    cell = deterministic_seed(base_seed, "extensions", original_cell_id)
    inner = deterministic_seed(cell, "inner_cv")
    return {
        "original_cell_id": original_cell_id, "base_seed": base_seed, "cell": cell,
        "outer_prior": deterministic_seed(cell, "outer_prior"), "inner_cv": inner,
        "outer_fit_attempts": [deterministic_seed(cell, "fit_attempt", a) for a in range(3)],
        "evaluation": cell,
        "inner_prior": {str(f): deterministic_seed(inner, "inner_prior", f) for f in range(1, 4)},
        "inner_fit": {f"{f}:{c}": deterministic_seed(inner, "inner_fit", f, c)
                      for f in range(1, 4) for c in range(3)},
    }


def required_roles(model: str) -> tuple[str, ...]:
    """Return the complete declared comparison surface, including all WME folds.

    Each role binds exact values, dtypes, shapes and ordered identities, or a
    byte-bound recipe proving an unchanged unreachable stage. An outcome
    alone, patient IDs alone or full rank alone does not satisfy a role.
    """
    roles = COMMON_ROLES
    if model in CATALYTIC_MODELS:
        roles += ("outer.synthetic_constructor", "outer.legacy_metadata_or_absence")
    if model == "catalytic_wme":
        roles += tuple(f"inner.{f}.{role}" for f in range(1, 4) for role in INNER_ROLES)
    return roles


@dataclass(frozen=True)
class Comparison:
    """An actual-byte or exact-reconstruction equality witness for one role.

    Missing values/receipts remain unresolved. ``reconstructed`` must be
    labelled explicitly in the referenced receipt; it is not a claim that the
    old cell saved an array or returned rejected-draw metadata.
    """

    original_sha256: str | None
    corrected_sha256: str | None
    proof_receipt_sha256: str | None
    basis: Literal["saved_bytes", "exact_reconstruction"]

    def complete(self) -> bool:
        """Validate supplied digests, returning whether all three are present."""
        require(self.basis in {"saved_bytes", "exact_reconstruction"}, "unknown witness basis")
        for value in (self.original_sha256, self.corrected_sha256, self.proof_receipt_sha256):
            if value is not None:
                check_digest(value)
        return all(v is not None for v in
                   (self.original_sha256, self.corrected_sha256, self.proof_receipt_sha256))


@dataclass(frozen=True)
class SourceEvidence:
    """Immutable original outcome and actual recorded/orphan trace inventory.

    ``verification_receipt_sha256`` must bind a fresh check of the manifest,
    cell bytes/content and referenced traces. Orphans are preserved but have
    no invented stored diagnostic or gate claims. This carrier does not read
    or independently verify those files.
    """

    original_cell_id: str
    original_manifest_sha256: str
    cell_byte_sha256: str
    cell_content_sha256: str
    status: str
    verification_receipt_sha256: str
    referenced_trace_sha256: dict[str, str]
    unreferenced_trace_sha256: dict[str, str]
    wme_tuning_record_sha256: str | None = None

    def validate(self) -> None:
        """Check evidence structure while treating accepted and failed outcomes alike."""
        require(bool(self.original_cell_id), "missing original evidence identity")
        require(self.status in OUTCOME_STATUSES, "unknown original outcome")
        require(self.original_manifest_sha256 == ORIGINAL_MANIFEST_SHA256, "foreign original manifest")
        for value in (self.original_manifest_sha256, self.cell_byte_sha256,
                      self.cell_content_sha256, self.verification_receipt_sha256):
            check_digest(value)
        require(not (set(self.referenced_trace_sha256) & set(self.unreferenced_trace_sha256)),
                "trace cannot be both referenced and orphaned")
        for group in (self.referenced_trace_sha256, self.unreferenced_trace_sha256):
            for name, value in group.items():
                require(bool(name) and not name.startswith("/") and ".." not in name.split("/"),
                        "unsafe relative trace name")
                check_digest(value)
        if self.wme_tuning_record_sha256 is not None:
            check_digest(self.wme_tuning_record_sha256)


@dataclass(frozen=True)
class FitWitness:
    """One proposed whole-cell reuse comparison under a distinct correction.

    Generator context names are ``outer`` and, for WME, ``inner_01..03``.
    Their receipt hashes bind all attempts/cap/exhaustion and actual preflight
    outcomes. Equal successful first proposals may be reused; a terminal
    corrected input failure is a new retained execution outcome, not a fit.
    """

    original_cell_id: str
    model: str
    correction_specification_sha256: str
    original_seeds: dict[str, Any]
    corrected_seeds: dict[str, Any]
    roles: dict[str, Comparison]
    generator_contexts: dict[str, tuple[str, str]]
    original_evidence: SourceEvidence | None


def classify(witness: FitWitness) -> dict[str, Any]:
    """Classify supplied proof as reuse, selective fit, input failure or unresolved.

    This is a pure planning decision. A changed-input cell may be scheduled
    before its original worker finishes; its original outcome remains pending.
    An identical-input cell waits for actual original evidence. No optimizer/
    MCMC failure is retried just because its old outcome failed.
    """
    check_digest(witness.correction_specification_sha256)
    expected = seed_ledger(witness.original_cell_id)
    require(witness.original_seeds == expected and witness.corrected_seeds == expected,
            "cell/inner/fit/evaluation seed identity differs")
    require(witness.model and f"__{witness.model}__" in witness.original_cell_id,
            "model does not agree with original cell ID")
    missing, changed = [], []
    for role in required_roles(witness.model):
        comparison = witness.roles.get(role)
        if comparison is None or not comparison.complete():
            missing.append(role)
        elif comparison.original_sha256 != comparison.corrected_sha256:
            changed.append(role)
    expected_contexts = {"outer"} if witness.model in CATALYTIC_MODELS else set()
    if witness.model == "catalytic_wme":
        expected_contexts |= {f"inner_{f:02}" for f in range(1, 4)}
    require(not (set(witness.generator_contexts) - expected_contexts), "unexpected generator context")
    for context in sorted(expected_contexts - set(witness.generator_contexts)):
        missing.append(f"generator_receipt:{context}")
    failures = {}
    for context, (status, receipt_sha) in witness.generator_contexts.items():
        require(status in GENERATOR_STATUSES, "unknown corrected generator outcome")
        check_digest(receipt_sha)
        if status != "accepted":
            failures[context] = status
    if witness.original_evidence is not None:
        witness.original_evidence.validate()
        require(witness.original_evidence.original_cell_id == witness.original_cell_id,
                "original outcome belongs to another cell")
    tuning_dependencies = {
        "model_sources", "model_configuration", "fit_sources", "fit_configuration",
        "evaluation_sources", "evaluation_configuration", "environment",
        "candidate_configuration", "unchanged_execution_dependencies",
    }
    inner_changed = any(role.startswith("inner.") or role in tuning_dependencies for role in changed)
    recorded_tuning = (None if witness.original_evidence is None else
                       witness.original_evidence.wme_tuning_record_sha256)
    wme_action = ("retune_then_fit_changed_inputs" if inner_changed or recorded_tuning is None
                  else "fit_changed_inputs_reuse_tuning")
    action = ("retain_input_failure" if failures else "unresolved" if missing else
              wme_action if changed and witness.model == "catalytic_wme" else
              "fit_changed_inputs" if changed else "await_original_outcome"
              if witness.original_evidence is None else "reuse_original_outcome")
    result = {
        "schema_version": 1, "scope": "supplied_evidence_contract_not_actual_byte_verification",
        "original_cell_id": witness.original_cell_id, "model": witness.model,
        "correction_specification_sha256": witness.correction_specification_sha256,
        "action": action, "missing_roles": missing, "changed_roles": changed,
        "generator_failures": failures, "witness_sha256": digest(asdict(witness)),
        "tuning_record_reused_sha256": recorded_tuning
        if action == "fit_changed_inputs_reuse_tuning" else None,
        "original_status": None if witness.original_evidence is None else witness.original_evidence.status,
        "original_outcome_available": witness.original_evidence is not None,
        "source_evidence": None if witness.original_evidence is None else asdict(witness.original_evidence),
        "seed_ledger_sha256": digest(expected), "fit_dispatched": False,
    }
    result["decision_content_sha256"] = digest(result)
    return result


def reuse_envelope(decision: dict[str, Any], corrected_manifest_sha256: str) -> dict[str, Any]:
    """Reference immutable old payloads without claiming a newly executed fit.

    The later resolver checks every referenced byte and returns the original
    cell unmodified to analysis, with this provenance retained alongside it.
    """
    check_digest(corrected_manifest_sha256)
    require(decision.get("decision_content_sha256") ==
            digest({k: v for k, v in decision.items() if k != "decision_content_sha256"}),
            "decision changed")
    require(decision["action"] == "reuse_original_outcome" and not decision["missing_roles"]
            and not decision["changed_roles"] and not decision["generator_failures"], "not exact reuse")
    return {
        "schema_version": 1, "original_cell_id": decision["original_cell_id"],
        "corrected_manifest_sha256": corrected_manifest_sha256,
        "evidence_status": "post_hoc_generator_correction",
        "result_origin": "reused_original_immutable_outcome",
        "fit_execution": "not_run_reused_reference", "status": decision["original_status"],
        "original_evidence": decision["source_evidence"],
        "decision_content_sha256": decision["decision_content_sha256"],
        "witness_sha256": decision["witness_sha256"],
    }


@dataclass(frozen=True)
class TuningUse:
    """One WME fold/candidate slot, preserving its actual result or nonexecution.

    A finite ``score`` is used only for ``scored``. Failures/nonexecution have
    no score and require a bound record explaining their cause; failed
    candidate indices remain in the selection denominator.
    """

    fold: int
    candidate: int
    synthetic_sha256: str
    seed: int
    state: Literal["scored", "failed", "not_executed"]
    score: float | None
    record_sha256: str


def resolve_wme_tuning(original_cell_id: str, designs: dict[int, str],
                       uses: list[TuningUse]) -> dict[str, Any]:
    """Resolve nine recorded slots with the unchanged all-three-fold IBS rule.

    Missing slots remain pending. A not-executed slot means a terminal input
    or execution interruption and blocks selection. Candidate failures do
    not trigger synthetic redraws. Ties choose the original candidate order.
    This function consumes supplied synthetic scores in unit tests only here.
    """
    require(set(designs) == {1, 2, 3}, "all three WME shared designs are required")
    for value in designs.values():
        check_digest(value)
    ledger = seed_ledger(original_cell_id)
    observed = set()
    rows = {c: [] for c in range(3)}
    for use in uses:
        key = (use.fold, use.candidate)
        require(use.fold in designs and use.candidate in rows and key not in observed,
                "unexpected or duplicate WME use")
        observed.add(key)
        require(use.synthetic_sha256 == designs[use.fold], "WME candidates do not share their fold design")
        require(use.seed == ledger["inner_fit"][f"{use.fold}:{use.candidate}"], "WME fit seed changed")
        check_digest(use.record_sha256)
        require(use.state in {"scored", "failed", "not_executed"}, "unknown WME use state")
        require((use.state == "scored" and isinstance(use.score, (int, float))
                 and not isinstance(use.score, bool) and math.isfinite(use.score))
                or (use.state != "scored" and use.score is None), "invalid WME score/failure record")
        rows[use.candidate].append(use)
    means = {c: sum(float(u.score) for u in row) / 3 for c, row in rows.items()
             if len(row) == 3 and all(u.state == "scored" for u in row)}
    terminal = any(u.state == "not_executed" for u in uses)
    state = ("pending" if len(observed) != 9 else "blocked_execution" if terminal else
             "selected" if means else "failed_no_eligible_candidate")
    return {
        "status": state, "selected_index": min(means, key=lambda c: (means[c], c))
        if state == "selected" else None,
        "eligible_mean_ibs": means, "recorded_uses": len(observed), "expected_uses": 9,
        "candidate_multipliers": [0.25, 1.0, 4.0],
        "scope": "supplied_record_accounting_original_numpy_selection_required_in_integration",
        "states": dict(Counter(u.state for u in uses)),
        "all_actual_records_sha256": digest([asdict(u) for u in sorted(uses, key=lambda u: (u.fold, u.candidate))]),
    }


def utc(value: str) -> datetime:
    """Parse an explicit UTC timestamp; local/naive times are rejected."""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None and parsed.utcoffset().total_seconds() == 0,
            "timestamp is not explicit UTC")
    return parsed


def pilot_dispatch_contract(freeze: dict[str, Any], specification: dict[str, Any],
                            decisions: list[dict[str, Any]], sampling: dict[str, Any]) -> dict[str, Any]:
    """Validate a future root-reviewed full-budget pilot plan, without launching it.

    Required review hashes are actual evidence dependencies, not approval
    booleans supplied by this preparation. The contract does not choose pilot
    membership; its frozen specification does so before corrected scoring.
    """
    require(sampling == FULL_BUDGET, "pilot changes the original sampler/remedy/gate budget")
    require(freeze["preflight_coverage"] == {"outer": 825, "inner": 825, "logical_grid": 1625},
            "whole-block preflight accounting is incomplete")
    for role in ("specification", "addendum", "code", "inputs", "preflight", "reuse_inventory",
                 "implementation_review", "method_review", "changed_input_arithmetic_review"):
        check_digest(freeze[f"{role}_sha256"])
    check_digest(freeze["freeze_sha256"])
    check_digest(specification["review_sha256"])
    require(specification["freeze_sha256"] == freeze["freeze_sha256"], "pilot refers to another freeze")
    require(utc(specification["specified_at_utc"]) <= utc(freeze["frozen_at_utc"]),
            "pilot specified after freeze")
    require(freeze["first_corrected_score_at_utc"] is None, "prelaunch contract already has corrected scores")
    lookup = {}
    for decision in decisions:
        identity = decision["original_cell_id"]
        require(identity not in lookup, "duplicate inventory decision")
        require(decision["decision_content_sha256"] ==
                digest({k: v for k, v in decision.items() if k != "decision_content_sha256"}), "changed decision")
        require(decision["correction_specification_sha256"] == freeze["specification_sha256"],
                "inventory scientific specification changed")
        lookup[identity] = decision
    ids = specification["cell_ids"]
    require(isinstance(ids, list) and bool(ids) and len(set(ids)) == len(ids), "invalid pilot IDs")
    require(all(i in lookup and lookup[i]["action"] in
                {"fit_changed_inputs", "retune_then_fit_changed_inputs", "fit_changed_inputs_reuse_tuning"}
                for i in ids),
            "pilot contains reused, unresolved or input-failed cells")
    return {
        "status": "pilot_contract_validated_not_dispatched", "cell_ids": ids,
        "freeze_sha256": freeze["freeze_sha256"], "sampling_sha256": digest(sampling),
        "frozen_at_utc": freeze["frozen_at_utc"],
        "specification_sha256": digest(specification),
        "decision_sha256": {i: lookup[i]["decision_content_sha256"] for i in ids},
        "failed_outcomes_must_be_retained": True, "fits_launched": 0,
    }


def summarize_pilot(plan: dict[str, Any], outcomes: list[dict[str, Any]]) -> dict[str, Any]:
    """Account for actual supplied pilot receipts; leave launch approval to root.

    Every scheduled outcome, including failures, needs an actual execution
    record, matching budget/freeze and measured wall time. Execution and
    diagnostic failures require review; they are never silently removed
    from timing or rerun under a changed specification.
    """
    require(plan["status"] == "pilot_contract_validated_not_dispatched", "invalid pilot plan")
    require(len(outcomes) == len(plan["cell_ids"]), "pilot outcome accounting incomplete")
    seen = set()
    for row in outcomes:
        identity = row["original_cell_id"]
        require(identity in plan["cell_ids"] and identity not in seen, "pilot result grid changed")
        seen.add(identity)
        require(row["freeze_sha256"] == plan["freeze_sha256"] and
                row["sampling_sha256"] == plan["sampling_sha256"], "pilot budget/freeze differs")
        require(row["status"] in OUTCOME_STATUSES, "unknown pilot outcome")
        require(row["full_budget_verified"] is True, "unverified or reduced pilot execution")
        for field in ("result_evidence_sha256", "execution_receipt_sha256", "independent_verification_sha256"):
            check_digest(row[field])
        start, finish = utc(row["started_at_utc"]), utc(row["finished_at_utc"])
        require(start >= utc(plan["frozen_at_utc"]), "pilot executed before correction freeze")
        score_at = row["score_started_at_utc"]
        if score_at is not None:
            require(start <= utc(score_at) <= finish, "score timestamp is outside execution/freeze")
        seconds = row["wall_seconds"]
        require(isinstance(seconds, (int, float)) and not isinstance(seconds, bool)
                and math.isfinite(seconds) and seconds >= 0 and finish >= start, "invalid measured timing")
        if row["status"] == "complete":
            require(score_at is not None, "accepted pilot omits actual scoring chronology")
            require(row["unchanged_acceptance_gates_passed"] is True, "accepted pilot bypasses gates")
    counts = dict(Counter(row["status"] for row in outcomes))
    return {
        "status": "all_pilot_outcomes_accounted_review_required", "status_counts": counts,
        "measured_wall_seconds_including_failures": sum(row["wall_seconds"] for row in outcomes),
        "failed_cells": [row["original_cell_id"] for row in outcomes if row["status"] != "complete"],
        "outcome_receipts_sha256": digest(outcomes), "remaining_grid_launch_approved": False,
        "total_grid_time_estimated": False,
    }
