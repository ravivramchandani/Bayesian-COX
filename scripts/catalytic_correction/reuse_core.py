"""Exact witnessed input comparisons and immutable original-outcome acquisition.

The CLI injects byte-pinned preparation modules. No scientific ``src`` module
is imported here, and no generator, model or scoring function is invoked here.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

import _reuse_bound_contracts as contracts
import _reuse_bound_core as pf

ACCEPTED = {"accepted_original_first_draw", "accepted_rank_conditioned_redraw"}
NUMERIC_KEYS = {"synthetic_design", "synthetic_time", "hazard", "time_scale"}


def require(condition: bool, message: str) -> None:
    """Fail closed on missing, foreign or altered evidence."""
    if not condition:
        raise pf.InvalidCheckpoint(message)


def input_error_value(error: Exception) -> dict[str, str]:
    """Bind exception identity without caller-specific traceback/file locations."""
    return {"type": f"{type(error).__module__}.{type(error).__qualname__}", "message": str(error)}


def checked_path(root: Path, relative: str) -> Path:
    """Resolve an owned relative artifact without following links."""
    value = Path(relative)
    require(not value.is_absolute() and ".." not in value.parts, "unsafe evidence path")
    path = root / value
    require(not any(item.is_symlink() for item in (path, *path.parents)), "linked evidence path")
    return path


def verified_json(path: Path, binding: dict[str, Any] | None = None, *,
                  artifact_root: Path | None = None) -> dict[str, Any]:
    """Check both artifact bytes and the complete canonical JSON envelope."""
    if binding is not None:
        require(pf.artifact_binding(path) == binding, "JSON artifact bytes differ")
    value = pf.read_sealed(path)
    pf.verify_artifacts(path.parent if artifact_root is None else artifact_root, value)
    return value


def numeric_archive(path: Path, binding: dict[str, Any], witnesses: dict[str, Any],
                    keys: set[str]) -> dict[str, np.ndarray]:
    """Load exact numeric keys only after a complete byte hash check."""
    require(pf.artifact_binding(path) == binding, "numeric archive bytes differ")
    arrays = pf.read_arrays(path)
    require(set(arrays) == keys, "numeric archive keys differ")
    require({key: pf.array_witness(value) for key, value in arrays.items()} == witnesses,
            "numeric archive dtype/shape/element bytes differ")
    return arrays


class CompletePreflight:
    """Verify every scheduled context, including rejected and unreached inputs."""

    def __init__(self, root: Path, rows: list[dict[str, Any]], *, expected_count: int = 1650) -> None:
        self.root, self.rows = root, rows
        self.manifest = verified_json(root / "manifest.json")
        self.completion = verified_json(root / "completion.json")
        complete = self.completion
        require(complete["status"] == "all_scheduled_contexts_accounted"
                and complete["scheduled_contexts"] == complete["accounted_contexts"] == expected_count
                and len(rows) == expected_count, "full preflight coverage is required")
        require(complete["run_binding_sha256"] == self.manifest["content_sha256"],
                "preflight completion belongs to another manifest")
        entries = complete["outcomes"]
        require([item["context_id"] for item in entries] == [row["context_id"] for row in rows],
                "complete ordered context inventory differs")
        self.lookup = {item["context_id"]: item for item in entries}
        require(len(self.lookup) == expected_count, "duplicate preflight contexts")

    def context(self, row: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
        """Check one complete context and all retained proposal archives."""
        item = self.lookup[row["context_id"]]
        path = checked_path(self.root, item["receipt_path"])
        record = verified_json(path)
        require(pf.sha256_file(path) == item["receipt_sha256"]
                and record["content_sha256"] == item["receipt_content_sha256"]
                and record["status"] == item["status"], "context completion binding differs")
        request = record["request"]
        require(request["context_id"] == row["context_id"]
                and request["context_row_sha256"] == pf.canonical_hash(row)
                and request["original_generation_seed"] == row["generation_seed"]
                and request["run_binding_sha256"] == self.manifest["content_sha256"],
                "context original request differs")
        attempts = record["attempts"]
        actual_dirs = {item.name for item in path.parent.glob("attempt_*")}
        require(actual_dirs == {f"attempt_{index:03d}" for index in range(len(attempts))},
                "extra or missing proposal directories")
        if record["status"] == "input_failure":
            require(not attempts and record["accepted_attempt_index"] is None
                    and not record["artifacts"], "input failure contains invented proposals")
            return path.parent, record
        require(1 <= len(attempts) <= request["candidate_cap"] == 256,
                "invalid proposal count or cap")
        saved_input = verified_json(path.parent / "input.json", record["artifacts"]["input.json"])
        require(saved_input["request"] == request
                and pf.canonical_hash(saved_input["input_witness"]) == request["input_witness_sha256"],
                "preflight training witness differs")
        real_witnesses = {"real_design": saved_input["input_witness"]["real_design"],
                          "real_time": saved_input["input_witness"]["training_time"],
                          "real_event": saved_input["input_witness"]["training_event"]}
        numeric_archive(path.parent / "inputs.npz", record["artifacts"]["inputs.npz"],
                        real_witnesses, set(real_witnesses))
        for index, attempt in enumerate(attempts):
            expected_seed = row["generation_seed"] if index == 0 else contracts.deterministic_seed(
                row["generation_seed"], "rank_conditioned_retry", index)
            require(attempt["request"] == request and attempt["attempt_index"] == index
                    and attempt["seed"] == expected_seed, "attempt index/request/seed differs")
            prefix = f"attempt_{index:03d}"
            saved = verified_json(path.parent / prefix / "receipt.json",
                                  record["artifacts"][f"{prefix}/receipt.json"])
            require(saved == attempt, "attempt/context history differs")
            if index < len(attempts) - 1:
                require(attempt["status"] == "frozen_rank_rejected", "retry followed nonrank outcome")
            if attempt["status"] == "nonrank_error":
                require(not attempt["artifacts"] and attempt["constructor_inputs"] is None,
                        "nonrank attempt contains fabricated constructor")
            else:
                require(attempt["status"] in {"accepted_original_constructor", "frozen_rank_rejected"},
                        "unknown constructor outcome")
                numeric_archive(path.parent / prefix / "proposal.npz",
                                attempt["artifacts"]["proposal.npz"], attempt["array_witnesses"], NUMERIC_KEYS)
        accepted = record["accepted_attempt_index"]
        if record["status"] in ACCEPTED:
            require(accepted == len(attempts) - 1 and attempts[-1]["status"] == "accepted_original_constructor"
                    and (record["status"] == "accepted_original_first_draw") == (accepted == 0),
                    "accepted proposal accounting differs")
        elif record["status"] == "exhausted_rank_cap":
            require(accepted is None and len(attempts) == 256
                    and all(a["status"] == "frozen_rank_rejected" for a in attempts), "rank exhaustion differs")
        elif record["status"] == "nonrank_failure":
            require(accepted is None and attempts[-1]["status"] == "nonrank_error", "nonrank accounting differs")
        else:
            raise pf.InvalidCheckpoint("unknown preflight context status")
        metadata = record["candidate_metadata"]
        if metadata is not None:
            require(metadata["proposal_metadata_sha256"] == pf.canonical_hash({
                key: value for key, value in metadata.items() if key != "proposal_metadata_sha256"})
                and metadata["original_seed"] == row["generation_seed"]
                and metadata["accepted_attempt_index"] == accepted
                and metadata["attempts_generated"] == len(attempts) and metadata["attempt_cap"] == 256,
                "candidate complete history differs")
        return path.parent, record


def compare_first_draw(preflight: dict[str, Any], replay: dict[str, Any],
                       reconstructed_witness: dict[str, Any] | None) -> dict[str, Any]:
    """Require independent full proposal identity, including original failures."""
    if preflight["status"] == "input_failure":
        require(replay["status"] == "input_failure"
                and replay["error"]["type"] == preflight["input_error"]["type"]
                and replay["error"]["message"] == preflight["input_error"]["message"],
                "independent original input failure differs")
        return {"status": "exact_original_input_failure", "generator_called": False,
                "full_constructor_identity_witnessed": False}
    require(reconstructed_witness is not None, "constructed context witness missing")
    first = preflight["attempts"][0]
    require(replay["status"] == first["status"], "independent first constructor outcome differs")
    require(replay["seed"] == first["seed"], "independent first draw seed differs")
    require(replay["processor_metadata"] == reconstructed_witness["processor_metadata"],
            "independent original learned processor differs")
    if first["status"] == "nonrank_error":
        require(replay["error"]["type"] == first["error"]["type"]
                and replay["error"]["message"] == first["error"]["message"],
                "independent nonrank exception differs")
        return {"status": "exact_original_nonrank_error", "generator_called": True,
                "full_constructor_identity_witnessed": False}
    require(replay["array_witnesses"] == first["array_witnesses"],
            "independent normal-import first proposal design/time/hazard/scale differs")
    require(replay["legacy_metadata"] == first["legacy_metadata"],
            "independent original returned metadata or its absence differs")
    require(replay["processor_metadata"] == first["actual_metadata"]["processor_metadata"],
            "independent original vs proposal-child processor differs")
    require(first["status"] != "frozen_rank_rejected" or replay["legacy_metadata"] is None,
            "rejected original constructor has fabricated legacy metadata")
    return {"status": "exact_normal_import_first_proposal_identity", "generator_called": True,
            "full_constructor_identity_witnessed": True,
            "constructor_result": first["status"], "metadata_basis": "actual_returned_or_original_absence",
            "arrays_basis": "dtype_shape_and_exact_C_order_element_bytes_not_only_legacy_JSON_hash"}


def full_frame_witness(frame: Any) -> dict[str, Any]:
    """Bind all raw columns, their order, dtypes, values and ordered row index."""
    value = pf.source_frame_witness(frame, list(frame.columns))
    value["index"] = {"dtype": str(frame.index.dtype),
                      "values_sha256": pf.canonical_hash([pf.scalar_tag(v) for v in frame.index.tolist()])}
    return value


def outcome_witness(time: np.ndarray, event: np.ndarray) -> dict[str, Any]:
    """Bind exact censored outcomes without calculating any score."""
    return {"time": pf.array_witness(time), "event": pf.array_witness(event)}


def reconstruction_inputs(job: Any, raw: Any, backend: Any, ledger: dict[str, Any]) -> dict[str, Any]:
    """Build original fit/evaluation inputs; heldout data never reach a generator."""
    training, validation = raw.iloc[job.train], raw.iloc[job.validation]
    ids, heldout_ids = training.subject_id.tolist(), validation.subject_id.tolist()
    require(not set(ids) & set(heldout_ids), "training/heldout membership overlaps")
    tt, ee = backend.apply_censor(raw.duration.to_numpy(float)[job.train],
                                  raw.event.to_numpy(int)[job.train], job.censoring_cutoff)
    vt, ve = backend.apply_censor(raw.duration.to_numpy(float)[job.validation],
                                  raw.event.to_numpy(int)[job.validation], job.censoring_cutoff)
    base = {"job_and_censoring": {"cell_id": job.cell_id, "dataset": job.dataset, "setting": job.setting,
            "model": job.model, "repeat": job.repeat, "fold": job.fold, "condition": job.condition,
            "censoring_cutoff": job.censoring_cutoff, "train_indices": pf.array_witness(job.train),
            "validation_indices": pf.array_witness(job.validation)},
            "ordered_raw_training": {"subject_ids": ids, "frame": full_frame_witness(training)},
            "ordered_raw_validation": {"subject_ids": heldout_ids, "frame": full_frame_witness(validation)},
            "feature_spec_and_gene_budget": {"feature_spec": backend.feature_spec(job.dataset),
                                               "gene_budget": job.gene_budget},
            "training_outcomes": outcome_witness(tt, ee), "validation_outcomes": outcome_witness(vt, ve)}
    context = {"training": training, "validation": validation, "tt": tt, "ee": ee,
               "vt": vt, "ve": ve, "base_roles": base, "inner": [], "p": None,
               "generator_training_contexts": {}, "candidates": backend.candidates(job.model)}
    if int(ee.sum()) < 20:
        context["input_error"] = {"type": "builtins.ValueError",
                                  "message": "fewer than 20 training events under frozen information-regime rule"}
        return context
    try:
        processor = backend.preprocess(backend.feature_spec(job.dataset), job.gene_budget, training)
        xt, xv = processor.transform(training).to_numpy(float), processor.transform(validation).to_numpy(float)
    except Exception as error:
        context["input_error"] = input_error_value(error)
        return context
    context.update(processor=processor, xt=xt, xv=xv, p=xt.shape[1])
    context["generator_training_contexts"]["outer"] = {"training": training, "processor": processor,
                                                     "time": tt, "event": ee}
    base.update(preprocessing_state=processor.metadata(),
                encoded_training={"feature_names": list(processor.feature_names), "design": pf.array_witness(xt)},
                encoded_validation={"feature_names": list(processor.feature_names), "design": pf.array_witness(xv)})
    context["outer_evaluation_inputs"] = backend.evaluation_inputs(tt, ee, vt, ve)
    candidates = context["candidates"]
    if len(candidates) > 1:
        folds = backend.inner_folds(tt, ee, ledger["inner_cv"])
        require(len(folds) == 3 and {fold.fold for fold in folds} == {1, 2, 3}, "tuning inner coverage differs")
        for fold in folds:
            require(fold.seed == ledger["inner_cv"], "tuning splitter seed differs")
            tr, va = fold.train_indices, fold.validation_indices
            it, iv = training.iloc[tr], training.iloc[va]
            require(not set(it.subject_id) & (set(iv.subject_id) | set(heldout_ids)),
                    "inner preprocessing contains heldout rows")
            record = {"fold": fold.fold, "train_indices": pf.array_witness(tr),
                      "validation_indices": pf.array_witness(va),
                      "ordered_training_ids": it.subject_id.tolist(), "ordered_validation_ids": iv.subject_id.tolist(),
                      "raw_training": full_frame_witness(it), "raw_validation": full_frame_witness(iv),
                      "training_outcomes": outcome_witness(tt[tr], ee[tr]),
                      "validation_outcomes": outcome_witness(tt[va], ee[va])}
            try:
                inner_processor = backend.preprocess(backend.feature_spec(job.dataset), job.gene_budget, it)
                record.update(processor_metadata=inner_processor.metadata(),
                              feature_names=list(inner_processor.feature_names),
                              encoded_training=pf.array_witness(inner_processor.transform(it).to_numpy(float)),
                              encoded_validation=pf.array_witness(inner_processor.transform(iv).to_numpy(float)),
                              evaluation_inputs=backend.evaluation_inputs(tt[tr], ee[tr], tt[va], ee[va]))
                context["generator_training_contexts"][f"inner_{fold.fold:02d}"] = {
                    "training": it, "processor": inner_processor, "time": tt[tr], "event": ee[tr]}
            except Exception as error:
                record["unreachable_input_error"] = input_error_value(error)
            record["candidate_slots"] = [{"fold": fold.fold, "candidate_index_zero_based": index,
                "parameters": candidate, "inner_fit_seed": contracts.deterministic_seed(
                    ledger["inner_cv"], "inner_fit", fold.fold, index),
                "input_only_no_fit_prediction_score_or_selection_executed": True}
                for index, candidate in enumerate(candidates)]
            context["inner"].append(record)
    return context


def source_groups(manifest: dict[str, Any]) -> dict[str, dict[str, str]]:
    """Bind source bytes by role, retaining the complete dependency closure too."""
    values = manifest["input_sha256"]
    return {"model_sources": {key: value for key, value in values.items() if key.startswith("src/models/")},
            "fit_sources": {key: value for key, value in values.items() if key.startswith(("src/pipelines/", "src/data/"))},
            "evaluation_sources": {key: value for key, value in values.items() if key.startswith(("src/evaluation/", "src/pipelines/confirmatory/evaluation"))},
            "unchanged_execution_dependencies": values}


def proposal_roles(record: dict[str, Any], replay: dict[str, Any]) -> tuple[Any, Any, Any, Any]:
    """Compare independently witnessed first inputs with actual accepted inputs."""
    first = record["attempts"][0] if record["attempts"] else None
    accepted_index = record["accepted_attempt_index"]
    accepted = None if accepted_index is None else record["attempts"][accepted_index]
    original_constructor = {"status": replay["status"], "arrays": replay.get("array_witnesses"),
                            "error": replay.get("error") if replay["status"] in {"input_failure", "nonrank_error"} else None}
    corrected_constructor = {"status": "accepted_original_constructor" if accepted is not None else record["status"],
                             "arrays": None if accepted is None else accepted["array_witnesses"],
                             "error": record.get("input_error") or record.get("nonrank_error") if accepted is None else None}
    original_legacy = {"returned": None if first is None else first.get("legacy_metadata"),
                       "absence_reason": None if first is not None and first.get("legacy_metadata") is not None else replay["status"]}
    corrected_legacy = {"returned": None if accepted is None else accepted.get("legacy_metadata"),
                        "absence_reason": None if accepted is not None and accepted.get("legacy_metadata") is not None else record["status"]}
    return original_constructor, corrected_constructor, original_legacy, corrected_legacy


def common_role_values(job: Any, context: dict[str, Any], backend: Any) -> dict[str, Any]:
    """Expose all nineteen reconstruction-only fit/evaluation input values."""
    original_values = dict(context["base_roles"])
    dependencies = source_groups(backend.manifest)
    original_values.update(dependencies)
    config, primary = backend.manifest["run_config"], backend.primary
    original_values.update(model_configuration={"model": job.model, "extensions": config, "primary": primary["models"]},
        fit_configuration={"sampling": config["sampling"], "primary": primary,
                           "event_guard": "outer_events_at_least20", "attempts": "original_fit_with_attempts"},
        evaluation_configuration={"configuration": primary["evaluation"],
                                  "calibration_bootstraps": config["calibration_bootstraps"],
                                  "actual_inputs": context.get("outer_evaluation_inputs"),
                                  "input_error": context.get("input_error")},
        environment=backend.environment,
        seed_ledger=contracts.seed_ledger(job.cell_id, config["base_seed"]),
        candidate_configuration={"ordered_candidates": context.get("candidates"), "inner_dependencies": context["inner"],
                                 "selection_recipe": "three-inner-fold mean IPCW IBS; stable candidate-order ties",
                                 "selection_execution": "not_invoked; actual saved record checked separately"})
    if "input_error" in context:
        for name in ("preprocessing_state", "encoded_training", "encoded_validation"):
            original_values.setdefault(name, {"unreachable": context["input_error"],
                                             "recipe_dependencies": dependencies["unchanged_execution_dependencies"]})
    require(set(original_values) == set(contracts.COMMON_ROLES), "common role surface is not exactly19")
    return original_values


def make_role_values(job: Any, context: dict[str, Any], backend: Any,
                     generator_records: dict[str, tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, tuple[Any, Any]]:
    """Produce all exact common/catalytic/WME comparison values, not hash claims."""
    dependencies = source_groups(backend.manifest)
    config, primary = backend.manifest["run_config"], backend.primary
    values = {key: (value, value) for key, value in common_role_values(job, context, backend).items()}
    if job.model in contracts.CATALYTIC_MODELS:
        before, after, old_legacy, new_legacy = proposal_roles(*generator_records["outer"])
        values["outer.synthetic_constructor"] = before, after
        values["outer.legacy_metadata_or_absence"] = old_legacy, new_legacy
    if job.model == "catalytic_wme":
        by_fold = {item["fold"]: item for item in context["inner"]}
        for fold in range(1, 4):
            name = f"inner_{fold:02d}"
            before, after, old_legacy, new_legacy = proposal_roles(*generator_records[name])
            inner = by_fold.get(fold, {"unreachable": context.get("input_error"),
                                      "source_and_input_bound_recipe": dependencies["unchanged_execution_dependencies"]})
            prefix = f"inner.{fold}."
            common = {
                "memberships_and_raw_values": {key: inner.get(key) for key in
                    ("train_indices", "validation_indices", "ordered_training_ids", "ordered_validation_ids", "raw_training", "raw_validation", "unreachable", "source_and_input_bound_recipe")},
                "training_and_validation_outcomes": {key: inner.get(key) for key in ("training_outcomes", "validation_outcomes", "unreachable")},
                "preprocessing_state": {key: inner.get(key) for key in ("processor_metadata", "unreachable_input_error", "unreachable")},
                "encoded_training_and_validation": {key: inner.get(key) for key in ("feature_names", "encoded_training", "encoded_validation", "unreachable_input_error", "unreachable")},
            }
            for role, value in common.items():
                values[prefix + role] = value, value
            values[prefix + "synthetic_constructor"] = before, after
            values[prefix + "legacy_metadata_or_absence"] = old_legacy, new_legacy
            candidate_base = {"inner_inputs": inner, "source_dependencies": dependencies,
                              "configuration": config, "primary": primary,
                              "candidate_count": 3, "candidate_order": [0.25, 1.0, 4.0]}
            values[prefix + "candidate_model_fit_evaluation_inputs"] = (
                {**candidate_base, "synthetic_constructor": before},
                {**candidate_base, "synthetic_constructor": after})
    require(set(values) == set(contracts.required_roles(job.model)), "role surface is not exactly19/21/42")
    return values


def write_role_witness(directory: Path, definition: str, job: Any, context: dict[str, Any],
                       values: dict[str, tuple[Any, Any]], generators: dict[str, Any]) -> dict[str, Any]:
    """Seal transparent role values and exact reconstruction proof receipts."""
    roles, proofs = {}, {}
    for role, (original, corrected) in values.items():
        proof = pf.seal({"schema_version": 1, "original_cell_id": job.cell_id,
            "definition_content_sha256": definition, "role": role,
            "basis": "exact_reconstruction", "original": original, "corrected": corrected,
            "original_sha256": contracts.digest(original), "corrected_sha256": contracts.digest(corrected),
            "claim": "actual_pinned_source_reconstruction_and_byte_witnesses; original arrays not presumed stored"})
        relative = f"roles/{role}.json"
        path = checked_path(directory, relative)
        if path.exists():
            require(verified_json(path) == proof, "existing exact role witness differs")
        else:
            pf.write_json_new(path, proof)
        binding = pf.artifact_binding(path)
        proofs[relative] = binding
        roles[role] = asdict(contracts.Comparison(proof["original_sha256"], proof["corrected_sha256"],
                                                 binding["sha256"], "exact_reconstruction"))
    selection_scope = {"original_cell_id": job.cell_id, "model": job.model, "setting": job.setting,
                       "gene_budget": job.gene_budget, "n_train": len(job.train), "p": context["p"]}
    fit_witness = {"original_cell_id": job.cell_id, "model": job.model,
        "correction_specification_sha256": definition,
        "original_seeds": contracts.seed_ledger(job.cell_id), "corrected_seeds": contracts.seed_ledger(job.cell_id),
        "roles": roles, "generator_contexts": generators, "original_evidence": None}
    wme_slots = []
    if job.model == "catalytic_wme":
        require(len(context["candidates"]) == 3, "WME ordered three candidates missing")
        by_fold = {record["fold"]: record for record in context["inner"]}
        for fold in range(1, 4):
            for index, parameters in enumerate(context["candidates"]):
                wme_slots.append({"fold": fold, "candidate_index_zero_based": index, "parameters": parameters,
                    "inner_fit_seed": contracts.seed_ledger(job.cell_id)["inner_fit"][f"{fold}:{index}"],
                    "shared_generator_context": f"inner_{fold:02d}",
                    "dependency_status": "constructed_input_only" if fold in by_fold and
                        "unreachable_input_error" not in by_fold[fold] else "unreachable_input_recipe_retained",
                    "original_candidate_result": "separate_saved_original_tuning_acquisition_required",
                    "corrected_candidate_result": "not_executed_by_builder"})
    value = pf.seal({"schema_version": 1, "original_cell_id": job.cell_id, "model": job.model,
        "dataset": job.dataset, "setting": job.setting, "definition_content_sha256": definition,
        "selection_scope": selection_scope, "fit_witness": fit_witness,
        "all_wme_candidate_slots": wme_slots,
        "proof_artifacts": proofs, "artifacts": proofs, "fit_dispatched": False,
        "stored_cell_header_expected": {"schema_version": 1, "dataset": job.dataset, "setting": job.setting,
            "model_key": job.model, "repeat": job.repeat, "fold": job.fold, "condition": job.condition,
            "seed": contracts.seed_ledger(job.cell_id)["cell"],
            "train_subject_ids": context["training"].subject_id.tolist(),
            "validation_subject_ids": context["validation"].subject_id.tolist(),
            "training_membership_sha256": pf.canonical_hash(context["training"].subject_id.tolist()),
            "n_train": len(context["training"]), "n_validation": len(context["validation"]),
            "events_train": int(context["ee"].sum()), "censoring_cutoff": job.censoring_cutoff,
            "gene_budget": job.gene_budget},
        "scope": "actual_reconstructed_input_proofs_only; no_model_or_evaluation_execution"})
    path = checked_path(directory, "input_witness.json")
    if path.exists():
        require(verified_json(path) == value, "sealed input witness differs")
    else:
        pf.write_json_new(path, value)
    return value


def checked_trace(path: Path) -> dict[str, Any]:
    """Stream-check immutable trace bytes and detect writes during acquisition."""
    require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), "missing/linked original trace")
    before = path.stat()
    value = pf.artifact_binding(path)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "original trace changed while hashing")
    return value


def verify_tuning(cell: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate an existing original selection without computing fresh scores."""
    selected, tuning = cell.get("selected_parameters"), cell.get("inner_tuning")
    if selected is None or tuning is None:
        require(selected is None and tuning is None, "partial saved original tuning record")
        return {"available": False, "selected_parameters": None, "inner_tuning": None,
                "combined_record_sha256": None}
    require(selected in candidates, "saved selected parameters are outside frozen candidate ordering")
    if len(candidates) == 1:
        require(selected == candidates[0] and tuning == {"tuned": False, "candidates": []},
                "saved untuned selection differs")
    else:
        rows = tuning.get("candidates", [])
        require(tuning.get("tuned") is True and len(rows) == len(candidates)
                and [row["parameters"] for row in rows] == candidates, "saved tuning candidate ordering differs")
        eligible = []
        for index, row in enumerate(rows):
            scores = row["scores"]
            require(len(scores) <= 3 and len(scores) + len(row["failures"]) == 3,
                    "saved tuning does not account for three folds")
            expected = float(np.mean(scores)) if len(scores) == 3 else None
            require(row["mean_ibs"] == expected, "saved original mean IBS differs")
            if expected is not None:
                require(np.isfinite(expected), "saved tuning mean is nonfinite")
                eligible.append(index)
        require(bool(eligible), "saved tuning has no eligible original candidate")
        chosen = min(eligible, key=lambda index: (rows[index]["mean_ibs"], index))
        require(tuning["selected_index"] == chosen and selected == candidates[chosen]
                and tuning["selection"] == "three-inner-fold mean IPCW IBS; stable candidate-order ties",
                "saved original stable selection differs")
    combined = {"selected_parameters": selected, "inner_tuning": tuning}
    return {"available": True, **combined, "combined_record_sha256": contracts.digest(combined)}


def original_snapshot(run: Path, cell_id: str, manifest_sha: str,
                      candidates: list[dict[str, Any]]) -> dict[str, Any]:
    """Acquire original bytes/traces or preserve a pending owner's claim."""
    claim_path = checked_path(run, f"claims/{cell_id}.json")
    cell_path = checked_path(run, f"cells/{cell_id}.json")
    claim_binding = pf.artifact_binding(claim_path) if claim_path.exists() else None
    if claim_binding is not None:
        return {"status": "await_original_owner", "original_claim_present": True,
                "claim_artifact": claim_binding, "cell_exists": cell_path.exists(),
                "source_evidence": None, "tuning": None, "artifacts": {}}
    if not cell_path.exists():
        return {"status": "await_original_outcome", "original_claim_present": False,
                "cell_exists": False, "source_evidence": None, "tuning": None, "artifacts": {}}
    before = pf.artifact_binding(cell_path)
    cell = json.loads(cell_path.read_text())
    require(cell["cell_id"] == cell_id and cell["status"] in contracts.OUTCOME_STATUSES,
            "original cell identity/status differs")
    require(cell["cell_content_sha256"] == pf.canonical_hash({
        key: value for key, value in cell.items() if key != "cell_content_sha256"}), "original cell canonical content differs")
    referenced, orphans, trace_bindings = {}, {}, {}
    trace_root = checked_path(run, f"traces/{cell_id}")
    observed = sorted(path.name for path in trace_root.iterdir()) if trace_root.exists() else []
    for attempt in cell.get("fit_attempts", []):
        for trace in attempt.get("traces", {}).values():
            name = trace["filename"]
            require(Path(name).name == name and f"traces/{cell_id}/{name}" not in referenced,
                    "unsafe/duplicate original trace name")
            value = checked_trace(trace_root / name)
            require(value["sha256"] == trace["sha256"], "referenced original trace bytes differ")
            relative = f"traces/{cell_id}/{name}"
            referenced[relative], trace_bindings[relative] = value["sha256"], value
    for name in observed:
        if f"traces/{cell_id}/{name}" not in referenced:
            value = checked_trace(trace_root / name)
            relative = f"traces/{cell_id}/{name}"
            orphans[relative], trace_bindings[relative] = value["sha256"], value
    require(observed == (sorted(path.name for path in trace_root.iterdir()) if trace_root.exists() else [])
            and pf.artifact_binding(cell_path) == before and not claim_path.exists(),
            "original owner/outcome/trace inventory changed during acquisition")
    tuning = verify_tuning(cell, candidates)
    return {"status": "original_outcome_bytes_verified", "original_claim_present": False,
            "cell_exists": True, "cell_byte_sha256": before["sha256"],
            "cell_content_sha256": cell["cell_content_sha256"], "cell_status": cell["status"],
            "original_manifest_sha256": manifest_sha, "referenced_trace_sha256": referenced,
            "unreferenced_trace_sha256": orphans, "trace_bindings": trace_bindings,
            "cell_artifact": before, "tuning": tuning, "saved_cell": cell,
            "source_evidence": "available_after_snapshot_receipt_publication", "artifacts": {}}


def snapshot_decision(directory: Path, definition: str, witness: dict[str, Any],
                      snapshot: dict[str, Any]) -> tuple[dict[str, Any], Path]:
    """Classify after transparent role proofs and fresh original bytes checks."""
    identity = witness["original_cell_id"]
    if snapshot["cell_exists"] and not snapshot["original_claim_present"]:
        validate_saved_input_fields(directory, witness, snapshot["saved_cell"])
    source_path = checked_path(directory, f"source_snapshots/{contracts.digest(snapshot)}.json")
    source = pf.seal({"schema_version": 1, "definition_content_sha256": definition,
                      "original_cell_id": identity, **snapshot})
    if source_path.exists():
        require(verified_json(source_path) == source, "original source acquisition differs")
    else:
        pf.write_json_new(source_path, source)
    evidence = None
    if snapshot["cell_exists"] and not snapshot["original_claim_present"]:
        evidence = contracts.SourceEvidence(identity, snapshot["original_manifest_sha256"],
            snapshot["cell_byte_sha256"], snapshot["cell_content_sha256"], snapshot["cell_status"],
            pf.sha256_file(source_path), snapshot["referenced_trace_sha256"], snapshot["unreferenced_trace_sha256"],
            snapshot["tuning"]["combined_record_sha256"] if witness["model"] == "catalytic_wme" else None)
    carrier = witness["fit_witness"]
    value = contracts.FitWitness(identity, witness["model"], definition, carrier["original_seeds"],
        carrier["corrected_seeds"], {key: contracts.Comparison(**record) for key, record in carrier["roles"].items()},
        {key: tuple(record) for key, record in carrier["generator_contexts"].items()}, evidence)
    decision = contracts.classify(value)
    potential_action = decision["action"]
    dispatch_action = potential_action
    if snapshot["original_claim_present"] or (not snapshot["cell_exists"] and potential_action in
            {"fit_changed_inputs", "fit_changed_inputs_reuse_tuning", "retune_then_fit_changed_inputs"}):
        dispatch_action = "await_original_owner"
    result = pf.seal({"schema_version": 1, "original_cell_id": identity,
        "definition_content_sha256": definition, "input_witness_sha256":
            pf.sha256_file(directory / "input_witness.json"), "action": dispatch_action,
        "potential_action": potential_action, "decision": decision,
        "selection_scope": witness["selection_scope"], "original_claim_active": snapshot["original_claim_present"],
        "source_evidence": None if evidence is None else asdict(evidence),
        "selected_parameters": None if snapshot["tuning"] is None else snapshot["tuning"]["selected_parameters"],
        "inner_tuning": None if snapshot["tuning"] is None else snapshot["tuning"]["inner_tuning"],
        "tuning_record_combined_sha256": None if snapshot["tuning"] is None else snapshot["tuning"]["combined_record_sha256"],
        "artifacts": {str(source_path.relative_to(directory)): pf.artifact_binding(source_path)},
        "artifact_base": "cell_directory",
        "fit_dispatched": False, "method_approved": False, "corrected_freeze_created": False})
    path = checked_path(directory, f"snapshots/{result['content_sha256']}.json")
    if path.exists():
        require(verified_json(path, artifact_root=directory) == result, "existing acquisition/classification differs")
    else:
        pf.write_json_new(path, result)
    return result, path


def validate_saved_input_fields(directory: Path, witness: dict[str, Any], cell: dict[str, Any]) -> None:
    """Cross-check every saved original input field against pinned reconstruction."""
    for name, expected in witness["stored_cell_header_expected"].items():
        require(name in cell and cell[name] == expected, f"saved original header/input differs: {name}")
    if "preprocessing" in cell:
        proof = verified_json(directory / "roles/preprocessing_state.json")
        require(cell["preprocessing"] == proof["original"], "saved original processor state differs")
    if "p" in cell:
        require(cell["p"] == witness["selection_scope"]["p"], "saved original feature dimension differs")
    if "events_per_coefficient" in cell:
        header = witness["stored_cell_header_expected"]
        require(cell["events_per_coefficient"] == float(header["events_train"] / cell["p"]),
                "saved original events-per-coefficient differs")
    if "synthetic_prior_data" in cell:
        proof = verified_json(directory / "roles/outer.legacy_metadata_or_absence.json")
        require(cell["synthetic_prior_data"] == proof["original"]["returned"],
                "saved original synthetic returned metadata differs from independent first draw")
    if "predictions" in cell:
        predictions = cell["predictions"]
        require(predictions["subject_ids"] == witness["stored_cell_header_expected"]["validation_subject_ids"],
                "saved prediction subject order differs")
        for role, fields in (("training_outcomes", ("training_time", "training_event")),
                             ("validation_outcomes", ("observed_time", "observed_event"))):
            proof = verified_json(directory / "roles" / f"{role}.json")
            for logical, name in zip(("time", "event"), fields, strict=True):
                expected = proof["original"][logical]
                array = np.asarray(predictions[name], dtype=np.dtype(expected["dtype"]))
                require(pf.array_witness(array) == expected, f"saved prediction outcome input differs: {name}")
    ledger = witness["fit_witness"]["original_seeds"]
    bayesian = {"bayesian_normal", "bayesian_horseshoe", "bayesian_spike_slab", "pv_horseshoe",
                "catalytic_fixed", "catalytic_adaptive"}
    maximum = 3 if witness["model"] in bayesian else 1
    for index, attempt in enumerate(cell.get("fit_attempts", [])):
        require(index < maximum and attempt["attempt"] == index + 1, "saved fit-attempt ordering differs")
        if "seed" in attempt:
            require(attempt["seed"] == ledger["outer_fit_attempts"][index], "saved fit-attempt seed differs")


def publish_inventory(output: Path, definition: str, preflight_completion: str,
                      replay_completion: str, entries: list[dict[str, Any]], *, expected_cells: int = 1625,
                      arithmetic_selector_sha256: str | None = None) -> Path:
    """Seal a complete versioned view without editing earlier pending snapshots."""
    require(len(entries) == expected_cells and len({entry["original_cell_id"] for entry in entries}) == expected_cells,
            "complete whole-cell inventory is required")
    value = pf.seal({"schema_version": 1, "status": "complete_input_witness_and_original_acquisition_inventory",
        "definition_content_sha256": definition, "preflight_completion_sha256": preflight_completion,
        "replay_completion_sha256": replay_completion, "scheduled_cells": expected_cells,
        "arithmetic_selector_sha256": arithmetic_selector_sha256,
        "selection_scope": pilot_input_scope(entries),
        "entries": entries, "action_counts": dict(sorted(Counter(item["action"] for item in entries).items())),
        "fit_dispatched": False, "method_approved": False, "corrected_freeze_created": False,
        "pending_original_acquisition_may_add_new_inventory_version": True})
    path = checked_path(output, f"inventories/{value['content_sha256']}/inventory.json")
    if path.exists():
        require(verified_json(path) == value, "existing inventory version differs")
    else:
        pf.write_json_new(path, value)
    return path


def pilot_input_scope(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep all complete changed accepted inputs, independently of old owners."""
    scope = []
    for entry in entries:
        decision = entry.get("decision", {})
        changed = decision.get("changed_roles", [])
        constructor_changed = any(name == "outer.synthetic_constructor" or
                                  (name.startswith("inner.") and name.endswith(".synthetic_constructor"))
                                  for name in changed)
        if (constructor_changed and not decision.get("missing_roles") and not decision.get("generator_failures")
                and entry.get("generator_contexts")
                and all(value[0] == "accepted" for value in entry["generator_contexts"].values())):
            metadata = entry["selection_scope"]
            require(type(metadata["n_train"]) is int and type(metadata["p"]) is int
                    and metadata["n_train"] > 0 and metadata["p"] > 0,
                    "changed accepted pilot dimensions are missing")
            scope.append(metadata)
    return scope


def arithmetic_selector_entry(row: dict[str, Any], preflight: dict[str, Any], replay: dict[str, Any],
                              preflight_receipt_path: str, preflight_receipt_sha256: str,
                              replay_receipt_path: str, replay_receipt_sha256: str) -> dict[str, Any]:
    """Select every changed accepted input and separately account terminal inputs."""
    accepted = preflight["accepted_attempt_index"]
    old_arrays = replay.get("array_witnesses")
    new_arrays = None if accepted is None else preflight["attempts"][accepted]["array_witnesses"]
    changed = [] if new_arrays is None or old_arrays is None else [
        key for key in sorted(NUMERIC_KEYS) if old_arrays[key] != new_arrays[key]]
    if preflight["status"] in ACCEPTED:
        require(old_arrays is not None, "accepted corrected input has no witnessed original constructor")
        require((accepted == 0) == (not changed), "constructor rank outcome changed with identical first input bytes")
        status = "changed_accepted_inputs" if changed else "unchanged_first_draw"
    else:
        status = {"input_failure": "terminal_input_failure", "exhausted_rank_cap": "terminal_rank_exhaustion",
                  "nonrank_failure": "terminal_nonrank_error"}[preflight["status"]]
    needs_kappa = status == "changed_accepted_inputs" and row["model"] in {"catalytic_fixed", "catalytic_adaptive"}
    return {"context_id": row["context_id"], "original_cell_id": row["outer_cell_id"], "model": row["model"],
        "context": "outer" if row["context"] == "outer" else f"inner_{row['inner_fold']:02d}",
        "status": status, "original_constructor_array_witnesses": old_arrays,
        "accepted_constructor_array_witnesses": new_arrays, "changed_logical_arrays": changed,
        "accepted_attempt_index": accepted, "requires_kappa_check": needs_kappa,
        "required_checks": (["q_and_gradient", "tau_scaled_identity", "weighted_merged_breslow"] +
                            (["original_kappa_and_adaptive_prior_terms"] if needs_kappa else []))
                            if status == "changed_accepted_inputs" else [],
        "preflight_receipt_path": preflight_receipt_path, "preflight_receipt_sha256": preflight_receipt_sha256,
        "replay_receipt_path": replay_receipt_path, "replay_receipt_sha256": replay_receipt_sha256,
        "arithmetic_executed_or_certified_by_selector": False}


def verify_execution_inputs(*, job: Any, raw: Any, runner: Any, fitting: Any,
                            primary: dict[str, Any], manifest: dict[str, Any],
                            input_witness: dict[str, Any], preflight_contexts: dict[str, Any],
                            core: Any, contracts: Any, witness_directory: Path,
                            input_witness_sha256: str, environment_verification: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct and compare every corrected role before a separately owned fit.

    This bridge executes preprocessing/folds and input-only horizon/truncation
    rules, never a generator/model/optimizer/prediction/score/selection function.
    Helper modules must already be byte pinned under the documented private
    import names. Source files, raw cohort loading and lock verification are
    owned by the caller; this bridge also checks loaded original source pins.
    """
    require(core is pf and contracts is globals()["contracts"], "foreign injected reconstruction helpers")
    path = witness_directory / "input_witness.json"
    require(pf.sha256_file(path) == input_witness_sha256 and verified_json(path) == input_witness,
            "execution input witness bytes differ")
    source = Path(runner.__file__).absolute().parents[3]
    for name, expected in manifest["input_sha256"].items():
        if name.startswith("src/"):
            require(pf.sha256_file(checked_path(source, name)) == expected, "execution scientific source bytes differ")
    require(input_witness["original_cell_id"] == job.cell_id
            and input_witness["model"] == job.model, "execution witness job identity differs")
    import importlib
    evaluation = importlib.import_module("src.pipelines.confirmatory.evaluation")

    class Backend:
        def __init__(self) -> None:
            self.manifest, self.primary, self.environment = manifest, primary, environment_verification

        def feature_spec(self, dataset: str) -> dict[str, Any]:
            mapping = runner.read_mapping(source / "config/datasets.yaml")
            return mapping["metabric" if dataset == "metabric_matched" else dataset]["primary_features"]

        def apply_censor(self, times: Any, events: Any, cutoff: Any) -> Any:
            return runner.apply_administrative_censoring(times, events, cutoff)

        def preprocess(self, specification: Any, budget: int, training: Any) -> Any:
            return runner.ExtensionPreprocessor(specification, budget).fit(training)

        def inner_folds(self, times: Any, events: Any, seed: int) -> Any:
            return fitting.repeated_survival_folds(times, events, n_splits=3, n_repeats=1,
                                                  base_seed=seed, max_time_bins=4)

        def candidates(self, model: str) -> Any:
            return fitting.candidates_for(model, manifest["run_config"], primary)

        def evaluation_inputs(self, tt: Any, ee: Any, vt: Any, ve: Any) -> dict[str, Any]:
            try:
                horizons, grid = evaluation.evaluation_horizons_and_grid(tt, ee, primary["evaluation"])
                clipped_time, clipped_event = evaluation.administratively_truncate_for_ipcw(vt, ve, float(grid[-1]))
                return {"status": "constructed_without_predictions_or_scores", "horizons": pf.array_witness(horizons),
                        "grid": pf.array_witness(grid), "ipcw_validation_time": pf.array_witness(clipped_time),
                        "ipcw_validation_event": pf.array_witness(clipped_event)}
            except Exception as error:
                return {"status": "original_evaluation_input_rule_failed", "error": input_error_value(error),
                        "no_model_prediction_or_score_executed": True}

    backend = Backend()
    context = reconstruction_inputs(job, raw, backend, contracts.seed_ledger(job.cell_id))
    require("input_error" not in context, "execution training input failure cannot launch a fit")
    generators = {}
    required = {"outer"} if job.model in contracts.CATALYTIC_MODELS else set()
    if job.model == "catalytic_wme":
        required |= {f"inner_{fold:02d}" for fold in range(1, 4)}
    require(set(preflight_contexts) == required, "execution generator context coverage differs")
    for name, supplied in preflight_contexts.items():
        current = context["generator_training_contexts"].get(name)
        require(current is not None, "missing current training-only generator context")
        witness = supplied["input_witness"]
        processor = current["processor"]
        sources = list(dict.fromkeys(processor.clinical.required_source_columns + processor.genes))
        current_real = {"real_design": processor.transform(current["training"]).to_numpy(float),
                        "real_time": current["time"], "real_event": current["event"]}
        require(set(supplied["real_arrays"]) == set(current_real)
                and all(pf.array_witness(supplied["real_arrays"][key]) == pf.array_witness(value)
                        for key, value in current_real.items()), "execution saved real arrays differ")
        require(witness["processor_metadata"] == processor.metadata()
                and witness["ordered_training_subject_ids"] == current["training"].subject_id.tolist()
                and witness["source_values"] == pf.source_frame_witness(current["training"], sources)
                and witness["real_design"] == pf.array_witness(processor.transform(current["training"]).to_numpy(float))
                and witness["training_time"] == pf.array_witness(current["time"])
                and witness["training_event"] == pf.array_witness(current["event"]),
                "execution current generator training/processor/design/outcomes differ")
        arrays = supplied["proposal_arrays"]
        require(set(arrays) == NUMERIC_KEYS, "execution accepted synthetic array keys differ")
        scale = float(np.median(current["time"][current["event"] == 1]))
        hazard = float(np.sum(current["event"]) / np.sum(current["time"] / scale))
        require(pf.array_witness(arrays["time_scale"]) == pf.array_witness(np.asarray(scale))
                and pf.array_witness(arrays["hazard"]) == pf.array_witness(np.asarray(hazard)),
                "execution training exponential scale/hazard differs")
        seed_key = "outer_prior" if name == "outer" else "inner_prior"
        ledger = contracts.seed_ledger(job.cell_id)
        original_seed = ledger[seed_key] if name == "outer" else ledger[seed_key][str(int(name[-2:]))]
        index = supplied["accepted_attempt_index"]
        require(type(index) is int and 0 <= index < 256, "execution accepted original attempt index differs")
        expected_seed = original_seed if index == 0 else contracts.deterministic_seed(
            original_seed, "rank_conditioned_retry", index)
        require(supplied["accepted_seed"] == expected_seed, "execution accepted retry seed differs")
        attempt = {"status": "accepted_original_constructor", "array_witnesses": {
            key: pf.array_witness(value) for key, value in arrays.items()},
            "legacy_metadata": supplied["legacy_metadata"]}
        require(attempt["legacy_metadata"] is not None
                and attempt["legacy_metadata"]["seed"] == supplied["accepted_seed"],
                "execution accepted original legacy seed differs")
        replay = {"status": "accepted_original_constructor", "array_witnesses": attempt["array_witnesses"]}
        generators[name] = ({"status": "accepted_original_first_draw", "attempts": [attempt],
                             "accepted_attempt_index": 0}, replay)
    values = make_role_values(job, context, backend, generators)
    role_hashes = {}
    carrier = input_witness["fit_witness"]
    require(set(carrier["roles"]) == set(contracts.required_roles(job.model)), "execution complete role coverage differs")
    for name, (_, current) in values.items():
        proof_path = checked_path(witness_directory, f"roles/{name}.json")
        proof = verified_json(proof_path, input_witness["proof_artifacts"][f"roles/{name}.json"])
        comparison = carrier["roles"][name]
        require(proof["role"] == name and proof["corrected"] == current
                and proof["corrected_sha256"] == contracts.digest(current) == comparison["corrected_sha256"]
                and comparison["proof_receipt_sha256"] == pf.sha256_file(proof_path),
                f"execution corrected complete input role differs: {name}")
        role_hashes[name] = contracts.digest(current)
    receipt = pf.seal({"status": "current_complete_inputs_match_corrected_witness",
            "input_witness_sha256": input_witness_sha256,
            "definition_content_sha256": input_witness["definition_content_sha256"],
            "required_role_count": len(role_hashes), "corrected_role_sha256": role_hashes,
            "no_generator_model_fit_prediction_or_score_executed": True})
    return {"status": receipt["status"], "receipt": receipt,
            "input_witness_sha256": input_witness_sha256,
            "definition_content_sha256": input_witness["definition_content_sha256"],
            "required_role_count": len(role_hashes), "corrected_role_sha256": role_hashes,
            "generator_training_contexts": {name: context["generator_training_contexts"][name] for name in required},
            "no_generator_model_fit_prediction_or_score_executed": True}
