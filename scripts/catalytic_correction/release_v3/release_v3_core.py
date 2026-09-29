"""Separately pinned per-entry transport wiring over unchanged release-v2 gates.

This module imports only verified standard-library adapters. Science, original
workers and package operations are never run on import. Production invocations
need genuine complete proofs; fictional injection is explicit and CLI-inaccessible.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

RELEASE_V2_SHA = "9e567639359328d958e73c476a2d16ec8b0ab408e17c1fb016c37c3234713c1d"
RECEIVING_V1_SHA = "fe0662adacbf29bc356d7c19f7abd40b2b6304cb9f683673fce1e7ae39f1e1ba"
PER_ENTRY_SHA = "6670b27e78fb05f7c266cc52b72241a4b477f5d9a27213e8882bdcbd1038f366"
PER_ENTRY_REVIEW_SHA = "af971b9dc4b3a9e016110e3cf8cab4996dd5f0444ea0ab5009856a28744091d5"
IO_NAMES = {"location_core.py", "capture_at_location.py", "capture_original_at_location.py",
            "selected_at_locations.py", "run_selected_at_locations.py", "receiving_at_locations.py",
            "verify_restored_at_locations.py", "verification_io.py"}
STATIC_LAYOUT = {
    "release_v3_preparation": "code/correction/release_adapter_v3",
    "per_entry_io_preparation": "code/correction/per_entry_io_v1",
    "per_entry_io_review": "code/correction/per_entry_io_review_v1",
    "original_capture_preparation": "code/correction/original_capture_v1",
    "per_entry_location_plan": "execution/per_entry_io/location_plan.json",
    "per_entry_controller_capture": "execution/per_entry_io/controller_capture",
}
CAPTURE_OPERATION = "actual_per_entry_release_v3_child_capture"
OWN_NAMES = {"release_v3_core.py", "stage_corrected_extensions_v3.py",
             "capture_per_entry_source_v3.py", "verify_restored_correction_v3.py"}


def byte_sha(path: Path) -> str:
    """Return a file-byte digest without interpreting numerical content."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strict_json(raw: bytes) -> dict[str, Any]:
    """Refuse duplicate keys, nonfinite JSON literals and non-object carriers."""
    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in rows:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value
    def constant(value: str) -> None:
        raise ValueError("nonfinite JSON literal: " + value)
    result = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(result, dict):
        raise ValueError("JSON object required")
    return result


def checked_prepare(root: Path, expected: str) -> dict[str, Any]:
    """Verify receipt and every retained small preparation file before import."""
    if not root.is_absolute() or any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError("absolute unlinked preparation root required")
    receipt = root / "preparation_receipt.json"
    if receipt.is_symlink() or not receipt.is_file():
        raise ValueError("regular unlinked preparation receipt required")
    raw = receipt.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError("preparation receipt bytes differ")
    value = strict_json(raw)
    canonical = hashlib.sha256(json.dumps({k: v for k, v in value.items() if k != "content_sha256"},
        sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if value["content_sha256"] != canonical:
        raise ValueError("preparation content seal differs")
    for relative, pin in value["artifacts"].items():
        part = Path(relative)
        if part.is_absolute() or ".." in part.parts or str(part) != relative or relative in {"", "."}:
            raise ValueError("unsafe preparation member")
        path = root / part
        if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file():
            raise ValueError("linked/missing preparation member")
        member = path.read_bytes()
        if len(member) != pin["bytes"] or hashlib.sha256(member).hexdigest() != pin["sha256"]:
            raise ValueError("preparation member bytes differ")
    if byte_sha(receipt) != expected:
        raise ValueError("preparation changed before import")
    return value


def import_file(path: Path, expected: str, name: str) -> Any:
    """Load an exact verified stdlib adapter in an unoccupied private namespace."""
    if (not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents))
            or not path.is_file() or name in sys.modules or byte_sha(path) != expected):
        raise ValueError("adapter source/namespace differs")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("adapter loader unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
        if byte_sha(path) != expected:
            raise ValueError("adapter changed during import")
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def foundation() -> Any:
    """Load the byte-identical v2 foundation; no old provenance is rewritten."""
    name = "_release_v3_original_core"
    root = Path(__file__).absolute().parent / "preserved_release_v2"
    prepared = checked_prepare(root, RELEASE_V2_SHA)
    if name in sys.modules:
        module = sys.modules[name]
        if Path(module.__file__).absolute() != root / "release_core.py":
            raise ValueError("foundation namespace belongs to another path")
        return module
    io_path = root / "verification_io.py"
    pin = prepared["implementation_source_sha256"][io_path.name]
    if "verification_io" in sys.modules:
        old = sys.modules["verification_io"]
        if not getattr(old, "__file__", None) or byte_sha(Path(old.__file__)) != pin:
            raise ValueError("foreign I/O namespace")
    else:
        import_file(io_path, pin, "verification_io")
    return import_file(root / "release_core.py", prepared["implementation_source_sha256"]["release_core.py"], name)


def own_prepare(path: Path, digest: str) -> dict[str, Any]:
    """Bind v3 honestly; it never substitutes a new digest for a predecessor."""
    root = Path(__file__).absolute().parent
    if path != root / "preparation_receipt.json":
        raise ValueError("explicit executing v3 receipt required")
    prepared = checked_prepare(root, digest)
    if prepared["status"] != "corrected_release_per_entry_wiring_v3_prepared" or set(prepared["implementation_source_sha256"]) != OWN_NAMES:
        raise ValueError("separately named v3 source surface required")
    for name, pin in prepared["implementation_source_sha256"].items():
        if byte_sha(root / name) != pin:
            raise ValueError("v3 source bytes differ")
    return prepared


def io_prepare(root: Path) -> dict[str, Any]:
    """Bind exact eight new sources and distinct old receiving/selected maps."""
    prepared = checked_prepare(root, PER_ENTRY_SHA)
    if prepared["status"] != "original_reproduction_per_entry_io_adapter_prepared" or set(prepared["implementation_source_sha256"]) != IO_NAMES:
        raise ValueError("exact reviewed per-entry source surface required")
    if prepared["legacy_preparation_receipt_sha256"]["receiving"] != RECEIVING_V1_SHA:
        raise ValueError("old receiving preparation was replaced")
    return prepared


def receiving_argv(python: str, root: Path, bindings: dict[str, Any], plan: dict[str, Any], output: Path) -> list[str]:
    """Construct the honest new read-only command; never an execution controller."""
    return [python, "-I", "-B", str(root / "verify_restored_at_locations.py"),
            "--bindings", bindings["path"], "--bindings-sha256", bindings["sha256"],
            "--location-plan", plan["path"], "--location-plan-sha256", plan["sha256"],
            "--preparation-receipt", str(root / "preparation_receipt.json"), "--preparation-receipt-sha256", PER_ENTRY_SHA,
            "--output", str(output), "--python", python]


def controller_argv(python: str, root: Path, request: dict[str, Any]) -> list[str]:
    """Canonical source execution command; underlying legacy budgets/gates remain."""
    result = [python, "-I", "-B", str(root / "run_selected_at_locations.py"),
              "--selection", request["selection"]["path"], "--selection-sha256", request["selection"]["sha256"],
              "--location-plan", request["location_plan"]["path"], "--location-plan-sha256", request["location_plan"]["sha256"],
              "--preparation-receipt", str(root / "preparation_receipt.json"), "--preparation-receipt-sha256", PER_ENTRY_SHA,
              "--output", request["evidence_output"], "--python", python]
    reviews = request["reviews"]
    if set(reviews) != {"pilot-review", "resolution-review", "original-numerical-resolution"}:
        raise ValueError("exact optional original review roles required")
    for role in sorted(reviews):
        if reviews[role] is not None:
            item = reviews[role]
            if set(item) != {"path", "sha256"}:
                raise ValueError("explicit unchanged review binding required")
            result += ["--" + role, item["path"], "--" + role + "-sha256", item["sha256"]]
    return result


def source_summary(summary: dict[str, Any], request: dict[str, Any], prepared: dict[str, Any]) -> None:
    """Require actual completed scope and honest new source/plan identities."""
    core = foundation()
    core.require(summary["status"] == "corrected_selected_reproduction_restored_read_only_verified"
                 and summary["selection_sha256"] == request["selection_sha256"]
                 and summary["selected_pass_sha256"] == request["completed_pass"]["sha256"]
                 and summary["scheduled_selected_cells"] == summary["accounted_selected_cells"]
                 and summary["no_new_numerical_fit"] is True and summary["no_new_generator_recipe"] is True
                 and summary["location_plan_sha256"] == request["location_extension"]["location_plan"]["sha256"]
                 and summary["io_adapter_source_sha256"] == prepared["implementation_source_sha256"],
                 "actual read-only per-entry summary differs")


def process_capture(argv: list[str], prefix: Path, pins: Any, *, status: str, checked: Any,
                    entrypoint: Path, entrypoint_sha: str, producer: dict[str, Any],
                    invoke: Any = subprocess.run, test_only: bool = False) -> dict[str, Any]:
    """Retain genuine rc/raw bytes before publishing a separately typed v3 proof."""
    core = foundation()
    core.require(type(test_only) is bool and (invoke is subprocess.run or test_only), "injected subprocess cannot certify production")
    core.require(isinstance(argv, list) and len(argv) >= 4 and all(isinstance(item, str) for item in argv)
                 and argv[1:4] == ["-I", "-B", str(entrypoint)], "exact isolated child argv required")
    if test_only:
        runtime = {"test_only_dependency_injection": True, "locked_interpreter_samefile": False}
    else:
        actual_python = core.runtime(Path(argv[0]))
        core.require(str(actual_python) == argv[0], "exact resolved actual interpreter required")
        runtime = {"python_executable": argv[0], "locked_interpreter_samefile": True,
                   "numeric_thread_environment": {name: os.environ[name] for name in core.NUMERIC}}
    core.safe(prefix)
    core.require(prefix.parent.is_dir() and not prefix.exists() and not any(prefix.parent.glob(prefix.name + ".*")), "exclusive capture prefix required")
    pins.bind(entrypoint, entrypoint_sha)
    paths = {kind: prefix.with_name(prefix.name + suffix) for kind, suffix in
             (("stdout", ".stdout.log"), ("stderr", ".stderr.log"), ("attempt", ".attempt.json"), ("receipt", ".receipt.json"))}
    started, tick = datetime.now(UTC).isoformat(), time.monotonic()
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    for name in core.NUMERIC:
        environment[name] = "1"
    rc, error, stdout, stderr = None, None, b"", b""
    try:
        result = invoke(argv, capture_output=True, check=False, env=environment)
        rc, stdout, stderr = result.returncode, result.stdout, result.stderr
    except BaseException as caught:
        error = {"type": f"{type(caught).__module__}.{type(caught).__qualname__}", "message": str(caught)}
    core.require(isinstance(stdout, bytes) and isinstance(stderr, bytes), "raw bytes required")
    for kind, raw in (("stdout", stdout), ("stderr", stderr)):
        core.write_bytes_new(paths[kind], raw)
    actual = {"operation": CAPTURE_OPERATION, "argv": argv, "entrypoint": {"historical_path": str(entrypoint), "sha256": entrypoint_sha},
              "capture_producer": producer, "runtime": runtime, "exit_code": rc, "launch_error": error,
              "started_at_utc": started, "finished_at_utc": datetime.now(UTC).isoformat(), "wall_seconds": time.monotonic() - tick,
              "numeric_thread_environment": {name: environment[name] for name in core.NUMERIC},
              "stdout_path": str(paths["stdout"]), "stderr_path": str(paths["stderr"]),
              "stdout_sha256": core.sha(paths["stdout"]), "stderr_sha256": core.sha(paths["stderr"]),
              "test_only_dependency_injection": test_only, "no_success_inferred_from_self_written_receipts": True}
    core.write_new(paths["attempt"], core.seal(actual))
    core.require(type(rc) is int and rc == 0 and error is None, "actual failed child retained; no completion receipt")
    lines = stdout.splitlines()
    core.require(bool(lines), "actual factual stdout absent")
    summary = core.strict_json(lines[-1])
    checked(summary)
    pins.recheck()
    value = core.seal({"schema_version": 3, "status": status, "exit_code": rc, "summary": summary,
        "capture_producer": producer, "runtime": runtime, "stdout_path": actual["stdout_path"], "stderr_path": actual["stderr_path"],
        "stdout_sha256": actual["stdout_sha256"], "stderr_sha256": actual["stderr_sha256"],
        "invocation_attempt_sha256": core.sha(paths["attempt"]), "test_only_dependency_injection": test_only,
        "artifacts": {path.name: {"sha256": core.sha(path), "bytes": path.stat().st_size}
                      for kind, path in paths.items() if kind != "receipt"},
        "programme_complete": False, "scientific_method_or_visual_approval_conferred": False})
    core.write_new(paths["receipt"], value)
    core.require({p.name for p in prefix.parent.glob(prefix.name + ".*")} == {p.name for p in paths.values()}
                 and not any(prefix.parent.glob(".verification-pending-" + prefix.name + ".*")), "capture residue")
    pins.recheck()
    return {**value, "receipt_path": str(paths["receipt"]), "receipt_sha256": core.sha(paths["receipt"])}


def checked_command(path: Path, value: dict[str, Any], pins: Any, argv: list[str], entrypoint_sha: str,
                    producer: dict[str, Any], *, test_only: bool = False) -> dict[str, Any]:
    """Verify typed actual v3 command/producer; never rebrand it as old capture."""
    core = foundation()
    attempt = core.document(path.with_name(path.name.removesuffix(".receipt.json") + ".attempt.json"), pins,
                            value["invocation_attempt_sha256"])
    core.require(attempt["operation"] == CAPTURE_OPERATION and attempt["argv"] == argv
                 and attempt["entrypoint"] == {"historical_path": argv[3], "sha256": entrypoint_sha}
                 and type(attempt["exit_code"]) is int and attempt["exit_code"] == 0 and attempt["launch_error"] is None
                 and attempt["capture_producer"] == value["capture_producer"] == producer
                 and attempt["numeric_thread_environment"] == {name: "1" for name in core.NUMERIC}
                 and (attempt["test_only_dependency_injection"] is False and value["test_only_dependency_injection"] is False or test_only),
                 "actual new-command/source/runtime proof differs")
    core.require(attempt["runtime"] == value["runtime"], "actual capture runtime binding differs")
    if not test_only:
        core.require(attempt["runtime"] == {"python_executable": argv[0], "locked_interpreter_samefile": True,
                     "numeric_thread_environment": {name: "1" for name in core.NUMERIC}}, "actual new producer interpreter proof differs")
    pins.bind(Path(argv[3]), entrypoint_sha)
    return attempt


@contextmanager
def legacy_module(root: Path, name: str, facade: Any):
    """Own a temporary stdlib import alias; original files/maps remain immutable."""
    prepared = checked_prepare(root, RELEASE_V2_SHA)
    previous = sys.modules.get("release_core")
    alias = "_release_v3_delegate_" + name.removesuffix(".py")
    if alias in sys.modules:
        raise ValueError("delegate namespace occupied")
    sys.modules["release_core"] = facade
    try:
        module = import_file(root / name, prepared["implementation_source_sha256"][name], alias)
        yield module
    finally:
        sys.modules.pop(alias, None)
        if previous is None:
            sys.modules.pop("release_core", None)
        else:
            sys.modules["release_core"] = previous


class CoreView(ModuleType):
    """Forward original predicates; override only declared transport I/O seams."""

    def __init__(self, wiring: dict[str, Any], own: dict[str, Any], own_sha: str):
        super().__init__("_release_v3_core_view")
        self.base, self.wiring, self.own, self.own_sha = foundation(), wiring, own, own_sha
        self.extra = dict(STATIC_LAYOUT)
        for identity, roles in wiring["tree_roles"].items():
            if not identity or Path(identity).name != identity or ".." in Path(identity).parts or set(roles) != {"numerical", "capture"}:
                raise ValueError("exact separate tree roles required")
            if roles != {"numerical": "per_entry_numerical__" + identity, "capture": "per_entry_capture__" + identity}:
                raise ValueError("deterministic distinct per-entry role names required")
            self.extra[roles["numerical"]] = "evidence/per_entry_original_reproduction/" + identity
            self.extra[roles["capture"]] = "execution/per_entry_original_capture/" + identity
        if len(self.extra) != len(STATIC_LAYOUT) + 2 * len(wiring["tree_roles"]):
            raise ValueError("duplicate per-entry tree role")
        if set(self.extra) & set(self.base.LAYOUT):
            raise ValueError("new roles cannot replace old roles")
        self.LAYOUT = {**self.base.LAYOUT, **self.extra}
        self.roots: dict[str, Path] = {}
        self.extension: dict[str, Any] | None = None

    def __getattr__(self, name: str) -> Any:
        return getattr(self.base, name)

    def seal(self, value: dict[str, Any]) -> dict[str, Any]:
        """Add honest v3 metadata only to final stage/receiving publications."""
        if value.get("status") in {"corrected_private_payload_staged_with_separate_actual_source_gates",
                                   "corrected_private_restore_source_and_science_replay_verified"}:
            if self.extension is None:
                raise ValueError("complete v3 binding absent before publication")
            value = {**value, "per_entry_release_wiring_v3": self.extension,
                     "old_preparation_and_source_maps_replaced": False}
        return self.base.seal(value)

    def validate_assets(self, request: dict[str, Any], bindings: dict[str, Any], pins: Any) -> dict[str, Path]:
        """Run every old asset gate, then exact new whole-tree/plan roles."""
        core = self.base
        core.require(set(request["assets"]) - set(core.LAYOUT) == set(self.extra), "exact additional asset roles required")
        old = {**request, "assets": {k: v for k, v in request["assets"].items() if k in core.LAYOUT}}
        roots = core.validate_assets(old, bindings, pins)
        for role, target in self.extra.items():
            item = request["assets"][role]
            path = core.safe(Path(item["source"]))
            kind = "file" if role == "per_entry_location_plan" else "group" if role == "per_entry_controller_capture" else "tree"
            core.require(item["kind"] == kind and item["target"] == target, "extra role kind/location differs")
            if kind == "file":
                pins.bind(path, item["binding"]["sha256"], size=item["binding"]["bytes"])
            else:
                core.verify_tree(path, item["inventory"], pins)
                if kind == "group":
                    capture = Path(self.wiring["controller_capture"]["path"])
                    names = {capture.name.removesuffix(".receipt.json") + suffix for suffix in
                             (".stdout.log", ".stderr.log", ".attempt.json", ".receipt.json")}
                    core.require(capture.parent == path and set(item["inventory"]["files"]) == names
                                 and item["inventory"]["directories"] == [], "controller capture must be an exact flat four-file group")
            roots[role] = path
        core.require(roots["release_v3_preparation"] == Path(__file__).absolute().parent
                     and byte_sha(roots["release_v3_preparation"] / "preparation_receipt.json") == self.own_sha,
                     "actual v3 preparation omitted/substituted")
        io_prepare(roots["per_entry_io_preparation"])
        review = core.document(roots["per_entry_io_review"] / "receipt.json", pins, PER_ENTRY_REVIEW_SHA)
        core.artifact_map(roots["per_entry_io_review"], review["artifacts"], pins)
        core.require(review["target_preparation_receipt_sha256"] == PER_ENTRY_SHA
                     and review["engineering_review_only"] is True and review["one_of_five_scientific_root_approvals"] is False,
                     "source review cannot substitute scientific approvals")
        core.require(self.wiring["location_plan"] == {"path": str(roots["per_entry_location_plan"]),
                     "sha256": request["assets"]["per_entry_location_plan"]["binding"]["sha256"]}, "current plan role differs")
        self.roots, self.request, self.bindings = roots, request, bindings
        return roots

    def validate_reproduction(self, roots: dict[str, Path], request: dict[str, Any], bindings: dict[str, Any],
                              ids: list[str], pins: Any, policy: Any) -> dict[str, Any]:
        """Run unchanged completion gates, then independent per-entry documentary law."""
        core = self.base
        result = core.validate_reproduction(roots, request, bindings, ids, pins, policy)
        prepared = io_prepare(roots["per_entry_io_preparation"])
        plan_path = roots["per_entry_location_plan"]
        plan = core.document(plan_path, pins, self.wiring["location_plan"]["sha256"])
        core.require(self.wiring["revision"] == 3 and set(self.wiring["tree_roles"]) == set(plan["entry_locations"]),
                     "exact root-chosen location roles required")
        expected_legacy = {"selected": str(roots["reproduction_preparation"]),
                           "receiving": str(roots["receiving_reproduction_preparation"]),
                           "capture": str(roots["original_capture_preparation"])}
        core.require(plan["legacy_code_roots"] == expected_legacy
                     and plan["legacy_source_sha256"] == prepared["legacy_source_sha256"],
                     "historical predecessor roots/maps must retain their exact old roles")
        context, locations = self.load_locations(plan_path, plan, prepared, request, pins, policy)
        completed = core.document(core.child(roots["reproduction"], request["reproduction_pass"]["relative_path"]),
                                  pins, request["reproduction_pass"]["sha256"])
        core.require(completed["location_extension"] == locations.envelope(), "completed pass uses another current plan")
        records = {}
        for identity in result["selected_cells"]:
            record = core.document(roots["reproduction"] / "cells" / (identity + ".json"), pins)
            locations.verify_envelope(record["location_extension"], identity)
            core.require(record["reproduction_location"] == locations.metadata(identity), "record used another introducing plan/location")
            if identity in plan["entry_locations"]:
                core.require(record["status"] == "reused_verified_original_numerical_reproduction", "alternate path cannot replace changed/terminal route")
                proof = self.location_module.acquired(locations, identity, context["numerical"][identity])
                core.require(record["retained_per_entry_trees"] == proof, "actual completed capture/acquisition differs")
                for label, key in (("numerical", "retained_original_reproduction_tree"), ("capture", "retained_original_capture_tree")):
                    role = self.wiring["tree_roles"][identity][label]
                    expected_root = locations.actual(identity) if label == "numerical" else locations.resolve(plan["entry_locations"][identity]["capture_root"])
                    core.require(roots[role] == expected_root, "whole tree source is not its declared exact per-entry root")
                    expected = {"files": proof[key]["artifacts"], "directories": proof[key]["directories"]}
                    core.require(request["assets"][role]["inventory"] == expected, "whole per-entry files/directories omitted or changed")
                    core.verify_tree(roots[role], expected, pins)
                capture_receipt = core.document(locations.resolve(plan["entry_locations"][identity]["capture_root"]) / "capture_receipt.json", pins)
                core.require(capture_receipt["io_adapter_source_sha256"] == prepared["implementation_source_sha256"], "actual producer adapter source map differs")
            else:
                core.require(record["reproduction_location"] is None, "unchosen identity was moved")
            records[identity] = core.sha(roots["reproduction"] / "cells" / (identity + ".json"))
        history = {}
        for digest, node in locations.history.items():
            path = locations.resolve(node["historical_plan_path"])
            core.require(core.explicit_retention(path, digest, request, bindings), "current/prior plan omitted from payload")
            history[digest] = {"historical_path": node["historical_plan_path"], "sha256": digest}
        for path, digest in locations.pins.files.items():
            pins.bind(path, digest)
            core.require(core.explicit_retention(path, digest, request, bindings), "plan/review/preparation/acquisition evidence omitted")
        self.locations, self.context, self.io_prepared = locations, context, prepared
        self.check_controller(request, bindings, pins, result)
        locations.recheck()
        self.extension = {"revision": 3, "release_v3_preparation_sha256": self.own_sha,
            "per_entry_preparation_sha256": PER_ENTRY_SHA, "per_entry_independent_source_review_sha256": PER_ENTRY_REVIEW_SHA,
            "io_adapter_source_sha256": prepared["implementation_source_sha256"],
            "legacy_source_sha256": plan["legacy_source_sha256"], "legacy_receiving_preparation_sha256": RECEIVING_V1_SHA,
            "legacy_release_v2_preparation_sha256": RELEASE_V2_SHA,
            "location_plan": {"historical_path": plan["historical_plan_path"], "sha256": self.wiring["location_plan"]["sha256"]},
            "location_history": history, "tree_roles": self.wiring["tree_roles"],
            "source_controller_capture_sha256": self.wiring["controller_capture"]["sha256"],
            "source_controller_request_sha256": self.wiring["controller_request"]["sha256"],
            "source_readonly_capture_request_sha256": self.wiring["source_capture_request"]["sha256"],
            "completed_record_sha256": records, "old_historical_source_maps_rewritten": False,
            "new_scientific_approval_conferred": False}
        return result

    def load_locations(self, path: Path, plan: dict[str, Any], prepared: dict[str, Any], request: dict[str, Any],
                       pins: Any, policy: Any) -> tuple[Any, Any]:
        """Load unchanged input/source controllers for reading only; never run them."""
        root = self.roots["per_entry_io_preparation"]
        name = "location_core"
        if name in sys.modules:
            raise ValueError("location namespace occupied; fresh owned process required")
        loc = import_file(root / "location_core.py", prepared["implementation_source_sha256"]["location_core.py"], name)
        self.location_module = loc
        support = loc.import_pin(root / "selected_at_locations.py", prepared["implementation_source_sha256"]["selected_at_locations.py"],
                                 "_release_v3_location_context")
        selection_path = self.roots["reproduction"] / "selection.json"
        context = support.load_context(plan, selection_path, request["selection_sha256"], prepared)
        locations = loc.Locations(path, self.wiring["location_plan"]["sha256"], prepared,
            selection=context["selection"], selection_sha=request["selection_sha256"],
            scope_sha=context["rc"].scope_definition(context["selection"]), original=context["original"],
            inventory=context["inventory"], base=context["evidence"], freeze=context["freeze"])
        _, controller_request = self.base.record(self.wiring["controller_request"], pins)
        review = controller_request["reviews"]["original-numerical-resolution"]
        context["numerical"] = context["legacy"].numerical_inventory(context["common"], context["rc"], context["selection"],
            context["evidence"], None if review is None else Path(review["path"]), None if review is None else review["sha256"])
        return context, locations

    def producer(self, mode: str, request_binding: dict[str, Any], io_root: Path, plan_binding: dict[str, Any],
                 *, helper: str = "capture_per_entry_source_v3.py") -> dict[str, Any]:
        """Explicit additional v3 producer identity; old maps retain old bytes."""
        own_root = Path(__file__).absolute().parent
        return {"revision": 3, "mode": mode,
            "entrypoint": {"historical_path": str(own_root / helper), "sha256": self.own["implementation_source_sha256"][helper]},
            "preparation_receipt": {"historical_path": str(own_root / "preparation_receipt.json"), "sha256": self.own_sha},
            "implementation_source_sha256": {str(own_root / k): v for k, v in self.own["implementation_source_sha256"].items()},
            "request": request_binding, "io_preparation": {"path": str(io_root / "preparation_receipt.json"), "sha256": PER_ENTRY_SHA},
            "location_plan": plan_binding}

    def check_controller(self, request: dict[str, Any], bindings: dict[str, Any], pins: Any, result: dict[str, Any]) -> None:
        """Require a genuine new-controller call; a pass cannot manufacture its rc."""
        core = self.base
        path, value = core.record(self.wiring["controller_capture"], pins)
        core.capture_record(path, self.wiring["controller_capture"]["sha256"], pins,
                            status="per_entry_selected_controller_actual_rc0_captured", summary_status="all_selected_reproduction_outcomes_accounted")
        req_path, captured_request = core.record(self.wiring["controller_request"], pins)
        core.require(core.explicit_retention(req_path, self.wiring["controller_request"]["sha256"], request, bindings), "actual controller request omitted")
        self.check_capture_request(captured_request, "controller", path)
        _, readonly_bindings = core.record(request["source_reproduction_bindings"], pins)
        review_keys = {"pilot-review": "pilot", "resolution-review": "original_resolution", "original-numerical-resolution": "original_numerical_resolution"}
        for old_key, receiving_key in review_keys.items():
            item = captured_request["reviews"].get(old_key)
            expected = None if item is None else {"historical_path": item["path"], "sha256": item["sha256"]}
            core.require(readonly_bindings["reviews"].get(receiving_key) == expected, "controller and read-only review acquisitions differ")
        core.require(captured_request["location_plan"] == self.wiring["location_plan"]
                     and captured_request["selection"] == {"path": str(self.roots["reproduction"] / "selection.json"), "sha256": request["selection_sha256"]}
                     and captured_request["evidence_output"] == str(self.roots["reproduction"]), "controller used different frozen inputs/output")
        summary = value["summary"]
        pass_path = core.child(self.roots["reproduction"], request["reproduction_pass"]["relative_path"])
        core.require(summary["pass_receipt_path"] == str(pass_path) and summary["pass_receipt_sha256"] == result["pass_sha256"]
                     and summary["selection_sha256"] == request["selection_sha256"], "controller stdout does not bind actual completed pass")
        actual_pass = core.document(pass_path, pins, result["pass_sha256"])
        core.require(actual_pass["location_extension"] == self.locations.envelope(), "actual pass has a foreign location envelope")
        attempt = core.document(path.with_name(path.name.removesuffix(".receipt.json") + ".attempt.json"), pins)
        root = self.roots["per_entry_io_preparation"]
        argv = controller_argv(attempt["argv"][0], root, captured_request)
        checked_command(path, value, pins, argv, self.io_prepared["implementation_source_sha256"]["run_selected_at_locations.py"],
                        self.producer("controller", self.wiring["controller_request"], root, self.wiring["location_plan"]))

    def captured_command(self, path: Path, value: dict[str, Any], pins: Any, **kwargs: Any) -> dict[str, Any]:
        """Redirect only the declared new read-only source gate, explicitly typed."""
        if Path(kwargs["entrypoint"]).name != "verify_restored_reproduction.py":
            return self.base.captured_command(path, value, pins, **kwargs)
        core = self.base
        request_binding = self.wiring["source_capture_request"]
        req_path, source_request = core.record(request_binding, pins)
        self.check_capture_request(source_request, "read_only", path)
        core.require(core.explicit_retention(req_path, request_binding["sha256"], self.request, self.bindings), "actual read-only capture request omitted")
        core.require(source_request["mode"] == "read_only" and source_request["location_plan"] == self.wiring["location_plan"], "new source-capture request differs")
        binding = source_request["input_request"]
        expected_options = ["--bindings", binding["path"], "--bindings-sha256", binding["sha256"],
                            "--output", source_request["evidence_output"], "--python", kwargs["options"][-1]]
        core.require(kwargs["options"] == expected_options and Path(kwargs["entrypoint"]) == self.roots["receiving_reproduction_preparation"] / "verify_restored_reproduction.py",
                     "legacy read-only gate cannot be widened")
        _, source_bindings = core.record(binding, pins)
        core.require(binding == self.request["source_reproduction_bindings"]
                     and source_request["evidence_output"] == str(self.roots["source_reproduction_review"]), "source read-only roles were substituted")
        self.check_receiving_bindings(source_bindings, self.wiring["location_plan"], self.roots["receiving_reproduction_preparation"], self.io_prepared)
        source_summary(value["summary"], source_bindings, self.io_prepared)
        argv = receiving_argv(kwargs["options"][-1], self.roots["per_entry_io_preparation"], binding,
                              self.wiring["location_plan"], Path(source_request["evidence_output"]))
        pins.bind(req_path, request_binding["sha256"])
        return checked_command(path, value, pins, argv, self.io_prepared["implementation_source_sha256"]["verify_restored_at_locations.py"],
                               self.producer("read_only", request_binding, self.roots["per_entry_io_preparation"], self.wiring["location_plan"]))

    def check_capture_request(self, request: dict[str, Any], mode: str, capture: Path) -> None:
        """Require the exact additional producer request, preserving old bindings."""
        self.base.require(request["schema_version"] == 3 and request["status"] == "per_entry_release_v3_source_capture_request"
                          and request["test_only"] is False and request["mode"] == mode
                          and request["io_preparation"] == {"path": str(self.roots["per_entry_io_preparation"] / "preparation_receipt.json"), "sha256": PER_ENTRY_SHA}
                          and Path(request["capture_prefix"]) == capture.with_name(capture.name.removesuffix(".receipt.json")),
                          "genuine separately versioned capture request differs")

    def check_receiving_bindings(self, value: dict[str, Any], plan: dict[str, Any], receiving_root: Path,
                                prepared: dict[str, Any]) -> None:
        """Old maps and explicit new receiving code/plan remain separate."""
        core = self.base
        legacy = prepared["legacy_source_sha256"]
        actual_plan = core.document(Path(plan["path"]), core.Pins(), plan["sha256"])
        core.require(value["reproduction_source_sha256"] == legacy["selected"]
                     and value["receiving_source_sha256"] == legacy["receiving"]
                     and value["location_receiving_code"] == str(receiving_root)
                     and value["location_extension"] == {"location_plan": {"historical_path": actual_plan["historical_plan_path"], "sha256": plan["sha256"]},
                         "io_adapter_source_sha256": prepared["implementation_source_sha256"]}, "honest old/new receiving bindings differ")


class ReceivingView(CoreView):
    """Only replace the prospective read-only child command; delegate all replays."""

    def __init__(self, wiring: dict[str, Any], own: dict[str, Any], own_sha: str,
                 manifest: dict[str, Any], restored: Path, request_binding: dict[str, Any]):
        super().__init__(wiring, own, own_sha)
        self.manifest, self.restored, self.request_binding = manifest, restored, request_binding
        self.extension = manifest["per_entry_release_wiring_v3"]
        if self.extension["revision"] != 3 or self.extension["per_entry_preparation_sha256"] != PER_ENTRY_SHA:
            raise ValueError("explicit separately staged v3 extension required")
        if wiring["tree_roles"] != self.extension["tree_roles"] or wiring["location_plan"]["sha256"] != self.extension["location_plan"]["sha256"]:
            raise ValueError("receiving plan/tree roles differ from actual stage")
        if (self.extension["release_v3_preparation_sha256"] != own_sha
                or self.extension["per_entry_independent_source_review_sha256"] != PER_ENTRY_REVIEW_SHA
                or self.extension["legacy_receiving_preparation_sha256"] != RECEIVING_V1_SHA
                or self.extension["legacy_release_v2_preparation_sha256"] != RELEASE_V2_SHA
                or self.extension["old_historical_source_maps_rewritten"] is not False):
            raise ValueError("restored version law differs from its actual stage")

    def capture_process(self, argv: list[str], prefix: Path, pins: Any, **kwargs: Any) -> dict[str, Any]:
        """Record the actual new command, while original mixed/report IO is intact."""
        old_script = self.restored / self.base.LAYOUT["receiving_reproduction_preparation"] / "verify_restored_reproduction.py"
        if kwargs["entrypoint"] != old_script:
            return self.base.capture_process(argv, prefix, pins, **kwargs)
        expected = [argv[0], "-I", "-B", str(old_script), "--bindings", argv[5], "--bindings-sha256", argv[7],
                    "--output", str(prefix.parent / "reproduction_review"), "--python", argv[0]]
        self.base.require(argv == expected, "original receiver seam differs; no other command may change")
        root = self.restored / STATIC_LAYOUT["per_entry_io_preparation"]
        prepared = io_prepare(root)
        self.base.require(prepared["implementation_source_sha256"] == self.extension["io_adapter_source_sha256"]
                          and prepared["legacy_source_sha256"] == self.extension["legacy_source_sha256"],
                          "restored new/old source maps differ from actual stage")
        for name, digest in prepared["implementation_source_sha256"].items():
            pins.bind(root / name, digest)
        pins.bind(root / "preparation_receipt.json", PER_ENTRY_SHA)
        binding = {"path": argv[5], "sha256": argv[7]}
        _, value = self.base.record(binding, pins)
        plan = self.wiring["location_plan"]
        self.base.require(Path(plan["path"]) == self.restored / STATIC_LAYOUT["per_entry_location_plan"], "current restored plan is not its exact staged role")
        self.check_receiving_bindings(value, plan, old_script.parent, prepared)
        self.check_restored_maps(value)
        actual = receiving_argv(argv[0], root, binding, plan, prefix.parent / "reproduction_review")
        def checked(summary: dict[str, Any]) -> None:
            kwargs["validate_summary"](summary)
            source_summary(summary, value, prepared)
        producer = self.producer("remote_read_only", self.request_binding, root, plan,
                                 helper="verify_restored_correction_v3.py")
        return process_capture(actual, prefix, pins, status=kwargs["status"], checked=checked,
            entrypoint=root / "verify_restored_at_locations.py", entrypoint_sha=prepared["implementation_source_sha256"]["verify_restored_at_locations.py"],
            producer=producer, invoke=kwargs.get("invoke", subprocess.run), test_only=kwargs.get("invoke", subprocess.run) is not subprocess.run)

    def check_restored_maps(self, value: dict[str, Any]) -> None:
        """Require exact whole-directory tuples, including every alternate tree."""
        pairs = {(row["historical"], row["restored"], row["kind"]) for row in value["path_map"]}
        self.base.require(len(pairs) == len(value["path_map"]), "duplicate restored map carrier")
        for roles in self.extension["tree_roles"].values():
            for role in roles.values():
                stored = self.manifest["historical_roots"][role]
                expected = (stored["historical_source"], str(self.restored / stored["payload_relative"]), "directory")
                self.base.require(expected in pairs, "alternate numerical/capture whole-directory map omitted")
        for role in ("per_entry_io_preparation", "original_capture_preparation", "receiving_reproduction_preparation"):
            stored = self.manifest["historical_roots"][role]
            self.base.require((stored["historical_source"], str(self.restored / stored["payload_relative"]), "directory") in pairs,
                              "separately pinned preparation directory mapping omitted")


def source_capture(request: dict[str, Any], request_binding: dict[str, Any], python: Path,
                   own: dict[str, Any], own_sha: str, *, invoke: Any = subprocess.run,
                   test_only: bool = False) -> dict[str, Any]:
    """Capture one declared new controller or receiving CLI; no science on import."""
    core = foundation()
    core.require(type(test_only) is bool and (invoke is subprocess.run or test_only), "injection is test-only")
    core.require(request["schema_version"] == 3 and request["status"] == "per_entry_release_v3_source_capture_request"
                 and request["test_only"] is False and request["mode"] in {"read_only", "controller"}, "explicit source-capture mode required")
    root = core.safe(Path(request["io_preparation"]["path"])).parent
    core.require(request["io_preparation"]["sha256"] == PER_ENTRY_SHA, "new preparation cannot replace historical sources")
    core.require(Path(request["io_preparation"]["path"]).name == "preparation_receipt.json", "exact new preparation filename required")
    prepared = io_prepare(root)
    pins = core.Pins()
    _, current_plan = core.record(request["location_plan"], pins)
    pins.bind(Path(request_binding["path"]), request_binding["sha256"])
    pins.bind(root / "preparation_receipt.json", PER_ENTRY_SHA)
    own_root = Path(__file__).absolute().parent
    if not test_only:
        own_prepare(own_root / "preparation_receipt.json", own_sha)
        pins.bind(own_root / "preparation_receipt.json", own_sha)
    for name, digest in prepared["implementation_source_sha256"].items():
        pins.bind(root / name, digest)
    for name, digest in own["implementation_source_sha256"].items():
        pins.bind(own_root / name, digest)
    immutable = [core.safe(Path(p)) for p in request["immutable_roots"] + request["immutable_files"]]
    immutable += [root, Path(__file__).absolute().parent, Path(request_binding["path"]), Path(request["location_plan"]["path"])]
    prefix, output = core.safe(Path(request["capture_prefix"])), core.safe(Path(request["evidence_output"]))
    core.no_overlap(prefix, [*immutable, output])
    view = CoreView({"tree_roles": {}}, own, own_sha)
    mode = request["mode"]
    if mode == "read_only":
        core.no_overlap(output, immutable)
        input_path, inputs = core.record(request["input_request"], pins)
        core.no_overlap(prefix, [input_path])
        expected_paths = [Path(row["root"]) for row in inputs["immutable_roots"]] + [Path(row["path"]) for row in inputs["immutable_files"]]
        core.require(all(any(p == parent or p.is_relative_to(parent) for parent in immutable) for p in expected_paths), "receiving immutable roles omitted from overlap protection")
        core.no_overlap(output, [input_path])
        core.require(not output.exists(), "read-only receiving proof output must be new")
        view.check_receiving_bindings(inputs, request["location_plan"], Path(inputs["location_receiving_code"]), prepared)
        argv = receiving_argv(str(python), root, request["input_request"], request["location_plan"], output)
        def checked(summary: dict[str, Any]) -> None:
            source_summary(summary, inputs, prepared)
        helper, status = "verify_restored_at_locations.py", "corrected_readonly_reproduction_actual_rc0_captured"
    else:
        core.require(output.parent.is_dir() and (not output.exists() or output.is_dir())
                     and all(not output.is_relative_to(p) and not p.is_relative_to(output) for p in immutable),
                     "controller output overlaps immutable inputs or is not a directory")
        selection_path, selection = core.record(request["selection"], pins)
        core.require(all(any(Path(p) == parent or Path(p).is_relative_to(parent) for parent in immutable)
                         for p in selection["paths"].values()), "controller immutable input roles omitted")
        for item in request["reviews"].values():
            if item is not None:
                review_path, _ = core.record(item, pins)
                core.no_overlap(prefix, [review_path])
                core.require(not output.is_relative_to(review_path) and not review_path.is_relative_to(output),
                             "controller output overlaps its immutable review")
        core.no_overlap(prefix, [selection_path])
        argv = controller_argv(str(python), root, request)
        helper, status = "run_selected_at_locations.py", "per_entry_selected_controller_actual_rc0_captured"
        def checked(summary: dict[str, Any]) -> None:
            core.require(summary["status"] == "all_selected_reproduction_outcomes_accounted"
                         and summary["selection_sha256"] == request["selection"]["sha256"],
                         "pending/foreign controller pass cannot certify completion")
            pass_path = core.safe(Path(summary["pass_receipt_path"]))
            core.require(pass_path.parent == output / "passes", "completed pass escaped controller output")
            actual_pass = core.document(pass_path, pins, summary["pass_receipt_sha256"])
            expected_extension = {"location_plan_path": current_plan["historical_plan_path"],
                "location_plan_sha256": request["location_plan"]["sha256"], "io_adapter_source_sha256": prepared["implementation_source_sha256"],
                "legacy_source_sha256": prepared["legacy_source_sha256"], "selection_bytes_rewritten": False}
            core.require(actual_pass["location_extension"] == expected_extension
                         and actual_pass["status"] == summary["status"]
                         and actual_pass["selection_sha256"] == summary["selection_sha256"],
                         "actual completed pass has another source/plan envelope")
    producer = view.producer(mode, request_binding, root, request["location_plan"])
    captured = process_capture(argv, prefix, pins, status=status, checked=checked,
        entrypoint=root / helper, entrypoint_sha=prepared["implementation_source_sha256"][helper],
        producer=producer, invoke=invoke, test_only=test_only)
    if mode == "read_only":
        proof = core.document(output / "receipt.json", pins, captured["summary"]["receipt_sha256"])
        core.require(captured["summary"]["receipt_path"] == str(output / "receipt.json")
                     and proof["status"] == captured["summary"]["status"]
                     and proof["bindings_sha256"] == request["input_request"]["sha256"]
                     and proof["selection_sha256"] == inputs["selection_sha256"]
                     and proof["completed_pass_sha256"] == inputs["completed_pass"]["sha256"]
                     and proof["new_numerical_fit_executed"] is False and proof["new_generator_recipe_executed"] is False
                     and proof["test_only_dependency_injection"] is False and proof["io_adapter_source_sha256"] == prepared["implementation_source_sha256"],
                     "actual source receiver proof absent/synthetic")
        core.declared_output_tree(output, proof, pins)
    pins.recheck()
    return {"status": status, "receipt_path": captured["receipt_path"], "receipt_sha256": captured["receipt_sha256"],
            "programme_complete": False, "new_scientific_approval_conferred": False}
