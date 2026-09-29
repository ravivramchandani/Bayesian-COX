"""Portable private imports for the exact sealed release-v3 fictional guards.

The full 233-member carrier is verified and copied only into a disposable small
source fixture. All 32 original method objects are inherited without rewriting.
Public aliases and interpreter globals exist only inside restored scopes.
"""

from __future__ import annotations

import ast
import atexit
import hashlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

PREPARATION_SHA = "5ded4445b5a1488e0ab02a4eadbab43a8159e422a385918a2551e1989d0b5034"
TEST_SOURCE_SHA = "ce1d916b82eccb4769c495491450a83cbb62bba57df0b18842e05a039b6797a8"
SOURCE_SHA = {
    "release_v3_core.py": "448c32dde298b98ba75218df1b5c6a9a0a09c3e85fa8108d06e38f11ce206068",
    "stage_corrected_extensions_v3.py": "91d0430405ec0841c3b1b37d85567c2a0c92abf5585addf2d7bad29d6b75acd4",
    "capture_per_entry_source_v3.py": "c58a66cc22e668fc2377530d114ed16fceb07f58f23cc2b5df0d385ee89412ae",
    "verify_restored_correction_v3.py": "9c6f5372edb32b937f2a8e926fad62a5d75ea1f1f7477dad0a78803d0ee11dea",
}
LEGACY_SHA = {
    "release_v2": "9e567639359328d958e73c476a2d16ec8b0ab408e17c1fb016c37c3234713c1d",
    "receiving_v1": "fe0662adacbf29bc356d7c19f7abd40b2b6304cb9f683673fce1e7ae39f1e1ba",
    "per_entry_io_v1": "6670b27e78fb05f7c266cc52b72241a4b477f5d9a27213e8882bdcbd1038f366",
}
PUBLIC_ALIASES = frozenset({
    "release_v3_core", "stage_corrected_extensions_v3", "capture_per_entry_source_v3",
    "verify_restored_correction_v3", "release_core", "verification_io", "_release_v3_original_core",
    "_release_v3_delegate_stage_corrected_extensions", "_release_v3_delegate_verify_restored_correction",
})
SCIENCE_PREFIXES = ("src", "numpy", "scipy", "arviz", "pymc", "pytensor", "sksurv", "lifelines", "torch", "jax")


def require(value: Any, message: str) -> None:
    """Refuse absent or changed source-only test evidence without skipping."""
    if not value:
        raise ValueError(message)


def sha(path: Path) -> str:
    """Digest one absolute regular unlinked source/metadata file."""
    require(path.is_absolute() and not any(p.is_symlink() for p in (path, *path.parents)), "absolute unlinked member required")
    require(path.is_file(), "regular source/metadata member required")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    """Use the original content-seal JSON convention for small metadata."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def document(path: Path, expected: str) -> dict[str, Any]:
    """Bind exact bytes/content and refuse duplicate or nonfinite JSON fields."""
    require(sha(path) == expected, "document byte binding differs")
    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            require(key not in result, "duplicate JSON field")
            result[key] = value
        return result
    def nonfinite(value: str) -> None:
        raise ValueError("nonfinite JSON literal " + value)
    value = json.loads(path.read_bytes(), object_pairs_hook=pairs, parse_constant=nonfinite)
    require(isinstance(value, dict) and value["content_sha256"] == canonical({k: v for k, v in value.items() if k != "content_sha256"}), "document content seal differs")
    require(sha(path) == expected, "document changed while read")
    return value


def method_surface(source: Path) -> dict[str, str]:
    """Return the unchanged 32 original test-method AST digests."""
    path = source / "test_release_v3.py"
    require(sha(path) == TEST_SOURCE_SHA, "original test source changed")
    classes = [n for n in ast.parse(path.read_bytes()).body if isinstance(n, ast.ClassDef)]
    require(len(classes) == 1 and classes[0].name == "Fixture", "original class surface changed")
    methods = {n.name: hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest()
               for n in classes[0].body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}
    require(len(methods) == 32, "all 32 original test methods required")
    return methods


def validate_surface(source: Path) -> dict[str, Any]:
    """Verify exact four runtime sources and all 232 artifacts/233 carrier files."""
    require(source.is_absolute() and source.is_dir() and not any(p.is_symlink() for p in (source, *source.parents)), "absolute unlinked complete source carrier required")
    value = document(source / "preparation_receipt.json", PREPARATION_SHA)
    require(value["status"] == "corrected_release_per_entry_wiring_v3_prepared"
            and value["implementation_source_sha256"] == SOURCE_SHA
            and value["unchanged_preparation_receipt_sha256"] == LEGACY_SHA
            and value["actual_location_plan_or_missing_producer_subset_approved"] is False
            and value["actual_numerical_scientific_producer_receiver_qa_stage_package_download_restore_or_publication_invoked"] is False,
            "honest separately prepared source surface differs")
    artifacts = value["artifacts"]
    require(len(artifacts) == value["artifact_count_excluding_receipt"] == 232
            and value["archive_member_count_including_receipt"] == 233, "full carrier counts differ")
    expected = set(artifacts) | {"preparation_receipt.json"}
    files, directories = set(), []
    for path in source.rglob("*"):
        require(not path.is_symlink() and (path.is_file() or path.is_dir()), "unsafe source carrier member")
        if path.is_file():
            files.add(str(path.relative_to(source)))
        else:
            directories.append(str(path.relative_to(source)))
    require(files == expected and sorted(directories) == value["directories"], "complete carrier file/directory roster differs")
    require((source / "archive_members.txt").read_text().splitlines() == sorted(expected), "complete 233-member archive roster differs")
    for relative, pin in artifacts.items():
        member = Path(relative)
        require(not member.is_absolute() and ".." not in member.parts and str(member) == relative and relative not in {"", "."}, "unsafe carrier artifact")
        path = source / member
        require(type(pin["bytes"]) is int and pin["bytes"] >= 0
                and sha(path) == pin["sha256"] and path.stat().st_size == pin["bytes"], "carrier artifact byte binding differs")
    require(all(sha(source / name) == pin for name, pin in SOURCE_SHA.items()), "exact runtime source changed")
    method_surface(source)
    require(sha(source / "preparation_receipt.json") == PREPARATION_SHA, "preparation changed before return")
    return value


def configured(test_file: Path) -> Path:
    """Resolve the adopted repository-relative carrier; no machine-path fallback."""
    repo = Path(os.environ.get("BAYES_COX_RELEASE_V3_TEST_REPOSITORY_ROOT", str(test_file.absolute().parents[1]))).absolute()
    return Path(os.environ.get("BAYES_COX_RELEASE_V3_TEST_SOURCE_ROOT", str(repo / "scripts/catalytic_correction/release_v3"))).absolute()


def fixture_parent() -> Path | None:
    """An explicit prep-only scratch override bounds all temporary source copies."""
    supplied = os.environ.get("BAYES_COX_RELEASE_V3_TEST_FIXTURE_ROOT")
    if supplied is None:
        return None
    path = Path(supplied).absolute()
    require(path.is_dir() and not any(p.is_symlink() for p in (path, *path.parents)), "absolute unlinked test scratch directory required")
    return path


def science_names() -> set[str]:
    """Compare imported scientific names with the pre-existing process state."""
    return {name for name in sys.modules if any(name == p or name.startswith(p + ".") for p in SCIENCE_PREFIXES)}


class ImportedGuards:
    """Private unchanged modules and one disposable 1.69MB source/log carrier."""

    def __init__(self, source: Path) -> None:
        self.source, self.preparation = source, validate_surface(source)
        self.original_methods = method_surface(source)
        self.temporary = tempfile.TemporaryDirectory(prefix="fictional-release-v3-carrier-", dir=fixture_parent())
        self.carrier = Path(self.temporary.name).resolve() / "release_v3"
        self.private: dict[str, Any] = {}
        self.aliases: dict[str, Any] = {}
        self.closed = False
        self.prefix = "_portable_release_v3_" + uuid.uuid4().hex
        before_science = science_names()
        before_aliases = {name: sys.modules.get(name) for name in PUBLIC_ALIASES}
        before_path, before_bytecode = list(sys.path), sys.dont_write_bytecode
        try:
            shutil.copytree(source, self.carrier)
            require(validate_surface(self.carrier) == self.preparation, "small source carrier round-trip differs")
            io_path = self.carrier / "preserved_release_v2" / "verification_io.py"
            self.io = self._import(io_path, self.preparation["artifacts"][str(io_path.relative_to(self.carrier))]["sha256"], "io")
            self.aliases["verification_io"] = self.io
            base_path = self.carrier / "preserved_release_v2" / "release_core.py"
            self.base = self._import(base_path, self.preparation["artifacts"][str(base_path.relative_to(self.carrier))]["sha256"], "base")
            self.aliases["_release_v3_original_core"] = self.base
            self.runtime = self._import(self.carrier / "release_v3_core.py", SOURCE_SHA["release_v3_core.py"], "runtime")
            self.aliases["release_v3_core"] = self.runtime
            self.entrypoints = {}
            for name in sorted(set(SOURCE_SHA) - {"release_v3_core.py"}):
                self.entrypoints[name] = self._import(self.carrier / name, SOURCE_SHA[name], name.removesuffix(".py"))
            self.tests = self._import(self.carrier / "test_release_v3.py", TEST_SOURCE_SHA, "original_tests")
            self.original_classes = [candidate for candidate in vars(self.tests).values() if isinstance(candidate, type)
                and issubclass(candidate, unittest.TestCase) and candidate.__module__ == self.tests.__name__]
            methods = [(cls.__name__, name) for cls in self.original_classes for name in unittest.defaultTestLoader.getTestCaseNames(cls)]
            require(len(self.original_classes) == 1 and len(methods) == len(set(methods)) == 32, "original methods missing or duplicate collection possible")
            require(science_names() == before_science, "private guard import introduced scientific modules")
            require(all(sys.modules.get(name) is before_aliases[name] for name in PUBLIC_ALIASES), "public aliases leaked at collection")
            require(sys.path == before_path and sys.dont_write_bytecode == before_bytecode, "interpreter globals leaked at collection")
            self.runtime.own_prepare(self.carrier / "preparation_receipt.json", PREPARATION_SHA)
            require(validate_surface(source) == self.preparation and validate_surface(self.carrier) == self.preparation,
                    "source preparation changed during private import")
        except BaseException:
            self.close()
            raise
        atexit.register(self.close)

    def _import(self, path: Path, expected: str, role: str) -> Any:
        """Import source bytes only under a fresh owned private name."""
        name = self.prefix + "_" + role
        require(name not in sys.modules and sha(path) == expected, "private source/namespace differs")
        spec = importlib.util.spec_from_file_location(name, path)
        require(spec is not None and spec.loader is not None, "private stdlib source loader unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.private[name] = module
        with patch.object(sys, "dont_write_bytecode", True), patch.object(sys, "path", list(sys.path)), patch.dict(sys.modules, self.aliases):
            spec.loader.exec_module(module)
        require(sha(path) == expected, "source changed during private import")
        return module

    @contextmanager
    def scope(self):
        """Restore all temporary public names and interpreter globals after a test."""
        aliases = {name: sys.modules.get(name) for name in PUBLIC_ALIASES}
        before_science = science_names()
        before_path, before_bytecode = list(sys.path), sys.dont_write_bytecode
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, "dont_write_bytecode", True))
            stack.enter_context(patch.object(sys, "path", list(sys.path)))
            stack.enter_context(patch.dict(sys.modules, self.aliases))
            yield
        require(all(sys.modules.get(name) is aliases[name] for name in PUBLIC_ALIASES), "public aliases leaked after test")
        require(sys.path == before_path and sys.dont_write_bytecode == before_bytecode, "interpreter globals leaked after test")
        require(science_names() == before_science, "fixture introduced scientific imports")

    def export(self, namespace: dict[str, Any]) -> None:
        """One inherited class exports each unchanged original method exactly once."""
        imported = self
        class ScopedRun:
            def run(self, result=None):
                try:
                    with imported.scope():
                        return super().run(result)
                finally:
                    temporary = getattr(self, "temporary", None)
                    if temporary is not None:
                        temporary.cleanup()
        for original in self.original_classes:
            name = "TestRetainedReleaseV3" + original.__name__
            require(name not in namespace, "original class exported twice")
            exported = type(name, (ScopedRun, original), {"__module__": namespace["__name__"]})
            for method in unittest.defaultTestLoader.getTestCaseNames(original):
                require(getattr(exported, method) is getattr(original, method), "an original method was rewritten")
            namespace[name] = exported

    def report(self) -> dict[str, Any]:
        """Report source-only portability; never scientific production completion."""
        require(validate_surface(self.source) == self.preparation and validate_surface(self.carrier) == self.preparation,
                "original or small source fixture differs")
        return {"status": "release_v3_complete_carrier_private_import_verified", "preparation_sha256": PREPARATION_SHA,
            "runtime_source_sha256": SOURCE_SHA, "original_test_source_sha256": TEST_SOURCE_SHA,
            "complete_carrier_members": 233, "bound_artifacts": 232, "original_method_count": 32,
            "original_method_ast_sha256": self.original_methods, "entrypoints_imported_without_dispatch": sorted(self.entrypoints),
            "public_aliases_leaked": False, "interpreter_globals_leaked": False, "new_scientific_modules_loaded": False,
            "actual_plan_scientific_source_receiving_producer_or_transfer_invoked": False,
            "original_source_modified": False, "root_adoption_or_approval_conferred": False}

    def close(self) -> None:
        """Delete only the owned small source fixture and owned private module names."""
        if self.closed:
            return
        self.closed = True
        for name, module in self.private.items():
            if sys.modules.get(name) is module:
                sys.modules.pop(name)
        self.temporary.cleanup()
        atexit.unregister(self.close)
