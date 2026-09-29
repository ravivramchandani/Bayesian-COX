"""Read-only v3 receiving orchestration; never selected execute/resume."""

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
    """Require actual safe transport and fresh mixed/selected/reporting replay."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("preparation-receipt", "request", "output", "python"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("preparation-receipt-sha256", "request-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    base = wiring.foundation()
    python = base.runtime(args.python)
    own = wiring.own_prepare(args.preparation_receipt, args.preparation_receipt_sha256)
    pins = base.Pins()
    request = base.document(args.request, pins, args.request_sha256)
    restored = base.safe(Path(request["restored"]))
    manifest = base.document(restored / "corrected_release_stage.json", pins, request["stage_manifest_sha256"])
    extra = request["per_entry_io"]
    base.require(extra["revision"] == 3 and extra["release_v3_preparation_sha256"] == args.preparation_receipt_sha256
                 and args.preparation_receipt == restored / wiring.STATIC_LAYOUT["release_v3_preparation"] / "preparation_receipt.json",
                 "byte-identical restored v3 source role required")
    view = wiring.ReceivingView(extra, own, args.preparation_receipt_sha256, manifest, restored,
                               {"path": str(args.request), "sha256": args.request_sha256})
    legacy_root = restored / base.LAYOUT["release_adapter_preparation"]
    sources = base.document(legacy_root / "source_pins.json", pins, field=None)
    base.no_overlap(args.output, [restored, args.request, Path(__file__).absolute().parent])
    with wiring.legacy_module(legacy_root, "verify_restored_correction.py", view) as original:
        result = original.science(request, args.output, python, sources, pins, {})
    pins.recheck()
    print(json.dumps({**result, "release_wiring_revision": 3, "publication_certified": False}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
