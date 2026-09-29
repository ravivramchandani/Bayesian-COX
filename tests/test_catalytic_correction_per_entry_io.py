"""Preserve all 53 reviewed fictional guards, plus one portable import guard."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _support():
    # This adapter helper belongs beside the adopted repository test module.
    path = Path(__file__).absolute().with_name("repository_adapter.py")
    name = "_portable_per_entry_repository_adapter"
    if name in sys.modules:
        raise ValueError("private repository adapter namespace occupied")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("repository adapter loader unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_adapter = _support()
_source, _roots = _adapter.configured(Path(__file__))
_retained = _adapter.ImportedGuards(_source, _roots)
_retained.export(globals())


class TestPortableSourceAndDependencySurface(unittest.TestCase):
    def test_exact_eleven_sources_preparation_dependencies_and_fresh_private_import(
        self,
    ):
        """A source-only child validates honest pins, no alias leaks or science."""
        prepared = _adapter.validate_surface(_source)
        _adapter.validate_dependencies(prepared, _roots)
        self.assertEqual(
            set(_adapter.SOURCE_SHA),
            set(prepared["implementation_source_sha256"])
            | set(prepared["test_source_sha256"]),
        )
        self.assertEqual(len(_retained.original_methods), 53)
        with _retained.scope():
            self.assertEqual(
                _retained.aliases["location_core"].preparation(
                    _source / "preparation_receipt.json", _adapter.PREPARATION_SHA
                ),
                prepared,
            )
        # Tamper only a new ordinary source-copy fixture, never the sealed tree.
        with tempfile.TemporaryDirectory(
            prefix="fictional-per-entry-surface-"
        ) as temporary:
            copied = Path(temporary).resolve() / "source"
            shutil.copytree(_source, copied)
            (copied / "location_core.py").write_bytes(
                b"# fictional changed source; never imported\n"
            )
            with self.assertRaisesRegex(ValueError, "artifact|source"):
                _adapter.validate_surface(copied)
        driver = (
            "import importlib.util,json,sys;from pathlib import Path;"
            "p=Path(sys.argv[1]);s=importlib.util.spec_from_file_location('_fresh_private_test_adapter',p);"
            "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);"
            "r=m.ImportedGuards(Path(sys.argv[2]),{k:Path(v) for k,v in json.loads(sys.argv[3]).items()});"
            "print(json.dumps(r.report(),sort_keys=True))"
        )
        argv = [
            sys.executable,
            "-I",
            "-B",
            "-c",
            driver,
            str(Path(_adapter.__file__).absolute()),
            str(_source),
            json.dumps(
                {key: str(value) for key, value in _roots.items()}, sort_keys=True
            ),
        ]
        result = subprocess.run(
            argv,
            capture_output=True,
            check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            text=True,
        )
        self.assertIs(type(result.returncode), int)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["status"], "private_source_import_fixture_verified")
        self.assertEqual(value["reviewed_source_sha256"], _adapter.SOURCE_SHA)
        self.assertEqual(value["original_method_count"], 53)
        self.assertEqual(value["complete_preparation_members"], 44)
        self.assertFalse(value["public_aliases_leaked"])
        self.assertFalse(value["new_scientific_modules_loaded"])
        self.assertFalse(
            value["actual_dispatcher_checker_capture_or_numerical_job_invoked"]
        )


if __name__ == "__main__":
    unittest.main()
