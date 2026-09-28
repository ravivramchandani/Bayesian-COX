"""Pure publication rendering from frozen result files.

``scripts/render_confirmatory.py`` calls :func:`render_run`, which verifies a
completed confirmatory run (and, optionally, an explainability result and a
robustness run), then writes tables and figures into a new, empty output
directory together with ``lineage.json``. The renderer is pure: it reads only
stored, hash-verified artefacts, never imports a model or pipeline module and
never fits anything (a test in ``tests/test_holm_bounds.py`` enforces this).

Modules:

- ``verification``: hash and completeness checks on every source artefact.
- ``outputs``: deterministic table and figure writers and the lineage record.
- ``metrics``: cohort flow, fold metrics, paired IBS effects, calibration and
  runtime.
- ``holm_bounds``: the ADR-033 post-hoc bound on the incomplete Holm family.
- ``diagnostics``: predictive checks, proportional-hazards tests and trace
  snapshots.
- ``supplemental``: explanation and robustness summaries.
- ``runner``: the order in which the above are called.
- ``constants``: shared labels, colours and fixed figure metadata.

The names below, including private helpers, are re-exported so that
``scripts/render_confirmatory.py`` and existing imports of it keep working."""

from .constants import COLORS as COLORS
from .constants import FIXED_PDF_DATE as FIXED_PDF_DATE
from .constants import METRIC_LABELS as METRIC_LABELS
from .constants import MODEL_LABELS as MODEL_LABELS
from .constants import PROJECT_ROOT as PROJECT_ROOT
from .diagnostics import _component_labels as _component_labels
from .diagnostics import _ph_rows_from_cells as _ph_rows_from_cells
from .diagnostics import _predictive_check_rows as _predictive_check_rows
from .diagnostics import _render_ph as _render_ph
from .diagnostics import _render_predictive_checks as _render_predictive_checks
from .diagnostics import _render_trace_snapshots as _render_trace_snapshots
from .diagnostics import _render_trace_variable as _render_trace_variable
from .diagnostics import _snapshot_records as _snapshot_records
from .diagnostics import _trace_array as _trace_array
from .metrics import _calibration_rows as _calibration_rows
from .metrics import _cohort_rows as _cohort_rows
from .metrics import _metric_rows as _metric_rows
from .metrics import _metric_summary as _metric_summary
from .metrics import _paired_ibs_rows as _paired_ibs_rows
from .metrics import _render_calibration as _render_calibration
from .metrics import _render_cohort_flow as _render_cohort_flow
from .metrics import _render_fold_metrics as _render_fold_metrics
from .metrics import _render_paired_ibs as _render_paired_ibs
from .metrics import _render_runtime as _render_runtime
from .metrics import _runtime_rows as _runtime_rows
from .outputs import OutputRegistry as OutputRegistry
from .outputs import _atomic_text as _atomic_text
from .outputs import _cell_sources as _cell_sources
from .outputs import _configure_style as _configure_style
from .outputs import _save_figure as _save_figure
from .outputs import _write_table as _write_table
from .runner import render_run as render_run
from .supplemental import _explanation_rows as _explanation_rows
from .supplemental import _render_explanation as _render_explanation
from .supplemental import _render_robustness as _render_robustness
from .supplemental import _robustness_effect_rows as _robustness_effect_rows
from .verification import FrozenRun as FrozenRun
from .verification import _finite as _finite
from .verification import _load_mapping as _load_mapping
from .verification import _safe_child as _safe_child
from .verification import _slug as _slug
from .verification import _source as _source
from .verification import _verify_content_hash as _verify_content_hash
from .verification import canonical_json_hash as canonical_json_hash
from .verification import sha256_file as sha256_file
from .verification import verify_explainability_artifact as verify_explainability_artifact
from .verification import verify_frozen_run as verify_frozen_run
from .verification import verify_robustness_run as verify_robustness_run
