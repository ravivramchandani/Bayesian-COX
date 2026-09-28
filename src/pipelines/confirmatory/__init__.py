"""Confirmatory repeated nested cross-validation, from fold-local fitting to paired inference.

Six models are compared on paired outer folds of each cohort: Cox
proportional hazards (PH), random survival forest, DeepSurv, and the Bayesian
piecewise-exponential PH model under normal, horseshoe and spike-and-slab
coefficient priors. One *cell* is one model fitted and scored on one outer
fold. A run moves through these modules:

1. ``options``: model roster, run controls and per-cell seeds.
2. ``runner``: plans the fold-by-model grid, skips cells already stored, and
   orchestrates the stages below.
3. ``fitting``: builds each model, tunes the forest and DeepSurv by inner
   cross-validation, and applies the Bayesian diagnostic gate with its
   prespecified refits.
4. ``evaluation``: chooses training-derived horizons and the integrated Brier
   score (IBS) grid, and scores the outer-validation fold.
5. ``cells`` and ``posterior``: assemble one content-hashed JSON record per
   cell.
6. ``aggregation``: checks every cell hash and writes the fold-metric and
   out-of-fold (OOF) prediction tables.
7. ``inference``: paired Nadeau–Bengio (NB) contrasts, Holm adjustment and the
   event-stratified paired OOF bootstrap.
8. ``provenance``: the input inventory and protocol-freeze checks.
   ``storage`` holds the YAML reader they share.

``scripts/run_confirmatory.py`` calls :func:`execute_confirmatory_run`. This
initialiser re-exports the names that scripts, tests and the robustness
package import, including private helpers under their original aliases (for
example ``_ibs_times`` for :func:`evaluation_horizons_and_grid`). ``fitting``
and ``cells`` look up ``_model_from_parameters``, ``_posterior_trace_snapshot``
and ``_fit_with_diagnostic_rule`` in this namespace at call time, so a
replacement made here takes effect; the diagnostic-failure tests rely on this
for the first two.
"""

from src.data.cohorts import load_analysis_dataset as load_analysis_dataset
from src.data.cohorts import select_feature_spec as _feature_spec
from src.utils.io import json_safe as _json_safe
from src.utils.io import write_json_atomic as _atomic_json

from .aggregation import _aggregate_tables as _aggregate_tables
from .aggregation import _cell_path as _cell_path
from .aggregation import _load_cells as _load_cells
from .cells import run_cell as run_cell
from .evaluation import administratively_truncate_for_ipcw as administratively_truncate_for_ipcw
from .evaluation import evaluate_predictions as _evaluate_predictions
from .evaluation import evaluation_horizons_and_grid as _ibs_times
from .evaluation import evaluation_horizons_and_grid as evaluation_horizons_and_grid
from .evaluation import validate_survival_prediction_matrix as validate_survival_prediction_matrix
from .fitting import _fit_with_diagnostic_rule as _fit_with_diagnostic_rule
from .fitting import _model_candidates as _model_candidates
from .fitting import _model_from_parameters as _model_from_parameters
from .fitting import tune_candidate as tune_candidate
from .inference import _event_stratified_indices as _event_stratified_indices
from .inference import _paired_oof_ibs_bootstrap as _paired_oof_ibs_bootstrap
from .inference import _repeated_cv_inference as _repeated_cv_inference
from .options import MODEL_KEYS as MODEL_KEYS
from .options import MODEL_LABELS as MODEL_LABELS
from .options import DiagnosticFailure as DiagnosticFailure
from .options import RunOptions as RunOptions
from .options import deterministic_seed as deterministic_seed
from .posterior import _model_details as _model_details
from .posterior import _posterior_trace_snapshot as _posterior_trace_snapshot
from .provenance import relevant_input_files as relevant_input_files
from .provenance import verify_protocol_freeze as verify_protocol_freeze
from .provenance import verify_run_inputs_unchanged as verify_run_inputs_unchanged
from .runner import execute_confirmatory_run as execute_confirmatory_run
from .storage import _load_yaml as _load_yaml

__all__ = [
    "DiagnosticFailure",
    "MODEL_KEYS",
    "MODEL_LABELS",
    "RunOptions",
    "_aggregate_tables",
    "_atomic_json",
    "_cell_path",
    "_evaluate_predictions",
    "_event_stratified_indices",
    "_feature_spec",
    "_fit_with_diagnostic_rule",
    "_ibs_times",
    "_json_safe",
    "_load_cells",
    "_load_yaml",
    "_model_candidates",
    "_model_details",
    "_model_from_parameters",
    "_paired_oof_ibs_bootstrap",
    "_posterior_trace_snapshot",
    "_repeated_cv_inference",
    "administratively_truncate_for_ipcw",
    "deterministic_seed",
    "evaluation_horizons_and_grid",
    "execute_confirmatory_run",
    "load_analysis_dataset",
    "relevant_input_files",
    "run_cell",
    "tune_candidate",
    "validate_survival_prediction_matrix",
    "verify_protocol_freeze",
    "verify_run_inputs_unchanged",
]
