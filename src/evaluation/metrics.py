"""Survival evaluation metrics.

Harrell's concordance index, the integrated Brier score, and time-dependent
AUC are delegated to scikit-survival so that results match the reference
implementations used in the published benchmarks.
"""

from typing import Any

import numpy as np
from sksurv.metrics import (
    concordance_index_censored,
    cumulative_dynamic_auc,
    integrated_brier_score,
)
from sksurv.util import Surv


def _as_structured(time: np.ndarray, event: np.ndarray) -> np.ndarray:
    return Surv.from_arrays(
        event=np.asarray(event).astype(bool), time=np.asarray(time, dtype=float)
    )


def concordance_index(
    y_time: np.ndarray, y_event: np.ndarray, risk_scores: np.ndarray
) -> tuple[float, float]:
    """Harrell's C-index and its standard error.

    Args:
        y_time: Follow-up time.
        y_event: 1 if the event was observed, 0 if censored.
        risk_scores: Predicted risk; higher means shorter expected survival.

    Returns:
        The C-index and an asymptotic standard error based on the number of
        comparable pairs.
    """
    y_time = np.asarray(y_time, dtype=float)
    y_event = np.asarray(y_event).astype(bool)
    risk_scores = np.asarray(risk_scores, dtype=float)

    c_index, concordant, discordant, tied_risk, _ = concordance_index_censored(
        y_event, y_time, risk_scores
    )

    n_pairs = concordant + discordant + tied_risk
    se = float(np.sqrt(c_index * (1 - c_index) / n_pairs)) if n_pairs > 0 else 0.0
    return float(c_index), se


def integrated_brier(
    train_time: np.ndarray,
    train_event: np.ndarray,
    test_time: np.ndarray,
    test_event: np.ndarray,
    survival_probs: np.ndarray,
    eval_times: np.ndarray,
) -> float:
    """Integrated Brier score over `eval_times`.

    Args:
        survival_probs: Predicted survival probabilities, shape
            (n_test_samples, n_eval_times).
    """
    return float(
        integrated_brier_score(
            _as_structured(train_time, train_event),
            _as_structured(test_time, test_event),
            np.asarray(survival_probs, dtype=float),
            np.asarray(eval_times, dtype=float),
        )
    )


def time_dependent_auc(
    train_time: np.ndarray,
    train_event: np.ndarray,
    test_time: np.ndarray,
    test_event: np.ndarray,
    risk_scores: np.ndarray,
    eval_times: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Cumulative/dynamic AUC at each evaluation time and its mean."""
    auc, mean_auc = cumulative_dynamic_auc(
        _as_structured(train_time, train_event),
        _as_structured(test_time, test_event),
        np.asarray(risk_scores, dtype=float),
        np.asarray(eval_times, dtype=float),
    )
    return np.asarray(auc, dtype=float), float(mean_auc)


def evaluation_times(
    time: np.ndarray, event: np.ndarray, n_times: int = 3
) -> np.ndarray:
    """Evaluation time grid inside the follow-up range.

    Times are quantiles of the observed event times, clipped away from the
    boundaries so that the censoring distribution remains estimable.
    """
    time = np.asarray(time, dtype=float)
    event = np.asarray(event).astype(bool)

    event_times = time[event]
    if event_times.size == 0:
        event_times = time

    lower, upper = np.percentile(event_times, [10, 90])
    grid = np.linspace(lower, upper, n_times)
    return np.unique(np.clip(grid, time.min() + 1e-6, time.max() - 1e-6))


def evaluate_survival_model(
    y_time: np.ndarray,
    y_event: np.ndarray,
    risk_scores: np.ndarray,
    surv_prob_fn: Any = None,
    eval_times: np.ndarray | None = None,
) -> dict[str, Any]:
    """Evaluate a model on a single sample.

    Censoring weights are estimated from the same sample being scored, which
    is the correct choice for bootstrap resampling and cross-validation folds
    where no separate reference set exists.

    Args:
        surv_prob_fn: Callable taking evaluation times and returning a
            (n_samples, n_times) survival probability matrix.
    """
    if eval_times is None:
        eval_times = evaluation_times(y_time, y_event)

    survival_probs = None
    if surv_prob_fn is not None:
        survival_probs = np.asarray(surv_prob_fn(eval_times), dtype=float)

    result = evaluate_model(
        y_time,
        y_event,
        y_time,
        y_event,
        risk_scores,
        survival_probs=survival_probs,
        eval_times=eval_times,
    )

    out: dict[str, Any] = {
        "c_index": result["c_index"],
        "c_index_se": result["c_index_se"],
        "time_dependent_auc": dict(
            zip(result["eval_times"], result["auc_at_times"], strict=True)
        ),
        "mean_auc": result["mean_auc"],
    }
    if "ibs" in result:
        out["integrated_brier_score"] = result["ibs"]
    return out


def evaluate_model(
    train_time: np.ndarray,
    train_event: np.ndarray,
    test_time: np.ndarray,
    test_event: np.ndarray,
    risk_scores: np.ndarray,
    survival_probs: np.ndarray | None = None,
    eval_times: np.ndarray | None = None,
) -> dict[str, Any]:
    """Compute the full metric set for one fitted model.

    Concordance uses the test data as given. The censoring-weighted metrics
    additionally require every test event time to fall inside the training
    follow-up, because the censoring distribution is estimated there. Test
    observations beyond the training horizon are therefore administratively
    censored at that horizon before the AUC and Brier score are computed.
    """
    train_time = np.asarray(train_time, dtype=float)
    test_time = np.asarray(test_time, dtype=float)
    train_event = np.asarray(train_event).astype(int)
    test_event = np.asarray(test_event).astype(int)

    if eval_times is None:
        eval_times = evaluation_times(test_time, test_event)
    eval_times = np.asarray(eval_times, dtype=float)

    c_index, se = concordance_index(test_time, test_event, risk_scores)
    results: dict[str, Any] = {"c_index": c_index, "c_index_se": se}

    # Administrative censoring at the training horizon.
    horizon = float(np.max(train_time))
    beyond = test_time > horizon
    ipcw_time = np.where(beyond, horizon, test_time)
    ipcw_event = np.where(beyond, 0, test_event)

    # Evaluation times must sit strictly inside the retained follow-up.
    upper = min(horizon, float(np.max(ipcw_time)))
    lower = max(float(np.min(train_time)), float(np.min(ipcw_time)))
    keep = (eval_times > lower) & (eval_times < upper)
    if not keep.any():
        raise ValueError(
            "No evaluation time lies inside both the training and test follow-up."
        )

    eval_times = eval_times[keep]
    if survival_probs is not None:
        survival_probs = np.asarray(survival_probs, dtype=float)[:, keep]

    results["eval_times"] = eval_times.tolist()
    results["n_administratively_censored"] = int(beyond.sum())

    auc, mean_auc = time_dependent_auc(
        train_time, train_event, ipcw_time, ipcw_event, risk_scores, eval_times
    )
    results["auc_at_times"] = auc.tolist()
    results["mean_auc"] = mean_auc

    if survival_probs is not None:
        results["ibs"] = integrated_brier(
            train_time,
            train_event,
            ipcw_time,
            ipcw_event,
            survival_probs,
            eval_times,
        )

    return results
