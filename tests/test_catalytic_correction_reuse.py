"""Invented/injected checks only; no real cohort or original generator calls."""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import pickle
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).absolute().parents[1] / "scripts/catalytic_correction"


def load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PF_PATH = ROOT / "preflight_core.py"
CONTRACT_PATH = ROOT / "correction_fit_contracts.py"
pf = load(PF_PATH, "_reuse_bound_core")
contracts = load(CONTRACT_PATH, "_reuse_bound_contracts")
core = load(ROOT / "reuse_core.py", "reuse_test_core")
cli = load(ROOT / "run_reuse.py", "reuse_test_cli")
H = "7" * 64


class Processor:
    def __init__(self, training: pd.DataFrame) -> None:
        self.mean = float(training.x.mean())
        self.feature_names = ["x"]
        self.genes = []
        self.clinical = SimpleNamespace(required_source_columns=["x"])

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame({"x": frame.x - self.mean}, index=frame.index)

    def metadata(self) -> dict[str, Any]:
        return {"mean": self.mean, "feature_names": ["x"]}


class Backend:
    def __init__(self, model: str = "catalytic_wme") -> None:
        self.model, self.observed_split_times = model, []
        self.manifest = {"input_sha256": {"src/models/fake.py": H, "src/pipelines/fake.py": H,
            "src/evaluation/fake.py": H}, "run_config": {"base_seed": 260817, "sampling": {"draws": 2000},
            "calibration_bootstraps": 500, "catalytic": {"wme_tau_multipliers": [0.25, 1.0, 4.0]}}}
        self.primary, self.environment = {"models": {}, "evaluation": {}}, {"status": "invented_lock_ok"}

    def feature_spec(self, _dataset: str) -> dict[str, Any]:
        return {"continuous": ["x"]}

    def apply_censor(self, times: np.ndarray, events: np.ndarray, cutoff: float | None) -> Any:
        if cutoff is None:
            return times.copy(), events.copy()
        return np.minimum(times, cutoff), (events * (times <= cutoff)).astype(int)

    def preprocess(self, _spec: Any, _budget: int, training: pd.DataFrame) -> Processor:
        return Processor(training)

    def inner_folds(self, times: np.ndarray, events: np.ndarray, seed: int) -> Any:
        self.observed_split_times.append(times.copy())
        indices = np.arange(len(times))
        return [SimpleNamespace(fold=fold, seed=seed, train_indices=indices[indices % 3 != fold - 1],
                validation_indices=indices[indices % 3 == fold - 1]) for fold in range(1, 4)]

    def evaluation_inputs(self, tt: np.ndarray, ee: np.ndarray, vt: np.ndarray, ve: np.ndarray) -> Any:
        return {"status": "invented_no_scores", "training": core.outcome_witness(tt, ee),
                "validation": core.outcome_witness(vt, ve)}

    def candidates(self, model: str) -> Any:
        return [{"tau_multiplier": value} for value in (0.25, 1.0, 4.0)] if model == "catalytic_wme" else [{}]


def fixture(model: str = "catalytic_wme", cutoff: float | None = 45.0) -> tuple[Any, pd.DataFrame, Backend]:
    raw = pd.DataFrame({"subject_id": [f"p{index:02d}" for index in range(70)],
        "x": np.arange(70, dtype=float), "duration": np.arange(1, 71, dtype=float), "event": np.ones(70, dtype=int)})
    cell_id = f"gbsg2__clinical__r01f01__{model}__full"
    job = SimpleNamespace(cell_id=cell_id, dataset="gbsg2", setting="clinical", model=model,
                          repeat=1, fold=1, condition="full", train=np.arange(60), validation=np.arange(60, 70),
                          censoring_cutoff=cutoff, gene_budget=0)
    return job, raw, Backend(model)


def generator_pair(changed: bool = False) -> tuple[Any, Any]:
    arrays = {"synthetic_design": pf.array_witness(np.arange(4, dtype=float).reshape(4, 1)),
              "synthetic_time": pf.array_witness(np.arange(1, 5, dtype=float)),
              "hazard": pf.array_witness(np.asarray(1.0)), "time_scale": pf.array_witness(np.asarray(10.0))}
    processor = {"mean": 1.0}
    first = {"status": "accepted_original_constructor", "array_witnesses": arrays,
             "legacy_metadata": {"seed": 11}, "actual_metadata": {"processor_metadata": processor}, "seed": 11}
    record = {"status": "accepted_original_first_draw", "attempts": [first], "accepted_attempt_index": 0}
    replay = {"status": first["status"], "array_witnesses": arrays, "legacy_metadata": first["legacy_metadata"],
              "processor_metadata": processor, "seed": 11, "error": None}
    if changed:
        old = copy.deepcopy(first)
        old.update(status="frozen_rank_rejected", legacy_metadata=None)
        old["array_witnesses"]["synthetic_design"]["values_sha256"] = "4" * 64
        record.update(status="accepted_rank_conditioned_redraw", attempts=[old, first], accepted_attempt_index=1)
        replay.update(status=old["status"], array_witnesses=old["array_witnesses"], legacy_metadata=None)
    return record, replay


def make_witness(tmp_path: Path, model: str = "catalytic_wme", changed: str | None = None) -> tuple[Any, Any, Any]:
    job, raw, backend = fixture(model)
    context = core.reconstruction_inputs(job, raw, backend, contracts.seed_ledger(job.cell_id))
    names = ["outer", "inner_01", "inner_02", "inner_03"] if model == "catalytic_wme" else ["outer"]
    pairs = {name: generator_pair(name == changed) for name in names} if model in contracts.CATALYTIC_MODELS else {}
    values = core.make_role_values(job, context, backend, pairs)
    contexts = {name: ["accepted", H] for name in pairs}
    directory = tmp_path / "cells" / job.cell_id
    witness = core.write_role_witness(directory, H, job, context, values, contexts)
    return job, witness, directory


def original_cell(run: Path, job: Any, *, status: str = "complete", tuning: bool = True) -> dict[str, Any]:
    _, raw, backend = fixture(job.model, job.censoring_cutoff)
    context = core.reconstruction_inputs(job, raw, backend, contracts.seed_ledger(job.cell_id))
    ids = raw.subject_id.iloc[job.train].tolist()
    value = {"cell_id": job.cell_id, "status": status, "fit_attempts": [], "schema_version": 1,
        "dataset": job.dataset, "setting": job.setting, "model_key": job.model, "repeat": job.repeat,
        "fold": job.fold, "condition": job.condition, "seed": contracts.seed_ledger(job.cell_id)["cell"],
        "train_subject_ids": ids, "validation_subject_ids": raw.subject_id.iloc[job.validation].tolist(),
        "training_membership_sha256": pf.canonical_hash(ids), "n_train": len(job.train), "n_validation": len(job.validation),
        "events_train": int(context["ee"].sum()), "censoring_cutoff": job.censoring_cutoff, "gene_budget": job.gene_budget}
    if tuning:
        value.update(selected_parameters={}, inner_tuning={"tuned": False, "candidates": []})
    value["cell_content_sha256"] = pf.canonical_hash(value)
    path = run / "cells" / f"{job.cell_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))
    return value


def test_censoring_precedes_inner_splits_and_all_nine_slots() -> None:
    job, raw, backend = fixture()
    context = core.reconstruction_inputs(job, raw, backend, contracts.seed_ledger(job.cell_id))
    assert max(backend.observed_split_times[0]) == 45
    assert len(context["inner"]) == 3
    assert sum(len(inner["candidate_slots"]) for inner in context["inner"]) == 9
    assert all(slot["inner_fit_seed"] == contracts.seed_ledger(job.cell_id)["inner_fit"][
        f"{slot['fold']}:{slot['candidate_index_zero_based']}"] for inner in context["inner"] for slot in inner["candidate_slots"])


def test_heldout_change_cannot_change_training_or_generators() -> None:
    job, raw, backend = fixture()
    old = core.reconstruction_inputs(job, raw, backend, contracts.seed_ledger(job.cell_id))
    changed = raw.copy()
    changed.loc[job.validation, "x"] = 9999
    new = core.reconstruction_inputs(job, changed, backend, contracts.seed_ledger(job.cell_id))
    assert old["base_roles"]["encoded_training"] == new["base_roles"]["encoded_training"]
    assert old["base_roles"]["encoded_validation"] != new["base_roles"]["encoded_validation"]
    assert old["inner"] == new["inner"]
    assert old["processor"].metadata() == new["processor"].metadata()


@pytest.mark.parametrize(("model", "count"), [("ridge", 19), ("catalytic_fixed", 21), ("catalytic_wme", 42)])
def test_complete_role_values_and_transparent_proofs(tmp_path: Path, model: str, count: int) -> None:
    job, witness, directory = make_witness(tmp_path, model)
    assert len(witness["fit_witness"]["roles"]) == count
    assert len(witness["proof_artifacts"]) == count
    assert witness["fit_witness"]["original_evidence"] is None
    for name, comparison in witness["fit_witness"]["roles"].items():
        proof = core.verified_json(directory / "roles" / f"{name}.json")
        assert proof["original"] == proof["corrected"]
        assert proof["corrected_sha256"] == comparison["corrected_sha256"]
    assert witness["selection_scope"] == {"original_cell_id": job.cell_id, "model": model,
        "setting": "clinical", "gene_budget": 0, "n_train": 60, "p": 1}
    assert len(witness["all_wme_candidate_slots"]) == (9 if model == "catalytic_wme" else 0)


def test_first_draw_requires_all_values_not_legacy_hash_only() -> None:
    record, replay = generator_pair()
    witness = {"processor_metadata": replay["processor_metadata"]}
    assert core.compare_first_draw(record, replay, witness)["full_constructor_identity_witnessed"]
    broken = copy.deepcopy(replay)
    broken["array_witnesses"]["hazard"]["values_sha256"] = "5" * 64
    with pytest.raises(pf.InvalidCheckpoint, match="design/time/hazard"):
        core.compare_first_draw(record, broken, witness)


def test_original_rank_rejection_retains_absence_and_arrays() -> None:
    record, replay = generator_pair(True)
    result = core.compare_first_draw(record, replay, {"processor_metadata": replay["processor_metadata"]})
    assert result["constructor_result"] == "frozen_rank_rejected"
    assert replay["legacy_metadata"] is None
    changed = copy.deepcopy(replay)
    changed["legacy_metadata"] = {"fabricated": True}
    with pytest.raises(pf.InvalidCheckpoint, match="metadata"):
        core.compare_first_draw(record, changed, {"processor_metadata": replay["processor_metadata"]})


def test_input_and_nonrank_failures_require_exact_exception_identity() -> None:
    error = {"type": "builtins.ValueError", "message": "invented failure"}
    assert not core.compare_first_draw({"status": "input_failure", "input_error": error},
        {"status": "input_failure", "error": error}, None)["generator_called"]
    first = {"status": "nonrank_error", "seed": 4, "error": error}
    before = {"status": "nonrank_failure", "attempts": [first]}
    replay = {"status": "nonrank_error", "seed": 4, "error": error, "processor_metadata": {}}
    assert core.compare_first_draw(before, replay, {"processor_metadata": {}})["status"] == "exact_original_nonrank_error"
    replay["error"] = {**error, "message": "different"}
    with pytest.raises(pf.InvalidCheckpoint, match="nonrank"):
        core.compare_first_draw(before, replay, {"processor_metadata": {}})


@pytest.mark.parametrize("status", contracts.OUTCOME_STATUSES)
def test_unchanged_success_and_failures_reuse_equally(tmp_path: Path, status: str) -> None:
    job, witness, directory = make_witness(tmp_path, "catalytic_fixed")
    run = tmp_path / "original"
    original_cell(run, job, status=status)
    snapshot = core.original_snapshot(run, job.cell_id, contracts.ORIGINAL_MANIFEST_SHA256, [{}])
    decision, path = core.snapshot_decision(directory, H, witness, snapshot)
    assert decision["action"] == "reuse_original_outcome"
    assert decision["source_evidence"]["status"] == status
    assert decision["source_evidence"]["verification_receipt_sha256"] != pf.sha256_file(path)
    assert core.snapshot_decision(directory, H, witness, snapshot)[1] == path
    assert core.verified_json(path, artifact_root=directory) == decision


def test_pending_and_owner_block_changed_dispatch_without_changing_pilot_scope(tmp_path: Path) -> None:
    job, witness, directory = make_witness(tmp_path, "catalytic_fixed", "outer")
    run = tmp_path / "original"
    absent = core.original_snapshot(run, job.cell_id, contracts.ORIGINAL_MANIFEST_SHA256, [{}])
    first, _ = core.snapshot_decision(directory, H, witness, absent)
    assert first["potential_action"] == "fit_changed_inputs"
    assert first["action"] == "await_original_owner"
    original_cell(run, job)
    claim = run / "claims" / f"{job.cell_id}.json"
    claim.parent.mkdir()
    claim.write_text('{"pid":1234}')
    active = core.original_snapshot(run, job.cell_id, contracts.ORIGINAL_MANIFEST_SHA256, [{}])
    second, _ = core.snapshot_decision(directory, H, witness, active)
    assert second["action"] == "await_original_owner"
    assert first["selection_scope"] == second["selection_scope"] == witness["selection_scope"]
    claim.unlink()
    ready = core.original_snapshot(run, job.cell_id, contracts.ORIGINAL_MANIFEST_SHA256, [{}])
    final, _ = core.snapshot_decision(directory, H, witness, ready)
    assert final["action"] == "fit_changed_inputs"
    assert len(list((directory / "snapshots").glob("*.json"))) == 3


def wme_cell(run: Path, job: Any) -> dict[str, Any]:
    rows = [{"parameters": {"tau_multiplier": multiplier}, "scores": [value] * 3,
             "failures": [], "mean_ibs": float(np.mean([value] * 3))} for multiplier, value in zip((0.25, 1.0, 4.0), (0.2, 0.1, 0.1), strict=True)]
    cell = original_cell(run, job, tuning=False)
    cell.pop("cell_content_sha256")
    cell.update({
        "selected_parameters": {"tau_multiplier": 1.0}, "inner_tuning": {"tuned": True,
            "selected_index": 1, "candidates": rows, "selection": "three-inner-fold mean IPCW IBS; stable candidate-order ties"}})
    cell["cell_content_sha256"] = pf.canonical_hash(cell)
    path = run / "cells" / f"{job.cell_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cell))
    return cell


@pytest.mark.parametrize(("changed", "expected"), [("outer", "fit_changed_inputs_reuse_tuning"),
                                                  ("inner_02", "retune_then_fit_changed_inputs")])
def test_wme_outer_vs_inner_change_and_actual_tuning_record(tmp_path: Path, changed: str, expected: str) -> None:
    job, witness, directory = make_witness(tmp_path, changed=changed)
    run = tmp_path / "original"
    cell = wme_cell(run, job)
    candidates = [{"tau_multiplier": value} for value in (0.25, 1.0, 4.0)]
    snapshot = core.original_snapshot(run, job.cell_id, contracts.ORIGINAL_MANIFEST_SHA256, candidates)
    decision, _ = core.snapshot_decision(directory, H, witness, snapshot)
    assert decision["action"] == expected
    expected_digest = contracts.digest({"selected_parameters": cell["selected_parameters"], "inner_tuning": cell["inner_tuning"]})
    assert decision["tuning_record_combined_sha256"] == expected_digest
    assert decision["source_evidence"]["wme_tuning_record_sha256"] == expected_digest


def test_saved_tuning_incomplete_or_unstable_tie_is_rejected(tmp_path: Path) -> None:
    job, _, _ = fixture()
    cell = wme_cell(tmp_path, job)
    candidates = [{"tau_multiplier": value} for value in (0.25, 1.0, 4.0)]
    changed = copy.deepcopy(cell)
    changed["inner_tuning"]["selected_index"] = 2
    changed["selected_parameters"] = candidates[2]
    with pytest.raises(pf.InvalidCheckpoint, match="stable selection"):
        core.verify_tuning(changed, candidates)
    changed = copy.deepcopy(cell)
    changed["inner_tuning"]["candidates"][0]["scores"].pop()
    with pytest.raises(pf.InvalidCheckpoint, match="three folds"):
        core.verify_tuning(changed, candidates)


def test_referenced_and_orphan_traces_are_bound_with_run_relative_names(tmp_path: Path) -> None:
    job, _, _ = fixture("catalytic_fixed")
    cell = original_cell(tmp_path, job)
    trace = tmp_path / "traces" / job.cell_id / "attempt_1_posterior.nc"
    trace.parent.mkdir(parents=True)
    trace.write_bytes(b'invented referenced trace')
    orphan = trace.parent / "attempt_2_prior.nc"
    orphan.write_bytes(b'invented orphan trace')
    cell["fit_attempts"] = [{"traces": {"posterior": {"filename": trace.name, "sha256": pf.sha256_file(trace)}}}]
    cell.pop("cell_content_sha256")
    cell["cell_content_sha256"] = pf.canonical_hash(cell)
    (tmp_path / "cells" / f"{job.cell_id}.json").write_text(json.dumps(cell))
    snapshot = core.original_snapshot(tmp_path, job.cell_id, contracts.ORIGINAL_MANIFEST_SHA256, [{}])
    assert set(snapshot["referenced_trace_sha256"]) == {f"traces/{job.cell_id}/{trace.name}"}
    assert set(snapshot["unreferenced_trace_sha256"]) == {f"traces/{job.cell_id}/{orphan.name}"}
    trace.write_bytes(b'changed')
    with pytest.raises(pf.InvalidCheckpoint, match="trace bytes differ"):
        core.original_snapshot(tmp_path, job.cell_id, contracts.ORIGINAL_MANIFEST_SHA256, [{}])


def test_partial_role_receipt_and_tamper_never_skip_or_overwrite(tmp_path: Path) -> None:
    job, witness, directory = make_witness(tmp_path, "catalytic_fixed")
    before = pf.sha256_file(directory / "input_witness.json")
    proof = directory / "roles" / "encoded_training.json"
    proof.write_text('{}')
    with pytest.raises(pf.InvalidCheckpoint):
        core.verified_json(directory / "input_witness.json")
    assert pf.sha256_file(directory / "input_witness.json") == before
    assert witness["selection_scope"]["original_cell_id"] == job.cell_id


def test_full_raw_witness_detects_dtype_order_values_and_row_index() -> None:
    _, raw, _ = fixture()
    original = core.full_frame_witness(raw)
    assert core.full_frame_witness(raw[list(reversed(raw.columns))]) != original
    changed = raw.copy()
    changed.event = changed.event.astype('int32')
    assert core.full_frame_witness(changed) != original
    changed = raw.copy()
    changed.index = changed.index + 100
    assert core.full_frame_witness(changed) != original


def test_complete_inventory_versions_are_immutable_and_require_whole_coverage(tmp_path: Path) -> None:
    entries = [{"original_cell_id": "invented", "action": "await_original_outcome"}]
    path = core.publish_inventory(tmp_path, H, H, H, entries, expected_cells=1)
    assert core.publish_inventory(tmp_path, H, H, H, entries, expected_cells=1) == path
    changed = [{"original_cell_id": "invented", "action": "reuse_original_outcome"}]
    newer = core.publish_inventory(tmp_path, H, H, H, changed, expected_cells=1)
    assert newer != path and path.exists()
    with pytest.raises(pf.InvalidCheckpoint, match="whole-cell"):
        core.publish_inventory(tmp_path, H, H, H, entries)


def test_bootstrap_foreign_src_fails_before_any_source_or_data_read(monkeypatch: Any) -> None:
    monkeypatch.setitem(sys.modules, "src", SimpleNamespace())
    with pytest.raises(ValueError, match="foreign src"):
        cli.bootstrap(SimpleNamespace())


def test_pinned_import_and_path_traversal_fail_closed(tmp_path: Path) -> None:
    source = tmp_path / "module.py"
    source.write_text('raise AssertionError("must not import")')
    with pytest.raises(ValueError, match="bytes differ"):
        cli.import_pinned(source, "must_not_load", H)
    with pytest.raises(pf.InvalidCheckpoint, match="unsafe"):
        core.checked_path(tmp_path, '../other')


def test_parent_owned_child_receipt_cache_never_calls_real_subprocess(tmp_path: Path, monkeypatch: Any) -> None:
    request = {"context_id": "invented"}
    child = tmp_path / "normal_original_child"
    pf.write_json_new(child / "receipt.json", pf.seal({"request": request, "artifacts": {}}))
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: pytest.fail('unexpected process'))
    assert cli.run_independent_child(SimpleNamespace(), tmp_path, request, None, {}, {}, pf)["request"] == request
    with pytest.raises(pf.InvalidCheckpoint, match="request differs"):
        cli.run_independent_child(SimpleNamespace(), tmp_path, {"context_id": "changed"}, None, {}, {}, pf)


def test_partial_independent_child_requires_review(tmp_path: Path) -> None:
    child = tmp_path / "normal_original_child"
    child.mkdir()
    (child / "request.json").write_text('{}')
    with pytest.raises(pf.InvalidCheckpoint, match="partial independent"):
        cli.run_independent_child(SimpleNamespace(), tmp_path, {}, None, {}, {}, pf)


def tiny_preflight(tmp_path: Path) -> tuple[Path, dict[str, Any]]:
    row = {"context_id": "invented::outer", "generation_seed": 11}
    manifest = pf.seal({"schema_version": 1})
    pf.write_json_new(tmp_path / "manifest.json", manifest)
    directory = tmp_path / "contexts" / "invented" / "outer"
    real = {"real_design": np.arange(4, dtype=float).reshape(4, 1), "real_time": np.arange(1, 5, dtype=float),
            "real_event": np.ones(4, dtype=int)}
    witness = {"real_design": pf.array_witness(real["real_design"]), "training_time": pf.array_witness(real["real_time"]),
               "training_event": pf.array_witness(real["real_event"])}
    request = {"context_id": row["context_id"], "context_row_sha256": pf.canonical_hash(row),
        "original_generation_seed": 11, "run_binding_sha256": manifest["content_sha256"],
        "candidate_cap": 256, "input_witness_sha256": pf.canonical_hash(witness)}
    pf.save_arrays(directory / "inputs.npz", real)
    pf.write_json_new(directory / "input.json", pf.seal({"request": request, "input_witness": witness}))
    proposal = {"synthetic_design": real["real_design"], "synthetic_time": real["real_time"],
                "hazard": np.asarray(1.0), "time_scale": np.asarray(10.0)}
    pf.save_arrays(directory / "attempt_000" / "proposal.npz", proposal)
    attempt = pf.seal({"request": request, "attempt_index": 0, "seed": 11,
        "status": "accepted_original_constructor", "array_witnesses": {key: pf.array_witness(value) for key, value in proposal.items()},
        "artifacts": {"proposal.npz": pf.artifact_binding(directory / "attempt_000/proposal.npz")}})
    pf.write_json_new(directory / "attempt_000/receipt.json", attempt)
    record = pf.seal({"request": request, "status": "accepted_original_first_draw", "attempts": [attempt],
        "accepted_attempt_index": 0, "candidate_metadata": None,
        "artifacts": {name: pf.artifact_binding(directory / name) for name in
                     ("input.json", "inputs.npz", "attempt_000/receipt.json", "attempt_000/proposal.npz")}})
    pf.write_json_new(directory / "receipt.json", record)
    pf.write_json_new(tmp_path / "completion.json", pf.seal({"status": "all_scheduled_contexts_accounted",
        "scheduled_contexts": 1, "accounted_contexts": 1, "run_binding_sha256": manifest["content_sha256"],
        "outcomes": [{"context_id": row["context_id"], "status": record["status"],
            "receipt_path": "contexts/invented/outer/receipt.json", "receipt_sha256": pf.sha256_file(directory / "receipt.json"),
            "receipt_content_sha256": record["content_sha256"]}]}))
    return directory, row


def test_complete_preflight_requires_actual_whole_coverage(tmp_path: Path) -> None:
    directory, row = tiny_preflight(tmp_path)
    complete = core.CompletePreflight(tmp_path, [row], expected_count=1)
    assert complete.context(row)[0] == directory
    with pytest.raises(pf.InvalidCheckpoint, match="full preflight"):
        core.CompletePreflight(tmp_path, [row])


@pytest.mark.parametrize("changed", ["array", "attempt", "extra", "completion"])
def test_preflight_corruption_is_never_treated_as_reusable(tmp_path: Path, changed: str) -> None:
    directory, row = tiny_preflight(tmp_path)
    if changed == "array":
        (directory / "attempt_000/proposal.npz").write_bytes(b'changed')
    elif changed == "attempt":
        (directory / "attempt_000/receipt.json").write_text('{}')
    elif changed == "extra":
        (directory / "attempt_001").mkdir()
    else:
        (tmp_path / "completion.json").write_text('{}')
    with pytest.raises(pf.InvalidCheckpoint):
        core.CompletePreflight(tmp_path, [row], expected_count=1).context(row)


def test_saved_original_membership_state_and_prediction_inputs_must_match(tmp_path: Path) -> None:
    job, witness, directory = make_witness(tmp_path, "catalytic_fixed")
    run = tmp_path / "original"
    cell = original_cell(run, job)
    wrong = copy.deepcopy(cell)
    wrong["train_subject_ids"] = list(reversed(wrong["train_subject_ids"]))
    with pytest.raises(pf.InvalidCheckpoint, match="train_subject_ids"):
        core.validate_saved_input_fields(directory, witness, wrong)
    wrong = copy.deepcopy(cell)
    wrong["preprocessing"] = {"mean": 999}
    with pytest.raises(pf.InvalidCheckpoint, match="processor state"):
        core.validate_saved_input_fields(directory, witness, wrong)
    wrong = copy.deepcopy(cell)
    wrong["predictions"] = {"subject_ids": cell["validation_subject_ids"],
        "training_time": [1.0] * 60, "training_event": [1] * 60, "observed_time": [45.0] * 10, "observed_event": [0] * 10}
    with pytest.raises(pf.InvalidCheckpoint, match="prediction outcome"):
        core.validate_saved_input_fields(directory, witness, wrong)
    recorded = copy.deepcopy(cell)
    recorded['fit_attempts'] = [{'attempt': 1, 'warnings': []}]
    core.validate_saved_input_fields(directory, witness, recorded)
    recorded['fit_attempts'][0]['attempt'] = 2
    with pytest.raises(pf.InvalidCheckpoint, match="ordering"):
        core.validate_saved_input_fields(directory, witness, recorded)


@pytest.mark.parametrize("model", ["catalytic_fixed", "catalytic_adaptive", "catalytic_wme"])
def test_changed_arithmetic_selector_requires_fixed_and_adaptive_kappa(model: str) -> None:
    row = {"context_id": "invented::outer", "outer_cell_id": "invented", "context": "outer", "model": model}
    changed, replay = generator_pair(True)
    entry = core.arithmetic_selector_entry(row, changed, replay, 'pf/receipt.json', H, 'replay/receipt.json', H)
    assert entry["status"] == "changed_accepted_inputs"
    assert entry["requires_kappa_check"] == (model != "catalytic_wme")
    original, replay = generator_pair()
    assert core.arithmetic_selector_entry(row, original, replay, 'pf/receipt.json', H, 'replay/receipt.json', H)["status"] == "unchanged_first_draw"


@pytest.mark.parametrize(("old", "new"), [("input_failure", "terminal_input_failure"),
    ("nonrank_failure", "terminal_nonrank_error"), ("exhausted_rank_cap", "terminal_rank_exhaustion")])
def test_arithmetic_selector_accounts_all_terminal_inputs(old: str, new: str) -> None:
    row = {"context_id": "invented::outer", "outer_cell_id": "invented", "context": "outer", "model": "catalytic_fixed"}
    entry = core.arithmetic_selector_entry(row, {"status": old, "accepted_attempt_index": None},
        {"array_witnesses": None}, 'pf/receipt.json', H, 'replay/receipt.json', H)
    assert entry["status"] == new and not entry["required_checks"]


FAKE_SOURCE = '''"""Entirely invented normal-import dependency fixture; no scientific SVD."""
import numpy as np
import pandas as pd
from types import SimpleNamespace
class ExtensionPreprocessor:
    def __init__(self, spec, budget):
        self.spec, self.budget = spec, budget
        self.genes = []
        self.clinical = SimpleNamespace(required_source_columns=['x'])
        self.feature_names = ['x']
    def fit(self, training):
        self.mean = float(training.x.mean())
        return self
    def transform(self, frame):
        return pd.DataFrame({'x': frame.x-self.mean}, index=frame.index)
    def metadata(self):
        return {'mean': self.mean, 'feature_names': ['x']}
class CatalyticData:
    def __init__(self, design, time, hazard):
        self.design, self.time, self.hazard = design, time, hazard
        self.__post_init__()
    def __post_init__(self):
        if self.design[0,0] < -100:
            raise ValueError('synthetic design is not full column rank')
def generate_catalytic_data(training, processor, time, event, seed):
    design = processor.transform(training.iloc[:4]).to_numpy(float)
    if seed == 12:
        design[0,0] = -1000
    if seed == 13:
        raise RuntimeError('invented nonrank error before constructor')
    data = CatalyticData(design, np.arange(1,5,dtype=float), 1.0)
    return data, {'seed': seed, 'invented_returned_metadata': True}
def select_parameters(*args, **kwargs):
    raise AssertionError('selection is forbidden in this fixture')
def fit(*args, **kwargs):
    raise AssertionError('fit is forbidden in this fixture')
'''


@pytest.mark.parametrize(("seed", "status"), [(11, "accepted_original_constructor"),
    (12, "frozen_rank_rejected"), (13, "nonrank_error")])
def test_owned_new_process_uses_normal_invented_import_capture_and_no_fit(tmp_path: Path, seed: int, status: str) -> None:
    source = tmp_path / "fake_original"
    names = ['src/__init__.py', 'src/pipelines/__init__.py', 'src/pipelines/extensions/__init__.py',
             'src/pipelines/extensions/preprocessing.py']
    for name in names:
        path = source / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(FAKE_SOURCE if name.endswith('preprocessing.py') else '')
    child = tmp_path / "owned"
    child.mkdir()
    _, raw, _ = fixture()
    training = raw.iloc[:60].copy()
    processor = Processor(training)
    time, event = training.duration.to_numpy(float), training.event.to_numpy(int)
    expected = {"ordered_training_subject_ids": training.subject_id.tolist(), "processor_metadata": processor.metadata(),
                "source_values": pf.source_frame_witness(training, ['x']),
                "real_design": pf.array_witness(processor.transform(training).to_numpy(float)),
                "training_time": pf.array_witness(time), "training_event": pf.array_witness(event)}
    payload = child / "owned_training_transport.pkl"
    pf.publish_new(payload, lambda stream: pickle.dump({"training": training, "time": time, "event": event,
        "feature_spec": {}, "gene_budget": 0}, stream, protocol=5))
    request = pf.seal({"request": {"original_generation_seed": seed}, "source": str(source),
        "original_input_sha256": {name: pf.sha256_file(source / name) for name in names},
        "payload_artifact": pf.artifact_binding(payload), "expected_input_witness": expected,
        "full_raw_training_witness": pf.source_frame_witness(training, list(training.columns)),
        "preflight_core": str(PF_PATH), "preflight_core_sha256": pf.sha256_file(PF_PATH),
        "child_source_sha256": pf.sha256_file(ROOT / 'normal_first_draw_child.py')})
    pf.write_json_new(child / "request.json", request)
    environment = os.environ.copy()
    for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        environment[key] = '1'
    result = subprocess.run([sys.executable, '-I', '-B', str(ROOT / 'normal_first_draw_child.py'),  # noqa: S603 - owned invented fixture only
        '--owned-directory', str(child), '--request-sha256', pf.sha256_file(child / 'request.json')],
        capture_output=True, text=True, env=environment)  # noqa: S603 - owned invented fixture only
    assert result.returncode == 0, result.stderr
    record = core.verified_json(child / "receipt.json")
    assert record["status"] == status
    assert record["constructor_alias_restored"] and not record["candidate_adapter_or_helpers_imported"]
    assert record["processor_metadata"] == processor.metadata()
    if status == 'nonrank_error':
        assert record["array_witnesses"] is None
    else:
        assert set(record["array_witnesses"]) == core.NUMERIC_KEYS
        assert record["array_witnesses"]["hazard"]["shape"] == []
        assert (record["legacy_metadata"] is None) == (status == 'frozen_rank_rejected')


def bridge_fixture(tmp_path: Path, monkeypatch: Any) -> tuple[Any, Any, Any]:
    job, raw, backend = fixture('catalytic_fixed')
    source = tmp_path / 'invented_source'
    runner_path = source / 'src/pipelines/extensions/runner.py'
    evaluation_path = source / 'src/pipelines/confirmatory/evaluation.py'
    for path in (runner_path, evaluation_path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('# invented injected source marker, never original programme source\n')
    backend.manifest['input_sha256'] = {str(path.relative_to(source)): pf.sha256_file(path)
                                        for path in (runner_path, evaluation_path)}
    horizon = np.asarray([1.0, 2.0])
    evaluation = SimpleNamespace(__file__=str(evaluation_path),
        evaluation_horizons_and_grid=lambda *args: (horizon.copy(), horizon.copy()),
        administratively_truncate_for_ipcw=lambda times, events, tau: (times.copy(), events.copy()))
    monkeypatch.setitem(sys.modules, 'src.pipelines.confirmatory.evaluation', evaluation)

    def evaluation_inputs(tt: Any, ee: Any, vt: Any, ve: Any) -> Any:
        return {'status': 'constructed_without_predictions_or_scores', 'horizons': pf.array_witness(horizon),
                'grid': pf.array_witness(horizon), 'ipcw_validation_time': pf.array_witness(vt),
                'ipcw_validation_event': pf.array_witness(ve)}
    backend.evaluation_inputs = evaluation_inputs
    context = core.reconstruction_inputs(job, raw, backend, contracts.seed_ledger(job.cell_id))
    time, event = context['tt'], context['ee']
    scale = float(np.median(time[event == 1]))
    hazard = float(np.sum(event) / np.sum(time / scale))
    arrays = {'synthetic_design': np.arange(4, dtype=float).reshape(4, 1), 'synthetic_time': np.arange(1, 5, dtype=float),
              'hazard': np.asarray(hazard), 'time_scale': np.asarray(scale)}
    seed = contracts.seed_ledger(job.cell_id)['outer_prior']
    first = {'status': 'accepted_original_constructor', 'array_witnesses': {
        name: pf.array_witness(value) for name, value in arrays.items()}, 'legacy_metadata': {'seed': seed}}
    record = {'status': 'accepted_original_first_draw', 'attempts': [first], 'accepted_attempt_index': 0}
    replay = {'status': 'accepted_original_constructor', 'array_witnesses': first['array_witnesses']}
    values = core.make_role_values(job, context, backend, {'outer': (record, replay)})
    directory = tmp_path / 'witness' / job.cell_id
    witness = core.write_role_witness(directory, H, job, context, values, {'outer': ['accepted', H]})
    runner = SimpleNamespace(__file__=str(runner_path),
        read_mapping=lambda path: {'gbsg2': {'primary_features': backend.feature_spec('gbsg2')}},
        apply_administrative_censoring=backend.apply_censor,
        ExtensionPreprocessor=lambda spec, budget: SimpleNamespace(fit=lambda training: Processor(training)))
    fitting = SimpleNamespace(candidates_for=lambda model, config, primary: backend.candidates(model),
        repeated_survival_folds=lambda times, events, **options: backend.inner_folds(times, events, options['base_seed']))
    kwargs = {'job': job, 'raw': raw, 'runner': runner, 'fitting': fitting, 'primary': backend.primary,
        'manifest': backend.manifest, 'input_witness': witness, 'preflight_contexts': {'outer': {
            'input_witness': {'processor_metadata': context['processor'].metadata(),
                'ordered_training_subject_ids': context['training'].subject_id.tolist(),
                'source_values': pf.source_frame_witness(context['training'], ['x']),
                'real_design': pf.array_witness(context['xt']), 'training_time': pf.array_witness(time),
                'training_event': pf.array_witness(event)},
            'real_arrays': {'real_design': context['xt'], 'real_time': time, 'real_event': event},
            'proposal_arrays': arrays, 'legacy_metadata': first['legacy_metadata'], 'accepted_seed': seed,
            'accepted_attempt_index': 0, 'receipt_sha256': H}},
        'core': pf, 'contracts': contracts, 'witness_directory': directory,
        'input_witness_sha256': pf.sha256_file(directory / 'input_witness.json'),
        'environment_verification': backend.environment}
    return kwargs, witness, directory


def test_execution_bridge_reconstructs_every_current_role_without_generator(tmp_path: Path, monkeypatch: Any) -> None:
    kwargs, witness, _ = bridge_fixture(tmp_path, monkeypatch)
    result = core.verify_execution_inputs(**kwargs)
    assert result['status'] == 'current_complete_inputs_match_corrected_witness'
    assert result['required_role_count'] == 21
    assert set(result['corrected_role_sha256']) == set(witness['fit_witness']['roles'])
    assert set(result['generator_training_contexts']) == {'outer'}
    assert len(result['generator_training_contexts']['outer']['training']) == 60
    assert 'generator_training_contexts' not in result['receipt']
    assert result['receipt']['content_sha256'] == pf.canonical_hash({
        key: value for key, value in result['receipt'].items() if key != 'content_sha256'})


@pytest.mark.parametrize('changed', ['heldout', 'training', 'real_array', 'seed', 'environment', 'proof'])
def test_execution_bridge_rejects_actual_input_or_proof_drift(tmp_path: Path, monkeypatch: Any, changed: str) -> None:
    kwargs, _, directory = bridge_fixture(tmp_path, monkeypatch)
    if changed == 'heldout':
        kwargs['raw'] = kwargs['raw'].copy()
        kwargs['raw'].loc[kwargs['job'].validation, 'x'] += 100
    elif changed == 'training':
        kwargs['raw'] = kwargs['raw'].copy()
        kwargs['raw'].loc[0, 'x'] += 100
    elif changed == 'real_array':
        kwargs['preflight_contexts']['outer']['real_arrays']['real_time'] = np.zeros(60)
    elif changed == 'seed':
        kwargs['preflight_contexts']['outer']['accepted_seed'] += 1
    elif changed == 'environment':
        kwargs['environment_verification'] = {'status': 'invented_changed_lock'}
    else:
        (directory / 'roles/encoded_validation.json').write_text('{}')
    with pytest.raises(pf.InvalidCheckpoint):
        core.verify_execution_inputs(**kwargs)


def test_unreached_wme_inputs_keep_all_three_generators_and_nine_candidate_recipes(tmp_path: Path) -> None:
    job, raw, backend = fixture()
    raw.event = 0
    context = core.reconstruction_inputs(job, raw, backend, contracts.seed_ledger(job.cell_id))
    assert context['p'] is None and context['inner'] == []
    record = {'status': 'input_failure', 'attempts': [], 'accepted_attempt_index': None,
              'input_error': context['input_error']}
    replay = {'status': 'input_failure', 'error': context['input_error']}
    names = ['outer', 'inner_01', 'inner_02', 'inner_03']
    values = core.make_role_values(job, context, backend, {name: (record, replay) for name in names})
    witness = core.write_role_witness(tmp_path / job.cell_id, H, job, context, values,
                                    {name: ['input_failure', H] for name in names})
    assert len(witness['fit_witness']['roles']) == 42
    assert len(witness['all_wme_candidate_slots']) == 9
    assert all(slot['dependency_status'] == 'unreachable_input_recipe_retained'
               for slot in witness['all_wme_candidate_slots'])


def test_top_pilot_scope_keeps_pending_large_owner_and_excludes_input_failures() -> None:
    def entry(identity: str, action: str, n: int, p: int) -> dict[str, Any]:
        return {'original_cell_id': identity, 'action': action, 'selection_scope': {
            'original_cell_id': identity, 'model': 'catalytic_adaptive', 'setting': 'expression',
            'gene_budget': 512, 'n_train': n, 'p': p}, 'generator_contexts': {'outer': ['accepted', H]},
            'decision': {'changed_roles': ['outer.synthetic_constructor'], 'missing_roles': [], 'generator_failures': {}}}
    large = entry('large', 'await_original_owner', 1000, 512)
    small = entry('small', 'fit_changed_inputs', 500, 512)
    failed = entry('terminal', 'retain_input_failure', 1200, 512)
    failed['decision']['generator_failures'] = {'outer': 'input_failure'}
    failed['generator_contexts']['outer'][0] = 'input_failure'
    unresolved = entry('unresolved', 'unresolved', 1500, 512)
    unresolved['decision']['missing_roles'] = ['encoded_training']
    unchanged = entry('unchanged', 'reuse_original_outcome', 2000, 512)
    unchanged['decision']['changed_roles'] = []
    assert core.pilot_input_scope([large, small, failed, unresolved, unchanged]) == [
        large['selection_scope'], small['selection_scope']]
