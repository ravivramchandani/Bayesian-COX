"""Separately pinned per-entry I/O entrypoint; no execution occurs on import."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
OWN = ("location_core.py", "capture_at_location.py", "capture_original_at_location.py",
       "selected_at_locations.py", "run_selected_at_locations.py", "receiving_at_locations.py",
       "verify_restored_at_locations.py", "verification_io.py")


def bootstrap(path: Path, expected: str, python: Path) -> tuple[Any, dict[str, Any]]:
    if not python.is_absolute() or not python.is_file() or not python.samefile(Path(sys.executable)):
        raise ValueError("actual locked interpreter differs")
    numeric = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
    if any(os.environ.get(name) != "1" for name in numeric):
        raise ValueError("all five numeric thread variables must already equal one")
    if not path.is_absolute() or any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError("unlinked absolute preparation receipt required")
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("preparation bytes differ")
    prepared = json.loads(path.read_text())
    root = Path(__file__).absolute().parent
    if set(prepared["implementation_source_sha256"]) != set(OWN):
        raise ValueError("honest exact new implementation pins required")
    for name, pin in prepared["implementation_source_sha256"].items():
        item = root / name
        if any(part.is_symlink() for part in (item, *item.parents)) or hashlib.sha256(item.read_bytes()).hexdigest() != pin:
            raise ValueError("adapter sources differ")
    if "location_core" in sys.modules:
        raise ValueError("adapter namespace occupied")
    spec = importlib.util.spec_from_file_location("location_core", root / "location_core.py")
    if spec is None or spec.loader is None:
        raise ValueError("adapter loader unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    if module.preparation(path, expected) != prepared:
        raise ValueError("preparation changed while loading")
    return module, prepared


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("selection", "location-plan", "preparation-receipt", "output", "python"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("selection-sha256", "location-plan-sha256", "preparation-receipt-sha256"):
        parser.add_argument("--" + name, required=True)
    for name in ("pilot-review", "resolution-review", "original-numerical-resolution"):
        parser.add_argument("--" + name, type=Path)
        parser.add_argument("--" + name + "-sha256")
    args = parser.parse_args(argv)
    try:
        loc, prepared = bootstrap(args.preparation_receipt, args.preparation_receipt_sha256, args.python)
        support = loc.import_pin(Path(__file__).with_name("selected_at_locations.py").absolute(),
            prepared["implementation_source_sha256"]["selected_at_locations.py"], "_per_entry_selected_support")
        result = support.run(args, prepared)
        loc.preparation(args.preparation_receipt, args.preparation_receipt_sha256)
        print(json.dumps(result, sort_keys=True, allow_nan=False), flush=True)
        return 0
    except (ValueError, OSError, KeyError, TypeError) as error:
        print(json.dumps({"status": "per_entry_selected_reproduction_refused_or_failed", "error": str(error),
                          "programme_complete": False}, sort_keys=True), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
