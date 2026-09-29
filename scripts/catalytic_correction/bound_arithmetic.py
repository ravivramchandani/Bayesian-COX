"""Root-controlled arithmetic against accepted, byte-bound preflight inputs.

No cohort, generator, constructor or rank check is called. The default validate
command cannot optimize. compute-kappa is a separately named explicit stage;
an optimizer failure leaves a retained failed attempt, never a new proposal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

if __package__:
    from .independent_arithmetic import (
        ORIGINAL_CATALYTIC_SHA256,
        ORIGINAL_COMMIT,
        Inputs,
        load_original_functions,
        require,
        validate_arithmetic,
        validate_kappa,
        validate_training_units,
    )
else:
    from independent_arithmetic import (
        ORIGINAL_CATALYTIC_SHA256,
        ORIGINAL_COMMIT,
        Inputs,
        load_original_functions,
        require,
        validate_arithmetic,
        validate_kappa,
        validate_training_units,
    )

PRODUCTION_CONTEXTS = 1650
ACCEPTED = {"accepted_original_first_draw", "accepted_rank_conditioned_redraw"}
CONTEXT_PATTERN = re.compile(r"([a-z0-9_.]+)::(outer|inner_0[1-3])\Z")
ADDITIONAL_ORIGINAL_SOURCES = {
    "src/models/bayesian/extensions.py": "6148415b512915dbf4141c8bc1ce3ca4d6adcea4dea81d99f25f9c6909791449",
    "src/pipelines/extensions/preprocessing.py": "94f40f635c0b072e6f42314a04f7447f5ee9546297ee4fcd3cfed42a2af9f635",
}


def canonical_hash(value: Any) -> str:
    """Use the exact original canonical JSON encoding, rejecting nonfinite JSON."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def file_hash(path: Path) -> str:
    """Stream only explicitly bound small source/input artifacts, never traces."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    """Refuse absolute/traversing/linked paths including linked ancestor roots."""
    name = Path(relative)
    require(root.is_absolute() and root.is_dir() and not name.is_absolute()
            and bool(relative) and ".." not in name.parts, "unsafe bound artifact path")
    path = root / name
    require(path.is_file() and not any(item.is_symlink() for item in (path, *path.parents)),
            "missing or linked bound artifact")
    return path


def read_sealed(path: Path, expected_sha256: str | None = None) -> dict[str, Any]:
    """Check byte pin when supplied and the preflight receipt's content digest."""
    require(not any(item.is_symlink() for item in (path, *path.parents)), "linked receipt")
    data = path.read_bytes()
    if expected_sha256 is not None:
        require(hashlib.sha256(data).hexdigest() == expected_sha256, "receipt byte binding changed")
    value = json.loads(data)
    require(isinstance(value, dict) and value.get("content_sha256") == canonical_hash(
        {key: item for key, item in value.items() if key != "content_sha256"}), "receipt content changed")
    return value


def witness(array: np.ndarray) -> dict[str, Any]:
    """Verify the preflight's exact dtype/shape/C-order numeric element witness."""
    require(not array.dtype.hasobject, "object array is forbidden")
    return {"dtype": array.dtype.str, "shape": list(array.shape),
            "values_sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest()}


def context_parts(context_id: str) -> tuple[str, str]:
    """Derive a stable logical namespace, never a host-absolute output reference."""
    match = CONTEXT_PATTERN.fullmatch(context_id)
    require(match is not None, "invalid logical context ID")
    return match.group(1), match.group(2)


def retry_seed(base: int, index: int) -> int:
    """Account for the unchanged reviewed retry seed rule without drawing data."""
    if index == 0:
        return base
    payload = f"{base}|rank_conditioned_retry|{index}".encode()
    return int.from_bytes(hashlib.sha256(payload).digest()[:4], "big") % (2**31 - 1)


class Snapshot:
    """Byte-bound complete-context accounting and root-requested arithmetic scope.

    Production CLI fixes expected_contexts=1650. Smaller values exist solely
    for pure synthetic fixture tests. This class is not a preflight replay or
    a proof that the requested scope covers every changed fitting input.
    """

    def __init__(self, root: Path, completion_sha256: str, selection: Path,
                 selection_sha256: str, *, expected_contexts: int = PRODUCTION_CONTEXTS) -> None:
        self.root, self.pins = root, {}
        completion_path = safe_path(root, "completion.json")
        completion = read_sealed(completion_path, completion_sha256)
        self.pins[completion_path] = completion_sha256
        require(completion.get("schema_version") == 1
                and completion.get("status") == "all_scheduled_contexts_accounted"
                and completion.get("scheduled_contexts") == completion.get("accounted_contexts") == expected_contexts,
                "full scheduled preflight accounting is required")
        outcomes = completion.get("outcomes")
        require(isinstance(outcomes, list) and len(outcomes) == expected_contexts,
                "preflight completion outcome accounting differs")
        self.outcomes = {}
        for row in outcomes:
            context_id = row["context_id"]
            cell, role = context_parts(context_id)
            require(context_id not in self.outcomes and row["receipt_path"] == f"contexts/{cell}/{role}/receipt.json",
                    "duplicate or displaced preflight context")
            self.outcomes[context_id] = row
        require(completion["outcome_counts"] == dict(Counter(row["status"] for row in outcomes)),
                "preflight completion status counts differ")
        if expected_contexts == PRODUCTION_CONTEXTS:
            outer = [identity for identity in self.outcomes if identity.endswith("::outer")]
            inner = [identity for identity in self.outcomes if not identity.endswith("::outer")]
            require(len(outer) == len(inner) == 825 and all("__catalytic_wme__" in i for i in inner),
                    "all 825 outer and 825 WME inner contexts must be accounted")
            require(all(f"{context_parts(i)[0]}::inner_{fold:02d}" in self.outcomes
                        for i in inner for fold in range(1, 4)), "incomplete WME inner triplet")
        require(all(completion.get(key) is False for key in (
            "fit_reuse_certified", "model_fit_evaluation_identity_certified",
            "scientific_method_approved", "new_freeze_created")), "preflight scope flags changed")
        request = read_sealed(selection, selection_sha256)
        self.pins[selection] = selection_sha256
        require(request.get("schema_version") == 1
                and request.get("kind") == "root_requested_arithmetic_contexts"
                and request.get("preflight_completion_sha256") == completion_sha256
                and request.get("run_binding_sha256") == completion["run_binding_sha256"],
                "requested arithmetic scope refers to another preflight")
        selected = request.get("contexts")
        require(isinstance(selected, list) and bool(selected), "empty requested arithmetic scope")
        self.selected = []
        seen = set()
        for row in selected:
            identity = row["context_id"]
            require(identity in self.outcomes and identity not in seen, "missing or duplicate requested context")
            seen.add(identity)
            outcome = self.outcomes[identity]
            require(outcome["status"] in ACCEPTED
                    and row["context_receipt_sha256"] == outcome["receipt_sha256"],
                    "requested arithmetic needs bound accepted contexts")
            require(type(row["adaptive_required"]) is bool and type(row["kappa_required"]) is bool,
                    "adaptive and kappa requirements must be explicit")
            require(not row["adaptive_required"] or row["kappa_required"], "adaptive expression needs checked kappa")
            if any(f"__{model}__" in identity for model in ("catalytic_fixed", "catalytic_adaptive")) and identity.endswith("::outer"):
                require(row["kappa_required"], "both Bayesian catalytic outer contexts need original kappa initialization")
            if "__catalytic_adaptive__" in identity and identity.endswith("::outer"):
                require(row["adaptive_required"], "adaptive outer context cannot omit checked kappa arithmetic")
            path = safe_path(root, outcome["receipt_path"])
            receipt = read_sealed(path, outcome["receipt_sha256"])
            require(receipt["content_sha256"] == outcome["receipt_content_sha256"]
                    and receipt["status"] == outcome["status"]
                    and receipt["request"]["context_id"] == identity
                    and receipt["request"]["run_binding_sha256"] == completion["run_binding_sha256"],
                    "requested context completion binding differs")
            self.pins[path] = outcome["receipt_sha256"]
            # Retain only small selector/completion rows, not every context's
            # potentially long proposal/processor history in memory.
            self.selected.append((row, outcome, path.parent))
        self.completion_sha256, self.selection_sha256 = completion_sha256, selection_sha256
        self.run_binding_sha256 = completion["run_binding_sha256"]

    def artifact(self, directory: Path, name: str, binding: dict[str, Any]) -> Path:
        """Verify an accepted-input artifact and bind it for final recheck."""
        path = safe_path(directory, name)
        require(type(binding.get("bytes")) is int and path.stat().st_size == binding["bytes"]
                and file_hash(path) == binding["sha256"], "accepted artifact bytes changed")
        self.pins[path] = binding["sha256"]
        return path

    def load(self, selected: tuple[dict[str, Any], dict[str, Any], Path]) -> tuple[Inputs, dict[str, Any]]:
        """Read one accepted design and training context; do not load other arrays."""
        row, outcome, directory = selected
        receipt = read_sealed(directory / "receipt.json", outcome["receipt_sha256"])
        require(receipt["content_sha256"] == outcome["receipt_content_sha256"],
                "selected context content binding differs")
        artifacts = receipt["artifacts"]
        input_path = self.artifact(directory, "input.json", artifacts["input.json"])
        real_path = self.artifact(directory, "inputs.npz", artifacts["inputs.npz"])
        inputs_record = read_sealed(input_path)
        input_witness = inputs_record["input_witness"]
        require(inputs_record["request"] == receipt["request"]
                and canonical_hash(input_witness) == receipt["request"]["input_witness_sha256"],
                "training witness/request binding differs")
        attempts, accepted = receipt["attempts"], receipt["accepted_attempt_index"]
        require(type(accepted) is int and accepted == len(attempts) - 1
                and 0 <= accepted < receipt["request"]["candidate_cap"] <= 256,
                "accepted attempt accounting differs")
        original_seed = receipt["request"]["original_generation_seed"]
        for index, attempt in enumerate(attempts):
            name = f"attempt_{index:03d}/receipt.json"
            attempt_path = self.artifact(directory, name, artifacts[name])
            require(read_sealed(attempt_path) == attempt and attempt["request"] == receipt["request"]
                    and attempt["attempt_index"] == index
                    and attempt["seed"] == retry_seed(original_seed, index)
                    and attempt["status"] == ("accepted_original_constructor" if index == accepted
                                               else "frozen_rank_rejected"),
                    "original-only retry history accounting differs")
        require((receipt["status"] == "accepted_original_first_draw") == (accepted == 0),
                "first/redraw context status differs")
        prefix = f"attempt_{accepted:03d}"
        attempt = attempts[accepted]
        proposal_path = self.artifact(directory, prefix + "/proposal.npz", artifacts[prefix + "/proposal.npz"])
        require(attempt["artifacts"]["proposal.npz"] == artifacts[prefix + "/proposal.npz"],
                "accepted proposal artifact maps disagree")
        with np.load(real_path, allow_pickle=False) as archive:
            require(len(archive.files) == 3 and set(archive.files) == {"real_design", "real_time", "real_event"},
                    "unexpected real-input archive keys")
            real = {name: archive[name] for name in archive.files}
        with np.load(proposal_path, allow_pickle=False) as archive:
            require(len(archive.files) == 4 and set(archive.files) ==
                    {"synthetic_design", "synthetic_time", "hazard", "time_scale"},
                    "unexpected accepted proposal archive keys")
            synthetic = {name: archive[name] for name in archive.files}
        aliases = {"real_design": "real_design", "real_time": "training_time", "real_event": "training_event"}
        require(all(witness(array) == input_witness[aliases[name]] for name, array in real.items()),
                "real training array witnesses differ")
        require({name: witness(array) for name, array in synthetic.items()} == attempt["array_witnesses"],
                "accepted synthetic array witnesses differ")
        require(synthetic["hazard"].shape == synthetic["time_scale"].shape == ()
                and synthetic["hazard"].dtype == synthetic["time_scale"].dtype == np.dtype("float64"),
                "accepted hazard/time scale must be float64 scalars")
        ids = input_witness["ordered_training_subject_ids"]
        require(canonical_hash(ids) == input_witness["training_membership_sha256"]
                and len(ids) == len(real["real_time"]) == input_witness["n_train"]
                and len(input_witness["feature_names"]) == real["real_design"].shape[1]
                and canonical_hash(input_witness["processor_metadata"]) == input_witness["processor_metadata_sha256"],
                "training identity/preprocessing witness differs")
        inputs = Inputs(synthetic["synthetic_design"], synthetic["synthetic_time"], float(synthetic["hazard"]),
                        real["real_design"], real["real_time"], real["real_event"], float(synthetic["time_scale"]))
        inputs.validate()
        lineage = {"context_id": row["context_id"], "context_receipt_sha256": row["context_receipt_sha256"],
                   "input_witness_sha256": receipt["request"]["input_witness_sha256"],
                   "accepted_attempt_index": accepted, "original_generation_seed": original_seed,
                   "accepted_proposal_sha256": artifacts[prefix + "/proposal.npz"]["sha256"],
                   "real_inputs_sha256": artifacts["inputs.npz"]["sha256"],
                   "accepted_array_witnesses": attempt["array_witnesses"],
                   "training_array_witnesses": {name: input_witness[key] for name, key in aliases.items()},
                   "training_membership_sha256": input_witness["training_membership_sha256"]}
        return inputs, lineage

    def recheck(self) -> None:
        """Refuse source/input changes after calculations and before final receipt."""
        for path, digest in self.pins.items():
            require(not any(item.is_symlink() for item in (path, *path.parents))
                    and file_hash(path) == digest, "bound evidence changed during arithmetic")


def publish_new(path: Path, value: dict[str, Any]) -> None:
    """Publish closed fsynced JSON bytes atomically without replacing a path.

    A failure retains the output attempt. No final receipt is written until
    exact inventory and rechecks pass. A cleanup/link failure propagates.
    """
    payload = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    require(not path.exists() and not path.is_symlink(), "refuse output overwrite")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".arithmetic-", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        temporary.unlink()
        descriptor = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    except BaseException:
        # Do not remove residual partial/temp evidence after publication errors.
        raise


def sealed(value: dict[str, Any]) -> dict[str, Any]:
    """Seal a newly produced mapping without promoting its scientific scope."""
    require("content_sha256" not in value, "mapping already sealed")
    return {**value, "content_sha256": canonical_hash(value)}


def prepare_destination(path: Path, forbidden: list[Path]) -> None:
    """Create a new external attempt outside immutable inputs/reference roots."""
    require(path.is_absolute() and ".." not in path.parts and path.parent.is_dir()
            and not any(item.is_symlink() for item in (path, *path.parents)), "unsafe output destination")
    require(all(not path.is_relative_to(root) and not root.is_relative_to(path) for root in forbidden),
            "output overlaps immutable input/source roots")
    path.mkdir(exist_ok=False)
    (path / "contexts").mkdir()


def context_output_name(identity: str) -> str:
    """One stable flat filename per context; no host-path leakage into facts."""
    return canonical_hash(identity) + ".json"


def verify_output_inventory(root: Path, expected_files: set[str]) -> None:
    """Refuse all residual/temp/linked files and unexpected empty directories."""
    files, directories = set(), set()
    for path in root.rglob("*"):
        require(not path.is_symlink(), "linked output artifact")
        name = str(path.relative_to(root))
        if path.is_file():
            files.add(name)
        elif path.is_dir():
            directories.add(name)
        else:
            require(False, "unrecognized output artifact")
    require(files == expected_files and directories == {"contexts"},
            "residual/missing output artifacts prevent final arithmetic receipt")


def read_kappa(root: Path, completion_sha: str,
               snapshot: Snapshot) -> dict[str, tuple[float, np.ndarray, str, dict[str, Any]]]:
    """Load separately bound finite optimum witnesses; never optimize here."""
    path = safe_path(root, "receipt.json")
    receipt = read_sealed(path, completion_sha)
    require(receipt["status"] == "requested_kappa_witnesses_computed"
            and receipt["preflight_completion_sha256"] == snapshot.completion_sha256
            and receipt["selection_sha256"] == snapshot.selection_sha256
            and receipt["original_source_sha256"] == ORIGINAL_CATALYTIC_SHA256
            and receipt["optimizer_invoked"] is True
            and receipt["new_proposals_generated"] is False
            and receipt["proposals_selected_by_optimizer"] is False,
            "kappa witness scope differs")
    snapshot.pins[path] = completion_sha
    invocation_path = safe_path(root, "invocation.json")
    invocation = read_sealed(invocation_path, receipt["invocation_sha256"])
    snapshot.pins[invocation_path] = receipt["invocation_sha256"]
    own_sources = {path.name: file_hash(path) for path in (Path(__file__), Path(__file__).with_name("independent_arithmetic.py"))}
    required = {row["context_id"] for row, _, _ in snapshot.selected if row["kappa_required"]}
    stages = invocation["optimizer_context_stages"]
    require(invocation["command"] == "compute-kappa"
            and invocation["sources"] == receipt["implementation_sources"] == own_sources
            and receipt["additional_original_source_bindings"] == ADDITIONAL_ORIGINAL_SOURCES
            and set(receipt["contexts"]) == set(stages) == required
            and receipt["reported_context_count"] == len(required)
            and receipt["requested_context_count"] == len(snapshot.selected)
            and all(stage["stage"] == "original_catalytic_kappa"
                    and stage["status"] == "computed_and_independently_checked"
                    and "started_at_utc" in stage and "finished_at_utc" in stage
                    and isinstance(stage["wall_seconds"], (int, float)) and stage["wall_seconds"] >= 0
                    for stage in stages.values()), "optimizer invocation/stage/source binding differs")
    found = {}
    for identity, row in receipt["contexts"].items():
        require(row["path"] == "contexts/" + context_output_name(identity), "displaced kappa witness")
        item_path = snapshot.artifact(root, row["path"], row["artifact"])
        item = read_sealed(item_path)
        require(item["context_id"] == identity and item["optimizer_stage"] == "original_catalytic_kappa"
                and item["original_source_sha256"] == ORIGINAL_CATALYTIC_SHA256
                and item["proposal_selected_by_optimizer"] is False,
                "unrecognized supplied kappa provenance")
        beta = np.asarray(item["beta_hat"], dtype=float)
        found[identity] = (float(item["kappa"]), beta, file_hash(item_path), item["lineage"])
    verify_output_inventory(root, {"invocation.json", "receipt.json",
                                   *(row["path"] for row in receipt["contexts"].values())})
    return found


def run(args: argparse.Namespace) -> dict[str, Any]:
    """Execute one explicitly requested arithmetic or separately named kappa stage."""
    started, monotonic = datetime.now(UTC).isoformat(), time.monotonic()
    snapshot = Snapshot(args.preflight_root, args.completion_sha256, args.selection, args.selection_sha256)
    source = load_original_functions(args.source_checkout, optimizer_enabled=args.command == "compute-kappa")
    own_sources = {path.name: file_hash(path) for path in (Path(__file__), Path(__file__).with_name("independent_arithmetic.py"))}
    source_path = args.source_checkout / source.source_relative
    snapshot.pins[source_path] = source.source_sha256
    for relative, digest in ADDITIONAL_ORIGINAL_SOURCES.items():
        path = safe_path(args.source_checkout, relative)
        require(file_hash(path) == digest, "original generator/Bayesian initialization source changed")
        snapshot.pins[path] = digest
    kappas = {}
    forbidden = [args.preflight_root, args.source_checkout, Path(__file__).parent]
    if args.kappa_root is not None:
        require(args.command == "validate" and args.kappa_receipt_sha256 is not None, "invalid kappa witness arguments")
        kappas = read_kappa(args.kappa_root, args.kappa_receipt_sha256, snapshot)
        forbidden.append(args.kappa_root)
    else:
        require(args.kappa_receipt_sha256 is None, "kappa receipt needs a witness root")
    required = {row["context_id"] for row, _, _ in snapshot.selected if row["kappa_required"]}
    if args.command == "validate":
        require(required <= set(kappas), "checked kappa witnesses are required before Bayesian catalytic validation")
    else:
        require(bool(required), "no requested kappa contexts")
    prepare_destination(args.destination, forbidden)
    records = {}
    optimizer_stages = {}
    current_context = None
    units = None
    result = None
    try:
        for selected in snapshot.selected:
            row, _, _ = selected
            identity = row["context_id"]
            if args.command == "compute-kappa" and identity not in required:
                continue
            current_context, units, result = identity, None, None
            inputs, lineage = snapshot.load(selected)
            units = validate_training_units(inputs)
            require(all(item["passed"] for item in units), "accepted time-scale/hazard differs from training convention")
            if args.command == "compute-kappa":
                stage_start, stage_clock = datetime.now(UTC).isoformat(), time.monotonic()
                optimizer_stages[identity] = {"stage": "original_catalytic_kappa", "started_at_utc": stage_start,
                                              "status": "started"}
                try:
                    kappa, beta_hat = source.catalytic_kappa(inputs.reference_data())
                    checks = validate_kappa(inputs, source, float(kappa), beta_hat)
                    require(all(item["passed"] for item in checks), "computed kappa fails independent witness checks")
                except Exception as error:
                    optimizer_stages[identity].update(status="failed_no_retry",
                                                      finished_at_utc=datetime.now(UTC).isoformat(),
                                                      wall_seconds=time.monotonic() - stage_clock,
                                                      exception_type=type(error).__name__, message=str(error))
                    raise
                optimizer_stages[identity].update(status="computed_and_independently_checked",
                                                  finished_at_utc=datetime.now(UTC).isoformat(),
                                                  wall_seconds=time.monotonic() - stage_clock)
                record = {"schema_version": 1, "context_id": identity, "lineage": lineage,
                          "optimizer_stage": "original_catalytic_kappa", "optimizer_invoked": True,
                          "proposal_selected_by_optimizer": False, "kappa": float(kappa),
                          "beta_hat": beta_hat.tolist(), "independent_checks": checks,
                          "training_unit_checks": units, "original_source_sha256": source.source_sha256}
            else:
                supplied = kappas.get(identity)
                if supplied is not None:
                    require(supplied[3] == lineage, "supplied kappa binds different accepted input arrays")
                result = validate_arithmetic(inputs, source, kappa=None if supplied is None else supplied[0],
                                             beta_hat=None if supplied is None else supplied[1])
                record = {"schema_version": 1, "context_id": identity, "lineage": lineage,
                          "result": result, "training_unit_checks": units,
                          "supplied_kappa_witness_sha256": None if supplied is None else supplied[2],
                          "original_source_sha256": source.source_sha256}
            name = "contexts/" + context_output_name(identity)
            publish_new(args.destination / name, sealed(record))
            path = args.destination / name
            records[identity] = {"path": name, "artifact": {"sha256": file_hash(path), "bytes": path.stat().st_size}}
            if args.command == "validate":
                require(result["status"] == "arithmetic_passed", "finite-design arithmetic comparison failed")
                require(not row["adaptive_required"] or result["adaptive_status"] == "checked_supplied_kappa",
                        "required adaptive arithmetic remains incomplete")
            del inputs, record
        snapshot.recheck()
        require(own_sources == {path.name: file_hash(path) for path in (Path(__file__), Path(__file__).with_name("independent_arithmetic.py"))},
                "arithmetic implementation changed during execution")
        invocation = {"schema_version": 1, "argv": sys.argv, "command": args.command,
                      "absolute_paths": {"preflight_root": str(args.preflight_root), "selection": str(args.selection),
                                         "source_checkout": str(args.source_checkout), "destination": str(args.destination),
                                         "kappa_root": None if args.kappa_root is None else str(args.kappa_root)},
                      "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(),
                      "wall_seconds": time.monotonic() - monotonic, "sources": own_sources,
                      "optimizer_context_stages": optimizer_stages}
        publish_new(args.destination / "invocation.json", sealed(invocation))
        expected = {"invocation.json", *(item["path"] for item in records.values())}
        verify_output_inventory(args.destination, expected)
        receipt = sealed({"schema_version": 1, "status": "requested_kappa_witnesses_computed"
                          if args.command == "compute-kappa" else "requested_context_arithmetic_passed",
                          "scope": "requested_accepted_contexts_only_not_all_changed_fit_inputs_certification",
                          "preflight_completion_sha256": snapshot.completion_sha256,
                          "selection_sha256": snapshot.selection_sha256, "run_binding_sha256": snapshot.run_binding_sha256,
                          "original_commit": ORIGINAL_COMMIT, "original_source_sha256": source.source_sha256,
                          "additional_original_source_bindings": ADDITIONAL_ORIGINAL_SOURCES,
                          "implementation_sources": own_sources, "contexts": records,
                          "requested_context_count": len(snapshot.selected), "reported_context_count": len(records),
                          "invocation_sha256": file_hash(args.destination / "invocation.json"),
                          "optimizer_invoked": args.command == "compute-kappa", "rank_check_invoked": False,
                          "new_proposals_generated": False, "proposals_selected_by_optimizer": False,
                          "predictive_metrics_computed": False, "fit_reuse_certified": False,
                          "method_freeze_certified": False, "programme_completion_certified": False})
        publish_new(args.destination / "receipt.json", receipt)
        verify_output_inventory(args.destination, expected | {"receipt.json"})
        return receipt
    except Exception as error:
        # Partial scientific rows and exact failure are retained; no success receipt
        # is manufactured. If publication itself failed, residual temp files remain.
        failure = {"schema_version": 1, "command": args.command, "exception_type": type(error).__name__,
                   "message": str(error), "reported_contexts": sorted(records),
                   "failed_context_id": current_context, "training_unit_checks": units,
                   "arithmetic_result": result, "optimizer_context_stages": optimizer_stages,
                   "failed_at_utc": datetime.now(UTC).isoformat(), "status": "failed_arithmetic_attempt",
                   "retry_or_replacement_proposal_generated": False}
        if not (args.destination / "receipt.json").exists() and not (args.destination / "failure.json").exists():
            publish_new(args.destination / "failure.json", sealed(failure))
        raise


def parser() -> argparse.ArgumentParser:
    """Expose explicit stage names; there is no optimize/fitting fallback."""
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("command", choices=("validate", "compute-kappa"))
    for option in ("preflight-root", "selection", "source-checkout", "destination"):
        result.add_argument("--" + option, type=Path, required=True)
    for option in ("completion-sha256", "selection-sha256"):
        result.add_argument("--" + option, required=True)
    result.add_argument("--kappa-root", type=Path)
    result.add_argument("--kappa-receipt-sha256")
    return result


def main() -> int:
    """Return rc0 only for the completed requested stage's verified inventory."""
    try:
        value = run(parser().parse_args())
    except Exception as error:
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"status": value["status"], "reported_context_count": value["reported_context_count"],
                      "optimizer_invoked": value["optimizer_invoked"], "fit_reuse_certified": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
