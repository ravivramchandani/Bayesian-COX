"""Retain the sealed fictional guard methods and one portable isolation guard."""

from __future__ import annotations

import builtins
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch


def _support():
    path = Path(__file__).absolute().with_name("guarded_dispatch_repository_adapter.py")
    name = "_portable_guarded_dispatch_repository_adapter"
    if name in sys.modules:
        raise ValueError("portable guard adapter imported twice")
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("portable guard helper loader unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        with patch.object(sys, "dont_write_bytecode", True):
            spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


_adapter = _support()
_source, _roots = _adapter.configured(Path(__file__))
_retained = _adapter.ImportedGuards(_source, _roots)
_retained.export(globals())


class TestGuardCarrierPortability(unittest.TestCase):
    def test_complete_carrier_preserved_methods_caller_isolation_and_failed_setup_cleanup(self):
        fictional_repo = _retained.carrier.parent / "repository"
        fictional_test = fictional_repo / "tests/test_catalytic_correction_guarded_dispatch.py"
        with patch.dict(os.environ, {}, clear=True):
            source, roots = _adapter.configured(fictional_test)
            self.assertEqual(source, fictional_repo / "scripts/catalytic_correction/guarded_dispatch")
            self.assertEqual(roots, {"fit": fictional_repo / "scripts/catalytic_correction",
                                     "reproduction": fictional_repo / "scripts/catalytic_correction/reproduction"})
        with patch.dict(os.environ, {"BAYES_COX_GUARD_TEST_REPOSITORY_ROOT": str(fictional_repo)}, clear=True):
            self.assertEqual(_adapter.configured(Path(__file__)), (source, roots))
        original = _adapter.validate_surface(_source)
        self.assertEqual(_adapter.validate_surface(_retained.carrier), original)
        self.assertEqual(_adapter.method_surface(_source), _adapter.ORIGINAL_METHOD_AST)
        self.assertEqual(len(_adapter.ORIGINAL_METHOD_AST), 23)
        self.assertEqual(_adapter.regression_surface(_source), _adapter.REGRESSION_METHOD_AST)
        self.assertEqual(_adapter.consistency_surface(_source), _adapter.CONSISTENCY_METHOD_AST)
        self.assertEqual(len(_adapter.REGRESSION_METHOD_AST), 11)
        self.assertEqual(len(_adapter.CONSISTENCY_METHOD_AST), 7)
        self.assertEqual(len(_retained.original_methods), 41)
        self.assertEqual(_adapter.CARRIER_MEMBERS, 116)
        self.assertEqual(original["artifact_directories"], list(_adapter.CARRIER_DIRECTORIES))
        for case in _retained.original_classes:
            exported = globals()["TestRetainedGuard" + case.__name__]
            for name in unittest.defaultTestLoader.getTestCaseNames(case):
                self.assertIs(getattr(exported, name), getattr(case, name))
        self.assertEqual(len(_retained.original_methods), len(set(_retained.original_methods)))

        # Mutate only disposable ordinary source copies, never the sealed carrier.
        with tempfile.TemporaryDirectory(prefix="fictional-guard-tamper-", dir=_adapter.fixture_parent()) as directory:
            copy = Path(directory).resolve() / "carrier"
            shutil.copytree(_source, copy)
            member = copy / "guard_fit_dispatch.py"
            preserved = member.read_bytes()
            member.write_bytes(b"# fictional tamper; never imported\n")
            with self.assertRaisesRegex(_adapter.InvalidFixture, "artifact|source"):
                _adapter.validate_surface(copy)
            member.write_bytes(preserved)
            extra = copy / "extra.fake"
            extra.write_bytes(b"fictional extra source member; never imported\n")
            with self.assertRaisesRegex(_adapter.InvalidFixture, "roster"):
                _adapter.validate_surface(copy)
            extra.unlink()
            (copy / "unexpected_empty").mkdir()
            with self.assertRaisesRegex(_adapter.InvalidFixture, "roster"):
                _adapter.validate_surface(copy)
            (copy / "unexpected_empty").rmdir()
            (copy / "README.md").unlink()
            with self.assertRaisesRegex(_adapter.InvalidFixture, "roster"):
                _adapter.validate_surface(copy)

        # A full scientific suite may already own these names. The fixture alone
        # gets an empty src namespace; every caller object must return unchanged.
        caller = {"src.__guard_portability_caller": ModuleType("src.__guard_portability_caller"),
                  "fit_common": ModuleType("fit_common"), "_reproduction_bound_common": object(),
                  "_fictional_guard_core": object(), "_fictional_guard_capture": object(),
                  "test_guarded_dispatch": object(), "test_guarded_dispatch_regressions": object(),
                  "test_guarded_dispatch_reuse_consistency": object()}
        before_science = _adapter.science_names()
        before_path, before_bytecode = list(sys.path), sys.dont_write_bytecode
        before_env = dict(os.environ)
        with patch.dict(sys.modules, caller), patch.dict(os.environ, {"OMP_NUM_THREADS": "7"}):
            with _retained.scope():
                self.assertFalse(any(name == "src" or name.startswith("src.") for name in sys.modules))
                self.assertNotIn("fit_common", sys.modules)
                self.assertNotIn("_reproduction_bound_common", sys.modules)
                self.assertIs(sys.modules["_fictional_guard_core"], _retained.tests[0].g)
                for name, module in zip((path.removesuffix(".py") for path in _adapter.TEST_ORDER), _retained.tests, strict=True):
                    self.assertIs(sys.modules[name], module)
                self.assertTrue(all(os.environ[name] == "1" for name in _adapter.THREADS))
                self.assertTrue(sys.dont_write_bytecode)
                os.environ["FICTIONAL_GUARD_MUST_NOT_LEAK"] = "fictional"
            self.assertTrue(all(sys.modules[name] is value for name, value in caller.items()))
            self.assertEqual(os.environ["OMP_NUM_THREADS"], "7")
            self.assertNotIn("FICTIONAL_GUARD_MUST_NOT_LEAK", os.environ)
        self.assertEqual(_adapter.science_names(), before_science)
        self.assertEqual(sys.path, before_path)
        self.assertEqual(sys.dont_write_bytecode, before_bytecode)
        self.assertEqual(dict(os.environ), before_env)

        # Verify process/import attempts fail before running, and are still
        # reported as boundary violations even if the invented case catches them.
        for forbidden in (lambda: subprocess.Popen(["FICTIONAL_MUST_NOT_EXECUTE"]),
                          lambda: builtins.__import__("numpy")):
            with (self.subTest(boundary=forbidden),
                  self.assertRaisesRegex(_adapter.InvalidFixture, "fixture attempted"),
                  _retained.scope(), self.assertRaises(_adapter.InvalidFixture)):
                forbidden()
        new_src = "src.__guard_forbidden_new_name"
        self.assertNotIn(new_src, sys.modules)
        with self.assertRaisesRegex(_adapter.InvalidFixture, "introduced science"), _retained.scope():
            sys.modules[new_src] = ModuleType(new_src)
        self.assertNotIn(new_src, sys.modules)
        self.assertEqual(_adapter.science_names(), before_science)

        # unittest skips tearDown after failed setUp. The outer fixture scope
        # must clean its recorded directories and temporary module names anyway.
        setup_paths = []

        class FailedSetup(unittest.TestCase):
            def setUp(self):
                self.directory = _retained.tests[0].tempfile.TemporaryDirectory(prefix="fictional-failed-setup-")
                setup_paths.append(Path(self.directory.name))
                sys.modules["_fictional_common_FAILED_SETUP"] = ModuleType("fictional")
                raise RuntimeError("FICTIONAL expected failed setUp")

            def runTest(self):
                self.fail("failed setUp must prevent the invented body")

        result = unittest.TestResult()
        with _retained.scope():
            FailedSetup().run(result)
        self.assertEqual(result.testsRun, 1)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("FICTIONAL expected failed setUp", result.errors[0][1])
        self.assertTrue(setup_paths and all(not path.exists() for path in setup_paths))
        self.assertNotIn("_fictional_common_FAILED_SETUP", sys.modules)

        # Constructor failure after the carrier copy removes only its own copy.
        temporary_paths = []
        actual_temporary = tempfile.TemporaryDirectory

        def track_temporary(*args, **kwargs):
            temporary = actual_temporary(*args, **kwargs)
            temporary_paths.append(Path(temporary.name))
            return temporary

        with (patch.object(tempfile, "TemporaryDirectory", side_effect=track_temporary),
              patch.object(_adapter.ImportedGuards, "_import", side_effect=RuntimeError("FICTIONAL failed private import")),
              self.assertRaisesRegex(RuntimeError, "failed private import")):
            _adapter.ImportedGuards(_source, _roots)
        self.assertTrue(temporary_paths and all(not path.exists() for path in temporary_paths))
        fresh = _adapter.ImportedGuards(_source, _roots)
        report, carrier = fresh.report(), fresh.carrier
        fresh.close()
        self.assertFalse(carrier.exists())
        self.assertEqual(report["preparation_sha256"], _adapter.PREPARATION_SHA)
        self.assertFalse(report["actual_subprocess_controller_checker_generator_model_score_or_approval_invoked"])
        self.assertEqual(_adapter.validate_surface(_source), original)
        self.assertEqual(_adapter.validate_surface(_retained.carrier), original)
        self.assertEqual(_adapter.science_names(), before_science)


if __name__ == "__main__":
    unittest.main(verbosity=2)
