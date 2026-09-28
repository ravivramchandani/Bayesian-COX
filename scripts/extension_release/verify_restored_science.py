"""Recheck transferred extension evidence and stored refits without fitting."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from failure_transfer import verify_failure_transfer
from qa_transfer import verify_visual_transfer
from stage_extensions import verify_source_inputs


def main() -> None:
    """Require source, baseline, all-cell and exact stored-refit checks to pass."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("production-code", "analysis-code", "restored", "primary", "sampler", "robustness"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--report", type=Path, help="new receipt outside the restored evidence tree")
    args = parser.parse_args()
    if args.report and (args.report.exists() or args.report.is_symlink()):
        raise FileExistsError(args.report)
    production, analysis, restored = args.production_code.resolve(), args.analysis_code.resolve(), args.restored.resolve()
    if args.report and args.report.resolve().is_relative_to(restored):
        raise ValueError("write the new verification receipt outside the preserved evidence tree")
    sys.path.insert(0, str(analysis))
    from scripts.reproduce_extensions import compare_traces, scientific_content
    from src.pipelines.extensions.runner import verified_cell
    from src.pipelines.extensions.verification import assert_scientific_equal
    from src.utils.io import read_mapping
    from src.utils.reproducibility import sha256_file

    run, refits = restored / "evidence/run", restored / "evidence/reproduction"
    manifest = read_mapping(run / "manifest.json")
    sources = verify_source_inputs(production, manifest, restored / "data/matched_metabric.parquet",
                                   restored / "data/matched_metabric_manifest.json", restored / "data/metabric_raw",
                                   restored / "data/metabric_source_report.json", analysis=analysis)
    failure_helper = restored / "execution/audit_rank_failures.py"
    failure_provenance = verify_failure_transfer(run, restored / "failure_provenance", failure_helper)
    stage_record = read_mapping(restored / "release_stage.json")
    if (stage_record["failure_provenance"] != failure_provenance
            or stage_record["transfer_tool_sha256"]["audit_rank_failures.py"] != sha256_file(failure_helper)):
        raise ValueError("restored supplemental failure provenance differs from staging")
    visual_transfer = verify_visual_transfer(restored / "visual_qa", restored / "rendered", run,
                                            qa_helper=analysis / "scripts/extension_release/extension_pdf_qa.py",
                                            renderer=analysis / "scripts/render_extensions.py")
    if stage_record["visual_qa_transfer"] != visual_transfer:
        raise ValueError("restored visual-review evidence differs from staging")
    subprocess.run([sys.executable, str(analysis / "scripts/verify_environment.py"),
                    "--lock-file", str(analysis / "conda-lock.yml"),
                    "--hash-file", str(analysis / "conda-lock.yml.sha256")], check=True)
    subprocess.run([sys.executable, str(analysis / "scripts/finalize_extensions.py"),
                    "--matched", str(restored / "data/matched_metabric.parquet"), "--run", str(run),
                    "--production-code", str(production), "--primary", str(args.primary),
                    "--sampler", str(args.sampler), "--robustness", str(args.robustness)], check=True)
    selected = {row["cell_id"] for row in manifest["plan"] if "__r01f01__" in row["cell_id"]}
    if len(selected) != 92:
        raise ValueError("selected reproduction grid differs from 92 frozen cells")
    for folder in ("cells", "receipts"):
        if {p.stem for p in (refits / folder).glob("*.json")} != selected:
            raise ValueError(f"stored refit inventory differs: {folder}")
    for identity in sorted(selected):
        source = verified_cell(run / "cells" / f"{identity}.json")
        refit = verified_cell(refits / "cells" / f"{identity}.json")
        receipt = read_mapping(refits / "receipts" / f"{identity}.json")
        expected = {"cell_id": identity, "status": "scientific_match",
                    "source_content_sha256": source["cell_content_sha256"],
                    "refit_content_sha256": refit["cell_content_sha256"],
                    "trace_sample_arrays": "exact; timing/NetCDF metadata excluded"}
        if receipt != expected:
            raise ValueError(f"stored reproduction receipt differs: {identity}")
        assert_scientific_equal(scientific_content(source), scientific_content(refit), identity)
        compare_traces(run, refits, source, refit)
    with tempfile.TemporaryDirectory(prefix="extension-rank-restore-") as temporary:
        repeated_audit = Path(temporary) / "failure_provenance"
        subprocess.run([sys.executable, str(failure_helper), "--production-code", str(production),
                        "--run", str(run), "--matched", str(restored / "data/matched_metabric.parquet"),
                        "--output", str(repeated_audit)], check=True)
        if verify_failure_transfer(run, repeated_audit, failure_helper) != failure_provenance:
            raise ValueError("independently reconstructed rank-failure provenance differs")
    report = {"status": "restored_science_verified", "evidence_status": "post_hoc_extension",
              "verified_utc": datetime.now(UTC).isoformat(), "frozen_source_sha256": sources,
              "run_completion_sha256": sha256_file(run / "completion.json"),
              "selected_refits_recompared": 92, "trace_arrays": "exact; timing/NetCDF metadata excluded",
              "rank_failed_cells_reconstructed": failure_provenance["rank_failed_cells_audited"],
              "failure_snapshot_sha256": failure_provenance["snapshot_sha256"],
              "visual_qa_transfer": visual_transfer,
              "verifier_sha256": sha256_file(Path(__file__)),
              "source_gate_sha256": sha256_file(Path(__file__).with_name("stage_extensions.py")),
              "visual_review": "preserved original receipt; no new visual review claimed"}
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        with args.report.open("x") as handle:
            handle.write(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
