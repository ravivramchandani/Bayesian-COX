"""Capture exactly one root-selected missing ORIGINAL numerical producer proof.

No execution occurs on import. The CLI has no dependency-injection, arbitrary
command, retry, resume, all92 or review-generation option.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    """Verify this sealed preparation before importing the stdlib adapter."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument("--preparation-receipt", type=Path, required=True)
    parser.add_argument("--preparation-receipt-sha256", required=True)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        own = Path(__file__).absolute().parent
        receipt = args.preparation_receipt
        if not receipt.is_absolute() or any(path.is_symlink() for path in (receipt, *receipt.parents)):
            raise ValueError("unlinked absolute preparation receipt required")
        if hashlib.sha256(receipt.read_bytes()).hexdigest() != args.preparation_receipt_sha256:
            raise ValueError("preparation receipt byte SHA differs")
        preparation: dict[str, Any] = json.loads(receipt.read_text(encoding="utf-8"))
        pins = preparation["implementation_source_sha256"]
        if set(pins) != {"producer_capture.py", "capture_original_producer.py", "verification_io.py"}:
            raise ValueError("exact implementation source pins required")
        for name, expected in pins.items():
            path = own / name
            if any(item.is_symlink() for item in (path, *path.parents)) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("capture source differs")
        spec = importlib.util.spec_from_file_location("_bound_original_producer_capture", own / "producer_capture.py")
        if spec is None or spec.loader is None:
            raise ValueError("capture module loader unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        if module.io.read(receipt, args.preparation_receipt_sha256) != preparation or preparation["status"] != "original_missing_producer_capture_adapter_prepared":
            raise ValueError("sealed preparation status/content differs")
        module.io.require(preparation["actual_science_executed"] is False, "preparation cannot claim actual science")
        # Pin the preparation itself before dispatch and after process return.
        before = module.io.sha(receipt)
        result = module.capture(args.request, args.request_sha256, args.python, preparation)
        module.io.require(module.io.sha(receipt) == before, "preparation changed during capture")
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "original_producer_capture_refused_or_failed", "error": str(error),
                          "programme_complete": False}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
