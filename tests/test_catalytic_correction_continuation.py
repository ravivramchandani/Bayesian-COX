"""Synthetic orchestration guards; no scientific subprocess is launched."""

from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from scripts.catalytic_correction import continue_prefit as helper


class ContinuationGuards(unittest.TestCase):
    """Check stopped owners, malformed evidence and retained process failures."""

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_sealed_roundtrip_and_no_overwrite(self) -> None:
        path = self.root / "receipt.json"
        helper.publish(path, {"synthetic_fixture": True, "value": 1})
        self.assertEqual(helper.read(path, helper.sha(path))["value"], 1)
        with self.assertRaises(ValueError):
            helper.publish(path, {"value": 2})
        path.write_text(path.read_text().replace('"value": 1', '"value": 2'))
        with self.assertRaises(ValueError):
            helper.read(path)

    def test_nonfinite_or_wrong_byte_receipt_rejected(self) -> None:
        path = self.root / "receipt.json"
        helper.publish(path, {"value": 1})
        with self.assertRaises(ValueError):
            helper.read(path, "0" * 64)
        path.write_text('{"value": NaN}')
        with self.assertRaises(ValueError):
            helper.read(path)

    def test_complete_accounting_does_not_require_all_inputs_accepted(self) -> None:
        path = self.root / "completion.json"
        value = {"status": "all_scheduled_contexts_accounted", "scheduled_contexts": 1650,
                 "accounted_contexts": 1650,
                 "outcomes": [{"context_id": f"fixture_{i}", "status": "exhausted_rank_cap"} for i in range(1650)]}
        helper.publish(path, value)
        self.assertEqual(len(helper.complete_preflight(path)["outcomes"]), 1650)

    def test_reduced_or_duplicate_coverage_refused(self) -> None:
        for case in ("reduced", "duplicate"):
            value = {"status": "all_scheduled_contexts_accounted", "scheduled_contexts": 1650,
                     "accounted_contexts": 1650,
                     "outcomes": [{"context_id": f"fixture_{i}"} for i in range(1650)]}
            if case == "reduced":
                value["outcomes"].pop()
            else:
                value["outcomes"][-1] = value["outcomes"][0]
            path = self.root / (case + ".json")
            helper.publish(path, value)
            with self.assertRaises(ValueError):
                helper.complete_preflight(path)

    def test_dead_and_reused_preflight_pid_distinguished(self) -> None:
        command = b"invented preflight command\n"
        request = {"preflight_pid": 999999, "preflight_process_command_sha256": hashlib.sha256(command).hexdigest()}
        with patch.object(helper.os, "kill", side_effect=ProcessLookupError):
            self.assertFalse(helper.preflight_running(request))
        with patch.object(helper.os, "kill"), patch.object(helper.subprocess, "run",
                return_value=SimpleNamespace(returncode=0, stdout=command)):
            self.assertTrue(helper.preflight_running(request))
        with patch.object(helper.os, "kill"), patch.object(helper.subprocess, "run",
                return_value=SimpleNamespace(returncode=0, stdout=b"unrelated command")):
            with self.assertRaises(ValueError):
                helper.preflight_running(request)

    def test_code_drift_rejected_before_execution(self) -> None:
        path = self.root / "helper.py"
        path.write_text("invented source")
        request = {"paths": {"code": str(self.root)}, "code_commit": "fixture_commit",
                   "code_sha256": {"helper.py": "0" * 64}}
        with patch.object(helper.subprocess, "check_output", side_effect=["fixture_commit\n", ""]):
            with self.assertRaises(ValueError):
                helper.verify_code(request)

    def test_failed_process_retains_invocation_and_logs(self) -> None:
        environment = {name: "1" for name in helper.THREADS}

        def failing(_command, *, stdout, stderr, **_kwargs):
            stdout.write(b"synthetic partial stdout")
            stderr.write(b"synthetic failure")
            return SimpleNamespace(returncode=7)

        with patch.object(helper.subprocess, "run", side_effect=failing):
            with self.assertRaises(ValueError):
                helper.execute("fixture", ["invented-command"], self.root, environment)
        record = helper.read(self.root / "fixture.invocation.json")
        self.assertEqual(record["exit_code"], 7)
        self.assertEqual(record["stdout_sha256"], helper.sha(self.root / "fixture.stdout.log"))
        self.assertEqual((self.root / "fixture.stderr.log").read_bytes(), b"synthetic failure")

    def test_failed_link_retains_attributable_closed_bytes_and_refuses_retry(self) -> None:
        path = self.root / "new.json"
        with patch.object(helper.os, "link", side_effect=OSError("synthetic link failure")):
            with self.assertRaises(OSError):
                helper.publish(path, {"fixture": "closed bytes"})
        retained = list(self.root.glob(".continuation-new.json-*"))
        self.assertEqual(len(retained), 1)
        self.assertEqual(helper.read(retained[0])["fixture"], "closed bytes")
        self.assertFalse(path.exists())
        with self.assertRaises(ValueError):
            helper.publish(path, {"fixture": "new attempt"})

    def test_cleanup_failure_cannot_be_success_and_keeps_both_byte_identical_names(self) -> None:
        path = self.root / "new.json"
        with patch.object(Path, "unlink", side_effect=OSError("synthetic cleanup failure")):
            with self.assertRaises(OSError):
                helper.publish(path, {"fixture": 1})
        retained = list(self.root.glob(".continuation-new.json-*"))
        self.assertEqual(len(retained), 1)
        self.assertEqual(retained[0].read_bytes(), path.read_bytes())

    def test_publication_syncs_file_and_parent_after_commit_and_cleanup(self) -> None:
        sync = helper.os.fsync
        with patch.object(helper.os, "fsync", wraps=sync) as observed:
            helper.publish(self.root / "new.json", {"fixture": 1})
        self.assertEqual(observed.call_count, 3)
        self.assertFalse(list(self.root.glob(".continuation-new.json-*")))

    def test_overlap_refused_before_directory_creation(self) -> None:
        code = self.root / "code"
        code.mkdir()
        for destination in (code / "output", self.root):
            request = {"paths": {"code": str(code), "continuation": str(destination)}}
            with self.assertRaises(ValueError):
                helper.safe_destination(request)
        self.assertFalse((code / "output").exists())

    def test_only_actual_interpreter_alias_is_permitted(self) -> None:
        alias = self.root / "python"
        alias.symlink_to(sys.executable)
        output = self.root / "output"
        request = {"paths": {"python": str(alias), "continuation": str(output)}}
        self.assertEqual(helper.safe_destination(request), output)
        self.assertFalse(output.exists())
        other = self.root / "invented-interpreter"
        other.write_bytes(b"invented executable")
        request["paths"]["python"] = str(other)
        with self.assertRaises(ValueError):
            helper.safe_destination(request)


if __name__ == "__main__":
    unittest.main(verbosity=2)
