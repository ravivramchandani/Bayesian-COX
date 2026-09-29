"""Narrow V3 impossible-reuse regressions using fictional metadata only."""

from __future__ import annotations

import unittest
from pathlib import Path
from typing import Any

import test_guarded_dispatch as fixture
import test_guarded_dispatch_regressions as previous

g = fixture.g


class GuardV3ReuseConsistency(unittest.TestCase):
    """Borrow only fixture helpers, preserving all original 34 test methods."""

    setUp = fixture.GuardTests.setUp
    tearDown = fixture.GuardTests.tearDown
    rewrite = fixture.GuardTests.rewrite
    make_reuse = previous.GuardV2Regressions.make_reuse

    def change_decision(self, key: str, value: Any) -> None:
        """Reseal a single invented decision without touching any real outcome."""
        path = self.fixture.output / "cells/a.json"
        cell = g.document(path)
        decision = {name: item for name, item in cell["decision"].items() if name != "decision_content_sha256"}
        decision[key] = value
        decision["decision_content_sha256"] = g.digest(decision)
        self.rewrite(path, {**cell, "decision": decision})

    def refuse_before_introduction(self) -> None:
        """Refuse both account validation and launcher before any guard write."""
        f = self.fixture
        before = g.tree(f.output)
        with self.assertRaises(g.InvalidProof):
            g.account_only(f.output, f.request, f.gates())
        with self.assertRaises(g.InvalidProof):
            f.launch()
        self.assertEqual(g.tree(f.output), before)
        self.assertEqual(f.controller_calls, 0)
        self.assertFalse((f.output / g.NAMESPACE).exists())

    def test_reused_changed_roles_impossible_and_refused(self) -> None:
        self.make_reuse("failed_diagnostics")
        self.change_decision("changed_roles", ["model_sources"])
        self.refuse_before_introduction()

    def test_reused_missing_roles_impossible_and_refused(self) -> None:
        self.make_reuse("failed_diagnostics")
        self.change_decision("missing_roles", ["model_sources"])
        self.refuse_before_introduction()

    def test_reused_generator_failure_impossible_and_refused(self) -> None:
        self.make_reuse("failed_diagnostics")
        self.change_decision("generator_failures", {"outer": "input_failure"})
        self.refuse_before_introduction()

    def test_reused_nonnull_tuning_marker_impossible_and_refused(self) -> None:
        self.make_reuse("failed_diagnostics")
        self.change_decision("tuning_record_reused_sha256", g.digest("FICTIONAL impossible tuning reuse"))
        self.refuse_before_introduction()

    def test_terminal_nonnull_tuning_marker_impossible_and_refused(self) -> None:
        self.change_decision("tuning_record_reused_sha256", g.digest("FICTIONAL terminal tuning reuse"))
        self.refuse_before_introduction()

    def test_original_negative_reuse_statuses_remain_valid(self) -> None:
        for status in ("complete", "failed", "failed_diagnostics"):
            with self.subTest(status=status):
                self.make_reuse(status)
                state = g.account_only(self.fixture.output, self.fixture.request, self.fixture.gates())
                cell = g.document(self.fixture.output / "cells/a.json")
                self.assertEqual(cell["scientific_status"], status)
                self.assertIsNone(cell["decision"]["tuning_record_reused_sha256"])
                self.assertEqual(state, g.tree(self.fixture.output, omit_guard=True))

    def test_terminal_failures_keep_legitimate_missing_and_changed_roles(self) -> None:
        self.change_decision("missing_roles", ["model_sources"])
        self.change_decision("changed_roles", ["outer.synthetic_constructor_inputs"])
        state = g.account_only(self.fixture.output, self.fixture.request, self.fixture.gates())
        cell = g.document(Path(self.fixture.output) / "cells/a.json")
        self.assertEqual(cell["decision"]["action"], "retain_input_failure")
        self.assertEqual(cell["failure_contexts"], {"outer": "input_failure"})
        self.assertEqual(cell["decision"]["missing_roles"], ["model_sources"])
        self.assertEqual(cell["decision"]["changed_roles"], ["outer.synthetic_constructor_inputs"])
        self.assertIsNone(cell["decision"]["tuning_record_reused_sha256"])
        self.assertEqual(state, g.tree(self.fixture.output, omit_guard=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
