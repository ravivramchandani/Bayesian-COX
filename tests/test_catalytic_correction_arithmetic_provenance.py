"""Fictional sealed receipts only; no data or scientific backend is imported."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

VERIFICATION = Path(__file__).resolve().parents[1] / "scripts/catalytic_correction/verification"
sys.path.insert(0, str(VERIFICATION))

from verification_gates import verify_arithmetic_provenance  # noqa: E402
from verification_io import Pins, VerificationFailure, seal, sha, write_new  # noqa: E402


class ArithmeticProvenanceTests(unittest.TestCase):
    """Keep stale but otherwise complete arithmetic from authorising new inputs."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.definition = seal({"synthetic_fixture_only": "immutable_definition"})
        identifiers = [f"invented_context_{index:04d}::outer" for index in range(1650)]
        self.completion = seal({"status": "all_scheduled_contexts_accounted", "scheduled_contexts": 1650,
            "accounted_contexts": 1650, "outcomes": [{"context_id": identity,
                "status": "input_failure", "receipt_path": f"contexts/{identity}/receipt.json",
                "receipt_sha256": f"{index + 1:064x}"} for index, identity in enumerate(identifiers)]})
        self.replay = seal({"status": "all1650_independent_first_draw_contexts_accounted",
            "definition_content_sha256": self.definition["content_sha256"], "scheduled_contexts": 1650,
            "accounted_contexts": 1650, "outcomes": [{"context_id": identity,
                "receipt_path": f"replay/{identity}/receipt.json", "receipt_sha256": f"{index + 1651:064x}"}
                for index, identity in enumerate(identifiers)]})
        write_new(self.root / "preflight_completion.json", self.completion)
        write_new(self.root / "replay_completion.json", self.replay)
        self.completion_sha = sha(self.root / "preflight_completion.json")
        self.selector = {"schema_version": 1, "status": "all1650_context_arithmetic_requirements_accounted",
            "definition_content_sha256": self.definition["content_sha256"],
            "preflight_completion_sha256": self.completion_sha,
            "replay_completion_sha256": sha(self.root / "replay_completion.json"), "scheduled_contexts": 1650,
            "arithmetic_validation_executed": False, "scientific_method_approved": False,
            "entries": [{"context_id": original["context_id"],
                "preflight_receipt_path": original["receipt_path"], "preflight_receipt_sha256": original["receipt_sha256"],
                "replay_receipt_path": replay["receipt_path"], "replay_receipt_sha256": replay["receipt_sha256"],
                "arithmetic_executed_or_certified_by_selector": False}
                for original, replay in zip(self.completion["outcomes"], self.replay["outcomes"], strict=True)]}
        self.inventory = {"definition_content_sha256": self.definition["content_sha256"],
            "preflight_completion_sha256": self.completion_sha,
            "replay_completion_sha256": sha(self.root / "replay_completion.json")}
        self.arithmetic = {"status": "all_scheduled_arithmetic_outcomes_accounted",
            "preflight_completion_sha256": self.completion_sha,
            "definition_content_sha256": self.definition["content_sha256"], "scheduled_contexts": 1650,
            "context_outcomes": [{"context_id": identity, "status": "preflight_input_failure"}
                                 for identity in identifiers]}
        self.rebind_selector()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def rebind_selector(self) -> None:
        """Reseal fictional mutations so provenance tests cannot rely on bad JSON."""
        path = self.root / "arithmetic_selector.json"
        path.write_text(json.dumps(seal(self.selector), sort_keys=True, indent=2, allow_nan=False) + "\n")
        self.inventory["arithmetic_selector_sha256"] = sha(path)
        self.arithmetic["selector_sha256"] = sha(path)
        self.rebind_inventory()

    def rebind_inventory(self) -> None:
        path = self.root / "inventory.json"
        path.write_text(json.dumps(seal(self.inventory), sort_keys=True, indent=2, allow_nan=False) + "\n")
        self.inventory_sha = sha(path)
        self.arithmetic["input_inventory_sha256"] = self.inventory_sha

    def verify(self, pins: Pins | None = None):
        return verify_arithmetic_provenance(pins or Pins(), self.root, self.arithmetic, self.inventory,
            self.definition, self.inventory_sha, self.completion, self.completion_sha, self.replay)

    def test_current_complete_provenance_keeps_terminal_inputs_without_approval(self) -> None:
        observed = self.verify()
        self.assertEqual(observed, seal(self.selector))
        self.assertFalse(observed["arithmetic_validation_executed"])
        self.assertFalse(observed["scientific_method_approved"])
        self.assertNotIn("input_inventory_sha256", observed)

    def test_stale_inventory_or_missing_account_inventory_binding_refused(self) -> None:
        self.arithmetic["input_inventory_sha256"] = "0" * 64
        with self.assertRaisesRegex(VerificationFailure, "different input inventory"):
            self.verify()
        del self.arithmetic["input_inventory_sha256"]
        with self.assertRaisesRegex(VerificationFailure, "different input inventory"):
            self.verify()

    def test_stale_definition_in_account_inventory_selector_or_replay_refused(self) -> None:
        original = copy.deepcopy((self.arithmetic, self.inventory, self.selector, self.replay))
        for location in range(4):
            self.arithmetic, self.inventory, self.selector, self.replay = copy.deepcopy(original)
            target = (self.arithmetic, self.inventory, self.selector, self.replay)[location]
            target["definition_content_sha256"] = "0" * 64
            self.rebind_selector()
            with self.assertRaisesRegex(VerificationFailure, "scientific definition"):
                self.verify()

    def test_stale_account_selector_or_missing_inventory_selector_refused(self) -> None:
        self.arithmetic["selector_sha256"] = "0" * 64
        with self.assertRaisesRegex(VerificationFailure, "different selector"):
            self.verify()
        self.rebind_selector()
        for value in (None, "nonhex", "z" * 64):
            self.inventory["arithmetic_selector_sha256"] = value
            with self.assertRaisesRegex(VerificationFailure, "actual arithmetic selector bytes"):
                self.verify()

    def test_wrong_count_partial_account_or_selector_refused(self) -> None:
        original = copy.deepcopy((self.arithmetic, self.selector))
        for location, count in ((0, 1649), (0, None), (1, 1649), (1, True)):
            self.arithmetic, self.selector = copy.deepcopy(original)
            (self.arithmetic, self.selector)[location]["scheduled_contexts"] = count
            self.rebind_selector()
            with self.assertRaisesRegex(VerificationFailure, "whole1650"):
                self.verify()
        for location in range(2):
            self.arithmetic, self.selector = copy.deepcopy(original)
            (self.arithmetic["context_outcomes"], self.selector["entries"])[location].pop()
            self.rebind_selector()
            with self.assertRaisesRegex(VerificationFailure, "whole1650"):
                self.verify()

    def test_tampered_selector_bytes_and_post_read_change_refused(self) -> None:
        path = self.root / "arithmetic_selector.json"
        original = path.read_bytes()
        path.write_bytes(original + b" ")
        with self.assertRaises(VerificationFailure):
            self.verify()
        path.write_bytes(original)
        pins = Pins()
        self.verify(pins)
        path.write_bytes(original + b" ")
        with self.assertRaises(VerificationFailure):
            pins.recheck()

    def test_complete_but_duplicate_or_reordered_selector_refused(self) -> None:
        original = copy.deepcopy(self.selector)
        self.selector["entries"][-1] = copy.deepcopy(self.selector["entries"][0])
        self.rebind_selector()
        with self.assertRaisesRegex(VerificationFailure, "scope/order/duplicates"):
            self.verify()
        self.selector = original
        self.selector["entries"].reverse()
        self.rebind_selector()
        with self.assertRaisesRegex(VerificationFailure, "scope/order/duplicates"):
            self.verify()

    def test_selector_preflight_replay_and_current_receipt_bindings_refused(self) -> None:
        original = copy.deepcopy(self.selector)
        for field in ("preflight_completion_sha256", "replay_completion_sha256"):
            self.selector = copy.deepcopy(original)
            self.selector[field] = "0" * 64
            self.rebind_selector()
            with self.assertRaisesRegex(VerificationFailure, "preflight/independent replay provenance"):
                self.verify()
        for field in ("preflight_receipt_path", "preflight_receipt_sha256", "replay_receipt_path", "replay_receipt_sha256"):
            self.selector = copy.deepcopy(original)
            self.selector["entries"][0][field] = "invented_stale_receipt"
            self.rebind_selector()
            with self.assertRaisesRegex(VerificationFailure, "current context receipt/scope"):
                self.verify()

    def test_selector_cannot_claim_executed_arithmetic_or_method_approval(self) -> None:
        original = copy.deepcopy(self.selector)
        for field in ("arithmetic_validation_executed", "scientific_method_approved"):
            self.selector = copy.deepcopy(original)
            self.selector[field] = True
            self.rebind_selector()
            with self.assertRaisesRegex(VerificationFailure, "input-only"):
                self.verify()
        self.selector = original
        self.selector["entries"][0]["arithmetic_executed_or_certified_by_selector"] = True
        self.rebind_selector()
        with self.assertRaisesRegex(VerificationFailure, "current context receipt/scope"):
            self.verify()


if __name__ == "__main__":
    unittest.main(verbosity=2)
