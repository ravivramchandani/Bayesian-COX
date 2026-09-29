"""One isolated corrected cell, delegated to unchanged original scientific code."""

from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import sys
import threading
import traceback
from contextlib import AbstractContextManager
from pathlib import Path
from types import FrameType
from typing import Any

# -I omits the script directory. Verify the explicitly supplied request before
# loading the support module; the controller has checked this child's bytes.
if __name__ == "__main__":
    _bootstrap = argparse.ArgumentParser(add_help=False)
    _bootstrap.add_argument("--request", type=Path, required=True)
    _bootstrap.add_argument("--request-sha256", required=True)
    _initial, _unknown = _bootstrap.parse_known_args()
    if hashlib.sha256(_initial.request.read_bytes()).hexdigest() != _initial.request_sha256:
        raise RuntimeError("child request byte hash differs")
    _document = json.loads(_initial.request.read_text())
    _support = Path(__file__).absolute().with_name("fit_common.py")
    if hashlib.sha256(_support.read_bytes()).hexdigest() != _document["implementation_source_sha256"]["fit_common.py"]:
        raise RuntimeError("child support source byte pin differs")
    sys.path.insert(0, str(_support.parent))

import fit_common as common  # noqa: E402 - explicit verified support bootstrap

sys.dont_write_bytecode = True


class InputBoundaryAbort(BaseException):
    """A binding violation must escape the original generic fit-failure catch."""


def boundary(condition: bool, message: str) -> None:
    """Abort a child without turning unsafe evidence into a scientific failure."""
    if not condition:
        raise InputBoundaryAbort(message)


class GenerationSupply:
    """Supply only accepted byte-verified proposals to original generation sites.

    Args:
        contexts: Outer and all WME inner bound context records and arrays.
        constructor: The normally imported original ``CatalyticData`` class.
        core: Byte-pinned preflight array/source witness functions.
    Returns:
        Calls return the original guarded object and unchanged accepted legacy
        metadata. They never sample, select a proposal using scores or fit.
    Raises:
        InputBoundaryAbort: A current call does not match its frozen training
        context, constructor rejects the saved accepted proposal, or a context
        is consumed twice. Original constructor guards are always executed.
    """

    def __init__(self, contexts: dict[str, dict[str, Any]], constructor: Any, core: Any) -> None:
        self.contexts, self.constructor, self.core = contexts, constructor, core
        self.calls: list[dict[str, Any]] = []
        self.by_seed = {row["input_witness"]["original_generation_seed"]: name
                        for name, row in contexts.items()}
        boundary(len(self.by_seed) == len(contexts), "generation seeds collide")

    def verify_training(self, name: str, training: Any, processor: Any, times: Any, events: Any) -> None:
        """Bind ordered raw sources, complete state and censored real arrays."""
        row = self.contexts[name]
        witness, saved = row["input_witness"], row["real_arrays"]
        boundary(training.subject_id.tolist() == witness["ordered_training_subject_ids"],
                 "ordered current training patients differ")
        boundary(processor.metadata() == witness["processor_metadata"]
                 and common.digest(processor.metadata()) == witness["processor_metadata_sha256"]
                 and list(processor.feature_names) == witness["feature_names"], "training processor differs")
        sources = list(dict.fromkeys(processor.clinical.required_source_columns + processor.genes))
        boundary(self.core.source_frame_witness(training, sources) == witness["source_values"],
                 "current generator source values differ")
        actual = {"real_design": processor.transform(training).to_numpy(float),
                  "real_time": times, "real_event": events}
        keys = {"real_design": "real_design", "real_time": "training_time", "real_event": "training_event"}
        for key, array in actual.items():
            signature = self.core.array_witness(array)
            boundary(signature == self.core.array_witness(saved[key]) == witness[keys[key]],
                     f"current real array differs: {name}:{key}")

    def __call__(self, training: Any, processor: Any, times: Any, events: Any, seed: int) -> tuple[Any, dict[str, Any]]:
        """Match an original seed/context, then run the untouched constructor."""
        boundary(type(seed) is int and seed in self.by_seed, "unexpected original generation seed")
        name = self.by_seed[seed]
        boundary(name not in {item["context"] for item in self.calls}, "generation context consumed twice")
        self.verify_training(name, training, processor, times, events)
        row = self.contexts[name]
        arrays = row["proposal_arrays"]
        try:
            synthetic = self.constructor(arrays["synthetic_design"].copy(), arrays["synthetic_time"].copy(),
                                         float(arrays["hazard"]))
        except Exception as error:
            raise InputBoundaryAbort(f"saved accepted original constructor rejected: {name}: {type(error).__name__}: {error}") from error
        legacy = row["legacy_metadata"]
        boundary(isinstance(legacy, dict), "accepted proposal lacks returned original metadata")
        self.calls.append({"context": name, "original_generation_seed": seed,
                           "accepted_proposal_seed": row["accepted_seed"],
                           "accepted_attempt_index": row["accepted_attempt_index"],
                           "context_receipt_sha256": row["receipt_sha256"],
                           "legacy_metadata_sha256": common.digest(legacy)})
        return synthetic, copy.deepcopy(legacy)


class AliasScope(AbstractContextManager["AliasScope"]):
    """Own serial aliases in one fresh process and restore every original value."""

    def __init__(self) -> None:
        self.previous: list[tuple[Any, str, Any]] = []

    def __enter__(self) -> AliasScope:
        boundary(threading.active_count() == 1, "Python thread concurrency is not allowed for aliases")
        return self

    def set(self, owner: Any, name: str, replacement: Any) -> None:
        """Retain an existing attribute before replacing it in the owned child."""
        boundary(not any(obj is owner and attribute == name for obj, attribute, _ in self.previous),
                 "alias already replaced")
        self.previous.append((owner, name, getattr(owner, name)))
        setattr(owner, name, replacement)

    def __exit__(self, *_arguments: Any) -> None:
        for owner, name, original in reversed(self.previous):
            setattr(owner, name, original)


def finite_value(value: Any) -> Any:
    """Represent actual nonfinite telemetry explicitly without JSON NaNs."""
    import math
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, dict):
        return {str(key): finite_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [finite_value(item) for item in value]
    if hasattr(value, "tolist"):
        return finite_value(value.tolist())
    number = float(value)
    return number if math.isfinite(number) else {"nonfinite": "nan" if math.isnan(number) else "positive_infinity" if number > 0 else "negative_infinity"}


class Observations:
    """Retain original candidate errors and actual optimizer predicates only.

    Observers call each original optimizer/kernel/model method exactly once,
    return the same result, preserve its exception and never add a fit or gate.
    Telemetry errors abort evidence production instead of silently omitting
    required evidence. No optimizer or model function is called by construction.
    """

    def __init__(self, fitting: Any, catalytic: Any, np: Any) -> None:
        self.fitting, self.catalytic, self.np = fitting, catalytic, np
        self.select_original = fitting.select_parameters
        self.make_original, self.minimize_original = fitting.make_model, catalytic.minimize
        self.kernel_original, self.weighted_original = catalytic.catalytic_kernel, catalytic.weighted_breslow_objective
        self.model_calls: list[dict[str, Any]] = []
        self.optimizers: list[dict[str, Any]] = []
        self.tuning: dict[str, Any] = {"invoked": False, "reused": False, "candidate_slots": [], "rows": []}
        self.current_model: dict[str, Any] | None = None
        self.in_optimizer = False
        self.post_optimizer: tuple[Any, dict[str, Any]] | None = None
        self.score_lengths: dict[int, int] = {}
        self.fit_aliases: list[tuple[Any, bool, Any]] = []

    def make_model(self, key: str, parameters: dict[str, Any], *args: Any, **kwargs: Any) -> Any:
        """Wrap real returned fit methods; construction/order/arguments stay intact."""
        caller = sys._getframe(1)
        inner = caller.f_code is self.select_original.__code__
        fold = getattr(caller.f_locals.get("fold"), "fold", None) if inner else None
        ci = caller.f_locals.get("ci") if inner else None
        record = {"index": len(self.model_calls), "scope": "inner" if inner else "outer",
                  "fold": fold, "candidate_index_zero_based": ci, "model": key,
                  "parameters": copy.deepcopy(parameters), "seed": kwargs.get("seed"),
                  "attempt_index": kwargs.get("attempt", 0), "construction": "started", "fit": "not_invoked"}
        self.model_calls.append(record)
        try:
            model = self.make_original(key, parameters, *args, **kwargs)
        except BaseException as error:
            record.update(construction="raised", construction_error=self.error(error))
            raise
        record["construction"] = "returned"
        original_fit = model.fit
        had_instance_fit = "fit" in model.__dict__
        old_instance_fit = model.__dict__.get("fit")
        self.fit_aliases.append((model, had_instance_fit, old_instance_fit))

        def observed_fit(*fit_args: Any, **fit_kwargs: Any) -> Any:
            previous = self.current_model
            self.current_model = record
            record["fit"] = "started"
            try:
                result = original_fit(*fit_args, **fit_kwargs)
                record["fit"] = "returned"
                return result
            except BaseException as error:
                record.update(fit="raised", fit_error=self.error(error))
                raise
            finally:
                self.current_model = previous
                if had_instance_fit:
                    model.fit = old_instance_fit
                else:
                    model.__dict__.pop("fit", None)

        model.fit = observed_fit
        return model

    def restore_models(self) -> None:
        """Restore even a returned model whose fit was never reached."""
        for model, existed, original in reversed(self.fit_aliases):
            if existed:
                model.fit = original
            else:
                model.__dict__.pop("fit", None)

    @staticmethod
    def error(error: BaseException) -> dict[str, Any]:
        """Retain real exception identity/message without relabelling its cause."""
        return {"type": f"{type(error).__module__}.{type(error).__qualname__}", "message": str(error)}

    def minimize(self, *args: Any, **kwargs: Any) -> Any:
        """Capture one actual original optimizer result and return it unchanged."""
        record = {"index": len(self.optimizers), "model_call_index": None if self.current_model is None else self.current_model["index"],
                  "method": kwargs.get("method"), "options": copy.deepcopy(kwargs.get("options")),
                  "jac_argument": kwargs.get("jac"), "status": "started", "post_optimum_predicate": None}
        self.optimizers.append(record)
        prior = self.in_optimizer
        self.in_optimizer = True
        try:
            result = self.minimize_original(*args, **kwargs)
        except BaseException as error:
            record.update(status="raised", error=self.error(error))
            raise
        finally:
            self.in_optimizer = prior
        record.update(status="returned", success=bool(result.success),
                      x_finite=bool(self.np.isfinite(result.x).all()),
                      x=finite_value(result.x), jac=finite_value(getattr(result, "jac", None)),
                      max_absolute_jac=None if getattr(result, "jac", None) is None else finite_value(self.np.max(self.np.abs(result.jac))),
                      fun=finite_value(getattr(result, "fun", None)), nit=finite_value(getattr(result, "nit", None)),
                      message=str(result.message), optimizer_status=finite_value(getattr(result, "status", None)))
        self.post_optimizer = (result, record)
        return result

    def _post(self, kind: str, beta: Any, value: Any, score: Any) -> None:
        """Observe the already-called original post-optimum kernel/score."""
        if self.in_optimizer or self.post_optimizer is None:
            return
        result, record = self.post_optimizer
        if not self.np.array_equal(beta, result.x, equal_nan=True):
            return
        maximum = self.np.max(self.np.abs(score))
        predicate = ((not result.success or not self.np.isfinite(value) or maximum > 1e-6)
                     if kind == "kappa" else
                     (not result.success or not self.np.isfinite(result.x).all() or maximum > 1e-4))
        record["post_optimum_predicate"] = {"kind": kind, "value": finite_value(value),
                                              "value_finite": bool(self.np.isfinite(value)),
                                              "max_absolute_score": finite_value(maximum),
                                              "score_all_finite": bool(self.np.isfinite(score).all()),
                                              "tolerance": 1e-6 if kind == "kappa" else 1e-4,
                                              "original_reject_predicate": bool(predicate)}
        self.post_optimizer = None

    def kernel(self, beta: Any, *args: Any, **kwargs: Any) -> Any:
        """Return the original catalytic kernel and retain a real post-opt value."""
        result = self.kernel_original(beta, *args, **kwargs)
        self._post("kappa", beta, *result)
        return result

    def weighted(self, beta: Any, *args: Any, **kwargs: Any) -> Any:
        """Return the original weighted Cox objective with its observed predicate."""
        result = self.weighted_original(beta, *args, **kwargs)
        self._post("wme", beta, *result)
        return result

    def trace(self, frame: FrameType, event: str, argument: Any) -> Any:
        """Copy only small candidate records from the unchanged tuning frame."""
        if frame.f_code is not self.select_original.__code__:
            return None
        rows = frame.f_locals.get("rows")
        if rows is not None:
            self.tuning["rows"] = finite_value(copy.deepcopy(rows))
            fold = getattr(frame.f_locals.get("fold"), "fold", None)
            for ci, row in enumerate(rows):
                old = self.score_lengths.get(ci, 0)
                if len(row["scores"]) > old:
                    boundary(len(row["scores"]) == old + 1 and fold in {1, 2, 3}, "ambiguous original score telemetry")
                    self.tuning["candidate_slots"].append({"fold": fold, "candidate_index_zero_based": ci,
                                                           "status": "score_recorded", "score": finite_value(row["scores"][-1])})
                    self.score_lengths[ci] = len(row["scores"])
        if event == "exception":
            error = argument[1]
            self.tuning["last_observed_exception"] = self.error(error)
        return self.trace

    def select(self, *args: Any, **kwargs: Any) -> Any:
        """Call original tuning once and preserve partial rows when it raises."""
        if args[0] != "catalytic_wme":
            return self.select_original(*args, **kwargs)
        boundary(sys.gettrace() is None, "existing trace hook prevents isolated tuning observations")
        self.tuning["invoked"] = True
        sys.settrace(self.trace)
        try:
            result = self.select_original(*args, **kwargs)
            self.tuning["returned"] = finite_value(copy.deepcopy(result))
            return result
        except BaseException as error:
            self.tuning["raised"] = self.error(error)
            raise
        finally:
            sys.settrace(None)
            # Every attempted failure has its original fold. Unvisited slots
            # remain explicit, never fabricated optimizer or fit executions.
            slots = {(item["fold"], item["candidate_index_zero_based"]): item
                     for item in self.tuning["candidate_slots"]}
            for ci, row in enumerate(self.tuning["rows"]):
                for failure in row.get("failures", []):
                    slots[(failure["fold"], ci)] = {"fold": failure["fold"], "candidate_index_zero_based": ci,
                                                       "status": "original_candidate_failure", "failure": failure}
            self.tuning["candidate_slots"] = [slots.get((fold, ci), {"fold": fold, "candidate_index_zero_based": ci,
                                                                       "status": "not_executed_before_tuning_exit"})
                                                    for fold in range(1, 4) for ci in range(3)]

    def data(self) -> dict[str, Any]:
        """Return observed telemetry without upgrading it to a numerical gate."""
        return {"model_calls": self.model_calls, "optimizer_calls": self.optimizers, "inner_tuning": self.tuning,
                "additional_optimizer_calls": 0, "proposal_selection_by_optimizer": False,
                "original_predicates_and_selection_unchanged": True}


def load_contexts(preflight: Path, completion: dict[str, Any], identity: str, expected: dict[str, Any],
                  core: Any, contracts: Any) -> dict[str, dict[str, Any]]:
    """Verify full recorded attempt lineages before loading accepted arrays."""
    lookup = {row["context_id"]: row for row in completion["outcomes"]}
    found = {}
    for name, (abstract_status, receipt_sha) in expected.items():
        boundary(abstract_status == "accepted", "nonaccepted generator context cannot supply a fit")
        key = f"{identity}::{name}"
        boundary(key in lookup and lookup[key]["receipt_sha256"] == receipt_sha, "preflight context binding differs")
        path = common.below(preflight, lookup[key]["receipt_path"])
        boundary(path == preflight / "contexts" / identity / name / "receipt.json", "context path differs")
        receipt = common.read_json(path, receipt_sha)
        common.verify_files(path.parent, receipt["artifacts"])
        boundary(receipt["status"] in {"accepted_original_first_draw", "accepted_rank_conditioned_redraw"}
                 and lookup[key]["status"] == receipt["status"] and lookup[key]["receipt_content_sha256"] == receipt["content_sha256"],
                 "fit context is not an accepted original constructor")
        request = receipt["request"]
        boundary(request["context_id"] == key and request["run_binding_sha256"] == completion["run_binding_sha256"],
                 "preflight run/context request differs")
        attempts = receipt["attempts"]
        index, seed = receipt["accepted_attempt_index"], request["original_generation_seed"]
        boundary(type(index) is int and index == len(attempts) - 1 and 0 <= index < request["candidate_cap"] <= 256,
                 "accepted proposal/cap accounting differs")
        for ai, attempt in enumerate(attempts):
            expected_seed = seed if ai == 0 else contracts.deterministic_seed(seed, "rank_conditioned_retry", ai)
            boundary(attempt["request"] == request and attempt["attempt_index"] == ai and attempt["seed"] == expected_seed
                     and attempt["status"] == ("accepted_original_constructor" if ai == index else "frozen_rank_rejected"),
                     "attempt seed/order/rank-only accounting differs")
            attempt_path = path.parent / f"attempt_{ai:03d}" / "receipt.json"
            boundary(common.read_json(attempt_path) == attempt, "embedded proposal receipt differs")
            common.verify_files(attempt_path.parent, attempt["artifacts"])
        metadata = receipt["candidate_metadata"]
        boundary(metadata["proposal_metadata_sha256"] == common.digest({k: v for k, v in metadata.items() if k != "proposal_metadata_sha256"})
                 and metadata["accepted_attempt_index"] == index and metadata["attempts_generated"] == len(attempts)
                 and metadata["original_seed"] == seed and metadata["attempt_cap"] == request["candidate_cap"],
                 "accepted correction history differs")
        input_record = common.read_json(path.parent / "input.json")
        boundary(input_record["request"] == request
                 and common.digest(input_record["input_witness"]) == request["input_witness_sha256"], "real input witness differs")
        real = core.read_arrays(path.parent / "inputs.npz")
        proposal = core.read_arrays(path.parent / f"attempt_{index:03d}" / "proposal.npz")
        boundary(set(real) == {"real_design", "real_time", "real_event"}
                 and set(proposal) == {"synthetic_design", "synthetic_time", "hazard", "time_scale"}
                 and {name: core.array_witness(array) for name, array in proposal.items()} == attempts[-1]["array_witnesses"],
                 "numeric proposal archive keys/bytes differ")
        found[name] = {"input_witness": input_record["input_witness"], "real_arrays": real,
                       "proposal_arrays": proposal, "legacy_metadata": attempts[-1]["legacy_metadata"],
                       "accepted_seed": attempts[-1]["seed"], "accepted_attempt_index": index, "receipt_sha256": receipt_sha}
    return found


def delegate_cell(runner: Any, fitting: Any, catalytic: Any, job: Any, raw: Any, specification: dict[str, Any],
                  primary: dict[str, Any], config: dict[str, Any], attempt: Path,
                  supply: GenerationSupply, observations: Observations, cached_tuning: dict[str, Any] | None = None) -> dict[str, Any]:
    """Delegate the unchanged cell and all actual fit/evaluation calls exactly once."""
    with AliasScope() as scope:
        scope.set(runner, "generate_catalytic_data", supply)
        scope.set(fitting, "generate_catalytic_data", supply)
        scope.set(fitting, "make_model", observations.make_model)
        scope.set(catalytic, "minimize", observations.minimize)
        scope.set(catalytic, "catalytic_kernel", observations.kernel)
        scope.set(catalytic, "weighted_breslow_objective", observations.weighted)
        if cached_tuning is None:
            scope.set(runner, "select_parameters", observations.select)
        else:
            def selected(*args: Any, **kwargs: Any) -> Any:
                boundary(args[0] == "catalytic_wme" and kwargs["seed"] == cached_tuning["inner_cv_seed"],
                         "unexpected cached selection request")
                observations.tuning.update(reused=True, selected_parameters=copy.deepcopy(cached_tuning["selected_parameters"]),
                                          inner_tuning=copy.deepcopy(cached_tuning["inner_tuning"]),
                                          source_record_sha256=cached_tuning["source_record_sha256"])
                return copy.deepcopy(cached_tuning["selected_parameters"]), copy.deepcopy(cached_tuning["inner_tuning"])
            scope.set(runner, "select_parameters", selected)
        try:
            return runner.run_extension_cell(job, raw, specification, primary, config, attempt)
        finally:
            observations.restore_models()


def main() -> None:
    """Require real gates, clean normal imports, actual byte checks, then one cell."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    args = parser.parse_args()
    request = common.read_json(common.safe(args.request), args.request_sha256)
    runtime = common.validate_runtime(Path(request["locked_python"]))
    own = Path(__file__).absolute().parent
    boundary(request["implementation_source_sha256"] == {name: common.sha(own / name) for name in common.OWN_SOURCES},
             "child sources changed after dispatch")
    freeze, manifest, _, completion = common.load_gates(Path(request["freeze_path"]), request["freeze_sha256"],
                                                       Path(request["manifest_path"]), request["manifest_sha256"], own)
    paths = {key: Path(value) for key, value in freeze["paths"].items()}
    original = common.read_original_manifest(paths["original_run"])
    common.verify_original_source(paths["source"], original)
    boundary(common.sha(paths["matched"]) == original["matched_sha256"], "matched input changed")
    attempt = common.safe(Path(request["attempt_path"]))
    boundary(attempt.is_dir() and not (attempt / "cells").exists() and not (attempt / "traces").exists(), "child attempt already contains scientific output")
    preflight_manifest = common.read_json(paths["preflight"] / "manifest.json", freeze["preflight_manifest_sha256"])
    fresh_environment = common.verify_environment(paths["source"], original, Path(request["locked_python"]), preflight_manifest, attempt)
    boundary(not any(name == "src" or name.startswith("src.") for name in sys.modules), "foreign src namespace already loaded")
    sys.path.insert(0, str(paths["source"]))
    runner = importlib.import_module("src.pipelines.extensions.runner")
    fitting = importlib.import_module("src.pipelines.extensions.fitting")
    catalytic = importlib.import_module("src.models.catalytic")
    planning = importlib.import_module("src.pipelines.extensions.planning")
    options = importlib.import_module("src.pipelines.confirmatory.options")
    io = importlib.import_module("src.utils.io")
    reproducibility = importlib.import_module("src.utils.reproducibility")
    common.verify_src_modules(paths["source"], original)
    import platform

    import numpy as np
    dependencies = reproducibility.dependency_versions()
    boundary(platform.python_version() == original["environment"]["python"]
             and dependencies == original["environment"]["dependencies"]
             and common.digest(dependencies) == original["environment"]["dependency_set_sha256"]
             and Path(request["locked_python"]).samefile(Path(sys.executable)),
             "locked scientific dependency/Python/interpreter identity differs")
    environment = {"status": "exact_lock_versions_match", "observed_python": platform.python_version(),
                   "observed_dependencies": dependencies, "observed_dependency_set_sha256": common.digest(dependencies),
                   "frozen_environment_sha256": common.digest(original["environment"]),
                   "observed_executable": sys.executable, "locked_interpreter_samefile": True}
    primary, config = io.read_mapping(paths["source"] / "config/confirmatory.yaml"), io.read_mapping(paths["source"] / "config/extensions.yaml")
    boundary(config == original["run_config"], "original complete fit/evaluation configuration differs")
    common.validate_budget(config)
    cohorts = runner.load_extension_cohorts(paths["source"], paths["matched"])
    jobs = planning.build_extension_jobs(cohorts, config)
    plan = [{"cell_id": job.cell_id, "train_sha256": common.digest(cohorts[job.dataset].subject_id.iloc[job.train].tolist()),
             "validation_sha256": common.digest(cohorts[job.dataset].subject_id.iloc[job.validation].tolist()),
             "censoring_cutoff": job.censoring_cutoff} for job in jobs]
    boundary(plan == original["plan"] and len(jobs) == 1625, "original full plan reconstruction differs")
    identity = request["original_cell_id"]
    job = next(job for job in jobs if job.cell_id == identity)
    entry = request["entry"]
    witness_path = common.below(paths["witness_root"], entry["input_witness_path"])
    witness_document = common.read_json(witness_path, entry["input_witness_sha256"])
    common.verify_files(witness_path.parent, witness_document["proof_artifacts"])
    contracts = common.module_from_pin(paths["contracts"], common.CONTRACTS_SHA, "_correction_fit_contracts_child")
    common.verify_witness_proofs(witness_path.parent, witness_document, contracts)
    core = common.module_from_pin(paths["preflight_core"], common.PREFLIGHT_CORE_SHA, "_correction_preflight_core_child")
    witness = common.witness_from_json(contracts, witness_document, request["source_evidence"])
    decision = contracts.classify(witness)
    boundary(decision["action"] == request["action"] and decision["action"] in common.FIT_ACTIONS,
             "fresh child input decision differs")
    old = common.verify_original_outcome(paths["original_run"], identity, request["source_evidence"])
    boundary(old is not None, "original owner is unfinished or source outcome unbound")
    contexts = load_contexts(paths["preflight"], completion, identity, witness.generator_contexts, core, contracts)
    supply = GenerationSupply(contexts, catalytic.CatalyticData, core)
    specification = io.read_mapping(paths["source"] / "config/datasets.yaml")["metabric" if job.dataset == "metabric_matched" else job.dataset]["primary_features"]
    # The separate reviewed witness builder supplies the reconstruction-only
    # API. Its concrete protocol is checked before any scientific delegation.
    boundary("_reuse_bound_core" not in sys.modules and "_reuse_bound_contracts" not in sys.modules,
             "reuse helper injection namespaces already occupied")
    sys.modules["_reuse_bound_core"], sys.modules["_reuse_bound_contracts"] = core, contracts
    reuse = common.module_from_pin(paths["reuse_core"], freeze["dependency_source_sha256"]["reuse_core"], "_correction_reuse_core_child")
    boundary(hasattr(reuse, "verify_execution_inputs"), "reviewed reconstruction-only reuse adapter is not integrated")
    verified = reuse.verify_execution_inputs(job=job, raw=cohorts[job.dataset], runner=runner, fitting=fitting,
                                             primary=primary, manifest=original, input_witness=witness_document,
                                             preflight_contexts=contexts, core=core, contracts=contracts,
                                             witness_directory=witness_path.parent,
                                             input_witness_sha256=entry["input_witness_sha256"],
                                             environment_verification=fresh_environment["report"])
    common.verify_src_modules(paths["source"], original)
    boundary(verified["status"] == "current_complete_inputs_match_corrected_witness"
             and verified["input_witness_sha256"] == entry["input_witness_sha256"], "full corrected execution inputs differ")
    expected_roles = {name: witness.roles[name].corrected_sha256 for name in contracts.required_roles(witness.model)}
    boundary(verified["required_role_count"] == len(expected_roles)
             and verified["corrected_role_sha256"] == expected_roles
             and verified["no_generator_model_fit_prediction_or_score_executed"] is True,
             "current reconstructed role surface differs")
    verification_receipt = verified["receipt"]
    boundary(verification_receipt["content_sha256"] == common.digest({key: value for key, value in verification_receipt.items() if key != "content_sha256"})
             and verification_receipt["status"] == verified["status"]
             and verification_receipt["input_witness_sha256"] == entry["input_witness_sha256"]
             and verification_receipt["definition_content_sha256"] == freeze["definition_content_sha256"]
             and verification_receipt["corrected_role_sha256"] == expected_roles,
             "small complete-input verification receipt differs")
    for name, row in verified["generator_training_contexts"].items():
        boundary(name in contexts, "unexpected reconstructed context")
        supply.verify_training(name, row["training"], row["processor"], row["time"], row["event"])
    boundary(set(verified["generator_training_contexts"]) == set(contexts), "all WME inner context dependencies required")
    cached = None
    if decision["action"] == "fit_changed_inputs_reuse_tuning":
        tuning_sha = common.digest({"selected_parameters": old["selected_parameters"], "inner_tuning": old["inner_tuning"]})
        boundary(tuning_sha == decision["tuning_record_reused_sha256"], "recorded WME selection changed")
        cached = {"selected_parameters": old["selected_parameters"], "inner_tuning": old["inner_tuning"],
                  "source_record_sha256": tuning_sha, "inner_cv_seed": options.deterministic_seed(witness.corrected_seeds["cell"], "inner_cv")}
    observations = Observations(fitting, catalytic, np)
    try:
        cell = delegate_cell(runner, fitting, catalytic, job, cohorts[job.dataset], specification, primary, config,
                             attempt, supply, observations, cached)
    finally:
        common.write_new(attempt / "observations.json", common.seal({"original_cell_id": identity,
                          "generation_calls": supply.calls, "all_bound_generator_contexts": sorted(contexts),
                          "telemetry": observations.data(), "scope": "actual_unchanged_original_execution_observation"}))
    boundary(cell["cell_id"] == identity and cell["status"] in common.OUTCOMES
             and cell["cell_content_sha256"] == common.digest({k: v for k, v in cell.items() if k != "cell_content_sha256"}),
             "original delegated cell identity/content differs")
    common.verify_original_source(paths["source"], original)
    common.verify_src_modules(paths["source"], original)
    boundary(common.sha(paths["matched"]) == original["matched_sha256"]
             and common.verify_original_outcome(paths["original_run"], identity, request["source_evidence"]) is not None,
             "input/source ownership changed during fit")
    common.load_gates(Path(request["freeze_path"]), request["freeze_sha256"], Path(request["manifest_path"]), request["manifest_sha256"], own)
    common.verify_files(witness_path.parent, witness_document["proof_artifacts"])
    for name, (_, receipt_sha) in witness.generator_contexts.items():
        context_path = paths["preflight"] / "contexts" / identity / name / "receipt.json"
        context_receipt = common.read_json(context_path, receipt_sha)
        common.verify_files(context_path.parent, context_receipt["artifacts"])
    (attempt / "cells").mkdir()
    common.write_new(attempt / "cells" / f"{identity}.json", cell)
    common.write_new(attempt / "child_receipt.json", common.seal({"status": "original_cell_delegated_with_verified_corrected_inputs",
                     "original_cell_id": identity, "corrected_manifest_sha256": request["manifest_sha256"],
                     "cell": common.file_binding(attempt / "cells" / f"{identity}.json"),
                     "observations": common.file_binding(attempt / "observations.json"),
                     "input_witness_sha256": entry["input_witness_sha256"], "action": decision["action"],
                     "original_seed_namespace": witness.corrected_seeds,
                     "full_current_execution_input_verification": verified["receipt"],
                     "full_environment_verification": fresh_environment["report"],
                     "actual_process_runtime_verification": runtime,
                     "supplemental_interpreter_version_verification": environment,
                     "scientific_status": cell["status"], "fit_dispatched": True,
                     "programme_complete": False, "reporting_certified": False, "release_certified": False}))
    print(json.dumps({"cell_id": identity, "status": cell["status"], "child_receipt_sha256": common.sha(attempt / "child_receipt.json")}, sort_keys=True), flush=True)


if __name__ == "__main__":
    try:
        main()
    except BaseException:
        traceback.print_exc()
        raise
