"""Read-only semantic guard replay, with explicit authenticated receiving mappings."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path


def main() -> None:
    """Write only new external factual evidence; never rewrite restored input."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("request", "locations", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    for name in ("request", "locations", "location-review"):
        parser.add_argument(f"--{name}-sha256", required=True)
    args = parser.parse_args()
    if not (sys.flags.isolated == 1 and sys.dont_write_bytecode):
        raise RuntimeError("read-only verifier requires -I -B")
    if hashlib.sha256(args.request.read_bytes()).hexdigest() != args.request_sha256:
        raise RuntimeError("trusted request hash differs")
    request = json.loads(args.request.read_text())
    code = Path(__file__).absolute().parent
    for name in ("verify_guarded_dispatch_proof.py", "guard_fit_dispatch.py"):
        path = code / name
        if any(node.is_symlink() for node in (path, *path.parents)) or hashlib.sha256(path.read_bytes()).hexdigest() != request["guard_source_sha256"][name]:
            raise RuntimeError("actual verifier source differs")
    alias = "_guard_dispatch_runtime"
    if alias in sys.modules:
        raise RuntimeError("occupied runtime alias")
    specification = importlib.util.spec_from_file_location(alias, code / "guard_fit_dispatch.py")
    if specification is None or specification.loader is None:
        raise RuntimeError("runtime source unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[alias] = module
    try:
        specification.loader.exec_module(module)
        result = module.verify_guarded_dispatch_proof(args.request, args.request_sha256, args.locations,
            args.locations_sha256, args.location_review_sha256, args.output, executing_code_directory=code)
        print(json.dumps({"status": result["status"], "receipt_path": str(args.output / "receipt.json"),
              "receipt_sha256": module.binding(args.output / "receipt.json")["sha256"],
              "scientific_completion_certified": False}, sort_keys=True))
        if not result["successful_guard_coverage"]:
            raise SystemExit(1)
    finally:
        sys.modules.pop(alias, None)


if __name__ == "__main__":
    main()
