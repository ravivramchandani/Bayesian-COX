"""Factual corrected claim inputs with original primary negative evidence intact."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

if __name__ == "__main__":
    _initial = argparse.ArgumentParser(add_help=False)
    _initial.add_argument("--request", type=Path, required=True)
    _initial.add_argument("--request-sha256", required=True)
    _args, _remaining = _initial.parse_known_args()
    if hashlib.sha256(_args.request.read_bytes()).hexdigest() != _args.request_sha256:
        raise RuntimeError("request byte pin differs")
    _request = json.loads(_args.request.read_text())
    _receipt_path = Path(_request["preparation_receipt"]["path"])
    if hashlib.sha256(_receipt_path.read_bytes()).hexdigest() != _request["preparation_receipt"]["sha256"]:
        raise RuntimeError("preparation receipt byte pin differs")
    _receipt = json.loads(_receipt_path.read_text())
    _own = Path(__file__).absolute().parent
    _required_implementation = {"support_core.py", "reporting.py", "corrected_pdf_qa.py",
                                "generate_corrected_reporting.py", "summarize_corrected_claims.py",
                                "replay_corrected_reporting.py"}
    if set(_receipt["implementation_source_sha256"]) != _required_implementation:
        raise RuntimeError("reporting/QA implementation scope differs")
    for _name, _digest in _receipt["implementation_source_sha256"].items():
        if Path(_name).name != _name or hashlib.sha256((_own / _name).read_bytes()).hexdigest() != _digest:
            raise RuntimeError("reporting/QA implementation bytes differ")
    sys.path.insert(0, str(_own))

import reporting  # noqa: E402
import support_core as core  # noqa: E402


def main() -> None:
    """Emit only source-bound stored facts; actual caller rc0 capture stays separate."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("request", "python"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    args = parser.parse_args()
    core.runtime(args.python)
    snapshot = core.Snapshot()
    request = snapshot.read("invocation/request.json", args.request, args.request_sha256, field="content_sha256")
    core.bind_preparation(request, snapshot)
    deps = core.dependencies(snapshot)
    state = reporting.prerequisite_state(request, snapshot, deps)
    result = reporting.claim_summary(state, deps)
    snapshot.recheck()
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
