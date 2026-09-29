"""Invented bytes/injected process guards only; no scientific operations."""

from __future__ import annotations

import copy
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import capture_mixed_source as mixed
import release_core as core
import verify_restored_correction as restored
from test_release_adapters import Fixture, binding, raw, save


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fictional-bound-mixed-capture-")
        self.base = Path(self.temp.name).resolve(strict=True)
        self.output = self.base / "verified"
        self.prefix = self.base / "actual_capture_fixture"
        self.script = self.base / "code" / "verify_mixed_extensions.py"
        raw(self.script, b"# fictional stdlib file; never imported or executed\n")
        self.producer_file = self.base / "producer" / "capture_mixed_source.py"
        raw(self.producer_file, b"# fictional producer; never executed\n")
        self.prep = self.producer_file.with_name("preparation_receipt.json")
        save(self.prep, {"fictional": True})
        self.source_inputs = {str(self.script): core.sha(self.script)}
        self.producer = {"entrypoint": {"historical_path": str(self.producer_file), "sha256": core.sha(self.producer_file)},
            "preparation_receipt": {"historical_path": str(self.prep), "sha256": core.sha(self.prep)},
            "implementation_source_sha256": {str(self.producer_file): core.sha(self.producer_file)}}
        self.runtime = {"python_executable": "/fictional/locked_python", "locked_interpreter_samefile": True,
                        "numeric_thread_environment": dict.fromkeys(core.NUMERIC, "1")}
        self.argv = [self.runtime["python_executable"], "-I", "-B", str(self.script),
            "--preparation-receipt", str(self.prep), "--preparation-receipt-sha256", core.sha(self.prep),
            "--input-bindings", str(self.base / "fictional_bound_inputs.json"), "--input-bindings-sha256", "a" * 64,
            "--output", str(self.output)]
        self.calls = []

    def tearDown(self):
        self.temp.cleanup()

    def child(self, argv, **kwargs):
        self.calls.append(argv)
        self.assertEqual(kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
        self.assertTrue(all(kwargs["env"][key] == "1" for key in core.NUMERIC))
        self.output.mkdir()
        summary = {"status": core.MIXED_STATUS, "verified_logical_cells": 1625,
                   "programme_complete": False, "verify_existing": False}
        save(self.output / "completion.json", summary)
        return SimpleNamespace(returncode=0, stdout=(json.dumps(summary) + "\n").encode(), stderr=b"fictional retained stderr\n")

    def capture(self, child=None, **options):
        return mixed.capture(self.argv, self.prefix, self.output, core.Pins(), source_inputs=self.source_inputs,
            producer=self.producer, runtime=self.runtime, invoke=self.child if child is None else child,
            test_only=True, **options)

    def test_injected_success_is_only_synthetic_and_retains_exact_bytes(self):
        result = self.capture()
        self.assertEqual(result["status"], "synthetic_mixed_verifier_capture_fixture_passed")
        self.assertTrue(result["test_only_dependency_injection"])
        receipt = core.document(Path(result["receipt_path"]), core.Pins())
        attempt = core.document(self.prefix.with_name(self.prefix.name + ".attempt.json"), core.Pins())
        self.assertTrue(receipt["test_only_dependency_injection"])
        self.assertTrue(attempt["test_only_dependency_injection"])
        self.assertEqual(attempt["operation"], "synthetic_mixed_verifier_capture_fixture")
        self.assertEqual(attempt["argv"], self.argv)
        self.assertEqual(self.calls, [self.argv])
        self.assertFalse(receipt["programme_complete"])

    def test_production_api_rejects_injected_call_before_launch(self):
        with self.assertRaisesRegex(ValueError, "fictional"):
            mixed.capture(self.argv, self.prefix, self.output, core.Pins(), source_inputs=self.source_inputs,
                          producer=self.producer, runtime=self.runtime, invoke=self.child)
        self.assertFalse(self.calls)
        self.assertFalse(self.output.exists())

    def test_initial_capture_refuses_existing_output_or_false_runtime(self):
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, "fresh absent"):
            self.capture()
        self.output.rmdir()
        self.runtime["numeric_thread_environment"][core.NUMERIC[-1]] = "2"
        with self.assertRaisesRegex(ValueError, "numeric runtime"):
            self.capture()
        self.assertFalse(self.calls)

    def test_nonzero_keeps_rc_stdout_stderr_without_completion(self):
        def failed(*_args, **_kwargs):
            return SimpleNamespace(returncode=29, stdout=b"original failed stdout\n", stderr=b"exact original stderr\n")
        with self.assertRaisesRegex(ValueError, "failed"):
            self.capture(failed)
        attempt = core.document(self.prefix.with_name(self.prefix.name + ".attempt.json"), core.Pins())
        self.assertEqual(attempt["exit_code"], 29)
        self.assertEqual(self.prefix.with_name(self.prefix.name + ".stdout.log").read_bytes(), b"original failed stdout\n")
        self.assertFalse(self.prefix.with_name(self.prefix.name + ".receipt.json").exists())

    def test_launch_error_is_not_zero_and_retains_attempt(self):
        def failed(*_args, **_kwargs):
            raise OSError("fictional unavailable child")
        with self.assertRaisesRegex(ValueError, "failed"):
            self.capture(failed)
        attempt = core.document(self.prefix.with_name(self.prefix.name + ".attempt.json"), core.Pins())
        self.assertIsNone(attempt["exit_code"])
        self.assertIn("unavailable", attempt["launch_error"]["message"])
        self.assertFalse(self.prefix.with_name(self.prefix.name + ".receipt.json").exists())

    def test_boolean_zero_refused(self):
        def failed(*_args, **_kwargs):
            return SimpleNamespace(returncode=False, stdout=b"not rc0", stderr=b"")
        with self.assertRaises(ValueError):
            self.capture(failed)

    def test_changed_source_refuses_receipt(self):
        def changed(argv, **kwargs):
            result = self.child(argv, **kwargs)
            self.script.write_bytes(b"# changed fictional source\n")
            return result
        with self.assertRaisesRegex(ValueError, "changed"):
            self.capture(changed)
        self.assertFalse(self.prefix.with_name(self.prefix.name + ".receipt.json").exists())

    def test_wrong_or_missing_completion_and_summary_refuse(self):
        for mode in ("missing", "partial", "foreign", "replay"):
            with self.subTest(mode=mode):
                self.prefix = self.base / ("attempt_" + mode)
                self.output = self.base / ("output_" + mode)
                def changed(argv, selected_mode=mode, **kwargs):
                    result = self.child(argv, **kwargs)
                    path = self.output / "completion.json"
                    if selected_mode == "missing":
                        path.unlink()
                    elif selected_mode == "partial":
                        save(path, {"status": core.MIXED_STATUS, "verified_logical_cells": 1624})
                    else:
                        summary = json.loads(result.stdout)
                        summary["status" if selected_mode == "foreign" else "verify_existing"] = "foreign" if selected_mode == "foreign" else True
                        result.stdout = (json.dumps(summary) + "\n").encode()
                    return result
                with self.assertRaises(ValueError):
                    self.capture(changed)
                self.assertFalse(self.prefix.with_name(self.prefix.name + ".receipt.json").exists())

    def test_collision_symlink_overlap_refuse_before_launch(self):
        raw(self.prefix.with_name(self.prefix.name + ".stdout.log"), b"retained previous failed attempt")
        with self.assertRaises(ValueError):
            self.capture()
        self.assertFalse(self.calls)
        self.prefix = self.output / "forbidden_capture"
        with self.assertRaisesRegex(ValueError, "overlaps"):
            self.capture()
        self.prefix = self.base / "link"
        self.prefix.symlink_to(self.base)
        with self.assertRaisesRegex(ValueError, "linked"):
            self.capture()
        self.assertFalse(self.calls)

    def test_publication_failure_keeps_closed_bytes_no_success(self):
        original = core.write_new
        def fail_receipt(path, value):
            if path.name.endswith(".receipt.json"):
                raise OSError("fictional atomic publication failure")
            return original(path, value)
        with patch.object(core, "write_new", fail_receipt), self.assertRaises(OSError):
            self.capture()
        self.assertTrue(self.prefix.with_name(self.prefix.name + ".attempt.json").exists())
        self.assertFalse(self.prefix.with_name(self.prefix.name + ".receipt.json").exists())

    def test_residual_after_receipt_refuses_reported_success(self):
        original = core.write_new
        def residue(path, value):
            original(path, value)
            if path.name.endswith(".receipt.json"):
                raw(path.with_name(".verification-pending-" + self.prefix.name + ".receipt.json-fictional"), b"retained residue")
        with patch.object(core, "write_new", residue), self.assertRaisesRegex(ValueError, "residue"):
            self.capture()
        self.assertTrue(self.prefix.with_name(self.prefix.name + ".receipt.json").exists())


class RetentionAndProducerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fictional-v2-retention-")
        self.base = Path(self.temp.name).resolve(strict=True)

    def tearDown(self):
        self.temp.cleanup()

    def mutate_source(self, fixture, change):
        path = Path(fixture.request["source_capture"]["path"])
        attempt_path = path.with_name("source.attempt.json")
        attempt = core.document(attempt_path, core.Pins())
        receipt = core.document(path, core.Pins())
        change(attempt, receipt)
        save(attempt_path, attempt)
        receipt["invocation_attempt_sha256"] = core.sha(attempt_path)
        receipt["artifacts"][attempt_path.name] = binding(attempt_path)
        fixture.request["source_capture"]["sha256"] = save(path, receipt)
        fixture.refresh_assets()

    def test_both_source_capture_flags_must_be_explicit_false(self):
        for role, replacement in (("attempt", True), ("receipt", True), ("attempt", None), ("receipt", None)):
            with self.subTest(role=role, replacement=replacement):
                root = self.base / (role + str(replacement))
                root.mkdir()
                fixture = Fixture(root)
                def change(attempt, receipt, selected_role=role, selected_replacement=replacement):
                    record = attempt if selected_role == "attempt" else receipt
                    if selected_replacement is None:
                        del record["test_only_dependency_injection"]
                    else:
                        record["test_only_dependency_injection"] = selected_replacement
                self.mutate_source(fixture, change)
                with self.assertRaisesRegex(ValueError, "genuine mixed"):
                    fixture.stage()
                self.assertFalse((root / "payload").exists())

    def test_original_unmarked_capture_operation_refused(self):
        fixture = Fixture(self.base)
        self.mutate_source(fixture, lambda attempt, _receipt: attempt.update(operation="actual_mixed_verifier_child_capture"))
        with self.assertRaisesRegex(ValueError, "reviewed v2 mixed"):
            fixture.stage()

    def test_wrong_producer_pin_and_missing_implementation_refuse(self):
        for mode in ("entrypoint", "preparation", "implementation"):
            with self.subTest(mode=mode):
                root = self.base / mode
                root.mkdir()
                fixture = Fixture(root)
                def change(attempt, receipt, selected_mode=mode):
                    producer = copy.deepcopy(attempt["capture_producer"])
                    if selected_mode == "entrypoint":
                        producer["entrypoint"]["sha256"] = "f" * 64
                    elif selected_mode == "preparation":
                        producer["preparation_receipt"]["sha256"] = "f" * 64
                    else:
                        producer["implementation_source_sha256"].clear()
                    attempt["capture_producer"] = receipt["capture_producer"] = producer
                self.mutate_source(fixture, change)
                with self.assertRaisesRegex(ValueError, "producer/source/preparation"):
                    fixture.stage()

    def test_evidence_and_code_roots_cannot_use_filtered_group(self):
        for role in ("original_run", "preflight", "witness_root", "verification_preparation"):
            with self.subTest(role=role):
                root = self.base / role
                root.mkdir()
                fixture = Fixture(root)
                asset = fixture.request["assets"][role]
                asset["kind"] = "group"
                asset["inventory"] = {"files": {}, "directories": []}
                with self.assertRaisesRegex(ValueError, "exact whole-tree"):
                    fixture.stage()
                self.assertFalse((root / "payload").exists())

    def test_tree_inventory_omitted_orphan_and_empty_directory_refuse(self):
        for mode in ("orphan", "empty_directory"):
            with self.subTest(mode=mode):
                root = self.base / mode
                root.mkdir()
                fixture = Fixture(root)
                target = fixture.roots["preflight"]
                if mode == "orphan":
                    raw(target / "failed_attempt_orphan.log", b"retained actual failure-shaped fictional bytes")
                else:
                    (target / "unreached_attempt").mkdir()
                # The supplied old inventory intentionally omits the new node.
                with self.assertRaisesRegex(ValueError, "tree changed"):
                    fixture.stage()
                self.assertFalse((root / "payload").exists())

    def test_fixed_files_cannot_be_trees_and_captures_cannot_be_trees(self):
        for role in ("matched", "review_method", "source_capture", "claim_capture"):
            with self.subTest(role=role):
                root = self.base / role
                root.mkdir()
                fixture = Fixture(root)
                fixture.request["assets"][role]["kind"] = "tree"
                with self.assertRaisesRegex(ValueError, "exact whole-tree"):
                    fixture.stage()

    def test_flat_capture_cannot_omit_member_or_include_nested_file(self):
        for mode in ("missing", "nested"):
            with self.subTest(mode=mode):
                root = self.base / mode
                root.mkdir()
                fixture = Fixture(root)
                files = fixture.request["assets"]["source_capture"]["inventory"]["files"]
                value = files.pop("source.stderr.log")
                if mode == "nested":
                    files["filtered/source.stderr.log"] = value
                with self.assertRaisesRegex(ValueError, "exactly its four"):
                    fixture.stage()

    def test_relocated_source_capture_revalidates_history_without_new_process(self):
        fixture = Fixture(self.base)
        root, _ = fixture.stage()
        manifest = core.document(root / "corrected_release_stage.json", core.Pins())
        with patch("subprocess.run", side_effect=AssertionError("no process in historical source-proof read")):
            restored.validate_historical_mixed_capture(root, manifest, core.Pins())

    def test_relocated_source_metadata_cannot_substitute_receiving_paths(self):
        fixture = Fixture(self.base)
        root, _ = fixture.stage()
        manifest = core.document(root / "corrected_release_stage.json", core.Pins())
        path = root / manifest["source_verifier_capture_location"]
        attempt_path = path.with_name("source.attempt.json")
        attempt = core.document(attempt_path, core.Pins())
        attempt["argv"][3] = str(root / core.LAYOUT["verification_preparation"] / "verify_mixed_extensions.py")
        save(attempt_path, attempt)
        receipt = core.document(path, core.Pins())
        receipt["invocation_attempt_sha256"] = core.sha(attempt_path)
        receipt["artifacts"][attempt_path.name] = binding(attempt_path)
        manifest["source_verifier_capture_sha256"] = save(path, receipt)
        with self.assertRaisesRegex(ValueError, "historical mixed"):
            restored.validate_historical_mixed_capture(root, manifest, core.Pins())

    def test_prepare_rejects_foreign_runtime_before_checkers_or_creation(self):
        with patch.dict(os.environ, dict.fromkeys(core.NUMERIC, "1")), self.assertRaisesRegex(ValueError, "same"):
            mixed.prepare(self.base / "receipt.json", "a" * 64, self.base / "verifier_receipt.json", "b" * 64,
                          self.base / "bindings.json", "c" * 64, self.base / "output", self.base / "prefix",
                          Path("/fictional/foreign_python"))
        self.assertFalse((self.base / "output").exists())

    def test_prepare_rejects_numeric_threads_before_any_scientific_import(self):
        with patch.dict(os.environ, dict.fromkeys(core.NUMERIC, "1")):
            os.environ[core.NUMERIC[0]] = "2"
            with self.assertRaisesRegex(ValueError, "numeric"):
                mixed.prepare(self.base / "receipt.json", "a" * 64, self.base / "verifier_receipt.json", "b" * 64,
                              self.base / "bindings.json", "c" * 64, self.base / "output", self.base / "prefix",
                              Path(sys.executable))
        self.assertFalse((self.base / "output").exists())

    def preparation_fixture(self, root):
        """Build fictional complete source roles; prepare() launches nothing."""
        producer_root, verifier_root, evidence = (root / name for name in ("producer", "verifier", "evidence"))
        for directory in (producer_root, verifier_root, evidence):
            directory.mkdir(parents=True)
        for name in mixed.OWN:
            raw(producer_root / name, b"# fictional producer role, never executed\n")
        for name in mixed.VERIFIER_NAMES:
            raw(verifier_root / name, b"# fictional scientific role, never imported\n")
        verifier_receipt = verifier_root / "preparation_receipt.json"
        verifier_sha = save(verifier_receipt, {"status": "fictional_preparation",
            "implementation_source_sha256": {name: core.sha(verifier_root / name) for name in mixed.VERIFIER_NAMES},
            "artifacts": {name: binding(verifier_root / name) for name in mixed.VERIFIER_NAMES}})
        source_pins = producer_root / "source_pins.json"
        save(source_pins, {"mixed_verifier_preparation_sha256": verifier_sha}, None)
        producer_receipt = producer_root / "preparation_receipt.json"
        producer_sha = save(producer_receipt, {"status": "fictional_preparation", "source_pins_sha256": core.sha(source_pins),
            "implementation_source_sha256": {name: core.sha(producer_root / name) for name in mixed.OWN},
            "artifacts": {name: binding(producer_root / name) for name in mixed.OWN}})
        bindings = {"roots": {}, "files": {}, "review_paths": {}}
        for role in core.ROOTS:
            path = evidence / role
            path.mkdir()
            bindings["roots"][role] = str(path)
        for role in core.FILES:
            path = evidence / (role + ".json")
            save(path, {"fictional": role})
            bindings["files"][role] = {"path": str(path), "sha256": core.sha(path)}
        for role in core.REVIEWS:
            path = evidence / ("review_" + role + ".json")
            save(path, {"fictional_pending_not_actual_review": role})
            bindings["review_paths"][role] = str(path)
        request = root / "bindings.json"
        request_sha = save(request, bindings)
        args = (producer_receipt, producer_sha, verifier_receipt, verifier_sha, request, request_sha,
                root / "verified", root / "capture", Path(sys.executable))
        return args, producer_root, verifier_root, bindings

    def test_prepare_complete_pinned_roles_build_only_exact_initial_argv(self):
        args, producer, verifier, bindings = self.preparation_fixture(self.base / "positive")
        with patch.object(mixed, "__file__", str(producer / "capture_mixed_source.py")), \
             patch.dict(os.environ, dict.fromkeys(core.NUMERIC, "1")), \
             patch("subprocess.run", side_effect=AssertionError("prepare cannot launch a checker/fit/verifier")):
            argv, pins, metadata = mixed.prepare(*args)
        self.assertEqual(len(argv), 14)
        self.assertEqual(argv[3], str(verifier / "verify_mixed_extensions.py"))
        self.assertNotIn("--verify-existing", argv)
        self.assertEqual(set(metadata["source_inputs"]), {str(verifier / name) for name in mixed.VERIFIER_NAMES}
                         | {str(args[2]), str(args[4])})
        self.assertEqual(len(metadata["producer"]["implementation_source_sha256"]), 6)
        self.assertFalse(args[6].exists())
        self.assertTrue(bindings)
        pins.recheck()

    def test_prepare_changed_missing_pins_incomplete_roots_overlap_and_existing_output(self):
        for mode in ("missing_verifier_pin", "changed_source", "incomplete_roots", "overlap", "existing", "linked"):
            with self.subTest(mode=mode):
                args, producer, verifier, _bindings = self.preparation_fixture(self.base / mode)
                args = list(args)
                if mode == "missing_verifier_pin":
                    receipt = core.document(args[2], core.Pins())
                    del receipt["implementation_source_sha256"]["science_verification.py"]
                    args[3] = save(args[2], receipt)
                    source_pins = producer / "source_pins.json"
                    save(source_pins, {"mixed_verifier_preparation_sha256": args[3]}, None)
                    receipt = core.document(args[0], core.Pins())
                    receipt["source_pins_sha256"] = core.sha(source_pins)
                    args[1] = save(args[0], receipt)
                elif mode == "changed_source":
                    raw(verifier / "science_verification.py", b"# changed fictional source\n")
                elif mode == "incomplete_roots":
                    request = core.document(args[4], core.Pins())
                    del request["roots"]["preflight"]
                    args[5] = save(args[4], request)
                elif mode == "overlap":
                    args[6] = verifier / "forbidden_output"
                elif mode == "existing":
                    args[6].mkdir()
                else:
                    linked = args[6].parent / "linked"
                    linked.symlink_to(verifier)
                    args[6] = linked / "forbidden_output"
                with patch.object(mixed, "__file__", str(producer / "capture_mixed_source.py")), \
                     patch.dict(os.environ, dict.fromkeys(core.NUMERIC, "1")), \
                     patch("subprocess.run", side_effect=AssertionError("no actual launch on failed role guard")), \
                     self.assertRaises(ValueError):
                    mixed.prepare(*args)


if __name__ == "__main__":
    unittest.main()
