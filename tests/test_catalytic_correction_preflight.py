"""Invented frames and injected proposals; no real cohorts, SVD or model fits."""

from __future__ import annotations

import contextlib
import io
import json
import os
import socket
import sys
import tarfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import numpy as np
import pandas as pd
import pytest

from scripts.catalytic_correction import preflight_core as core
from scripts.catalytic_correction import run_preflight as cli


@pytest.fixture(scope="module")
def candidate():
    """Import reviewed wrapper bytes; tests never instantiate its real adapter."""
    path = Path(__file__).absolute().parents[1] / "src/pipelines/extensions/correction_generator.py"
    return cli.load_candidate(path, core.sha256_file(path))


class FakeProcessor:
    """An observable training-only transformation for invented fixtures."""

    def __init__(self, training):
        self.fitted_ids = training.subject_id.tolist()
        self.feature_names = ["x", "category=B"]
        self.clinical = SimpleNamespace(required_source_columns=["x", "category"])
        self.genes = []

    def transform(self, frame):
        return pd.DataFrame({"x": frame.x.astype(float), "category=B": (frame.category == "B").astype(float)}, index=frame.index)

    def metadata(self):
        return {"clinical": {"category_levels": {"category": ["A", "B"]}},
                "feature_names": self.feature_names, "fitted_ids": self.fitted_ids,
                "state_sha256": core.canonical_hash(self.fitted_ids)}


class FakeBackend:
    """Expose exact call order and training membership without real data code."""

    def __init__(self):
        self.split_inputs = []
        self.fit_ids = []
        self.original = None
        self.boundary_checks = 0

    def feature_spec(self, _dataset):
        return {"numeric": ["x"], "categorical": ["category"]}

    def apply_censor(self, times, events, cutoff):
        if cutoff is None:
            return times.copy(), events.copy()
        return np.minimum(times, cutoff), (events.astype(bool) & (times <= cutoff)).astype(int)

    def inner_folds(self, times, events, seed):
        self.split_inputs.append((times.copy(), events.copy(), seed))
        result = []
        indices = np.arange(len(times))
        for number, validation in enumerate(np.array_split(indices, 3), 1):
            result.append(SimpleNamespace(fold=number, seed=seed, train_indices=indices[~np.isin(indices, validation)], validation_indices=validation))
        return result

    def preprocess(self, _specification, _budget, training):
        self.fit_ids.append(training.subject_id.tolist())
        return FakeProcessor(training)

    def original_cell(self, _cell_id):
        if self.original is None:
            return None
        return self.original, core.canonical_hash(self.original)

    def verify_boundary(self):
        self.boundary_checks += 1


def fixture(candidate, *, inner=None, cutoff=45.0):
    """Build a deliberately separate held-out group and censored training tail."""
    raw = pd.DataFrame({"subject_id": [f"invented-{index}" for index in range(70)],
                        "duration": np.arange(1, 71, dtype=float), "event": np.ones(70, dtype=int),
                        "x": np.arange(70, dtype=float), "category": ["A", "B"] * 35})
    model = "catalytic_wme" if inner is not None else "catalytic_fixed"
    cell_id = f"gbsg2__clinical__r01f01__{model}__admin_q0.75"
    seed = candidate.deterministic_seed(260817, "extensions", cell_id)
    inner_seed = candidate.deterministic_seed(seed, "inner_cv")
    row = {"outer_cell_id": cell_id, "context_id": f"{cell_id}::{('outer' if inner is None else f'inner_{inner:02d}')}",
           "context": "outer" if inner is None else "inner", "inner_fold": inner,
           "dataset": "gbsg2", "setting": "clinical", "model": model, "repeat": 1, "fold": 1,
           "condition": "admin_q0.75", "gene_budget": 0, "censoring_cutoff_from_manifest": cutoff,
           "outer_train_sha256_from_manifest": core.canonical_hash(raw.subject_id.iloc[:60].tolist()),
           "outer_validation_sha256_from_manifest": core.canonical_hash(raw.subject_id.iloc[60:].tolist()),
           "generation_seed": candidate.deterministic_seed(seed, "outer_prior") if inner is None else candidate.deterministic_seed(inner_seed, "inner_prior", inner),
           "cell_seed": seed, "inner_cv_seed": inner_seed, "inner_split_seed": None if inner is None else inner_seed,
           "original_outer_fit_attempt_seeds": [candidate.deterministic_seed(seed, "fit_attempt", index) for index in range(1 if model == "catalytic_wme" else 3)],
           "outer_evaluation_seed": seed,
           "shared_tau_candidate_uses": [] if inner is None else [{"candidate_index_zero_based": index, "tau_multiplier": value,
                                                                  "inner_fit_seed": candidate.deterministic_seed(inner_seed, "inner_fit", inner, index)} for index, value in enumerate((0.25, 1.0, 4.0))]}
    job = SimpleNamespace(train=np.arange(60), validation=np.arange(60, 70), censoring_cutoff=cutoff, gene_budget=0, dataset="gbsg2")
    return row, job, raw


def make_proposal(candidate, inputs, seed, *, rejected=False):
    design = np.asarray([[1., 0.], [2., 0. if rejected else 1.], [3., 0.], [4., 0. if rejected else 1.]])
    prior_time = np.asarray([1., 2., 3., 4.])
    data = candidate.SyntheticInputs(design, prior_time, 0.5)
    legacy = None if rejected else {"seed": seed, "M": 4, "p": 2, "time_scale": 3.0,
                                   "hazard_scaled": 0.5, "synthetic_sha256": data.hashes()["synthetic_sha256"]}
    return candidate.DrawProposal(data, legacy, {"seed": seed, "processor_metadata": inputs.processor.metadata(),
                                               "feature_names": inputs.processor.feature_names, "time_scale": 3.0})


def engine(tmp_path, candidate, backend, outcomes=None, *, cap=2, binding="fixture-binding"):
    calls = []
    outcomes = list(outcomes or ["accepted"])

    def factory(inputs):
        def draw(seed):
            calls.append((seed, inputs.training.subject_id.tolist()))
            item = outcomes.pop(0) if outcomes else "accepted"
            if isinstance(item, BaseException):
                raise item
            proposal = make_proposal(candidate, inputs, seed, rejected=item == "rank")
            if item == "rank":
                raise candidate.FrozenRankRejection(proposal)
            return proposal
        return draw

    diagnostics = Mock(return_value={"status": "fake_measurement_no_svd", "rank": 2})
    return core.PreflightEngine(tmp_path, binding, candidate, backend, factory, cap=cap, diagnostics=diagnostics), calls


def test_censorship_precedes_inner_split_and_training_only_preprocessing(candidate):
    row, job, raw = fixture(candidate, inner=1)
    backend = FakeBackend()
    inputs = core.build_context(row, job, raw, backend)
    split_time, split_event, split_seed = backend.split_inputs[0]
    assert np.max(split_time) == 45 and split_event.sum() == 45
    assert split_seed == row["inner_cv_seed"]
    assert backend.fit_ids == [raw.subject_id.iloc[20:60].tolist()]
    assert inputs.training.subject_id.tolist() == raw.subject_id.iloc[20:60].tolist()
    assert inputs.event.sum() == 25
    assert set(inputs.training.subject_id).isdisjoint(raw.subject_id.iloc[:20])
    assert set(inputs.training.subject_id).isdisjoint(raw.subject_id.iloc[60:])


def test_held_out_values_cannot_change_generator_inputs(candidate):
    row, job, raw = fixture(candidate, inner=1)
    before = core.build_context(row, job, raw, FakeBackend())
    raw.loc[60:, ["duration", "x"]] = 1e10
    raw.loc[60:, "event"] = 0
    raw.loc[60:, "category"] = "NEVER_TRAINED"
    after = core.build_context(row, job, raw, FakeBackend())
    assert before.witness == after.witness
    pd.testing.assert_frame_equal(before.training, after.training)


def test_explicit_restoration_narrows_adapter_input_and_passes_complete_state(candidate, tmp_path):
    row, job, raw = fixture(candidate)
    inputs = core.build_context(row, job, raw, FakeBackend())
    constructor = Mock()
    injected = SimpleNamespace(IsolatedOriginalAdapter=constructor)
    args = SimpleNamespace(source=tmp_path, python=tmp_path / "python", restore_processor_state=True)
    cli.make_adapter(injected, args, inputs)
    arguments, keywords = constructor.call_args
    assert arguments[1].columns.tolist() == ["x", "category"]
    assert "subject_id" not in arguments[1]
    assert keywords["processor_metadata"] == inputs.processor.metadata()
    assert keywords["gene_budget"] == 0
    assert np.array_equal(arguments[3], inputs.time) and np.array_equal(arguments[4], inputs.event)
    args.restore_processor_state = False
    cli.make_adapter(injected, args, inputs)
    assert constructor.call_args.args[1] is inputs.training
    assert "processor_metadata" not in constructor.call_args.kwargs


def test_membership_and_split_seed_mismatches_abort(candidate):
    row, job, raw = fixture(candidate, inner=1)
    row["outer_train_sha256_from_manifest"] = "altered"
    with pytest.raises(core.InvalidCheckpoint, match="membership"):
        core.build_context(row, job, raw, FakeBackend())
    row, job, raw = fixture(candidate, inner=1)
    row["inner_split_seed"] += 1
    with pytest.raises(core.InvalidCheckpoint, match="recipe"):
        core.build_context(row, job, raw, FakeBackend())


def test_first_draw_arrays_sealed_and_resume_uses_no_proposal_calls(tmp_path, candidate):
    row, job, raw = fixture(candidate)
    backend = FakeBackend()
    runner, calls = engine(tmp_path, candidate, backend)
    with patch.object(np.linalg, "svd", side_effect=AssertionError("no real SVD allowed")), patch.object(np.linalg, "matrix_rank", side_effect=AssertionError("no real rank call allowed")):
        first = runner.run_context(row, job, raw)
        again = runner.run_context(row, job, raw)
    assert first == again and len(calls) == 1
    assert first["status"] == "accepted_original_first_draw"
    assert first["accepted_attempt_index"] == 0 and first["fit_reuse_certified"] is False
    path = runner.context_directory(row)
    arrays = core.read_arrays(path / "inputs.npz")
    assert set(arrays) == {"real_design", "real_time", "real_event"}
    proposal = core.read_arrays(path / "attempt_000" / "proposal.npz")
    assert set(proposal) == {"synthetic_design", "synthetic_time", "hazard", "time_scale"}
    assert first["attempts"][0]["array_witnesses"] == {name: core.array_witness(array) for name, array in proposal.items()}


def test_rank_redraw_preserves_original_rejected_draw(tmp_path, candidate):
    row, job, raw = fixture(candidate)
    runner, calls = engine(tmp_path, candidate, FakeBackend(), ["rank", "accepted"])
    record = runner.run_context(row, job, raw)
    assert record["status"] == "accepted_rank_conditioned_redraw" and record["accepted_attempt_index"] == 1
    assert [seed for seed, _ids in calls] == [row["generation_seed"], candidate.deterministic_seed(row["generation_seed"], candidate.RETRY_LABEL, 1)]
    assert record["attempts"][0]["legacy_metadata"] is None
    assert record["attempts"][0]["status"] == "frozen_rank_rejected"
    assert (runner.context_directory(row) / "attempt_000" / "proposal.npz").is_file()


def test_cap_exhaustion_and_nonrank_failure_after_rank_have_distinct_outcomes(tmp_path, candidate):
    row, job, raw = fixture(candidate)
    runner, calls = engine(tmp_path / "exhausted", candidate, FakeBackend(), ["rank", "rank"])
    exhausted = runner.run_context(row, job, raw)
    assert exhausted["status"] == "exhausted_rank_cap" and len(calls) == 2
    assert exhausted["candidate_metadata"]["exhausted"] is True
    other, calls = engine(tmp_path / "other", candidate, FakeBackend(), ["rank", ValueError("bad reference hazard"), "accepted"])
    failed = other.run_context(row, job, raw)
    assert failed["status"] == "nonrank_failure" and len(calls) == 2
    assert failed["nonrank_error"]["type"] == "builtins.ValueError"
    assert failed["attempts"][-1]["status"] == "nonrank_error"
    again, resumed_calls = engine(tmp_path / "other", candidate, FakeBackend())
    assert again.run_context(row, job, raw) == failed and resumed_calls == []


def test_rank_message_without_original_guard_tag_is_not_retried(tmp_path, candidate):
    row, job, raw = fixture(candidate)
    runner, calls = engine(tmp_path, candidate, FakeBackend(), [ValueError(candidate.RANK_MESSAGE)])
    record = runner.run_context(row, job, raw)
    assert record["status"] == "nonrank_failure" and len(calls) == 1


def test_resume_after_interrupt_reuses_only_verified_completed_attempt(tmp_path, candidate):
    row, job, raw = fixture(candidate)
    runner, calls = engine(tmp_path, candidate, FakeBackend(), ["rank", KeyboardInterrupt()])
    with pytest.raises(KeyboardInterrupt):
        runner.run_context(row, job, raw)
    rejected_path = runner.context_directory(row) / "attempt_000" / "proposal.npz"
    rejected_hash = core.sha256_file(rejected_path)
    resumed, next_calls = engine(tmp_path, candidate, FakeBackend())
    record = resumed.run_context(row, job, raw)
    assert len(calls) == 2 and len(next_calls) == 1
    assert next_calls[0][0] == candidate.deterministic_seed(row["generation_seed"], candidate.RETRY_LABEL, 1)
    assert record["status"] == "accepted_rank_conditioned_redraw"
    assert core.sha256_file(rejected_path) == rejected_hash


@pytest.mark.parametrize("corruption", ["array", "receipt", "extra_attempt"])
def test_invalid_saved_checkpoint_aborts_without_new_draw_or_overwrite(tmp_path, candidate, corruption):
    row, job, raw = fixture(candidate)
    runner, calls = engine(tmp_path, candidate, FakeBackend())
    runner.run_context(row, job, raw)
    directory = runner.context_directory(row)
    if corruption == "array":
        (directory / "attempt_000" / "proposal.npz").write_bytes(b"changed")
    elif corruption == "receipt":
        value = json.loads((directory / "receipt.json").read_text())
        value["accepted_attempt_index"] = 20
        (directory / "receipt.json").write_text(json.dumps(value))
    else:
        (directory / "attempt_009").mkdir()
    snapshot = {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob("*") if path.is_file()}
    with pytest.raises(core.InvalidCheckpoint):
        runner.run_context(row, job, raw)
    assert len(calls) == 1
    assert snapshot == {str(path.relative_to(directory)): path.read_bytes() for path in directory.rglob("*") if path.is_file()}


def test_partial_archive_and_changed_binding_are_not_silently_skipped(tmp_path, candidate):
    row, job, raw = fixture(candidate)
    runner, _calls = engine(tmp_path / "partial", candidate, FakeBackend())
    attempt = runner.context_directory(row) / "attempt_000"
    attempt.mkdir(parents=True)
    (attempt / "proposal.npz").write_bytes(b"unbound-partial")
    with pytest.raises(core.InvalidCheckpoint, match="partial"):
        runner.run_context(row, job, raw)
    runner, _calls = engine(tmp_path / "changed", candidate, FakeBackend())
    runner.run_context(row, job, raw)
    new_runner, calls = engine(tmp_path / "changed", candidate, FakeBackend(), binding="different")
    with pytest.raises(core.InvalidCheckpoint, match="witness"):
        new_runner.run_context(row, job, raw)
    assert calls == []


def test_input_failure_retained_and_cannot_turn_into_acceptance_in_same_output(tmp_path, candidate):
    row, job, raw = fixture(candidate, cutoff=10.0)
    runner, calls = engine(tmp_path, candidate, FakeBackend())
    failed = runner.run_context(row, job, raw)
    assert failed["status"] == "input_failure" and calls == []
    assert runner.run_context(row, job, raw) == failed
    raw.loc[:59, "duration"] = 1.0
    with pytest.raises(core.InvalidCheckpoint, match="saved input failure"):
        runner.run_context(row, job, raw)


def test_diagnostic_error_preserves_constructor_result_and_no_retry(tmp_path, candidate):
    row, job, raw = fixture(candidate)
    runner, calls = engine(tmp_path, candidate, FakeBackend())
    runner.diagnostics = Mock(side_effect=RuntimeError("diagnostic unavailable"))
    record = runner.run_context(row, job, raw)
    assert len(calls) == 1 and record["status"] == "accepted_original_first_draw"
    assert record["attempts"][0]["rank_measurement"]["status"] == "measurement_unavailable"


def test_rank_measurement_support_uses_injected_singular_values_only(candidate):
    row, job, raw = fixture(candidate)
    inputs = core.build_context(row, job, raw, FakeBackend())
    proposal = make_proposal(candidate, inputs, 7, rejected=True)
    with patch.object(np.linalg, "svd", return_value=np.asarray([1.0, 0.0])) as fake_svd:
        measured = core.rank_diagnostics(proposal, inputs)
    fake_svd.assert_called_once()
    assert measured["rank"] == 1
    assert measured["zero_encoded_columns"] == ["category=B"]
    omitted = next(item for item in measured["category_support"] if item["level"] == "B")
    assert omitted["training_count"] == 30 and omitted["synthetic_count"] == 0
    assert omitted["omitted_in_proposal"] is True


def test_original_witness_match_never_certifies_fit_reuse_and_late_original_is_separate(tmp_path, candidate):
    row, job, raw = fixture(candidate)
    backend = FakeBackend()
    runner, _calls = engine(tmp_path, candidate, backend)
    record = runner.run_context(row, job, raw)
    directory = runner.context_directory(row)
    assert (directory / "comparisons" / "not_recorded.json").exists()
    inputs = core.build_context(row, job, raw, backend)
    original = {"cell_id": row["outer_cell_id"], "status": "failed_diagnostics",
                "preprocessing": inputs.processor.metadata(),
                "synthetic_prior_data": record["attempts"][0]["legacy_metadata"]}
    original["cell_content_sha256"] = core.canonical_hash(original)
    backend.original = original
    assert runner.run_context(row, job, raw) == record
    comparisons = list((directory / "comparisons").glob("*.json"))
    assert len(comparisons) == 2
    observed = core.read_sealed(next(path for path in comparisons if path.stem != "not_recorded"))["assessment"]
    assert observed["status"] == "stored_preprocessing_and_legacy_metadata_exact_match"
    assert observed["original_status"] == "failed_diagnostics"
    assert observed["fit_reuse_certified"] is False
    inner, _job, _raw = fixture(candidate, inner=1)
    assessment = core.compare_original(original, inner, inputs, record["attempts"], 0)
    assert assessment["status"] == "original_inner_inputs_not_saved_unresolved"


def test_whole_coverage_includes_all_three_shared_wme_inner_positions(tmp_path, candidate):
    inner_rows = [fixture(candidate, inner=index)[0] for index in (1, 2, 3)]
    outer, job, raw = fixture(candidate, inner=1)
    outer = {**outer, "context": "outer", "inner_fold": None, "context_id": f"{outer['outer_cell_id']}::outer",
             "generation_seed": candidate.deterministic_seed(outer["cell_seed"], "outer_prior"),
             "inner_split_seed": None, "shared_tau_candidate_uses": []}
    rows = [outer, *inner_rows]
    backend = FakeBackend()
    runner, calls = engine(tmp_path, candidate, backend)
    with contextlib.redirect_stdout(io.StringIO()):
        partial = runner.execute(rows, {outer["outer_cell_id"]: job}, {"gbsg2": raw}, limit=1)
        completed = runner.execute(rows, {outer["outer_cell_id"]: job}, {"gbsg2": raw})
        again = runner.execute(rows, {outer["outer_cell_id"]: job}, {"gbsg2": raw})
    assert partial["status"] == "partial_context_pass"
    assert completed == again and completed["accounted_contexts"] == 4
    assert completed["outcome_counts"] == {"accepted_original_first_draw": 4}
    assert len(calls) == 4
    assert all(item["fit_reuse_certified"] is False for item in (partial, completed))
    assert backend.boundary_checks == 3


def test_claim_collision_and_explicit_dead_local_recovery(tmp_path):
    path = tmp_path / "claim.json"
    with core.Claim(path, "run"):
        with pytest.raises(core.InvalidCheckpoint, match="already exists"):
            with core.Claim(path, "run"):
                pytest.fail("second owner acquired the claim")
    dead = core.seal({"schema_version": 1, "run_binding_sha256": "run", "pid": 99999999,
                      "host": socket.gethostname(), "nonce": "old", "created_at_utc": "invented"})
    core.write_json_new(path, dead)
    with patch.object(os, "kill", side_effect=ProcessLookupError):
        with core.Claim(path, "run", recover_stale=True):
            assert core.read_sealed(path)["nonce"] != "old"
    assert core.read_sealed(tmp_path / "abandoned_claims" / "old.json") == dead


def test_no_replace_and_object_archive_refusal(tmp_path):
    path = tmp_path / "record.json"
    core.write_json_new(path, {"actual": 1})
    with pytest.raises(FileExistsError):
        core.write_json_new(path, {"actual": 2})
    assert json.loads(path.read_text()) == {"actual": 1}
    with pytest.raises(ValueError, match="object"):
        core.save_arrays(tmp_path / "object.npz", {"bad": np.asarray([object()], dtype=object)})


def test_scalar_array_witness_preserves_zero_dimensional_archive_shape(tmp_path):
    scalar = np.asarray(0.5, dtype=float)
    witness = core.array_witness(scalar)
    assert witness["shape"] == []
    core.save_arrays(tmp_path / "scalar.npz", {"hazard": scalar})
    restored = core.read_arrays(tmp_path / "scalar.npz")["hazard"]
    assert restored.shape == () and core.array_witness(restored) == witness


def test_inventory_counts_and_seed_tampering_checked_without_real_cohort_loading():
    inventory = Path(__file__).absolute().parents[1] / "coordination/recovery/2026-09-29-generator-correction-inventory.tar.gz"
    with tarfile.open(inventory, "r:gz") as archive:
        rows = [json.loads(line) for line in archive.extractfile("contexts.jsonl").read().decode().splitlines()]
        bindings = json.loads(archive.extractfile("source_bindings.json").read())
    manifest = {"plan": [{"cell_id": row["outer_cell_id"], "train_sha256": row["outer_train_sha256_from_manifest"],
                          "validation_sha256": row["outer_validation_sha256_from_manifest"], "censoring_cutoff": row["censoring_cutoff_from_manifest"]} for row in rows if row["context"] == "outer"]}
    assert bindings["sealed_source_commit"] == cli.PRODUCTION_COMMIT
    cli.validate_inventory(rows, manifest)
    rows[1]["generation_seed"] += 1
    with pytest.raises(core.InvalidCheckpoint, match="seed"):
        cli.validate_inventory(rows, manifest)


def test_foreign_src_namespace_fails_before_source_or_cohort_operations():
    with patch.dict(sys.modules, {"src": SimpleNamespace(__file__="foreign")}), patch.object(cli, "verify_bindings") as bindings:
        with pytest.raises(core.InvalidCheckpoint, match="foreign src"):
            cli.FrozenBackend(SimpleNamespace(), {})
        bindings.assert_not_called()


def test_candidate_byte_mismatch_and_linked_paths_fail_closed(tmp_path):
    source = tmp_path / "candidate.py"
    source.write_text("raise AssertionError('must not execute')")
    with pytest.raises(core.InvalidCheckpoint, match="candidate source"):
        cli.load_candidate(source, "0" * 64)
    linked = tmp_path / "linked"
    linked.symlink_to(source)
    with pytest.raises(core.InvalidCheckpoint, match="linked"):
        cli.safe_absolute(linked)


def test_conda_interpreter_alias_resolves_only_to_current_interpreter(tmp_path):
    binary = tmp_path / "python3.11"
    binary.write_bytes(b"invented-not-executed")
    alias = tmp_path / "python"
    alias.symlink_to(binary)
    with patch.object(sys, "executable", str(binary)):
        assert cli.locked_interpreter(alias) == binary
    with pytest.raises(core.InvalidCheckpoint, match="same explicit lock"):
        cli.locked_interpreter(alias)
