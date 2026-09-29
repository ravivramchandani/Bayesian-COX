"""Delegate frozen855 presentation to a separately certified mixed view."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __name__ == "__main__":
    _bootstrap = argparse.ArgumentParser(add_help=False)
    _bootstrap.add_argument("--preparation-receipt", type=Path, required=True)
    _bootstrap.add_argument("--preparation-receipt-sha256", required=True)
    _initial, _unknown = _bootstrap.parse_known_args()
    if hashlib.sha256(_initial.preparation_receipt.read_bytes()).hexdigest() != _initial.preparation_receipt_sha256:
        raise RuntimeError("preparation receipt bytes differ")
    _document = json.loads(_initial.preparation_receipt.read_text())
    _own = Path(__file__).absolute().parent
    for _name, _expected in _document["implementation_source_sha256"].items():
        if Path(_name).name != _name or hashlib.sha256((_own / _name).read_bytes()).hexdigest() != _expected:
            raise RuntimeError("verification implementation bytes differ")
    sys.path.insert(0, str(_own))

from verification_io import (  # noqa: E402
    Pins,
    child,
    require,
    safe,
    seal,
    sha,
    write_new,
)


def renderer_namespace(path: Path) -> dict[str, Any]:
    """Load pinned renderer definitions/imports, withholding its CLI invocation."""
    tree = ast.parse(path.read_bytes(), filename=str(path))
    # Only the last original __name__ guard is removed; no scientific reducer
    # or presentation definition is rewritten. Imports run only at real render.
    require(isinstance(tree.body[-1], ast.If) and isinstance(tree.body[-1].test, ast.Compare), "renderer main guard differs")
    tree.body.pop()
    namespace: dict[str, Any] = {"__file__": str(path), "__name__": "_mixed_frozen_renderer"}
    exec(compile(ast.fix_missing_locations(tree), str(path), "exec"), namespace)
    return namespace


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("preparation-receipt", "verified", "analysis", "verification-capture", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("preparation-receipt-sha256", "completion-sha256", "verification-capture-sha256"):
        parser.add_argument("--" + name, required=True)
    args = parser.parse_args()
    pins = Pins()
    own = Path(__file__).absolute().parent
    preparation = pins.json(safe(args.preparation_receipt), args.preparation_receipt_sha256)
    for name, digest in preparation["implementation_source_sha256"].items():
        pins.bind(child(own, name), digest)
    verified, analysis, output = safe(args.verified), safe(args.analysis), safe(args.output)
    require(not output.exists() and output.parent.is_dir() and all(not output.is_relative_to(root) and not root.is_relative_to(output)
        for root in (verified, analysis, own)), "new renderer output must be outside immutable evidence/source")
    completion = pins.json(verified / "completion.json", args.completion_sha256)
    capture = pins.json(safe(args.verification_capture), args.verification_capture_sha256)
    require(capture["status"] == "mixed_verification_actual_rc0_captured" and capture["exit_code"] == 0
            and capture["completion_sha256"] == args.completion_sha256
            and completion["status"] == "mixed_original_corrected_grid_deep_verified_and_frozen_analysis_recomputed"
            and completion["verified_logical_cells"] == completion["planned_logical_cells"] == 1625,
            "actual successful mixed-verifier capture and complete certificate required")
    pins.artifacts(args.verification_capture.parent, capture["artifacts"])
    require(args.verification_capture.name.endswith(".receipt.json"), "capture receipt name differs")
    capture_prefix = args.verification_capture.name.removesuffix(".receipt.json")
    require({path.name for path in args.verification_capture.parent.glob(capture_prefix + ".*")} ==
            {capture_prefix + suffix for suffix in (".stdout.log", ".stderr.log", ".attempt.json", ".receipt.json")}
            and not any(args.verification_capture.parent.glob(".verification-pending-" + capture_prefix + ".*")),
            "capture inventory has residual/missing/colliding files")
    for name in ("stdout", "stderr"):
        # Preserve actual original absolute argv/log paths as metadata; restored
        # artifact resolution uses the capture receipt's logical sibling files.
        require(capture["artifacts"][Path(capture[name + "_path"]).name]["sha256"] == capture[name + "_sha256"],
                "capture raw log binding differs")
    for field in ("cell_sha256", "aggregate_sha256", "lineage_sha256", "check_sha256", "initial_invocation_metadata_sha256"):
        for name, digest in completion[field].items():
            pins.bind(child(verified, name), digest)
    for name, field in (("manifest.json", "manifest_sha256"), ("render_input.json", "render_input_sha256"),
                        ("comparison_accounting.json", "comparison_accounting_sha256"), ("reference_verification.json", "reference_verification_sha256")):
        pins.bind(verified / name, completion[field])
    source_pins = json.loads((own / "source_pins.json").read_text())
    pins.bind(own / "source_pins.json", preparation["source_pins_sha256"])
    for name, digest in source_pins["files"]["analysis"].items():
        pins.bind(child(analysis, name), digest)
    require(not any(name == "src" or name.startswith("src.") for name in sys.modules), "fresh renderer project namespace required")
    namespace = renderer_namespace(analysis / "scripts/render_extensions.py")
    original_read = namespace["read_mapping"]
    def mixed_cell(path: Path) -> dict[str, Any]:
        name = str(path.relative_to(verified))
        require(name in completion["cell_sha256"], "renderer requests an unverified mixed cell")
        return pins.json(path, completion["cell_sha256"][name], field="cell_content_sha256")
    def mapped_read(path: Path) -> dict[str, Any]:
        if path.parent == verified and path.name in {"paired_families.json", "rq2_effects.json", "decision_curves.json"}:
            return original_read(verified / "aggregates" / path.name)
        return original_read(path)
    namespace["verified_cell"], namespace["read_mapping"] = mixed_cell, mapped_read
    original_save = namespace["save_figure"]
    def labelled_save(fig: Any, destination: Path, name: str, sources: list[str]) -> dict[str, Any]:
        fig.text(0.01, 0.036, "Post-hoc rank-conditioned correction | Mixed original reuse and corrected fits | Original failures retained", fontsize=7)
        return original_save(fig, destination, name, sources)
    namespace["save_figure"] = labelled_save
    previous = sys.argv
    try:
        sys.argv = [str(analysis / "scripts/render_extensions.py"), "--run", str(verified), "--output", str(output)]
        namespace["main"]()
    finally:
        sys.argv = previous
    for name, module in list(sys.modules.items()):
        if name == "src" or name.startswith("src."):
            path = safe(Path(module.__file__).absolute())
            require(path.is_relative_to(analysis), "renderer imported a foreign project module")
            pins.bind(path, source_pins["files"]["analysis"][str(path.relative_to(analysis))])
    pins.recheck()
    write_new(output / "mixed_correction_lineage.json", seal({"schema_version": 1,
        "evidence_status": "post_hoc_rank_conditioned_correction_after_original_failures_known",
        "mixed_completion_sha256": args.completion_sha256, "actual_verifier_capture_sha256": args.verification_capture_sha256,
        "original_renderer_sha256": source_pins["files"]["analysis"]["scripts/render_extensions.py"],
        "adapter_sha256": sha(Path(__file__).absolute()), "original_renderer_lineage_sha256": sha(output / "lineage.json"),
        "aggregate_source_mapping": {name: "aggregates/" + name for name in ("paired_families.json", "rq2_effects.json", "decision_curves.json")},
        "renderer_changes": ["bind_verified_mixed_cells_without_copying_raw_traces", "resolve_own_aggregate_namespace", "add_correction_provenance_footer"],
        "actual_visual_review": "pending; rendering is not QA", "programme_complete": False,
        "selected_reproduction_and_private_fresh_restore": "pending"}))


if __name__ == "__main__":
    main()
