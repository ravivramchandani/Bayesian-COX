"""Read-only receiving checks for the sealed selected reproduction programme.

Only explicit receiving mappings affect I/O. Historical documents, selected
identities, original producer proofs and scientific exclusions stay unchanged.
No execution/resume controller or generator/model entry point is dispatched.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

V1_PINS = {
    "reproduction_core.py": "fa43d4c75f231a59f12adb73b312627744b6c40dd0a97c002016ed4cba597cb5",
    "run_reproduction.py": "86eed8bd3af2f5ddab9b1bf354e7251518cfb64932da778d05d63a937209829c",
    "terminal_replay_child.py": "830e866d38eb65f9742cb9e7e48212f532ee1d1bfd9eeb7791ca89dbe3dacc61",
}
V1_TEST_SHA = "516282c3b79a500fa1d1f3bd692f9a9021c321be2ac36d7bd7269e856e9a7bac"
V1_RECEIPT_SHA = "43f2dba209a4d068df7122a3be956d295f7810601272b271fa996ad5a27aa95b"
FIT_COMMON_SHA = "b17f378ba77ea3ae5ba25c836e963a1a0160556465b25745462f648e325d1f11"
NUMERIC_VARIABLES = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
                     "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
OWN_SOURCES = ("receiving_core.py", "verify_restored_reproduction.py")
FINAL_STATUSES = {
    "reused_verified_original_numerical_reproduction", "new_corrected_numerical_reproduction",
    "terminal_no_fit_recipe_replay",
}


class InvalidEvidence(ValueError):
    """An unsafe, missing, changed or unresolved receiving binding."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise InvalidEvidence(message)


def absolute(path: Path) -> Path:
    require(path.is_absolute() and ".." not in path.parts, "explicit absolute path required")
    require(not any(part.is_symlink() for part in (path, *path.parents)), "symlinked receiving evidence refused")
    return path


def relative(name: str) -> Path:
    path = Path(name)
    require(bool(name) and not path.is_absolute() and ".." not in path.parts
            and str(path) == name and name != ".", "ordinary canonical relative file required")
    return path


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def binding(path: Path) -> dict[str, Any]:
    absolute(path)
    require(path.is_file(), "regular evidence file required")
    hashed = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hashed.update(block)
    return {"sha256": hashed.hexdigest(), "bytes": path.stat().st_size}


def document(path: Path, expected: str | None = None, *, field: str = "content_sha256") -> dict[str, Any]:
    before = binding(path)
    require(expected is None or before["sha256"] == expected, "document byte pin differs")
    value = json.loads(path.read_text(), parse_constant=lambda text: (_ for _ in ()).throw(InvalidEvidence(text)))
    require(isinstance(value, dict) and value.get(field) == digest({key: item for key, item in value.items() if key != field}),
            "document content seal differs")
    require(binding(path) == before, "document changed while read")
    return value


def seal(value: dict[str, Any]) -> dict[str, Any]:
    require("content_sha256" not in value, "already sealed")
    return {**value, "content_sha256": digest(value)}


def write_new(path: Path, value: dict[str, Any]) -> None:
    absolute(path)
    require(path.parent.is_dir(), "existing external output parent required")
    with path.open("xb") as stream:
        stream.write((json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode())
        stream.flush()
        os.fsync(stream.fileno())


def runtime(python: Path, environment: dict[str, str] | None = None) -> dict[str, Any]:
    """Validate actual receiving process before evidence/source imports.

    An explicit interpreter symlink alias is allowed only for this argument;
    immutable evidence and source paths still prohibit symlinks.
    """
    require(python.is_absolute() and ".." not in python.parts and python.is_file()
            and python.samefile(Path(sys.executable)), "current receiving interpreter differs")
    supplied = os.environ if environment is None else environment
    observed = {name: supplied.get(name) for name in NUMERIC_VARIABLES}
    require(all(value == "1" for value in observed.values()), "all five numeric thread variables must already equal one")
    return {"observed_executable": sys.executable, "requested_locked_python": str(python),
            "locked_interpreter_samefile": True, "numeric_thread_environment": observed}


class Resolver:
    """An explicit, hash-preserving historical-to-receiving I/O mapping.

    Every receiving file must belong to an exact trusted tree inventory or an
    explicitly pinned file. Directory mappings cannot invent unlisted bytes.
    Nested mappings are permitted only when both mappings resolve identically.
    """

    def __init__(self, value: dict[str, Any], owned_output: Path) -> None:
        self.output = absolute(owned_output)
        self.maps: list[tuple[Path, Path, str]] = []
        self.roots: dict[Path, dict[str, Any]] = {}
        self.files: dict[Path, dict[str, Any]] = {}
        for item in value["immutable_roots"]:
            root = absolute(Path(item["root"]))
            require(root.is_dir() and root not in self.roots, "duplicate/missing immutable root")
            artifacts = item["artifacts"]
            require(isinstance(artifacts, dict), "exact immutable tree inventory required")
            for name, expected in artifacts.items():
                path = absolute(root / relative(name))
                require(path not in self.files or self.files[path] == expected, "conflicting receiving file pin")
                self.files[path] = expected
            self.roots[root] = artifacts
        for item in value["immutable_files"]:
            path = absolute(Path(item["path"]))
            require(path not in self.files or self.files[path] == item["binding"], "conflicting receiving file pin")
            self.files[path] = item["binding"]
        require(self.roots and self.files, "trusted immutable inventories required")
        for item in value["path_map"]:
            historical = Path(item["historical"])
            require(historical.is_absolute() and ".." not in historical.parts, "historical path must be absolute and unambiguous")
            restored = absolute(Path(item["restored"]))
            kind = item["kind"]
            require(kind in {"directory", "file"}, "mapping kind differs")
            require((kind == "directory" and restored in self.roots)
                    or (kind == "file" and restored in self.files), "mapping destination is not exactly inventoried")
            require(all(historical != old for old, _, _ in self.maps), "duplicate historical mapping")
            self.maps.append((historical, restored, kind))
        require(self.maps, "explicit receiving mappings required")
        for first, target, kind in self.maps:
            for second, other, other_kind in self.maps:
                if first == second:
                    continue
                if second.is_relative_to(first):
                    require(kind == "directory" and other == target / second.relative_to(first),
                            "ambiguous nested historical mapping")
                if other.is_relative_to(target):
                    require(kind == "directory" and second == first / other.relative_to(target),
                            "ambiguous receiving aliases")
                require(other_kind == "directory" or other in self.files, "unbound receiving alias")
        self.maps.sort(key=lambda row: len(row[0].parts), reverse=True)
        for root in (*self.roots, *self.files):
            require(not self.output.is_relative_to(root) and not root.is_relative_to(self.output),
                    "fresh output overlaps immutable receiving evidence")

    def resolve(self, value: Path | str) -> Path:
        path = Path(value)
        require(path.is_absolute() and ".." not in path.parts, "mapped path must be explicit absolute")
        matches = [(new / path.relative_to(old) if kind == "directory" else new)
                   for old, new, kind in self.maps if path == old or kind == "directory" and path.is_relative_to(old)]
        if matches:
            require(all(candidate == matches[0] for candidate in matches), "ambiguous historical mapping")
            result = matches[0]
        else:
            result = path
        absolute(result)
        require(result == self.output or result.is_relative_to(self.output)
                or result in self.files or result in self.roots
                or any(result.is_relative_to(root) for root in self.roots), "path has no trusted receiving role")
        if result.exists() and result.is_file() and not result.is_relative_to(self.output):
            require(result in self.files, "unlisted restored file refused")
        return result

    def historical(self, restored: Path) -> Path:
        """Reverse only an unambiguous declared mapping, never guess a path."""
        absolute(restored)
        matches = [(old / restored.relative_to(new) if kind == "directory" else old)
                   for old, new, kind in self.maps if restored == new or kind == "directory" and restored.is_relative_to(new)]
        require(matches and all(path == matches[0] for path in matches), "receiving path has no unique historical role")
        return matches[0]

    def verify(self) -> dict[str, Any]:
        """Bind every immutable file, including failed and orphan artifacts."""
        for root, expected in self.roots.items():
            actual = {}
            for path in sorted(root.rglob("*")):
                absolute(path)
                require(path.is_file() or path.is_dir(), "unsafe immutable artifact")
                if path.is_file():
                    actual[str(path.relative_to(root))] = binding(path)
            require(actual == expected, "immutable tree file set/bytes differ")
        for path, expected in self.files.items():
            require(binding(path) == expected, "immutable file bytes differ")
        return {"immutable_root_count": len(self.roots), "immutable_file_count": len(self.files),
                "immutable_file_map_sha256": digest({str(path): value for path, value in sorted(self.files.items())})}


def import_pinned(path: Path, expected: str, name: str) -> Any:
    require(binding(path)["sha256"] == expected and name not in sys.modules, "source pin or private namespace differs")
    specification = importlib.util.spec_from_file_location(name, path)
    require(specification is not None and specification.loader is not None, "cannot load pinned support")
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    try:
        specification.loader.exec_module(module)
        require(binding(path)["sha256"] == expected, "support source changed while loading")
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def mapped_common(common: Any, resolver: Resolver) -> Any:
    """Adapt only explicit I/O for the original byte-pinned stdlib gates.

    Reads retain document bytes. Writes are restricted to the new external
    receiving output; destructive/claim/dispatch helpers are unavailable.
    """
    originals = {name: getattr(common, name) for name in (
        "safe", "sha", "read_json", "file_binding", "verify_files", "module_from_pin", "read_original_manifest",
        "verify_original_outcome", "write_new", "write_bytes_new", "copy_new")}
    for name in ("safe", "sha", "read_json", "file_binding", "module_from_pin", "read_original_manifest", "verify_original_outcome"):
        original = originals[name]
        def mapped(path: Path, *args: Any, _function: Any = original, **kwargs: Any) -> Any:
            return _function(resolver.resolve(path), *args, **kwargs)
        setattr(common, name, mapped)
    common.verify_files = lambda root, values: originals["verify_files"](resolver.resolve(root), values)
    for name in ("write_new", "write_bytes_new"):
        original = originals[name]
        def external_write(path: Path, *args: Any, _function: Any = original, **kwargs: Any) -> Any:
            target = absolute(path)
            require(target.is_relative_to(resolver.output), "receiving writes are external-output-only")
            return _function(target, *args, **kwargs)
        setattr(common, name, external_write)
    def forbidden(*_args: Any, **_kwargs: Any) -> None:
        raise InvalidEvidence("receiving verifier cannot claim/copy/execute original science")
    common.copy_new, common.Claim, common.verify_original_source = forbidden, forbidden, forbidden
    return common


def bootstrap(value: dict[str, Any], resolver: Resolver) -> tuple[Any, Any]:
    require(not any(name == "src" or name.startswith("src.") for name in sys.modules), "foreign scientific namespace refused")
    code = resolver.resolve(value["reproduction_code"])
    require(value["reproduction_source_sha256"] == V1_PINS, "receiving v1 source scope differs")
    for name, expected in V1_PINS.items():
        require(binding(code / name)["sha256"] == expected, "sealed v1 source bytes differ")
    require(binding(code / "test_reproduction.py")["sha256"] == V1_TEST_SHA
            and binding(code / "preparation_receipt.json")["sha256"] == V1_RECEIPT_SHA,
            "sealed v1 tests/preparation lineage differs")
    selection = document(resolver.resolve(value["selection"]), value["selection_sha256"])
    common_file = resolver.resolve(Path(selection["paths"]["fit_code"]) / "fit_common.py")
    common = mapped_common(import_pinned(common_file, FIT_COMMON_SHA, "_reproduction_bound_common"), resolver)
    rc = common.module_from_pin(code / "reproduction_core.py", V1_PINS["reproduction_core.py"], "_receiving_v1_core")
    return common, rc


def recorded_argv(record: dict[str, Any], script: Path, options: tuple[tuple[str, str], ...]) -> None:
    """Compare the historical recorded argv as recorded, without relocation."""
    values, cwd, index = record["argv"], Path(record["cwd"]), record["script_index"]
    require(isinstance(values, list) and all(isinstance(item, str) for item in values)
            and cwd.is_absolute() and ".." not in cwd.parts
            and type(index) is int and 0 <= index < len(values), "recorded argv grammar differs")
    declared = Path(values[index])
    declared = declared if declared.is_absolute() else cwd / declared
    require(".." not in declared.parts and declared == script, "historical script/argv differs")
    for option, expected in options:
        require(values.count(option) == 1 and values.index(option) + 1 < len(values)
                and values[values.index(option) + 1] == expected, "historical argv input differs")


def verify_producer(producer: dict[str, Any], original: dict[str, Any], environment: dict[str, Any],
                    historical_original: Path, historical_reproduction: Path, identity: str,
                    resolver: Resolver, common: Any, rc: Any) -> dict[str, Any]:
    """Preserve actual original producer proof while relocating only file I/O.

    Current receiving Git/interpreter identity cannot establish a historical
    worker. Full recorded source/input/runtime/execution/delegation proofs and
    actual production v1 comparison remain required. Current environment is
    checked separately; missing producer evidence is never inferred.
    """
    source = Path(producer["source_path"])
    require(source.is_absolute() and producer["git_commit"] in rc.ORIGINAL_NUMERICAL_PRODUCER_COMMITS
            and set(producer["input_sha256"]) == set(original["input_sha256"]), "historical producer/source coverage differs")
    actual_source = resolver.resolve(source)
    for name, expected in producer["input_sha256"].items():
        require(binding(actual_source / relative(name))["sha256"] == expected, "restored original producer source/input differs")
    require(producer["input_sha256"]["scripts/reproduce_extensions.py"] == rc.COMPARISON_PINS["scripts/reproduce_extensions.py"],
            "historical official comparison source differs")
    documents = {}
    for role in ("environment_report", "invocation_record", "scientific_lineage_review", "official_comparison_record"):
        item = producer[role]
        path = resolver.resolve(item["path"])
        require(binding(path) == item["binding"], "restored producer evidence differs")
        documents[role] = json.loads(path.read_text()) if role == "environment_report" else document(path)
    require(documents["environment_report"] == environment and environment["status"] == "ok"
            and environment["package_count"] == 259, "historic producer full259 environment differs")
    invocation = documents["invocation_record"]
    require(invocation["status"] == "actual_original_numerical_worker_invocation_recorded"
            and invocation["source_path"] == str(source) and invocation["git_commit"] == producer["git_commit"]
            and invocation["original_manifest_sha256"] == common.ORIGINAL_MANIFEST_SHA
            and invocation["original_run"] == str(historical_original)
            and invocation["reproduction_output"] == str(historical_reproduction)
            and invocation["source_input_sha256"] == producer["input_sha256"]
            and invocation["environment_report_sha256"] == producer["environment_report"]["binding"]["sha256"]
            and invocation["original_full_budget"] is True and invocation["actual_numerical_refit_execution"] is True
            and invocation["exit_code"] == 0 and invocation["owner_finished"] is True
            and invocation["cached_comparison_only"] is False
            and identity in invocation["numerically_refitted_cell_ids"]
            and invocation["numeric_thread_environment"] == {name: "1" for name in NUMERIC_VARIABLES},
            "actual historical numerical producer proof required")
    require(Path(invocation["python_executable"]).is_absolute(), "historic numerical interpreter record absent")
    matched = producer["matched_input"]
    require(binding(resolver.resolve(matched["path"])) == matched["binding"]
            and matched["binding"]["sha256"] == original["matched_sha256"], "restored matched input differs")
    options = (("--source", str(historical_original)), ("--output", str(historical_reproduction)), ("--matched", matched["path"]))
    route = producer["route"]
    if route == "official_fresh_refit":
        recorded_argv(invocation, source / "scripts/reproduce_extensions.py", options)
    elif route == "reviewed_external_prestage":
        require(producer["git_commit"] == common.ORIGINAL_COMMIT and producer["input_sha256"] == original["input_sha256"],
                "prestage must delegate exact original119 source")
        helper = producer["helper"]
        require(binding(resolver.resolve(helper["path"])) == helper["binding"]
                and helper["binding"]["sha256"] == rc.PRESTAGE_HELPER_SHA, "actual historic prestage helper pin differs")
        worker, workers = invocation["worker"], invocation["workers"]
        require(type(worker) is int and type(workers) is int and 0 <= worker < workers, "actual historical shard differs")
        recorded_argv(invocation, Path(helper["path"]), options + (("--production-code", str(source)),
                      ("--worker", str(worker)), ("--workers", str(workers))))
        chosen = [row["cell_id"] for row in original["plan"] if "__r01f01__" in row["cell_id"]]
        require(len(chosen) == 92 and identity in chosen and chosen.index(identity) % workers == worker, "historic shard does not own cell")
        item = producer["helper_scientific_delegation_review"]
        require(binding(resolver.resolve(item["path"])) == item["binding"], "historic helper review differs")
        review = document(resolver.resolve(item["path"]))
        require(review["status"] == "actual_prestage_helper_scientific_delegation_reviewed"
                and review["helper_sha256"] == rc.PRESTAGE_HELPER_SHA
                and review["original_manifest_sha256"] == common.ORIGINAL_MANIFEST_SHA
                and review["production_source_commit"] == common.ORIGINAL_COMMIT
                and review["unchanged_run_extension_cell_inputs_seeds_budget_and_guards"] is True
                and review["issues_official_final_receipts"] is False, "actual historic helper delegation review required")
        log = invocation["stdout"]
        path = resolver.resolve(log["path"])
        require(binding(path) == log["binding"] and f"{identity} prestaged_exact" in path.read_text().splitlines(),
                "historic prestage log does not witness new refit")
    else:
        raise InvalidEvidence("unknown historic numerical producer route")
    official = documents["official_comparison_record"]
    require(official["status"] == "actual_official_original_92_comparison_recorded"
            and official["source_path"] == str(source) and official["git_commit"] == producer["git_commit"]
            and official["original_manifest_sha256"] == common.ORIGINAL_MANIFEST_SHA
            and official["source_input_sha256"] == producer["input_sha256"]
            and official["environment_report_sha256"] == producer["environment_report"]["binding"]["sha256"]
            and official["exit_code"] == 0 and official["owner_finished"] is True
            and identity in official["scientifically_compared_cell_ids"]
            and official["numeric_thread_environment"] == {name: "1" for name in NUMERIC_VARIABLES}
            and Path(official["python_executable"]).is_absolute()
            and official["cached_comparison_only"] is (route == "reviewed_external_prestage"),
            "separate actual historic official comparison proof required")
    recorded_argv(official, source / "scripts/reproduce_extensions.py", options)
    lineage = documents["scientific_lineage_review"]
    require(lineage["status"] == "original_numerical_execution_input_and_algorithm_lineage_reviewed"
            and lineage["original_manifest_sha256"] == common.ORIGINAL_MANIFEST_SHA
            and lineage["producer_git_commit"] == producer["git_commit"]
            and lineage["producer_input_sha256"] == producer["input_sha256"]
            and lineage["original_input_sha256"] == original["input_sha256"]
            and lineage["invocation_record_sha256"] == producer["invocation_record"]["binding"]["sha256"]
            and lineage["official_comparison_record_sha256"] == producer["official_comparison_record"]["binding"]["sha256"]
            and lineage["producer_route"] == route
            and lineage["frozen_primary_scientific_inputs_algorithms_seeds_budgets_and_gates_identical"] is True,
            "independent actual historical producer algorithm/input lineage required")
    return {"status": "historic_actual_numerical_producer_and_distinct_official_comparison_preserved",
            "route": route, "historic_git_commit": producer["git_commit"],
            "historical_interpreter_identity": "retained_in_immutable_actual_v1_execution_proof_not_replaced_by_receiving_interpreter",
            "restored_source_input_count": len(producer["input_sha256"]), "new_numerical_fit_executed": False}


def complete_pass(value: dict[str, Any], selection: dict[str, Any], selection_sha: str, rc: Any) -> None:
    required = rc.publication_status(value["outcomes"], selection["selected_cells"])
    require(value["status"] == required["status"] == "all_selected_reproduction_outcomes_accounted"
            and all(value[key] == item for key, item in required.items())
            and value["selection_sha256"] == selection_sha
            and value["scope_definition_sha256"] == rc.scope_definition(selection)
            and value["original_fixed_selected_cells"] == 92
            and value["pilot_union_selected_cells"] == len(selection["selected_cells"])
            and value["correction_freeze_sha256"] == selection["correction_freeze_sha256"]
            and value["corrected_manifest_sha256"] == selection["corrected_manifest_sha256"]
            and value["original_comparison_source_sha256"] == rc.COMPARISON_PINS,
            "explicit complete selected-union pass required")


def verify_capture(invocation: dict[str, Any], request: dict[str, Any], request_path: Path,
                   request_sha: str, script: Path, python: str, common: Any) -> None:
    require(invocation["operation"] == "isolated_selected_reproduction_child"
            and invocation["exit_code"] == 0 and invocation["launch_error"] is None
            and invocation["numeric_thread_environment"] == {name: "1" for name in NUMERIC_VARIABLES}
            and request["locked_python"] == python
            and invocation["argv"] == [python, "-I", "-B", str(script), "--request", str(request_path),
                                       "--request-sha256", request_sha],
            "actual isolated historical child execution/request evidence differs")
    for role in ("stdout", "stderr"):
        path = request_path.parent / f"{role}.log"
        require(common.file_binding(path) == invocation[role], "actual child output log differs")


def verify_historic_environment(attempt: Path, historical_source: Path, python: str,
                                expected_report: dict[str, Any], original: dict[str, Any], common: Any) -> None:
    """Preserve the actual child's fresh checker rc0 and full report bytes."""
    stdout, stderr = attempt / "environment.stdout.json", attempt / "environment.stderr.log"
    invocation = common.read_json(attempt / "environment_invocation.json")
    require(invocation["operation"] == "fresh_original_259_package_environment_verification"
            and invocation["exit_code"] == 0
            and invocation["argv"] == [python, "-B", str(historical_source / "scripts/verify_environment.py"),
                "--lock-file", str(historical_source / "conda-lock.yml"),
                "--hash-file", str(historical_source / "conda-lock.yml.sha256")]
            and invocation["source_sha256"] == original["input_sha256"]["scripts/verify_environment.py"]
            and common.file_binding(stdout) == invocation["stdout"]
            and common.file_binding(stderr) == invocation["stderr"]
            and json.loads(stdout.read_text()) == expected_report,
            "actual historical child environment checker rc0/full259 evidence differs")


def verify_record(value: dict[str, Any], identity: str, selection: dict[str, Any], selection_sha: str,
                  root: Path, resolver: Resolver, common: Any, rc: Any) -> None:
    require(value["schema_version"] == 1 and value["original_cell_id"] == identity
            and value["status"] in FINAL_STATUSES and value["selection_sha256"] == selection_sha
            and value["scope_definition_sha256"] == rc.scope_definition(selection)
            and value["corrected_manifest_sha256"] == selection["corrected_manifest_sha256"]
            and value["correction_freeze_sha256"] == selection["correction_freeze_sha256"]
            and value["definition_content_sha256"] == selection["definition_content_sha256"]
            and value["selected_scope_only"] is True and value["programme_complete"] is False
            and value["reporting_certified"] is False and value["release_certified"] is False,
            "immutable selected record scope/status differs")
    common.verify_files(root, value["artifacts"])
    for historical, expected in value["external_artifacts"].items():
        require(binding(resolver.resolve(historical)) == expected, "external immutable reproduction lineage differs")
    outcome = resolver.resolve(value["corrected_outcome_path"])
    require(binding(outcome)["sha256"] == value["corrected_outcome_sha256"], "immutable corrected outcome differs")


def read_review(role: str, value: dict[str, Any], resolver: Resolver) -> tuple[Path, dict[str, Any]] | None:
    item = value["reviews"].get(role)
    if item is None:
        return None
    require(set(item) == {"historical_path", "sha256"}, "review receiving binding fields differ")
    path = resolver.resolve(item["historical_path"])
    return path, document(path, item["sha256"])


def original_evidence(selection: dict[str, Any], base: dict[str, Any], resolution: Any, common: Any, rc: Any) -> dict[str, Any]:
    if resolution is None:
        return base["entries"]
    _, value = resolution
    require(value["status"] == "reviewed_original_numerical_evidence_resolution"
            and value["scope_definition_sha256"] == rc.scope_definition(selection)
            and value["original_manifest_sha256"] == common.ORIGINAL_MANIFEST_SHA
            and set(value["entries"]) <= set(selection["original_selected_cells"]), "foreign numerical evidence acquisition")
    for identity, evidence in value["entries"].items():
        require(base["entries"][identity]["status"] == "pending_original_numerical_reproduction"
                and evidence["status"] == "verified_original_numerical_reproduction_evidence", "numerical resolution replaces known evidence")
    return {**base["entries"], **value["entries"]}


class ReceivingVerifier:
    """Recompare supplied, finished evidence; never dispatch missing work."""

    def __init__(self, *, value: dict[str, Any], resolver: Resolver, common: Any, rc: Any,
                 selection: Any, freeze: Any, manifest: Any, inventory: Any, completion: Any,
                 rows: Any, numerical: Any, contracts: Any, fit_controller: Any,
                 complete: Any, pf: Any, np: Any, comparators: Any) -> None:
        self.value, self.resolver, self.common, self.rc = value, resolver, common, rc
        self.selection, self.freeze, self.manifest = selection, freeze, manifest
        self.inventory, self.completion, self.rows, self.numerical = inventory, completion, rows, numerical
        self.contracts, self.fit_controller = contracts, fit_controller
        self.complete, self.pf, self.np, self.comparators = complete, pf, np, comparators
        self.root = resolver.resolve(value["reproduction_root"])
        self.paths = {key: resolver.resolve(path) for key, path in freeze["paths"].items()}
        self.repro_paths = {key: resolver.resolve(path) for key, path in selection["paths"].items()}
        self.reviews = {role: read_review(role, value, resolver) for role in (
            "original_resolution", "original_numerical_resolution", "pilot")}
        resolutions = {}
        item = self.reviews["original_resolution"]
        if item is not None:
            path, review = item
            resolutions = fit_controller.read_resolution_review(path, binding(path)["sha256"], freeze)
        # Calling current() verifies only immutable witness/snapshot/ownership
        # documents. No record()/run()/capture_child() method is ever invoked.
        args = type("ReadOnlyInputs", (), {"manifest_sha256": selection["corrected_manifest_sha256"]})()
        self.inputs = fit_controller.Controller(args, freeze, manifest, inventory, completion, contracts, resolutions)
        self.numerical = original_evidence(selection, numerical, self.reviews["original_numerical_resolution"], common, rc)
        self.original = common.read_original_manifest(self.paths["original_run"])
        self.preflight = common.read_json(self.paths["preflight"] / "manifest.json", freeze["preflight_manifest_sha256"])

    def acquisition(self, value: dict[str, Any], entry: dict[str, Any], decision: dict[str, Any],
                    baseline: dict[str, Any], witness: Any) -> None:
        """Verify pending-origin history without rewriting its old decision."""
        require(value["snapshot_path"] == self.inputs.resolutions[entry["original_cell_id"]]["snapshot_path"]
                and value["snapshot_sha256"] == self.inputs.resolutions[entry["original_cell_id"]]["snapshot_sha256"],
                "terminal acquisition lacks exact reviewed source snapshot")
        snapshot = self.common.read_json(self.paths["witness_root"] / relative(value["snapshot_path"]), value["snapshot_sha256"])
        require(snapshot["source_evidence"] == decision["source_evidence"]
                and snapshot["decision"] == decision == value["current_reviewed_acquisition_decision"]
                and snapshot["input_witness_sha256"] == entry["input_witness_sha256"]
                and snapshot["definition_content_sha256"] == self.freeze["definition_content_sha256"],
                "terminal later acquisition binds different immutable inputs/source")
        pending = self.contracts.classify(replace(witness, original_evidence=None))
        require(baseline["operation"] == "retain_corrected_input_failure"
                and baseline["original_outcome_pending"] is True and baseline["source_evidence"] is None
                and baseline["decision"] == pending and decision["action"] == "retain_input_failure"
                and decision["source_evidence"] is not None, "terminal pending-origin history differs")
        if "retained_original_terminal_decision" in value:
            require(value["status"] == "finished_original_acquisition_verified_for_pending_origin_terminal"
                    and value["retained_original_terminal_decision"] == pending, "immutable earlier terminal decision differs")

    def baseline(self, record: dict[str, Any], entry: dict[str, Any], outcome: dict[str, Any],
                 decision: dict[str, Any], witness: Any) -> dict[str, Any]:
        identity, c = entry["original_cell_id"], self.common
        path = self.repro_paths["corrected_run"] / "cells" / f"{identity}.json"
        require(self.resolver.resolve(record["corrected_outcome_path"]) == path
                and c.sha(path) == record["corrected_outcome_sha256"], "selected record corrected baseline differs")
        require(not (path.parent.parent / "claims" / f"{identity}.json").exists(), "corrected source owner is active")
        baseline = self.fit_controller.verify_record(path, self.selection["corrected_manifest_sha256"], identity)
        require(baseline["correction_freeze_sha256"] == self.selection["correction_freeze_sha256"]
                and baseline["definition_content_sha256"] == self.freeze["definition_content_sha256"]
                and baseline["input_witness_sha256"] == entry["input_witness_sha256"]
                and baseline["original_seed_namespace"] == witness.corrected_seeds, "corrected baseline input law differs")
        if baseline["decision"] != decision or baseline["source_evidence"] != decision["source_evidence"]:
            acquisition = record.get("pending_origin_terminal_resolution") or outcome.get("later_reviewed_original_acquisition")
            require(acquisition is not None and self.reviews["original_resolution"] is not None,
                    "later source acquisition cannot be inferred from pending terminal")
            self.acquisition(acquisition, entry, decision, baseline, witness)
        else:
            require(not outcome.get("later_reviewed_original_acquisition"), "foreign later acquisition on unchanged decision")
        if record["current_input_decision"] != decision:
            require(record["status"] == "terminal_no_fit_recipe_replay"
                    and record["current_input_decision"] == self.contracts.classify(replace(witness, original_evidence=None))
                    and outcome.get("later_reviewed_original_acquisition") is not None,
                    "selected record decision differs outside exact pending-origin terminal acquisition")
        return baseline

    def inherited(self, identity: str, record: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
        c, rc, root = self.common, self.rc, self.repro_paths["original_reproduction"]
        require(identity in self.numerical, "no actual original numerical producer evidence")
        evidence = self.numerical[identity]
        require(evidence["status"] == "verified_original_numerical_reproduction_evidence"
                and evidence["original_cell_id"] == identity and evidence["owner_finished"] is True,
                "pending/unknown original producer evidence cannot be promoted")
        require(not (root / "claims" / f"{identity}.json").exists(), "original numerical owner active")
        official_path = c.below(root, evidence["official_receipt_path"])
        require(evidence["official_receipt_path"] == f"receipts/{identity}.json"
                and c.file_binding(official_path) == evidence["official_receipt"], "official original receipt differs")
        source_path, refit_path = self.paths["original_run"] / "cells" / f"{identity}.json", root / "cells" / f"{identity}.json"
        require(c.file_binding(source_path) == evidence["source_cell"] and c.file_binding(refit_path) == evidence["refit_cell"],
                "actual source/refit cells differ")
        review = c.read_json(Path(evidence["execution_review"]["path"]), evidence["execution_review"]["sha256"])
        require(review["status"] == "original_numerical_refit_and_trace_comparison_execution_reviewed"
                and review["original_cell_id"] == identity and review["original_manifest_sha256"] == c.ORIGINAL_MANIFEST_SHA
                and review["comparison_source_sha256"] == rc.COMPARISON_PINS
                and review["source_cell"] == evidence["source_cell"] and review["refit_cell"] == evidence["refit_cell"]
                and review["official_receipt"] == evidence["official_receipt"]
                and review["original_full_budget"] is True and review["numerical_refit_executed"] is True
                and review["owner_finished"] is True, "actual reviewed historical numerical execution required")
        producer = verify_producer(review["producer"], self.original, self.preflight["environment_verification"],
            Path(self.freeze["paths"]["original_run"]), Path(self.selection["paths"]["original_reproduction"]),
            identity, self.resolver, c, rc)
        result = rc.compare_cells(source_path, refit_path, self.paths["original_run"], root, self.comparators)
        official = json.loads(official_path.read_text())
        require(official == {"cell_id": identity, "status": "scientific_match",
            "source_content_sha256": result["left_content_sha256"], "refit_content_sha256": result["right_content_sha256"],
            "trace_sample_arrays": "exact; timing/NetCDF metadata excluded"}, "official original comparison semantics differ")
        require(result == record["comparison"] and result["trace_inventory"] == evidence["trace_inventory"] == review["trace_inventory"]
                and baseline["operation"] == "reuse_original_outcome"
                and baseline["original_reference"]["sha256"] == evidence["source_cell"]["sha256"]
                and record["new_numerical_fit_executed"] is False
                and record["inherited_actual_original_numerical_refit_evidence"] is True,
                "inherited actual numerical proof is not exact unchanged reuse")
        return {"comparison": result, "producer": producer, "new_numerical_fit_executed_at_receiving": False}

    def changed(self, identity: str, record: dict[str, Any], baseline: dict[str, Any], entry: dict[str, Any],
                decision: dict[str, Any], witness: Any) -> dict[str, Any]:
        c = self.common
        require(baseline["operation"] == "fit_corrected_inputs" and decision["action"] in c.FIT_ACTIONS
                and record["new_numerical_fit_executed"] is True, "changed route lacks actual corrected numerical execution")
        if identity not in self.manifest["pilot_cells"]:
            require(self.reviews["pilot"] is not None, "nonpilot numerical reproduction lacks actual pilot review")
            self.fit_controller.validate_pilot_review(self.reviews["pilot"][1], self.manifest,
                self.selection["corrected_manifest_sha256"], self.repro_paths["corrected_run"])
        child_path = c.below(self.root, record["child_receipt_path"])
        require(child_path.name == "child_receipt.json" and child_path.parent.parent == self.root / "attempts",
                "changed child receipt namespace differs")
        attempt = child_path.parent
        child, request = c.read_json(child_path), c.read_json(attempt / "request.json")
        historical_attempt = self.resolver.historical(attempt)
        expected = {"original_cell_id": identity, "entry": entry, "source_evidence": decision["source_evidence"],
            "action": decision["action"], "freeze_path": self.selection["paths"]["freeze"],
            "freeze_sha256": self.selection["correction_freeze_sha256"], "manifest_path": self.selection["paths"]["manifest"],
            "manifest_sha256": self.selection["corrected_manifest_sha256"], "attempt_path": str(historical_attempt),
            "locked_python": request["locked_python"], "implementation_source_sha256": self.rc.FIT_SOURCE_PINS}
        require(request == seal(expected), "changed reproduction request is not exact original law")
        verify_capture(c.read_json(attempt / "invocation.json"), request, historical_attempt / "request.json",
            c.sha(attempt / "request.json"), Path(self.selection["paths"]["fit_code"]) / "fit_child.py", request["locked_python"], c)
        verify_historic_environment(attempt, Path(self.freeze["paths"]["source"]), request["locked_python"],
                                   self.preflight["environment_verification"], self.original, c)
        path = attempt / "cells" / f"{identity}.json"
        require(child["status"] == "original_cell_delegated_with_verified_corrected_inputs"
                and child["original_cell_id"] == identity
                and child["corrected_manifest_sha256"] == self.selection["corrected_manifest_sha256"]
                and child["input_witness_sha256"] == entry["input_witness_sha256"] and child["action"] == decision["action"]
                and child["original_seed_namespace"] == witness.corrected_seeds and c.file_binding(path) == child["cell"]
                and child["fit_dispatched"] is True
                and child["full_environment_verification"] == self.preflight["environment_verification"]
                and child["actual_process_runtime_verification"]["locked_interpreter_samefile"] is True
                and child["actual_process_runtime_verification"]["numeric_thread_environment"] == {name: "1" for name in NUMERIC_VARIABLES},
                "actual historical corrected child input/runtime/seed proof differs")
        checked = child["full_current_execution_input_verification"]
        require(checked["content_sha256"] == digest({key: item for key, item in checked.items() if key != "content_sha256"})
                and checked["status"] == "current_complete_inputs_match_corrected_witness"
                and checked["input_witness_sha256"] == entry["input_witness_sha256"]
                and checked["definition_content_sha256"] == self.freeze["definition_content_sha256"]
                and checked["corrected_role_sha256"] == {name: item.corrected_sha256 for name, item in witness.roles.items()}
                and checked["required_role_count"] == len(witness.roles)
                and checked["no_generator_model_fit_prediction_or_score_executed"] is True,
                "actual child complete execution input witness differs")
        old_path = c.below(self.repro_paths["corrected_run"], baseline["corrected_cell"]["path"])
        require(c.sha(old_path) == baseline["corrected_cell"]["sha256"], "corrected original fit comparison source differs")
        result = self.rc.compare_cells(old_path, path, old_path.parent.parent, attempt, self.comparators)
        saved = c.read_json(attempt / "comparison.json")
        require(saved == seal(result) and result == record["comparison"]
                and child["scientific_status"] == record["scientific_status"], "actual corrected numeric cell/sample comparison differs")
        return {"comparison": result, "historical_new_corrected_numerical_reproduction_preserved": True,
                "new_numerical_fit_executed_at_receiving": False}

    def terminal(self, identity: str, record: dict[str, Any], baseline: dict[str, Any], entry: dict[str, Any]) -> dict[str, Any]:
        c, rc = self.common, self.rc
        require(baseline["operation"] == "retain_corrected_input_failure"
                and record["new_numerical_fit_executed"] is False and record["scientific_status"] == "not_fit_input_failure",
                "terminal route cannot be a fitted-cell reproduction")
        receipt_path = c.below(self.root, record["terminal_receipt_path"])
        require(receipt_path.name == "receipt.json" and receipt_path.parent.parent == self.root / "attempts",
                "terminal receipt namespace differs")
        attempt, result = receipt_path.parent, c.read_json(receipt_path)
        request = c.read_json(attempt / "request.json")
        historical_attempt = self.resolver.historical(attempt)
        request_selection = c.read_json(Path(request["selection_path"]), self.value["selection_sha256"])
        require(request_selection == self.selection, "historical terminal request selection differs from immutable copied selection")
        expected = {"original_cell_id": identity, "entry": entry, "attempt_path": str(historical_attempt),
            "selection_path": request["selection_path"],
            "selection_sha256": self.value["selection_sha256"], "fit_code": self.selection["paths"]["fit_code"],
            "locked_python": request["locked_python"], "fit_implementation_source_sha256": rc.FIT_SOURCE_PINS,
            "implementation_source_sha256": self.selection["implementation_source_sha256"]}
        require(request == seal(expected), "actual terminal child request differs")
        script = self.resolver.historical(self.resolver.resolve(self.value["reproduction_code"])) / "terminal_replay_child.py"
        verify_capture(c.read_json(attempt / "invocation.json"), request, historical_attempt / "request.json",
                       c.sha(attempt / "request.json"), script, request["locked_python"], c)
        verify_historic_environment(attempt, Path(self.freeze["paths"]["source"]), request["locked_python"],
                                   self.preflight["environment_verification"], self.original, c)
        c.verify_files(attempt, result["artifacts"])
        chosen = rc.selected_contexts(self.rows, identity, entry["model"])
        require(result["status"] == "selected_terminal_full_recipe_independently_replayed_without_fit"
                and result["original_cell_id"] == identity and result["selection_sha256"] == self.value["selection_sha256"]
                and result["scope_definition_sha256"] == rc.scope_definition(self.selection)
                and result["corrected_manifest_sha256"] == self.selection["corrected_manifest_sha256"]
                and result["input_witness_sha256"] == entry["input_witness_sha256"]
                and [item["context_id"] for item in result["contexts"]] == [row["context_id"] for row in chosen]
                and result["scoped_context_count"] == len(chosen)
                and result["normal_full_raw_training_preprocessor_fit"] is True
                and result["candidate_adapter_restoration_or_thinning_used"] is False
                and result["no_model_optimizer_mcmc_prediction_or_score_executed"] is True
                and result["new_numerical_fitted_cell_reproduction"] is False
                and result["all1650_contexts_replayed"] is False
                and result["runtime"]["locked_interpreter_samefile"] is True
                and result["runtime"]["numeric_thread_environment"] == {name: "1" for name in NUMERIC_VARIABLES},
                "actual historical scoped no-fit recipe replay proof differs")
        comparisons, saw_terminal = [], False
        for row, outcome in zip(chosen, result["contexts"], strict=True):
            directory, saved = self.complete.context(row)
            actual_path = c.below(attempt, outcome["actual_receipt_path"])
            expected_relative = f"contexts/{row['context_id'].split('::')[-1]}/actual.json"
            require(outcome["actual_receipt_path"] == expected_relative, "terminal actual context namespace differs")
            actual = c.read_json(actual_path, outcome["actual_receipt_sha256"])
            require(actual["context_id"] == row["context_id"]
                    and actual["preflight_receipt_sha256"] == self.complete.lookup[row["context_id"]]["receipt_sha256"],
                    "terminal replay binds another actual preflight context")
            assessment = rc.compare_context_history(saved, actual)
            require(assessment == outcome["assessment"] and outcome["status"] == actual["status"], "terminal recipe assessment differs")
            require({path.name for path in actual_path.parent.glob("attempt_*")}
                    == {f"attempt_{index:03d}" for index in range(len(actual["attempts"]))},
                    "terminal rejected/nonrank/orphan attempt set differs")
            for index, after in enumerate(actual["attempts"]):
                draw_directory = actual_path.parent / f"attempt_{index:03d}"
                persisted = c.read_json(draw_directory / "receipt.json")
                require({key: item for key, item in persisted.items() if key not in {"artifacts", "content_sha256"}} == after,
                        "terminal draw receipt/history differs")
                c.verify_files(draw_directory, persisted["artifacts"])
                if saved["attempts"][index]["status"] != "nonrank_error":
                    old, new = self.pf.read_arrays(directory / f"attempt_{index:03d}/proposal.npz"), self.pf.read_arrays(draw_directory / "proposal.npz")
                    require(set(old) == set(new) == rc.NUMERIC_KEYS
                            and {key: self.pf.array_witness(item) for key, item in new.items()} == after["array_witnesses"]
                            and all(self.np.array_equal(old[key], new[key], equal_nan=True) for key in old),
                            "actual restored constructor dtype/shape/element bytes differ")
                elif persisted["artifacts"]:
                    # Preserve actual new nonrank constructor evidence without
                    # inventing unavailable historical constructor identity.
                    arrays = self.pf.read_arrays(draw_directory / "proposal.npz")
                    require(set(arrays) == rc.NUMERIC_KEYS
                            and {key: self.pf.array_witness(item) for key, item in arrays.items()} == after["array_witnesses"],
                            "retained nonrank constructor evidence differs")
            saw_terminal |= saved["status"] in rc.TERMINAL
            comparisons.append({"context_id": row["context_id"], "assessment": assessment,
                                "status": actual["status"], "actual_receipt_sha256": outcome["actual_receipt_sha256"]})
        require(saw_terminal and record["scoped_generator_contexts"] == [row["context_id"] for row in chosen],
                "terminal route does not contain a nonaccepted frozen input")
        return {"status": "stored_actual_terminal_recipe_evidence_recompared_without_generation", "contexts": comparisons,
                "new_terminal_recipe_execution_at_receiving": False, "new_numerical_fit_executed_at_receiving": False}

    def run(self, pass_value: dict[str, Any], output: Path) -> list[dict[str, Any]]:
        """A finished selected pass is mandatory; no pending row is repaired."""
        c, results = self.common, []
        complete_pass(pass_value, self.selection, self.value["selection_sha256"], self.rc)
        c.verify_files(self.root, pass_value["controller_environment_artifacts"])
        if "actual_original_resolution_review" in pass_value:
            item = self.value["reviews"].get("original_resolution")
            require(item is not None and pass_value["actual_original_resolution_review"] == {
                "path": item["historical_path"], "sha256": item["sha256"]}, "completed pass actual source-resolution review differs")
        lookup = {item["original_cell_id"]: item for item in self.inventory["entries"]}
        for outcome in pass_value["outcomes"]:
            identity = outcome["original_cell_id"]
            path = self.root / "cells" / f"{identity}.json"
            require(not (self.root / "claims" / f"{identity}.json").exists(), "reproduction owner remains active")
            value = c.read_json(path, outcome["record_sha256"])
            verify_record(value, identity, self.selection, self.value["selection_sha256"], self.root, self.resolver, c, self.rc)
            require(value["status"] == outcome["status"], "completed pass route/record differs")
            entry = lookup[identity]
            require(value["input_witness_sha256"] == entry["input_witness_sha256"], "selected reproduction immutable input differs")
            _, decision, old, witness = self.inputs.current(entry)
            require(decision["action"] not in {"await_original_owner_or_outcome", "await_original_outcome", "unresolved"},
                    "restored original outcome/role proof is unresolved")
            require(decision["source_evidence"] is None or old is not None, "finished original source proof unavailable")
            baseline = self.baseline(value, entry, outcome, decision, witness)
            if value["status"] == "reused_verified_original_numerical_reproduction":
                result = self.inherited(identity, value, baseline)
            elif value["status"] == "new_corrected_numerical_reproduction":
                result = self.changed(identity, value, baseline, entry, decision, witness)
            else:
                result = self.terminal(identity, value, baseline, entry)
            after = self.inputs.current(entry)[1]
            require(after == decision, "immutable input decision/source changed during receiving comparison")
            result.update(original_cell_id=identity, route=value["status"], original_record_sha256=outcome["record_sha256"])
            write_new(output / "cells" / f"{identity}.json", seal(result))
            results.append(result)
        return results


def load_receiving_dependencies(value: dict[str, Any], resolver: Resolver, output: Path, python: Path) -> dict[str, Any]:
    """Load only bound read-only gates after a fresh actual259 environment check."""
    common, rc = bootstrap(value, resolver)
    code = resolver.resolve(value["reproduction_code"])
    selection, freeze, manifest, inventory, (completion, rows, numerical) = rc.load_selection(
        resolver.resolve(value["selection"]), value["selection_sha256"], code)
    source = resolver.resolve(freeze["paths"]["source"])
    original = common.read_original_manifest(Path(freeze["paths"]["original_run"]))
    # Receiving archive extraction may not have a Git checkout. Frozen source
    # and recorded commits remain verified by complete actual file byte maps.
    for name, expected in original["input_sha256"].items():
        require(binding(source / relative(name))["sha256"] == expected, "restored original119 source/input differs")
    require(binding(resolver.resolve(freeze["paths"]["matched"]))["sha256"] == original["matched_sha256"], "restored matched input differs")
    preflight = common.read_json(Path(freeze["paths"]["preflight"]) / "manifest.json", freeze["preflight_manifest_sha256"])
    (output / "environment").mkdir()
    actual_environment = common.verify_environment(source, original, python, preflight, output / "environment")
    for name in ("matplotlib", "numba", "pytensor"):
        (output / "cache" / name).mkdir(parents=True)
    os.environ.update(MPLCONFIGDIR=str(output / "cache/matplotlib"), NUMBA_CACHE_DIR=str(output / "cache/numba"),
                      PYTENSOR_FLAGS=f"compiledir={output / 'cache/pytensor'}")
    # Exact original comparison function ASTs avoid importing scientific src.
    import arviz as az
    import numpy as np
    paths = {key: resolver.resolve(path) for key, path in freeze["paths"].items()}
    contracts = common.module_from_pin(paths["contracts"], common.CONTRACTS_SHA, "_reuse_bound_contracts")
    pf = common.module_from_pin(paths["preflight_core"], common.PREFLIGHT_CORE_SHA, "_reuse_bound_core")
    reuse = common.module_from_pin(paths["reuse_core"], common.REUSE_CORE_SHA, "_receiving_reuse_core")
    require("fit_common" not in sys.modules, "fit support namespace occupied")
    sys.modules["fit_common"] = common
    fit_directory = resolver.resolve(selection["paths"]["fit_code"])
    fit_controller = common.module_from_pin(fit_directory / "fit_controller.py", rc.FIT_SOURCE_PINS["fit_controller.py"], "_receiving_fit_input_gates")
    complete = reuse.CompletePreflight(paths["preflight"], rows)
    require(complete.completion == completion and complete.manifest == preflight, "receiving preflight belongs to another run")
    return {"common": common, "rc": rc, "selection": selection, "freeze": freeze, "manifest": manifest,
            "inventory": inventory, "completion": completion, "rows": rows, "numerical": numerical,
            "contracts": contracts, "fit_controller": fit_controller, "complete": complete, "pf": pf, "np": np,
            "comparators": rc.original_comparators(source, np, az), "environment": actual_environment}


def verify_receiving(bindings_path: Path, bindings_sha256: str, output: Path, python: Path,
                     *, dependencies: Any = None) -> dict[str, Any]:
    """Verify an immutable restored selected pass, writing only external evidence.

    ``dependencies`` is an invented/injected test seam, unavailable through the
    production CLI. Production uses byte-pinned source and a fresh actual
    environment checker; it never invokes numerical jobs or generation.
    """
    actual_runtime = runtime(python)
    value = document(absolute(bindings_path), bindings_sha256)
    require(value["schema_version"] == 1 and value["status"] == "corrected_selected_reproduction_receiving_bindings"
            and set(value["reviews"]) <= {"original_resolution", "original_numerical_resolution", "pilot"},
            "receiving bindings status/review scope differs")
    require(value["receiving_source_sha256"] == {name: binding(Path(__file__).absolute().parent / name)["sha256"] for name in OWN_SOURCES},
            "actual receiving helper sources differ from trusted binding")
    own_directory = Path(__file__).absolute().parent
    require(not output.is_relative_to(own_directory) and not own_directory.is_relative_to(output),
            "receiving output overlaps its own sealed implementation")
    resolver = Resolver(value, output)
    before = resolver.verify()
    require(output.parent.is_dir() and not output.exists(), "new external output directory required; receiving never resumes")
    output.mkdir()
    (output / "cells").mkdir()
    write_new(output / "bindings_capture.json", seal({"bindings_path": str(bindings_path), "bindings_sha256": bindings_sha256,
        "actual_runtime": actual_runtime, "immutable_inventory": before, "no_controller_execute_or_resume": True}))
    try:
        pack = (load_receiving_dependencies(value, resolver, output, python) if dependencies is None
                else dependencies(value, resolver, output, python))
        environment = pack.pop("environment")
        require(environment["report"]["status"] == "ok" and environment["report"]["package_count"] == 259
                and environment["invocation"]["exit_code"] == 0, "actual fresh environment rc0 evidence required")
        verifier = ReceivingVerifier(value=value, resolver=resolver, **pack)
        root = verifier.root
        require(resolver.resolve(value["selection"]) == root / "selection.json", "receiving selection must be immutable run selection")
        require(not (root / "controller.claim.json").exists(), "reproduction controller remains active")
        pass_item = value["completed_pass"]
        require(set(pass_item) == {"path", "sha256"} and relative(pass_item["path"]).parent == Path("passes"),
                "explicit completed pass namespace required")
        pass_path = root / relative(pass_item["path"])
        pass_value = document(pass_path, pass_item["sha256"])
        results = verifier.run(pass_value, output)
        after = resolver.verify()
        require(before == after and binding(bindings_path)["sha256"] == bindings_sha256,
                "receiving immutable evidence changed during verification")
        routes = {status: sum(result["route"] == status for result in results) for status in sorted(FINAL_STATUSES)}
        owned_artifacts = {str(path.relative_to(output)): binding(path) for path in sorted(output.rglob("*")) if path.is_file()}
        receipt = seal({"schema_version": 1,
            "status": "corrected_selected_reproduction_restored_read_only_verified" if dependencies is None else "synthetic_receiving_verification_fixture_passed",
            "bindings_sha256": bindings_sha256, "selection_sha256": value["selection_sha256"],
            "completed_pass_sha256": pass_item["sha256"], "scope_definition_sha256": verifier.rc.scope_definition(verifier.selection),
            "original_fixed_selected_cells": 92, "selected_union_cells": len(verifier.selection["selected_cells"]),
            "accounted_selected_cells": len(results), "selected_route_counts": routes,
            "receiving_source_sha256": value["receiving_source_sha256"], "reproduction_source_sha256": V1_PINS,
            "v1_preparation_receipt_sha256": V1_RECEIPT_SHA, "v1_test_source_sha256": V1_TEST_SHA,
            "immutable_inventory_before": before, "immutable_inventory_after": after,
            "current_receiving_runtime": actual_runtime, "environment": environment,
            "cells": {result["original_cell_id"]: binding(output / "cells" / f"{result['original_cell_id']}.json") for result in results},
            "artifacts": owned_artifacts,
            "historical_absolute_paths_rewritten": False, "restored_evidence_modified": False,
            "new_numerical_fit_executed": False, "new_generator_recipe_executed": False,
            "test_only_dependency_injection": dependencies is not None,
            "verification_kind": "fresh_stored_scientific_sample_array_and_terminal_recipe_evidence_comparison",
            "actual_cli_exit_code_capture": "caller_must_capture_real_process_rc0_separately",
            "whole_1625_grid_numerically_reproduced": False, "programme_complete": False,
            "reporting_certified": False, "release_certified": False, "scientific_approval_created": False})
        write_new(output / "receipt.json", receipt)
        require(owned_artifacts == {str(path.relative_to(output)): binding(path) for path in sorted(output.rglob("*"))
                                    if path.is_file() and path != output / "receipt.json"},
                "fresh receiving output artifacts changed before publication")
        return receipt
    except BaseException as error:
        write_new(output / "failure.json", seal({"status": "receiving_verification_failed_retained",
            "bindings_sha256": bindings_sha256, "type": f"{type(error).__module__}.{type(error).__qualname__}",
            "message": str(error), "scientific_verification_certified": False,
            "no_resume_or_numerical_repair_attempted": True}))
        raise
