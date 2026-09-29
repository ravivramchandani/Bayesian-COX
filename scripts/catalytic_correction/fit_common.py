"""Byte-bound, write-once support for a separately reviewed correction run."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ORIGINAL_COMMIT = "119476fef55b1eeb690527f234c1423440720d45"
ORIGINAL_MANIFEST_SHA = "83b9049fb6aaaadab576b34de0741e4f510344dcefba9f96198d15b5ab4f49b9"
ORIGINAL_CONTENT_SHA = "4577c615486ee871d508837aa812f59539b59338c63834716453a8b03ea394a3"
CONTRACTS_SHA = "83cb84002cd9dc447f70d9346baaba16197fa04d5a43e8b2fb500c2ce38f7fef"
PREFLIGHT_CORE_SHA = "6b03c18a7dc55f896d7c999e0cca676cffb9822132914ce86a90867986a4798c"
REUSE_CORE_SHA = "db558bee7973677305cc9f6e6062bb753e3dbe7daba3f5e08b80b657f115ac84"
OWN_SOURCES = ("fit_common.py", "fit_child.py", "fit_controller.py")
FIT_ACTIONS = frozenset({"fit_changed_inputs", "fit_changed_inputs_reuse_tuning",
                         "retune_then_fit_changed_inputs"})
OUTCOMES = frozenset({"complete", "failed", "failed_diagnostics"})
PILOT_RULE = "each(model,setting,gene_budget):max(n_train*p),then_lexicographic_original_cell_id"
PILOT_ELIGIBILITY = "changed_accepted_training_inputs_complete_role_and_arithmetic_accounting;original_owner_is_launch_barrier_only"
NUMERIC_THREAD_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                            "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")


class InvalidBinding(ValueError):
    """Evidence is absent, unsafe, changed or outside the reviewed contract."""


def require(condition: bool, message: str) -> None:
    """Reject an invalid boundary without changing a scientific outcome."""
    if not condition:
        raise InvalidBinding(message)


def validate_runtime(python: Path, environment: dict[str, str] | None = None) -> dict[str, Any]:
    """Require the actual requested interpreter and numeric-one environment.

    Check before checker subprocesses or scientific imports; a successful report
    from a different interpreter cannot certify this process. The fresh full
    lock check remains a separate execution-time prerequisite.
    """
    supplied = environment if environment is not None else os.environ
    safe(python)
    require(python.is_file() and python.samefile(Path(sys.executable)),
            "current process differs from requested locked interpreter")
    observed = {name: supplied.get(name) for name in NUMERIC_THREAD_VARIABLES}
    require(all(value == "1" for value in observed.values()), "all numeric thread variables must equal one")
    return {"observed_executable": sys.executable, "requested_locked_python": str(python),
            "locked_interpreter_samefile": True, "numeric_thread_environment": observed}


def digest(value: Any) -> str:
    """Hash finite canonical JSON using the original canonical representation."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def sha(path: Path) -> str:
    """Hash bytes of a regular unlinked file with bounded memory."""
    safe(path)
    require(path.is_file(), f"not a regular file: {path}")
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def safe(path: Path) -> Path:
    """Require an explicit absolute path without symlink or parent traversal."""
    require(path.is_absolute() and ".." not in path.parts, f"unsafe path: {path}")
    require(not any(item.is_symlink() for item in (path, *path.parents)), f"linked path: {path}")
    return path


def below(root: Path, name: str) -> Path:
    """Resolve an ordinary nonempty relative artifact name below a bound root."""
    relative = Path(name)
    require(bool(name) and not relative.is_absolute() and ".." not in relative.parts,
            "unsafe relative artifact")
    path = safe(root / relative)
    require(path != root, "artifact name must name a file")
    return path


def read_json(path: Path, expected: str | None = None, *, field: str = "content_sha256") -> dict[str, Any]:
    """Read and recheck byte/content-bound finite JSON without accepting NaNs."""
    before = sha(path)
    require(expected is None or before == expected, f"byte hash differs: {path}")
    value = json.loads(path.read_text(), parse_constant=lambda value: (_ for _ in ()).throw(InvalidBinding(value)))
    require(isinstance(value, dict), "receipt must be a mapping")
    require(value.get(field) == digest({key: item for key, item in value.items() if key != field}),
            f"content hash differs: {path}")
    require(sha(path) == before, f"file changed during read: {path}")
    return value


def seal(value: dict[str, Any]) -> dict[str, Any]:
    """Add an internal digest to a new mapping without claiming approval."""
    require("content_sha256" not in value, "mapping already sealed")
    return {**value, "content_sha256": digest(value)}


def write_new(path: Path, value: dict[str, Any]) -> None:
    """Publish closed/fsynced JSON by exclusive link; never overwrite evidence."""
    safe(path)
    require(path.parent.is_dir() and not path.exists(), "destination absent with existing parent required")
    payload = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()
    write_bytes_new(path, payload)


def write_bytes_new(path: Path, payload: bytes) -> None:
    """Publish exact closed/fsynced bytes exclusively, including raw logs."""
    safe(path)
    require(path.parent.is_dir() and not path.exists(), "destination absent with existing parent required")
    descriptor, name = tempfile.mkstemp(prefix=".fit-pending-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
        temporary.unlink()
        parent = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(parent)
        finally:
            os.close(parent)
    except BaseException:
        # Retain a temporary or partial publication as diagnostic evidence.
        raise


def copy_new(source: Path, destination: Path, expected: str) -> None:
    """Preserve small input receipt bytes exactly rather than reserializing JSON."""
    require(sha(source) == expected, "copy source byte hash differs")
    write_bytes_new(destination, source.read_bytes())
    require(sha(source) == sha(destination) == expected, "copied bytes changed")


def file_binding(path: Path) -> dict[str, Any]:
    """Describe exact current bytes, including zero-length diagnostic logs."""
    return {"sha256": sha(path), "bytes": path.stat().st_size}


def verify_files(root: Path, artifacts: dict[str, Any]) -> None:
    """Verify each hash/length-bound artifact without importing its contents."""
    for name, binding in artifacts.items():
        require(file_binding(below(root, name)) == binding, f"artifact differs: {name}")


def module_from_pin(path: Path, expected: str, name: str) -> Any:
    """Import one explicit verified helper, refusing a reused module namespace."""
    require(name not in sys.modules and sha(path) == expected, "helper byte pin or namespace differs")
    specification = importlib.util.spec_from_file_location(name, path)
    require(specification is not None and specification.loader is not None, "cannot import pinned helper")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    try:
        specification.loader.exec_module(module)
        require(sha(path) == expected, "helper changed while importing")
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


class Claim:
    """Exclusive local owner; stale claims require an explicit external recovery."""

    def __init__(self, path: Path, binding: str) -> None:
        self.path, self.binding, self.nonce = path, binding, uuid.uuid4().hex

    def __enter__(self) -> Claim:
        write_new(self.path, seal({"run_binding_sha256": self.binding, "nonce": self.nonce,
                                   "pid": os.getpid(), "host": socket.gethostname(),
                                   "created_at_utc": datetime.now(UTC).isoformat()}))
        return self

    def __exit__(self, *_arguments: Any) -> None:
        require(read_json(self.path)["nonce"] == self.nonce, "claim ownership changed")
        self.path.unlink()


def verify_original_source(source: Path, manifest: dict[str, Any]) -> None:
    """Require the clean original checkout and every frozen source/input byte."""
    safe(source)
    executable = shutil.which("git")
    require(executable is not None, "Git required for the original checkout boundary")
    commit = subprocess.run([executable, "rev-parse", "HEAD"], cwd=source, capture_output=True,
                            text=True, check=True).stdout.strip()
    status = subprocess.run([executable, "status", "--porcelain"], cwd=source, capture_output=True,
                            text=True, check=True).stdout
    require(commit == ORIGINAL_COMMIT and not status, "original source must remain clean 119476f")
    for name, expected in manifest["input_sha256"].items():
        require(sha(below(source, name)) == expected, f"original source/input differs: {name}")


def verify_environment(source: Path, original: dict[str, Any], python: Path, preflight_manifest: dict[str, Any],
                       output: Path, invoke: Any = subprocess.run) -> dict[str, Any]:
    """Run the pinned 259-package checker and preserve its actual invocation.

    This is an execution-time environment check, not a preparation-time call.
    It performs no cohort, generator, optimizer, scoring or fit operation.
    """
    script, lock, hash_file = source / "scripts/verify_environment.py", source / "conda-lock.yml", source / "conda-lock.yml.sha256"
    require(sha(script) == original["input_sha256"]["scripts/verify_environment.py"]
            and sha(lock) == original["input_sha256"]["conda-lock.yml"], "environment checker/lock bytes differ")
    safe(hash_file)
    argv = [str(python), "-B", str(script), "--lock-file", str(lock), "--hash-file", str(hash_file)]
    started, monotonic = datetime.now(UTC).isoformat(), time.monotonic()
    result = invoke(argv, capture_output=True, check=False)
    write_bytes_new(output / "environment.stdout.json", result.stdout)
    write_bytes_new(output / "environment.stderr.log", result.stderr)
    receipt = seal({"operation": "fresh_original_259_package_environment_verification", "argv": argv,
                    "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(),
                    "wall_seconds": time.monotonic() - monotonic, "exit_code": result.returncode,
                    "stdout": file_binding(output / "environment.stdout.json"),
                    "stderr": file_binding(output / "environment.stderr.log"), "source_sha256": sha(script)})
    write_new(output / "environment_invocation.json", receipt)
    require(result.returncode == 0, "environment checker failed; preserve raw diagnostics")
    report = json.loads(result.stdout, parse_constant=lambda value: (_ for _ in ()).throw(InvalidBinding(value)))
    require(report == preflight_manifest["environment_verification"] and report["status"] == "ok"
            and report["package_count"] == 259 and report["lock_sha256"] == original["input_sha256"]["conda-lock.yml"],
            "fresh full locked environment differs from preflight/witness environment")
    return {"report": report, "invocation": receipt}


def verify_src_modules(source: Path, manifest: dict[str, Any], modules: dict[str, Any] | None = None) -> dict[str, str]:
    """Check every normally imported project module's origin and frozen bytes."""
    found = {}
    for name, module in list((sys.modules if modules is None else modules).items()):
        if name == "src" or name.startswith("src."):
            origin = getattr(module, "__file__", None)
            require(origin is not None, "project namespace module has no bound origin")
            path = safe(Path(origin).absolute())
            require(path.is_relative_to(source), f"foreign project namespace: {name}")
            relative = str(path.relative_to(source))
            require(relative in manifest["input_sha256"] and sha(path) == manifest["input_sha256"][relative],
                    f"imported original project source differs: {name}")
            found[name] = relative
    return found


def read_original_manifest(root: Path) -> dict[str, Any]:
    """Verify original fixed manifest bytes/content before interpreting inputs."""
    value = read_json(root / "manifest.json", ORIGINAL_MANIFEST_SHA, field="manifest_content_sha256")
    require(value["manifest_content_sha256"] == ORIGINAL_CONTENT_SHA
            and value["code"]["git_commit"] == ORIGINAL_COMMIT and not value["code"]["git_dirty"],
            "foreign original manifest")
    return value


def verify_original_outcome(root: Path, identity: str, evidence: dict[str, Any] | None) -> dict[str, Any] | None:
    """Wait for the owner, then verify the exact recorded outcome and all traces.

    None denotes an unfinished/unbound original. It never authorizes either a
    reuse or changed-input fit. Failures have the same byte requirements as
    successes. Orphan bytes are inventoried without invented diagnostics.
    """
    require(re.fullmatch(r"[a-z0-9_.]+", identity) is not None, "unsafe cell identity")
    if safe(root / "claims" / f"{identity}.json").exists():
        return None
    path = safe(root / "cells" / f"{identity}.json")
    if not path.exists() or evidence is None:
        return None
    require(evidence["original_cell_id"] == identity
            and evidence["original_manifest_sha256"] == ORIGINAL_MANIFEST_SHA, "source evidence identity differs")
    cell = read_json(path, evidence["cell_byte_sha256"], field="cell_content_sha256")
    require(cell["cell_id"] == identity and cell["cell_content_sha256"] == evidence["cell_content_sha256"]
            and cell["status"] == evidence["status"] and cell["status"] in OUTCOMES, "source outcome differs")
    referenced = {}
    for attempt in cell.get("fit_attempts", []):
        for record in attempt.get("traces", {}).values():
            name = record["filename"]
            require(Path(name).name == name, "unsafe original trace filename")
            referenced[f"traces/{identity}/{name}"] = record["sha256"]
    require(referenced == evidence["referenced_trace_sha256"], "recorded original trace inventory differs")
    prefix = f"traces/{identity}/"
    orphans = evidence["unreferenced_trace_sha256"]
    require(not set(referenced) & set(orphans), "trace has conflicting ownership")
    all_traces = {**referenced, **orphans}
    for name, expected in all_traces.items():
        require(name.startswith(prefix) and sha(below(root, name)) == expected, "original trace bytes differ")
    directory = safe(root / "traces" / identity)
    actual = set()
    if directory.exists():
        for item in directory.rglob("*"):
            safe(item)
            require(item.is_file() or item.is_dir(), "unsafe original trace node")
            if item.is_file():
                actual.add(str(item.relative_to(root)))
    require(actual == set(all_traces), "original orphan/reference inventory changed")
    require(not (root / "claims" / f"{identity}.json").exists()
            and sha(path) == evidence["cell_byte_sha256"], "original owner/outcome changed during check")
    return cell


def witness_from_json(contracts: Any, value: dict[str, Any], evidence: dict[str, Any] | None = None) -> Any:
    """Decode the pinned pure contract; supplied proof is still not byte proof."""
    document = value["fit_witness"]
    require(set(document) == {"original_cell_id", "model", "correction_specification_sha256",
                              "original_seeds", "corrected_seeds", "roles", "generator_contexts", "original_evidence"},
            "fit witness schema differs")
    original = document["original_evidence"] if evidence is None else evidence
    return contracts.FitWitness(
        original_cell_id=document["original_cell_id"], model=document["model"],
        correction_specification_sha256=document["correction_specification_sha256"],
        original_seeds=document["original_seeds"], corrected_seeds=document["corrected_seeds"],
        roles={key: contracts.Comparison(**row) for key, row in document["roles"].items()},
        generator_contexts={key: tuple(row) for key, row in document["generator_contexts"].items()},
        original_evidence=None if original is None else contracts.SourceEvidence(**original))


def verify_witness_proofs(directory: Path, document: dict[str, Any], contracts: Any) -> None:
    """Check actual role-proof bytes, identities and both canonical value hashes."""
    verify_files(directory, document["proof_artifacts"])
    artifacts = document["proof_artifacts"]
    roles = document["fit_witness"]["roles"]
    for name in contracts.required_roles(document["fit_witness"]["model"]):
        if name in roles:
            comparison = contracts.Comparison(**roles[name])
            if comparison.complete():
                relative = f"roles/{name}.json"
                require(relative in artifacts and artifacts[relative]["sha256"] == comparison.proof_receipt_sha256,
                        f"actual exact role proof absent: {name}")
                proof = read_json(below(directory, relative), comparison.proof_receipt_sha256)
                require(proof["schema_version"] == 1 and proof["role"] == name
                        and proof["original_cell_id"] == document["fit_witness"]["original_cell_id"]
                        and proof["definition_content_sha256"] == document["definition_content_sha256"]
                        and document["fit_witness"]["correction_specification_sha256"] == document["definition_content_sha256"]
                        and proof["basis"] == comparison.basis
                        and digest(proof["original"]) == proof["original_sha256"] == comparison.original_sha256
                        and digest(proof["corrected"]) == proof["corrected_sha256"] == comparison.corrected_sha256,
                        f"role proof values/identity differ: {name}")


def select_pilots(scope: list[dict[str, Any]]) -> list[str]:
    """Choose solely by frozen input dimensions, never by status or performance."""
    groups: dict[tuple[str, str, int], list[dict[str, Any]]] = {}
    require(len({row["original_cell_id"] for row in scope}) == len(scope), "duplicate pilot scope")
    for row in scope:
        require(type(row["n_train"]) is int and type(row["p"]) is int
                and row["n_train"] > 0 and row["p"] > 0 and type(row["gene_budget"]) is int,
                "pilot dimensions must be independently bound positive integers")
        groups.setdefault((row["model"], row["setting"], row["gene_budget"]), []).append(row)
    return sorted(min(rows, key=lambda row: (-row["n_train"] * row["p"], row["original_cell_id"]))["original_cell_id"]
                  for rows in groups.values())


def validate_budget(config: dict[str, Any]) -> None:
    """Require the original full sampling budget and diagnostic remedy count."""
    require(config["sampling"]["draws"] == 2000 and config["sampling"]["tune"] == 2000
            and config["sampling"]["chains"] == 4 and config["sampling"]["target_accept"] == 0.999,
            "full original four-chain budget required")
    require(config["sampling"]["maximum_refits"] == 2
            and config["sampling"]["cores"] == 1
            and config["sampling"]["refit_tune_multiplier"] == 2
            and config["sampling"]["final_noncentered_baseline"] is True,
            "original serial chains and diagnostic remedies required")


def validate_arithmetic(account: dict[str, Any], completion: dict[str, Any], completion_sha: str) -> None:
    """Account genuine kappa-gate failures without redraw or formula relaxation."""
    require(account["status"] == "all_scheduled_arithmetic_outcomes_accounted"
            and account["preflight_completion_sha256"] == completion_sha
            and account["proposals_selected_by_optimizer"] is False
            and account["extra_proposals_generated"] is False, "complete unchanged arithmetic accounting required")
    preflight = {row["context_id"]: row for row in completion["outcomes"]}
    outcomes = account["context_outcomes"]
    require(len(outcomes) == len(preflight) and {row["context_id"] for row in outcomes} == set(preflight),
            "arithmetic context coverage differs")
    bound = {record["sha256"] for record in account["artifacts"].values()}
    for row in outcomes:
        original = preflight[row["context_id"]]
        require(row["preflight_status"] == original["status"]
                and row["preflight_receipt_sha256"] == original["receipt_sha256"]
                and bool(row["evidence_sha256"]) and set(row["evidence_sha256"]) <= bound,
                "arithmetic row lacks current byte-bound evidence")
        accepted = original["status"].startswith("accepted_")
        kappa = row["context_id"].endswith("::outer") and any(f"__{model}__" in row["context_id"] for model in ("catalytic_fixed", "catalytic_adaptive"))
        unchanged = row["status"] == "unchanged_inputs_independently_witnessed"
        require(row["kappa_required"] is (accepted and kappa and not unchanged), "changed fixed/adaptive outer kappa requirements differ")
        if accepted:
            if unchanged:
                require(original["status"] == "accepted_original_first_draw"
                        and row["formula_checks"] == row["original_kappa_status"] == "not_required"
                        and row["independent_replay_receipt_sha256"] in row["evidence_sha256"],
                        "unchanged inputs require exact independent replay evidence")
                continue
            require(row["formula_checks"] == "passed" and row["status"] in {"arithmetic_verified", "original_kappa_gate_failed"},
                    "formula mismatch or missing arithmetic check blocks execution")
            failed = row["status"] == "original_kappa_gate_failed"
            require(row["original_kappa_status"] == ("original_gate_failed" if failed else "passed" if kappa else "not_required"),
                    "kappa outcome marker differs")
            if failed:
                require(kappa and row["optimizer_predicate_evidence_sha256"] in row["evidence_sha256"],
                        "original kappa failure requires exact optimizer/predicate evidence")
                if "__catalytic_adaptive__" in row["context_id"]:
                    require(row["adaptive_status"] == "pending_original_kappa_gate_failure",
                            "failed original kappa cannot imply adaptive optimum verification")
        else:
            require(row["status"] == "preflight_" + original["status"]
                    and row["formula_checks"] == row["original_kappa_status"] == "not_applicable",
                    "nonaccepted input is not an arithmetic or optimizer success")


def execution_definition(freeze: dict[str, Any]) -> str:
    """Acyclic digest of execution inputs/code/policy, excluding reviews/freeze."""
    keys = ("original_production_commit", "original_manifest_sha256", "definition_content_sha256",
            "input_inventory_sha256", "preflight_completion_sha256", "preflight_manifest_sha256",
            "implementation_source_sha256", "dependency_source_sha256", "execution")
    value = {key: freeze[key] for key in keys}
    value["arithmetic_accounting_sha256"] = freeze["arithmetic_accounting"]["sha256"]
    return digest(value)


def load_gates(freeze_path: Path, freeze_sha: str, manifest_path: Path, manifest_sha: str,
               own_directory: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Require actual reviewed correction files before child execution is possible.

    This function verifies supplied review evidence and bindings; it cannot
    confer scientific approval or produce a freeze. Preparation has no actual
    files satisfying this contract.
    """
    freeze, manifest = read_json(freeze_path, freeze_sha), read_json(manifest_path, manifest_sha)
    require(freeze["status"] == "reviewed_corrected_fit_freeze"
            and manifest["status"] == "corrected_fit_manifest_frozen"
            and manifest["freeze_sha256"] == freeze_sha
            and freeze["original_production_commit"] == ORIGINAL_COMMIT
            and freeze["original_manifest_sha256"] == ORIGINAL_MANIFEST_SHA,
            "a separate reviewed correction freeze/manifest is required")
    require(freeze["implementation_source_sha256"] == {name: sha(own_directory / name) for name in OWN_SOURCES},
            "controller/child/support bytes differ from reviewed correction freeze")
    dependencies = freeze["dependency_source_sha256"]
    require(set(dependencies) == {"contracts", "preflight_core", "reuse_core"}
            and dependencies["contracts"] == CONTRACTS_SHA and dependencies["preflight_core"] == PREFLIGHT_CORE_SHA
            and dependencies["reuse_core"] == REUSE_CORE_SHA,
            "reviewed dependency pins differ")
    paths = {key: safe(Path(value)) for key, value in freeze["paths"].items()}
    require(set(paths) == {"source", "original_run", "matched", "preflight", "contracts", "preflight_core",
                           "witness_root", "inventory", "reuse_core"}, "explicit frozen input path roles differ")
    require(sha(paths["contracts"]) == CONTRACTS_SHA and sha(paths["preflight_core"]) == PREFLIGHT_CORE_SHA
            and sha(paths["reuse_core"]) == dependencies["reuse_core"],
            "external dependency bytes differ")
    original = read_original_manifest(paths["original_run"])
    validate_budget(original["run_config"])
    inventory = read_json(paths["inventory"], freeze["input_inventory_sha256"])
    require(inventory["definition_content_sha256"] == freeze["definition_content_sha256"]
            == manifest["definition_content_sha256"]
            and manifest["input_inventory_sha256"] == freeze["input_inventory_sha256"]
            and inventory["scheduled_cells"] == 1625 and len(inventory["entries"]) == 1625
            and len({row["original_cell_id"] for row in inventory["entries"]}) == 1625,
            "whole immutable input inventory differs")
    require({row["original_cell_id"] for row in inventory["entries"]}
            == {row["cell_id"] for row in original["plan"]}, "inventory does not cover the exact original logical grid")
    require(len({row["original_cell_id"] for row in inventory["selection_scope"]}) == len(inventory["selection_scope"])
            and {row["original_cell_id"] for row in inventory["selection_scope"]}
            <= {row["original_cell_id"] for row in inventory["entries"]}, "pilot input scope is duplicate or foreign")
    completion = read_json(paths["preflight"] / "completion.json", freeze["preflight_completion_sha256"])
    preflight_manifest = read_json(paths["preflight"] / "manifest.json", freeze["preflight_manifest_sha256"])
    require(completion["status"] == "all_scheduled_contexts_accounted"
            and completion["scheduled_contexts"] == completion["accounted_contexts"] == 1650
            and len(completion["outcomes"]) == 1650
            and len({row["context_id"] for row in completion["outcomes"]}) == 1650
            and inventory["preflight_completion_sha256"] == freeze["preflight_completion_sha256"],
            "full 825 outer plus 825 WME inner preflight accounting required")
    require(preflight_manifest["content_sha256"] == completion["run_binding_sha256"]
            and preflight_manifest["original_manifest_sha256"] == ORIGINAL_MANIFEST_SHA
            and preflight_manifest["environment_verification"]["status"] == "ok"
            and preflight_manifest["environment_verification"]["package_count"] == 259
            and preflight_manifest["environment_verification"]["lock_sha256"] == original["input_sha256"]["conda-lock.yml"],
            "actual full locked preflight environment/run binding required")
    arithmetic_path = safe(Path(freeze["arithmetic_accounting"]["path"]))
    arithmetic = read_json(arithmetic_path, freeze["arithmetic_accounting"]["sha256"])
    verify_files(arithmetic_path.parent, arithmetic["artifacts"])
    validate_arithmetic(arithmetic, completion, freeze["preflight_completion_sha256"])
    require(set(freeze["review_bindings"]) == {"method", "arithmetic", "input_witness", "implementation", "freeze"},
            "actual method/arithmetic/input/implementation/freeze reviews are required")
    for role, record in freeze["review_bindings"].items():
        review = read_json(safe(Path(record["path"])), record["sha256"])
        require(review["status"] == "reviewed_for_corrected_fit_execution"
                and review["role"] == role
                and review["definition_content_sha256"] == freeze["definition_content_sha256"]
                and review["input_inventory_sha256"] == freeze["input_inventory_sha256"]
                and review["execution_definition_sha256"] == execution_definition(freeze),
                "review is not bound to this correction input scope")
    require(freeze["execution"] == {"fit_workers": 1, "numeric_threads": 1,
                                     "original_full_budget": True, "pilot_rule": PILOT_RULE,
                                     "pilot_eligibility": PILOT_ELIGIBILITY,
                                     "original_resolution_policy": "fresh_reviewed_finished_source_snapshot"},
            "serial full-budget pilot and original ownership policy required")
    require(manifest["pilot_cells"] == select_pilots(inventory["selection_scope"]), "pilot scope/rule differs")
    return freeze, manifest, inventory, completion
