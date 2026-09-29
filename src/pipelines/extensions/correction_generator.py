"""One synthetic-input candidate; no fitting, evaluation or reuse certification.

The pure wrapper retries only a tagged rejection from the frozen constructor.
The original-source adapter runs each complete proposal in a fresh child and
keeps interception out of the caller's process. This is not a frozen method.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import pickle
import subprocess
import sys
import threading
import types
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

RANK_MESSAGE = "synthetic design is not full column rank"
CANDIDATE_CAP = 256
RETRY_LABEL = "rank_conditioned_retry"
SOURCE_PINS = {
    "src/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "src/pipelines/__init__.py": "1005c54824748f721b35128f106e3385e4a77425b22afc8600a1854db6dd95d0",
    "src/pipelines/extensions/__init__.py": "e4217b1fe22d45e1febc65fa320b455769912fae513f04bff0504d879d3a90f0",
    "src/pipelines/confirmatory/__init__.py": "bdfc04a0accfc39f32a8c53f9345fa14a943072a4b3a203aa34ff7c8ac3d4185",
    "src/pipelines/confirmatory/options.py": "3b8e03d1f11770be98d4c6c68a21123475a8f3b61a8fe26c55f40e50daafe49e",
    "src/pipelines/extensions/preprocessing.py": "94f40f635c0b072e6f42314a04f7447f5ee9546297ee4fcd3cfed42a2af9f635",
    "src/models/__init__.py": "7983aabd5d70ad3074441fab9486a85fa05a6da3d93a34e80780b6585ea4ce59",
    "src/models/catalytic.py": "53b38e5d9314fefcfd37260ac95d1bd9400af44f564c2142f7e7d61986f20332",
    "src/models/base.py": "8e18214edccf2ced6f6f790ccd8e624490add80581b177efd7b1b78b7eddf355",
    "src/data/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "src/data/fold_preprocessing.py": "499006f731c5f26ed13ba69385dae29b21b510e3c64a550015487283a587f7fa",
    "src/utils/__init__.py": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "src/utils/reproducibility.py": "6cd0c57ffe823f85945bdf365b346b3183d38697fc25ee1781e06dc8e699f676",
}
_INTERCEPTION_LOCK = threading.Lock()


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(value: Any) -> str:
    return _sha(json.dumps(value, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False).encode())


def deterministic_seed(base_seed: int, *parts: object) -> int:
    """Use the exact frozen SHA-256 derivation in ``[0, 2**31 - 1)``."""
    payload = "|".join([str(base_seed), *(str(part) for part in parts)])
    digest = hashlib.sha256(payload.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % (2**31 - 1)


@dataclass(frozen=True)
class SyntheticInputs:
    """Captured constructor values: M-by-p design, M scaled times and rate.

    This carrier does not replace or bypass the original data constructor.
    Only an accepted original constructor permits an accepted proposal.
    """

    design: np.ndarray
    time: np.ndarray
    hazard: float

    def hashes(self) -> dict[str, Any]:
        """Describe exact dtype/shape/C-order values, plus canonical array values."""
        arrays = {}
        for name, array in (("design", self.design), ("time", self.time)):
            contiguous = np.ascontiguousarray(array)
            arrays[name] = {"dtype": contiguous.dtype.str, "shape": list(contiguous.shape),
                            "values_sha256": _sha(contiguous.tobytes(order="C"))}
        arrays["hazard"] = self.hazard
        arrays["synthetic_sha256"] = _canonical({"X": self.design.tolist(),
                                                "time": self.time.tolist()})
        return arrays


@dataclass(frozen=True)
class DrawProposal:
    """Actual constructor inputs, unchanged returned metadata and capture details.

    ``legacy_metadata`` is ``None`` when the original generator raised before
    returning it. ``actual_metadata`` is separately labelled instrumentation.
    """

    data: SyntheticInputs
    legacy_metadata: dict[str, Any] | None
    actual_metadata: dict[str, Any]


class FrozenRankRejection(ValueError):
    """Tag only the exact rank guard reached in the pinned original constructor."""

    def __init__(self, proposal: DrawProposal) -> None:
        """Retain actual rejected constructor inputs; fabricate no legacy metadata."""
        super().__init__(RANK_MESSAGE)
        self.proposal = proposal


@dataclass(frozen=True)
class RankConditionedResult:
    """Accepted proposal plus separate candidate attempt/cap/hash accounting."""

    proposal: DrawProposal
    proposal_metadata: dict[str, Any]


class RankConditionedExhausted(ValueError):
    """Explicit execution outcome when every bounded proposal fails rank."""

    def __init__(self, metadata: dict[str, Any]) -> None:
        """Expose the actual rejected attempt hashes and exhausted candidate cap."""
        super().__init__(f"rank-conditioned candidate exhausted {metadata['attempt_cap']} attempts")
        self.proposal_metadata = metadata


def generate_rank_conditioned(
    draw: Callable[[int], DrawProposal], original_seed: int, *, cap: int = CANDIDATE_CAP,
) -> RankConditionedResult:
    """Retry only tagged constructor rank failures, preserving the first proposal.

    Args:
        draw: Trusted proposal adapter. Only ``FrozenRankRejection`` from the
            actual original constructor is retryable; other exceptions escape.
        original_seed: Original nonnegative integer generator seed.
        cap: Candidate bound, including the unchanged first draw; integer 1–256.
            The default 256 is a candidate setting, not a scientific freeze.

    Returns:
        The accepted original proposal and separate deterministic attempt history.

    Raises:
        ValueError: Seed/cap is invalid. Nonrank original errors propagate.
        RankConditionedExhausted: All ``cap`` original proposals failed rank.
    """
    _require(type(cap) is int and 1 <= cap <= CANDIDATE_CAP, "candidate cap must be an integer in 1..256")
    _require(type(original_seed) is int and original_seed >= 0, "original seed must be a nonnegative integer")
    attempts: list[dict[str, Any]] = []
    metadata: dict[str, Any] = {
        "schema_version": 1, "candidate": "bounded_rank_conditioned_v1",
        "original_seed": original_seed, "attempt_cap": cap, "retry_label": RETRY_LABEL,
        "attempts": attempts, "scientific_method_approved": False, "new_freeze_created": False,
        "fit_reuse_certified": False, "fitting_provenance_compatibility_certified": False,
        "full_block_preflight_performed": False, "scope": "synthetic_proposal_inputs_only",
    }
    for index in range(cap):
        seed = original_seed if index == 0 else deterministic_seed(original_seed, RETRY_LABEL, index)
        try:
            proposal = draw(seed)
        except FrozenRankRejection as error:
            if type(error) is not FrozenRankRejection:
                raise
            proposal = error.proposal
            attempts.append(_attempt_record(index, seed, "frozen_rank_rejected", proposal))
            continue
        attempts.append(_attempt_record(index, seed, "accepted_original_constructor", proposal))
        metadata.update(status="candidate_rank_conditioned_accepted", attempts_generated=len(attempts),
                        accepted_attempt_index=index, first_draw_accepted=index == 0, exhausted=False)
        metadata["proposal_metadata_sha256"] = _canonical(metadata)
        return RankConditionedResult(proposal, metadata)
    metadata.update(status="candidate_rank_conditioned_exhausted", attempts_generated=len(attempts),
                    accepted_attempt_index=None, first_draw_accepted=False, exhausted=True)
    metadata["proposal_metadata_sha256"] = _canonical(metadata)
    raise RankConditionedExhausted(metadata)


def _attempt_record(index: int, seed: int, status: str, proposal: DrawProposal) -> dict[str, Any]:
    return {"attempt_index": index, "seed": seed, "status": status,
            "constructor_inputs": proposal.data.hashes(), "actual_proposal_metadata": proposal.actual_metadata,
            "legacy_metadata_returned": proposal.legacy_metadata is not None,
            "legacy_metadata_sha256": None if proposal.legacy_metadata is None else _canonical(proposal.legacy_metadata)}


def _source_bytes(root: Path) -> dict[str, bytes]:
    _require(root.is_absolute() and ".." not in root.parts and root.is_dir()
             and not any(p.is_symlink() for p in (root, *root.parents)), "source checkout must be absolute and unlinked")
    result = {}
    for name, expected in SOURCE_PINS.items():
        path = root / name
        _require(path.is_file() and not any(p.is_symlink() for p in (path, *path.parents)), "unsafe original source")
        data = path.read_bytes()
        _require(_sha(data) == expected, f"original source bytes differ: {name}")
        result[name] = data
    return result


def _load_original(root: Path) -> tuple[types.ModuleType, types.ModuleType]:
    """Execute verified leaf bytes in a fresh child's minimal package namespace."""
    _require(not any(n == "src" or n.startswith("src.") for n in sys.modules), "foreign src modules already loaded")
    sources = _source_bytes(root)
    for name in ("src", "src.utils", "src.data", "src.models", "src.pipelines", "src.pipelines.extensions"):
        package = types.ModuleType(name)
        package.__path__ = [str(root / name.replace(".", "/"))]
        package.__file__ = str(root / name.replace(".", "/") / "__init__.py")
        sys.modules[name] = package
    modules = {}
    for name, path in (
        ("src.utils.reproducibility", "src/utils/reproducibility.py"),
        ("src.data.fold_preprocessing", "src/data/fold_preprocessing.py"),
        ("src.models.base", "src/models/base.py"),
        ("src.models.catalytic", "src/models/catalytic.py"),
        ("src.pipelines.extensions.preprocessing", "src/pipelines/extensions/preprocessing.py"),
        ("_pinned_original_seed_options", "src/pipelines/confirmatory/options.py"),
    ):
        module = types.ModuleType(name)
        module.__file__ = str(root / path)
        module.__package__ = name.rpartition(".")[0]
        sys.modules[name] = module
        exec(compile(sources[path], str(root / path), "exec"), module.__dict__)
        modules[name] = module
    return modules["src.pipelines.extensions.preprocessing"], modules["_pinned_original_seed_options"]


def _capture_original(
    module: types.ModuleType, training: pd.DataFrame, processor: Any,
    time: np.ndarray, event: np.ndarray, seed: int,
) -> DrawProposal:
    """Intercept the local alias serially, always delegating to the frozen guard."""
    _require(threading.current_thread() is threading.main_thread(), "constructor interception requires a serial main thread")
    original = module.CatalyticData
    _require(_INTERCEPTION_LOCK.acquire(blocking=False), "constructor interception already active")
    captured: dict[str, Any] = {}

    def constructor(design: np.ndarray, prior_time: np.ndarray, hazard: float) -> Any:
        captured.update(data=SyntheticInputs(design.copy(), prior_time.copy(), float(hazard)))
        try:
            return original(design, prior_time, hazard)
        except ValueError as error:
            trace = error.__traceback__
            while trace is not None and trace.tb_next is not None:
                trace = trace.tb_next
            guard = getattr(original, "__post_init__", None)
            if (type(error) is ValueError and error.args == (RANK_MESSAGE,)
                    and guard is not None and trace is not None
                    and trace.tb_frame.f_code is guard.__code__ and trace.tb_lineno == 32):
                captured["rank_error"] = error
            raise

    legacy = None
    error: BaseException | None = None
    try:
        module.CatalyticData = constructor
        try:
            _data, legacy = module.generate_catalytic_data(training, processor, time, event, seed)
        except BaseException as caught:
            error = caught
    finally:
        module.CatalyticData = original
        _INTERCEPTION_LOCK.release()
    if error is not None and error is not captured.get("rank_error"):
        raise error
    _require("data" in captured, "original generator did not reach its constructor")
    sources = list(dict.fromkeys(processor.clinical.required_source_columns + processor.genes))
    scale = float(np.median(time[event == 1]))
    actual = {"seed": seed, "M": len(captured["data"].time), "p": len(processor.feature_names),
              "time_scale": scale, "hazard_scaled": captured["data"].hazard,
              "source_variables": sources, "feature_names": list(processor.feature_names),
              "processor_metadata": processor.metadata(), "constructor_restored": module.CatalyticData is original,
              "legacy_metadata_origin": "original returned value" if legacy is not None else "not returned by original generator",
              "capture_scope": "constructor inputs and training-derived proposal metadata only"}
    proposal = DrawProposal(captured["data"], copy.deepcopy(legacy), actual)
    if error is not None:
        raise FrozenRankRejection(proposal) from error
    return proposal


def _restore_original_processor(
    module: types.ModuleType, feature_spec: dict[str, Any], state: dict[str, Any],
) -> Any:
    """Restore complete learned state using the original clinical hash guard.

    The caller must independently bind this state to its training rows. This
    routine checks state integrity and reconstruction, not training provenance.
    """
    keys = {"clinical", "keep_clinical", "gene_budget", "gene_state",
            "feature_names", "state_sha256"}
    _require(type(state) is dict and set(state) == keys, "incomplete original processor state")
    _require(_canonical({k: v for k, v in state.items() if k != "state_sha256"})
             == state["state_sha256"], "original processor state hash differs")
    budget = state["gene_budget"]
    _require(type(budget) is int and budget >= 0, "invalid original gene budget")
    processor = module.ExtensionPreprocessor(feature_spec, budget)
    processor.clinical = module.FoldFeaturePreprocessor.from_metadata(feature_spec, state["clinical"])
    processor.keep_clinical = list(state["keep_clinical"])
    processor.feature_names = list(state["feature_names"])
    _require(processor.feature_names[:len(processor.keep_clinical)] == processor.keep_clinical,
             "original feature prefix differs")
    processor.genes = processor.feature_names[len(processor.keep_clinical):]
    _require(len(processor.genes) == budget and set(processor.genes) == set(state["gene_state"])
             and all(c.startswith("gene:") for c in processor.genes), "original gene state differs")
    _require(all(c in processor.clinical.feature_names for c in processor.keep_clinical),
             "unknown original clinical output")
    processor.gene_state = copy.deepcopy(state["gene_state"])
    _require(processor.metadata() == state, "restored original processor state differs")
    return processor


class IsolatedOriginalAdapter:
    """Call original preprocessing in a new process using trusted training objects.

    No evaluation argument exists. The processor is reconstructed by the exact
    original ``fit(training)`` from the supplied spec/budget by default. An
    optional complete hash-verified training state restores the original
    transformer, allowing only its selected source columns to be transferred.
    Training provenance remains the caller's responsibility. Pickle transport
    accepts trusted in-memory caller objects, never external files.
    """

    def __init__(
        self, source_checkout: Path, training: pd.DataFrame, feature_spec: dict[str, Any],
        time: np.ndarray, event: np.ndarray, *, gene_budget: int = 0, python: Path | None = None,
        processor_metadata: dict[str, Any] | None = None,
    ) -> None:
        """Bind an explicitly selected byte-matched checkout and training inputs."""
        _source_bytes(source_checkout)
        self.source_checkout = source_checkout
        self.request = {"training": training.copy(deep=True), "feature_spec": copy.deepcopy(feature_spec),
                        "time": time.copy(), "event": event.copy(), "gene_budget": gene_budget,
                        "processor_metadata": copy.deepcopy(processor_metadata)}
        self.python = Path(sys.executable) if python is None else python
        _require(self.python.is_absolute() and self.python.is_file(), "Python must be an explicit existing absolute path")

    def __call__(self, seed: int) -> DrawProposal:
        """Return one proposal or propagate the original nonrank exception.

        A tagged rank exception retains rejected constructor values. No files
        are written, optimizers called, or parent-process modules modified.
        """
        _source_bytes(self.source_checkout)
        payload = pickle.dumps({**self.request, "seed": seed}, protocol=5)
        worker = Path(__file__).absolute()
        worker_hash = _sha(worker.read_bytes())
        command = [str(self.python), "-I", "-B", str(worker), "--worker", str(self.source_checkout)]
        environment = {**os.environ, "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
                       "MKL_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"}
        result = subprocess.run(command, input=payload, capture_output=True, env=environment, check=False)
        _require(result.returncode == 0, f"isolated original proposal worker failed: {result.stderr.decode(errors='replace')}")
        _require(_sha(worker.read_bytes()) == worker_hash, "candidate worker source changed")
        _source_bytes(self.source_checkout)
        reply = pickle.loads(result.stdout)
        if reply["status"] == "nonrank_error":
            raise reply["error"]
        _require(reply["status"] in ("accepted", "rank_rejected"), "invalid worker reply")
        data = SyntheticInputs(reply["design"], reply["time"], reply["hazard"])
        proposal = DrawProposal(data, reply["legacy_metadata"], reply["actual_metadata"])
        if reply["status"] == "rank_rejected":
            raise FrozenRankRejection(proposal)
        return proposal


def _worker(root: Path) -> None:
    """Private child protocol: trusted parent bytes only, no filesystem payload."""
    try:
        module, options = _load_original(root)
        request = pickle.loads(sys.stdin.buffer.read())
        state = request["processor_metadata"]
        if state is None:
            processor = module.ExtensionPreprocessor(request["feature_spec"], request["gene_budget"])
            processor.fit(request["training"])
            processor_origin = "original fit(training) in proposal child"
        else:
            processor = _restore_original_processor(module, request["feature_spec"], state)
            _require(processor.gene_budget == request["gene_budget"], "requested original gene budget differs")
            processor_origin = "restored original training state; caller provenance required"
        try:
            proposal = _capture_original(module, request["training"], processor,
                                         request["time"], request["event"], request["seed"])
            status = "accepted"
        except FrozenRankRejection as error:
            proposal, status = error.proposal, "rank_rejected"
        proposal.actual_metadata.update(source_sha256=dict(SOURCE_PINS),
                                        original_retry_seed_1=options.deterministic_seed(request["seed"], RETRY_LABEL, 1),
                                        processor_origin=processor_origin)
        reply = {"status": status, "design": proposal.data.design, "time": proposal.data.time,
                 "hazard": proposal.data.hazard, "legacy_metadata": proposal.legacy_metadata,
                 "actual_metadata": proposal.actual_metadata}
    except BaseException as error:
        reply = {"status": "nonrank_error", "error": error}
    sys.stdout.buffer.write(pickle.dumps(reply, protocol=5))


if __name__ == "__main__":
    if len(sys.argv) != 3 or sys.argv[1] != "--worker":
        raise SystemExit("Private candidate adapter worker only; use its typed API with trusted training inputs.")
    _worker(Path(sys.argv[2]))
