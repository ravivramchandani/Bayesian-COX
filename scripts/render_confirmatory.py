"""Render a publication package from verified frozen result files."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.rendering import COLORS as COLORS
from src.rendering import FIXED_PDF_DATE as FIXED_PDF_DATE
from src.rendering import METRIC_LABELS as METRIC_LABELS
from src.rendering import MODEL_LABELS as MODEL_LABELS
from src.rendering import PROJECT_ROOT as PROJECT_ROOT
from src.rendering import FrozenRun as FrozenRun
from src.rendering import OutputRegistry as OutputRegistry
from src.rendering import _atomic_text as _atomic_text
from src.rendering import _calibration_rows as _calibration_rows
from src.rendering import _cell_sources as _cell_sources
from src.rendering import _cohort_rows as _cohort_rows
from src.rendering import _component_labels as _component_labels
from src.rendering import _configure_style as _configure_style
from src.rendering import _explanation_rows as _explanation_rows
from src.rendering import _finite as _finite
from src.rendering import _load_mapping as _load_mapping
from src.rendering import _metric_rows as _metric_rows
from src.rendering import _metric_summary as _metric_summary
from src.rendering import _paired_ibs_rows as _paired_ibs_rows
from src.rendering import _ph_rows_from_cells as _ph_rows_from_cells
from src.rendering import _predictive_check_rows as _predictive_check_rows
from src.rendering import _render_calibration as _render_calibration
from src.rendering import _render_cohort_flow as _render_cohort_flow
from src.rendering import _render_explanation as _render_explanation
from src.rendering import _render_fold_metrics as _render_fold_metrics
from src.rendering import _render_paired_ibs as _render_paired_ibs
from src.rendering import _render_ph as _render_ph
from src.rendering import _render_predictive_checks as _render_predictive_checks
from src.rendering import _render_robustness as _render_robustness
from src.rendering import _render_runtime as _render_runtime
from src.rendering import _render_trace_snapshots as _render_trace_snapshots
from src.rendering import _render_trace_variable as _render_trace_variable
from src.rendering import _robustness_effect_rows as _robustness_effect_rows
from src.rendering import _runtime_rows as _runtime_rows
from src.rendering import _safe_child as _safe_child
from src.rendering import _save_figure as _save_figure
from src.rendering import _slug as _slug
from src.rendering import _snapshot_records as _snapshot_records
from src.rendering import _source as _source
from src.rendering import _trace_array as _trace_array
from src.rendering import _verify_content_hash as _verify_content_hash
from src.rendering import _write_table as _write_table
from src.rendering import canonical_json_hash as canonical_json_hash
from src.rendering import render_run as render_run
from src.rendering import sha256_file as sha256_file
from src.rendering import verify_explainability_artifact as verify_explainability_artifact
from src.rendering import verify_frozen_run as verify_frozen_run
from src.rendering import verify_robustness_run as verify_robustness_run


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Pure renderer for a completed frozen confirmatory run. Rehearsals "
            "produce a labelled runtime-only package."
        )
    )
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--explainability-artifact", type=Path, default=None)
    parser.add_argument("--robustness-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dir = args.run_dir.resolve()
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else PROJECT_ROOT / "reports" / "rendered" / run_dir.name
    )
    rendered = render_run(
        run_dir,
        output_dir,
        explainability_artifact=(
            args.explainability_artifact.resolve()
            if args.explainability_artifact is not None
            else None
        ),
        robustness_dir=(args.robustness_dir.resolve() if args.robustness_dir is not None else None),
    )
    print(f"rendered_artifact={rendered}", flush=True)
    print(f"evidence_lineage={rendered / 'lineage.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
