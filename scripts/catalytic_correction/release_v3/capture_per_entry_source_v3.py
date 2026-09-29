"""Genuine v3 source controller/read-only capture; no dispatch on import."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    initial = argparse.ArgumentParser(add_help=False)
    initial.add_argument("--preparation-receipt", type=Path, required=True)
    initial.add_argument("--preparation-receipt-sha256", required=True)
    args, _ = initial.parse_known_args()
    root = Path(__file__).absolute().parent
    if (args.preparation_receipt != root / "preparation_receipt.json"
            or not args.preparation_receipt.is_absolute()
            or any(p.is_symlink() for p in (args.preparation_receipt, *args.preparation_receipt.parents))
            or not args.preparation_receipt.is_file()):
        raise RuntimeError("actual unlinked v3 preparation path required")
    if hashlib.sha256(args.preparation_receipt.read_bytes()).hexdigest() != args.preparation_receipt_sha256:
        raise RuntimeError("v3 preparation bytes differ")
    prepared = json.loads(args.preparation_receipt.read_bytes())
    exact = {"release_v3_core.py", "stage_corrected_extensions_v3.py", "capture_per_entry_source_v3.py", "verify_restored_correction_v3.py"}
    if set(prepared["implementation_source_sha256"]) != exact:
        raise RuntimeError("separately named exact v3 source surface required")
    for name, digest in prepared["implementation_source_sha256"].items():
        path = root / name
        if (any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file()
                or hashlib.sha256(path.read_bytes()).hexdigest() != digest):
            raise RuntimeError("v3 source bytes differ")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root))

import release_v3_core as wiring  # noqa: E402


def main() -> None:
    """The CLI has no injection option and cannot infer success from a pass."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("preparation-receipt", "request", "python"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("preparation-receipt-sha256", "request-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    base = wiring.foundation()
    python = base.runtime(args.python)
    own = wiring.own_prepare(args.preparation_receipt, args.preparation_receipt_sha256)
    pins = base.Pins()
    request = base.document(args.request, pins, args.request_sha256)
    result = wiring.source_capture(request, {"path": str(args.request), "sha256": args.request_sha256},
                                   python, own, args.preparation_receipt_sha256)
    pins.recheck()
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
