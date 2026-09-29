"""Fictional/injected transport guards; no science or real process is invoked."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).absolute().parent
sys.dont_write_bytecode = True
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
import release_v3_core as v3  # noqa: E402


class Fixture(unittest.TestCase):
    """Use disposable invented JSON/bytes under this preparation only."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fictional-v3-", dir=ROOT)
        self.root = Path(self.temporary.name)
        self.core = v3.foundation()
        self.io_root = ROOT / "preserved_per_entry_io_v1"
        self.prepared = v3.io_prepare(self.io_root)
        self.own = {"implementation_source_sha256": {name: v3.byte_sha(ROOT / name) for name in v3.OWN_NAMES}}
        self.own_sha = "b" * 64
        self.fixture_code = self.root / "invented_owned_source"
        self.fixture_code.mkdir()
        for name in v3.OWN_NAMES:
            (self.fixture_code / name).write_bytes((ROOT / name).read_bytes())
        self.source = self.root / "invented_entrypoint.py"
        self.source.write_text('"""Fictional stdlib source; never dispatched."""\n')
        self.source_sha = v3.byte_sha(self.source)

    def tearDown(self):
        self.temporary.cleanup()

    def document(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        self.core.write_new(path, self.core.seal({"fictional_fixture_only": True, **value}))
        return {"path": str(path), "sha256": v3.byte_sha(path)}

    def capture(self, callback=None, *, rc=0, name="captured", producer=None):
        summary = {"status": "fictional_completed", "fictional_fixture_only": True}
        def invoke(argv, **kwargs):
            self.assertEqual(kwargs["env"]["NUMEXPR_NUM_THREADS"], "1")
            if callback is not None:
                callback()
            return SimpleNamespace(returncode=rc, stdout=json.dumps(summary).encode() + b"\n", stderr=b"retained fictional stderr")
        prefix = self.root / name
        argv = [str(Path(sys.executable).absolute()), "-I", "-B", str(self.source)]
        result = v3.process_capture(argv, prefix, self.core.Pins(), status="fictional_capture_completed",
            checked=lambda value: self.assertEqual(value, summary), entrypoint=self.source, entrypoint_sha=self.source_sha,
            producer=producer or {"revision": 3, "fictional_fixture_only": True}, invoke=invoke, test_only=True)
        return result, argv

    def controller_request(self):
        plan_path = self.root / "plan.json"
        plan = self.document("plan.json", {"historical_plan_path": str(plan_path)})
        training = self.root / "training_metadata_only"
        training.mkdir()
        selection = self.document("selection.json", {"paths": {"invented_input": str(training)}})
        output = self.root / "selected_output"
        request = {"schema_version": 3, "status": "per_entry_release_v3_source_capture_request", "test_only": False,
            "mode": "controller", "io_preparation": {"path": str(self.io_root / "preparation_receipt.json"), "sha256": v3.PER_ENTRY_SHA},
            "location_plan": plan, "selection": selection, "evidence_output": str(output),
            "capture_prefix": str(self.root / "controller_capture"), "immutable_roots": [str(training)], "immutable_files": [],
            "reviews": {"pilot-review": None, "resolution-review": None, "original-numerical-resolution": None}}
        return request, output

    def invoke_controller(self, request, output, *, wrong_envelope=False, mutate_request=False, rc=0):
        def invoke(argv, **kwargs):
            self.assertIn("run_selected_at_locations.py", argv[3])
            output.mkdir()
            (output / "passes").mkdir()
            envelope = {"location_plan_path": request["location_plan"]["path"],
                "location_plan_sha256": "c" * 64 if wrong_envelope else request["location_plan"]["sha256"],
                "io_adapter_source_sha256": self.prepared["implementation_source_sha256"],
                "legacy_source_sha256": self.prepared["legacy_source_sha256"], "selection_bytes_rewritten": False}
            summary = {"status": "all_selected_reproduction_outcomes_accounted", "selection_sha256": request["selection"]["sha256"],
                       "scheduled_selected_cells": 1, "accounted_selected_cells": 1, "fictional_fixture_only": True}
            receipt = output / "passes" / "fictional.json"
            self.core.write_new(receipt, self.core.seal({**summary, "location_extension": envelope}))
            summary.update(pass_receipt_path=str(receipt), pass_receipt_sha256=v3.byte_sha(receipt))
            if mutate_request:
                Path(request["selection"]["path"]).write_text("changed fictional input")
            return SimpleNamespace(returncode=rc, stdout=json.dumps(summary).encode() + b"\n", stderr=b"")
        return invoke

    def fictional_source_capture(self, request, binding, invoke, *, test_only=True):
        """Isolate mocked host source paths; no production guard is changed."""
        with patch.object(v3, "__file__", str(self.fixture_code / "release_v3_core.py")), patch.object(v3, "foundation", return_value=self.core):
            return v3.source_capture(request, binding, Path(sys.executable).absolute(), self.own, self.own_sha,
                                     invoke=invoke, test_only=test_only)

    def test_predecessor_small_byte_pins(self):
        for role, expected in (("preserved_release_v2", v3.RELEASE_V2_SHA), ("preserved_receiving_v1", v3.RECEIVING_V1_SHA),
                               ("preserved_per_entry_io_v1", v3.PER_ENTRY_SHA)):
            with self.subTest(role=role):
                self.assertIn("artifacts", v3.checked_prepare(ROOT / role, expected))
        self.assertEqual(v3.byte_sha(ROOT / "preserved_per_entry_io_review_v1" / "receipt.json"), v3.PER_ENTRY_REVIEW_SHA)

    def test_duplicate_nonfinite_and_nonobject_json_refused(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}', b'[]'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                v3.strict_json(raw)

    def test_preparation_member_content_and_traversal_refused(self):
        root = self.root / "preparation"
        root.mkdir()
        member = root / "member.txt"
        member.write_bytes(b"invented member")
        value = {"artifacts": {"member.txt": {"sha256": v3.byte_sha(member), "bytes": member.stat().st_size}}}
        receipt = root / "preparation_receipt.json"
        self.core.write_new(receipt, self.core.seal(value))
        digest = v3.byte_sha(receipt)
        self.assertIn("artifacts", v3.checked_prepare(root, digest))
        member.write_bytes(b"different")
        with self.assertRaises(ValueError):
            v3.checked_prepare(root, digest)
        receipt.unlink()
        self.core.write_new(receipt, self.core.seal({"artifacts": {"../member.txt": {"sha256": "a" * 64, "bytes": 1}}}))
        with self.assertRaises(ValueError):
            v3.checked_prepare(root, v3.byte_sha(receipt))

    def test_linked_preparation_and_adapter_refused(self):
        linked = self.root / "linked.py"
        linked.symlink_to(self.source)
        with self.assertRaises(ValueError):
            v3.import_file(linked, self.source_sha, "_fictional_link")
        root = self.root / "linked_preparation"
        root.symlink_to(ROOT / "preserved_per_entry_io_v1", target_is_directory=True)
        with self.assertRaises(ValueError):
            v3.checked_prepare(root, v3.PER_ENTRY_SHA)

    def test_pinned_import_namespace_and_changed_source(self):
        name = "_fictional_v3_import"
        module = v3.import_file(self.source, self.source_sha, name)
        try:
            self.assertEqual(Path(module.__file__), self.source)
            with self.assertRaises(ValueError):
                v3.import_file(self.source, self.source_sha, name)
        finally:
            sys.modules.pop(name, None)
        with self.assertRaises(ValueError):
            v3.import_file(self.source, "e" * 64, name)
        self.assertNotIn(name, sys.modules)

    def test_controller_argv_keeps_explicit_optional_reviews(self):
        request, _ = self.controller_request()
        review = self.document("review.json", {"status": "fictional_not_a_root_review"})
        request["reviews"]["resolution-review"] = review
        argv = v3.controller_argv("/fictional/python", self.io_root, request)
        self.assertEqual(argv[1:4], ["-I", "-B", str(self.io_root / "run_selected_at_locations.py")])
        self.assertEqual(argv[-4:], ["--resolution-review", review["path"], "--resolution-review-sha256", review["sha256"]])
        request["reviews"]["foreign"] = None
        with self.assertRaises(ValueError):
            v3.controller_argv("/fictional/python", self.io_root, request)

    def test_new_receiving_command_is_read_only_and_separately_named(self):
        argv = v3.receiving_argv("/fictional/python", self.io_root, {"path": "/fictional/bindings", "sha256": "a" * 64},
                                 {"path": "/fictional/plan", "sha256": "b" * 64}, self.root / "new_review")
        self.assertEqual(argv[3], str(self.io_root / "verify_restored_at_locations.py"))
        self.assertIn(v3.PER_ENTRY_SHA, argv)
        self.assertNotIn("--execute", argv)
        self.assertNotIn("--resume", argv)

    def test_core_proxy_preserves_old_predicate_identity(self):
        view = v3.CoreView({"tree_roles": {}}, self.own, self.own_sha)
        for name in ("validate_mixed", "validate_visual", "validate_reporting", "validate_retained", "structural_gates",
                     "captured_command", "validate_mixed_capture_producer", "verify_tree", "validate_extra_retention"):
            if name != "captured_command":
                self.assertIs(getattr(view, name), getattr(self.core, name))
        self.assertEqual({key: view.LAYOUT[key] for key in self.core.LAYOUT}, self.core.LAYOUT)

    def test_old_asset_optional_roles_are_decided_by_unchanged_gate(self):
        view = v3.CoreView({"tree_roles": {}}, self.own, self.own_sha)
        old_roles = set(self.core.LAYOUT) - {"resolution_review", "pilot_review"}
        assets = {name: {} for name in old_roles | set(view.extra)}
        with patch.object(self.core, "validate_assets", side_effect=RuntimeError("stop at fictional original gate")) as gate:
            with self.assertRaises(RuntimeError):
                view.validate_assets({"assets": assets}, {}, self.core.Pins())
        self.assertEqual(set(gate.call_args.args[0]["assets"]), old_roles)

    def test_old_reproduction_failure_is_never_bypassed(self):
        view = v3.CoreView({"tree_roles": {}}, self.own, self.own_sha)
        with patch.object(self.core, "validate_reproduction", side_effect=ValueError("fictional original completion missing")) as gate:
            with self.assertRaises(ValueError):
                view.validate_reproduction({}, {}, {}, [], self.core.Pins(), self.core.Policy(test_only=True))
        gate.assert_called_once()

    def test_exact_distinct_tree_role_names(self):
        roles = {"fictional": {"numerical": "per_entry_numerical__fictional", "capture": "per_entry_capture__fictional"}}
        view = v3.CoreView({"tree_roles": roles}, self.own, self.own_sha)
        self.assertEqual(view.LAYOUT[roles["fictional"]["numerical"]], "evidence/per_entry_original_reproduction/fictional")
        for invalid in ("../escape", "", "/absolute"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                v3.CoreView({"tree_roles": {invalid: roles["fictional"]}}, self.own, self.own_sha)
        roles["fictional"]["capture"] = "original_reproduction"
        with self.assertRaises(ValueError):
            v3.CoreView({"tree_roles": roles}, self.own, self.own_sha)

    def test_legacy_alias_restored_even_after_exception(self):
        view = v3.CoreView({"tree_roles": {}}, self.own, self.own_sha)
        sentinel = SimpleNamespace(fictional=True)
        prior = sys.modules.get("release_core")
        sys.modules["release_core"] = sentinel
        try:
            with self.assertRaises(RuntimeError):
                with v3.legacy_module(ROOT / "preserved_release_v2", "stage_corrected_extensions.py", view) as module:
                    self.assertIs(module.core, view)
                    self.assertEqual(Path(module.__file__).parent, ROOT / "preserved_release_v2")
                    raise RuntimeError("fictional delegate failure")
            self.assertIs(sys.modules["release_core"], sentinel)
            self.assertNotIn("_release_v3_delegate_stage_corrected_extensions", sys.modules)
        finally:
            if prior is None:
                sys.modules.pop("release_core", None)
            else:
                sys.modules["release_core"] = prior

    def test_final_stage_cannot_publish_without_extension(self):
        view = v3.CoreView({"tree_roles": {}}, self.own, self.own_sha)
        with self.assertRaises(ValueError):
            view.seal({"status": "corrected_private_payload_staged_with_separate_actual_source_gates"})
        view.extension = {"revision": 3, "fictional_fixture_only": True}
        result = view.seal({"status": "corrected_private_payload_staged_with_separate_actual_source_gates"})
        self.assertFalse(result["old_preparation_and_source_maps_replaced"])

    def test_fictional_capture_raw_exit_and_injection_flag(self):
        value, _ = self.capture()
        self.assertEqual(value["exit_code"], 0)
        self.assertTrue(value["test_only_dependency_injection"])
        self.assertFalse(value["runtime"]["locked_interpreter_samefile"])
        self.assertFalse(value["programme_complete"])
        self.core.capture_record(Path(value["receipt_path"]), value["receipt_sha256"], self.core.Pins(),
            status="fictional_capture_completed", summary_status="fictional_completed")

    def test_nonzero_and_boolean_exit_do_not_install_success(self):
        for rc, name in ((7, "exit7"), (False, "boolean_exit")):
            with self.subTest(rc=rc), self.assertRaises(ValueError):
                self.capture(rc=rc, name=name)
            self.assertTrue((self.root / (name + ".attempt.json")).exists())
            self.assertTrue((self.root / (name + ".stdout.log")).exists())
            self.assertFalse((self.root / (name + ".receipt.json")).exists())

    def test_launch_exception_retains_actual_unavailable(self):
        def refused(*args, **kwargs):
            raise OSError("fictional launch unavailable")
        prefix = self.root / "launch_failure"
        with self.assertRaises(ValueError):
            v3.process_capture([str(Path(sys.executable)), "-I", "-B", str(self.source)], prefix, self.core.Pins(),
                status="never", checked=lambda _: None, entrypoint=self.source, entrypoint_sha=self.source_sha,
                producer={"fictional": True}, invoke=refused, test_only=True)
        attempt = self.core.document(self.root / "launch_failure.attempt.json", self.core.Pins())
        self.assertIsNone(attempt["exit_code"])
        self.assertEqual(attempt["launch_error"]["type"], "builtins.OSError")
        self.assertFalse((self.root / "launch_failure.receipt.json").exists())

    def test_capture_collision_refuses_without_invoke(self):
        prefix = self.root / "collision"
        prefix.write_bytes(b"existing")
        with self.assertRaises(ValueError):
            self.capture(name="collision")
        self.assertEqual(prefix.read_bytes(), b"existing")
        self.capture(name="four_file_collision")
        with self.assertRaises(ValueError):
            self.capture(name="four_file_collision")

    def test_injected_capture_cannot_pass_production_command_gate(self):
        value, argv = self.capture()
        path = Path(value["receipt_path"])
        with self.assertRaises(ValueError):
            v3.checked_command(path, value, self.core.Pins(), argv, self.source_sha, value["capture_producer"])
        v3.checked_command(path, value, self.core.Pins(), argv, self.source_sha, value["capture_producer"], test_only=True)

    def test_changed_command_or_producer_is_refused(self):
        value, argv = self.capture()
        for command, producer in (([*argv, "--foreign"], value["capture_producer"]), (argv, {"revision": 2})):
            with self.subTest(command=command), self.assertRaises(ValueError):
                v3.checked_command(Path(value["receipt_path"]), value, self.core.Pins(), command, self.source_sha, producer, test_only=True)

    def test_controller_capture_binds_actual_written_pass_not_invented_stdout(self):
        request, output = self.controller_request()
        request_binding = self.document("capture_request.json", request)
        result = self.fictional_source_capture(request, request_binding, self.invoke_controller(request, output))
        value = self.core.document(Path(result["receipt_path"]), self.core.Pins())
        self.assertNotIn("location_extension", value["summary"])
        self.assertTrue(value["test_only_dependency_injection"])
        self.assertFalse(result["programme_complete"])

    def test_controller_foreign_written_pass_refused(self):
        request, output = self.controller_request()
        binding = self.document("capture_request.json", request)
        with self.assertRaises(ValueError):
            self.fictional_source_capture(request, binding, self.invoke_controller(request, output, wrong_envelope=True))
        self.assertTrue((self.root / "controller_capture.attempt.json").exists())
        self.assertFalse((self.root / "controller_capture.receipt.json").exists())

    def test_controller_input_changed_during_actual_capture_refused(self):
        request, output = self.controller_request()
        binding = self.document("capture_request.json", request)
        with self.assertRaises(ValueError):
            self.fictional_source_capture(request, binding, self.invoke_controller(request, output, mutate_request=True))
        self.assertFalse((self.root / "controller_capture.receipt.json").exists())

    def test_production_injection_is_refused_before_launch(self):
        request, output = self.controller_request()
        binding = self.document("capture_request.json", request)
        with self.assertRaises(ValueError):
            self.fictional_source_capture(request, binding, self.invoke_controller(request, output), test_only=False)
        self.assertFalse(output.exists())

    def test_immutable_input_overlap_refuses_before_mock_dispatch(self):
        request, output = self.controller_request()
        request["evidence_output"] = request["immutable_roots"][0]
        binding = self.document("capture_request.json", request)
        with self.assertRaises(ValueError):
            self.fictional_source_capture(request, binding, self.invoke_controller(request, output))
        self.assertFalse(output.exists())

    def test_old_maps_cannot_be_rebranded_as_new_receiving(self):
        plan = self.document("plan.json", {"historical_plan_path": "/fictional/historical_plan.json"})
        value = {"reproduction_source_sha256": self.prepared["legacy_source_sha256"]["selected"],
            "receiving_source_sha256": self.prepared["legacy_source_sha256"]["receiving"],
            "location_receiving_code": str(ROOT / "preserved_receiving_v1"),
            "location_extension": {"location_plan": {"historical_path": "/fictional/historical_plan.json", "sha256": plan["sha256"]},
                                   "io_adapter_source_sha256": self.prepared["implementation_source_sha256"]}}
        view = v3.CoreView({"tree_roles": {}}, self.own, self.own_sha)
        view.check_receiving_bindings(value, plan, ROOT / "preserved_receiving_v1", self.prepared)
        value["receiving_source_sha256"] = self.prepared["implementation_source_sha256"]
        with self.assertRaises(ValueError):
            view.check_receiving_bindings(value, plan, ROOT / "preserved_receiving_v1", self.prepared)

    def test_readonly_source_capture_binds_real_named_receipt_in_fictional_fixture(self):
        plan_path = self.root / "plan.json"
        plan = self.document("plan.json", {"historical_plan_path": str(plan_path)})
        inputs = {"immutable_roots": [{"root": str(ROOT / "preserved_receiving_v1")}], "immutable_files": [],
            "selection_sha256": "a" * 64, "completed_pass": {"path": "passes/fictional.json", "sha256": "b" * 64},
            "location_receiving_code": str(ROOT / "preserved_receiving_v1"),
            "reproduction_source_sha256": self.prepared["legacy_source_sha256"]["selected"],
            "receiving_source_sha256": self.prepared["legacy_source_sha256"]["receiving"],
            "location_extension": {"location_plan": {"historical_path": str(plan_path), "sha256": plan["sha256"]},
                                   "io_adapter_source_sha256": self.prepared["implementation_source_sha256"]}}
        input_binding = self.document("receiving_bindings.json", inputs)
        output = self.root / "fresh_readonly_proof"
        request = {"schema_version": 3, "status": "per_entry_release_v3_source_capture_request", "test_only": False,
            "mode": "read_only", "io_preparation": {"path": str(self.io_root / "preparation_receipt.json"), "sha256": v3.PER_ENTRY_SHA},
            "location_plan": plan, "input_request": input_binding, "evidence_output": str(output),
            "capture_prefix": str(self.root / "readonly_capture"), "immutable_roots": [str(ROOT / "preserved_receiving_v1")], "immutable_files": []}
        binding = self.document("readonly_capture_request.json", request)
        def invoke(argv, **kwargs):
            self.assertTrue(argv[3].endswith("verify_restored_at_locations.py"))
            output.mkdir()
            evidence = output / "fictional_scientific_comparison.json"
            evidence.write_bytes(b'{"fictional_fixture_only":true}\n')
            receipt = {"status": "corrected_selected_reproduction_restored_read_only_verified", "bindings_sha256": input_binding["sha256"],
                "selection_sha256": inputs["selection_sha256"], "completed_pass_sha256": inputs["completed_pass"]["sha256"],
                "new_numerical_fit_executed": False, "new_generator_recipe_executed": False, "test_only_dependency_injection": False,
                "io_adapter_source_sha256": self.prepared["implementation_source_sha256"], "fictional_fixture_only": True,
                "artifacts": {evidence.name: {"sha256": v3.byte_sha(evidence), "bytes": evidence.stat().st_size}}}
            self.core.write_new(output / "receipt.json", self.core.seal(receipt))
            summary = {"status": receipt["status"], "selection_sha256": inputs["selection_sha256"],
                "selected_pass_sha256": inputs["completed_pass"]["sha256"], "scheduled_selected_cells": 1, "accounted_selected_cells": 1,
                "no_new_numerical_fit": True, "no_new_generator_recipe": True, "location_plan_sha256": plan["sha256"],
                "io_adapter_source_sha256": self.prepared["implementation_source_sha256"],
                "receipt_path": str(output / "receipt.json"), "receipt_sha256": v3.byte_sha(output / "receipt.json")}
            return SimpleNamespace(returncode=0, stdout=json.dumps(summary).encode() + b"\n", stderr=b"")
        result = self.fictional_source_capture(request, binding, invoke)
        receipt = self.core.document(Path(result["receipt_path"]), self.core.Pins())
        self.assertTrue(receipt["test_only_dependency_injection"])
        self.assertEqual(receipt["summary"]["receipt_sha256"], v3.byte_sha(output / "receipt.json"))

    def test_restored_distinct_tree_directory_maps_required(self):
        roles = {"fictional": {"numerical": "per_entry_numerical__fictional", "capture": "per_entry_capture__fictional"}}
        extension = {"revision": 3, "per_entry_preparation_sha256": v3.PER_ENTRY_SHA, "tree_roles": roles,
            "location_plan": {"sha256": "d" * 64}, "release_v3_preparation_sha256": self.own_sha,
            "per_entry_independent_source_review_sha256": v3.PER_ENTRY_REVIEW_SHA,
            "legacy_receiving_preparation_sha256": v3.RECEIVING_V1_SHA,
            "legacy_release_v2_preparation_sha256": v3.RELEASE_V2_SHA, "old_historical_source_maps_rewritten": False}
        view = v3.ReceivingView({"tree_roles": roles, "location_plan": {"sha256": "d" * 64}}, self.own, self.own_sha,
            {"per_entry_release_wiring_v3": extension, "historical_roots": {}}, self.root / "restored", {"path": "/fictional/request", "sha256": "f" * 64})
        names = [*roles["fictional"].values(), "per_entry_io_preparation", "original_capture_preparation", "receiving_reproduction_preparation"]
        view.manifest["historical_roots"] = {name: {"historical_source": "/fictional/" + name, "payload_relative": view.LAYOUT[name]} for name in names}
        rows = [{"historical": "/fictional/" + name, "restored": str(view.restored / view.LAYOUT[name]), "kind": "directory"} for name in names]
        view.check_restored_maps({"path_map": rows})
        for altered in (rows[:-1], [*rows, rows[0]], [{**rows[0], "kind": "file"}, *rows[1:]]):
            with self.subTest(altered=altered), self.assertRaises(ValueError):
                view.check_restored_maps({"path_map": altered})

    def test_full_tree_and_prior_history_are_retained_or_refused(self):
        identity = "fictional"
        roles = {identity: {"numerical": "per_entry_numerical__fictional", "capture": "per_entry_capture__fictional"}}
        numerical, capture = self.root / "numeric_tree", self.root / "capture_tree"
        numerical.mkdir()
        capture.mkdir()
        (numerical / "empty_orphan_directory").mkdir()
        (numerical / "failed_attempt.bin").write_bytes(b"fictional failed bytes")
        self.core.write_new(capture / "capture_receipt.json", self.core.seal({"io_adapter_source_sha256": self.prepared["implementation_source_sha256"]}))
        tree_pins = self.core.Pins()
        num_inventory, cap_inventory = (self.core.inventory_tree(path, tree_pins) for path in (numerical, capture))
        proof = {"reproduction_location": {"original_cell_id": identity, "location_plan_sha256": "p" * 64},
            "retained_original_reproduction_tree": {"artifacts": num_inventory["files"], "directories": num_inventory["directories"]},
            "retained_original_capture_tree": {"artifacts": cap_inventory["files"], "directories": cap_inventory["directories"]}}
        repro = self.root / "reproduction"
        (repro / "cells").mkdir(parents=True)
        (repro / "passes").mkdir()
        legacy_roots = {"selected": "/fictional/old_selected", "receiving": "/fictional/old_receiving", "capture": "/fictional/old_capture"}
        plan_path = self.root / "plan.json"
        plan_binding = self.document("plan.json", {"historical_plan_path": str(plan_path), "entry_locations": {
            identity: {"capture_root": str(capture)}}, "legacy_code_roots": legacy_roots, "legacy_source_sha256": self.prepared["legacy_source_sha256"]})
        prior = self.document("prior_plan.json", {"historical_plan_path": str(self.root / "prior_plan.json")})
        envelope = {"location_plan_path": str(plan_path), "location_plan_sha256": plan_binding["sha256"]}
        record = {"status": "reused_verified_original_numerical_reproduction", "location_extension": envelope,
            "reproduction_location": proof["reproduction_location"], "retained_per_entry_trees": proof}
        self.core.write_new(repro / "cells" / "fictional.json", self.core.seal(record))
        pass_path = repro / "passes" / "pass.json"
        self.core.write_new(pass_path, self.core.seal({"location_extension": envelope}))
        plan_pins = self.core.Pins()
        plan_pins.bind(plan_path, plan_binding["sha256"])
        plan_pins.bind(Path(prior["path"]), prior["sha256"])
        locations = SimpleNamespace(envelope=lambda: envelope, metadata=lambda _: proof["reproduction_location"],
            actual=lambda _: numerical, resolve=lambda text: Path(text), verify_envelope=lambda value, _: self.assertEqual(value, envelope),
            recheck=plan_pins.recheck, pins=plan_pins,
            history={plan_binding["sha256"]: {"historical_plan_path": str(plan_path)}, prior["sha256"]: {"historical_plan_path": prior["path"]}})
        wiring = {"revision": 3, "tree_roles": roles, "location_plan": plan_binding,
            "controller_capture": {"sha256": "c" * 64}, "controller_request": {"sha256": "r" * 64}, "source_capture_request": {"sha256": "s" * 64}}
        view = v3.CoreView(wiring, self.own, self.own_sha)
        view.location_module = SimpleNamespace(acquired=lambda *args: proof)
        roots = {"per_entry_io_preparation": self.io_root, "per_entry_location_plan": plan_path, "reproduction": repro,
            "reproduction_preparation": Path(legacy_roots["selected"]), "receiving_reproduction_preparation": Path(legacy_roots["receiving"]),
            "original_capture_preparation": Path(legacy_roots["capture"]), roles[identity]["numerical"]: numerical, roles[identity]["capture"]: capture}
        result = {"selected_cells": [identity], "pass_sha256": v3.byte_sha(pass_path)}
        request = {"reproduction_pass": {"relative_path": "passes/pass.json", "sha256": v3.byte_sha(pass_path)}, "assets": {
            roles[identity]["numerical"]: {"inventory": num_inventory}, roles[identity]["capture"]: {"inventory": cap_inventory}}}
        with patch.object(self.core, "validate_reproduction", return_value=result), patch.object(view, "load_locations", return_value=({"numerical": {identity: {}}}, locations)), patch.object(view, "check_controller"), patch.object(self.core, "explicit_retention", return_value=True) as retention:
            view.validate_reproduction(roots, request, {}, [identity], self.core.Pins(), self.core.Policy(test_only=True))
            self.assertIn(prior["sha256"], view.extension["location_history"])
            self.assertTrue(any(call.args[1] == prior["sha256"] for call in retention.call_args_list))
            broken = {**request, "assets": {**request["assets"], roles[identity]["numerical"]: {"inventory": {"files": num_inventory["files"], "directories": []}}}}
            with self.assertRaises(ValueError):
                view.validate_reproduction(roots, broken, {}, [identity], self.core.Pins(), self.core.Policy(test_only=True))
        with patch.object(self.core, "validate_reproduction", return_value=result), patch.object(view, "load_locations", return_value=({"numerical": {identity: {}}}, locations)), patch.object(self.core, "explicit_retention", return_value=False):
            with self.assertRaises(ValueError):
                view.validate_reproduction(roots, request, {}, [identity], self.core.Pins(), self.core.Policy(test_only=True))

    def test_receiver_final_version_pins_cannot_change(self):
        extension = {"revision": 3, "per_entry_preparation_sha256": v3.PER_ENTRY_SHA, "tree_roles": {},
            "location_plan": {"sha256": "d" * 64}, "release_v3_preparation_sha256": self.own_sha,
            "per_entry_independent_source_review_sha256": v3.PER_ENTRY_REVIEW_SHA,
            "legacy_receiving_preparation_sha256": "wrong", "legacy_release_v2_preparation_sha256": v3.RELEASE_V2_SHA,
            "old_historical_source_maps_rewritten": False}
        with self.assertRaises(ValueError):
            v3.ReceivingView({"tree_roles": {}, "location_plan": {"sha256": "d" * 64}}, self.own, self.own_sha,
                {"per_entry_release_wiring_v3": extension}, self.root / "restored", {})

    def receiver_view(self):
        extension = {"revision": 3, "per_entry_preparation_sha256": v3.PER_ENTRY_SHA, "tree_roles": {},
            "location_plan": {"sha256": "d" * 64}, "release_v3_preparation_sha256": self.own_sha,
            "per_entry_independent_source_review_sha256": v3.PER_ENTRY_REVIEW_SHA,
            "legacy_receiving_preparation_sha256": v3.RECEIVING_V1_SHA, "legacy_release_v2_preparation_sha256": v3.RELEASE_V2_SHA,
            "old_historical_source_maps_rewritten": False, "io_adapter_source_sha256": self.prepared["implementation_source_sha256"],
            "legacy_source_sha256": self.prepared["legacy_source_sha256"]}
        restored = self.root / "restored"
        root = restored / v3.STATIC_LAYOUT["per_entry_io_preparation"]
        root.mkdir(parents=True)
        for name in [*v3.IO_NAMES, "preparation_receipt.json"]:
            (root / name).write_bytes((self.io_root / name).read_bytes())
        plan = {"path": str(restored / v3.STATIC_LAYOUT["per_entry_location_plan"]), "sha256": "d" * 64}
        return v3.ReceivingView({"tree_roles": {}, "location_plan": plan}, self.own, self.own_sha,
            {"per_entry_release_wiring_v3": extension}, restored, {"path": "/fictional/remote_request", "sha256": "f" * 64})

    def test_receiver_changes_only_exact_read_only_entrypoint(self):
        view = self.receiver_view()
        old = view.restored / self.core.LAYOUT["receiving_reproduction_preparation"] / "verify_restored_reproduction.py"
        binding = self.document("read_only_binding.json", {"selection_sha256": "a" * 64})
        output = self.root / "fresh_replay"
        output.mkdir()
        prefix = output / "reproduction_process"
        argv = ["/fictional/python", "-I", "-B", str(old), "--bindings", binding["path"], "--bindings-sha256", binding["sha256"],
                "--output", str(output / "reproduction_review"), "--python", "/fictional/python"]
        with patch.object(v3, "io_prepare", return_value=self.prepared), patch.object(view, "check_receiving_bindings"), patch.object(view, "check_restored_maps"), patch.object(v3, "process_capture", return_value={"fictional_fixture_only": True}) as capture:
            view.capture_process(argv, prefix, self.core.Pins(), entrypoint=old, status="fictional_readonly", validate_summary=lambda _: None)
        actual = capture.call_args.args[0]
        self.assertEqual(actual[3], str(view.restored / v3.STATIC_LAYOUT["per_entry_io_preparation"] / "verify_restored_at_locations.py"))
        self.assertEqual(actual[actual.index("--location-plan") + 1], view.wiring["location_plan"]["path"])
        self.assertNotIn("run_selected_at_locations.py", actual[3])
        self.assertEqual(capture.call_args.kwargs["producer"]["mode"], "remote_read_only")
        with self.assertRaises(ValueError):
            view.capture_process([*argv, "--execute"], prefix, self.core.Pins(), entrypoint=old, status="never", validate_summary=lambda _: None)

    def test_receiver_keeps_mixed_and_reporting_commands_unchanged(self):
        view = self.receiver_view()
        kwargs = {"entrypoint": self.source, "status": "fictional_mixed", "validate_summary": lambda _: None}
        argv = ["/fictional/python", "-I", "-B", str(self.source)]
        with patch.object(self.core, "capture_process", return_value={"fictional_delegate": True}) as original:
            result = view.capture_process(argv, self.root / "unchanged", self.core.Pins(), **kwargs)
        self.assertEqual(result, {"fictional_delegate": True})
        self.assertEqual(original.call_args.args[0], argv)
        self.assertEqual(original.call_args.kwargs, kwargs)

    def test_python_runtime_thread_guards_remain_original(self):
        with patch.dict(os.environ, {name: "1" for name in self.core.NUMERIC}):
            self.assertTrue(self.core.runtime(Path(sys.executable).absolute()).samefile(Path(sys.executable)))
            with patch.dict(os.environ, {"OMP_NUM_THREADS": "2"}), self.assertRaises(ValueError):
                self.core.runtime(Path(sys.executable).absolute())
        with self.assertRaises(ValueError):
            self.core.runtime(Path("/fictional/not_the_current_python"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
