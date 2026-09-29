"""All 32 unchanged fictional guards plus one complete-carrier portability guard."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


def _support():
    """Use a distinct private helper name; never the per-entry public adapter."""
    path = Path(__file__).absolute().with_name("release_v3_repository_adapter.py")
    name = "_portable_release_v3_repository_adapter"
    if name in sys.modules:
        raise ValueError("release-v3 test adapter imported twice")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("portable release-v3 helper loader unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


_adapter = _support()
_source = _adapter.configured(Path(__file__))
_retained = _adapter.ImportedGuards(_source)
_retained.export(globals())


class TestCompleteReleaseV3CarrierPortability(unittest.TestCase):
    def test_complete233_original32_bindings_and_fresh_private_source_import(self):
        """Verify source-only carrier completeness, refusal and independent imports."""
        fictional_repo = _retained.carrier.parent / "portable-repository"
        fictional_test = fictional_repo / "tests/test_catalytic_correction_release_v3.py"
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(_adapter.configured(fictional_test), fictional_repo / "scripts/catalytic_correction/release_v3")
        with patch.dict(os.environ, {"BAYES_COX_RELEASE_V3_TEST_REPOSITORY_ROOT": str(fictional_repo)}, clear=True):
            self.assertEqual(_adapter.configured(Path(__file__)), fictional_repo / "scripts/catalytic_correction/release_v3")
        original = _adapter.validate_surface(_source)
        self.assertEqual(original["implementation_source_sha256"], _adapter.SOURCE_SHA)
        self.assertEqual(_adapter.method_surface(_source), _retained.original_methods)
        self.assertEqual(len(_retained.original_methods), 32)
        self.assertEqual(_adapter.validate_surface(_retained.carrier), original)
        self.assertEqual(_retained.runtime.own_prepare(_retained.carrier / "preparation_receipt.json", _adapter.PREPARATION_SHA), original)
        # Only a disposable ~1.69MB source/log fixture is changed, never the seal.
        with tempfile.TemporaryDirectory(prefix="fictional-release-v3-tamper-", dir=_adapter.fixture_parent()) as temporary:
            copied = Path(temporary).resolve() / "carrier"
            shutil.copytree(_source, copied)
            member = copied / "release_v3_core.py"
            preserved = member.read_bytes()
            member.write_bytes(b"# fictional changed source; never imported\n")
            with self.assertRaisesRegex(ValueError, "artifact|source|byte"):
                _adapter.validate_surface(copied)
            member.write_bytes(preserved)
            extra = copied / "__init__.py"
            extra.write_bytes(b"# forbidden extra carrier member; never imported\n")
            with self.assertRaisesRegex(ValueError, "carrier"):
                _adapter.validate_surface(copied)
            extra.unlink()
            (copied / "unexpected_empty_directory").mkdir()
            with self.assertRaisesRegex(ValueError, "carrier"):
                _adapter.validate_surface(copied)
            (copied / "unexpected_empty_directory").rmdir()
            (copied / "README.md").unlink()
            with self.assertRaisesRegex(ValueError, "carrier"):
                _adapter.validate_surface(copied)
        helper = Path(_adapter.__file__).absolute()
        helper_sha = hashlib.sha256(helper.read_bytes()).hexdigest()
        driver = (
            "import hashlib,importlib.util,json,sys;from pathlib import Path;"
            "p=Path(sys.argv[1]);assert hashlib.sha256(p.read_bytes()).hexdigest()==sys.argv[2];"
            "s=importlib.util.spec_from_file_location('_fresh_release_v3_adapter',p);"
            "m=importlib.util.module_from_spec(s);sys.modules[s.name]=m;s.loader.exec_module(m);"
            "r=m.ImportedGuards(Path(sys.argv[3]));v=r.report();c=r.carrier;r.close();"
            "assert hashlib.sha256(p.read_bytes()).hexdigest()==sys.argv[2];"
            "v['disposable_source_fixture_removed']=not c.exists();"
            "v['fresh_scientific_import_names']=sorted(m.science_names());"
            "print(json.dumps(v,sort_keys=True))"
        )
        argv = [sys.executable, "-I", "-B", "-c", driver, str(helper), helper_sha, str(_source)]
        result = subprocess.run(argv, capture_output=True, check=False, text=True,
                                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
        self.assertIs(type(result.returncode), int)
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["status"], "release_v3_complete_carrier_private_import_verified")
        self.assertEqual(value["preparation_sha256"], _adapter.PREPARATION_SHA)
        self.assertEqual(value["runtime_source_sha256"], _adapter.SOURCE_SHA)
        self.assertEqual(value["original_test_source_sha256"], _adapter.TEST_SOURCE_SHA)
        self.assertEqual(value["original_method_ast_sha256"], _retained.original_methods)
        self.assertEqual(value["complete_carrier_members"], 233)
        self.assertEqual(value["bound_artifacts"], 232)
        self.assertEqual(value["original_method_count"], 32)
        self.assertEqual(value["entrypoints_imported_without_dispatch"], sorted(set(_adapter.SOURCE_SHA) - {"release_v3_core.py"}))
        self.assertFalse(value["public_aliases_leaked"])
        self.assertFalse(value["interpreter_globals_leaked"])
        self.assertFalse(value["new_scientific_modules_loaded"])
        self.assertEqual(value["fresh_scientific_import_names"], [])
        self.assertFalse(value["actual_plan_scientific_source_receiving_producer_or_transfer_invoked"])
        self.assertTrue(value["disposable_source_fixture_removed"])
        self.assertFalse(value["original_source_modified"])
        self.assertFalse(value["root_adoption_or_approval_conferred"])
        self.assertEqual(_adapter.validate_surface(_source), original)


if __name__ == "__main__":
    unittest.main(verbosity=2)
