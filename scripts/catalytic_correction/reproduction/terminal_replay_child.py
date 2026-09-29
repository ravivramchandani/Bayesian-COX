"""Owned normal-source training-only terminal recipe replay; never fit/score."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
FIT_COMMON_SHA = "b17f378ba77ea3ae5ba25c836e963a1a0160556465b25745462f648e325d1f11"


def bootstrap(request_path: Path, request_sha: str) -> tuple[Any, Any, dict[str, Any]]:
    """Pin support before import; refuse current-main scientific namespaces."""
    if hashlib.sha256(request_path.read_bytes()).hexdigest() != request_sha:
        raise ValueError("terminal request bytes differ")
    document = json.loads(request_path.read_text())
    common_path = Path(document["fit_code"]) / "fit_common.py"
    if not hashlib.sha256(common_path.read_bytes()).hexdigest() == document["fit_implementation_source_sha256"]["fit_common.py"] == FIT_COMMON_SHA:
        raise ValueError("terminal fit support source differs")
    spec = importlib.util.spec_from_file_location("_reproduction_bound_common", common_path)
    if spec is None or spec.loader is None or spec.name in sys.modules:
        raise ValueError("terminal support namespace unavailable")
    common = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = common
    spec.loader.exec_module(common)
    core_path = Path(__file__).absolute().with_name("reproduction_core.py")
    core = common.module_from_pin(core_path, document["implementation_source_sha256"][core_path.name], "_terminal_reproduction_core")
    request = common.read_json(request_path, request_sha)
    common.require(not any(name == "src" or name.startswith("src.") for name in sys.modules),
                   "terminal child has foreign src namespace")
    common.validate_runtime(Path(request["locked_python"]))
    common.require(bool(sys.flags.isolated) and sys.dont_write_bytecode, "terminal child must use -I -B")
    return common, core, request


def rank_rejection(error: Exception, constructor: Any, line: int = 32) -> bool:
    """Only the byte-pinned original guard's exact raise is retryable."""
    trace = error.__traceback__
    while trace is not None and trace.tb_next is not None:
        trace = trace.tb_next
    guard = getattr(constructor, "__post_init__", None)
    return (type(error) is ValueError and error.args == ("synthetic design is not full column rank",)
            and trace is not None and guard is not None and trace.tb_frame.f_code is guard.__code__
            and trace.tb_lineno == line)


def original_draw(module: Any, inputs: Any, seed: int, pf: Any, options: Any,
                  source_pins: dict[str, str], np: Any, *, rank_line: int = 32) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Capture once and delegate the untouched original constructor/guard.

    ``rank_line`` is an injected invented-fixture hook; actual CLI always uses
    the sealed original line32. Original full raw processor state is supplied
    by normal ``fit(training)``, never metadata restoration or thin adapters.
    """
    if threading.active_count() != 1:
        raise ValueError("terminal alias replay requires one Python thread")
    original = module.CatalyticData
    captured: dict[str, Any] = {}

    def capture(design: Any, synthetic_time: Any, hazard: Any) -> Any:
        if captured:
            raise ValueError("original generator reached constructor more than once")
        captured.update(synthetic_design=np.asarray(design).copy(), synthetic_time=np.asarray(synthetic_time).copy(),
                        hazard=np.asarray(hazard, dtype=float),
                        time_scale=np.asarray(float(np.median(inputs.time[inputs.event == 1])), dtype=float))
        return original(design, synthetic_time, hazard)

    error, legacy = None, None
    before = inputs.processor.metadata()
    module.CatalyticData = capture
    try:
        try:
            _, legacy = module.generate_catalytic_data(inputs.training, inputs.processor, inputs.time, inputs.event, seed)
        except Exception as caught:
            error = caught
    finally:
        module.CatalyticData = original
    arrays = {name: captured[name] for name in ("synthetic_design", "synthetic_time", "hazard", "time_scale")} if captured else None
    if module.CatalyticData is not original or inputs.processor.metadata() != before:
        raise ValueError("normal generator changed processor/constructor scope")
    status = ("accepted_original_constructor" if error is None else
              "frozen_rank_rejected" if rank_rejection(error, original, rank_line) else "nonrank_error")
    if error is None and arrays is None:
        raise ValueError("original generator returned without reaching constructor")
    result: dict[str, Any] = {"seed": seed, "status": status, "error": None if error is None else pf.error_record(error),
                              "processor_metadata": before, "legacy_metadata": legacy,
                              "array_witnesses": None if arrays is None else {name: pf.array_witness(value) for name, value in arrays.items()},
                              "constructor_inputs": None, "actual_metadata": None}
    if arrays is not None:
        sources = list(dict.fromkeys(inputs.processor.clinical.required_source_columns + inputs.processor.genes))
        # Same reviewed carrier hashes, computed from the actually captured
        # normal-source values; no catalytic wrapper or constructor replacement.
        signatures = {}
        for name, key in (("design", "synthetic_design"), ("time", "synthetic_time")):
            witness = pf.array_witness(arrays[key])
            signatures[name] = {"dtype": witness["dtype"], "shape": witness["shape"], "values_sha256": witness["values_sha256"]}
        signatures.update(hazard=float(arrays["hazard"]), synthetic_sha256=pf.canonical_hash({
            "X": arrays["synthetic_design"].tolist(), "time": arrays["synthetic_time"].tolist()}))
        result["constructor_inputs"] = signatures
        result["actual_metadata"] = {
            "seed": seed, "M": len(arrays["synthetic_time"]), "p": len(inputs.processor.feature_names),
            "time_scale": float(arrays["time_scale"]), "hazard_scaled": float(arrays["hazard"]),
            "source_variables": sources, "feature_names": list(inputs.processor.feature_names),
            "processor_metadata": before, "constructor_restored": True,
            "legacy_metadata_origin": "original returned value" if legacy is not None else "not returned by original generator",
            "capture_scope": "constructor inputs and training-derived proposal metadata only", "source_sha256": source_pins,
            "original_retry_seed_1": options.deterministic_seed(seed, "rank_conditioned_retry", 1),
            "processor_origin": "independent normal full raw training fit in terminal replay child"}
    return result, arrays


def replay_recipe(inputs: Any, row: dict[str, Any], draw: Any, seed_function: Any, save: Any,
                  *, cap: int = 256) -> dict[str, Any]:
    """Run the frozen complete recipe, never stop/choose using saved outcomes."""
    if cap != 256:
        raise ValueError("terminal replay cap must retain the frozen256 law")
    attempts, accepted = [], None
    for index in range(cap):
        seed = row["generation_seed"] if index == 0 else seed_function(row["generation_seed"], "rank_conditioned_retry", index)
        result, arrays = draw(inputs, seed)
        record = {**result, "attempt_index": index}
        save(record, arrays)
        attempts.append(record)
        if record["status"] == "accepted_original_constructor":
            accepted, status = index, "accepted_original_first_draw" if index == 0 else "accepted_rank_conditioned_redraw"
            break
        if record["status"] == "nonrank_error":
            status = "nonrank_failure"
            break
        if record["status"] != "frozen_rank_rejected":
            raise ValueError("unknown original terminal draw outcome")
    else:
        status = "exhausted_rank_cap"
    return {"status": status, "attempts": attempts, "accepted_attempt_index": accepted}


class NormalTrainingBackend:
    """Only frozen censor/split/preprocess functions, no fit/tune/evaluation."""

    def __init__(self, source: Path, modules: dict[str, Any]) -> None:
        self.modules = modules
        self.specs = modules["io"].read_mapping(source / "config/datasets.yaml")

    def feature_spec(self, dataset: str) -> Any:
        return self.specs["metabric" if dataset == "metabric_matched" else dataset]["primary_features"]

    def apply_censor(self, times: Any, events: Any, cutoff: Any) -> Any:
        return self.modules["conditions"].apply_administrative_censoring(times, events, cutoff)

    def inner_folds(self, times: Any, events: Any, seed: int) -> Any:
        return self.modules["folds"].repeated_survival_folds(times, events, n_splits=3, n_repeats=1, base_seed=seed, max_time_bins=4)

    def preprocess(self, spec: Any, budget: int, training: Any) -> Any:
        return self.modules["preprocessing"].ExtensionPreprocessor(spec, budget).fit(training)


def execute(request_path: Path, request_sha: str) -> None:
    """Actually execute selected training recipes only after real supplied gates."""
    common, rc, request = bootstrap(request_path, request_sha)
    own, attempt = Path(__file__).absolute().parent, common.safe(Path(request["attempt_path"]))
    common.require(attempt == request_path.parent and not (attempt / "receipt.json").exists(), "terminal owned attempt differs or already finished")
    selection, freeze, manifest, inventory, (completion, rows, _) = rc.load_selection(
        Path(request["selection_path"]), request["selection_sha256"], own)
    common.require(request["implementation_source_sha256"] == selection["implementation_source_sha256"]
                   and request["original_cell_id"] in selection["selected_cells"], "terminal request is outside frozen scope")
    entry = next(row for row in inventory["entries"] if row["original_cell_id"] == request["original_cell_id"])
    common.require(entry == request["entry"], "terminal inventory entry differs")
    paths = {key: Path(value) for key, value in freeze["paths"].items()}
    original = common.read_original_manifest(paths["original_run"])
    common.verify_original_source(paths["source"], original)
    common.require(common.sha(paths["matched"]) == original["matched_sha256"], "matched input bytes differ")
    preflight_manifest = common.read_json(paths["preflight"] / "manifest.json", freeze["preflight_manifest_sha256"])
    common.verify_environment(paths["source"], original, Path(request["locked_python"]), preflight_manifest, attempt)
    for name in ("matplotlib", "numba", "pytensor"):
        (attempt / "cache" / name).mkdir(parents=True)
    os.environ.update(MPLCONFIGDIR=str(attempt / "cache/matplotlib"), NUMBA_CACHE_DIR=str(attempt / "cache/numba"),
                      PYTENSOR_FLAGS=f"compiledir={attempt / 'cache/pytensor'}")
    sys.path.insert(0, str(paths["source"]))
    module_names = {
        "runner": "src.pipelines.extensions.runner", "planning": "src.pipelines.extensions.planning",
        "preprocessing": "src.pipelines.extensions.preprocessing", "folds": "src.data.survival_folds",
        "conditions": "src.pipelines.robustness.conditions", "io": "src.utils.io",
        "options": "src.pipelines.confirmatory.options", "reproducibility": "src.utils.reproducibility"}
    modules = {key: importlib.import_module(name) for key, name in module_names.items()}
    common.verify_src_modules(paths["source"], original)
    import platform

    import numpy as np
    common.require(platform.python_version() == original["environment"]["python"]
                   and modules["reproducibility"].dependency_versions() == original["environment"]["dependencies"],
                   "actual normal child Python/dependency versions differ")
    contracts = common.module_from_pin(paths["contracts"], common.CONTRACTS_SHA, "_reuse_bound_contracts")
    pf = common.module_from_pin(paths["preflight_core"], common.PREFLIGHT_CORE_SHA, "_reuse_bound_core")
    reuse = common.module_from_pin(paths["reuse_core"], common.REUSE_CORE_SHA, "_terminal_reuse_core")
    complete = reuse.CompletePreflight(paths["preflight"], rows)
    common.require(complete.completion == completion and complete.manifest == preflight_manifest, "complete preflight differs")
    cohorts = modules["runner"].load_extension_cohorts(paths["source"], paths["matched"])
    jobs = modules["planning"].build_extension_jobs(cohorts, original["run_config"])
    plan = [{"cell_id": job.cell_id, "train_sha256": common.digest(cohorts[job.dataset].subject_id.iloc[job.train].tolist()),
             "validation_sha256": common.digest(cohorts[job.dataset].subject_id.iloc[job.validation].tolist()),
             "censoring_cutoff": job.censoring_cutoff} for job in jobs]
    common.require(plan == original["plan"] and len(jobs) == 1625, "normal original full plan differs")
    identity = request["original_cell_id"]
    job = next(job for job in jobs if job.cell_id == identity)
    chosen = rc.selected_contexts(rows, identity, job.model)
    witness_path = common.below(paths["witness_root"], entry["input_witness_path"])
    witness = common.read_json(witness_path, entry["input_witness_sha256"])
    common.verify_witness_proofs(witness_path.parent, witness, contracts)
    context_status = {row["context_id"].split("::")[-1]: complete.lookup[row["context_id"]]["status"] for row in chosen}
    abstract = {key: "accepted" if value in rc.ACCEPTED else value for key, value in context_status.items()}
    common.require(any(status in rc.TERMINAL for status in context_status.values())
                   and {key: value[0] for key, value in witness["fit_witness"]["generator_contexts"].items()} == abstract
                   and {key: value[1] for key, value in witness["fit_witness"]["generator_contexts"].items()} == {
                       row["context_id"].split("::")[-1]: complete.lookup[row["context_id"]]["receipt_sha256"] for row in chosen},
                   "terminal input action requires nonaccepted bound context")
    backend, outcomes = NormalTrainingBackend(paths["source"], modules), []
    (attempt / "contexts").mkdir()
    source_names = ("src/__init__.py", "src/pipelines/__init__.py", "src/pipelines/extensions/__init__.py",
                    "src/pipelines/confirmatory/__init__.py", "src/pipelines/confirmatory/options.py",
                    "src/pipelines/extensions/preprocessing.py", "src/models/__init__.py", "src/models/catalytic.py",
                    "src/models/base.py", "src/data/__init__.py", "src/data/fold_preprocessing.py",
                    "src/utils/__init__.py", "src/utils/reproducibility.py")
    source_pins = {name: original["input_sha256"][name] for name in source_names}
    for row in chosen:
        directory, saved = complete.context(row)
        destination = attempt / "contexts" / row["context_id"].split("::")[-1]
        destination.mkdir()
        try:
            inputs = pf.build_context(row, job, cohorts[job.dataset], backend)
        except pf.InvalidCheckpoint:
            raise
        except Exception as error:
            actual = {"status": "input_failure", "attempts": [], "accepted_attempt_index": None,
                      "input_error": pf.error_record(error), "input_witness_sha256": None}
        else:
            common.require(pf.canonical_hash(inputs.witness) == saved["request"].get("input_witness_sha256"), "normal full raw input witness differs")
            def save(record: dict[str, Any], arrays: Any) -> None:
                target = destination / f"attempt_{record['attempt_index']:03d}"
                target.mkdir()
                artifacts = {}
                if arrays is not None:
                    pf.save_arrays(target / "proposal.npz", arrays)
                    artifacts["proposal.npz"] = pf.artifact_binding(target / "proposal.npz")
                common.write_new(target / "receipt.json", common.seal({**record, "artifacts": artifacts}))
            actual = replay_recipe(inputs, row,
                lambda current, seed: original_draw(modules["preprocessing"], current, seed, pf, modules["options"], source_pins, np),
                modules["options"].deterministic_seed, save)
            actual["input_witness_sha256"] = pf.canonical_hash(inputs.witness)
        # Publish actual failure/history first. A mismatch cannot erase it or
        # authorize a fit; the controller retains the child and nonzero logs.
        common.write_new(destination / "actual.json", common.seal({**actual, "context_id": row["context_id"],
                         "preflight_receipt_sha256": complete.lookup[row["context_id"]]["receipt_sha256"]}))
        assessment = rc.compare_context_history(saved, actual)
        for index, before in enumerate(saved["attempts"]):
            if before["status"] == "nonrank_error":
                continue
            old = pf.read_arrays(directory / f"attempt_{index:03d}/proposal.npz")
            new = pf.read_arrays(destination / f"attempt_{index:03d}/proposal.npz")
            common.require(set(old) == set(new) == rc.NUMERIC_KEYS
                           and all(np.array_equal(old[key], new[key], equal_nan=True) for key in old),
                           "actual constructor arrays differ from sealed preflight")
        outcomes.append({"context_id": row["context_id"], "status": actual["status"], "assessment": assessment,
                         "actual_receipt_path": str((destination / "actual.json").relative_to(attempt)),
                         "actual_receipt_sha256": common.sha(destination / "actual.json")})
    common.verify_original_source(paths["source"], original)
    common.verify_src_modules(paths["source"], original)
    common.require(common.sha(paths["matched"]) == original["matched_sha256"], "matched input changed during terminal replay")
    rc.load_selection(Path(request["selection_path"]), request["selection_sha256"], own)
    artifacts = {str(path.relative_to(attempt)): common.file_binding(path) for path in sorted(attempt.rglob("*")) if path.is_file()}
    common.write_new(attempt / "receipt.json", common.seal({"schema_version": 1,
        "status": "selected_terminal_full_recipe_independently_replayed_without_fit", "original_cell_id": identity,
        "selection_sha256": request["selection_sha256"], "scope_definition_sha256": rc.scope_definition(selection),
        "corrected_manifest_sha256": selection["corrected_manifest_sha256"], "input_witness_sha256": entry["input_witness_sha256"],
        "contexts": outcomes, "artifacts": artifacts, "normal_full_raw_training_preprocessor_fit": True,
        "candidate_adapter_restoration_or_thinning_used": False, "scoped_context_count": len(chosen),
        "all1650_contexts_replayed": False, "no_model_optimizer_mcmc_prediction_or_score_executed": True,
        "new_numerical_fitted_cell_reproduction": False, "runtime": common.validate_runtime(Path(request["locked_python"]))}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    arguments = parser.parse_args()
    execute(arguments.request, arguments.request_sha256)
