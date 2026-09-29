"""Recompute preserved sidecar/claim bytes with explicit relocated evidence roles."""

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
    """Read-only relocated replay; new metadata lives wholly outside restored inputs."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("request", "output", "python"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    args = parser.parse_args()
    core.runtime(args.python)
    snapshot = core.Snapshot()
    request = snapshot.read("invocation/request.json", args.request, args.request_sha256, field="content_sha256")
    core.require(request["status"] == "corrected_reporting_read_only_replay_request", "receiving-only request required")
    core.bind_preparation(request, snapshot)
    deps = core.dependencies(snapshot, interval=True)
    state = reporting.prerequisite_state(request, snapshot, deps)
    _, artifacts = reporting.build(state, deps, snapshot)
    helper_sha = core.sha_bytes((Path(__file__).absolute().parent / "generate_corrected_reporting.py").read_bytes())
    sidecar = core.safe(Path(request["roots"]["sidecar"]))
    result = reporting.verify_existing(sidecar, artifacts, state, helper_sha, snapshot)
    core.require(request["sidecar_receipt_sha256"] == result["sidecar_receipt_sha256"], "preserved original reporting receipt differs")
    claim_binding = request["files"]["claim_stdout"]
    original_claim_raw = snapshot.capture("invocation/original_claim_stdout", Path(claim_binding["path"]), claim_binding["sha256"])
    core.require(bool(original_claim_raw.splitlines()), "actual source claim raw stdout missing")
    original_claim = core.strict_json(original_claim_raw.splitlines()[-1])
    current_claim = reporting.claim_summary(state, deps)
    core.require(current_claim == original_claim, "restored factual claim summary differs from actual captured source stdout")
    snapshot.recheck()
    immutable = [Path(value) for value in request["roots"].values()] + [Path(__file__).absolute().parent, args.request]
    core.new_directory(args.output, immutable)
    core.write_new(args.output / "claim_replay_summary.json", current_claim)
    core.write_new(args.output / "preserved_visual_qa.json", state["visual"])
    receipt = core.seal({**result, "original_claim_stdout_sha256": claim_binding["sha256"],
        "claim_summary_reproduced_exactly": True, "new_visual_approval_conferred": False,
        "test_only": False,
        "artifacts": {name: {"sha256": core.sha_bytes((args.output / name).read_bytes()),
                             "bytes": (args.output / name).stat().st_size}
                      for name in ("claim_replay_summary.json", "preserved_visual_qa.json")},
        "invocation": core.invocation(args.request_sha256)})
    core.write_new(args.output / "reporting_replay_receipt.json", receipt)
    core.require({p.name for p in args.output.iterdir()} == {"claim_replay_summary.json", "preserved_visual_qa.json", "reporting_replay_receipt.json"},
                 "external replay metadata inventory differs")
    snapshot.recheck()
    summary = {key: value for key, value in receipt.items() if key != "content_sha256"}
    summary.update(receipt_path=str(args.output / "reporting_replay_receipt.json"),
                   receipt_sha256=core.sha_bytes((args.output / "reporting_replay_receipt.json").read_bytes()))
    print(json.dumps(summary, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
