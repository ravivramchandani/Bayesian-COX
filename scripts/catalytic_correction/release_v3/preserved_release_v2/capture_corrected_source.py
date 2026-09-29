"""Capture one pinned read-only source prerequisite using a genuine subprocess.

This is process provenance only. Deep verification, fitting, rendering, visual
approval, selected execution/resume and publication are outside this entrypoint.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    _parser = argparse.ArgumentParser(add_help=False)
    _parser.add_argument("--preparation-receipt", type=Path, required=True)
    _parser.add_argument("--preparation-receipt-sha256", required=True)
    _initial, _unknown = _parser.parse_known_args()
    if hashlib.sha256(_initial.preparation_receipt.read_bytes()).hexdigest() != _initial.preparation_receipt_sha256:
        raise RuntimeError("adapter preparation receipt differs")
    _preparation = json.loads(_initial.preparation_receipt.read_text())
    _own = Path(__file__).absolute().parent
    for _name, _digest in _preparation["implementation_source_sha256"].items():
        if Path(_name).name != _name or hashlib.sha256((_own / _name).read_bytes()).hexdigest() != _digest:
            raise RuntimeError("adapter implementation source differs")
    sys.path.insert(0, str(_own))

import release_core as core  # noqa: E402

MODES = {
    "reproduction": ("verify_restored_reproduction.py", "corrected_readonly_reproduction_actual_rc0_captured",
                     "corrected_selected_reproduction_restored_read_only_verified"),
    "reporting": ("replay_corrected_reporting.py", "corrected_reporting_replay_actual_rc0_captured",
                  "corrected_reporting_source_replay_verified"),
    "claims": ("summarize_corrected_claims.py", "corrected_claim_review_actual_rc0_captured",
               "corrected_factual_claim_inputs_verified"),
}


def capture_source(request: dict[str, Any], python: Path, pins: core.Pins, source_pins: dict[str, Any],
                   *, dependencies: dict[str, Any] | None = None, test_only: bool = False) -> dict[str, Any]:
    """No scientific dispatch; the injection seam cannot be selected by the CLI."""
    dependencies = {} if dependencies is None else dependencies
    core.require(not dependencies or test_only, "only fictional tests can inject a subprocess")
    core.require(request["schema_version"] == 1 and request["status"] == "corrected_read_only_source_capture_request"
                 and request["mode"] in MODES and request["test_only"] is False, "explicit read-only source capture required")
    mode = request["mode"]
    helper_name, capture_status, summary_status = MODES[mode]
    preparation_path, _ = core.record(request["helper_preparation"], pins)
    preparation_sha = source_pins["receiving_reproduction_preparation_sha256" if mode == "reproduction" else "reporting_qa_preparation_sha256"]
    core.require(request["helper_preparation"]["sha256"] == preparation_sha
                 and preparation_path.name == "preparation_receipt.json", "actual reviewed helper preparation differs")
    helper_root = preparation_path.parent
    preparation = core.load_preparation(helper_root, preparation_sha, pins)
    if mode == "reproduction":
        core.require(preparation["status"] == "corrected_reproduction_receiving_adapter_prepared"
                     and preparation["no_fit_or_generator_dispatch"] is True, "receiving-only reproduction preparation required")
    helper = helper_root / helper_name
    core.require(helper_name in preparation["implementation_source_sha256"], "read-only source helper omitted from byte pins")
    input_path, input_request = core.record(request["input_request"], pins)
    immutable = [core.safe(Path(value)) for value in request["immutable_roots"]]
    immutable_files = [core.safe(Path(value)) for value in request["immutable_files"]]
    core.require(immutable and len(set(immutable)) == len(immutable)
                 and len(set(immutable_files)) == len(immutable_files), "explicit unique source evidence roles required")
    actual_roots = ([Path(item["root"]) for item in input_request["immutable_roots"]] if mode == "reproduction"
                    else [Path(value) for value in input_request["roots"].values()])
    actual_files = ([Path(item["path"]) for item in input_request["immutable_files"]] if mode == "reproduction"
                    else [Path(value["path"]) for value in input_request["files"].values()])
    core.require(all(path in immutable for path in actual_roots)
                 and all(path in immutable_files or any(path.is_relative_to(root) for root in immutable) for path in actual_files),
                 "actual source evidence roles omitted from output-overlap protection")
    immutable += immutable_files + [helper_root, input_path, Path(__file__).absolute().parent]
    prefix = core.safe(Path(request["capture_prefix"]))
    core.no_overlap(prefix, immutable)
    core.require(prefix.parent.is_dir() and not any(prefix.parent.glob(prefix.name + ".*")), "exclusive external capture prefix required")
    output = None if mode == "claims" else core.safe(Path(request["evidence_output"]))
    core.require(mode != "claims" or request["evidence_output"] is None, "claims emit factual stdout only")
    if output is not None:
        core.no_overlap(output, [*immutable, prefix])
        core.no_overlap(prefix, [output])
    flag = "--bindings" if mode == "reproduction" else "--request"
    argv = [str(python), "-I", "-B", str(helper), flag, str(input_path), flag + "-sha256", request["input_request"]["sha256"]]
    if output is not None:
        argv += ["--output", str(output)]
    argv += ["--python", str(python)]
    def checked(summary: dict[str, Any]) -> None:
        core.require(summary["status"] == summary_status, "actual source helper emitted a pending/foreign/synthetic summary")
        if mode == "reproduction":
            core.require(summary["scheduled_selected_cells"] == summary["accounted_selected_cells"]
                         and summary["selection_sha256"] == input_request["selection_sha256"]
                         and summary["selected_pass_sha256"] == input_request["completed_pass"]["sha256"]
                         and summary["no_new_numerical_fit"] is True and summary["no_new_generator_recipe"] is True,
                         "actual source selected comparison incomplete or execution route")
        elif mode == "reporting":
            core.require(set(summary["source_bindings"]) == core.REPORT_BINDINGS
                         and summary["source_bindings"] == {name: input_request[name] for name in core.REPORT_BINDINGS}
                         and summary["sidecar_receipt_sha256"] == input_request["sidecar_receipt_sha256"]
                         and summary["deterministic_bytes_reproduced_exactly"] is True
                         and summary["no_new_fit_generator_optimizer_or_inference"] is True, "actual source report replay differs")
        else:
            core.require(summary["original_primary_negative_findings_preserved"] is True and summary["new_inferential_promotion"] is False,
                         "source factual claim summary changed frozen findings")
    pins.recheck()
    captured = core.capture_process(argv, prefix, pins, status=capture_status, validate_summary=checked,
        entrypoint=helper, entrypoint_sha=preparation["implementation_source_sha256"][helper_name],
        invoke=dependencies.get("invoke", subprocess.run))
    if output is not None:
        receipt_name = "receipt.json" if mode == "reproduction" else "reporting_replay_receipt.json"
        proof_path = output / receipt_name
        summary = captured["summary"]
        core.require(summary["receipt_path"] == str(proof_path), "actual source proof is not in its new external output")
        proof = core.document(proof_path, pins, summary["receipt_sha256"])
        core.require(proof["status"] == summary_status and
                     (proof["test_only_dependency_injection"] is False if mode == "reproduction" else proof["test_only"] is False),
                     "actual source proof absent or synthetic")
        core.declared_output_tree(output, proof, pins, receipt_name=receipt_name)
    pins.recheck()
    return {"status": capture_status, "receipt_path": captured["receipt_path"], "receipt_sha256": captured["receipt_sha256"],
            "actual_source_gates_remain_separate": True, "programme_complete": False, "test_only": test_only}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("preparation-receipt", "request", "python"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("preparation-receipt-sha256", "request-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    python = core.runtime(args.python)
    pins = core.Pins()
    own = Path(__file__).absolute().parent
    preparation = core.load_preparation(own, args.preparation_receipt_sha256, pins)
    core.require(args.preparation_receipt == own / "preparation_receipt.json", "adapter receipt path differs")
    source_pins = core.document(own / "source_pins.json", pins, preparation["source_pins_sha256"], field=None)
    request = core.document(args.request, pins, args.request_sha256)
    result = capture_source(request, python, pins, source_pins)
    pins.recheck()
    print(json.dumps(result, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
