"""Fictional metadata/ordinary bytes/injected processes; no numerical work."""

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

import capture_at_location as core
import fictional_support as fixture


def write(path, value, field="content_sha256"):
    path.parent.mkdir(parents=True, exist_ok=True)
    value = copy.deepcopy(value)
    if field is not None:
        value.pop(field, None)
        value[field] = core.io.canonical(value)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n")
    return core.io.sha(path)


class OriginalCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fictional-original-producer-")
        self.base = Path(self.temp.name).resolve(strict=True)
        self.source = self.base / "source"
        self.original = self.base / "original"
        self.output = self.base / "fresh_refit"
        self.capture_root = self.base / "capture"
        for name in ("scripts/reproduce_extensions.py", "scripts/verify_environment.py", "conda-lock.yml"):
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"# fictional immutable file; never imported or executed\n")
        digest = core.io.sha(self.source / "conda-lock.yml")
        self.hash_file = self.source / "conda-lock.yml.sha256"
        self.hash_file.write_text(digest + "  conda-lock.yml\n")
        selected = [f"cohort__condition__r01f01__clinical__model{n:03d}" for n in range(92)]
        # Official shards follow this reversed plan, not the sorted scope list.
        self.ordered = list(reversed(selected))
        plan = [{"cell_id": identity} for identity in self.ordered]
        plan += [{"cell_id": f"cohort__condition__r02f01__clinical__model{n:04d}"} for n in range(1533)]
        self.identity = self.ordered[8]
        self.original_manifest = {"code": {"git_commit": core.Policy().commit, "git_dirty": False},
            "plan": plan, "input_sha256": {name: core.io.sha(self.source / name) for name in
                ("scripts/reproduce_extensions.py", "scripts/verify_environment.py", "conda-lock.yml")},
            "matched_sha256": ""}
        self.matched = self.base / "matched.bytes"
        self.matched.write_bytes(b"fictional ordinary matched bytes; no data parser\n")
        self.original_manifest["matched_sha256"] = core.io.sha(self.matched)
        manifest_path = self.original / "manifest.json"
        manifest_sha = write(manifest_path, self.original_manifest, "manifest_content_sha256")
        manifest = core.io.read(manifest_path, field="manifest_content_sha256")
        self.policy = core.Policy(manifest_sha=manifest_sha, manifest_content_sha=manifest["manifest_content_sha256"],
                                  official_script_sha=core.io.sha(self.source / "scripts/reproduce_extensions.py"))
        self.source_cell = self.original / "cells" / (self.identity + ".json")
        write(self.source_cell, {"cell_id": self.identity, "status": "failed", "actual_fictional_fixture": True}, "cell_content_sha256")
        self.selection_path = self.base / "selection.json"
        selection_sha = write(self.selection_path, {"status": "reviewed_corrected_reproduction_selection", "schema_version": 1,
            "original_manifest_sha256": manifest_sha, "scope_rule": core.SCOPE_RULE,
            "original_selected_cells": sorted(selected), "selected_cells": sorted(selected), "pilot_cells": [],
            "paths": {"original_reproduction": str(self.output)}, "fictional_not_an_actual_review": True})
        self.choice_path = self.base / "root_choice.json"
        choice_sha = write(self.choice_path, {"status": "root_selected_missing_original_producer_proofs",
            "selection_sha256": selection_sha, "original_manifest_sha256": manifest_sha,
            "selected_missing_producer_cell_ids": [self.identity],
            "reason": "existing_actual_numerical_producer_proof_genuinely_unavailable",
            "source_score_selection": False, "automatic_all92_rerun": False, "fictional_not_an_actual_review": True})
        self.environment = {"status": "ok", "package_count": 259, "lock_sha256": digest, "python": "3.11.15",
                            "fictional_report_no_checker_executed": True}
        self.environment_path = self.base / "environment.json"
        environment_sha = write(self.environment_path, self.environment, None)
        self.request_path = self.base / "request.json"
        self.request = {"schema_version": 1, "status": "root_selected_original_producer_completion_request", "test_only": False,
            "route": "official_fresh_refit", "source": str(self.source), "original_run": str(self.original),
            "selected_reproduction_selection": {"path": str(self.selection_path), "sha256": selection_sha},
            "root_missing_producer_choice": {"path": str(self.choice_path), "sha256": choice_sha},
            "original_cell_id": self.identity, "workers": 92, "worker": 8, "matched": str(self.matched),
            "expected_environment_report": {"path": str(self.environment_path), "sha256": environment_sha},
            "lock_hash_file_sha256": core.io.sha(self.hash_file), "reproduction_output": str(self.output),
            "capture_output": str(self.capture_root)}
        self.calls = []
        self.numeric = dict.fromkeys(core.NUMERIC, "1")
        own = Path(core.__file__).absolute().parent
        self.preparation = {"implementation_source_sha256": {name: core.io.sha(own / name) for name in core.OWN}}
        fixture.enrich(self)

    def tearDown(self):
        self.temp.cleanup()

    def invoke(self, argv, **kwargs):
        self.calls.append(argv)
        if "rev-parse" in argv:
            return SimpleNamespace(returncode=0, stdout=self.policy.commit + "\n", stderr="")
        if "status" in argv:
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        self.assertTrue(all(kwargs["env"][name] == "1" for name in core.NUMERIC))
        self.assertEqual(kwargs["env"]["PYTHONDONTWRITEBYTECODE"], "1")
        if Path(argv[3]).name == "verify_environment.py":
            kwargs["stdout"].write((json.dumps(self.environment) + "\n").encode())
            kwargs["stderr"].write(b"fictional environment stderr\n")
        else:
            self.assertEqual(Path(argv[3]).name, "reproduce_extensions.py")
            self.assertFalse(any(self.output.iterdir()))
            self.assertEqual(argv[-4:], ["--workers", "92", "--worker", "8"])
            source = core.io.read(self.source_cell, field="cell_content_sha256")
            refit_path = self.output / "cells" / (self.identity + ".json")
            write(refit_path, source, "cell_content_sha256")
            refit = core.io.read(refit_path, field="cell_content_sha256")
            write(self.output / "receipts" / (self.identity + ".json"), {"cell_id": self.identity, "status": "scientific_match",
                "source_content_sha256": source["cell_content_sha256"], "refit_content_sha256": refit["cell_content_sha256"],
                "trace_sample_arrays": "exact; timing/NetCDF metadata excluded"}, None)
            orphan = self.output / "traces" / self.identity / "failed_orphan.nc"
            orphan.parent.mkdir(parents=True)
            orphan.write_bytes(b"fictional ordinary bytes; never parsed as traces\n")
            kwargs["stdout"].write((self.identity + " scientific_match\n").encode())
            kwargs["stderr"].write(b"fictional numerical stderr; no model ran\n")
        return SimpleNamespace(returncode=0)

    def run_capture(self, invoke=None, **kwargs):
        request_sha = write(self.request_path, self.request)
        return core.capture(self.request_path, request_sha, Path(sys.executable), self.preparation,
            dependencies={"invoke": self.invoke if invoke is None else invoke, "policy": self.policy, "environment": self.numeric, "context_loader": lambda *_: self.context},
            test_only=True, **kwargs)

    def test_single_fixed_identity_synthetic_capture_retains_failures_without_reviews(self):
        result = self.run_capture()
        self.assertEqual(result["status"], "synthetic_original_producer_completion_fixture_passed")
        self.assertTrue(result["test_only_dependency_injection"])
        self.assertTrue(result["scientific_reviews_still_pending"])
        self.assertEqual(len(self.calls), 6)
        numerical = core.io.read(self.capture_root / "numerical.attempt.json")
        self.assertEqual(numerical["exit_code"], 0)
        self.assertTrue(numerical["test_only_dependency_injection"])
        self.assertEqual(numerical["argv"][-4:], ["--workers", "92", "--worker", "8"])
        invocation = core.io.read(self.capture_root / "invocation_record.json")
        comparison = core.io.read(self.capture_root / "official_comparison_record.json")
        self.assertTrue(invocation["status"].startswith("synthetic_"))
        self.assertTrue(comparison["status"].startswith("synthetic_"))
        self.assertFalse(invocation["actual_numerical_refit_execution"])
        pending = core.io.read(self.capture_root / "producer_pending_review.json")
        self.assertIsNone(pending["scientific_lineage_review"])
        self.assertIsNone(pending["original_owner_execution_review"])
        self.assertIsNone(pending["original_numerical_resolution_review"])
        inventory = core.io.read(self.capture_root / "output_inventory.json")
        self.assertIn("traces/" + self.identity + "/failed_orphan.nc", inventory["artifacts"])
        self.assertFalse(inventory["trace_containers_parsed_by_adapter"])

    def test_production_api_refuses_dependency_injection(self):
        digest = write(self.request_path, self.request)
        with self.assertRaisesRegex(ValueError, "fictional"):
            core.capture(self.request_path, digest, Path(sys.executable), self.preparation, dependencies={"invoke": self.invoke})
        self.assertFalse(self.calls)
        self.assertFalse(self.capture_root.exists())

    def test_sorted_scope_position_is_not_official_plan_order(self):
        self.assertNotEqual(sorted(self.ordered).index(self.identity), 8)
        self.request["worker"] = sorted(self.ordered).index(self.identity)
        with self.assertRaisesRegex(ValueError, "plan-order"):
            self.run_capture()
        self.assertFalse(self.calls)

    def test_nonselected_identity_and_changed_scope_refuse(self):
        self.request["original_cell_id"] = self.ordered[7]
        with self.assertRaisesRegex(ValueError, "root-selected|review|root-chosen"):
            self.run_capture()
        self.request["original_cell_id"] = self.identity
        selection = core.io.read(self.selection_path)
        selection["original_selected_cells"].pop()
        self.request["selected_reproduction_selection"]["sha256"] = write(self.selection_path, selection)
        with self.assertRaisesRegex(ValueError, "ADR041"):
            self.run_capture()

    def test_changed_manifest_source_and_matched_bytes_refuse(self):
        self.matched.write_bytes(b"changed fictional bytes\n")
        with self.assertRaisesRegex(ValueError, "byte binding|bindings differ|preparation"):
            self.run_capture()
        self.assertFalse(self.capture_root.exists())

    def test_changed_own_capture_implementation_pin_refuses(self):
        self.preparation["implementation_source_sha256"]["capture_at_location.py"] = "f" * 64
        with self.assertRaisesRegex(ValueError, "byte binding|bindings differ|preparation"):
            self.run_capture()
        self.assertFalse(self.capture_root.exists())

    def test_existing_outputs_and_capture_collision_refuse(self):
        self.output.mkdir()
        with self.assertRaisesRegex(ValueError, "fresh absent"):
            self.run_capture()
        self.output.rmdir()
        self.capture_root.mkdir()
        with self.assertRaisesRegex(ValueError, "fresh absent"):
            self.run_capture()
        self.assertFalse(self.calls)

    def test_output_overlap_and_symlink_refuse(self):
        self.request["capture_output"] = str(self.original / "unsafe_capture")
        with self.assertRaisesRegex(ValueError, "overlaps|declared"):
            self.run_capture()
        linked = self.base / "linked"
        linked.symlink_to(self.source)
        self.request["capture_output"] = str(linked / "unsafe_capture")
        with self.assertRaisesRegex(ValueError, "linked"):
            self.run_capture()

    def test_alternate_root_differs_from_default_but_same_declared_root_is_used(self):
        self.assertNotEqual(self.selection["paths"]["original_reproduction"], str(self.output))
        result = self.run_capture()
        self.assertEqual(result["status"], "synthetic_original_producer_completion_fixture_passed")
        invocation = core.io.read(self.capture_root / "invocation_record.json")
        self.assertEqual(invocation["reproduction_output"], str(self.output))
        self.assertEqual(invocation["reproduction_location"]["historical_reproduction_root"], str(self.output))
        self.assertEqual(invocation["reproduction_location"]["location_plan_sha256"], self.request["location_plan"]["sha256"])

    def test_active_original_owner_refuses_before_dispatch(self):
        write(self.original / "claims" / (self.identity + ".json"), {"fictional_owner": True}, None)
        with self.assertRaisesRegex(ValueError, "owner still active"):
            self.run_capture()
        self.assertFalse(self.calls)

    def test_wrong_numeric_or_interpreter_runtime_refuses(self):
        self.numeric[core.NUMERIC[0]] = "2"
        with self.assertRaisesRegex(ValueError, "numeric"):
            self.run_capture()
        self.assertFalse(self.calls)
        self.numeric[core.NUMERIC[0]] = "1"
        request_sha = write(self.request_path, self.request)
        with self.assertRaisesRegex(ValueError, "current locked"):
            core.capture(self.request_path, request_sha, self.matched, self.preparation,
                dependencies={"invoke": self.invoke, "policy": self.policy, "environment": self.numeric, "context_loader": lambda *_: self.context}, test_only=True)

    def test_environment_mismatch_prevents_numerical_child(self):
        def invoke(argv, **kwargs):
            if len(argv) > 3 and Path(argv[3]).name == "verify_environment.py":
                kwargs["stdout"].write(json.dumps({**self.environment, "package_count": 258}).encode())
                return SimpleNamespace(returncode=0)
            return self.invoke(argv, **kwargs)
        with self.assertRaisesRegex(ValueError, "full259 report differs"):
            self.run_capture(invoke)
        self.assertFalse((self.capture_root / "numerical.attempt.json").exists())
        self.assertTrue((self.capture_root / "environment.attempt.json").exists())

    def test_numerical_failure_retains_rc_and_logs_no_success_receipt(self):
        def invoke(argv, **kwargs):
            if len(argv) > 3 and Path(argv[3]).name == "reproduce_extensions.py":
                kwargs["stdout"].write(b"fictional failed stdout\n")
                kwargs["stderr"].write(b"fictional precise stderr\n")
                return SimpleNamespace(returncode=17)
            return self.invoke(argv, **kwargs)
        with self.assertRaisesRegex(ValueError, "child failed"):
            self.run_capture(invoke)
        self.assertEqual(core.io.read(self.capture_root / "numerical.attempt.json")["exit_code"], 17)
        self.assertEqual((self.capture_root / "numerical.stderr.log").read_bytes(), b"fictional precise stderr\n")
        self.assertFalse((self.capture_root / "capture_receipt.json").exists())
        self.assertFalse((self.capture_root / "invocation_record.json").exists())

    def test_changed_bytes_after_numerical_child_prevent_producer_proof(self):
        def invoke(argv, **kwargs):
            result = self.invoke(argv, **kwargs)
            if len(argv) > 3 and Path(argv[3]).name == "reproduce_extensions.py":
                (self.source / "scripts/reproduce_extensions.py").write_bytes(b"# changed fictional source after child\n")
            return result
        with self.assertRaisesRegex(ValueError, "changed"):
            self.run_capture(invoke)
        self.assertFalse((self.capture_root / "invocation_record.json").exists())
        self.assertFalse((self.capture_root / "capture_receipt.json").exists())

    def test_dirty_source_refuses_before_output_creation(self):
        def invoke(argv, **kwargs):
            if "status" in argv:
                return SimpleNamespace(returncode=0, stdout=" M scripts/reproduce_extensions.py\n", stderr="")
            return self.invoke(argv, **kwargs)
        with self.assertRaisesRegex(ValueError, "clean original119"):
            self.run_capture(invoke)
        self.assertFalse(self.capture_root.exists())
        self.assertFalse(self.output.exists())

    def test_reserved_output_race_cannot_become_cached_refit(self):
        def invoke(argv, **kwargs):
            result = self.invoke(argv, **kwargs)
            if len(argv) > 3 and Path(argv[3]).name == "verify_environment.py":
                (self.output / "unexpected_prior_cell.bytes").write_bytes(b"fictional competing output\n")
            return result
        with self.assertRaisesRegex(ValueError, "no longer empty"):
            self.run_capture(invoke)
        self.assertFalse((self.capture_root / "numerical.attempt.json").exists())

    def test_source_score_selection_and_automatic_all92_choice_refuse(self):
        for field in ("source_score_selection", "automatic_all92_rerun"):
            with self.subTest(field=field):
                choice = core.io.read(self.choice_path)
                choice[field] = True
                self.request["root_missing_producer_choice"]["sha256"] = write(self.choice_path, choice)
                with self.assertRaisesRegex(ValueError, "root-selected missing"):
                    self.run_capture()
                choice[field] = False
                self.request["root_missing_producer_choice"]["sha256"] = write(self.choice_path, choice)
        self.assertFalse(self.calls)

    def test_launch_error_retains_none_rc_without_success(self):
        def invoke(argv, **kwargs):
            if len(argv) > 3 and Path(argv[3]).name == "reproduce_extensions.py":
                raise OSError("fictional launch error")
            return self.invoke(argv, **kwargs)
        with self.assertRaises(ValueError):
            self.run_capture(invoke)
        attempt = core.io.read(self.capture_root / "numerical.attempt.json")
        self.assertIsNone(attempt["exit_code"])
        self.assertIsNotNone(attempt["launch_error"])
        self.assertFalse((self.capture_root / "capture_receipt.json").exists())

    def test_receipt_or_stdout_mismatch_is_not_completion(self):
        def invoke(argv, **kwargs):
            result = self.invoke(argv, **kwargs)
            if len(argv) > 3 and Path(argv[3]).name == "reproduce_extensions.py":
                write(self.output / "receipts" / (self.identity + ".json"), {"status": "scientific_match"}, None)
            return result
        with self.assertRaisesRegex(ValueError, "five-field"):
            self.run_capture(invoke)
        self.assertFalse((self.capture_root / "capture_receipt.json").exists())

    def test_source_mutation_after_child_and_unknown_output_refuse(self):
        def invoke(argv, **kwargs):
            result = self.invoke(argv, **kwargs)
            if len(argv) > 3 and Path(argv[3]).name == "reproduce_extensions.py":
                (self.output / "unknown_failure_file.log").write_bytes(b"extra retained fictional failure\n")
            return result
        with self.assertRaisesRegex(ValueError, "unexpected/partial"):
            self.run_capture(invoke)
        self.assertTrue((self.output / "unknown_failure_file.log").exists())
        self.assertFalse((self.capture_root / "capture_receipt.json").exists())

    def test_atomic_receipt_publication_failure_has_no_reported_success(self):
        original_link = os.link
        def fail(source, destination, *args, **kwargs):
            if Path(destination).name == "capture_receipt.json":
                raise OSError("fictional receipt link failure")
            return original_link(source, destination, *args, **kwargs)
        with patch("os.link", fail), self.assertRaises(OSError):
            self.run_capture()
        self.assertFalse((self.capture_root / "capture_receipt.json").exists())
        self.assertEqual(len(list(self.capture_root.glob(".verification-pending-capture_receipt.json-*"))), 1)


if __name__ == "__main__":
    unittest.main()
