"""Original transport delegation guards; fictional ordinary files, no archives."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import release_core as c
import verify_restored_correction as vr
from test_release_adapters import raw


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="fictional-corrected-transport-")
        self.base = Path(self.temp.name).resolve(strict=True)
        self.code, self.package = (self.base / name for name in ("code", "package"))
        self.code.mkdir()
        self.package.mkdir()
        sources = ("archive_common.py", "stage_extensions.py", "package.py", "verify.py", "qa_transfer.py")
        for name in sources:
            raw(self.code / name, b"# fictional original transport, never imported or executed\n")
        self.pins = {"transport_sources": {name: c.sha(self.code / name) for name in sources}}
        self.restored, self.output = (self.base / name for name in ("restored", "capture"))
        self.request = {"status": "corrected_transport_restore_request", "transport_code": str(self.code),
            "package": str(self.package), "restored": str(self.restored), "trusted_inventory_canonical_sha256": "a" * 64}
        self.python = Path("/fictional/locked_python")

    def tearDown(self):
        self.temp.cleanup()

    def test_original_verifier_isolated_bootstrap_and_exact_capture(self):
        calls = []
        def invoke(argv, **_kwargs):
            calls.append(argv)
            self.restored.mkdir()
            raw(self.restored / "fictional_member.bytes", b"ordinary copied fixture; no archive")
            return SimpleNamespace(returncode=0, stdout=(json.dumps({"canonical_sha256": "a" * 64,
                "restored": str(self.restored), "shards": 1, "members": 1}) + "\n").encode(), stderr=b"")
        result = vr.transport(self.request, self.output, self.python, self.pins, c.Pins(), {"invoke": invoke})
        self.assertEqual(calls[0][1:4], ["-I", "-B", "-c"])
        self.assertEqual(calls[0][6], str(self.code / "verify.py"))
        self.assertFalse(result["scientific_verification_completed"])
        self.assertEqual(len(list(self.output.iterdir())), 4)
        self.assertTrue(c.document(Path(result["receipt_path"]), c.Pins())["test_only_dependency_injection"])

    def test_wrong_trusted_canonical_digest_fails_with_actual_logs(self):
        def invoke(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout=(json.dumps({"canonical_sha256": "b" * 64,
                "restored": str(self.restored), "shards": 1, "members": 1}) + "\n").encode(), stderr=b"fixture stderr")
        with self.assertRaisesRegex(ValueError, "trusted inventory"):
            vr.transport(self.request, self.output, self.python, self.pins, c.Pins(), {"invoke": invoke})
        self.assertEqual(c.document(self.output / "transport.attempt.json", c.Pins())["exit_code"], 0)
        self.assertFalse((self.output / "transport.receipt.json").exists())

    def test_no_overwrite_or_overlap(self):
        self.restored.mkdir()
        with self.assertRaises(ValueError):
            vr.transport(self.request, self.output, self.python, self.pins, c.Pins(), {})
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
