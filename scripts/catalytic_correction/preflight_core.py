"""Write-once training-input feasibility accounting; no model or score reuse."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import tempfile
import time
import traceback
import uuid
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


class InvalidCheckpoint(ValueError):
    """A saved input, receipt, artifact or claim cannot be safely reused."""


class RecordedNonRankError(Exception):
    """A verified prior proposal stopped before an original constructor result."""

    def __init__(self, record: dict[str, Any]) -> None:
        self.record = record
        super().__init__(record["message"])


def canonical_hash(value: Any) -> str:
    """Hash strict canonical JSON using the original source's encoding."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def sha256_file(path: Path) -> str:
    """Stream file bytes, without opening an array or evaluating a model."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def seal(value: dict[str, Any]) -> dict[str, Any]:
    """Add a content digest without changing a previously sealed mapping."""
    if "content_sha256" in value:
        raise ValueError("mapping already sealed")
    return {**value, "content_sha256": canonical_hash(value)}


def read_sealed(path: Path) -> dict[str, Any]:
    """Reject altered receipts rather than skipping them during resume."""
    if path.is_symlink():
        raise InvalidCheckpoint(f"symlink checkpoint: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = value.get("content_sha256")
    if expected != canonical_hash({key: item for key, item in value.items() if key != "content_sha256"}):
        raise InvalidCheckpoint(f"checkpoint content changed: {path}")
    return value


def publish_new(path: Path, writer: Callable[[Any], None]) -> None:
    """Publish with atomic no-replace semantics; leave no guessed checkpoint."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        raise FileExistsError(path)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".preflight-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            writer(stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        directory_descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_descriptor)
        finally:
            os.close(directory_descriptor)
    finally:
        temporary.unlink(missing_ok=True)


def write_json_new(path: Path, value: dict[str, Any]) -> None:
    """Write one complete mapping without replacing an existing path."""
    payload = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    publish_new(path, lambda stream: stream.write(payload))


def array_witness(array: np.ndarray) -> dict[str, Any]:
    """Bind dtype, shape and exact C-order element bytes."""
    array = np.asarray(array)
    if array.dtype.hasobject:
        raise ValueError("array witnesses require non-object dtype")
    return {"dtype": array.dtype.str, "shape": list(array.shape),
            "values_sha256": hashlib.sha256(np.ascontiguousarray(array).tobytes(order="C")).hexdigest()}


def scalar_tag(value: Any) -> list[Any]:
    """Encode actual source categories, including missing float values."""
    if value is pd.NA:
        return ["pandas.NA"]
    if value is None:
        return ["None"]
    if isinstance(value, (np.bool_, bool)):
        return ["bool", bool(value)]
    if isinstance(value, (np.integer, int)):
        return ["int", str(int(value))]
    if isinstance(value, (np.floating, float)):
        return ["float64", np.asarray(float(value), dtype="<f8").tobytes().hex()]
    if isinstance(value, str):
        return ["str", value]
    if isinstance(value, bytes):
        return ["bytes", value.hex()]
    raise TypeError(f"unsupported source scalar type: {type(value).__name__}")


def source_frame_witness(frame: pd.DataFrame, columns: list[str]) -> dict[str, Any]:
    """Bind only the exact source columns used by this trained generator."""
    records = []
    for column in columns:
        series = frame[column]
        values = series.to_numpy()
        record = {"column": column, "pandas_dtype": str(series.dtype)}
        if values.dtype.hasobject:
            record["values_sha256"] = canonical_hash([scalar_tag(value) for value in values])
            record["numpy_dtype"] = values.dtype.str
        else:
            record["array"] = array_witness(values)
        records.append(record)
    return {"ordered_source_columns": columns, "rows": len(frame), "columns": records,
            "source_values_sha256": canonical_hash(records)}


def verify_artifacts(root: Path, receipt: dict[str, Any]) -> None:
    """Verify every bound artifact and reject path traversal or symlinks."""
    for name, binding in receipt.get("artifacts", {}).items():
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise InvalidCheckpoint("unsafe artifact path")
        path = root / relative
        if not path.is_file() or any(item.is_symlink() for item in (path, *path.parents)):
            raise InvalidCheckpoint(f"missing or linked artifact: {name}")
        if path.stat().st_size != binding["bytes"] or sha256_file(path) != binding["sha256"]:
            raise InvalidCheckpoint(f"artifact bytes changed: {name}")


def artifact_binding(path: Path) -> dict[str, Any]:
    """Record a complete artifact's bytes and digest."""
    return {"sha256": sha256_file(path), "bytes": path.stat().st_size}


def save_arrays(path: Path, arrays: dict[str, np.ndarray]) -> None:
    """Save numeric arrays compressed with atomic no-replace publication."""
    if any(np.asarray(array).dtype.hasobject for array in arrays.values()):
        raise ValueError("object arrays are not permitted")
    publish_new(path, lambda stream: np.savez_compressed(stream, **arrays))


def read_arrays(path: Path) -> dict[str, np.ndarray]:
    """Read only hash-verified numeric archives, never external pickle data."""
    with np.load(path, allow_pickle=False) as saved:
        return {name: saved[name].copy() for name in saved.files}


class Claim:
    """One serial owner; dead local claims require explicit recovery."""

    def __init__(self, path: Path, binding: str, *, recover_stale: bool = False) -> None:
        self.path, self.binding, self.recover_stale = path, binding, recover_stale
        self.nonce = uuid.uuid4().hex

    def __enter__(self) -> Claim:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            existing = read_sealed(self.path)
            if not self.recover_stale or existing["run_binding_sha256"] != self.binding:
                raise InvalidCheckpoint(f"claim already exists: {self.path}")
            if existing["host"] != socket.gethostname():
                raise InvalidCheckpoint("cannot recover another host's claim")
            try:
                os.kill(existing["pid"], 0)
            except ProcessLookupError:
                archive = self.path.parent / "abandoned_claims" / f"{existing['nonce']}.json"
                archive.parent.mkdir(exist_ok=True)
                os.link(self.path, archive)
                self.path.unlink()
            else:
                raise InvalidCheckpoint("claim process still exists")
        write_json_new(self.path, seal({"schema_version": 1, "run_binding_sha256": self.binding,
                                       "pid": os.getpid(), "host": socket.gethostname(),
                                       "nonce": self.nonce, "created_at_utc": datetime.now(UTC).isoformat()}))
        return self

    def __exit__(self, *_arguments: Any) -> None:
        if read_sealed(self.path)["nonce"] != self.nonce:
            raise InvalidCheckpoint("claim owner changed")
        self.path.unlink()


@dataclass
class ContextInputs:
    """Current training only; evaluation patients are never passed to an adapter."""

    training: pd.DataFrame
    time: np.ndarray
    event: np.ndarray
    processor: Any
    feature_spec: dict[str, Any]
    witness: dict[str, Any]
    design: np.ndarray


def build_context(row: dict[str, Any], job: Any, raw: pd.DataFrame, backend: Any) -> ContextInputs:
    """Reconstruct outer censorship before WME splitting and local preprocessing."""
    times, events = raw.duration.to_numpy(float), raw.event.to_numpy(int)
    training = raw.iloc[job.train]
    outer_ids = training.subject_id.tolist()
    validation_ids = raw.subject_id.iloc[job.validation].tolist()
    if canonical_hash(outer_ids) != row["outer_train_sha256_from_manifest"] or canonical_hash(validation_ids) != row["outer_validation_sha256_from_manifest"]:
        raise InvalidCheckpoint("outer ordered membership differs from manifest")
    if set(outer_ids) & set(validation_ids):
        raise InvalidCheckpoint("outer training contains validation patients")
    if job.censoring_cutoff != row["censoring_cutoff_from_manifest"] or job.gene_budget != row["gene_budget"]:
        raise InvalidCheckpoint("outer recipe cutoff or gene budget differs")
    tt, ee = backend.apply_censor(times[job.train], events[job.train], job.censoring_cutoff)
    if int(ee.sum()) < 20:
        raise ValueError("fewer than 20 training events under frozen information-regime rule")
    inner_validation_ids: list[str] = []
    if row["context"] == "inner":
        if row["model"] != "catalytic_wme" or row["inner_split_seed"] != row["inner_cv_seed"]:
            raise InvalidCheckpoint("invalid WME inner recipe")
        folds = backend.inner_folds(tt, ee, row["inner_cv_seed"])
        if len(folds) != 3 or {fold.fold for fold in folds} != {1, 2, 3}:
            raise InvalidCheckpoint("inner coverage differs from the original three-fold rule")
        fold = next(fold for fold in folds if fold.fold == row["inner_fold"])
        if fold.seed != row["inner_split_seed"]:
            raise InvalidCheckpoint("inner splitter seed differs")
        inner_validation_ids = training.subject_id.iloc[fold.validation_indices].tolist()
        training = training.iloc[fold.train_indices]
        tt, ee = tt[fold.train_indices], ee[fold.train_indices]
    elif row["context"] != "outer":
        raise InvalidCheckpoint("unknown context kind")
    training = training.copy(deep=True)
    ids = training.subject_id.tolist()
    if set(ids) & (set(validation_ids) | set(inner_validation_ids)):
        raise InvalidCheckpoint("current training contains held-out patients")
    specification = backend.feature_spec(job.dataset)
    processor = backend.preprocess(specification, job.gene_budget, training)
    design = processor.transform(training).to_numpy(float)
    metadata = processor.metadata()
    if design.shape != (len(training), len(processor.feature_names)) or not np.isfinite(design).all():
        raise ValueError("invalid transformed training design")
    sources = list(dict.fromkeys(processor.clinical.required_source_columns + processor.genes))
    witness = {
        "schema_version": 1, "context_id": row["context_id"],
        "ordered_training_subject_ids": ids, "training_membership_sha256": canonical_hash(ids),
        "outer_training_membership_sha256": canonical_hash(outer_ids),
        "outer_validation_membership_sha256": canonical_hash(validation_ids),
        "inner_validation_membership_sha256": None if not inner_validation_ids else canonical_hash(inner_validation_ids),
        "membership_scope": "original_outer_manifest_match_and_pinned_splitter_reconstruction",
        "inner_membership_has_independent_original_saved_witness": False,
        "censoring_cutoff": job.censoring_cutoff, "events_train": int(ee.sum()),
        "n_train": len(training), "gene_budget": job.gene_budget, "feature_spec": specification,
        "feature_names": list(processor.feature_names), "processor_metadata": metadata,
        "processor_metadata_sha256": canonical_hash(metadata),
        "source_values": source_frame_witness(training, sources),
        "real_design": array_witness(design), "training_time": array_witness(tt), "training_event": array_witness(ee),
        "original_generation_seed": row["generation_seed"], "original_cell_seed": row["cell_seed"],
        "original_outer_fit_attempt_seeds": row["original_outer_fit_attempt_seeds"],
        "original_outer_evaluation_seed": row["outer_evaluation_seed"],
        "shared_tau_candidate_uses": row["shared_tau_candidate_uses"],
        "fit_reuse_certified": False,
    }
    return ContextInputs(training, tt.copy(), ee.copy(), processor, specification, witness, design)


def rank_diagnostics(proposal: Any, inputs: ContextInputs) -> dict[str, Any]:
    """Measure singular values without controlling the original constructor gate."""
    x = proposal.data.design
    singular = np.linalg.svd(x, compute_uv=False)
    tolerance = float(singular.max() * max(x.shape) * np.finfo(singular.dtype).eps)
    zero_indices = np.flatnonzero(np.all(x == 0, axis=0)).tolist()
    names = inputs.processor.feature_names
    support = []
    metadata = inputs.processor.metadata()["clinical"]
    for column, levels in metadata.get("category_levels", {}).items():
        real = inputs.training[column].astype(object).where(inputs.training[column].notna(), "__MISSING__").astype(str)
        synthetic_counts = {}
        for level in levels[1:]:
            name = f"{column}={level}"
            synthetic_counts[level] = int(np.count_nonzero(x[:, names.index(name)])) if name in names else None
        synthetic_counts[levels[0]] = len(x) - sum(synthetic_counts.values()) if all(value is not None for value in synthetic_counts.values()) else None
        for level in levels:
            count = synthetic_counts[level]
            support.append({"source_column": column, "level": level,
                            "training_count": int((real == level).sum()), "synthetic_count": count,
                            "omitted_in_proposal": None if count is None else count == 0})
    return {"status": "measured", "rank": int(np.sum(singular > tolerance)),
            "singular_values": singular.tolist(), "default_matrix_rank_tolerance": tolerance,
            "rank_rule": "numpy default SVD tolerance; measurement only; original guard determines acceptance",
            "zero_encoded_column_indices": zero_indices, "zero_encoded_columns": [names[index] for index in zero_indices],
            "category_support": support}


def error_record(error: Exception) -> dict[str, Any]:
    """Preserve original exception identity and traceback without retrying it."""
    if isinstance(error, RecordedNonRankError):
        return error.record
    return {"type": f"{type(error).__module__}.{type(error).__qualname__}",
            "message": str(error), "traceback": traceback.format_exc()}


def compare_original(original: dict[str, Any] | None, row: dict[str, Any], inputs: ContextInputs | None,
                     attempts: list[dict[str, Any]], accepted_index: int | None) -> dict[str, Any]:
    """Assess saved generator witnesses, explicitly stopping short of fit reuse."""
    base = {"scope": "stored_preprocessing_and_generator_metadata_only", "fit_reuse_certified": False,
            "model_fit_evaluation_identity_certified": False, "independent_normal_import_replay": False}
    if original is None:
        return {**base, "status": "original_cell_not_yet_recorded", "original_status": None}
    original_status = original["status"]
    base.update(original_status=original_status, original_message=original.get("message"),
                original_rank_failure=original.get("message") == "synthetic design is not full column rank")
    if row["context"] == "inner":
        return {**base, "status": "original_inner_inputs_not_saved_unresolved",
                "original_outer_preprocessing_available": "preprocessing" in original,
                "original_inner_preprocessing_match": None, "original_inner_synthetic_metadata_match": None}
    if inputs is None or not attempts:
        return {**base, "status": "no_constructed_first_proposal_unresolved"}
    first = attempts[0]
    preprocessing = original.get("preprocessing")
    processor_match = None if preprocessing is None else canonical_hash(preprocessing) == inputs.witness["processor_metadata_sha256"]
    legacy = original.get("synthetic_prior_data")
    first_legacy = first.get("legacy_metadata")
    legacy_match = None if legacy is None or first_legacy is None else canonical_hash(legacy) == canonical_hash(first_legacy)
    if processor_match is False or legacy_match is False:
        status = "stored_input_witness_mismatch"
    elif accepted_index == 0 and processor_match is True and legacy_match is True:
        status = "stored_preprocessing_and_legacy_metadata_exact_match"
    elif first["status"] == "frozen_rank_rejected":
        status = "original_first_proposal_rank_rejected_retained"
    else:
        status = "saved_generator_witness_incomplete_unresolved"
    return {**base, "status": status, "original_outer_preprocessing_match": processor_match,
            "original_outer_synthetic_metadata_match": legacy_match,
            "original_saved_design_byte_array_witness_available": False,
            "accepted_attempt_index": accepted_index, "first_proposal_status": first["status"]}


class PreflightEngine:
    """Serial context/attempt checkpoints bound to an immutable run request."""

    def __init__(self, output: Path, binding: str, candidate: Any, backend: Any,
                 adapter_factory: Callable[[ContextInputs], Any], *, cap: int,
                 diagnostics: Callable[[Any, ContextInputs], dict[str, Any]] = rank_diagnostics,
                 recover_stale: bool = False) -> None:
        if type(cap) is not int or not 1 <= cap <= candidate.CANDIDATE_CAP:
            raise ValueError("explicit candidate cap must be in 1..256")
        self.output, self.binding, self.candidate, self.backend = output, binding, candidate, backend
        self.adapter_factory, self.cap, self.diagnostics = adapter_factory, cap, diagnostics
        self.recover_stale = recover_stale

    def context_directory(self, row: dict[str, Any]) -> Path:
        """Use validated labels only, never a caller-provided filesystem path."""
        cell_id = row["outer_cell_id"]
        if not cell_id or any(character not in "abcdefghijklmnopqrstuvwxyz0123456789_." for character in cell_id):
            raise InvalidCheckpoint("unsafe cell label")
        name = "outer" if row["context"] == "outer" else f"inner_{row['inner_fold']:02d}"
        return self.output / "contexts" / cell_id / name

    def _save_inputs(self, directory: Path, inputs: ContextInputs, request: dict[str, Any]) -> None:
        record = seal({"request": request, "input_witness": inputs.witness})
        path = directory / "input.json"
        if path.exists():
            if read_sealed(path) != record:
                raise InvalidCheckpoint("reconstructed input witness differs")
            if (directory / "inputs.npz").is_symlink():
                raise InvalidCheckpoint("linked real training array archive")
            saved = read_arrays(directory / "inputs.npz")
            for name, actual in (("real_design", inputs.design), ("real_time", inputs.time), ("real_event", inputs.event)):
                if name not in saved or array_witness(saved[name]) != array_witness(actual):
                    raise InvalidCheckpoint("saved real training arrays differ")
            if set(saved) != {"real_design", "real_time", "real_event"}:
                raise InvalidCheckpoint("unexpected real training array keys")
            return
        if (directory / "inputs.npz").exists():
            raise InvalidCheckpoint("partial real-input checkpoint lacks a receipt")
        save_arrays(directory / "inputs.npz", {"real_design": inputs.design, "real_time": inputs.time, "real_event": inputs.event})
        write_json_new(path, record)

    def _attempt(self, directory: Path, request: dict[str, Any], inputs: ContextInputs,
                 adapter: Any, index: int, seed: int) -> tuple[Any, dict[str, Any]]:
        attempt_dir = directory / f"attempt_{index:03d}"
        path = attempt_dir / "receipt.json"
        if path.exists():
            record = read_sealed(path)
            if record["request"] != request or record["attempt_index"] != index or record["seed"] != seed:
                raise InvalidCheckpoint("proposal checkpoint request differs")
            verify_artifacts(attempt_dir, record)
            if record["status"] == "nonrank_error":
                raise RecordedNonRankError(record["error"])
            if record["status"] not in {"accepted_original_constructor", "frozen_rank_rejected"}:
                raise InvalidCheckpoint("unexpected saved constructor status")
            arrays = read_arrays(attempt_dir / "proposal.npz")
            if set(arrays) != {"synthetic_design", "synthetic_time", "hazard", "time_scale"}:
                raise InvalidCheckpoint("unexpected proposal array keys")
            if {name: array_witness(array) for name, array in arrays.items()} != record["array_witnesses"]:
                raise InvalidCheckpoint("proposal array witnesses differ")
            proposal = self.candidate.DrawProposal(self.candidate.SyntheticInputs(arrays["synthetic_design"], arrays["synthetic_time"], float(arrays["hazard"])), record["legacy_metadata"], record["actual_metadata"])
            if proposal.data.hashes() != record["constructor_inputs"]:
                raise InvalidCheckpoint("proposal element witnesses differ")
            return proposal, record
        if attempt_dir.exists() and any(attempt_dir.iterdir()):
            raise InvalidCheckpoint("partial proposal checkpoint lacks a receipt")
        try:
            proposal = adapter(seed)
            status = "accepted_original_constructor"
        except self.candidate.FrozenRankRejection as error:
            if type(error) is not self.candidate.FrozenRankRejection:
                raise
            proposal, status = error.proposal, "frozen_rank_rejected"
        except Exception as error:
            record = seal({"schema_version": 1, "request": request, "attempt_index": index,
                           "seed": seed, "status": "nonrank_error", "error": error_record(error),
                           "constructor_inputs": None, "artifacts": {}})
            write_json_new(path, record)
            raise
        if canonical_hash(proposal.actual_metadata["processor_metadata"]) != inputs.witness["processor_metadata_sha256"]:
            raise InvalidCheckpoint("proposal child preprocessing differs from controller")
        if proposal.actual_metadata["seed"] != seed or proposal.data.design.shape[1] != len(inputs.processor.feature_names):
            raise InvalidCheckpoint("proposal seed or column count differs")
        try:
            diagnostic = self.diagnostics(proposal, inputs)
        except Exception as error:
            diagnostic = {"status": "measurement_unavailable", "error": error_record(error),
                          "original_constructor_result_unchanged": True}
        arrays = {"synthetic_design": proposal.data.design, "synthetic_time": proposal.data.time,
                  "hazard": np.asarray(proposal.data.hazard, dtype=float),
                  "time_scale": np.asarray(proposal.actual_metadata["time_scale"], dtype=float)}
        save_arrays(attempt_dir / "proposal.npz", arrays)
        record = seal({"schema_version": 1, "request": request, "attempt_index": index, "seed": seed,
                       "status": status, "constructor_inputs": proposal.data.hashes(),
                       "legacy_metadata": proposal.legacy_metadata, "actual_metadata": proposal.actual_metadata,
                       "array_witnesses": {name: array_witness(array) for name, array in arrays.items()},
                       "rank_measurement": diagnostic, "artifacts": {"proposal.npz": artifact_binding(attempt_dir / "proposal.npz")}})
        write_json_new(path, record)
        return proposal, record

    def compare_source(self, directory: Path, row: dict[str, Any], inputs: ContextInputs | None,
                       attempts: list[dict[str, Any]], accepted_index: int | None) -> Path:
        """Write a separate immutable comparison for the currently available original."""
        source = self.backend.original_cell(row["outer_cell_id"])
        source_identity = "not_recorded" if source is None else source[1]
        original = None if source is None else source[0]
        record = seal({"schema_version": 1, "run_binding_sha256": self.binding,
                       "context_row_sha256": canonical_hash(row), "source_cell_byte_sha256": None if source is None else source[1],
                       "source_cell_content_sha256": None if original is None else original["cell_content_sha256"],
                       "assessment": compare_original(original, row, inputs, attempts, accepted_index)})
        path = directory / "comparisons" / f"{source_identity}.json"
        if path.exists():
            if read_sealed(path) != record:
                raise InvalidCheckpoint("existing original comparison differs")
        else:
            write_json_new(path, record)
        return path

    def run_context(self, row: dict[str, Any], job: Any, raw: pd.DataFrame) -> dict[str, Any]:
        """Account for one scheduled context, including cached or failed inputs."""
        directory = self.context_directory(row)
        if any(path.is_symlink() for path in (directory, *directory.parents)):
            raise InvalidCheckpoint("linked context output directory")
        request_base = {"run_binding_sha256": self.binding, "context_row_sha256": canonical_hash(row),
                        "context_id": row["context_id"], "original_generation_seed": row["generation_seed"],
                        "candidate_cap": self.cap}
        claim_path = self.output / "claims" / f"{canonical_hash(row['context_id'])}.json"
        with Claim(claim_path, self.binding, recover_stale=self.recover_stale):
            started = time.perf_counter()
            inputs = None
            try:
                inputs = build_context(row, job, raw, self.backend)
            except InvalidCheckpoint:
                raise
            except Exception as error:
                failure = error_record(error)
                path = directory / "receipt.json"
                if path.exists():
                    record = read_sealed(path)
                    if record["request"] != request_base or record["status"] != "input_failure" or record["input_error"]["type"] != failure["type"] or record["input_error"]["message"] != failure["message"]:
                        raise InvalidCheckpoint("saved input failure differs") from error
                    verify_artifacts(directory, record)
                    self.compare_source(directory, row, None, [], None)
                    return record
                record = seal({"schema_version": 1, "request": request_base, "status": "input_failure",
                               "input_error": failure, "attempts": [], "accepted_attempt_index": None,
                               "seconds": time.perf_counter() - started, "artifacts": {},
                               "scope": "training_input_feasibility_only", "fit_reuse_certified": False,
                               "scientific_method_approved": False, "new_freeze_created": False})
                write_json_new(path, record)
                self.compare_source(directory, row, None, [], None)
                return record
            request = {**request_base, "input_witness_sha256": canonical_hash(inputs.witness)}
            receipt_path = directory / "receipt.json"
            if receipt_path.exists() and read_sealed(receipt_path)["status"] == "input_failure":
                raise InvalidCheckpoint("a saved input failure now constructs; separate outputs are required")
            self._save_inputs(directory, inputs, request)
            if receipt_path.exists():
                record = read_sealed(receipt_path)
                if record["request"] != request:
                    raise InvalidCheckpoint("context input or run request differs")
                verify_artifacts(directory, record)
                self._validate_attempt_sequence(record, directory)
                self.compare_source(directory, row, inputs, record["attempts"], record["accepted_attempt_index"])
                return record
            adapter_holder = []

            def adapter(seed: int) -> Any:
                if not adapter_holder:
                    adapter_holder.append(self.adapter_factory(inputs))
                return adapter_holder[0](seed)
            attempts = []

            def draw(seed: int) -> Any:
                index = len(attempts)
                try:
                    proposal, attempt = self._attempt(directory, request, inputs, adapter, index, seed)
                except RecordedNonRankError:
                    attempts.append(read_sealed(directory / f"attempt_{index:03d}" / "receipt.json"))
                    raise
                except InvalidCheckpoint:
                    raise
                except Exception:
                    path = directory / f"attempt_{index:03d}" / "receipt.json"
                    if not path.exists():
                        raise
                    attempts.append(read_sealed(path))
                    raise
                attempts.append(attempt)
                if attempt["status"] == "frozen_rank_rejected":
                    raise self.candidate.FrozenRankRejection(proposal)
                return proposal

            candidate_metadata = None
            accepted_index = None
            failure = None
            try:
                result = self.candidate.generate_rank_conditioned(draw, row["generation_seed"], cap=self.cap)
                candidate_metadata = result.proposal_metadata
                accepted_index = candidate_metadata["accepted_attempt_index"]
                status = "accepted_original_first_draw" if accepted_index == 0 else "accepted_rank_conditioned_redraw"
            except self.candidate.RankConditionedExhausted as error:
                candidate_metadata, status = error.proposal_metadata, "exhausted_rank_cap"
            except InvalidCheckpoint:
                raise
            except Exception as error:
                failure, status = error_record(error), "nonrank_failure"
            artifacts = {"input.json": artifact_binding(directory / "input.json"),
                         "inputs.npz": artifact_binding(directory / "inputs.npz")}
            for attempt in attempts:
                prefix = f"attempt_{attempt['attempt_index']:03d}"
                artifacts[f"{prefix}/receipt.json"] = artifact_binding(directory / prefix / "receipt.json")
                for name, binding in attempt["artifacts"].items():
                    artifacts[f"{prefix}/{name}"] = binding
            record = seal({"schema_version": 1, "request": request, "status": status,
                           "attempts": attempts, "accepted_attempt_index": accepted_index,
                           "candidate_metadata": candidate_metadata, "nonrank_error": failure,
                           "seconds": time.perf_counter() - started, "artifacts": artifacts,
                           "scope": "training_input_feasibility_only", "fit_reuse_certified": False,
                           "scientific_method_approved": False, "new_freeze_created": False,
                           "first_draw_scope": "untouched_original_call_captured_by_reviewed_adapter; no_independent_normal_import_replay"})
            self._validate_attempt_sequence(record, directory)
            write_json_new(receipt_path, record)
            self.compare_source(directory, row, inputs, attempts, accepted_index)
            return record

    def _validate_attempt_sequence(self, record: dict[str, Any], directory: Path) -> None:
        attempts = record["attempts"]
        if not 1 <= len(attempts) <= self.cap:
            raise InvalidCheckpoint("invalid generated attempt count")
        existing = {path.name for path in directory.glob("attempt_*")}
        if existing != {f"attempt_{index:03d}" for index in range(len(attempts))}:
            raise InvalidCheckpoint("unexpected extra or missing proposal checkpoint")
        original_seed = record["request"]["original_generation_seed"]
        for index, attempt in enumerate(attempts):
            seed = original_seed if index == 0 else self.candidate.deterministic_seed(original_seed, self.candidate.RETRY_LABEL, index)
            if attempt["request"] != record["request"] or attempt["attempt_index"] != index or attempt["seed"] != seed:
                raise InvalidCheckpoint("attempt ordering, request or seed differs")
            path = directory / f"attempt_{index:03d}" / "receipt.json"
            if read_sealed(path) != attempt:
                raise InvalidCheckpoint("context/attempt receipt mismatch")
            verify_artifacts(path.parent, attempt)
            if index < len(attempts) - 1 and attempt["status"] != "frozen_rank_rejected":
                raise InvalidCheckpoint("redraw followed a non-rank outcome")
        accepted = record["accepted_attempt_index"]
        if record["status"] in {"accepted_original_first_draw", "accepted_rank_conditioned_redraw"}:
            if accepted != len(attempts) - 1 or attempts[-1]["status"] != "accepted_original_constructor" or (record["status"] == "accepted_original_first_draw") != (accepted == 0):
                raise InvalidCheckpoint("accepted attempt accounting differs")
        elif record["status"] == "exhausted_rank_cap":
            if accepted is not None or len(attempts) != self.cap or any(attempt["status"] != "frozen_rank_rejected" for attempt in attempts):
                raise InvalidCheckpoint("rank exhaustion accounting differs")
        elif record["status"] == "nonrank_failure":
            if accepted is not None or attempts[-1]["status"] != "nonrank_error":
                raise InvalidCheckpoint("non-rank failure accounting differs")
        else:
            raise InvalidCheckpoint("unexpected context outcome")
        metadata = record["candidate_metadata"]
        if metadata is not None:
            if metadata["proposal_metadata_sha256"] != canonical_hash({key: value for key, value in metadata.items() if key != "proposal_metadata_sha256"}):
                raise InvalidCheckpoint("candidate attempt history digest differs")
            if metadata["attempts_generated"] != len(attempts) or metadata["original_seed"] != original_seed or metadata["attempt_cap"] != self.cap or metadata["accepted_attempt_index"] != accepted:
                raise InvalidCheckpoint("candidate/context accounting differs")

    def execute(self, rows: list[dict[str, Any]], jobs: dict[str, Any], cohorts: dict[str, pd.DataFrame],
                *, limit: int | None = None) -> dict[str, Any]:
        """Verify/resume a serial pass and seal whole coverage only when complete."""
        if limit is not None and limit < 1:
            raise ValueError("limit must be positive")
        outcomes = []
        with Claim(self.output / "controller.claim.json", self.binding, recover_stale=self.recover_stale):
            for row in rows if limit is None else rows[:limit]:
                record = self.run_context(row, jobs[row["outer_cell_id"]], cohorts[row["dataset"]])
                path = self.context_directory(row) / "receipt.json"
                outcomes.append({"context_id": row["context_id"], "status": record["status"],
                                 "receipt_path": str(path.relative_to(self.output)), "receipt_sha256": sha256_file(path),
                                 "receipt_content_sha256": record["content_sha256"]})
                print(json.dumps({"context_id": row["context_id"], "status": record["status"], "accounted_this_pass": len(outcomes)}, sort_keys=True), flush=True)
            self.backend.verify_boundary()
            value = seal({"schema_version": 1, "run_binding_sha256": self.binding,
                          "status": "all_scheduled_contexts_accounted" if len(outcomes) == len(rows) else "partial_context_pass",
                          "scheduled_contexts": len(rows), "accounted_contexts": len(outcomes),
                          "outcome_counts": dict(sorted(Counter(item["status"] for item in outcomes).items())),
                          "outcomes": outcomes, "scope": "training_input_feasibility_accounting_only",
                          "all_contexts_feasible": all(item["status"].startswith("accepted_") for item in outcomes) and len(outcomes) == len(rows),
                          "fit_reuse_certified": False, "model_fit_evaluation_identity_certified": False,
                          "scientific_method_approved": False, "new_freeze_created": False,
                          "pending_gates": ["mathematical_and_changed_input_arithmetic_review", "scope_and_exact_fit_reuse_inventory",
                                            "corrected_addendum_code_input_freeze", "full_budget_pilot", "fits_and_analysis", "verification_and_transfer"]})
            if len(outcomes) == len(rows):
                path = self.output / "completion.json"
                if path.exists():
                    if read_sealed(path) != value:
                        raise InvalidCheckpoint("existing completion receipt differs")
                else:
                    write_json_new(path, value)
            else:
                write_json_new(self.output / "passes" / f"{uuid.uuid4().hex}.json", value)
            return value
