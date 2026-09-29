"""Fictional metadata/subprocess tests; no scientific or original main execution."""

from __future__ import annotations

import contextlib
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

HERE = Path(__file__).absolute().parent


def load(name: str, path: Path) -> Any:
    specification = importlib.util.spec_from_file_location(name, path)
    assert specification is not None and specification.loader is not None
    module = importlib.util.module_from_spec(specification)
    sys.modules[name] = module
    specification.loader.exec_module(module)
    return module


g = load("_fictional_guard_core", HERE / "guard_fit_dispatch.py")
c = load("_fictional_guard_capture", HERE / "capture_guarded_dispatch.py")


class Fixture:
    """Two invented jobs; immutable documents explicitly marked test_only."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.inputs, self.code, self.fit, self.repro = (root / name for name in ("inputs", "code", "fit", "reproduction"))
        for path in (self.inputs, self.code, self.fit, self.repro):
            path.mkdir()
        source = json.loads((HERE / "source_bindings.json").read_text())
        for name in g.SOURCES:
            shutil.copyfile(HERE / name, self.code / name)
        for name, expected in g.FIT_PINS.items():
            origin = Path(source["fit_code"]) / name
            assert g.binding(origin)["sha256"] == expected
            shutil.copyfile(origin, self.fit / name)
        for name, expected in g.REPRODUCTION_PINS.items():
            origin = Path(source["reproduction_code"]) / name
            assert g.binding(origin)["sha256"] == expected
            shutil.copyfile(origin, self.repro / name)
        self.common = load(f"_fictional_common_{uuid.uuid4().hex}", self.fit / "fit_common.py")
        assert "fit_common" not in sys.modules
        sys.modules["fit_common"] = self.common
        try:
            self.controller = load(f"_fictional_controller_{uuid.uuid4().hex}", self.fit / "fit_controller.py")
        finally:
            sys.modules.pop("fit_common", None)
        self.output = root / "corrected"
        self.python = str(Path(sys.executable).resolve(strict=True))
        self.source, self.original, self.arithmetic = (self.inputs / name for name in ("source", "original", "arithmetic"))
        for path in (self.source, self.original, self.arithmetic):
            path.mkdir()
        self.source_map = {name: g.binding(self.code / name)["sha256"] for name in g.SOURCES}
        self.preparation = self.put(self.code / "preparation_receipt.json", {
            "status": "guarded_dispatch_preparation_sealed", "test_only": True,
            "runtime_source_sha256": self.source_map,
            "artifact_directories": [],
            "artifacts": {name: g.binding(self.code / name) for name in g.SOURCES}})
        self.definition, self.inventory_sha = g.digest("fictional_definition"), g.digest("fictional_inventory")
        self.entries = [{"original_cell_id": identity, "model": "catalytic_fixed", "input_witness_path": f"cells/{identity}/input_witness.json",
                         "input_witness_sha256": g.digest({"fictional_witness": identity})} for identity in ("a", "b")]
        self.implementation = self.put(self.inputs / "implementation.json", self.review({
            "status": "reviewed_for_corrected_fit_execution", "role": "implementation",
            "definition_content_sha256": self.definition, "input_inventory_sha256": self.inventory_sha,
            "execution_definition_sha256": g.digest("fictional_execution"),
            "dispatch_guard_implementation": {"source_sha256": self.source_map, "preparation": self.preparation}}))
        self.freeze_value = {"status": "reviewed_corrected_fit_freeze", "test_only": True,
                             "definition_content_sha256": self.definition, "input_inventory_sha256": self.inventory_sha,
                             "review_bindings": {"implementation": self.implementation},
                             "paths": {"source": str(self.source), "original_run": str(self.original)},
                             "arithmetic_accounting": {"path": str(self.arithmetic / "fixture_accounting.json")}}
        self.freeze = self.put(self.inputs / "freeze.json", self.freeze_value)
        self.manifest_value = {"status": "corrected_fit_manifest_frozen", "test_only": True,
                               "definition_content_sha256": self.definition, "input_inventory_sha256": self.inventory_sha,
                               "pilot_cells": ["b"], "freeze_sha256": self.freeze["sha256"]}
        self.manifest = self.put(self.inputs / "manifest.json", self.manifest_value)
        self.scope = self.put(self.inputs / "scope.json", self.review({
            "status": "reproduction_scope_frozen_before_corrected_score", "frozen_before_any_corrected_score": True,
            "corrected_manifest_sha256": self.manifest["sha256"], "scope_definition_sha256": g.digest("fictional_scope")}))
        self.selection_value = {"status": "reviewed_corrected_reproduction_selection", "test_only": True,
                                "paths": {"freeze": self.freeze["path"], "manifest": self.manifest["path"],
                                          "fit_code": str(self.fit), "corrected_run": str(self.output), "scope_review": self.scope["path"]},
                                "scope_review_sha256": self.scope["sha256"], "correction_freeze_sha256": self.freeze["sha256"],
                                "corrected_manifest_sha256": self.manifest["sha256"],
                                "definition_content_sha256": self.definition, "input_inventory_sha256": self.inventory_sha}
        self.selection = self.put(self.inputs / "selection.json", self.selection_value)
        self.request_path, self.request = self.make_request()
        self.args = self.arguments()
        self.controller.prepare_output(self.output, Path(self.manifest["path"]), self.manifest["sha256"], [self.fit, self.inputs])
        self.account("a")
        self.controller_calls = 0

    def review(self, fields: dict[str, Any]) -> dict[str, Any]:
        return {"test_only": True, "reviewer_name": "FICTIONAL_TEST_ROOT", "reviewer_role": "root",
                "reviewed_at_utc": (datetime.now(UTC) - timedelta(days=1)).isoformat(), **fields}

    def put(self, path: Path, value: dict[str, Any]) -> dict[str, str]:
        if value.get("phase") == "account":
            records = value["record_sha256"]
            value = {"schema_version": 1, "status": "all_logical_outcomes_accounted" if set(records) == {entry["original_cell_id"] for entry in self.entries} else "partial_selective_fit_accounting",
                     "scheduled_logical_cells": 1625, "retained_logical_outcomes": len(records),
                     "all_fits_numerically_verified": False, "programme_complete": False, "reporting_certified": False,
                     "release_certified": False, "pending_gates": ["mixed_lineage_deep_verification", "analysis_reporting_qa", "selected_reproduction", "package_restore_replay"], **value}
        self.common.write_new(path, self.common.seal(value))
        return {"path": str(path), "sha256": g.binding(path)["sha256"]}

    def make_request(self, *, phase: str = "pilot", pilot: dict[str, str] | None = None) -> tuple[Path, dict[str, Any]]:
        value = {"schema_version": 1, "status": "guarded_corrected_fit_dispatch_request", "test_only": True,
                 "guard_code": str(self.code), "guard_source_sha256": self.source_map, "guard_preparation": self.preparation,
                 "implementation_review": self.implementation, "scope_review": self.scope, "selection": self.selection,
                 "freeze": self.freeze, "manifest": self.manifest, "fit_code": str(self.fit), "reproduction_code": str(self.repro),
                 "corrected_run": str(self.output), "locked_python": self.python, "phase": phase, "limit": None,
                 "pilot_review": pilot, "resolution_review": None}
        value["request_body_sha256"] = g.request_definition(value)
        adoption = self.put(self.inputs / f"adoption_{uuid.uuid4().hex}.json", self.review({
            "status": "guard_dispatch_request_reviewed", "request_body_sha256": value["request_body_sha256"]}))
        value["adoption"] = adoption
        path = self.inputs / f"request_{uuid.uuid4().hex}.json"
        self.put(path, value)
        return path, g.document(path)

    def arguments(self) -> Any:
        return g.parser().parse_args(g.guard_cli_args(self.request_path, g.binding(self.request_path)["sha256"], self.request))

    def gates(self) -> dict[str, Any]:
        return {"selection": self.selection_value, "freeze": self.freeze_value, "manifest": self.manifest_value,
                "inventory": {"entries": self.entries}, "controller": self.controller, "common": self.common}

    @contextlib.contextmanager
    def factory(self, _request: dict[str, Any], _resolve: Any = g.safe, *, read_only: bool = False):
        yield self.gates()

    def account(self, identity: str) -> None:
        """Exact original terminal-account envelope through original seal/write helpers."""
        entry = next(row for row in self.entries if row["original_cell_id"] == identity)
        decision = {"schema_version": 1, "scope": "supplied_evidence_contract_not_actual_byte_verification", "original_cell_id": identity,
                    "model": entry["model"], "correction_specification_sha256": self.definition, "action": "retain_input_failure",
                    "missing_roles": [], "changed_roles": [], "generator_failures": {"outer": "input_failure"},
                    "witness_sha256": g.digest({"FICTIONAL_witness": identity}), "tuning_record_reused_sha256": None,
                    "original_status": None, "original_outcome_available": False, "source_evidence": None,
                    "seed_ledger_sha256": g.digest({"cell_seed": 17}), "fit_dispatched": False}
        decision["decision_content_sha256"] = g.digest(decision)
        value = {"schema_version": 1, "test_only": True, "original_cell_id": identity,
                 "evidence_status": "post_hoc_rank_conditioned_correction_after_original_failures_known",
                 "corrected_manifest_sha256": self.manifest["sha256"], "correction_freeze_sha256": self.freeze["sha256"],
                 "definition_content_sha256": self.definition, "input_witness_path": entry["input_witness_path"],
                 "input_witness_sha256": entry["input_witness_sha256"], "source_evidence": None,
                 "decision": decision,
                 "generator_contexts": {"outer": ["input_failure", g.digest("fictional_context")]},
                 "original_seed_namespace": {"cell_seed": 17}, "fit_dispatched": False, "artifacts": {},
                 "programme_complete": False, "reporting_certified": False, "release_certified": False,
                 "operation": "retain_corrected_input_failure", "scientific_status": "not_fit_input_failure",
                 "original_reference": None, "original_outcome_pending": True, "failure_contexts": {"outer": "input_failure"},
                 "newly_executed_fit": False, "fit_seconds": 0.0}
        self.put(self.output / "cells" / f"{identity}.json", value)

    def controller_invoke(self, argv: list[str], *, stdout: Any, stderr: Any, **_kwargs: Any) -> Any:
        """Invented subprocess side effects; never call an original main/model."""
        self.controller_calls += 1
        self.test_before_spawn = g.document(self.output / g.NAMESPACE / "introduction.json")
        identity = "b"
        attempt = self.output / "attempts" / identity
        dispatched = False
        if not attempt.exists() and not (self.output / "cells" / "b.json").exists():
            dispatched = True
            attempt.mkdir()
            self.put(attempt / "request.json", {"schema_version": 1, "test_only": True, "original_cell_id": identity,
                "entry": self.entries[1], "source_evidence": {"fictional": True}, "action": "fit_changed_inputs",
                "freeze_path": self.freeze["path"], "freeze_sha256": self.freeze["sha256"],
                "manifest_path": self.manifest["path"], "manifest_sha256": self.manifest["sha256"],
                "attempt_path": str(attempt), "locked_python": self.python, "implementation_source_sha256": g.FIT_PINS})
            (attempt / "retained_failure.fake").write_bytes(b"FICTIONAL failure bytes; no numerical array")
            self.put(self.output / "cells" / "b.json", {"schema_version": 1, "test_only": True, "original_cell_id": identity,
                "corrected_manifest_sha256": self.manifest["sha256"], "operation": "fit_corrected_inputs", "artifacts": {},
                "fit_dispatched": True, "newly_executed_fit": True, "programme_complete": False})
        records = {path.stem: g.binding(path)["sha256"] for path in (self.output / "cells").glob("*.json")}
        phase = argv[argv.index("--phase") + 1]
        self.put(self.output / "passes" / f"{uuid.uuid4().hex}.json", {"schema_version": 1, "test_only": True,
            "phase": phase, "corrected_manifest_sha256": self.manifest["sha256"], "status": "partial_selective_fit_accounting",
            "scheduled_logical_cells": 1625, "retained_logical_outcomes": len(records),
            "current_pass": [{"original_cell_id": "b", "fit_dispatched": True}] if dispatched else
                            [{"original_cell_id": "b", "status": "verified_existing_outcome", "record_sha256": records["b"]}],
            "record_sha256": records, "programme_complete": False})
        stdout.write(b'{"status":"partial_selective_fit_accounting","programme_complete":false}\n')
        stderr.write(b"fictional diagnostic preserved\n")
        return SimpleNamespace(returncode=0)

    def guard_invoke(self, argv: list[str], *, stdout: Any, stderr: Any, **_kwargs: Any) -> Any:
        args = g.parser(gate=True).parse_args(argv[4:])
        try:
            result = g.dispatch(args, self.gates(), invoke=self.controller_invoke, testing=True)
            stdout.write(b'{"status":"fictional_guard_return"}\n')
            return SimpleNamespace(returncode=0 if result["controller_returncode"] == 0 else 1)
        except Exception as exception:
            stderr.write(f"FICTIONAL caught child exception: {exception}\n".encode())
            return SimpleNamespace(returncode=1)

    def launch(self) -> dict[str, Any]:
        return c.launch(g, self.args, self.gates(), invoke=self.guard_invoke, gates_factory=self.factory, testing=True)

    def locations(self, control: Path, *, restored: Path | None = None) -> tuple[Path, str]:
        roots = []
        for source in (self.code, self.fit, self.repro, self.inputs, self.output):
            destination = source if restored is None else restored / source.name
            if restored is not None:
                shutil.copytree(source, destination)
            roots.append({"historical": str(source), "restored": str(destination), "payload_role": "corrected_payload" if restored else None,
                          "inventory": g.tree(destination)})
        transport = control / "transport.json"
        self.put(transport, self.review({"status": "FICTIONAL_actual_source_transport_evidence"}))
        immutable_files = []
        source_proof = None
        if restored is not None:
            proof_source = self.root / "source_verification/receipt.json"
            proof_destination = restored / "source_guard_proof.json"
            shutil.copyfile(proof_source, proof_destination)
            immutable_files.append({"historical": str(proof_source), "restored": str(proof_destination),
                                    "payload_role": "corrected_payload", "binding": g.binding(proof_destination)})
            source_proof = {"path": str(proof_source), "sha256": g.binding(proof_source)["sha256"]}
        value = {"schema_version": 1, "status": "guard_proof_locations_proposed", "request_sha256": g.binding(self.request_path)["sha256"],
                 "mode": "receiving" if restored else "source", "fresh_payload_roles": {"corrected_payload": str(restored)} if restored else {},
                 "source_guard_proof": source_proof, "immutable_roots": roots, "immutable_files": immutable_files,
                 "transport_evidence": [{"path": str(transport), "binding": g.binding(transport), "role": role}
                                        for role in (("actual_stage", "actual_restore") if restored else ("actual_source_review",))]}
        authority = self.put(control / "locations_review.json", self.review({"status": "guard_proof_locations_reviewed",
            "locations_definition_sha256": g.digest(value), "request_sha256": value["request_sha256"],
            "verification_mode": value["mode"], "fresh_payload_roles": value["fresh_payload_roles"]}))
        value["authority"] = authority
        path = control / "locations.json"
        self.put(path, value)
        return path, authority["sha256"]


class GuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.saved_modules = set(sys.modules)
        self.directory = tempfile.TemporaryDirectory(prefix="guard-fictional-")
        self.root = Path(self.directory.name).resolve(strict=True)
        self.fixture = Fixture(self.root)

    def tearDown(self) -> None:
        self.directory.cleanup()
        for name in set(sys.modules) - self.saved_modules:
            if name.startswith(("_fictional_common_", "_fictional_controller_")):
                sys.modules.pop(name, None)
        self.assertNotIn("fit_common", sys.modules)
        self.assertNotIn("src", sys.modules)

    def rewrite(self, path: Path, value: dict[str, Any]) -> None:
        """Deliberately corrupt only a disposable fictional fixture."""
        value = {key: item for key, item in value.items() if key != "content_sha256"}
        path.write_text(json.dumps(g.sealed(value), sort_keys=True, indent=2) + "\n")

    def test_original_helpers_accept_exact_no_fit_account_and_existing_pass(self) -> None:
        f = self.fixture
        cell = f.output / "cells/a.json"
        actual = f.controller.verify_record(cell, f.manifest["sha256"], "a")
        self.assertIs(actual["newly_executed_fit"], False)
        f.put(f.output / "passes" / "account.json", {"phase": "account", "corrected_manifest_sha256": f.manifest["sha256"],
            "current_pass": [{"original_cell_id": "a", "status": "verified_existing_outcome", "record_sha256": g.binding(cell)["sha256"]}],
            "record_sha256": {"a": g.binding(cell)["sha256"]}})
        g.account_only(f.output, f.request, f.gates())

    def test_narrow_old_helper_cannot_hide_bad_freeze_definition_witness_or_flags(self) -> None:
        f = self.fixture
        path = f.output / "cells/a.json"
        original = g.document(path)
        for key, value in (("correction_freeze_sha256", "0" * 64), ("definition_content_sha256", "0" * 64),
                           ("input_witness_sha256", "0" * 64), ("input_witness_path", "other"),
                           ("newly_executed_fit", True), ("fit_dispatched", True)):
            with self.subTest(key=key):
                self.rewrite(path, {**original, key: value})
                f.controller.verify_record(path, f.manifest["sha256"], "a")
                with self.assertRaises(g.InvalidProof):
                    g.account_only(f.output, f.request, f.gates())
        self.rewrite(path, original)

    def test_prior_fit_rejected_even_latest_pass_account(self) -> None:
        f = self.fixture
        path = f.output / "cells/a.json"
        self.rewrite(path, {**g.document(path), "operation": "fit_corrected_inputs", "fit_dispatched": True})
        f.put(f.output / "passes" / "account.json", {"phase": "account", "corrected_manifest_sha256": f.manifest["sha256"],
            "current_pass": [], "record_sha256": {"a": g.binding(path)["sha256"]}})
        before = g.tree(f.output)
        with self.assertRaises(g.InvalidProof):
            f.launch()
        self.assertEqual(before, g.tree(f.output))
        self.assertEqual(f.controller_calls, 0)

    def test_empty_orphan_attempt_and_claim_directory_refuse_without_cleanup(self) -> None:
        f = self.fixture
        for namespace in ("attempts", "claims"):
            with self.subTest(namespace=namespace):
                orphan = f.output / namespace / "empty"
                orphan.mkdir()
                before = g.tree(f.output)
                with self.assertRaises(g.InvalidProof):
                    f.launch()
                self.assertEqual(before, g.tree(f.output))
                orphan.rmdir()

    def test_all_actual_arguments_match_including_optional_reviews_and_limit(self) -> None:
        f = self.fixture
        for key, value in (("phase", "remaining"), ("limit", 1), ("freeze_sha256", "0" * 64),
                           ("selection", f.root / "other"), ("output", f.root / "other"),
                           ("pilot_review", f.inputs / "unexpected.json")):
            with self.subTest(key=key):
                changed = SimpleNamespace(**vars(f.args))
                setattr(changed, key, value)
                with self.assertRaises(g.InvalidProof):
                    g.match_arguments(changed, f.request)

    def test_named_review_and_pre_freeze_guard_binding_required(self) -> None:
        f = self.fixture
        path = Path(f.implementation["path"])
        value = g.document(path)
        self.rewrite(path, {**value, "reviewer_name": ""})
        f.request["implementation_review"] = {"path": str(path), "sha256": g.binding(path)["sha256"]}
        f.freeze_value["review_bindings"]["implementation"] = f.request["implementation_review"]
        with self.assertRaises(g.InvalidProof):
            g.validate_authority(f.request, f.gates(), testing=True)

    def test_synthetic_request_cannot_authorize_production(self) -> None:
        with self.assertRaises(g.InvalidProof):
            g.validate_request(self.fixture.request)

    def test_future_dated_named_review_refused(self) -> None:
        value = self.fixture.review({"status": "FICTIONAL review"})
        value["reviewed_at_utc"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        with self.assertRaises(g.InvalidProof):
            g.named_root_review(value, testing=True)

    def test_preparation_rejects_unlisted_file_and_empty_directory(self) -> None:
        f = self.fixture
        for name, directory in (("unlisted.txt", False), ("empty_extra", True)):
            path = f.code / name
            if directory:
                path.mkdir()
            else:
                path.write_text("FICTIONAL unrelated bytes")
            before = g.tree(f.output)
            with self.assertRaises(g.InvalidProof):
                f.launch()
            self.assertEqual(before, g.tree(f.output))
            path.rmdir() if directory else path.unlink()

    def test_change_after_owned_launcher_preflight_refuses_controller(self) -> None:
        f = self.fixture
        f.launch()
        f.controller_calls = 0
        def changed_guard(argv: list[str], **kwargs: Any) -> Any:
            orphan = f.output / "attempts/unowned_empty"
            orphan.mkdir()
            try:
                return f.guard_invoke(argv, **kwargs)
            finally:
                self.assertTrue(orphan.exists())
        result = c.launch(g, f.args, f.gates(), invoke=changed_guard, gates_factory=f.factory, testing=True)
        self.assertEqual(result["guard_returncode"], 1)
        self.assertEqual(f.controller_calls, 0)
        self.assertTrue((f.output / "attempts/unowned_empty").is_dir())
        with self.assertRaises((g.InvalidProof, FileNotFoundError)):
            g.history(f.output, f.request, gates_factory=f.factory, testing=True)

    def test_guard_preparation_reproduction_ancestry_overlap_before_any_write(self) -> None:
        f = self.fixture
        for target in (f.code / "never_create", f.repro / "never_create", f.code.parent):
            with self.subTest(target=target):
                candidate = {key: value for key, value in f.request.items() if key != "content_sha256"}
                candidate["corrected_run"] = str(target)
                candidate["request_body_sha256"] = g.request_definition(candidate)
                candidate["adoption"] = f.put(f.inputs / f"overlap_review_{uuid.uuid4().hex}.json", f.review({
                    "status": "guard_dispatch_request_reviewed", "request_body_sha256": candidate["request_body_sha256"]}))
                before_code, before_repro = g.tree(f.code), g.tree(f.repro)
                with self.assertRaises(g.InvalidProof):
                    g.validate_request(candidate, testing=True)
                self.assertEqual(g.tree(f.code), before_code)
                self.assertEqual(g.tree(f.repro), before_repro)
                if target.name == "never_create":
                    self.assertFalse(target.exists())

    def test_exclusive_publication_and_noninteger_or_unavailable_return(self) -> None:
        f = self.fixture
        destination = f.root / "exclusive.json"
        g.write_new(destination, {"value": 1})
        with self.assertRaises(g.InvalidProof):
            g.write_new(destination, {"value": 2})
        for outcome in (True, None):
            folder = f.root / f"capture_{outcome}"
            folder.mkdir()
            result = g.capture(["fictional"], folder, "test", f.root, dict(os.environ),
                               invoke=lambda *_a, _outcome=outcome, **_kw: SimpleNamespace(returncode=_outcome), testing=True)
            self.assertIsNone(result["returncode"])
            self.assertEqual(result["status"], "subprocess_result_unavailable")
            self.assertTrue((folder / "test.stdout.log").is_file())

    def test_genuine_two_mocked_captures_introduction_before_controller(self) -> None:
        f = self.fixture
        result = f.launch()
        self.assertEqual(result["guard_returncode"], 0)
        self.assertEqual(f.controller_calls, 1)
        self.assertEqual(f.test_before_spawn["status"], "guard_introduced_before_controller_launch")
        proved = g.history(f.output, f.request, gates_factory=f.factory, testing=True)
        self.assertEqual(proved["owned_attempt_ids"], ["b"])
        self.assertEqual(proved["invocations"], 1)
        self.assertFalse((f.output / g.NAMESPACE / "guard.claim.json").exists())

    def test_remaining_uses_exact_original_pilot_predicate_and_resume_history(self) -> None:
        f = self.fixture
        f.launch()
        pilot = f.put(f.inputs / "pilot_review.json", f.review({"status": "full_budget_pilot_reviewed",
            "corrected_manifest_sha256": f.manifest["sha256"], "approve_remaining_selective_fits": True,
            "original_full_budget_retained": True, "all_failures_retained_and_reviewed": True,
            "pilot_outcomes": {"b": g.binding(f.output / "cells/b.json")}}))
        f.request_path, f.request = f.make_request(phase="remaining", pilot=pilot)
        f.args = f.arguments()
        result = f.launch()
        self.assertEqual(result["guard_returncode"], 0)
        proved = g.history(f.output, f.request, gates_factory=f.factory, testing=True)
        self.assertEqual(proved["invocations"], 2)
        self.assertEqual(proved["owned_attempt_ids"], ["b"])

    def test_missing_or_false_pilot_binding_refuses_remaining(self) -> None:
        f = self.fixture
        f.launch()
        bad = f.put(f.inputs / "bad_pilot.json", f.review({"status": "full_budget_pilot_reviewed",
            "corrected_manifest_sha256": f.manifest["sha256"], "approve_remaining_selective_fits": True,
            "original_full_budget_retained": True, "all_failures_retained_and_reviewed": True, "pilot_outcomes": {}}))
        _, request = f.make_request(phase="remaining", pilot=bad)
        with self.assertRaises(ValueError):
            g.validate_authority(request, f.gates(), testing=True)

    def test_changed_resume_bytes_extra_attempt_and_history_gap_block(self) -> None:
        f = self.fixture
        f.launch()
        for change in ("changed_cell", "empty_orphan", "empty_guard_dir"):
            with self.subTest(change=change):
                if change == "changed_cell":
                    node = f.output / "cells/a.json"
                    saved = node.read_bytes()
                    node.write_bytes(saved + b" ")
                else:
                    node = f.output / ("attempts/orphan" if change == "empty_orphan" else str(g.NAMESPACE / "extra"))
                    node.mkdir()
                with self.assertRaises(g.InvalidProof):
                    g.history(f.output, f.request, gates_factory=f.factory, testing=True)
                if change == "changed_cell":
                    node.write_bytes(saved)
                else:
                    node.rmdir()

    def test_nonzero_controller_retains_raw_and_failed_bytes_without_success(self) -> None:
        f = self.fixture
        original = f.controller_invoke
        def fail(*args: Any, **kwargs: Any) -> Any:
            original(*args, **kwargs)
            return SimpleNamespace(returncode=7)
        f.controller_invoke = fail
        result = f.launch()
        self.assertEqual(result["guard_returncode"], 1)
        proved = g.history(f.output, f.request, gates_factory=f.factory, testing=True)
        self.assertEqual(proved["failed_closed_invocations"], 1)
        self.assertFalse(proved["successful_guard_coverage"])
        self.assertTrue((f.output / "attempts/b/retained_failure.fake").is_file())
        directory = next((f.output / g.NAMESPACE / "invocations").iterdir())
        self.assertEqual(g.document(directory / "controller_invocation.json")["returncode"], 7)
        self.assertIn(b"fictional diagnostic", (directory / "controller.stderr.log").read_bytes())

    def test_partial_parent_capture_is_preserved_and_not_promoted(self) -> None:
        f = self.fixture
        def interruption(*_args: Any, **_kwargs: Any) -> Any:
            raise KeyboardInterrupt("FICTIONAL interruption")
        result = c.launch(g, f.args, f.gates(), invoke=interruption, gates_factory=f.factory, testing=True)
        self.assertIsNone(result["guard_returncode"])
        with self.assertRaises((g.InvalidProof, FileNotFoundError)):
            g.history(f.output, f.request, gates_factory=f.factory, testing=True)
        self.assertTrue(any((f.output / g.NAMESPACE / "invocations").glob("*/guard_invocation.json")))
        with self.assertRaises(g.InvalidProof):
            f.launch()

    def test_source_and_restored_readonly_semantics_and_external_output(self) -> None:
        f = self.fixture
        f.launch()
        control = f.root / "control"
        control.mkdir()
        path, review_sha = f.locations(control)
        before = g.tree(f.output)
        output = f.root / "source_verification"
        result = g.verify_guarded_dispatch_proof(f.request_path, g.binding(f.request_path)["sha256"], path,
            g.binding(path)["sha256"], review_sha, output, gates_factory=f.factory, testing=True)
        self.assertEqual(result["status"], "retained_guard_proof_semantically_verified")
        self.assertFalse(result["scientific_completion_certified"])
        self.assertEqual(before, g.tree(f.output))
        restored, second_control = f.root / "restored", f.root / "second_control"
        restored.mkdir()
        second_control.mkdir()
        second, second_review = f.locations(second_control, restored=restored)
        restored_request = restored / "inputs" / f.request_path.name
        restored_before = g.tree(restored)
        replay = g.verify_guarded_dispatch_proof(restored_request, g.binding(restored_request)["sha256"], second,
            g.binding(second)["sha256"], second_review, f.root / "receiving_verification", gates_factory=f.factory, testing=True)
        self.assertEqual(replay["history"]["owned_attempt_ids"], ["b"])
        self.assertEqual(restored_before, g.tree(restored))

    def test_location_authority_empty_dirs_extra_bytes_and_aliases_refused(self) -> None:
        f = self.fixture
        f.launch()
        control = f.root / "control"
        control.mkdir()
        path, review_sha = f.locations(control)
        expected = g.binding(path)["sha256"]
        with self.assertRaises(g.InvalidProof):
            g.TrustedLocations(path, expected, "0" * 64, g.binding(f.request_path)["sha256"], testing=True)
        resolver = g.TrustedLocations(path, expected, review_sha, g.binding(f.request_path)["sha256"], testing=True)
        (f.output / "attempts/empty_extra").mkdir()
        with self.assertRaises(g.InvalidProof):
            resolver.verify()
        (f.output / "attempts/empty_extra").rmdir()
        (f.output / "extra.fake").write_bytes(b"extra")
        with self.assertRaises(g.InvalidProof):
            resolver.verify()

    def test_receiving_identity_missing_relocation_and_wrong_role_refused(self) -> None:
        f = self.fixture
        f.launch()
        source_control = f.root / "source_control"
        source_control.mkdir()
        source_map, source_review = f.locations(source_control)
        g.verify_guarded_dispatch_proof(f.request_path, g.binding(f.request_path)["sha256"], source_map,
            g.binding(source_map)["sha256"], source_review, f.root / "source_verification", gates_factory=f.factory, testing=True)
        control, restored = f.root / "receiving_control", f.root / "fresh"
        control.mkdir()
        restored.mkdir()
        path, review_sha = f.locations(control, restored=restored)
        value = g.document(path)
        for mutation in ("identity", "missing_code", "wrong_role"):
            with self.subTest(mutation=mutation):
                candidate = json.loads(json.dumps(value))
                candidate.pop("content_sha256")
                if mutation == "identity":
                    candidate["immutable_roots"][0]["restored"] = candidate["immutable_roots"][0]["historical"]
                elif mutation == "missing_code":
                    candidate["immutable_roots"].pop(0)
                else:
                    candidate["immutable_roots"][0]["payload_role"] = "wrong"
                body = {key: item for key, item in candidate.items() if key != "authority"}
                authority = f.put(control / f"authority_{mutation}.json", f.review({"status": "guard_proof_locations_reviewed",
                    "locations_definition_sha256": g.digest(body), "request_sha256": candidate["request_sha256"],
                    "verification_mode": "receiving", "fresh_payload_roles": candidate["fresh_payload_roles"]}))
                candidate["authority"] = authority
                altered = control / f"locations_{mutation}.json"
                f.put(altered, candidate)
                before = g.tree(restored)
                with self.assertRaises(g.InvalidProof):
                    g.verify_guarded_dispatch_proof(restored / "inputs" / f.request_path.name,
                        g.binding(f.request_path)["sha256"], altered, g.binding(altered)["sha256"], authority["sha256"],
                        f.root / f"bad_replay_{mutation}", gates_factory=f.factory, testing=True)
                self.assertEqual(g.tree(restored), before)
                self.assertFalse((f.root / f"bad_replay_{mutation}").exists())

    def test_source_symlink_traversal_occupied_alias_and_numeric_env_refused(self) -> None:
        f = self.fixture
        link = f.root / "linked"
        link.symlink_to(f.inputs, target_is_directory=True)
        for path in (link / "freeze.json", f.root / ".." / "anything"):
            with self.subTest(path=path), self.assertRaises(g.InvalidProof):
                g.safe(path)
        sys.modules["fit_common"] = object()
        try:
            with self.assertRaises(g.InvalidProof), g.original_gates(f.request):
                pass
        finally:
            sys.modules.pop("fit_common", None)
        previous = os.environ[g.THREADS[0]]
        os.environ[g.THREADS[0]] = "2"
        try:
            with self.assertRaises(g.InvalidProof):
                g.runtime(Path(sys.executable))
        finally:
            os.environ[g.THREADS[0]] = previous

    def test_actual_pinned_stdlib_bootstrap_refuses_fixture_and_restores_aliases(self) -> None:
        """Call only the old metadata predicate on a deliberately incomplete fixture."""
        before = {name for name in sys.modules if name == "src" or name.startswith("src.")}
        with self.assertRaises(KeyError), g.original_gates(self.fixture.request):
            self.fail("fictional selection must not pass the original production predicate")
        for name in ("_reproduction_bound_common", "_guard_old_reproduction", "_guard_old_controller", "fit_common"):
            self.assertNotIn(name, sys.modules)
        self.assertEqual(before, {name for name in sys.modules if name == "src" or name.startswith("src.")})


if __name__ == "__main__":
    unittest.main(verbosity=2)
