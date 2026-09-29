"""Portable private imports for reviewed fictional per-entry I/O guards.

Only source/preparation and ordinary fixture bytes are read. No original
scientific helper, capture dispatcher or reproduction controller is invoked.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

PREPARATION_SHA = "6670b27e78fb05f7c266cc52b72241a4b477f5d9a27213e8882bdcbd1038f366"
SOURCE_SHA = {
    "location_core.py": "e2103480646cb5f26d30e0fbab6a740e53ba52778616c08c0b30fb5fb4cd17f0",
    "capture_at_location.py": "6eac7cda2a452552ee1e9c3b3aa9ee5909601729a841a75844eea43e9d43ff8d",
    "capture_original_at_location.py": "2a482751500025c73f7204c280f8e897d786eec54513520acca43adbd57cb8fe",
    "selected_at_locations.py": "4c26d2ede68554aee6ad80af3b372a5f5d09e6fb78525dcb0846c294ae7156dd",
    "run_selected_at_locations.py": "d444de262d568107db6a822a6c37142e81249810fa5f75e9d947902730fcd616",
    "receiving_at_locations.py": "6c56ceb15b19cc19204bf5139c7c9bbb28cb156faed5a5767e18ec53b6ad14b3",
    "verify_restored_at_locations.py": "e8e51e236d96687c549219091d6b2ca89e9c9a219cf49b48481c6485b51b525f",
    "verification_io.py": "389c09c0b4f151adf754d20b3c21b2cdd0fa6809bcc4cd78dda470739d2ea3b8",
    "fictional_support.py": "943d5104e1778de25a3253918b2a5c857dcde197bcbd57522f93c4bcd60b0b88",
    "test_capture_locations.py": "8966de4b62dd5e1a526fadba010b68cff1c6c0e58bd39956a866a23ef091da03",
    "test_locations.py": "5eb256e751c9ae99fe2b4d986aee4923b8852ad04f0fd4f66cb73e4b01b306af",
}
IMPORT_ORDER = (
    "verification_io",
    "location_core",
    "capture_at_location",
    "capture_original_at_location",
    "selected_at_locations",
    "run_selected_at_locations",
    "receiving_at_locations",
    "verify_restored_at_locations",
    "fictional_support",
    "test_capture_locations",
    "test_locations",
)
PUBLIC_ALIASES = frozenset(IMPORT_ORDER)
SCIENCE_PREFIXES = ("src", "numpy", "arviz", "pymc", "pytensor", "sksurv", "lifelines")


def require(value: Any, message: str) -> None:
    if not value:
        raise ValueError(message)


def sha(path: Path) -> str:
    require(
        path.is_absolute()
        and not any(part.is_symlink() for part in (path, *path.parents)),
        "absolute unlinked source role required",
    )
    require(path.is_file(), "regular source member required")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


def document(path: Path, expected: str) -> dict[str, Any]:
    require(sha(path) == expected, "document byte SHA differs")

    def nonfinite(text: str) -> None:
        raise ValueError("nonfinite JSON " + text)

    value = json.loads(path.read_text(), parse_constant=nonfinite)
    require(
        isinstance(value, dict)
        and value["content_sha256"]
        == canonical({k: v for k, v in value.items() if k != "content_sha256"}),
        "document content seal differs",
    )
    require(sha(path) == expected, "document changed during read")
    return value


def validate_surface(source: Path) -> dict[str, Any]:
    """Require the exact eleven sources and full immutable 44-member carrier."""
    preparation = document(source / "preparation_receipt.json", PREPARATION_SHA)
    require(
        preparation["status"] == "original_reproduction_per_entry_io_adapter_prepared"
        and preparation["actual_science_executed"] is False
        and preparation["actual_subset_or_reviews_created"] is False,
        "preparation is not source-only",
    )
    full = {
        **preparation["implementation_source_sha256"],
        **preparation["test_source_sha256"],
    }
    require(
        full == SOURCE_SHA and len(full) == 11,
        "exact original eleven-source surface differs",
    )
    artifacts = preparation["artifacts"]
    require(
        len(artifacts) == 43 and preparation["archive_member_count"] == 44,
        "sealed archival counts differ",
    )
    expected = set(artifacts) | {"preparation_receipt.json"}
    actual = set()
    for path in source.rglob("*"):
        require(
            not path.is_symlink() and (path.is_file() or path.is_dir()),
            "unsafe preparation member",
        )
        if path.is_file():
            actual.add(str(path.relative_to(source)))
    require(actual == expected, "complete retained preparation member set differs")
    require(
        (source / "archive_members.txt").read_text().splitlines() == sorted(expected),
        "archive roster differs",
    )
    for name, binding in artifacts.items():
        relative = Path(name)
        require(
            not relative.is_absolute()
            and ".." not in relative.parts
            and str(relative) == name,
            "unsafe artifact name",
        )
        path = source / relative
        require(
            sha(path) == binding["sha256"] and path.stat().st_size == binding["bytes"],
            "preparation artifact differs",
        )
    for name, digest in SOURCE_SHA.items():
        require(sha(source / name) == digest, "reviewed source differs")
    return preparation


def validate_dependencies(preparation: dict[str, Any], roots: dict[str, Path]) -> None:
    """Check predecessor sources/receipts only; never import those dispatchers."""
    require(
        set(roots) == {"selected", "receiving", "capture"},
        "exact portable predecessor roles required",
    )
    for role, mapping in preparation["legacy_source_sha256"].items():
        for name, pin in mapping.items():
            require(sha(roots[role] / name) == pin, "predecessor source differs")
        require(
            sha(roots[role] / "preparation_receipt.json")
            == preparation["legacy_preparation_receipt_sha256"][role],
            "predecessor preparation differs",
        )


def configured(test_file: Path) -> tuple[Path, dict[str, Path]]:
    """Explicit prep-only overrides; adopted defaults are repository-relative."""
    repo = Path(
        os.environ.get(
            "BAYES_COX_PER_ENTRY_TEST_REPOSITORY_ROOT",
            str(test_file.absolute().parents[1]),
        )
    ).absolute()
    source = Path(
        os.environ.get(
            "BAYES_COX_PER_ENTRY_TEST_SOURCE_ROOT",
            str(repo / "scripts/catalytic_correction/per_entry_io"),
        )
    ).absolute()
    capture = Path(
        os.environ.get(
            "BAYES_COX_PER_ENTRY_TEST_CAPTURE_FIXTURE",
            str(
                repo
                / "tests/fixtures/catalytic_correction/original_producer_completion_v1"
            ),
        )
    ).absolute()
    return source, {
        "selected": repo / "scripts/catalytic_correction/reproduction",
        "receiving": repo / "scripts/catalytic_correction/receiving",
        "capture": capture,
    }


def science_names() -> set[str]:
    return {
        name
        for name in sys.modules
        if any(
            name == prefix or name.startswith(prefix + ".")
            for prefix in SCIENCE_PREFIXES
        )
    }


class ImportedGuards:
    """Private module graph plus per-test scoped aliases and fixture roots."""

    def __init__(self, source: Path, roots: dict[str, Path]) -> None:
        self.source, self.roots = source, roots
        self.preparation = validate_surface(source)
        validate_dependencies(self.preparation, roots)
        self.aliases: dict[str, Any] = {}
        self.private: dict[str, Any] = {}
        before_science = science_names()
        original_public = {name: sys.modules.get(name) for name in PUBLIC_ALIASES}
        for name in IMPORT_ORDER:
            private_name = "_portable_per_entry_guard_" + name
            require(
                private_name not in sys.modules,
                "private test namespace already occupied",
            )
            path = source / (name + ".py")
            require(sha(path) == SOURCE_SHA[path.name], "private source pin differs")
            spec = importlib.util.spec_from_file_location(private_name, path)
            require(
                spec is not None and spec.loader is not None,
                "private source loader unavailable",
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[private_name] = module
            try:
                with (
                    patch.object(sys, "dont_write_bytecode", True),
                    patch.dict(sys.modules, self.aliases),
                ):
                    spec.loader.exec_module(module)
            except BaseException:
                sys.modules.pop(private_name, None)
                raise
            self.private[private_name], self.aliases[name] = module, module
            require(
                sha(path) == SOURCE_SHA[path.name],
                "source changed during private import",
            )
        require(
            science_names() == before_science, "guard import loaded scientific modules"
        )
        require(
            all(
                sys.modules.get(name) is original_public[name]
                for name in PUBLIC_ALIASES
            ),
            "public import aliases leaked",
        )
        self.original_classes = []
        for name in ("test_capture_locations", "test_locations"):
            module = self.aliases[name]
            self.original_classes += [
                candidate
                for candidate in vars(module).values()
                if isinstance(candidate, type)
                and issubclass(candidate, unittest.TestCase)
                and candidate.__module__ == module.__name__
            ]
        methods = [
            (cls.__name__, name)
            for cls in self.original_classes
            for name in unittest.defaultTestLoader.getTestCaseNames(cls)
        ]
        require(
            len(methods) == len(set(methods)) == 53,
            "original 53 guards changed or duplicate collection leaked",
        )
        self.original_methods = sorted(methods)

    @contextmanager
    def scope(self):
        """No public alias or original hardcoded Mac fixture root survives a test."""
        baseline = {name: sys.modules.get(name) for name in PUBLIC_ALIASES}
        with ExitStack() as stack:
            stack.enter_context(patch.object(sys, "dont_write_bytecode", True))
            stack.enter_context(patch.dict(sys.modules, self.aliases))
            stack.enter_context(
                patch.object(
                    self.aliases["fictional_support"], "ROOTS", dict(self.roots)
                )
            )
            yield
        require(
            all(sys.modules.get(name) is baseline[name] for name in PUBLIC_ALIASES),
            "scoped aliases leaked after test",
        )

    def export(self, namespace: dict[str, Any]) -> None:
        """One inherited class per original class; no test method is rewritten."""
        imported = self

        class ScopedRun:
            def run(self, result=None):
                with imported.scope():
                    return super().run(result)

        for original in self.original_classes:
            name = "TestRetained" + original.__name__
            namespace[name] = type(
                name, (ScopedRun, original), {"__module__": namespace["__name__"]}
            )

    def report(self) -> dict[str, Any]:
        return {
            "status": "private_source_import_fixture_verified",
            "reviewed_source_sha256": SOURCE_SHA,
            "preparation_sha256": PREPARATION_SHA,
            "source_members": 11,
            "retained_original_test_methods": self.original_methods,
            "original_method_count": 53,
            "complete_preparation_members": 44,
            "public_aliases_leaked": False,
            "new_scientific_modules_loaded": False,
            "actual_dispatcher_checker_capture_or_numerical_job_invoked": False,
        }
