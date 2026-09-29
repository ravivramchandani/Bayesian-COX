"""Prospective, byte-bound pilot/remaining dispatch; no scientific predicates."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SOURCES = ("capture_guarded_dispatch.py", "guard_fit_dispatch.py", "verify_guarded_dispatch_proof.py")
FIT_PINS = {
    "fit_common.py": "b17f378ba77ea3ae5ba25c836e963a1a0160556465b25745462f648e325d1f11",
    "fit_child.py": "8ec459f949d7edb18bb587b42eab5baa823fa606075b086c8a5b2475256b2935",
    "fit_controller.py": "1fdeecc9d437bae930414bc84094da01f21140e6db86e09193cf47a395f1a038",
}
REPRODUCTION_PINS = {
    "reproduction_core.py": "fa43d4c75f231a59f12adb73b312627744b6c40dd0a97c002016ed4cba597cb5",
    "run_reproduction.py": "86eed8bd3af2f5ddab9b1bf354e7251518cfb64932da778d05d63a937209829c",
    "terminal_replay_child.py": "830e866d38eb65f9742cb9e7e48212f532ee1d1bfd9eeb7791ca89dbe3dacc61",
}
THREADS = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
NAMESPACE = Path("passes/guarded_dispatch_v1")
REQUEST_KEYS = frozenset({
    "schema_version", "status", "test_only", "guard_code", "guard_source_sha256", "guard_preparation",
    "implementation_review", "scope_review", "adoption", "selection", "freeze", "manifest", "fit_code",
    "reproduction_code", "corrected_run", "locked_python", "phase", "limit", "pilot_review", "resolution_review",
    "request_body_sha256", "content_sha256",
})
FREEZE_TREE_ROLES = frozenset({"source", "original_run", "preflight", "witness_root"})
FREEZE_FILE_ROLES = frozenset({"matched", "contracts", "preflight_core", "reuse_core", "inventory"})
SELECTION_TREE_ROLES = frozenset({"fit_code", "original_reproduction"})
SELECTION_FILE_ROLES = frozenset({"freeze", "manifest", "original_numerical_evidence", "recipe_inventory", "scope_review"})
ACCOUNT_BASE_KEYS = frozenset({
    "schema_version", "original_cell_id", "evidence_status", "corrected_manifest_sha256", "correction_freeze_sha256",
    "definition_content_sha256", "input_witness_path", "input_witness_sha256", "source_evidence", "decision",
    "generator_contexts", "original_seed_namespace", "fit_dispatched", "artifacts", "programme_complete",
    "reporting_certified", "release_certified", "operation", "scientific_status", "original_reference",
    "newly_executed_fit", "fit_seconds", "content_sha256",
})
ACCOUNT_PASS_KEYS = frozenset({
    "schema_version", "phase", "corrected_manifest_sha256", "status", "scheduled_logical_cells",
    "retained_logical_outcomes", "current_pass", "record_sha256", "all_fits_numerically_verified",
    "programme_complete", "reporting_certified", "release_certified", "pending_gates", "content_sha256",
})
ACCOUNT_DECISION_KEYS = frozenset({
    "schema_version", "scope", "original_cell_id", "model", "correction_specification_sha256", "action",
    "missing_roles", "changed_roles", "generator_failures", "witness_sha256", "tuning_record_reused_sha256",
    "original_status", "original_outcome_available", "source_evidence", "seed_ledger_sha256", "fit_dispatched", "decision_content_sha256",
})
PENDING_ACCOUNT_STATUSES = frozenset({
    "await_original_owner_or_outcome", "await_original_outcome", "unresolved", "changed_inputs_waiting_for_authorized_phase",
})


class InvalidProof(ValueError):
    """Missing, unsafe, changed, retrospective or unavailable guard evidence."""


def require(condition: bool, message: str) -> None:
    """Refuse a binding without altering scientific evidence."""
    if not condition:
        raise InvalidProof(message)


def digest(value: Any) -> str:
    """Hash finite canonical JSON."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def safe(path: Path) -> Path:
    """Require an absolute, unlinked path without traversal."""
    require(path.is_absolute() and ".." not in path.parts, "absolute unambiguous path required")
    require(not any(node.is_symlink() for node in (path, *path.parents)), "linked path refused")
    return path


def relative(name: str) -> Path:
    """Require a canonical nonempty ordinary relative artifact path."""
    path = Path(name)
    require(bool(name) and not path.is_absolute() and ".." not in path.parts and str(path) == name and name != ".", "invalid artifact path")
    return path


def binding(path: Path) -> dict[str, Any]:
    """Bind a regular file's bytes with bounded memory and stable size."""
    safe(path)
    require(path.is_file(), "regular file required")
    before = path.stat()
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "file changed while hashing")
    return {"sha256": result.hexdigest(), "bytes": before.st_size}


def document(path: Path, expected: str | None = None) -> dict[str, Any]:
    """Read exact byte/content-sealed JSON without nonfinite constants."""
    before = binding(path)
    require(expected is None or before["sha256"] == expected, "document byte hash differs")
    value = json.loads(path.read_text(), parse_constant=lambda token: (_ for _ in ()).throw(InvalidProof(token)))
    require(isinstance(value, dict) and value.get("content_sha256") == digest({k: v for k, v in value.items() if k != "content_sha256"}), "document content seal differs")
    require(binding(path) == before, "document changed during read")
    return value


def sealed(value: dict[str, Any]) -> dict[str, Any]:
    """Seal a new factual mapping; never confer approval."""
    require("content_sha256" not in value, "already sealed")
    return {**value, "content_sha256": digest(value)}


def write_bytes_new(path: Path, payload: bytes) -> None:
    """Exclusively publish closed/fsynced bytes; refuse overwrite."""
    safe(path)
    require(path.parent.is_dir() and not path.exists(), "exclusive destination required")
    descriptor, name = tempfile.mkstemp(prefix=".guard-pending-", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink()


def write_new(path: Path, value: dict[str, Any]) -> None:
    """Publish a sealed factual JSON record, without replacing prior evidence."""
    write_bytes_new(path, (json.dumps(sealed(value), sort_keys=True, indent=2, allow_nan=False) + "\n").encode())


def copy_file(source: Path, destination: Path, expected: str) -> None:
    """Copy exact immutable small source evidence and recheck both ends."""
    require(binding(source)["sha256"] == expected, "copy source differs")
    write_bytes_new(destination, source.read_bytes())
    require(binding(source)["sha256"] == binding(destination)["sha256"] == expected, "copy changed")


def tree(root: Path, *, omit_guard: bool = False) -> dict[str, Any]:
    """Inventory all regular files and directories, including empty/orphan nodes."""
    safe(root)
    require(root.is_dir(), "tree root absent")
    files, directories = {}, []
    for path in sorted(root.rglob("*")):
        name = path.relative_to(root)
        if omit_guard and (name == NAMESPACE or name.is_relative_to(NAMESPACE)):
            continue
        safe(path)
        if path.is_dir():
            directories.append(str(name))
        else:
            require(path.is_file(), "nonregular tree member")
            files[str(name)] = binding(path)
    return {"files": files, "directories": directories}


def utc_now() -> str:
    """Record the actual current UTC time."""
    return datetime.now(UTC).isoformat()


def named_root_review(value: dict[str, Any], *, testing: bool = False) -> None:
    """Require named, dated actual root evidence; synthetic records stay typed."""
    require(isinstance(value.get("reviewer_name"), str) and bool(value["reviewer_name"].strip())
            and value.get("reviewer_role") == "root", "named root review required")
    timestamp = datetime.fromisoformat(value["reviewed_at_utc"])
    require(timestamp.utcoffset() is not None and timestamp.utcoffset().total_seconds() == 0, "UTC review time required")
    require(timestamp <= datetime.now(UTC), "future-dated review cannot authorize a launch")
    require(testing or value.get("test_only") is not True, "synthetic review cannot authorize production")


def request_definition(value: dict[str, Any]) -> str:
    """Hash the acyclic request body before adoption exists."""
    return digest({k: v for k, v in value.items() if k not in {"adoption", "request_body_sha256", "content_sha256"}})


def carrier(value: dict[str, Any]) -> tuple[Path, str]:
    """Validate an explicit path/byte-SHA carrier."""
    require(isinstance(value, dict) and set(value) == {"path", "sha256"}, "path/hash carrier differs")
    require(isinstance(value["sha256"], str) and len(value["sha256"]) == 64 and all(c in "0123456789abcdef" for c in value["sha256"]), "invalid SHA256")
    return safe(Path(value["path"])), value["sha256"]


def runtime(python: Path) -> dict[str, Any]:
    """Verify the executing interpreter and all five numeric-one variables."""
    safe(python)
    require(python.is_file() and python.samefile(Path(sys.executable)), "executing interpreter differs")
    observed = {name: os.environ.get(name) for name in THREADS}
    require(all(value == "1" for value in observed.values()), "all five numeric variables must equal one")
    return {"requested_locked_python": str(python), "observed_executable": sys.executable,
            "numeric_thread_environment": observed, "locked_interpreter_samefile": True}


def pinned_module(path: Path, expected: str, name: str) -> Any:
    """Import only an explicitly pinned private stdlib support module."""
    require(binding(path)["sha256"] == expected and name not in sys.modules, "module pin/alias differs")
    specification = importlib.util.spec_from_file_location(name, path)
    require(specification is not None and specification.loader is not None, "module unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    try:
        specification.loader.exec_module(module)
        require(binding(path)["sha256"] == expected, "module source changed")
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


@contextlib.contextmanager
def original_gates(request: dict[str, Any], resolve: Callable[[Path], Path] = safe,
                   *, read_only: bool = False) -> Iterator[dict[str, Any]]:
    """Use unchanged selection/freeze/pilot predicates through isolated I/O hooks.

    Never call an original main, environment checker, scientific loader, model,
    generator or comparator. All private/public aliases are restored in finally.
    """
    require(not any(name == "src" or name.startswith("src.") for name in sys.modules), "foreign scientific namespace")
    names = ("_reproduction_bound_common", "_guard_old_reproduction", "_guard_old_controller", "fit_common")
    require(not any(name in sys.modules for name in names), "occupied predecessor alias")
    fit = resolve(Path(request["fit_code"]))
    repro = resolve(Path(request["reproduction_code"]))
    try:
        for root, values in ((fit, FIT_PINS), (repro, REPRODUCTION_PINS)):
            for name, expected in values.items():
                require(binding(root / name)["sha256"] == expected, "predecessor source changed")
        common = pinned_module(fit / "fit_common.py", FIT_PINS["fit_common.py"], names[0])
        for name in ("safe", "sha", "read_json", "file_binding", "module_from_pin", "read_original_manifest"):
            function = getattr(common, name)
            setattr(common, name, lambda path, *a, _f=function, **kw: _f(resolve(path), *a, **kw))
        original_verify = common.verify_files
        common.verify_files = lambda root, values: original_verify(resolve(root), values)
        if read_only:
            def forbidden(*_args: Any, **_kwargs: Any) -> None:
                raise InvalidProof("read-only verifier cannot write, claim, copy or execute science")
            for name in ("write_new", "write_bytes_new", "copy_new", "Claim", "verify_original_source"):
                setattr(common, name, forbidden)
        rc = pinned_module(repro / "reproduction_core.py", REPRODUCTION_PINS["reproduction_core.py"], names[1])
        selected, freeze, manifest, inventory, evidence = rc.load_selection(
            resolve(Path(request["selection"]["path"])), request["selection"]["sha256"], repro)
        sys.modules["fit_common"] = common
        controller = pinned_module(fit / "fit_controller.py", FIT_PINS["fit_controller.py"], names[2])
        yield {"selection": selected, "freeze": freeze, "manifest": manifest, "inventory": inventory,
               "selection_evidence": evidence, "common": common, "controller": controller}
    finally:
        for name in names:
            sys.modules.pop(name, None)


def validate_request(value: dict[str, Any], *, resolve: Callable[[Path], Path] = safe,
                     testing: bool = False) -> dict[str, Any]:
    """Verify source/preparation/actual adoption pins before predecessor calls."""
    require(set(value) == REQUEST_KEYS and value["schema_version"] == 1
            and value["status"] == "guarded_corrected_fit_dispatch_request", "request schema differs")
    require(type(value["test_only"]) is bool and (testing or not value["test_only"]), "synthetic request refused")
    require(value["phase"] in {"pilot", "remaining"}, "guard supports pilot/remaining only")
    require(value["limit"] is None or type(value["limit"]) is int and value["limit"] > 0, "positive optional limit")
    require(value["request_body_sha256"] == request_definition(value), "request body digest differs")
    require(set(value["guard_source_sha256"]) == set(SOURCES), "guard source map differs")
    code = resolve(safe(Path(value["guard_code"])))
    for name, expected in value["guard_source_sha256"].items():
        require(binding(code / name)["sha256"] == expected, "guard source differs")
    prep_path, prep_sha = carrier(value["guard_preparation"])
    prep = document(resolve(prep_path), prep_sha)
    require(prep["status"] == "guarded_dispatch_preparation_sealed"
            and prep["runtime_source_sha256"] == value["guard_source_sha256"]
            and (testing or prep.get("test_only") is not True), "guard preparation/source binding differs")
    for name, expected in prep["artifacts"].items():
        require(binding(resolve(prep_path.parent / relative(name))) == expected, "preparation artifact differs")
    require(tree(resolve(prep_path.parent)) == {
        "files": {**prep["artifacts"], prep_path.name: binding(resolve(prep_path))},
        "directories": prep["artifact_directories"]}, "preparation file/directory inventory differs")
    adoption_path, adoption_sha = carrier(value["adoption"])
    adoption = document(resolve(adoption_path), adoption_sha)
    named_root_review(adoption, testing=testing)
    require(adoption["status"] == "guard_dispatch_request_reviewed"
            and adoption["request_body_sha256"] == value["request_body_sha256"], "actual request adoption differs")
    for name in ("freeze", "manifest", "selection", "implementation_review", "scope_review"):
        carrier(value[name])
    for name in ("pilot_review", "resolution_review"):
        if value[name] is not None:
            carrier(value[name])
    require(value["phase"] != "remaining" or value["pilot_review"] is not None, "remaining needs actual pilot review")
    require(value["phase"] != "pilot" or value["pilot_review"] is None, "pilot does not accept remaining review")
    for name in ("fit_code", "reproduction_code", "corrected_run", "locked_python"):
        safe(Path(value[name]))
    output = Path(value["corrected_run"])
    for immutable in (Path(value["guard_code"]), prep_path.parent, Path(value["fit_code"]), Path(value["reproduction_code"]),
                      *(Path(value[name]["path"]) for name in ("freeze", "manifest", "selection", "implementation_review", "scope_review", "adoption"))):
        require(not output.is_relative_to(immutable) and not immutable.is_relative_to(output), "output overlaps authority/source evidence")
    return prep


def validate_authority(request: dict[str, Any], gates: dict[str, Any], *, resolve: Callable[[Path], Path] = safe,
                       testing: bool = False) -> None:
    """Match every frozen selection/path and actual named role before dispatch."""
    selection, freeze, manifest = (gates[name] for name in ("selection", "freeze", "manifest"))
    for name in ("freeze", "manifest"):
        require(selection["paths"][name] == request[name]["path"], "selection/CLI path differs")
    require(selection["correction_freeze_sha256"] == request["freeze"]["sha256"]
            and selection["corrected_manifest_sha256"] == request["manifest"]["sha256"], "selection/CLI hash differs")
    require(selection["paths"]["fit_code"] == request["fit_code"]
            and selection["paths"]["corrected_run"] == request["corrected_run"]
            and selection["paths"]["scope_review"] == request["scope_review"]["path"]
            and selection["scope_review_sha256"] == request["scope_review"]["sha256"], "selection/path scope differs")
    require(freeze["review_bindings"]["implementation"] == request["implementation_review"], "implementation review differs")
    implementation = document(resolve(Path(request["implementation_review"]["path"])), request["implementation_review"]["sha256"])
    named_root_review(implementation, testing=testing)
    require(implementation["dispatch_guard_implementation"] == {
        "source_sha256": request["guard_source_sha256"], "preparation": request["guard_preparation"]}, "pre-freeze guard binding absent/different")
    scope = document(resolve(Path(request["scope_review"]["path"])), request["scope_review"]["sha256"])
    named_root_review(scope, testing=testing)
    require(selection["definition_content_sha256"] == freeze["definition_content_sha256"]
            == manifest["definition_content_sha256"] and selection["input_inventory_sha256"]
            == freeze["input_inventory_sha256"] == manifest["input_inventory_sha256"], "fixed scientific inputs differ")
    if request["phase"] == "remaining":
        path, expected = carrier(request["pilot_review"])
        review = document(resolve(path), expected)
        named_root_review(review, testing=testing)
        gates["controller"].validate_pilot_review(review, manifest, request["manifest"]["sha256"], resolve(Path(request["corrected_run"])))


def fixed_bindings(request: dict[str, Any]) -> dict[str, Any]:
    """Identify immutable introduction scope, independent of phase/limit."""
    keys = ("guard_code", "guard_source_sha256", "guard_preparation", "implementation_review", "scope_review",
            "selection", "freeze", "manifest", "fit_code", "reproduction_code", "corrected_run", "locked_python")
    return {key: request[key] for key in keys}


def immutable_output_roles(request: dict[str, Any], gates: dict[str, Any], request_path: Path,
                           *, include_corrected_run: bool = False) -> list[tuple[str, Path, str]]:
    """Declare every bound immutable file/tree; ordinary file siblings stay usable.

    The controller's intentional selection.corrected_run role is exempt only
    during dispatch. Read-only proof outputs protect that tree as well.
    """
    rows = [(key, safe(Path(request[key])), "tree") for key in ("guard_code", "fit_code", "reproduction_code")]
    rows.extend((("guard_preparation_tree", carrier(request["guard_preparation"])[0].parent, "tree"),
                 ("actual_request", safe(request_path), "file")))
    for key in ("guard_preparation", "implementation_review", "scope_review", "adoption", "selection", "freeze", "manifest", "pilot_review", "resolution_review"):
        if request[key] is not None:
            rows.append((f"request.{key}", carrier(request[key])[0], "file"))
    freeze, selection = gates["freeze"], gates["selection"]
    require(set(freeze["paths"]) <= FREEZE_TREE_ROLES | FREEZE_FILE_ROLES, "unclassified frozen path role")
    for key, value in freeze["paths"].items():
        rows.append((f"freeze.{key}", safe(Path(value)), "tree" if key in FREEZE_TREE_ROLES else "file"))
    arithmetic = safe(Path(freeze["arithmetic_accounting"]["path"]))
    rows.append(("arithmetic_tree", arithmetic.parent, "tree"))
    for key, value in freeze["review_bindings"].items():
        rows.append((f"freeze.review.{key}", carrier(value)[0], "file"))
    require(set(selection["paths"]) <= SELECTION_TREE_ROLES | SELECTION_FILE_ROLES | {"corrected_run"}, "unclassified selection path role")
    for key, value in selection["paths"].items():
        if key == "corrected_run" and not include_corrected_run:
            continue
        rows.append((f"selection.{key}", safe(Path(value)),
                     "tree" if key in SELECTION_TREE_ROLES or key == "corrected_run" else "file"))
    return rows


def protect_output(output: Path, request: dict[str, Any], gates: dict[str, Any], request_path: Path,
                   *, resolve: Callable[[Path], Path] = safe, include_corrected_run: bool = False,
                   extra_files: tuple[Path, ...] = ()) -> list[Path]:
    """Refuse both ancestry directions for all immutable roles before any write.

    Protect the exact bound file, not its parent directory. Check historical and
    mapped receiving paths so neither preserved tree can be changed.
    """
    safe(output)
    protected = []
    rows = immutable_output_roles(request, gates, request_path, include_corrected_run=include_corrected_run)
    for path in extra_files:
        safe(path)
        require(not output.is_relative_to(path) and not path.is_relative_to(output),
                "output overlaps actual verifier request/locations authority")
        protected.append(path)
    for label, historical, _kind in rows:
        for path in {historical, resolve(historical)}:
            require(not output.is_relative_to(path) and not path.is_relative_to(output),
                    f"output overlaps immutable role {label}")
            protected.append(path)
    return protected


def account_cell(value: dict[str, Any], identity: str, request: dict[str, Any], gates: dict[str, Any]) -> None:
    """Require exactly an original reuse or terminal-input account envelope."""
    terminal = value["operation"] == "retain_corrected_input_failure"
    expected = ACCOUNT_BASE_KEYS | ({"original_outcome_pending", "failure_contexts"} if terminal else set())
    if "test_only" in value:
        require(request["test_only"] is True and value["test_only"] is True, "synthetic account envelope refused")
        expected |= {"test_only"}
    require(set(value) == expected, "unclassified or corrected-fit-only account fields")
    entry = next(row for row in gates["inventory"]["entries"] if row["original_cell_id"] == identity)
    require(value["schema_version"] == 1 and value["original_cell_id"] == identity
            and value["evidence_status"] == "post_hoc_rank_conditioned_correction_after_original_failures_known"
            and value["corrected_manifest_sha256"] == request["manifest"]["sha256"]
            and value["correction_freeze_sha256"] == request["freeze"]["sha256"]
            and value["definition_content_sha256"] == gates["freeze"]["definition_content_sha256"]
            and value["input_witness_sha256"] == entry["input_witness_sha256"]
            and value["input_witness_path"] == entry["input_witness_path"], "account identity/witness binding differs")
    require(value["fit_dispatched"] is False and value["newly_executed_fit"] is False and value["artifacts"] == {}
            and type(value["fit_seconds"]) in {int, float} and value["fit_seconds"] == 0.0
            and all(value[key] is False for key in ("programme_complete", "reporting_certified", "release_certified")), "account contains numerical/completion metadata")
    decision = value["decision"]
    require(isinstance(decision, dict) and set(decision) == ACCOUNT_DECISION_KEYS
            and decision["decision_content_sha256"] == digest({key: item for key, item in decision.items() if key != "decision_content_sha256"})
            and decision["schema_version"] == 1 and decision["scope"] == "supplied_evidence_contract_not_actual_byte_verification"
            and decision["original_cell_id"] == identity and decision["model"] == entry["model"]
            and decision["correction_specification_sha256"] == gates["freeze"]["definition_content_sha256"]
            and decision["source_evidence"] == value["source_evidence"] and decision["fit_dispatched"] is False
            and isinstance(value["generator_contexts"], dict) and isinstance(value["original_seed_namespace"], dict)
            and decision["seed_ledger_sha256"] == digest(value["original_seed_namespace"]), "account decision/source grammar differs")
    source = value["source_evidence"]
    if source is not None:
        require(isinstance(source, dict) and source["original_cell_id"] == identity
                and source["status"] in {"complete", "failed", "failed_diagnostics"}, "original source identity/status differs")
    require(decision["original_outcome_available"] is (source is not None)
            and decision["original_status"] == (None if source is None else source["status"]), "original decision outcome metadata differs")
    if terminal:
        require(decision["action"] == "retain_input_failure" and value["scientific_status"] == "not_fit_input_failure"
                and value["original_reference"] is None and type(value["original_outcome_pending"]) is bool
                and isinstance(value["failure_contexts"], dict) and bool(value["failure_contexts"])
                and value["failure_contexts"] == decision["generator_failures"]
                and all(name in value["generator_contexts"] and len(value["generator_contexts"][name]) == 2
                        and value["generator_contexts"][name][0] == status for name, status in value["failure_contexts"].items()),
                "terminal-input account branch differs")
    else:
        require(value["operation"] == decision["action"] == "reuse_original_outcome" and source is not None
                and value["scientific_status"] == source["status"]
                and value["original_reference"] == {"logical_root": "original_extension_run", "path": f"cells/{identity}.json",
                    "sha256": source["cell_byte_sha256"], "cell_content_sha256": source["cell_content_sha256"]},
                "original reuse branch/reference differs")


def account_pass(value: dict[str, Any], checked: dict[str, str], cells: dict[str, dict[str, Any]],
                 request: dict[str, Any], gates: dict[str, Any]) -> set[str]:
    """Verify exact old rows and the cumulative roster of this historical pass.

    Earlier partial rosters are immutable subsets of the final snapshot. Pending
    rows cannot have a cell in that pass, but may acquire a later no-fit outcome.
    """
    expected = ACCOUNT_PASS_KEYS
    if "test_only" in value:
        require(request["test_only"] is True and value["test_only"] is True, "synthetic account pass refused")
        expected |= {"test_only"}
    identities = [entry["original_cell_id"] for entry in gates["inventory"]["entries"]]
    require(set(value) == expected and value["schema_version"] == 1 and value["phase"] == "account"
            and value["corrected_manifest_sha256"] == request["manifest"]["sha256"], "account pass grammar differs")
    records = value["record_sha256"]
    require(isinstance(records, dict) and set(records) <= set(checked)
            and all(checked[identity] == expected_sha for identity, expected_sha in records.items()),
            "historical pass contains foreign/changed/unclassified cells")
    require(type(value["scheduled_logical_cells"]) is int and value["scheduled_logical_cells"] == 1625
            and type(value["retained_logical_outcomes"]) is int and value["retained_logical_outcomes"] == len(records)
            and value["status"] == ("all_logical_outcomes_accounted" if set(records) == set(identities) else "partial_selective_fit_accounting")
            and all(value[key] is False for key in ("all_fits_numerically_verified", "programme_complete", "reporting_certified", "release_certified"))
            and value["pending_gates"] == ["mixed_lineage_deep_verification", "analysis_reporting_qa", "selected_reproduction", "package_restore_replay"],
            "account cumulative grid/count/status/flags differ")
    rows = value["current_pass"]
    require(isinstance(rows, list) and bool(rows) and all(isinstance(row, dict) for row in rows)
            and [row.get("original_cell_id") for row in rows] == identities[:len(rows)],
            "foreign/duplicate/reordered account pass identity")
    for row in rows:
        identity, status = row["original_cell_id"], row["status"]
        if status == "verified_existing_outcome":
            require(set(row) == {"original_cell_id", "status", "record_sha256"}
                    and identity in cells
                    and records.get(identity) == checked.get(identity) == row["record_sha256"], "existing account row is not bound to this pass")
        elif status == "outcome_retained":
            require(set(row) == {"original_cell_id", "status", "operation", "scientific_status", "record_sha256", "fit_dispatched"}
                    and identity in cells and records.get(identity) == checked.get(identity) == row["record_sha256"]
                    and row["fit_dispatched"] is False and row["operation"] == cells[identity]["operation"]
                    and row["scientific_status"] == cells[identity]["scientific_status"], "retained account row is not an exact no-fit outcome")
        else:
            require(status in PENDING_ACCOUNT_STATUSES and set(row) == {"original_cell_id", "status", "fit_dispatched"}
                    and row["fit_dispatched"] is False and identity not in records, "unclassified/bound numerical/pending account row")
    return set(records)


def validate_account_snapshot(root: Path, state: dict[str, Any], request: dict[str, Any], gates: dict[str, Any]) -> None:
    """Independently inspect initial cells/passes through unchanged metadata helpers."""
    require(not attempt_ids(state) and "controller.claim.json" not in state["files"]
            and not any(Path(name).parts[0] == "claims" for name in state["files"])
            and not any(Path(name).parts[0] == "claims" and len(Path(name).parts) > 1 for name in state["directories"]), "prior attempt or active owner blocks introduction")
    require(state["files"].get("manifest.json", {}).get("sha256") == request["manifest"]["sha256"], "account manifest differs")
    allowed = {"manifest.json", "cells", "claims", "attempts", "passes"}
    require({Path(name).parts[0] for name in (*state["files"], *state["directories"])} <= allowed, "unexpected account namespace")
    inventory = {entry["original_cell_id"]: entry for entry in gates["inventory"]["entries"]}
    names = [name for name in state["files"] if Path(name).parts[0] == "cells"]
    require(all(Path(name).parent == Path("cells") and Path(name).name in {f"{identity}.json" for identity in inventory} for name in names)
            and not any(Path(name).parts[0] == "cells" and len(Path(name).parts) > 1 for name in state["directories"]), "foreign cell node")
    checked, cells = {}, {}
    for name in names:
        path = root / name
        require(binding(path) == state["files"][name], "initial account bytes changed")
        value = gates["controller"].verify_record(path, request["manifest"]["sha256"], path.stem)
        account_cell(value, path.stem, request, gates)
        cells[path.stem] = value
        checked[path.stem] = binding(path)["sha256"]
    require(not any(Path(name).parts[0] == "passes" and len(Path(name).parts) > 1 for name in state["directories"]), "unexpected initial pass directory")
    rosters = []
    for name in (name for name in state["files"] if Path(name).parts[0] == "passes"):
        path = root / name
        require(Path(name).parent == Path("passes") and path.suffix == ".json" and binding(path) == state["files"][name], "unexpected/unbound account pass node")
        value = document(path)
        rosters.append(account_pass(value, checked, cells, request, gates))
    require(all(first <= second or second <= first for first in rosters for second in rosters),
            "historical account rosters imply removal/replacement rather than append-only cells")


def account_only(root: Path, request: dict[str, Any], gates: dict[str, Any]) -> dict[str, Any]:
    """Refuse every prior numerical attempt/score, including empty/orphan dirs."""
    state = tree(root, omit_guard=True)
    validate_account_snapshot(root, state, request, gates)
    require(state == tree(root, omit_guard=True), "initial account changed during validation")
    return state


def state_preserved(before: dict[str, Any], after: dict[str, Any]) -> None:
    """Require all earlier directories/files to survive byte-identically."""
    require(set(before["directories"]) <= set(after["directories"])
            and all(after["files"].get(name) == value for name, value in before["files"].items()), "prior state removed/rewritten")


def capture(argv: list[str], directory: Path, label: str, cwd: Path, environment: dict[str, str],
            *, invoke: Callable[..., Any] = subprocess.run, testing: bool = False) -> dict[str, Any]:
    """Capture real subprocess return and exclusive raw streams, even failures.

    Dependency injection is restricted to explicitly typed synthetic tests.
    Interrupted/launch-error receipts have returncode null; never infer success.
    """
    require(testing or invoke is subprocess.run, "unapproved subprocess injection")
    stdout, stderr = directory / f"{label}.stdout.log", directory / f"{label}.stderr.log"
    started = utc_now()
    result, error = None, None
    with stdout.open("xb") as out, stderr.open("xb") as err:
        try:
            result = invoke(argv, cwd=str(cwd), env=environment, stdout=out, stderr=err, check=False)
            require(type(result.returncode) is int, "typed actual subprocess return required")
        except BaseException as exception:
            error = {"type": type(exception).__name__, "message": str(exception)}
        finally:
            for stream in (out, err):
                stream.flush()
                os.fsync(stream.fileno())
    value = {"schema_version": 1, "status": "subprocess_return_captured" if error is None else "subprocess_result_unavailable",
             "test_only_dependency_injection": testing, "argv": argv, "cwd": str(cwd),
             "numeric_thread_environment": {key: environment.get(key) for key in THREADS}, "started_at_utc": started,
             "finished_at_utc": utc_now(), "returncode": None if error is not None else result.returncode,
            "error": error, "raw_streams_partial_or_execution_unavailable": error is not None,
             "raw_streams": {stdout.name: binding(stdout), stderr.name: binding(stderr)}}
    write_new(directory / f"{label}_invocation.json", value)
    return document(directory / f"{label}_invocation.json")


def controller_argv(request: dict[str, Any]) -> list[str]:
    """Build exact unchanged-controller arguments solely from reviewed inputs."""
    argv = [request["locked_python"], "-I", "-B", str(Path(request["fit_code"]) / "fit_controller.py")]
    for option, value in (("freeze", request["freeze"]["path"]), ("freeze-sha256", request["freeze"]["sha256"]),
                          ("manifest", request["manifest"]["path"]), ("manifest-sha256", request["manifest"]["sha256"]),
                          ("output", request["corrected_run"]), ("python", request["locked_python"]), ("phase", request["phase"])):
        argv.extend((f"--{option}", value))
    if request["limit"] is not None:
        argv.extend(("--limit", str(request["limit"])))
    for key in ("pilot_review", "resolution_review"):
        if request[key] is not None:
            flag = key.replace("_", "-")
            argv.extend((f"--{flag}", request[key]["path"], f"--{flag}-sha256", request[key]["sha256"]))
    return argv


def parser(*, gate: bool = False) -> argparse.ArgumentParser:
    """Require explicit actual paths/hashes in addition to the reviewed request."""
    result = argparse.ArgumentParser(description=__doc__)
    for name in ("request", "freeze", "manifest", "selection", "fit-code", "reproduction-code", "output", "python"):
        result.add_argument(f"--{name}", type=Path, required=True)
    for name in ("request", "freeze", "manifest", "selection"):
        result.add_argument(f"--{name}-sha256", required=True)
    result.add_argument("--phase", choices=("pilot", "remaining"), required=True)
    result.add_argument("--limit", type=int)
    for name in ("pilot-review", "resolution-review"):
        result.add_argument(f"--{name}", type=Path)
        result.add_argument(f"--{name}-sha256")
    if gate:
        result.add_argument("--invocation-id", required=True)
        result.add_argument("--launch-sha256", required=True)
    return result


def match_arguments(args: argparse.Namespace, request: dict[str, Any]) -> None:
    """Reject every CLI/request mismatch, including optional reviews and limits."""
    for key in ("freeze", "manifest", "selection"):
        require(str(getattr(args, key)) == request[key]["path"] and getattr(args, f"{key}_sha256") == request[key]["sha256"], "actual path/hash differs")
    for argument, key in (("fit_code", "fit_code"), ("reproduction_code", "reproduction_code"), ("output", "corrected_run"), ("python", "locked_python")):
        require(str(getattr(args, argument)) == request[key], "actual directory/interpreter differs")
    require(args.phase == request["phase"] and args.limit == request["limit"], "actual phase/limit differs")
    for key in ("pilot_review", "resolution_review"):
        item = request[key]
        actual = (getattr(args, key), getattr(args, f"{key}_sha256"))
        require(actual == (None, None) if item is None else actual == (Path(item["path"]), item["sha256"]), "actual optional review differs")


def guard_cli_args(request_path: Path, request_sha: str, request: dict[str, Any]) -> list[str]:
    """Construct child CLI which is independently matched before dispatch."""
    result = ["--request", str(request_path), "--request-sha256", request_sha]
    for name in ("freeze", "manifest", "selection"):
        result.extend((f"--{name}", request[name]["path"], f"--{name}-sha256", request[name]["sha256"]))
    for flag, key in (("fit-code", "fit_code"), ("reproduction-code", "reproduction_code"), ("output", "corrected_run"), ("python", "locked_python"), ("phase", "phase")):
        result.extend((f"--{flag}", request[key]))
    if request["limit"] is not None:
        result.extend(("--limit", str(request["limit"])))
    for key in ("pilot_review", "resolution_review"):
        if request[key] is not None:
            flag = key.replace("_", "-")
            result.extend((f"--{flag}", request[key]["path"], f"--{flag}-sha256", request[key]["sha256"]))
    return result


def copy_authority(directory: Path, request_path: Path, request: dict[str, Any], request_sha: str) -> None:
    """Retain exact request and every new actual review before dispatch."""
    copy_file(request_path, directory / "request.json", request_sha)
    for key in ("adoption", "implementation_review", "scope_review", "pilot_review", "resolution_review"):
        if request[key] is not None:
            source, expected = carrier(request[key])
            copy_file(source, directory / f"{key}.json", expected)


def copy_preparation(namespace: Path, request: dict[str, Any], preparation: dict[str, Any]) -> None:
    """Preserve the complete sealed guard preparation once, without large inputs."""
    target = namespace / "preparation"
    source, expected = carrier(request["guard_preparation"])
    require(not target.exists(), "preparation snapshot already exists")
    target.mkdir()
    for name, item in preparation["artifacts"].items():
        destination = safe(target / relative(name))
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy_file(source.parent / relative(name), destination, item["sha256"])
    copy_file(source, target / "preparation_receipt.json", expected)
    runtime_target = namespace / "runtime_code"
    runtime_target.mkdir()
    for name, expected_source in request["guard_source_sha256"].items():
        copy_file(Path(request["guard_code"]) / name, runtime_target / name, expected_source)


def attempt_ids(state: dict[str, Any]) -> set[str]:
    """Include identities from both files and empty directories."""
    return {Path(name).parts[1] for name in (*state["files"], *state["directories"])
            if len(Path(name).parts) > 1 and Path(name).parts[0] == "attempts"}


def verify_delta(before: dict[str, Any], after: dict[str, Any], request: dict[str, Any], resolve: Callable[[Path], Path],
                 *, complete: bool) -> dict[str, Any]:
    """Associate every newly created attempt with this exact controller invocation."""
    state_preserved(before, after)
    added = sorted(attempt_ids(after) - attempt_ids(before))
    for identity in added:
        name = f"attempts/{identity}/request.json"
        require(name in after["files"], "unclassified new attempt missing request")
        value = document(resolve(Path(request["corrected_run"]) / name), after["files"][name]["sha256"])
        require(value["original_cell_id"] == identity and value["freeze_path"] == request["freeze"]["path"]
                and value["freeze_sha256"] == request["freeze"]["sha256"] and value["manifest_path"] == request["manifest"]["path"]
                and value["manifest_sha256"] == request["manifest"]["sha256"]
                and value["attempt_path"] == str(Path(request["corrected_run"]) / "attempts" / identity)
                and value["locked_python"] == request["locked_python"] and value["implementation_source_sha256"] == FIT_PINS,
                "attempt is not bound to recorded dispatch")
    passes = sorted(name for name in after["files"] if name not in before["files"] and Path(name).parent == Path("passes"))
    if complete:
        require(len(passes) == 1, "rc0 controller must retain one actual direct pass")
        value = document(resolve(Path(request["corrected_run"]) / passes[0]), after["files"][passes[0]]["sha256"])
        require(value["phase"] == request["phase"] and value["corrected_manifest_sha256"] == request["manifest"]["sha256"], "actual controller pass differs")
        require({identity: item["sha256"] for name, item in after["files"].items() if Path(name).parent == Path("cells")
                 for identity in [Path(name).stem]} == value["record_sha256"], "cumulative pass/cell binding differs")
    return {"new_attempt_ids": added, "new_direct_passes": passes}


class TrustedLocations:
    """Read-only explicit mappings authenticated by separately pinned root review.

    Whole-tree inventories include empty directories. JSON/argv stay historical;
    only I/O paths resolve. No discovery, mutable map approval or aliases.
    """

    def __init__(self, path: Path, expected: str, review_sha: str, request_sha: str,
                 *, testing: bool = False) -> None:
        value = document(path, expected)
        self.value = value
        self.mode = value["mode"]
        require(self.mode in {"source", "receiving"}, "explicit source/receiving mode required")
        self.fresh_roles = {name: safe(Path(root)) for name, root in value["fresh_payload_roles"].items()}
        require(self.mode != "receiving" or self.fresh_roles and all(root.is_dir() for root in self.fresh_roles.values()), "actual fresh receiving role roots required")
        require(self.mode != "source" or not self.fresh_roles, "source mode cannot claim fresh receiving roles")
        self.maps: list[tuple[Path, Path, str]] = []
        self.roots: dict[Path, dict[str, Any]] = {}
        self.files: dict[Path, dict[str, Any]] = {}
        require(value["status"] == "guard_proof_locations_proposed" and value["schema_version"] == 1
                and value["request_sha256"] == request_sha, "location input scope differs")
        review_path, actual_review_sha = carrier(value["authority"])
        require(actual_review_sha == review_sha, "external trusted location-review SHA required")
        review = document(review_path, review_sha)
        named_root_review(review, testing=testing)
        definition = digest({key: item for key, item in value.items() if key not in {"authority", "content_sha256"}})
        require(review["status"] == "guard_proof_locations_reviewed" and review["locations_definition_sha256"] == definition
                and review["request_sha256"] == request_sha and review["verification_mode"] == self.mode
                and review["fresh_payload_roles"] == value["fresh_payload_roles"], "actual location review does not bind this map/mode")
        require(value["transport_evidence"], "separate actual source/stage/archive evidence required")
        if self.mode == "receiving":
            require({item["role"] for item in value["transport_evidence"]} >= {"actual_stage", "actual_restore"}, "actual external stage and fresh restore authorities required")
        for item in value["transport_evidence"]:
            require(binding(safe(Path(item["path"]))) == item["binding"], "transport/source review bytes differ")
        for item in value["immutable_roots"]:
            old, new = safe(Path(item["historical"])), safe(Path(item["restored"]))
            self.require_role(old, new, item["payload_role"])
            require(new not in self.roots and set(item["inventory"]) == {"files", "directories"}, "exact root/dir roster required")
            self.roots[new] = item["inventory"]
            self.maps.append((old, new, "directory"))
            for name, evidence in item["inventory"]["files"].items():
                target = new / relative(name)
                require(target not in self.files or self.files[target] == evidence, "conflicting file inventory")
                self.files[target] = evidence
            require(item["inventory"]["directories"] == sorted(set(item["inventory"]["directories"])), "directory roster duplicated/unsorted")
            for name in item["inventory"]["directories"]:
                relative(name)
        for item in value["immutable_files"]:
            old, new = safe(Path(item["historical"])), safe(Path(item["restored"]))
            self.require_role(old, new, item["payload_role"])
            require(new not in self.files or self.files[new] == item["binding"], "conflicting exact file mapping")
            self.files[new] = item["binding"]
            self.maps.append((old, new, "file"))
        require(self.maps and self.roots, "explicit full-tree mappings required")
        for old, new, kind in self.maps:
            if self.mode == "receiving":
                require(all(not old.is_relative_to(root) and not root.is_relative_to(old) for root in self.fresh_roles.values()), "historical domain overlaps fresh payload")
            require(sum(first == old for first, _, _ in self.maps) == 1, "duplicate historical map")
            for other, target, other_kind in self.maps:
                if other == old:
                    continue
                if other.is_relative_to(old):
                    require(kind == "directory" and target == new / other.relative_to(old), "ambiguous nested mapping")
                if target.is_relative_to(new):
                    require(kind == "directory" and other == old / target.relative_to(new), "receiving alias")
                require(other_kind in {"file", "directory"}, "mapping kind differs")
        if self.mode == "receiving":
            proof_path, proof_sha = carrier(value["source_guard_proof"])
            source_proof = document(self.resolve(proof_path), proof_sha)
            require(source_proof["status"] == "retained_guard_proof_semantically_verified"
                    and source_proof["verification_mode"] == "source" and source_proof["request_sha256"] == request_sha
                    and source_proof["successful_guard_coverage"] is True
                    and (testing or source_proof["test_only_dependency_injection"] is False), "actual prior source semantic proof required")
        else:
            require(value["source_guard_proof"] is None, "source proof must not bind its future receipt")

    def require_role(self, old: Path, new: Path, role: str | None) -> None:
        """Refuse same-Mac identity/fallback reads in fresh receiving mode."""
        if self.mode == "receiving":
            require(role in self.fresh_roles and new.is_relative_to(self.fresh_roles[role])
                    and new != old and not old.is_relative_to(new) and not new.is_relative_to(old), "receiving mapping must use its freshly restored role, never history")
        else:
            require(role is None, "source mapping cannot label a fresh receiving role")

    def resolve(self, path: Path) -> Path:
        """Resolve only a declared logical path or already inventoried physical path."""
        safe(path)
        candidates = [new / path.relative_to(old) if kind == "directory" else new
                      for old, new, kind in self.maps if path == old or kind == "directory" and path.is_relative_to(old)]
        if candidates:
            require(all(item == candidates[0] for item in candidates), "ambiguous map")
            path = candidates[0]
        elif self.mode == "receiving":
            require(path in self.files or path in self.roots or any(path.is_relative_to(root) for root in self.roots), "missing receiving relocation; historical fallback refused")
        safe(path)
        require(path in self.files or path in self.roots or any(path.is_relative_to(root) for root in self.roots), "untrusted/unmapped read")
        if path.is_file():
            require(path in self.files, "uninventoried physical file")
        return path

    def historical_read(self, path: Path) -> Path:
        """Require an explicit historical-role tuple, never physical-path fallback."""
        require(any(path == old or kind == "directory" and path.is_relative_to(old) for old, _, kind in self.maps), "missing declared historical mapping")
        return self.resolve(path)

    def verify(self) -> str:
        """Verify every byte and directory before and after the read-only proof."""
        for root, expected in self.roots.items():
            require(tree(root) == expected, "missing/extra/changed/linked tree or empty directory")
        for path, expected in self.files.items():
            require(binding(path) == expected, "immutable file differs")
        return digest({"roots": {str(path): row for path, row in self.roots.items()},
                       "files": {str(path): row for path, row in self.files.items()}})


def verify_capture(value: dict[str, Any], directory: Path, label: str, argv: list[str], cwd: str,
                   *, testing: bool = False) -> None:
    """Check complete genuine reviewed-capturer evidence; pass/rc alone is insufficient."""
    require(value["status"] == "subprocess_return_captured" and value["error"] is None
            and type(value["returncode"]) is int and value["argv"] == argv and value["cwd"] == cwd
            and value["raw_streams_partial_or_execution_unavailable"] is False
            and (testing or value["test_only_dependency_injection"] is False), "complete actual captured return required")
    require(value["numeric_thread_environment"] == dict.fromkeys(THREADS, "1"), "historical numeric environment differs")
    require(datetime.fromisoformat(value["started_at_utc"]) <= datetime.fromisoformat(value["finished_at_utc"]), "capture time order differs")
    require(set(value["raw_streams"]) == {f"{label}.stdout.log", f"{label}.stderr.log"}, "exact raw stream roster required")
    for name, expected in value["raw_streams"].items():
        require(binding(directory / name) == expected, "raw captured stream changed")


def verify_observed_runtime(value: dict[str, Any], request: dict[str, Any]) -> None:
    """Bind historical actual-runtime metadata without replacing it at receiving."""
    require(value["requested_locked_python"] == request["locked_python"]
            and isinstance(value["observed_executable"], str) and bool(value["observed_executable"])
            and value["locked_interpreter_samefile"] is True
            and value["numeric_thread_environment"] == dict.fromkeys(THREADS, "1"), "captured actual runtime differs")


def history(root: Path, request: dict[str, Any], *, resolve: Callable[[Path], Path] = safe,
            gates_factory: Callable[..., Any] = original_gates, testing: bool = False) -> dict[str, Any]:
    """Semantically verify whole immutable introduction/invocation/failure history.

    Read only. A failed closed no-dispatch invocation is retained; an interrupted
    parent return or unclassified new attempt cannot become complete proof.
    """
    require(testing or gates_factory is original_gates, "unapproved gate injection")
    namespace = root / NAMESPACE
    introduction = document(namespace / "introduction.json")
    require(introduction["status"] == "guard_introduced_before_controller_launch"
            and introduction["fixed_bindings"] == fixed_bindings(request)
            and (testing or introduction["test_only_dependency_injection"] is False), "first introduction differs")
    initial_path = resolve(Path(introduction["initial_request_path"]))
    initial = document(initial_path, introduction["initial_request_sha256"])
    require(initial["adoption"] == introduction["initial_adoption"] and fixed_bindings(initial) == fixed_bindings(request), "initial request/adoption identity differs")
    snapshot = introduction["account_snapshot"]
    require(not attempt_ids(snapshot) and "controller.claim.json" not in snapshot["files"]
            and not any(Path(name).parts[0] == "claims" for name in snapshot["files"])
            and not any(Path(name).parts[0] == "claims" and len(Path(name).parts) > 1 for name in snapshot["directories"]), "initial account snapshot contains numerical/owner node")
    with gates_factory(initial, resolve, read_only=True) as gates:
        validate_authority(initial, gates, resolve=resolve, testing=testing)
        validate_account_snapshot(root, snapshot, initial, gates)
    require((namespace / "invocations").is_dir(), "capture history absent")
    rows = []
    expected_files = {"introduction.json"}
    prep_path, prep_sha = carrier(request["guard_preparation"])
    preparation = document(resolve(prep_path), prep_sha)
    retained_preparation = namespace / "preparation"
    require(document(retained_preparation / "preparation_receipt.json", prep_sha) == preparation, "preserved preparation differs")
    for name, expected in preparation["artifacts"].items():
        require(binding(retained_preparation / relative(name)) == expected, "retained preparation byte differs")
        expected_files.add(f"preparation/{name}")
    expected_files.add("preparation/preparation_receipt.json")
    for name, expected in request["guard_source_sha256"].items():
        require(binding(namespace / "runtime_code" / name)["sha256"] == expected, "preserved runtime source differs")
        expected_files.add(f"runtime_code/{name}")
    for directory in (namespace / "invocations").iterdir():
        require(directory.is_dir() and len(directory.name) == 32 and all(c in "0123456789abcdef" for c in directory.name), "invalid invocation tree")
        launch = document(directory / "launcher_launch.json")
        rows.append((launch["sequence_index"], directory, launch))
    rows.sort(key=lambda item: item[0])
    require(rows and [index for index, _, _ in rows] == list(range(1, len(rows) + 1)), "missing/duplicate history order")
    previous = snapshot
    tail = None
    owned_attempts: set[str] = set()
    failed = 0
    for index, directory, launch in rows:
        require(launch["status"] == "guard_launch_prepared"
                and (testing or launch["test_only_dependency_injection"] is False), "actual owned launch required")
        require(launch["invocation_id"] == directory.name and launch["previous_guard_capture_sha256"] == tail, "capture predecessor chain differs")
        require(index != 1 or directory.name == introduction["initial_invocation_id"], "first introduction invocation differs")
        current = document(directory / "request.json", launch["request_sha256"])
        verify_observed_runtime(launch["runtime"], current)
        require(fixed_bindings(current) == fixed_bindings(request), "resumed scope changed")
        validate_request(current, resolve=resolve, testing=testing)
        with gates_factory(current, resolve, read_only=True) as gates:
            validate_authority(current, gates, resolve=resolve, testing=testing)
        for key in ("adoption", "implementation_review", "scope_review", "pilot_review", "resolution_review"):
            if current[key] is not None:
                require(binding(directory / f"{key}.json")["sha256"] == current[key]["sha256"], "retained actual authority copy differs")
        source_path = Path(launch["request_path"])
        require(document(resolve(source_path), launch["request_sha256"]) == current
                and launch["guard_source_sha256"] == current["guard_source_sha256"], "source request/capture source identity differs")
        prefix = [current["locked_python"], "-I", "-B", str(Path(current["guard_code"]) / "guard_fit_dispatch.py"),
                  *guard_cli_args(source_path, launch["request_sha256"], current), "--invocation-id", directory.name]
        require(launch["guard_argv_prefix"] == prefix, "historical guard argv prefix differs")
        guard_capture = document(directory / "guard_invocation.json")
        verify_capture(guard_capture, directory, "guard", [*prefix, "--launch-sha256", binding(directory / "launcher_launch.json")["sha256"]], current["guard_code"], testing=testing)
        before = document(directory / "launcher_before.json")["state"]
        after = document(directory / "launcher_after.json")["state"]
        require(before == previous, "root changed outside recorded controller history")
        result = document(directory / "launcher_result.json")
        require(result["guard_invocation_sha256"] == binding(directory / "guard_invocation.json")["sha256"]
                and result["before_sha256"] == binding(directory / "launcher_before.json")["sha256"]
                and result["after_sha256"] == binding(directory / "launcher_after.json")["sha256"]
                and result["request_sha256"] == launch["request_sha256"]
                and result["guard_returncode"] == guard_capture["returncode"]
                and (testing or result["test_only_dependency_injection"] is False), "actual parent result/raw binding differs")
        require(datetime.fromisoformat(launch["prepared_at_utc"]) <= datetime.fromisoformat(guard_capture["started_at_utc"]), "owned prelaunch order differs")
        for key in ("adoption", "scope_review"):
            review = document(directory / f"{key}.json", current[key]["sha256"])
            require(datetime.fromisoformat(review["reviewed_at_utc"]) <= datetime.fromisoformat(launch["prepared_at_utc"]), "prospective root review was dated after launch")
        expected_names = {"request.json", "adoption.json", "implementation_review.json", "scope_review.json",
                          "launcher_before.json", "launcher_launch.json", "guard.stdout.log", "guard.stderr.log",
                          "guard_invocation.json", "launcher_after.json", "launcher_result.json"}
        expected_names.update(f"{key}.json" for key in ("pilot_review", "resolution_review") if current[key] is not None)
        if (directory / "controller_launch.json").exists():
            controller_launch = document(directory / "controller_launch.json")
            controller_capture = document(directory / "controller_invocation.json")
            verify_observed_runtime(controller_launch["runtime"], current)
            verify_capture(controller_capture, directory, "controller", controller_argv(current), current["fit_code"], testing=testing)
            require(document(directory / "before.json")["state"] == before
                    and document(directory / "after.json")["state"] == after
                    and controller_launch["introduction_sha256"] == binding(namespace / "introduction.json")["sha256"]
                    and controller_launch["request_sha256"] == launch["request_sha256"]
                    and controller_launch["argv"] == controller_argv(current)
                    and controller_launch["fit_source_sha256"] == FIT_PINS
                    and controller_launch["guard_source_sha256"] == current["guard_source_sha256"]
                    and controller_launch["before_sha256"] == binding(directory / "before.json")["sha256"], "prelaunch causal source/request proof differs")
            require(datetime.fromisoformat(introduction["introduced_at_utc"]) <= datetime.fromisoformat(controller_launch["prepared_at_utc"])
                    <= datetime.fromisoformat(controller_capture["started_at_utc"]), "introduction was not recorded before launch")
            dispatch_result = document(directory / "dispatch_result.json")
            require(dispatch_result["controller_returncode"] == controller_capture["returncode"]
                    and dispatch_result["controller_invocation_sha256"] == binding(directory / "controller_invocation.json")["sha256"]
                    and dispatch_result["before_sha256"] == binding(directory / "before.json")["sha256"]
                    and dispatch_result["after_sha256"] == binding(directory / "after.json")["sha256"], "actual dispatch result differs")
            delta = verify_delta(before, after, current, resolve, complete=controller_capture["returncode"] == 0)
            require(dispatch_result["delta"] == delta and not owned_attempts.intersection(delta["new_attempt_ids"]), "duplicate or false attempt ownership")
            owned_attempts.update(delta["new_attempt_ids"])
            require(guard_capture["returncode"] != 0 or controller_capture["returncode"] == 0, "guard success despite failed controller")
            expected_names.update({"before.json", "after.json", "controller_launch.json", "controller.stdout.log",
                                   "controller.stderr.log", "controller_invocation.json", "dispatch_result.json"})
        else:
            require(guard_capture["returncode"] != 0 and before == after, "unrecorded numerical changes or false no-dispatch success")
        failed += guard_capture["returncode"] != 0
        require(set(path.name for path in directory.iterdir()) == expected_names
                and all(path.is_file() for path in directory.iterdir()), "unclassified extra/partial invocation files or dirs")
        expected_files.update(f"invocations/{directory.name}/{name}" for name in expected_names)
        previous = after
        tail = binding(directory / "guard_invocation.json")["sha256"]
    current_state = tree(root, omit_guard=True)
    require(current_state == previous and attempt_ids(current_state) == owned_attempts, "final root/attempt coverage differs")
    actual = tree(namespace)
    require(set(actual["files"]) == expected_files, "unretained/unclassified guard files")
    expected_directories = {"preparation", "runtime_code", "invocations", *(f"invocations/{directory.name}" for _, directory, _ in rows)}
    for name in expected_files:
        parent = Path(name).parent
        while str(parent) != ".":
            expected_directories.add(str(parent))
            parent = parent.parent
    require(set(actual["directories"]) == expected_directories, "extra/missing empty guard directory")
    require(not (namespace / "guard.claim.json").exists(), "guard still owned or interrupted")
    return {"invocations": len(rows), "failed_closed_invocations": failed, "successful_dispatch_invocations": len(rows) - failed,
            "successful_guard_coverage": failed == 0, "owned_attempt_ids": sorted(owned_attempts),
             "last_guard_capture_sha256": tail, "last_state": previous, "introduction_sha256": binding(namespace / "introduction.json")["sha256"]}


def validate_historical_roles(request: dict[str, Any], locations: TrustedLocations) -> None:
    """Require all immutable request/freeze/selection reads to have declared roles."""
    for key in ("guard_code", "fit_code", "reproduction_code", "corrected_run"):
        locations.historical_read(Path(request[key]))
    for key in ("guard_preparation", "implementation_review", "scope_review", "adoption", "selection", "freeze", "manifest", "pilot_review", "resolution_review"):
        if request[key] is not None:
            locations.historical_read(Path(request[key]["path"]))
    freeze = document(locations.historical_read(Path(request["freeze"]["path"])), request["freeze"]["sha256"])
    for value in freeze["paths"].values():
        locations.historical_read(Path(value))
    locations.historical_read(Path(freeze["arithmetic_accounting"]["path"]))
    for value in freeze["review_bindings"].values():
        locations.historical_read(Path(value["path"]))
    selection = document(locations.historical_read(Path(request["selection"]["path"])), request["selection"]["sha256"])
    for value in selection["paths"].values():
        locations.historical_read(Path(value))


def verify_guarded_dispatch_proof(request_path: Path, request_sha256: str, locations_path: Path,
                                 locations_sha256: str, location_review_sha256: str, output: Path,
                                 *, gates_factory: Callable[..., Any] = original_gates, testing: bool = False,
                                 executing_code_directory: Path | None = None) -> dict[str, Any]:
    """Verify retained source/receiving proof into a new external factual receipt.

    No dispatcher, original main, environment checker or scientific predicate is
    executed. Immutable historical bytes/path strings are never rewritten.
    """
    locations = TrustedLocations(locations_path, locations_sha256, location_review_sha256, request_sha256, testing=testing)
    safe(output)
    require(not output.exists() and output.parent.is_dir(), "new external output required")
    for immutable in (*locations.roots, *locations.files):
        require(not output.is_relative_to(immutable) and not immutable.is_relative_to(output), "output overlaps preserved evidence")
    before = locations.verify()
    request = document(locations.resolve(request_path), request_sha256)
    validate_historical_roles(request, locations)
    executing = executing_code_directory or Path(__file__).absolute().parent
    require(testing or safe(executing) == locations.historical_read(Path(request["guard_code"])), "actual verifier must run from its declared source/restored guard role")
    validate_request(request, resolve=locations.resolve, testing=testing)
    with gates_factory(request, locations.resolve, read_only=True) as gates:
        validate_authority(request, gates, resolve=locations.resolve, testing=testing)
        protect_output(output, request, gates, request_path, resolve=locations.resolve, include_corrected_run=True,
                       extra_files=(locations_path, carrier(locations.value["authority"])[0]))
    result = history(locations.resolve(Path(request["corrected_run"])), request, resolve=locations.resolve,
                     gates_factory=gates_factory, testing=testing)
    require(locations.verify() == before, "evidence changed during read-only semantic verification")
    output.mkdir()
    value = {"schema_version": 1, "status": "retained_guard_proof_semantically_verified" if result["successful_guard_coverage"] else "retained_guard_failure_history_accounted",
             "test_only_dependency_injection": testing, "request_sha256": request_sha256,
             "locations_sha256": locations_sha256, "actual_location_review_sha256": location_review_sha256,
             "verification_mode": locations.mode,
             "successful_guard_coverage": result["successful_guard_coverage"],
             "guard_source_sha256": request["guard_source_sha256"], "immutable_inventory_sha256": before,
             "history": {key: item for key, item in result.items() if key != "last_state"},
             "historical_json_or_argv_rewritten": False, "preserved_evidence_modified": False,
             "new_controller_or_scientific_calls": False, "scientific_completion_certified": False, "programme_complete": False}
    write_new(output / "receipt.json", value)
    return document(output / "receipt.json")


def dispatch(args: argparse.Namespace, gates: dict[str, Any], *, invoke: Callable[..., Any] = subprocess.run,
             testing: bool = False) -> dict[str, Any]:
    """Introduce/recheck prospective evidence, then capture the old controller."""
    request = document(args.request, args.request_sha256)
    validate_request(request, testing=testing)
    match_arguments(args, request)
    observed = runtime(args.python)
    validate_authority(request, gates, testing=testing)
    root = safe(args.output)
    protect_output(root, request, gates, args.request)
    namespace = root / NAMESPACE
    require(len(args.invocation_id) == 32 and all(c in "0123456789abcdef" for c in args.invocation_id), "unsafe invocation identity")
    directory = namespace / "invocations" / args.invocation_id
    require(directory.is_dir(), "owned invocation reservation absent")
    launch = document(directory / "launcher_launch.json", args.launch_sha256)
    require(launch["request_sha256"] == args.request_sha256 and launch["invocation_id"] == args.invocation_id
            and launch["guard_source_sha256"] == request["guard_source_sha256"] and launch["guard_argv_prefix"] ==
            [request["locked_python"], "-I", "-B", str(Path(request["guard_code"]) / "guard_fit_dispatch.py"),
             *guard_cli_args(args.request, args.request_sha256, request), "--invocation-id", args.invocation_id],
             "actual reserved guard launch differs")
    claim = document(namespace / "guard.claim.json")
    require(claim["request_sha256"] == args.request_sha256 and claim["invocation_id"] == args.invocation_id, "guard reservation differs")
    introduction_path = namespace / "introduction.json"
    if not introduction_path.exists():
        before = account_only(root, request, gates)
        require(before == tree(root, omit_guard=True), "account state changed before introduction")
        write_new(introduction_path, {"schema_version": 1, "status": "guard_introduced_before_controller_launch",
                  "test_only_dependency_injection": testing, "fixed_bindings": fixed_bindings(request),
                  "initial_request_path": str(args.request), "initial_request_sha256": args.request_sha256,
                  "initial_adoption": request["adoption"], "initial_invocation_id": args.invocation_id,
                  "introduced_at_utc": utc_now(), "account_snapshot": before})
    introduction = document(introduction_path)
    require(introduction["fixed_bindings"] == fixed_bindings(request), "immutable introduction scope changed")
    before = tree(root, omit_guard=True)
    require(document(directory / "launcher_before.json")["state"] == before,
            "root changed between owned launcher validation and guard dispatch")
    require(not any((root / "claims").iterdir()) and not (root / "controller.claim.json").exists(), "original controller/cell owner remains")
    write_new(directory / "before.json", {"schema_version": 1, "state": before})
    require(tree(root, omit_guard=True) == before, "state changed immediately before dispatch")
    argv = controller_argv(request)
    write_new(directory / "controller_launch.json", {"schema_version": 1, "status": "controller_launch_prepared",
              "request_sha256": args.request_sha256, "introduction_sha256": binding(introduction_path)["sha256"],
              "guard_source_sha256": request["guard_source_sha256"], "fit_source_sha256": FIT_PINS,
              "argv": argv, "cwd": request["fit_code"], "runtime": observed,
              "before_sha256": binding(directory / "before.json")["sha256"], "prepared_at_utc": utc_now(),
              "test_only_dependency_injection": testing})
    require(tree(root, omit_guard=True) == before, "state changed after prelaunch proof")
    result = capture(argv, directory, "controller", Path(request["fit_code"]), dict(os.environ), invoke=invoke, testing=testing)
    after = tree(root, omit_guard=True)
    write_new(directory / "after.json", {"schema_version": 1, "state": after})
    delta = verify_delta(before, after, request, safe, complete=result["returncode"] == 0)
    write_new(directory / "dispatch_result.json", {"schema_version": 1, "status": "guarded_dispatch_return_recorded",
              "test_only_dependency_injection": testing, "request_sha256": args.request_sha256,
              "introduction_sha256": binding(introduction_path)["sha256"], "controller_returncode": result["returncode"],
              "before_sha256": binding(directory / "before.json")["sha256"], "after_sha256": binding(directory / "after.json")["sha256"],
              "controller_invocation_sha256": binding(directory / "controller_invocation.json")["sha256"], "delta": delta,
              "scientific_completion_certified": False, "programme_complete": False})
    validate_request(request, testing=testing)
    validate_authority(request, gates, testing=testing)
    require(tree(root, omit_guard=True) == after, "root changed after controller capture")
    return document(directory / "dispatch_result.json")


def main() -> None:
    """Execute only an actual independently approved guarded child request."""
    args = parser(gate=True).parse_args()
    require(sys.flags.isolated == 1 and sys.dont_write_bytecode, "guard child requires -I -B")
    request = document(args.request, args.request_sha256)
    require(safe(Path(__file__).absolute()).parent == Path(request["guard_code"]), "executing guard directory differs")
    validate_request(request)
    match_arguments(args, request)
    require(sys.argv == [str(Path(request["guard_code"]) / "guard_fit_dispatch.py"),
            *guard_cli_args(args.request, args.request_sha256, request), "--invocation-id", args.invocation_id,
            "--launch-sha256", args.launch_sha256], "actual owned child argv differs")
    with original_gates(request) as gates:
        result = dispatch(args, gates)
    code = result["controller_returncode"]
    if code != 0:
        raise SystemExit(code if type(code) is int and code > 0 else 1)
    print(json.dumps({"status": "guarded_dispatch_capture_completed", "scientific_completion_certified": False}, sort_keys=True))


if __name__ == "__main__":
    main()
