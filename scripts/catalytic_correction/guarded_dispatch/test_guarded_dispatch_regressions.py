"""V2 counterexample regressions with invented metadata and no target execution."""

from __future__ import annotations

import shutil
import unittest
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import test_guarded_dispatch as fixture

g, c = fixture.g, fixture.c


class GuardV2Regressions(unittest.TestCase):
    """Borrow fixture lifecycle only; the original 23 methods are collected once."""

    setUp = fixture.GuardTests.setUp
    tearDown = fixture.GuardTests.tearDown
    rewrite = fixture.GuardTests.rewrite

    def expand_roles(self) -> None:
        """Declare the complete old immutable surface in a disposable fixture."""
        f = self.fixture
        original_reproduction = f.inputs / "original_reproduction"
        original_reproduction.mkdir()
        witness, preflight = f.inputs / "witness", f.inputs / "preflight"
        witness.mkdir()
        preflight.mkdir()
        f.freeze_value["paths"].update({"witness_root": str(witness), "preflight": str(preflight)})
        for role in g.FREEZE_FILE_ROLES:
            path = f.inputs / f"{role}.json"
            f.put(path, {"status": "FICTIONAL immutable file", "role": role, "test_only": True})
            f.freeze_value["paths"][role] = str(path)
        f.selection_value["paths"]["original_reproduction"] = str(original_reproduction)
        for role in ("recipe_inventory", "original_numerical_evidence"):
            path = f.inputs / f"{role}.json"
            f.put(path, {"status": "FICTIONAL selection-only input", "role": role, "test_only": True})
            f.selection_value["paths"][role] = str(path)
        self.rebind_inputs()

    def rebind_inputs(self) -> None:
        """Seal a fresh fictional chain before any tested guard invocation."""
        f = self.fixture
        f.freeze = f.put(f.inputs / f"freeze_{uuid.uuid4().hex}.json", f.freeze_value)
        f.manifest_value["freeze_sha256"] = f.freeze["sha256"]
        f.manifest = f.put(f.inputs / f"manifest_{uuid.uuid4().hex}.json", f.manifest_value)
        scope = {key: value for key, value in g.document(Path(f.scope["path"])).items() if key != "content_sha256"}
        scope["corrected_manifest_sha256"] = f.manifest["sha256"]
        f.scope = f.put(f.inputs / f"scope_{uuid.uuid4().hex}.json", scope)
        f.selection_value["paths"].update({"freeze": f.freeze["path"], "manifest": f.manifest["path"],
                                            "corrected_run": str(f.output), "scope_review": f.scope["path"]})
        f.selection_value.update(correction_freeze_sha256=f.freeze["sha256"], corrected_manifest_sha256=f.manifest["sha256"],
                                 scope_review_sha256=f.scope["sha256"])
        f.selection = f.put(f.inputs / f"selection_{uuid.uuid4().hex}.json", f.selection_value)
        f.request_path, f.request = f.make_request()
        f.args = f.arguments()
        shutil.rmtree(f.output)
        f.controller.prepare_output(f.output, Path(f.manifest["path"]), f.manifest["sha256"], [f.fit, f.inputs])
        f.account("a")

    def pass_record(self, rows: list[dict[str, Any]], records: dict[str, str], name: str | None = None) -> Path:
        """Use fixture-only builder to fill exactly the original pass metadata."""
        f = self.fixture
        path = f.output / "passes" / f"{name or uuid.uuid4().hex}.json"
        f.put(path, {"phase": "account", "corrected_manifest_sha256": f.manifest["sha256"],
                     "current_pass": rows, "record_sha256": records})
        return path

    def checked(self, identity: str) -> str:
        return g.binding(self.fixture.output / "cells" / f"{identity}.json")["sha256"]

    def existing(self, identity: str) -> dict[str, Any]:
        return {"original_cell_id": identity, "status": "verified_existing_outcome", "record_sha256": self.checked(identity)}

    def retained(self, identity: str) -> dict[str, Any]:
        value = g.document(self.fixture.output / "cells" / f"{identity}.json")
        return {"original_cell_id": identity, "status": "outcome_retained", "operation": value["operation"],
                "scientific_status": value["scientific_status"], "record_sha256": self.checked(identity), "fit_dispatched": False}

    def make_reuse(self, status: str) -> None:
        """Invent a byte-bound original outcome reference, including negative ones."""
        f = self.fixture
        path = f.output / "cells/a.json"
        value = g.document(path)
        for name in ("content_sha256", "original_outcome_pending", "failure_contexts"):
            value.pop(name, None)
        source = {"original_cell_id": "a", "original_manifest_sha256": f.common.ORIGINAL_MANIFEST_SHA,
                  "cell_byte_sha256": g.digest(["FICTIONAL original", status]), "cell_content_sha256": g.digest(["FICTIONAL content", status]),
                  "status": status, "verification_receipt_sha256": g.digest("FICTIONAL proof"),
                  "referenced_trace_sha256": {}, "unreferenced_trace_sha256": {}, "wme_tuning_record_sha256": None}
        value.update(operation="reuse_original_outcome", scientific_status=status, source_evidence=source,
                     original_reference={"logical_root": "original_extension_run", "path": "cells/a.json",
                                         "sha256": source["cell_byte_sha256"], "cell_content_sha256": source["cell_content_sha256"]},
                     generator_contexts={"outer": ["accepted", g.digest("FICTIONAL accepted context")]})
        decision = {key: item for key, item in value["decision"].items() if key != "decision_content_sha256"}
        decision.update(action="reuse_original_outcome", generator_failures={}, source_evidence=source,
                        original_status=status, original_outcome_available=True)
        decision["decision_content_sha256"] = g.digest(decision)
        value["decision"] = decision
        self.rewrite(path, value)

    def test_selection_only_original_reproduction_descendant_refused_before_first_write(self) -> None:
        self.expand_roles()
        f = self.fixture
        protected = Path(f.selection_value["paths"]["original_reproduction"])
        candidate = {key: value for key, value in f.request.items() if key != "content_sha256"}
        candidate["corrected_run"] = str(protected / "must_not_create")
        candidate["request_body_sha256"] = g.request_definition(candidate)
        candidate["adoption"] = f.put(f.inputs / "counterexample_adoption.json", f.review({
            "status": "guard_dispatch_request_reviewed", "request_body_sha256": candidate["request_body_sha256"]}))
        request_path = f.inputs / "counterexample_request.json"
        f.put(request_path, candidate)
        args = g.parser().parse_args(g.guard_cli_args(request_path, g.binding(request_path)["sha256"], candidate))
        f.selection_value["paths"]["corrected_run"] = candidate["corrected_run"]
        before = g.tree(protected)
        with self.assertRaises(g.InvalidProof):
            c.launch(g, args, f.gates(), invoke=lambda *_a, **_kw: SimpleNamespace(returncode=19), testing=True)
        self.assertEqual(g.tree(protected), before)
        self.assertFalse(args.output.exists())

    def test_every_declared_immutable_role_and_request_is_protected_both_directions(self) -> None:
        self.expand_roles()
        f = self.fixture
        rows = g.immutable_output_roles(f.request, f.gates(), f.request_path)
        self.assertIn("selection.original_reproduction", {row[0] for row in rows})
        for label, path, _kind in rows:
            for output in (path, path / "new_output", path.parent):
                with self.subTest(role=label, output=output), self.assertRaises(g.InvalidProof):
                    g.protect_output(output, f.request, f.gates(), f.request_path)

    def test_bound_file_siblings_allowed_and_only_corrected_selection_role_exempt(self) -> None:
        self.expand_roles()
        f = self.fixture
        sibling = Path(f.selection_value["paths"]["recipe_inventory"]).with_name("new_sibling_output")
        g.protect_output(sibling, f.request, f.gates(), f.request_path)
        self.assertFalse(sibling.exists())
        g.protect_output(f.output, f.request, f.gates(), f.request_path)
        with self.assertRaises(g.InvalidProof):
            g.protect_output(f.output, f.request, f.gates(), f.request_path, include_corrected_run=True)

    def test_actual_six_corrected_fit_fields_and_unknown_score_field_refused(self) -> None:
        f = self.fixture
        path = f.output / "cells/a.json"
        original = g.document(path)
        fields = {"corrected_cell": {"logical_root": "corrected_fit_run", "path": "outside.fake"},
                  "child_receipt_path": "outside/child_receipt.json", "invocation_path": "outside/invocation.json",
                  "observations_path": "outside/observations.json", "child_wall_seconds": 3.0, "child_exit_code": 0,
                  "corrected_reference": {"path": "outside.fake"}, "unclassified_corrected_score": 0.9}
        for name, value in fields.items():
            with self.subTest(name=name):
                self.rewrite(path, {**original, name: value})
                f.controller.verify_record(path, f.manifest["sha256"], "a")
                with self.assertRaises(g.InvalidProof):
                    g.account_only(f.output, f.request, f.gates())
        self.rewrite(path, {**original, **fields})
        with self.assertRaises(g.InvalidProof):
            g.account_only(f.output, f.request, f.gates())

    def test_legitimate_original_success_and_negative_reuse_kept(self) -> None:
        f = self.fixture
        for status in ("complete", "failed", "failed_diagnostics"):
            with self.subTest(status=status):
                self.make_reuse(status)
                g.account_only(f.output, f.request, f.gates())

    def test_reuse_reference_and_terminal_decision_status_must_match(self) -> None:
        f = self.fixture
        path = f.output / "cells/a.json"
        original = g.document(path)
        for key, value in (("scientific_status", "complete"), ("original_reference", {"path": "bad"}),
                           ("original_outcome_pending", 1), ("failure_contexts", {}), ("fit_seconds", True)):
            with self.subTest(key=key):
                self.rewrite(path, {**original, key: value})
                with self.assertRaises(g.InvalidProof):
                    g.account_only(f.output, f.request, f.gates())
        self.rewrite(path, original)
        self.make_reuse("failed")
        reused = g.document(path)
        self.rewrite(path, {**reused, "original_reference": {**reused["original_reference"], "sha256": "0" * 64}})
        with self.assertRaises(g.InvalidProof):
            g.account_only(f.output, f.request, f.gates())

    def test_foreign_numeric_false_flag_row_and_arbitrary_status_refused(self) -> None:
        f = self.fixture
        bad_rows = [
            {"original_cell_id": "foreign", "status": "outcome_retained", "operation": "fit_corrected_inputs",
             "scientific_status": "complete", "record_sha256": "0" * 64, "fit_dispatched": False},
            {"original_cell_id": "a", "status": "invented", "fit_dispatched": False},
            {"original_cell_id": "a", "status": "outcome_retained", "operation": "fit_corrected_inputs",
             "scientific_status": "complete", "record_sha256": self.checked("a"), "fit_dispatched": False},
            {"original_cell_id": "a", "status": "verified_existing_outcome", "record_sha256": None},
        ]
        for index, row in enumerate(bad_rows):
            path = self.pass_record([row], {"a": self.checked("a")}, f"bad_{index}")
            with self.assertRaises(g.InvalidProof):
                g.account_only(f.output, f.request, f.gates())
            path.unlink()

    def test_duplicate_foreign_reordered_or_extra_pending_fields_refused(self) -> None:
        f = self.fixture
        rows = [[self.existing("a"), self.existing("a")],
                [{"original_cell_id": "b", "status": "unresolved", "fit_dispatched": False}],
                [{"original_cell_id": "a", "status": "await_original_outcome", "fit_dispatched": False, "child_exit_code": 0}]]
        for index, items in enumerate(rows):
            path = self.pass_record(items, {"a": self.checked("a")}, f"bad_identity_{index}")
            with self.assertRaises(g.InvalidProof):
                g.account_only(f.output, f.request, f.gates())
            path.unlink()

    def test_all_legitimate_pending_rows_without_cells_are_kept(self) -> None:
        f = self.fixture
        for index, status in enumerate(sorted(g.PENDING_ACCOUNT_STATUSES)):
            path = self.pass_record([self.existing("a"), {"original_cell_id": "b", "status": status, "fit_dispatched": False}],
                                    {"a": self.checked("a")}, f"pending_{index}")
            g.account_only(f.output, f.request, f.gates())
            path.unlink()

    def test_partial_account_history_pending_then_terminal_then_more_cells_kept(self) -> None:
        f = self.fixture
        (f.output / "cells/a.json").unlink()
        self.pass_record([{"original_cell_id": "a", "status": "await_original_outcome", "fit_dispatched": False}], {}, "earlier_pending")
        f.account("a")
        self.pass_record([self.retained("a"), {"original_cell_id": "b", "status": "unresolved", "fit_dispatched": False}],
                         {"a": self.checked("a")}, "middle_partial")
        f.account("b")
        self.pass_record([self.existing("a"), self.retained("b")], {identity: self.checked(identity) for identity in ("a", "b")}, "later_full")
        g.account_only(f.output, f.request, f.gates())
        result = f.launch()
        self.assertEqual(result["guard_returncode"], 0)
        self.assertEqual(g.history(f.output, f.request, gates_factory=f.factory, testing=True)["invocations"], 1)

    def test_account_pass_counts_flags_hashes_and_subset_chain_refused(self) -> None:
        f = self.fixture
        path = self.pass_record([self.existing("a")], {"a": self.checked("a")})
        original = g.document(path)
        for key, value in (("retained_logical_outcomes", 7), ("scheduled_logical_cells", 2),
                           ("status", "all_logical_outcomes_accounted"), ("programme_complete", True),
                           ("record_sha256", {"foreign": None})):
            self.rewrite(path, {**original, key: value})
            with self.assertRaises(g.InvalidProof):
                g.account_only(f.output, f.request, f.gates())
        self.rewrite(path, original)
        f.account("b")
        self.pass_record([{"original_cell_id": "a", "status": "unresolved", "fit_dispatched": False}, self.retained("b")],
                         {"b": self.checked("b")})
        with self.assertRaises(g.InvalidProof):
            g.account_only(f.output, f.request, f.gates())


if __name__ == "__main__":
    unittest.main(verbosity=2)
