"""Check restored selected reproduction evidence without executing numerical jobs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bindings", type=Path, required=True)
    parser.add_argument("--bindings-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--python", type=Path, required=True)
    args = parser.parse_args()
    if not args.python.is_absolute() or not args.python.is_file() or not args.python.samefile(Path(sys.executable)):
        raise ValueError("actual process differs from supplied receiving interpreter")
    numeric = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
    if any(os.environ.get(name) != "1" for name in numeric):
        raise ValueError("all five numeric thread variables must already equal one")
    if hashlib.sha256(args.bindings.read_bytes()).hexdigest() != args.bindings_sha256:
        raise ValueError("receiving binding bytes differ before helper loading")
    value = json.loads(args.bindings.read_text())
    support = Path(__file__).absolute().with_name("receiving_core.py")
    if hashlib.sha256(support.read_bytes()).hexdigest() != value["receiving_source_sha256"][support.name]:
        raise ValueError("receiving support byte pin differs")
    specification = importlib.util.spec_from_file_location("_selected_reproduction_receiving", support)
    if specification is None or specification.loader is None or specification.name in sys.modules:
        raise ValueError("receiving support private namespace unavailable")
    module = importlib.util.module_from_spec(specification)
    sys.modules[specification.name] = module
    specification.loader.exec_module(module)
    receipt = module.verify_receiving(args.bindings, args.bindings_sha256, args.output, args.python)
    print(json.dumps({"status": receipt["status"], "receipt_path": str(args.output / "receipt.json"),
        "receipt_sha256": module.binding(args.output / "receipt.json")["sha256"],
        "selection_sha256": receipt["selection_sha256"], "selected_pass_sha256": receipt["completed_pass_sha256"],
        "scheduled_selected_cells": receipt["selected_union_cells"], "accounted_selected_cells": receipt["accounted_selected_cells"],
        "route_counts": receipt["selected_route_counts"], "no_new_numerical_fit": True,
        "no_new_generator_recipe": True}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
