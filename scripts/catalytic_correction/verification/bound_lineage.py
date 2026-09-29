"""Actual, byte-bound input reconstruction; instantiated only by root later."""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path
from typing import Any

from verification_gates import CONTRACTS, PREFLIGHT_CORE
from verification_io import Pins, canonical, child, require, sha


def import_pinned(path: Path, digest: str, name: str, pins: Pins) -> Any:
    """Import one explicit small source after byte verification, never implicitly."""
    pins.bind(path, digest)
    require(name not in sys.modules, "helper import namespace occupied")
    specification = importlib.util.spec_from_file_location(name, path)
    require(specification is not None and specification.loader is not None, "pinned helper cannot be imported")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    try:
        specification.loader.exec_module(module)
        pins.bind(path, digest)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def telemetry_number(value: Any) -> float:
    """Decode explicit original nonfinite observations without tightening guards."""
    if isinstance(value, dict):
        require(set(value) == {"nonfinite"}, "unknown nonfinite telemetry")
        table = {"nan": math.nan, "positive_infinity": math.inf, "negative_infinity": -math.inf}
        require(value["nonfinite"] in table, "unknown nonfinite observation")
        return table[value["nonfinite"]]
    require(type(value) in {int, float}, "expected numeric telemetry")
    return float(value)


def verify_observations(observed: dict[str, Any], cell: dict[str, Any], decision: dict[str, Any],
                        contexts: dict[str, dict[str, Any]], ledger: dict[str, Any],
                        candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Check real usage, seeds and retained nine-slot tuning/optimizer observations.

    This verifies recorded predicates rather than running an optimizer. It
    preserves the original NaN comparison semantics and adds no optimizer gate.
    """
    require(observed["original_cell_id"] == cell["cell_id"]
            and observed["all_bound_generator_contexts"] == sorted(contexts), "observation context scope differs")
    calls = observed["generation_calls"]
    names = [row["context"] for row in calls]
    require(len(names) == len(set(names)) and set(names) <= set(contexts), "generation call duplicated/foreign")
    for call in calls:
        current = contexts[call["context"]]
        request, index = current["record"]["request"], current["record"]["accepted_attempt_index"]
        attempt = current["record"]["attempts"][index]
        require(call["original_generation_seed"] == request["original_generation_seed"]
                and call["accepted_proposal_seed"] == attempt["seed"] and call["accepted_attempt_index"] == index
                and call["context_receipt_sha256"] == current["receipt_sha256"]
                and call["legacy_metadata_sha256"] == canonical(attempt["legacy_metadata"]),
                "generation usage/proposal seed/legacy metadata differs")
    telemetry = observed["telemetry"]
    require(telemetry["additional_optimizer_calls"] == 0 and telemetry["proposal_selection_by_optimizer"] is False
            and telemetry["original_predicates_and_selection_unchanged"] is True, "telemetry reports altered execution")
    models = telemetry["model_calls"]
    for index, row in enumerate(models):
        require(row["index"] == index and row["model"] == cell["model_key"], "model telemetry ordering/identity differs")
        if row["scope"] == "inner":
            fold, ci = row["fold"], row["candidate_index_zero_based"]
            require(fold in {1, 2, 3} and type(ci) is int and 0 <= ci < len(candidates)
                    and row["parameters"] == candidates[ci]
                    and row["seed"] == ledger["inner_fit"].get(f"{fold}:{ci}"), "inner candidate/fit seed differs")
        else:
            ai = row["attempt_index"]
            require(row["scope"] == "outer" and type(ai) is int and 0 <= ai < len(ledger["outer_fit_attempts"])
                    and row["seed"] == ledger["outer_fit_attempts"][ai]
                    and row["parameters"] == cell.get("selected_parameters"), "outer model seed/selection differs")
    for index, row in enumerate(telemetry["optimizer_calls"]):
        require(row["index"] == index and row["model_call_index"] in range(len(models)), "optimizer ownership differs")
        predicate = row["post_optimum_predicate"]
        if predicate is not None:
            kind, maximum = predicate["kind"], telemetry_number(predicate["max_absolute_score"])
            require(kind in {"kappa", "wme"}, "unknown original optimizer guard")
            limit = 1e-6 if kind == "kappa" else 1e-4
            expected = (not row["success"] or not predicate["value_finite"] or maximum > limit) if kind == "kappa" else (
                not row["success"] or not row["x_finite"] or maximum > limit)
            require(predicate["tolerance"] == limit and predicate["original_reject_predicate"] is expected,
                    "logged original optimizer predicate differs")
    tuning = telemetry["inner_tuning"]
    if decision["action"] == "fit_changed_inputs_reuse_tuning":
        require(tuning["reused"] is True and not tuning["invoked"] and not tuning["candidate_slots"]
                and tuning["source_record_sha256"] == decision["tuning_record_reused_sha256"]
                and tuning["selected_parameters"] == cell["selected_parameters"]
                and tuning["inner_tuning"] == cell["inner_tuning"], "cached WME tuning differs")
        require(not any(name.startswith("inner_") for name in names), "reused inner tuning was executed again")
    elif cell["model_key"] == "catalytic_wme":
        require(not tuning["reused"] and tuning["invoked"] is True, "changed WME inner inputs were not retuned")
        slots = tuning["candidate_slots"]
        require([(row["fold"], row["candidate_index_zero_based"]) for row in slots]
                == [(fold, ci) for fold in range(1, 4) for ci in range(3)], "WME nine-slot accounting differs")
        rows = tuning["rows"]
        if rows:
            require(len(rows) == 3 and [row["parameters"] for row in rows] == candidates, "retained tuning candidate order differs")
            for ci, row in enumerate(rows):
                these = [item for item in slots if item["candidate_index_zero_based"] == ci]
                scores = [item["score"] for item in these if item["status"] == "score_recorded"]
                failures = [item["failure"] for item in these if item["status"] == "original_candidate_failure"]
                require(row["scores"] == scores and row["failures"] == failures,
                        "retained score/failure slots do not match tuning rows")
                require(all(item["status"] in {"score_recorded", "original_candidate_failure", "not_executed_before_tuning_exit"}
                            for item in these), "unknown WME candidate slot outcome")
        if "inner_tuning" in cell:
            require(tuning.get("returned") == [cell["selected_parameters"], cell["inner_tuning"]], "returned saved tuning differs")
        if cell["status"] == "complete":
            require(set(names) == set(contexts), "accepted corrected WME lacks all inner/outer generator uses")
    if cell["status"] == "complete" and cell["model_key"] in {"catalytic_fixed", "catalytic_adaptive"}:
        require(names == ["outer"], "accepted corrected Bayesian catalyst lacks outer proposal usage")
    return {"actual_generation_calls": len(calls), "model_calls": len(models),
            "optimizer_observations": len(telemetry["optimizer_calls"]),
            "tuning_reused": tuning["reused"], "retained_wme_slots": len(tuning["candidate_slots"]),
            "optimizer_recomputed": False, "new_optimizer_acceptance_gate_added": False}


class InputBackend:
    """Expose the exact input-only interface shared with witnessed reconstruction."""

    def __init__(self, science: Any, core: Any, environment: dict[str, Any]) -> None:
        self.science, self.pf = science, core
        self.manifest, self.primary, self.environment = science.manifest, science.primary_config, environment
        self.fitting = __import__("importlib").import_module("src.pipelines.extensions.fitting")

    def feature_spec(self, dataset: str) -> dict[str, Any]:
        return self.science.datasets["metabric" if dataset == "metabric_matched" else dataset]["primary_features"]

    def apply_censor(self, times: Any, events: Any, cutoff: Any) -> Any:
        return self.science.conditions.apply_administrative_censoring(times, events, cutoff)

    def preprocess(self, specification: Any, budget: int, training: Any) -> Any:
        return self.science.preprocessing.ExtensionPreprocessor(specification, budget).fit(training)

    def inner_folds(self, times: Any, events: Any, seed: int) -> Any:
        return self.fitting.repeated_survival_folds(times, events, n_splits=3, n_repeats=1, base_seed=seed, max_time_bins=4)

    def candidates(self, model: str) -> list[dict[str, Any]]:
        return self.fitting.candidates_for(model, self.manifest["run_config"], self.primary)

    def evaluation_inputs(self, tt: Any, ee: Any, vt: Any, ve: Any) -> dict[str, Any]:
        evaluation, pf = self.science.evaluation, self.pf
        try:
            horizons, grid = evaluation.evaluation_horizons_and_grid(tt, ee, self.primary["evaluation"])
            clipped_time, clipped_event = evaluation.administratively_truncate_for_ipcw(vt, ve, float(grid[-1]))
            return {"status": "constructed_without_predictions_or_scores", "horizons": pf.array_witness(horizons),
                    "grid": pf.array_witness(grid), "ipcw_validation_time": pf.array_witness(clipped_time),
                    "ipcw_validation_event": pf.array_witness(clipped_event)}
        except Exception as error:
            return {"status": "original_evaluation_input_rule_failed", "error": {
                "type": f"{type(error).__module__}.{type(error).__qualname__}", "message": str(error)},
                "no_model_prediction_or_score_executed": True}


class BoundLineage:
    """Verify every transparent input role and full retained generator history."""

    def __init__(self, gates: Any, science: Any, pins: Pins, environment: dict[str, Any]) -> None:
        self.gates, self.science, self.pins = gates, science, pins
        roots, definition = gates.roots, gates.documents["definition"]
        self.contracts = import_pinned(roots["contracts"], CONTRACTS, "_mixed_verification_contracts", pins)
        self.pf = import_pinned(roots["preflight_code"] / "preflight_core.py", PREFLIGHT_CORE, "_mixed_verification_preflight", pins)
        require("_reuse_bound_contracts" not in sys.modules and "_reuse_bound_core" not in sys.modules, "reuse namespaces occupied")
        sys.modules["_reuse_bound_contracts"], sys.modules["_reuse_bound_core"] = self.contracts, self.pf
        try:
            self.reuse = import_pinned(roots["reuse_code"] / "reuse_core.py", definition["reuse_sources"]["reuse_core.py"],
                                      "_mixed_verification_reuse", pins)
        finally:
            sys.modules.pop("_reuse_bound_contracts", None)
            sys.modules.pop("_reuse_bound_core", None)
        self.backend = InputBackend(science, self.pf, environment)
        self.rows = [json.loads(line) for line in (roots["context_inventory"] / "contexts.jsonl").read_text().splitlines()]
        self.verify_rows()
        self.complete = self.reuse.CompletePreflight(roots["preflight"], self.rows)
        require(self.complete.manifest == gates.preflight_manifest and self.complete.completion == gates.preflight_completion,
                "preflight bytes/content changed")
        replay = gates.replay_completion
        require([row["context_id"] for row in replay["outcomes"]] == [row["context_id"] for row in self.rows],
                "full ordered independent replay coverage differs")
        self.replay = {row["context_id"]: row for row in replay["outcomes"]}
        self.by_cell: dict[str, list[dict[str, Any]]] = {}
        for row in self.rows:
            self.by_cell.setdefault(row["outer_cell_id"], []).append(row)

    def verify_rows(self) -> None:
        """Independently check 825 outer plus 825 three-fold WME context identities."""
        contracts = self.contracts
        jobs = {job.cell_id: job for job in self.science.jobs}
        expected = {f"{job.cell_id}::{name}" for job in jobs.values() if job.model in contracts.CATALYTIC_MODELS
                    for name in (["outer", "inner_01", "inner_02", "inner_03"] if job.model == "catalytic_wme" else ["outer"])}
        require(len(self.rows) == len(expected) == 1650 and {row["context_id"] for row in self.rows} == expected,
                "reconstructed generator context scope differs")
        plan = {row["cell_id"]: row for row in self.science.manifest["plan"]}
        for row in self.rows:
            job, source = jobs[row["outer_cell_id"]], plan[row["outer_cell_id"]]
            ledger = contracts.seed_ledger(job.cell_id)
            inner = row["context"] == "inner"
            name = f"inner_{row['inner_fold']:02d}" if inner else "outer"
            require(row["context_id"] == f"{job.cell_id}::{name}" and row["context"] in {"outer", "inner"}
                    and (not inner or job.model == "catalytic_wme" and row["inner_fold"] in {1, 2, 3}), "context identity differs")
            for name in ("dataset", "setting", "repeat", "fold", "condition", "gene_budget", "model"):
                require(row[name] == getattr(job, name), "context job field differs: " + name)
            require(row["outer_train_sha256_from_manifest"] == source["train_sha256"]
                    and row["outer_validation_sha256_from_manifest"] == source["validation_sha256"]
                    and row["censoring_cutoff_from_manifest"] == job.censoring_cutoff
                    and row["cell_seed"] == ledger["cell"] and row["inner_cv_seed"] == ledger["inner_cv"]
                    and row["generation_seed"] == (ledger["inner_prior"][str(row["inner_fold"])] if inner else ledger["outer_prior"])
                    and row["outer_evaluation_seed"] == ledger["evaluation"]
                    and row["original_outer_fit_attempt_seeds"] == ledger["outer_fit_attempts"][:1 if job.model == "catalytic_wme" else 3],
                    "context membership/censoring/seed ledger differs")
            subset = self.contracts.deterministic_seed(ledger["base_seed"], "robustness_subset", job.dataset, job.repeat, job.fold) if job.condition.startswith("fraction_") else None
            require(row["base_seed"] == ledger["base_seed"]
                    and row["outer_split_seed"] == ledger["base_seed"] + 1009 * (job.repeat - 1)
                    and row["robustness_subset_seed"] == subset, "declared original split/subset seed differs")
            if inner:
                require(row["inner_split_seed"] == ledger["inner_cv"] and row["shared_tau_candidate_uses"] == [
                    {"candidate_index_zero_based": ci, "tau_multiplier": value, "inner_fit_seed": ledger["inner_fit"][f"{row['inner_fold']}:{ci}"]}
                    for ci, value in enumerate((0.25, 1.0, 4.0))], "WME shared proposal candidate uses differ")

    def context(self, row: dict[str, Any], job: Any) -> dict[str, Any]:
        """Read all attempts and independently reconstruct training-only witnesses."""
        directory, record = self.complete.context(row)
        self.pins.bind(directory / "receipt.json", self.complete.lookup[row["context_id"]]["receipt_sha256"])
        self.pins.artifacts(directory, record["artifacts"])
        replay_item = self.replay[row["context_id"]]
        replay_path = child(self.gates.roots["witness_root"], replay_item["receipt_path"])
        replay = self.pins.json(replay_path, replay_item["receipt_sha256"])
        require(replay["content_sha256"] == replay_item["receipt_content_sha256"]
                and replay["context_id"] == row["context_id"] and replay["status"] == "independent_original_first_draw_verified"
                and replay["request"]["definition_content_sha256"] == self.gates.documents["definition"]["content_sha256"],
                "first-draw normal import replay binding differs")
        self.pins.artifacts(replay_path.parent, replay["artifacts"])
        inputs, error = None, None
        try:
            inputs = self.pf.build_context(row, job, self.science.cohorts[job.dataset], self.backend)
        except self.pf.InvalidCheckpoint:
            raise
        except Exception as caught:
            error = self.pf.error_record(caught)
        if inputs is None:
            require(record["status"] == "input_failure" and error is not None
                    and all(record["input_error"][key] == error[key] for key in ("type", "message")),
                    "current real input failure differs from frozen context")
        else:
            saved = self.pins.json(directory / "input.json", record["artifacts"]["input.json"]["sha256"])
            require(saved["input_witness"] == inputs.witness, "current full real context differs")
            arrays = self.pf.read_arrays(directory / "inputs.npz")
            actual = {"real_design": inputs.design, "real_time": inputs.time, "real_event": inputs.event}
            require(set(arrays) == set(actual) and all(self.pf.array_witness(arrays[key]) == self.pf.array_witness(value)
                                                      for key, value in actual.items()), "recorded actual real arrays differ")
        expected_replay_request = {"definition_content_sha256": self.gates.documents["definition"]["content_sha256"],
            "context_id": row["context_id"], "context_row_sha256": canonical(row),
            "original_generation_seed": row["generation_seed"],
            "preflight_receipt_sha256": sha(directory / "receipt.json"),
            "input_witness_sha256": None if inputs is None else canonical(inputs.witness)}
        require(replay["request"] == expected_replay_request, "independent normal-source replay request differs from actual context/input/seed/receipt")
        assessment = self.reuse.compare_first_draw(record, replay["original_replay"], None if inputs is None else inputs.witness)
        require(assessment == replay["assessment"], "original first-draw assessment differs")
        return {"record": record, "replay": replay["original_replay"], "receipt_sha256": sha(directory / "receipt.json"),
                "preflight_receipt_path": str((directory / "receipt.json").relative_to(self.gates.roots["preflight"]))}

    def verify(self, job: Any, entry: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
        """Rebuild nineteen/twenty-one/forty-two roles, then recompute pure decision."""
        path = child(self.gates.roots["witness_root"], entry["input_witness_path"])
        witness = self.pins.json(path, entry["input_witness_sha256"])
        require(witness["definition_content_sha256"] == self.gates.documents["definition"]["content_sha256"]
                and witness["original_cell_id"] == job.cell_id and witness["model"] == job.model, "input witness identity differs")
        self.pins.artifacts(path.parent, witness["proof_artifacts"])
        ledger = self.contracts.seed_ledger(job.cell_id)
        context = self.reuse.reconstruction_inputs(job, self.science.cohorts[job.dataset], self.backend, ledger)
        scope = {"original_cell_id": job.cell_id, "model": job.model, "setting": job.setting,
                 "gene_budget": job.gene_budget, "n_train": len(job.train), "p": context["p"]}
        require(witness["selection_scope"] == entry["selection_scope"] == scope, "pilot selection input dimensions differ")
        header = {"schema_version": 1, "dataset": job.dataset, "setting": job.setting, "model_key": job.model,
                  "repeat": job.repeat, "fold": job.fold, "condition": job.condition, "seed": ledger["cell"],
                  "train_subject_ids": context["training"].subject_id.tolist(),
                  "validation_subject_ids": context["validation"].subject_id.tolist(),
                  "training_membership_sha256": canonical(context["training"].subject_id.tolist()),
                  "n_train": len(context["training"]), "n_validation": len(context["validation"]),
                  "events_train": int(context["ee"].sum()), "censoring_cutoff": job.censoring_cutoff,
                  "gene_budget": job.gene_budget}
        require(witness["stored_cell_header_expected"] == header, "complete independently reconstructed cell header differs")
        contexts = {("outer" if row["context"] == "outer" else f"inner_{row['inner_fold']:02d}"): self.context(row, job)
                    for row in self.by_cell.get(job.cell_id, [])}
        generators = {name: (value["record"], value["replay"]) for name, value in contexts.items()}
        values = self.reuse.make_role_values(job, context, self.backend, generators)
        carrier = witness["fit_witness"]
        require(carrier["original_seeds"] == carrier["corrected_seeds"] == ledger
                and carrier["correction_specification_sha256"] == self.gates.documents["definition"]["content_sha256"]
                and set(carrier["roles"]) == set(values), "exact complete seed/role surface differs")
        for role, (before, after) in values.items():
            relative = f"roles/{role}.json"
            proof = self.pins.json(child(path.parent, relative), witness["proof_artifacts"][relative]["sha256"])
            comparison = carrier["roles"][role]
            require(proof["role"] == role and proof["original_cell_id"] == job.cell_id
                    and proof["definition_content_sha256"] == witness["definition_content_sha256"]
                    and proof["original"] == before and proof["corrected"] == after
                    and proof["original_sha256"] == comparison["original_sha256"] == canonical(before)
                    and proof["corrected_sha256"] == comparison["corrected_sha256"] == canonical(after)
                    and comparison["proof_receipt_sha256"] == sha(child(path.parent, relative)), "reconstructed role proof differs: " + role)
        expected_generators = {name: ["accepted" if value["record"]["status"] in self.reuse.ACCEPTED else value["record"]["status"],
                                      value["receipt_sha256"]] for name, value in contexts.items()}
        require(carrier["generator_contexts"] == witness["fit_witness"]["generator_contexts"] == expected_generators
                and record["generator_contexts"] == expected_generators and record["original_seed_namespace"] == ledger,
                "actual generator scope/seed bindings differ")
        recorded_evidence = record["source_evidence"]
        evidence = recorded_evidence
        if evidence is None:
            require(record["operation"] == "retain_corrected_input_failure" and job.cell_id in self.gates.resolutions,
                    "pending-origin input-failure envelope needs later reviewed finished source snapshot")
            resolution = self.gates.resolutions[job.cell_id]
            snapshot_path = child(self.gates.roots["witness_root"], resolution["snapshot_path"])
            snapshot = self.pins.json(snapshot_path, resolution["snapshot_sha256"])
            require(snapshot["original_cell_id"] == job.cell_id and snapshot["input_witness_sha256"] == entry["input_witness_sha256"]
                    and snapshot["definition_content_sha256"] == witness["definition_content_sha256"]
                    and snapshot["original_claim_active"] is False, "later finished-source snapshot binds different inputs")
            self.pins.artifacts(path.parent, snapshot["artifacts"])
            evidence = snapshot["source_evidence"]
        require(evidence is not None, "completed view awaits missing original outcome proof")
        # The acquisition receipt is separately byte-bound and retains original
        # finished ownership, saved cells, trace/tuning evidence. Deep science is
        # independently recomputed by the caller, never inherited from it.
        candidates = self.backend.candidates(job.model)
        source_receipt_path = path.parent / "source_snapshots" / f"{evidence['verification_receipt_sha256']}.json"
        if not source_receipt_path.exists():
            matching = [item for item in (path.parent / "source_snapshots").glob("*.json")
                        if sha(item) == evidence["verification_receipt_sha256"]]
            require(len(matching) == 1, "source acquisition receipt is missing/ambiguous")
            source_receipt_path = matching[0]
        acquisition = self.pins.json(source_receipt_path, evidence["verification_receipt_sha256"])
        require(acquisition["original_cell_id"] == job.cell_id and acquisition["status"] == "original_outcome_bytes_verified"
                and acquisition["cell_byte_sha256"] == evidence["cell_byte_sha256"]
                and acquisition["cell_content_sha256"] == evidence["cell_content_sha256"]
                and acquisition["definition_content_sha256"] == witness["definition_content_sha256"]
                and acquisition["original_claim_present"] is False, "source acquisition receipt is not finished exact evidence")
        saved_cell = acquisition["saved_cell"]
        require(saved_cell["cell_content_sha256"] == acquisition["cell_content_sha256"]
                == canonical({key: value for key, value in saved_cell.items() if key != "cell_content_sha256"})
                and saved_cell["status"] == evidence["status"]
                and acquisition["referenced_trace_sha256"] == evidence["referenced_trace_sha256"]
                and acquisition["unreferenced_trace_sha256"] == evidence["unreferenced_trace_sha256"],
                "source acquisition saved content/status/trace accounting differs")
        tuning = self.reuse.verify_tuning(acquisition["saved_cell"], candidates)
        require(tuning == acquisition["tuning"] and (job.model != "catalytic_wme"
                or tuning["combined_record_sha256"] == evidence["wme_tuning_record_sha256"]), "source tuning receipt differs")
        fit = self.contracts.FitWitness(job.cell_id, job.model, witness["definition_content_sha256"],
            carrier["original_seeds"], carrier["corrected_seeds"],
            {name: self.contracts.Comparison(**value) for name, value in carrier["roles"].items()},
            {name: tuple(value) for name, value in carrier["generator_contexts"].items()},
            None if recorded_evidence is None else self.contracts.SourceEvidence(**recorded_evidence))
        decision = self.contracts.classify(fit)
        require(record["decision"] == decision and not decision["missing_roles"], "actual complete reconstructed decision differs")
        return {"decision": decision, "witness": witness, "contexts": contexts, "candidates": candidates,
                "original_source_evidence": evidence,
                "ledger": ledger, "summary": {"status": "independently_reconstructed_complete_input_roles",
                    "role_count": len(values), "changed_roles": decision["changed_roles"],
                    "selection_scope": scope, "generator_contexts": expected_generators,
                    "generator_statuses": {name: value["record"]["status"] for name, value in contexts.items()},
                    "original_first_draw_normal_import_receipts_bound": True,
                    "original_source_resolution": "record_bound_finished_source" if recorded_evidence is not None else
                        "separate_later_reviewed_source_snapshot; earlier_pending_envelope_unchanged",
                    "original_source_evidence": evidence,
                    "rank_decisions": "bound_reviewed_preflight_evidence; not_recomputed_by_verifier",
                    "new_proposals_optimizer_fit_or_selection_executed": False},
                "terminal_header": witness["stored_cell_header_expected"]}

    def validate_pilot_scope(self, entries: list[dict[str, Any]]) -> None:
        """Check dimensions/input completeness independent of original availability."""
        actual = self.reuse.pilot_input_scope(entries)
        require(actual == self.gates.documents["inventory"]["selection_scope"], "independently reconstructed full changed-input pilot scope differs")
