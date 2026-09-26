"""Repeated nested-validation study, from fold-local fitting to paired inference.

The package keeps the original import surface for scripts and the robustness
stage. Cohort loading, evaluation, fitting, cell records, aggregation, inference
and run orchestration live in separate modules.
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
