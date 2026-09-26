"""Ranking and discrimination metrics."""

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
    """Cumulative/dynamic AUC at a single time point.

    Censoring weights come from the training sample when one is supplied,
    otherwise from the evaluated sample itself.
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
