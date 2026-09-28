"""Prespecified robustness analysis of the three Bayesian priors.

The robustness stage refits only the Bayesian models (normal, horseshoe and
spike-and-slab priors) under planned perturbations of the confirmatory design,
on selected outer folds, and summarises paired prior differences in the
integrated Brier score (IBS). Its components are:

- ``rq2``: research question 2 (RQ2), information-regime robustness. Training
  subsets of 25, 50, 75 and 100 percent, and two administrative-censoring
  truncations at full size, on outer folds 1 and 2 of every repeat.
- ``design``: prior-scale scenarios and baseline-hazard resolution, one
  factor at a time, compared on outer fold 1 of every repeat.
- ``feature``: alternative feature sets and, for METABRIC, a five-imputation
  sensitivity, compared on outer fold 1 of every repeat.
- ``ph``: a pure summary of the proportional-hazards (PH) tests stored in the
  confirmatory Cox cells; nothing is fitted.

A run moves through these modules:

1. ``protocol``: run options, the condition record and frozen constants.
2. ``conditions`` and ``planning``: the de-duplicated condition plan, the
   nested training subsets and truncation cutoffs, the fit counts and the
   result-blind runtime projection.
3. ``cells``, ``evaluation`` and ``imputation``: fit and score one Bayesian
   model under one condition on one fold, applying the confirmatory
   diagnostic gate in ``robustness`` mode, and store one content-hashed cell.
4. ``inference``: paired IBS contrasts, RQ2 difference-in-differences with a
   three-stage bootstrap, and the PH aggregation.
5. ``runner`` and ``provenance``: orchestration, the run manifest and the
   verification of a completed run without refitting.

``scripts/run_robustness.py`` calls :func:`execute_robustness_run`. This
initialiser re-exports the names that scripts and tests import, including the
confirmatory helpers the robustness modules reuse.
"""

from src.pipelines.confirmatory import (
    DiagnosticFailure,
    RunOptions,
    _feature_spec,
    _fit_with_diagnostic_rule,
    _ibs_times,
    administratively_truncate_for_ipcw,
    deterministic_seed,
    load_analysis_dataset,
    relevant_input_files,
    validate_survival_prediction_matrix,
    verify_protocol_freeze,
)
from src.utils.io import json_safe as _json_safe
from src.utils.io import write_json_atomic as _atomic_json

from .cells import _cell_path, load_robustness_cells, run_robustness_cell, validate_robustness_cell
from .conditions import (
    _condition_config,
    _fold_condition_indices,
    _merge_conditions,
    _stable_hash,
    apply_administrative_censoring,
    build_condition_plan,
    build_design_conditions,
    build_feature_conditions,
    build_rq2_conditions,
    effective_information_ratio,
    stratified_training_subsets,
)
from .evaluation import (
    _as_structured,
    evaluate_robustness_predictions,
    individual_integrated_brier_losses,
    summarize_imputation_predictions,
)
from .imputation import _MultipleImputationPredictionEnsemble, multiple_imputed_fold_frames
from .inference import (
    _bootstrap_contributions,
    _cell_analysis_names,
    aggregate_ph_tests,
    paired_ibs_inference,
)
from .planning import planned_fit_counts, projected_runtime_from_confirmatory
from .protocol import (
    BAYESIAN_MODEL_KEYS,
    DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT,
    ITERATIVE_IMPUTER_MAX_ITER,
    MULTIPLE_IMPUTATIONS,
    RUNTIME_OVERHEAD_MULTIPLIER,
    RobustnessCondition,
    RobustnessOptions,
)
from .provenance import (
    _external_result_inputs,
    robustness_input_files,
    verify_completed_robustness_run,
)
from .runner import _write_aggregates, execute_robustness_run

__all__ = [
    "verify_completed_robustness_run",
    "_json_safe",
    "_atomic_json",
    "BAYESIAN_MODEL_KEYS",
    "MULTIPLE_IMPUTATIONS",
    "ITERATIVE_IMPUTER_MAX_ITER",
    "DESIGN_FEATURE_FOLD_NUMBERS_PER_REPEAT",
    "RUNTIME_OVERHEAD_MULTIPLIER",
    "RobustnessOptions",
    "RobustnessCondition",
    "_stable_hash",
    "stratified_training_subsets",
    "apply_administrative_censoring",
    "effective_information_ratio",
    "build_rq2_conditions",
    "build_design_conditions",
    "build_feature_conditions",
    "_merge_conditions",
    "build_condition_plan",
    "_condition_config",
    "_fold_condition_indices",
    "planned_fit_counts",
    "projected_runtime_from_confirmatory",
    "_as_structured",
    "individual_integrated_brier_losses",
    "summarize_imputation_predictions",
    "evaluate_robustness_predictions",
    "multiple_imputed_fold_frames",
    "_MultipleImputationPredictionEnsemble",
    "run_robustness_cell",
    "validate_robustness_cell",
    "_cell_path",
    "load_robustness_cells",
    "_cell_analysis_names",
    "_bootstrap_contributions",
    "paired_ibs_inference",
    "aggregate_ph_tests",
    "robustness_input_files",
    "_external_result_inputs",
    "_write_aggregates",
    "execute_robustness_run",
    "DiagnosticFailure",
    "RunOptions",
    "_feature_spec",
    "_fit_with_diagnostic_rule",
    "_ibs_times",
    "administratively_truncate_for_ipcw",
    "deterministic_seed",
    "load_analysis_dataset",
    "relevant_input_files",
    "validate_survival_prediction_matrix",
    "verify_protocol_freeze",
]
