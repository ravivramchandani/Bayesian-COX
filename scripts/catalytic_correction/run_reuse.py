"""Independently replay original first proposals and build exact reuse witnesses.

Invoke directly; never import a current-main ``src`` package. Real execution
requires complete 1650-context preflight evidence and explicit byte pins.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import pickle
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True


def import_pinned(path: Path, name: str, digest: str) -> Any:
    """Load explicit reviewed bytes under a private module namespace."""
    if not path.is_file() or any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("missing or linked pinned module")
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise ValueError(f"pinned module bytes differ: {name}")
    if name in sys.modules:
        old = sys.modules[name]
        if getattr(old, "__file__", None) is None or not Path(old.__file__).samefile(path):
            raise ValueError(f"private pinned namespace collision: {name}")
        return old
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load pinned private module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def bootstrap(args: argparse.Namespace) -> tuple[Any, Any, Any, Any]:
    """Bind helpers before any scientific normal import or cohort construction."""
    if any(name == "src" or name.startswith("src.") for name in sys.modules):
        raise ValueError("foreign src namespace already loaded")
    if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != args.reuse_runner_sha256:
        raise ValueError("explicit reviewed reuse runner bytes differ")
    if hashlib.sha256(Path(__file__).with_name("normal_first_draw_child.py").read_bytes()).hexdigest() != args.first_draw_child_sha256:
        raise ValueError("explicit reviewed independent child bytes differ")
    pf = import_pinned(args.preflight_core, "_reuse_bound_core", args.preflight_core_sha256)
    if "preflight_core" in sys.modules and sys.modules["preflight_core"] is not pf:
        raise ValueError("private preflight sibling namespace collision")
    sys.modules["preflight_core"] = pf
    preflight = import_pinned(args.preflight_runner, "_reuse_bound_preflight", args.preflight_runner_sha256)
    contracts = import_pinned(args.contracts_module, "_reuse_bound_contracts", args.contracts_sha256)
    core = import_pinned(Path(__file__).with_name("reuse_core.py"), "_reuse_actual_core", args.reuse_core_sha256)
    return pf, preflight, contracts, core


def checked_scientific_modules(source: Path, hashes: dict[str, str], pf: Any) -> None:
    """All loaded scientific modules must be exact normal original imports."""
    for name, module in list(sys.modules.items()):
        if name == "src" or name.startswith("src."):
            path = Path(module.__file__).absolute()
            if not path.is_relative_to(source):
                raise pf.InvalidCheckpoint("normal scientific import came from another checkout")
            relative = str(path.relative_to(source))
            if relative not in hashes or pf.sha256_file(path) != hashes[relative]:
                raise pf.InvalidCheckpoint("normal scientific imported source bytes differ")


def environment_report(args: argparse.Namespace, manifest: dict[str, Any], pf: Any) -> dict[str, Any]:
    """Verify the same exact lock before processing any real cohort."""
    result = subprocess.run([str(args.python), "-B", str(args.source / "scripts/verify_environment.py"),  # noqa: S603 - explicit pinned local interpreter/script
        "--lock-file", str(args.source / "conda-lock.yml"), "--hash-file", str(args.source / "conda-lock.yml.sha256")],
        capture_output=True, text=True, check=True, env=os.environ.copy())  # noqa: S603 - explicit pinned local interpreter/script
    value = json.loads(result.stdout)
    if value["status"] != "ok" or value["package_count"] != 259 or value["lock_sha256"] != manifest["input_sha256"]["conda-lock.yml"]:
        raise pf.InvalidCheckpoint("exact lock environment verification failed")
    return value


class ReuseBackend:
    """Expose only pinned input construction and original saved candidate lists."""

    def __init__(self, original: Any, environment: dict[str, Any], source: Path, pf: Any) -> None:
        self.original, self.manifest, self.environment = original, original.manifest, environment
        self.primary = original.runner.read_mapping(source / "config/confirmatory.yaml")
        self.fitting = importlib.import_module("src.pipelines.extensions.fitting")
        self.evaluation = importlib.import_module("src.pipelines.confirmatory.evaluation")
        self.pf = pf
        checked_scientific_modules(source, self.manifest["input_sha256"], pf)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.original, name)

    def candidates(self, model: str) -> list[dict[str, Any]]:
        """Read the original pure config ordering; no selection function runs."""
        return self.fitting.candidates_for(model, self.manifest["run_config"], self.primary)

    def evaluation_inputs(self, tt: Any, ee: Any, vt: Any, ve: Any) -> dict[str, Any]:
        """Witness train-derived horizons/grid and IPCW truncation, without scoring."""
        try:
            horizons, grid = self.evaluation.evaluation_horizons_and_grid(tt, ee, self.primary["evaluation"])
            clipped_time, clipped_event = self.evaluation.administratively_truncate_for_ipcw(vt, ve, float(grid[-1]))
            return {"status": "constructed_without_predictions_or_scores", "horizons": self.pf.array_witness(horizons),
                    "grid": self.pf.array_witness(grid), "ipcw_validation_time": self.pf.array_witness(clipped_time),
                    "ipcw_validation_event": self.pf.array_witness(clipped_event)}
        except Exception as error:
            return {"status": "original_evaluation_input_rule_failed", "error": {
                "type": f"{type(error).__module__}.{type(error).__qualname__}", "message": str(error)},
                    "no_model_prediction_or_score_executed": True}


def stable_new_json(path: Path, record: dict[str, Any], pf: Any) -> None:
    """Publish once or verify exact equality; never overwrite an invalid checkpoint."""
    if any(value.is_symlink() for value in (path, *path.parents)):
        raise pf.InvalidCheckpoint("linked write-once output")
    if path.exists():
        if pf.read_sealed(path) != record:
            raise pf.InvalidCheckpoint("write-once checkpoint request or bytes differ")
    else:
        pf.write_json_new(path, record)


def replay_request(row: dict[str, Any], definition: str, preflight_receipt: Path,
                   inputs: Any | None, pf: Any) -> dict[str, Any]:
    """Bind independent replay to one exact original context and preflight record."""
    return {"definition_content_sha256": definition, "context_id": row["context_id"],
            "context_row_sha256": pf.canonical_hash(row), "original_generation_seed": row["generation_seed"],
            "preflight_receipt_sha256": pf.sha256_file(preflight_receipt),
            "input_witness_sha256": None if inputs is None else pf.canonical_hash(inputs.witness)}


def run_independent_child(args: argparse.Namespace, directory: Path, request: dict[str, Any],
                          inputs: Any, manifest: dict[str, Any], environment: dict[str, Any], pf: Any) -> dict[str, Any]:
    """Own one new normal-import process and training-only local transport."""
    child_root = directory / "normal_original_child"
    if any(value.is_symlink() for value in (child_root, *child_root.parents)):
        raise pf.InvalidCheckpoint("linked independent child output")
    path = child_root / "receipt.json"
    if path.exists():
        result = pf.read_sealed(path)
        if result["request"] != request:
            raise pf.InvalidCheckpoint("cached independent child request differs")
        pf.verify_artifacts(child_root, result)
        transport = child_root / "owned_training_transport.pkl"
        if transport.exists():
            original_request = pf.read_sealed(child_root / "request.json")
            if pf.artifact_binding(transport) != original_request["payload_artifact"]:
                raise pf.InvalidCheckpoint("cached verified child's temporary transport changed")
            transport.unlink()
        return result
    if child_root.exists() and any(child_root.iterdir()):
        raise pf.InvalidCheckpoint("partial independent child lacks a completed receipt; choose separate reviewed recovery")
    child_root.mkdir(parents=True)
    payload = child_root / "owned_training_transport.pkl"
    # This pickle is a locally created, hash-bound temporary transport, never an
    # externally supplied scientific artifact. No heldout rows are serialized.
    pf.publish_new(payload, lambda stream: pickle.dump({"training": inputs.training,
        "time": inputs.time, "event": inputs.event, "feature_spec": inputs.feature_spec,
        "gene_budget": inputs.witness["gene_budget"]}, stream, protocol=5))
    child_request = pf.seal({"schema_version": 1, "request": request, "source": str(args.source),
        "original_input_sha256": manifest["input_sha256"], "original_manifest_sha256": args.original_manifest_sha256,
        "payload_artifact": pf.artifact_binding(payload), "expected_input_witness": inputs.witness,
        "full_raw_training_witness": pf.source_frame_witness(inputs.training, list(inputs.training.columns)),
        "expected_environment_verification": environment,
        "preflight_core": str(args.preflight_core), "preflight_core_sha256": args.preflight_core_sha256,
        "child_source_sha256": pf.sha256_file(Path(__file__).with_name("normal_first_draw_child.py")),
        "owned_training_transport_not_external_pickle": True,
        "generator_receives_training_only": True})
    pf.write_json_new(child_root / "request.json", child_request)
    command = [str(args.python), "-I", "-B", str(Path(__file__).with_name("normal_first_draw_child.py")),
               "--owned-directory", str(child_root), "--request-sha256", pf.sha256_file(child_root / "request.json")]
    result = subprocess.run(command, capture_output=True, text=True, env=os.environ.copy())  # noqa: S603 - owned process, byte-pinned script/transport
    pf.publish_new(child_root / "stdout.txt", lambda stream: stream.write(result.stdout.encode()))
    pf.publish_new(child_root / "stderr.txt", lambda stream: stream.write(result.stderr.encode()))
    if result.returncode != 0 or not path.exists():
        raise pf.InvalidCheckpoint("independent original child failed; retained transport/logs require review")
    record = pf.read_sealed(path)
    if record["request"] != request:
        raise pf.InvalidCheckpoint("independent child result belongs to another request")
    pf.verify_artifacts(child_root, record)
    # Discard only our verified temporary transport. The retained request binds
    # its bytes and the full raw/processed input witnesses independently.
    if pf.artifact_binding(payload) != child_request["payload_artifact"]:
        raise pf.InvalidCheckpoint("owned transport changed after child verification")
    payload.unlink()
    return record


def replay_context(args: argparse.Namespace, output: Path, definition: str, row: dict[str, Any],
                   backend: ReuseBackend, complete: Any, core: Any, pf: Any, environment: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct, independently replay, and publish exact first-draw identity."""
    source_dir, source_record = complete.context(row)
    name = "outer" if row["context"] == "outer" else f"inner_{row['inner_fold']:02d}"
    directory = output / "replay" / "contexts" / row["outer_cell_id"] / name
    with pf.Claim(output / "claims" / f"replay-{pf.canonical_hash(row['context_id'])}.json", definition,
                  recover_stale=args.recover_stale_claims):
        inputs, failure = None, None
        try:
            inputs = pf.build_context(row, backend.jobs[row["outer_cell_id"]], backend.cohorts[row["dataset"]], backend)
        except pf.InvalidCheckpoint:
            raise
        except Exception as error:
            failure = pf.error_record(error)
        request = replay_request(row, definition, source_dir / "receipt.json", inputs, pf)
        target = directory / "receipt.json"
        if target.exists():
            record = core.verified_json(target)
            core.require(record["request"] == request, "independent replay resume inputs differ")
            if inputs is not None:
                saved = core.verified_json(source_dir / "input.json")
                core.require(saved["input_witness"] == inputs.witness, "normal reconstructed preflight inputs differ")
            return record
        if inputs is None:
            replay = {"status": "input_failure", "error": failure}
            artifacts = {}
        else:
            saved = core.verified_json(source_dir / "input.json")
            core.require(saved["input_witness"] == inputs.witness,
                         "normal original full input reconstruction differs from preflight")
            replay = run_independent_child(args, directory, request, inputs, backend.manifest, environment, pf)
            artifacts = {"normal_original_child/receipt.json": pf.artifact_binding(directory / "normal_original_child/receipt.json")}
            for key, value in replay["artifacts"].items():
                artifacts[f"normal_original_child/{key}"] = value
        assessment = core.compare_first_draw(source_record, replay, None if inputs is None else inputs.witness)
        result = pf.seal({"schema_version": 1, "request": request, "context_id": row["context_id"],
            "status": "independent_original_first_draw_verified", "assessment": assessment,
            "original_replay": replay, "preflight_status": source_record["status"], "artifacts": artifacts,
            "scope": "generator_input_and_first_proposal_identity_only; no_fit_or_evaluation_reuse_approval"})
        stable_new_json(target, result, pf)
        return result


def execute(args: argparse.Namespace, pf: Any, preflight: Any, contracts: Any, core: Any) -> Path:
    """Verify full inputs, replay all positions, then acquire whole-grid witnesses."""
    for path, expected in ((args.preflight_output / "manifest.json", args.preflight_manifest_sha256),
                           (args.preflight_output / "completion.json", args.preflight_completion_sha256),
                           (args.correction_config, args.correction_config_sha256),
                           (args.correction_addendum, args.correction_addendum_sha256)):
        core.require(pf.sha256_file(path) == expected, "explicit reviewed preflight/method bytes differ")
    manifest, rows, original_binding = preflight.verify_bindings(args)
    complete = core.CompletePreflight(args.preflight_output, rows)
    old = complete.manifest
    for key in ("original_manifest_sha256", "original_input_sha256", "matched_sha256", "candidate_source_sha256",
                "inventory_receipt_sha256", "contexts_jsonl_sha256", "correction_config_sha256", "correction_addendum_sha256"):
        core.require(old[key] == original_binding[key], f"actual preflight input binding differs: {key}")
    core.require(old["runner_source_sha256"] == {"preflight_core.py": args.preflight_core_sha256,
                 "run_preflight.py": args.preflight_runner_sha256}, "actual preflight runner bytes differ")
    environment = environment_report(args, manifest, pf)
    core.require(environment == old["environment_verification"], "preflight and reuse exact environment reports differ")
    source_hashes = {name: pf.sha256_file(Path(__file__).with_name(name)) for name in
                     ("run_reuse.py", "reuse_core.py", "normal_first_draw_child.py")}
    core.require(source_hashes["reuse_core.py"] == args.reuse_core_sha256, "reuse implementation bytes differ")
    definition = pf.seal({"schema_version": 1, "scope": "scientific_input_definition_and_policy_before_corrected_fits",
        "original_production_commit": preflight.PRODUCTION_COMMIT, "original_manifest_sha256": preflight.MANIFEST_SHA,
        "original_input_sha256": manifest["input_sha256"], "matched_sha256": manifest["matched_sha256"],
        "original_configuration": manifest["run_config"], "environment_verification": environment,
        "correction_config_sha256": original_binding["correction_config_sha256"],
        "correction_addendum_sha256": original_binding["correction_addendum_sha256"],
        "candidate_source_sha256": args.candidate_sha256, "attempt_cap": 256,
        "retry_seed_rule": "originalseed; deterministic_seed(originalseed,'rank_conditioned_retry',index1..255)",
        "preflight_sources": {"preflight_core.py": args.preflight_core_sha256, "run_preflight.py": args.preflight_runner_sha256},
        "reuse_sources": source_hashes, "contracts_sha256": args.contracts_sha256,
        "ownership_policy": "original missing or claims present waits; never duplicate or recover original claims",
        "comparison_policy": "exact19/21/42 roles with independent1650 normal-source firstdraw witnesses; failed outcomes retained equally",
        "numerical_thread_policy": 1, "definition_excludes_actual_reuse_outcome_snapshots_and_future_freeze": True})
    stable_new_json(args.output / "definition.json", definition, pf)
    execution_binding = pf.seal({"schema_version": 1, "definition_content_sha256": definition["content_sha256"],
        "preflight_manifest_sha256": pf.sha256_file(args.preflight_output / "manifest.json"),
        "preflight_completion_sha256": pf.sha256_file(args.preflight_output / "completion.json"),
        "input_paths": {key: str(getattr(args, key)) for key in
                       ("source", "run", "matched", "inventory", "preflight_output", "candidate_module", "python")},
        "scientific_method_approved": False, "corrected_fit_freeze_created": False,
        "source_sha256": source_hashes})
    stable_new_json(args.output / "manifest.json", execution_binding, pf)
    original = preflight.FrozenBackend(args, manifest)
    backend = ReuseBackend(original, environment, args.source, pf)
    definition_sha = definition["content_sha256"]
    replay_entries, generator_by_cell, arithmetic_entries = [], {}, []
    for row in rows:
        result = replay_context(args, args.output, definition_sha, row, backend, complete, core, pf, environment)
        name = "outer" if row["context"] == "outer" else f"inner_{row['inner_fold']:02d}"
        path = args.output / "replay" / "contexts" / row["outer_cell_id"] / name / "receipt.json"
        replay_entries.append({"context_id": row["context_id"], "receipt_path": str(path.relative_to(args.output)),
                               "receipt_sha256": pf.sha256_file(path), "receipt_content_sha256": result["content_sha256"]})
        preflight_directory, preflight_record = complete.context(row)
        generator_by_cell.setdefault(row["outer_cell_id"], {})[name] = (preflight_record, result["original_replay"])
        arithmetic_entries.append(core.arithmetic_selector_entry(row, preflight_record, result["original_replay"],
            str((preflight_directory / "receipt.json").relative_to(args.preflight_output)),
            pf.sha256_file(preflight_directory / "receipt.json"), str(path.relative_to(args.output)), pf.sha256_file(path)))
        print(json.dumps({"stage": "independent_first_draw_replay", "context_id": row["context_id"],
                          "accounted": len(replay_entries)}, sort_keys=True), flush=True)
    replay_completion = pf.seal({"schema_version": 1, "status": "all1650_independent_first_draw_contexts_accounted",
        "definition_content_sha256": definition_sha, "scheduled_contexts": 1650, "accounted_contexts": len(replay_entries),
        "outcomes": replay_entries, "artifacts": {str((args.output / item["receipt_path"]).relative_to(args.output / "replay")):
                                                   pf.artifact_binding(args.output / item["receipt_path"])
                                                   for item in replay_entries}, "no_fit_optimizer_mcmc_prediction_or_score_run": True})
    stable_new_json(args.output / "replay" / "completion.json", replay_completion, pf)
    selector = pf.seal({"schema_version": 1, "status": "all1650_context_arithmetic_requirements_accounted",
        "definition_content_sha256": definition_sha,
        "preflight_completion_sha256": execution_binding["preflight_completion_sha256"],
        "replay_completion_sha256": pf.sha256_file(args.output / "replay" / "completion.json"),
        "scheduled_contexts": 1650, "entries": arithmetic_entries,
        "arithmetic_validation_executed": False, "scientific_method_approved": False})
    stable_new_json(args.output / "arithmetic_selector.json", selector, pf)
    entries = []
    for job in backend.jobs.values():
        directory = args.output / "cells" / job.cell_id
        with pf.Claim(args.output / "claims" / f"cell-{pf.canonical_hash(job.cell_id)}.json", definition_sha,
                      recover_stale=args.recover_stale_claims):
            ledger = contracts.seed_ledger(job.cell_id)
            context = core.reconstruction_inputs(job, backend.cohorts[job.dataset], backend, ledger)
            values = core.make_role_values(job, context, backend, generator_by_cell.get(job.cell_id, {}))
            contexts = {}
            for name, (record, _) in generator_by_cell.get(job.cell_id, {}).items():
                row = next(row for row in rows if row["context_id"] == f"{job.cell_id}::{name}")
                path, _ = complete.context(row)
                contexts[name] = ["accepted" if record["status"] in core.ACCEPTED else record["status"],
                                  pf.sha256_file(path / "receipt.json")]
            witness = core.write_role_witness(directory, definition_sha, job, context, values, contexts)
            snapshot = core.original_snapshot(args.run, job.cell_id, preflight.MANIFEST_SHA, backend.candidates(job.model))
            decision, decision_path = core.snapshot_decision(directory, definition_sha, witness, snapshot)
            entries.append({"original_cell_id": job.cell_id, "model": job.model, "dataset": job.dataset,
                "setting": job.setting, "gene_budget": job.gene_budget, "n_train": len(job.train), "p": context["p"],
                "selection_scope": witness["selection_scope"], "action": decision["action"],
                "potential_action": decision["potential_action"], "input_witness_path": str((directory / "input_witness.json").relative_to(args.output)),
                "input_witness_sha256": pf.sha256_file(directory / "input_witness.json"),
                "snapshot_path": str(decision_path.relative_to(args.output)), "snapshot_sha256": pf.sha256_file(decision_path),
                "decision": decision["decision"], "selected_parameters": decision["selected_parameters"],
                "inner_tuning": decision["inner_tuning"], "generator_contexts": contexts,
                "original_claim_active": decision["original_claim_active"], "source_evidence": decision["source_evidence"]})
            print(json.dumps({"stage": "exact_reuse_input_witness", "original_cell_id": job.cell_id,
                              "action": decision["action"], "accounted": len(entries)}, sort_keys=True), flush=True)
    backend.verify_boundary()
    checked_scientific_modules(args.source, manifest["input_sha256"], pf)
    core.require({name: pf.sha256_file(Path(__file__).with_name(name)) for name in source_hashes} == source_hashes,
                 "reuse implementation changed during execution")
    for path, expected in ((args.preflight_output / "manifest.json", args.preflight_manifest_sha256),
                           (args.preflight_output / "completion.json", args.preflight_completion_sha256),
                           (args.correction_config, args.correction_config_sha256),
                           (args.correction_addendum, args.correction_addendum_sha256)):
        core.require(pf.sha256_file(path) == expected, "preflight/method bytes changed during execution")
    return core.publish_inventory(args.output, definition_sha, execution_binding["preflight_completion_sha256"],
                                  pf.sha256_file(args.output / "replay" / "completion.json"), entries,
                                  arithmetic_selector_sha256=pf.sha256_file(args.output / "arithmetic_selector.json"))


def parse_args() -> argparse.Namespace:
    """Require explicit inputs and reviewed helper bytes, with no user defaults."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "run", "matched", "inventory", "candidate-module", "correction-config", "correction-addendum",
                 "preflight-output", "preflight-core", "preflight-runner", "contracts-module", "output", "python"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    for name in ("candidate", "preflight-core", "preflight-runner", "contracts", "reuse-core", "reuse-runner",
                 "first-draw-child", "preflight-manifest", "preflight-completion", "correction-config", "correction-addendum"):
        parser.add_argument(f"--{name}-sha256", required=True)
    parser.add_argument("--recover-stale-claims", action="store_true", help="only owned local dead claims; never original claims")
    args = parser.parse_args()
    args.cap, args.restore_processor_state = 256, False
    return args


def main() -> int:
    args = parse_args()
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        if os.environ.get(name) != "1":
            raise ValueError("all numeric thread variables must be1 before invoking Python")
    pf, preflight, contracts, core = bootstrap(args)
    for key, value in vars(args).items():
        if isinstance(value, Path) and key != "python":
            setattr(args, key, preflight.safe_absolute(value))
    args.python = preflight.locked_interpreter(args.python)
    args.original_manifest_sha256 = preflight.MANIFEST_SHA
    forbidden = (args.source, args.run, args.inventory, args.preflight_output, args.candidate_module.parent,
                 args.preflight_core.parent, args.contracts_module.parent, Path(__file__).parent)
    for value in forbidden:
        core.require(not args.output.is_relative_to(value) and not value.is_relative_to(args.output),
                     "output must be separate from all source/evidence inputs")
    args.output.mkdir(parents=True, exist_ok=True)
    allowed = {"cache", "launcher.claim.json", "claims", "abandoned_claims", "definition.json", "manifest.json", "replay", "cells", "inventories", "arithmetic_selector.json"}
    core.require(not ({path.name for path in args.output.iterdir()} - allowed), "unbound evidence in output")
    if not (args.output / "manifest.json").exists():
        core.require(not ({path.name for path in args.output.iterdir()} -
                         {"cache", "launcher.claim.json", "claims", "abandoned_claims", "definition.json"}),
                     "unbound prior scientific checkpoints in new output")
    os.environ.update(MPLCONFIGDIR=str(args.output / "cache" / "matplotlib"),
                      NUMBA_CACHE_DIR=str(args.output / "cache" / "numba"), XDG_CACHE_HOME=str(args.output / "cache" / "xdg"),
                      PYTHONPYCACHEPREFIX=str(args.output / "cache" / "python"),
                      PYTENSOR_FLAGS=f"compiledir={args.output / 'cache' / 'pytensor'}")
    sys.pycache_prefix = str(args.output / "cache" / "controller_python")
    launch = pf.canonical_hash({key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()
                               if key != "recover_stale_claims"})
    with pf.Claim(args.output / "launcher.claim.json", launch, recover_stale=args.recover_stale_claims):
        path = execute(args, pf, preflight, contracts, core)
    print(json.dumps({"status": "complete_witness_inventory_sealed", "inventory": str(path),
                      "inventory_sha256": pf.sha256_file(path), "fit_dispatched": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
