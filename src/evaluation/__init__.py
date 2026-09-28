"""Public survival-evaluation interfaces.

``metrics`` holds the discrimination and prediction-error metrics and the
training-only choice of evaluation horizons; ``calibration`` and
``calibration_model`` hold the fixed-horizon calibration estimators. The
confirmatory and robustness pipelines call them once per fitted model and
validation fold.
"""

from .calibration import survival_calibration_curve, survival_calibration_summary
from .metrics import (
    UnsupportedCensoringError,
    censoring_survival_at,
    evaluate_model,
    harrell_c_index,
    integrated_brier,
    time_dependent_auc,
    training_event_time_horizons,
    uno_c_index,
    validate_ipcw_horizons,
)

__all__ = [
    "UnsupportedCensoringError",
    "censoring_survival_at",
    "evaluate_model",
    "harrell_c_index",
    "integrated_brier",
    "survival_calibration_curve",
    "survival_calibration_summary",
    "time_dependent_auc",
    "training_event_time_horizons",
    "uno_c_index",
    "validate_ipcw_horizons",
]
