"""Carry a complete first-draw replay into a fresh recovered-run output.

This copies only sealed replay evidence. It does not run a generator, fit a model,
or approve corrected fits. The frozen reuse runner remains byte-identical.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any

CONTEXTS = 1650
HEX_SHA = re.compile(r"[0-9a-f]{64}\Z")
CHILD_ARTIFACTS = {"proposal.npz", "request.json"}
TOP_ARTIFACTS = {f"normal_original_child/{name}" for name in CHILD_ARTIFACTS | {"receipt.json"}}
NUMERIC_KEYS = {"synthetic_design", "synthetic_time", "hazard", "time_scale"}


def require(condition: bool, message: str) -> None:
    """Reject an incomplete or foreign replay before publication."""
    if not condition:
        raise ValueError(message)


def checked_path(path: Path, *, exists: bool = True) -> Path:
    """Keep input and output paths absolute, ordinary, and link-free."""
    require(path.is_absolute() and ".." not in path.parts, f"unsafe path: {path}")
    require(not any(item.is_symlink() for item in (path, *path.parents)), f"linked path: {path}")
    if exists:
        require(path.exists(), f"missing path: {path}")
    return path


def file_sha(path: Path) -> str:
    """Hash a file without loading its contents into memory."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_pinned(path: Path, name: str, digest: str) -> Any:
    """Import an exact local helper under a private namespace."""
    checked_path(path)
    require(path.is_file() and file_sha(path) == digest, f"helper bytes differ: {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None and spec.loader is not None, f"cannot import helper: {path.name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def pinned_helpers(definition: dict[str, Any]) -> tuple[Any, Any, Any]:
    """Use the same exact comparison and preflight code that made the replay."""
    directory = Path(__file__).parent
    preflight_pins = definition["preflight_sources"]
    reuse_pins = definition["reuse_sources"]
    pf = load_pinned(directory / "preflight_core.py", "_stage_replay_pf", preflight_pins["preflight_core.py"])
    contracts = load_pinned(directory / "correction_fit_contracts.py", "_stage_replay_contracts",
                            definition["contracts_sha256"])
    previous = {name: sys.modules.get(name) for name in
                ("preflight_core", "_reuse_bound_core", "_reuse_bound_contracts")}
    try:
        sys.modules["preflight_core"] = pf
        sys.modules["_reuse_bound_core"] = pf
        sys.modules["_reuse_bound_contracts"] = contracts
        preflight = load_pinned(directory / "run_preflight.py", "_stage_replay_preflight",
                                preflight_pins["run_preflight.py"])
        core = load_pinned(directory / "reuse_core.py", "_stage_replay_core", reuse_pins["reuse_core.py"])
    finally:
        for name, value in previous.items():
            if value is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = value
    for name in ("run_reuse.py", "normal_first_draw_child.py"):
        require(file_sha(checked_path(directory / name)) == reuse_pins[name], f"frozen reuse source differs: {name}")
    return pf, preflight, core


def read_pinned(path: Path, digest: str, pf: Any) -> dict[str, Any]:
    """Require both explicit file bytes and the canonical content seal."""
    checked_path(path)
    require(path.is_file() and file_sha(path) == digest, f"pinned evidence bytes differ: {path}")
    return pf.read_sealed(path)


def context_name(row: dict[str, Any]) -> str:
    """Derive the only replay directory allowed for a validated recipe row."""
    require(row["context"] in {"outer", "inner"}, "invalid context kind")
    name = "outer" if row["context"] == "outer" else f"inner_{row['inner_fold']:02d}"
    require(row["context_id"] == f"{row['outer_cell_id']}::{name}", "context ID differs from row")
    require(re.fullmatch(r"[a-z0-9_.]+", row["outer_cell_id"]) is not None, "unsafe cell ID")
    return name


def verify_context(root: Path, row: dict[str, Any], outcome: dict[str, Any],
                   preflight_directory: Path, preflight_record: dict[str, Any],
                   definition: dict[str, Any], old_manifest: dict[str, Any],
                   pf: Any, core: Any) -> dict[str, dict[str, Any]]:
    """Check one top receipt, its independent child, and numeric witnesses."""
    name = context_name(row)
    relative = f"replay/contexts/{row['outer_cell_id']}/{name}/receipt.json"
    require(outcome["context_id"] == row["context_id"] and outcome["receipt_path"] == relative,
            "replay outcome path or identity differs")
    path = core.checked_path(root, relative)
    top = core.verified_json(path)
    require(pf.sha256_file(path) == outcome["receipt_sha256"]
            and top["content_sha256"] == outcome["receipt_content_sha256"],
            "top replay receipt differs from completion")
    require(top["schema_version"] == 1 and top["context_id"] == row["context_id"]
            and top["status"] == "independent_original_first_draw_verified"
            and top["scope"] == "generator_input_and_first_proposal_identity_only; no_fit_or_evaluation_reuse_approval"
            and top["preflight_status"] == preflight_record["status"]
            and preflight_record["status"] != "input_failure", "top replay scope or status differs")
    saved_input = core.verified_json(preflight_directory / "input.json",
                                    preflight_record["artifacts"]["input.json"])
    witness = saved_input["input_witness"]
    request = {"definition_content_sha256": definition["content_sha256"],
               "context_id": row["context_id"], "context_row_sha256": pf.canonical_hash(row),
               "original_generation_seed": row["generation_seed"],
               "preflight_receipt_sha256": pf.sha256_file(preflight_directory / "receipt.json"),
               "input_witness_sha256": pf.canonical_hash(witness)}
    require(top["request"] == request, "top replay request differs from row/preflight")
    require(set(top["artifacts"]) == TOP_ARTIFACTS, "top replay artifacts differ")
    child_directory = path.parent / "normal_original_child"
    child_request_path = child_directory / "request.json"
    child_path = child_directory / "receipt.json"
    checked_path(child_request_path)
    checked_path(child_path)
    child_request = core.verified_json(child_request_path)
    child = core.verified_json(child_path)
    require(child_request["schema_version"] == child["schema_version"] == 1
            and child_request["request"] == child["request"] == request,
            "independent child request differs")
    require(child_request["source"] == old_manifest["input_paths"]["source"]
            and child_request["original_input_sha256"] == definition["original_input_sha256"]
            and child_request["original_manifest_sha256"] == definition["original_manifest_sha256"]
            and child_request["preflight_core_sha256"] == definition["preflight_sources"]["preflight_core.py"]
            and child_request["child_source_sha256"] == definition["reuse_sources"]["normal_first_draw_child.py"]
            and child_request["expected_environment_verification"] == definition["environment_verification"]
            and child_request["expected_input_witness"] == witness
            and child_request["generator_receives_training_only"] is True
            and child_request["owned_training_transport_not_external_pickle"] is True,
            "independent child input/source binding differs")
    raw = child_request["full_raw_training_witness"]
    require(raw["rows"] == witness["n_train"]
            and raw["ordered_source_columns"] == [item["column"] for item in raw["columns"]]
            and raw["source_values_sha256"] == pf.canonical_hash(raw["columns"]),
            "independent child full raw training witness differs")
    require(child["normal_import_source_path"] == child_request["source"]
            and child["original_source_input_hashes"] == child_request["original_input_sha256"]
            and child["owned_transport_sha256"] == child_request["payload_artifact"]["sha256"]
            and child["seed"] == row["generation_seed"]
            and child["processor_metadata"] == witness["processor_metadata"]
            and child["constructor_alias_restored"] is True
            and child["candidate_adapter_or_helpers_imported"] is False
            and child["no_optimizer_mcmc_model_prediction_or_score_run"] is True
            and child["input_scope"] == "full_raw_training_local_preprocessor_fit; no_heldout_rows_received"
            and child["owned_process"]["interpreter"] == old_manifest["input_paths"]["python"]
            and child["owned_process"]["isolated"] is True
            and child["owned_process"]["dont_write_bytecode"] is True
            and child["status"] in {"accepted_original_constructor", "frozen_rank_rejected"}
            and set(child["artifacts"]) == CHILD_ARTIFACTS,
            "independent child scope/status differs")
    require(top["original_replay"] == child, "embedded child result differs from child receipt")
    child_bindings = {"normal_original_child/receipt.json": pf.artifact_binding(child_path),
                      **{f"normal_original_child/{key}": binding for key, binding in child["artifacts"].items()}}
    require(top["artifacts"] == child_bindings, "top/child artifact maps differ")
    core.numeric_archive(child_directory / "proposal.npz", child["artifacts"]["proposal.npz"],
                         child["array_witnesses"], NUMERIC_KEYS)
    require(top["assessment"] == core.compare_first_draw(preflight_record, child, witness),
            "independent first-draw assessment differs")
    return {relative: pf.artifact_binding(path),
            **{f"replay/contexts/{row['outer_cell_id']}/{name}/{key}": binding
               for key, binding in top["artifacts"].items()}}


def copy_bound(source: Path, destination: Path, binding: dict[str, Any], pf: Any) -> None:
    """Copy one already audited file and recheck both ends after publication."""
    checked_path(source)
    require(source.is_file() and pf.artifact_binding(source) == binding, f"source bytes differ: {source}")
    checked_path(destination, exists=False)

    def write(stream: Any) -> None:
        with source.open("rb") as reader:
            for block in iter(lambda: reader.read(4 * 1024 * 1024), b""):
                stream.write(block)

    pf.publish_new(destination, write)
    require(pf.artifact_binding(destination) == binding and pf.artifact_binding(source) == binding,
            f"copied bytes differ: {destination}")


def exact_tree(root: Path, files: set[str]) -> None:
    """Reject a staging tree with unbound files, extra directories, or links."""
    expected_directories = {"."}
    for relative in files:
        expected_directories.update(str(parent) for parent in Path(relative).parents)
    actual_files: set[str] = set()
    actual_directories: set[str] = {"."}
    for current, directories, names in os.walk(root, followlinks=False):
        for name in directories:
            path = Path(current) / name
            require(not path.is_symlink(), "linked staging directory")
            actual_directories.add(str(path.relative_to(root)))
        for name in names:
            path = Path(current) / name
            require(path.is_file() and not path.is_symlink(), "non-ordinary staging file")
            actual_files.add(str(path.relative_to(root)))
    require(actual_files == files and actual_directories == expected_directories,
            "staged replay tree has missing or unbound entries")


def stage(args: argparse.Namespace) -> dict[str, Any]:
    """Publish a byte-verified, context-verified copy for one recovered run."""
    for name in ("definition_sha256", "source_manifest_sha256", "replay_completion_sha256",
                 "preflight_manifest_sha256", "preflight_completion_sha256", "contexts_sha256",
                 "recovered_run_manifest_sha256", "recovery_continuation_sha256",
                 "recovery_lineage_verifier_sha256"):
        require(HEX_SHA.fullmatch(getattr(args, name)) is not None, f"invalid explicit SHA-256: {name}")
    source = checked_path(args.source_replay)
    preflight_root = checked_path(args.preflight_output)
    contexts_path = checked_path(args.contexts)
    run = checked_path(args.recovered_run)
    destination = checked_path(args.destination, exists=False)
    require(source.is_dir() and preflight_root.is_dir() and run.is_dir()
            and contexts_path.is_file() and destination.parent.is_dir()
            and not destination.exists(), "fresh output and existing evidence directories required")
    for value in (source, preflight_root, contexts_path.parent, run):
        require(not destination.is_relative_to(value) and not value.is_relative_to(destination),
                "destination overlaps an evidence input")
    receipt_path = checked_path(destination.with_name(destination.name + ".replay-stage.json"), exists=False)
    require(not receipt_path.exists(), "staging receipt already exists")

    definition_path = source / "definition.json"
    require(file_sha(checked_path(definition_path)) == args.definition_sha256, "definition bytes differ")
    definition = json.loads(definition_path.read_text(encoding="utf-8"))
    pf, preflight, core = pinned_helpers(definition)
    definition = read_pinned(definition_path, args.definition_sha256, pf)
    old_manifest = read_pinned(source / "manifest.json", args.source_manifest_sha256, pf)
    replay = read_pinned(source / "replay/completion.json", args.replay_completion_sha256, pf)
    preflight_manifest = read_pinned(preflight_root / "manifest.json", args.preflight_manifest_sha256, pf)
    preflight_completion = read_pinned(preflight_root / "completion.json", args.preflight_completion_sha256, pf)
    require(file_sha(contexts_path) == args.contexts_sha256, "recipe context inventory bytes differ")
    require(file_sha(run / "manifest.json") == args.recovered_run_manifest_sha256
            == definition["original_manifest_sha256"], "recovered run original manifest bytes differ")
    run_manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    require(run_manifest["manifest_content_sha256"] == pf.canonical_hash({
        key: value for key, value in run_manifest.items() if key != "manifest_content_sha256"})
        and run_manifest["code"]["git_commit"] == definition["original_production_commit"]
        and run_manifest["code"]["git_dirty"] is False, "recovered run original manifest content differs")
    lineage_path = Path(__file__).parents[1] / "extension_release/recovery_lineage.py"
    lineage = load_pinned(lineage_path, "_stage_recovered_lineage",
                          args.recovery_lineage_verifier_sha256)
    producer_proof = lineage.verify_recovered_lineage(run)
    require(producer_proof["status"] == "recovered_lineage_verified"
            and producer_proof["stored_cells"] == 1625
            and producer_proof["manifest_sha256"] == args.recovered_run_manifest_sha256
            and producer_proof["final_lineage_sha256"] == args.recovery_continuation_sha256,
            "recovered 1,625-cell producer proof differs")
    require(old_manifest["schema_version"] == 1
            and old_manifest["definition_content_sha256"] == definition["content_sha256"]
            and old_manifest["preflight_manifest_sha256"] == args.preflight_manifest_sha256
            and old_manifest["preflight_completion_sha256"] == args.preflight_completion_sha256
            and old_manifest["scientific_method_approved"] is False
            and old_manifest["corrected_fit_freeze_created"] is False
            and old_manifest["source_sha256"] == definition["reuse_sources"],
            "old replay manifest binding differs")
    require(Path(old_manifest["input_paths"]["preflight_output"]) == preflight_root
            and Path(old_manifest["input_paths"]["inventory"]) / "contexts.jsonl" == contexts_path
            and Path(old_manifest["input_paths"]["run"]) != run,
            "only the original run path may change")
    require(preflight_manifest["content_sha256"] == preflight_completion["run_binding_sha256"]
            and preflight_manifest["original_manifest_sha256"] == definition["original_manifest_sha256"]
            and preflight_manifest["contexts_jsonl_sha256"] == args.contexts_sha256
            and preflight_manifest["original_input_sha256"] == definition["original_input_sha256"]
            and preflight_manifest["environment_verification"] == definition["environment_verification"]
            and preflight_manifest["candidate_source_sha256"] == definition["candidate_source_sha256"]
            and preflight_manifest["correction_config_sha256"] == definition["correction_config_sha256"]
            and preflight_manifest["correction_addendum_sha256"] == definition["correction_addendum_sha256"],
            "preflight and replay definitions differ")
    rows = [json.loads(line) for line in contexts_path.read_text(encoding="utf-8").splitlines()]
    preflight.validate_inventory(rows, run_manifest)
    complete = core.CompletePreflight(preflight_root, rows, expected_count=CONTEXTS)
    require(replay["schema_version"] == 1
            and replay["status"] == "all1650_independent_first_draw_contexts_accounted"
            and replay["definition_content_sha256"] == definition["content_sha256"]
            and replay["scheduled_contexts"] == replay["accounted_contexts"] == len(rows) == CONTEXTS
            and replay["no_fit_optimizer_mcmc_prediction_or_score_run"] is True
            and [item["context_id"] for item in replay["outcomes"]] == [row["context_id"] for row in rows],
            "completed independent replay roster differs")
    new_manifest = pf.seal({**{key: value for key, value in old_manifest.items() if key != "content_sha256"},
                            "input_paths": {**old_manifest["input_paths"], "run": str(run)}})
    require({key: value for key, value in new_manifest.items() if key not in {"content_sha256", "input_paths"}}
            == {key: value for key, value in old_manifest.items() if key not in {"content_sha256", "input_paths"}},
            "staged execution manifest changed outside run path")

    temporary = destination.with_name(f".{destination.name}.replay-stage-{uuid.uuid4().hex}")
    checked_path(temporary, exists=False)
    temporary.mkdir()
    files: set[str] = set()
    copied_bytes = 0
    try:
        for row, outcome in zip(rows, replay["outcomes"], strict=True):
            preflight_directory, preflight_record = complete.context(row)
            bindings = verify_context(source, row, outcome, preflight_directory, preflight_record,
                                      definition, old_manifest, pf, core)
            completion_key = str(Path(outcome["receipt_path"]).relative_to("replay"))
            require(replay["artifacts"][completion_key] == bindings[outcome["receipt_path"]],
                    "replay completion artifact binding differs")
            for relative, binding in bindings.items():
                require(relative not in files, "duplicate replay artifact")
                copy_bound(source / relative, temporary / relative, binding, pf)
                files.add(relative)
                copied_bytes += binding["bytes"]
            verify_context(temporary, row, outcome, preflight_directory, preflight_record,
                           definition, old_manifest, pf, core)
        require(set(replay["artifacts"]) == {
            str(Path(outcome["receipt_path"]).relative_to("replay")) for outcome in replay["outcomes"]},
            "replay completion has extra or missing receipt bindings")
        for relative, digest in (("definition.json", args.definition_sha256),
                                 ("replay/completion.json", args.replay_completion_sha256)):
            binding = pf.artifact_binding(source / relative)
            require(binding["sha256"] == digest, f"source anchor changed: {relative}")
            copy_bound(source / relative, temporary / relative, binding, pf)
            files.add(relative)
            copied_bytes += binding["bytes"]
        pf.write_json_new(temporary / "manifest.json", new_manifest)
        files.add("manifest.json")
        copied_bytes += (temporary / "manifest.json").stat().st_size
        require(pf.read_sealed(temporary / "manifest.json") == new_manifest
                and pf.sha256_file(temporary / "definition.json") == args.definition_sha256
                and pf.sha256_file(temporary / "replay/completion.json") == args.replay_completion_sha256,
                "staged manifest or anchors differ")
        exact_tree(temporary, files)
        require(len(files) == 3 + 4 * CONTEXTS, "staged replay file count differs")
        require(all(file_sha(path) == digest for path, digest in (
            (source / "definition.json", args.definition_sha256),
            (source / "manifest.json", args.source_manifest_sha256),
            (source / "replay/completion.json", args.replay_completion_sha256),
            (preflight_root / "manifest.json", args.preflight_manifest_sha256),
            (preflight_root / "completion.json", args.preflight_completion_sha256),
            (contexts_path, args.contexts_sha256), (run / "manifest.json", args.recovered_run_manifest_sha256),
            (run / "recovery_continuation.json", args.recovery_continuation_sha256))),
            "pinned input changed during staging")
        require(not destination.exists(), "destination appeared during staging")
        temporary.rename(destination)
    except BaseException:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    result = pf.seal({"schema_version": 1, "status": "complete_first_draw_replay_staged_for_recovered_run",
                      "source_replay": str(source), "destination": str(destination),
                      "recovered_run": str(run), "definition_sha256": args.definition_sha256,
                      "source_manifest_sha256": args.source_manifest_sha256,
                      "staged_manifest_sha256": pf.sha256_file(destination / "manifest.json"),
                      "replay_completion_sha256": args.replay_completion_sha256,
                      "preflight_manifest_sha256": args.preflight_manifest_sha256,
                      "preflight_completion_sha256": args.preflight_completion_sha256,
                      "contexts_sha256": args.contexts_sha256,
                      "recovered_run_manifest_sha256": args.recovered_run_manifest_sha256,
                      "recovery_continuation_sha256": args.recovery_continuation_sha256,
                      "recovery_lineage_verifier_sha256": args.recovery_lineage_verifier_sha256,
                      "staged_contexts": CONTEXTS, "staged_files": len(files),
                      "staged_bytes": copied_bytes, "corrected_fits_executed": False,
                      "scientific_method_approved": False})
    pf.write_json_new(receipt_path, result)
    return result


def parse_args() -> argparse.Namespace:
    """Require explicit evidence locations and byte pins."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source-replay", "destination", "recovered-run", "preflight-output", "contexts"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    for name in ("definition", "source-manifest", "replay-completion", "preflight-manifest",
                 "preflight-completion", "contexts", "recovered-run-manifest",
                 "recovery-continuation", "recovery-lineage-verifier"):
        parser.add_argument(f"--{name}-sha256", required=True)
    return parser.parse_args()


def main() -> int:
    """Stage one complete replay without invoking the reuse runner."""
    result = stage(parse_args())
    print(json.dumps({"status": result["status"], "staged_contexts": result["staged_contexts"],
                      "staged_files": result["staged_files"], "destination": result["destination"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
