"""Single-time cumulative/dynamic area under the curve (AUC) compatibility wrapper.

The confirmatory pipeline calls :func:`src.evaluation.metrics.time_dependent_auc`
directly; :func:`time_dependent_auc_at` evaluates it at one time point.
"""

import numpy as np

from src.evaluation.metrics import time_dependent_auc as _cumulative_dynamic_auc


def time_dependent_auc_at(
    y_time: np.ndarray,
    y_event: np.ndarray,
    risk_scores: np.ndarray,
    eval_time: float,
    train_time: np.ndarray | None = None,
    train_event: np.ndarray | None = None,
) -> float:
    """Return cumulative/dynamic AUC at a single evaluation time.

    Censoring weights use training outcomes when both training arrays
    are supplied; otherwise both arrays come from the evaluated sample.

    Args:
        y_time: Evaluated times of shape (n_subjects,), in the cohort's unit.
        y_event: Matching binary event indicators (0/1).
        risk_scores: Finite scores of shape (n_subjects,); larger means greater risk.
        eval_time: Supported evaluation time in the same unit as ``y_time``.
        train_time: Optional separate training follow-up times.
        train_event: Matching training event indicators; both training
            arrays are needed to avoid the compatibility fallback.

    Returns:
        A scalar AUC at ``eval_time``.

    Raises:
        ValueError: Outcomes, scores or the evaluation time are invalid.
        UnsupportedCensoringError: The censoring or reference metric
            calculation does not support ``eval_time``.
    """
    if train_time is None or train_event is None:
        train_time, train_event = y_time, y_event

    auc, _ = _cumulative_dynamic_auc(
        train_time,
        train_event,
        y_time,
        y_event,
        risk_scores,
        np.array([eval_time], dtype=float),
    )
    return float(auc[0])
