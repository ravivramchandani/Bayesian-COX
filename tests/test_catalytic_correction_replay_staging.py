"""Invented replay receipts; no cohort, generator, or numerical fit is run."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

ROOT = Path(__file__).absolute().parents[1] / "scripts/catalytic_correction"
spec = importlib.util.spec_from_file_location("_test_replay_stage", ROOT / "stage_replay_for_recovered_run.py")
assert spec is not None and spec.loader is not None
stage = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = stage
spec.loader.exec_module(stage)


def write(path: Path, body: dict[str, Any], pf: Any) -> dict[str, Any]:
    """Publish or replace a sealed invented record."""
    path.parent.mkdir(parents=True, exist_ok=True)
    value = pf.seal(body)
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    return value


class InventedReplay:
    """One complete accepted first draw with independent nested proof."""

    def __init__(self, root: Path, *, original_manifest_sha256: str = "2" * 64) -> None:
        self.root = root
        self.source = root / "source"
        self.preflight = root / "preflight"
        self.cell = "gbsg2__clinical__r01f01__catalytic_fixed__full"
        self.row = {"outer_cell_id": self.cell, "context": "outer",
                    "context_id": f"{self.cell}::outer", "generation_seed": 17}
        definition = {"original_manifest_sha256": original_manifest_sha256,
                           "original_input_sha256": {"invented.py": "3" * 64},
                           "environment_verification": {"status": "invented_lock_ok"},
                           "original_production_commit": "c" * 40,
                           "candidate_source_sha256": "6" * 64,
                           "correction_config_sha256": "7" * 64,
                           "correction_addendum_sha256": "8" * 64,
                           "preflight_sources": {name: stage.file_sha(ROOT / name) for name in
                                                 ("preflight_core.py", "run_preflight.py")},
                           "reuse_sources": {name: stage.file_sha(ROOT / name) for name in
                                             ("run_reuse.py", "reuse_core.py", "normal_first_draw_child.py")},
                           "contracts_sha256": stage.file_sha(ROOT / "correction_fit_contracts.py")}
        self.pf, self.preflight_module, self.core = stage.pinned_helpers(definition)
        self.definition = self.pf.seal(definition)
        self.old_manifest = {"input_paths": {"source": "/fictional/original_source",
                                             "python": "/fictional/locked/python3.11"}}
        self.name = f"replay/contexts/{self.cell}/outer/receipt.json"
        self.top_path = self.source / self.name
        self.child_dir = self.top_path.parent / "normal_original_child"
        self.request_path = self.child_dir / "request.json"
        self.child_path = self.child_dir / "receipt.json"
        self.proposal_path = self.child_dir / "proposal.npz"
        self.preflight_dir = self.preflight / "contexts" / self.cell / "outer"
        self.witness = {"n_train": 2, "processor_metadata": {"mean": 2.0}}
        write(self.preflight_dir / "input.json", {"input_witness": self.witness}, self.pf)
        self.arrays = {"synthetic_design": np.asarray([[1.0], [2.0]]),
                       "synthetic_time": np.asarray([2.0, 3.0]),
                       "hazard": np.asarray(1.0), "time_scale": np.asarray(2.0)}
        self.pf.save_arrays(self.proposal_path, self.arrays)
        first = {"status": "accepted_original_constructor", "seed": 17,
                 "array_witnesses": {key: self.pf.array_witness(value) for key, value in self.arrays.items()},
                 "legacy_metadata": {"invented": True},
                 "actual_metadata": {"processor_metadata": self.witness["processor_metadata"]}}
        self.preflight_record = write(self.preflight_dir / "receipt.json", {
            "status": "accepted_original_first_draw", "attempts": [first],
            "artifacts": {"input.json": self.pf.artifact_binding(self.preflight_dir / "input.json")}}, self.pf)
        self.request = {"definition_content_sha256": self.definition["content_sha256"],
                        "context_id": self.row["context_id"],
                        "context_row_sha256": self.pf.canonical_hash(self.row),
                        "original_generation_seed": 17,
                        "preflight_receipt_sha256": self.pf.sha256_file(self.preflight_dir / "receipt.json"),
                        "input_witness_sha256": self.pf.canonical_hash(self.witness)}
        columns = [{"column": "x", "array": {"dtype": "<f8", "shape": [2],
                                                  "values_sha256": "4" * 64}}]
        self.child_request = write(self.request_path, {"schema_version": 1, "request": self.request,
            "source": self.old_manifest["input_paths"]["source"],
            "original_input_sha256": self.definition["original_input_sha256"],
            "original_manifest_sha256": self.definition["original_manifest_sha256"],
            "preflight_core_sha256": self.definition["preflight_sources"]["preflight_core.py"],
            "child_source_sha256": self.definition["reuse_sources"]["normal_first_draw_child.py"],
            "expected_environment_verification": self.definition["environment_verification"],
            "expected_input_witness": self.witness,
            "full_raw_training_witness": {"rows": 2, "ordered_source_columns": ["x"],
                                          "columns": columns,
                                          "source_values_sha256": self.pf.canonical_hash(columns)},
            "payload_artifact": {"bytes": 9, "sha256": "5" * 64},
            "generator_receives_training_only": True,
            "owned_training_transport_not_external_pickle": True}, self.pf)
        self.child = write(self.child_path, {"schema_version": 1, "request": self.request,
            "normal_import_source_path": self.child_request["source"],
            "original_source_input_hashes": self.definition["original_input_sha256"],
            "owned_transport_sha256": self.child_request["payload_artifact"]["sha256"],
            "owned_process": {"interpreter": self.old_manifest["input_paths"]["python"],
                              "isolated": True, "dont_write_bytecode": True,
                              "parent_pid": 100, "pid": 101},
            "seed": 17, "processor_metadata": self.witness["processor_metadata"],
            "constructor_alias_restored": True, "candidate_adapter_or_helpers_imported": False,
            "no_optimizer_mcmc_model_prediction_or_score_run": True,
            "input_scope": "full_raw_training_local_preprocessor_fit; no_heldout_rows_received",
            "status": "accepted_original_constructor", "array_witnesses": first["array_witnesses"],
            "legacy_metadata": first["legacy_metadata"], "error": None,
            "artifacts": {"request.json": self.pf.artifact_binding(self.request_path),
                          "proposal.npz": self.pf.artifact_binding(self.proposal_path)}}, self.pf)
        self.top = {}
        self.outcome = {}
        self.refresh_top()

    def refresh_top(self) -> None:
        """Rebind all enclosing seals after an invented nested mutation."""
        self.top = write(self.top_path, {"schema_version": 1, "request": self.request,
            "context_id": self.row["context_id"], "status": "independent_original_first_draw_verified",
            "scope": "generator_input_and_first_proposal_identity_only; no_fit_or_evaluation_reuse_approval",
            "preflight_status": self.preflight_record["status"], "original_replay": self.child,
            "assessment": self.core.compare_first_draw(self.preflight_record, self.child, self.witness),
            "artifacts": {"normal_original_child/receipt.json": self.pf.artifact_binding(self.child_path),
                          **{f"normal_original_child/{key}": value
                             for key, value in self.child["artifacts"].items()}}}, self.pf)
        self.refresh_outcome()

    def refresh_outcome(self) -> None:
        """Bind the invented completion row to current top bytes."""
        self.outcome = {"context_id": self.row["context_id"], "receipt_path": self.name,
                        "receipt_sha256": self.pf.sha256_file(self.top_path),
                        "receipt_content_sha256": self.top["content_sha256"]}

    def verify(self) -> dict[str, dict[str, Any]]:
        """Run the actual staging verifier over this one invented context."""
        return stage.verify_context(self.source, self.row, self.outcome, self.preflight_dir,
                                    self.preflight_record, self.definition, self.old_manifest,
                                    self.pf, self.core)


def test_invented_complete_context_and_exact_copy(tmp_path: Path) -> None:
    fixture = InventedReplay(tmp_path)
    bindings = fixture.verify()
    assert set(bindings) == {fixture.name, *(f"replay/contexts/{fixture.cell}/outer/normal_original_child/{name}"
                                             for name in ("receipt.json", "request.json", "proposal.npz"))}
    copied = tmp_path / "copied"
    for relative, binding in bindings.items():
        stage.copy_bound(fixture.source / relative, copied / relative, binding, fixture.pf)
    assert stage.verify_context(copied, fixture.row, fixture.outcome, fixture.preflight_dir,
                                fixture.preflight_record, fixture.definition, fixture.old_manifest,
                                fixture.pf, fixture.core) == bindings
    stage.exact_tree(copied, set(bindings))


def test_omitted_top_proposal_cannot_hide_corrupted_nested_archive(tmp_path: Path) -> None:
    fixture = InventedReplay(tmp_path)
    with fixture.proposal_path.open("wb") as stream:
        np.savez_compressed(stream, **{**fixture.arrays, "synthetic_time": np.asarray([9.0, 10.0])})
    top = {key: value for key, value in fixture.top.items() if key != "content_sha256"}
    top["artifacts"].pop("normal_original_child/proposal.npz")
    fixture.top = write(fixture.top_path, top, fixture.pf)
    fixture.refresh_outcome()
    with pytest.raises(ValueError, match="artifact bytes changed|top replay artifacts differ"):
        fixture.verify()


def test_resealed_child_proposal_still_must_match_preflight(tmp_path: Path) -> None:
    fixture = InventedReplay(tmp_path)
    changed = {**fixture.arrays, "synthetic_time": np.asarray([9.0, 10.0])}
    with fixture.proposal_path.open("wb") as stream:
        np.savez_compressed(stream, **changed)
    child = {key: value for key, value in fixture.child.items() if key != "content_sha256"}
    child["artifacts"]["proposal.npz"] = fixture.pf.artifact_binding(fixture.proposal_path)
    child["array_witnesses"] = {key: fixture.pf.array_witness(value) for key, value in changed.items()}
    fixture.child = write(fixture.child_path, child, fixture.pf)
    top = {key: value for key, value in fixture.top.items() if key != "content_sha256"}
    top["original_replay"] = fixture.child
    top["artifacts"]["normal_original_child/receipt.json"] = fixture.pf.artifact_binding(fixture.child_path)
    top["artifacts"]["normal_original_child/proposal.npz"] = fixture.pf.artifact_binding(fixture.proposal_path)
    fixture.top = write(fixture.top_path, top, fixture.pf)
    fixture.refresh_outcome()
    with pytest.raises(ValueError, match="independent normal-import first proposal"):
        fixture.verify()


def test_stages_one_invented_context_with_only_run_path_changed(tmp_path: Path,
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    run = tmp_path / "recovered"
    run.mkdir()
    run_body = {"code": {"git_commit": "c" * 40, "git_dirty": False}, "plan": []}
    run_manifest = {**run_body, "manifest_content_sha256": stage.file_sha(ROOT / "preflight_core.py")}
    # The original run uses its own canonical manifest content field.
    import hashlib

    run_manifest["manifest_content_sha256"] = hashlib.sha256(json.dumps(
        run_body, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False).encode()).hexdigest()
    (run / "manifest.json").write_text(json.dumps(run_manifest) + "\n", encoding="utf-8")
    run_sha = stage.file_sha(run / "manifest.json")
    fixture = InventedReplay(tmp_path, original_manifest_sha256=run_sha)
    pf = fixture.pf
    pf.write_json_new(fixture.source / "definition.json", fixture.definition)
    contexts = tmp_path / "inventory/contexts.jsonl"
    contexts.parent.mkdir()
    contexts.write_text(json.dumps(fixture.row) + "\n", encoding="utf-8")
    contexts_sha = pf.sha256_file(contexts)
    preflight_manifest = write(fixture.preflight / "manifest.json", {
        "original_manifest_sha256": run_sha, "contexts_jsonl_sha256": contexts_sha,
        "original_input_sha256": fixture.definition["original_input_sha256"],
        "environment_verification": fixture.definition["environment_verification"],
        "candidate_source_sha256": fixture.definition["candidate_source_sha256"],
        "correction_config_sha256": fixture.definition["correction_config_sha256"],
        "correction_addendum_sha256": fixture.definition["correction_addendum_sha256"]}, pf)
    write(fixture.preflight / "completion.json", {
        "run_binding_sha256": preflight_manifest["content_sha256"]}, pf)
    old_manifest = write(fixture.source / "manifest.json", {"schema_version": 1,
        "definition_content_sha256": fixture.definition["content_sha256"],
        "preflight_manifest_sha256": pf.sha256_file(fixture.preflight / "manifest.json"),
        "preflight_completion_sha256": pf.sha256_file(fixture.preflight / "completion.json"),
        "scientific_method_approved": False, "corrected_fit_freeze_created": False,
        "source_sha256": fixture.definition["reuse_sources"],
        "input_paths": {"source": fixture.old_manifest["input_paths"]["source"],
                        "python": fixture.old_manifest["input_paths"]["python"],
                        "run": "/fictional/interrupted_run", "inventory": str(contexts.parent),
                        "preflight_output": str(fixture.preflight)}}, pf)
    write(fixture.source / "replay/completion.json", {"schema_version": 1,
        "status": "all1650_independent_first_draw_contexts_accounted",
        "definition_content_sha256": fixture.definition["content_sha256"],
        "scheduled_contexts": 1, "accounted_contexts": 1,
        "no_fit_optimizer_mcmc_prediction_or_score_run": True,
        "outcomes": [fixture.outcome],
        "artifacts": {str(Path(fixture.name).relative_to("replay")):
                      pf.artifact_binding(fixture.top_path)}}, pf)
    continuation = run / "recovery_continuation.json"
    continuation.write_text('{"invented":true}\n', encoding="utf-8")
    monkeypatch.setattr(stage, "CONTEXTS", 1)
    monkeypatch.setattr(stage, "pinned_helpers", lambda _: (
        pf, fixture.preflight_module, fixture.core))
    monkeypatch.setattr(fixture.preflight_module, "validate_inventory", lambda rows, manifest: (
        rows == [fixture.row] and manifest == run_manifest) or (_ for _ in ()).throw(ValueError("rows differ")))

    class Complete:
        def __init__(self, root: Path, rows: list[dict[str, Any]], *, expected_count: int) -> None:
            assert root == fixture.preflight and rows == [fixture.row] and expected_count == 1

        def context(self, row: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
            assert row == fixture.row
            return fixture.preflight_dir, fixture.preflight_record

    monkeypatch.setattr(fixture.core, "CompletePreflight", Complete)
    original_loader = stage.load_pinned

    def load(path: Path, name: str, digest: str) -> Any:
        if name == "_stage_recovered_lineage":
            return SimpleNamespace(verify_recovered_lineage=lambda _: {
                "status": "recovered_lineage_verified", "stored_cells": 1625,
                "manifest_sha256": run_sha, "final_lineage_sha256": pf.sha256_file(continuation)})
        return original_loader(path, name, digest)

    monkeypatch.setattr(stage, "load_pinned", load)
    destination = tmp_path / "staged"
    args = SimpleNamespace(source_replay=fixture.source, destination=destination, recovered_run=run,
        preflight_output=fixture.preflight, contexts=contexts,
        definition_sha256=pf.sha256_file(fixture.source / "definition.json"),
        source_manifest_sha256=pf.sha256_file(fixture.source / "manifest.json"),
        replay_completion_sha256=pf.sha256_file(fixture.source / "replay/completion.json"),
        preflight_manifest_sha256=pf.sha256_file(fixture.preflight / "manifest.json"),
        preflight_completion_sha256=pf.sha256_file(fixture.preflight / "completion.json"),
        contexts_sha256=contexts_sha, recovered_run_manifest_sha256=run_sha,
        recovery_continuation_sha256=pf.sha256_file(continuation),
        recovery_lineage_verifier_sha256=stage.file_sha(ROOT.parent / "extension_release/recovery_lineage.py"))
    result = stage.stage(args)
    assert result["staged_files"] == 7 and result["staged_contexts"] == 1
    assert (destination / "definition.json").read_bytes() == (fixture.source / "definition.json").read_bytes()
    assert (destination / "replay/completion.json").read_bytes() == (
        fixture.source / "replay/completion.json").read_bytes()
    staged_manifest = pf.read_sealed(destination / "manifest.json")
    assert staged_manifest["input_paths"] == {**old_manifest["input_paths"], "run": str(run)}
    assert {key: value for key, value in staged_manifest.items() if key not in {"input_paths", "content_sha256"}} == {
        key: value for key, value in old_manifest.items() if key not in {"input_paths", "content_sha256"}}
    assert pf.read_sealed(tmp_path / "staged.replay-stage.json")["corrected_fits_executed"] is False
    stage.exact_tree(destination, {"definition.json", "manifest.json", "replay/completion.json",
                                   *fixture.verify()})
