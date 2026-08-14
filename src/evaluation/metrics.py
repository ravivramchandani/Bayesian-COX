"""Reference-matched metrics for right-censored survival predictions.

Harrell concordance, Uno IPCW concordance, integrated Brier score, and
cumulative/dynamic AUC delegate to scikit-survival. Evaluation horizons are
derived from training outcomes only and are rejected when the training
censoring distribution cannot support them.
"""

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
from sksurv.metrics import (
    concordance_index_censored,
    concordance_index_ipcw,
    cumulative_dynamic_auc,
    integrated_brier_score,
)
from sksurv.nonparametric import CensoringDistributionEstimator
from sksurv.util import Surv


class UnsupportedCensoringError(ValueError):
    """Raised when IPCW quantities are requested beyond observed support."""


def _as_structured(time: np.ndarray, event: np.ndarray) -> np.ndarray:
    return Surv.from_arrays(
        event=np.asarray(event).astype(bool), time=np.asarray(time, dtype=float)
    )


def _validate_survival(
    time: np.ndarray, event: np.ndarray, *, name: str
) -> tuple[np.ndarray, np.ndarray]:
    time_array = np.asarray(time, dtype=float)
    event_array = np.asarray(event)
    if time_array.ndim != 1 or event_array.ndim != 1:
        raise ValueError(f"{name} time and event must be one-dimensional.")
    if len(time_array) != len(event_array) or len(time_array) == 0:
        raise ValueError(f"{name} time and event must have the same non-zero length.")
    if not np.isfinite(time_array).all() or np.any(time_array < 0):
        raise ValueError(f"{name} times must be finite and non-negative.")
    if not np.isin(event_array, (0, 1, False, True)).all():
        raise ValueError(f"{name} event must contain only 0/1 values.")
    return time_array, event_array.astype(bool)


def _validate_estimate(estimate: np.ndarray, n_samples: int, *, name: str) -> np.ndarray:
    array = np.asarray(estimate, dtype=float)
    if array.ndim != 1 or len(array) != n_samples:
        raise ValueError(f"{name} must be one-dimensional with length {n_samples}.")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values.")
    return array


def _validate_times(times: Sequence[float] | np.ndarray) -> np.ndarray:
    array = np.asarray(times, dtype=float)
    if array.ndim != 1 or len(array) == 0:
        raise ValueError("Evaluation times must be a non-empty one-dimensional array.")
    if not np.isfinite(array).all() or np.any(array < 0):
        raise ValueError("Evaluation times must be finite and non-negative.")
    if np.any(np.diff(array) <= 0):
        raise ValueError("Evaluation times must be strictly increasing.")
    return array


def censoring_survival_at(
    train_time: np.ndarray,
    train_event: np.ndarray,
    times: Sequence[float] | np.ndarray,
) -> np.ndarray:
    """Estimate training censoring survival ``G(t)`` at requested times."""
    time, event = _validate_survival(train_time, train_event, name="Training")
    eval_times = _validate_times(times)
    estimator = CensoringDistributionEstimator().fit(_as_structured(time, event))
    try:
        values = np.asarray(estimator.predict_proba(eval_times), dtype=float)
    except ValueError as exc:
        raise UnsupportedCensoringError(
            "Evaluation time lies beyond the support of the training censoring "
            "distribution. Choose an earlier training-derived horizon."
        ) from exc
    return values


def validate_ipcw_horizons(
    train_time: np.ndarray,
    train_event: np.ndarray,
    eval_times: Sequence[float] | np.ndarray,
    *,
    min_censoring_survival: float = 0.0,
) -> np.ndarray:
    """Validate that training censoring weights exist at every horizon.

    ``min_censoring_survival`` can enforce a stricter positivity threshold than
    the mathematical minimum. A value of 0.1 is used when horizons are chosen
    automatically; explicit metric calls default to requiring only ``G(t)>0``.
    """
    if not 0 <= min_censoring_survival < 1:
        raise ValueError("min_censoring_survival must lie in [0, 1).")
    times = _validate_times(eval_times)
    censoring_survival = censoring_survival_at(train_time, train_event, times)
    unsupported = censoring_survival <= min_censoring_survival
    if unsupported.any():
        bad = ", ".join(f"{value:g}" for value in times[unsupported])
        raise UnsupportedCensoringError(
            f"Training censoring survival is not above {min_censoring_survival:g} "
            f"at evaluation time(s) {bad}."
        )
    return times


def training_event_time_horizons(
    train_time: np.ndarray,
    train_event: np.ndarray,
    *,
    quantiles: Sequence[float] = (0.25, 0.5, 0.75),
    min_censoring_survival: float = 0.1,
) -> np.ndarray:
    """Choose evaluation horizons exclusively from training event times.

    Quantiles are evaluated on observed event times. Duplicate quantiles are
    removed, and every retained horizon must have adequate support under the
    training censoring distribution.
    """
    time, event = _validate_survival(train_time, train_event, name="Training")
    probabilities = np.asarray(quantiles, dtype=float)
    if probabilities.ndim != 1 or len(probabilities) == 0:
        raise ValueError("quantiles must be a non-empty one-dimensional sequence.")
    if not np.isfinite(probabilities).all() or np.any(
        (probabilities <= 0) | (probabilities >= 1)
    ):
        raise ValueError("quantiles must lie strictly between 0 and 1.")
    if np.any(np.diff(probabilities) <= 0):
        raise ValueError("quantiles must be strictly increasing.")

    event_times = time[event]
    if len(event_times) < 2:
        raise ValueError("At least two observed training events are required.")
    horizons = np.unique(np.quantile(event_times, probabilities))
    if len(horizons) < 2:
        raise ValueError("Training event times do not define at least two horizons.")
    return validate_ipcw_horizons(
        time,
        event,
        horizons,
        min_censoring_survival=min_censoring_survival,
    )


def evaluation_times(
    time: np.ndarray,
    event: np.ndarray,
    n_times: int = 3,
    *,
    min_censoring_survival: float = 0.1,
) -> np.ndarray:
    """Backward-compatible training-only horizon selector.

    Callers must pass the training outcomes. New code should prefer
    :func:`training_event_time_horizons` with explicit quantiles.
    """
    if n_times < 2:
        raise ValueError("n_times must be at least 2.")
    quantiles = np.linspace(0.25, 0.75, n_times)
    return training_event_time_horizons(
        time,
        event,
        quantiles=quantiles,
        min_censoring_survival=min_censoring_survival,
    )


def harrell_c_index(
    y_time: np.ndarray, y_event: np.ndarray, risk_scores: np.ndarray
) -> float:
    """Harrell concordance, exactly as computed by scikit-survival."""
    time, event = _validate_survival(y_time, y_event, name="Evaluation")
    risk = _validate_estimate(risk_scores, len(time), name="risk_scores")
    result = concordance_index_censored(event, time, risk)
    return float(result[0])


def concordance_index(
    y_time: np.ndarray, y_event: np.ndarray, risk_scores: np.ndarray
) -> tuple[float, None]:
    """Backward-compatible Harrell concordance interface.

    The second element used to contain a binomial pair-count approximation that
    treats dependent subject pairs as independent. It is now ``None``; use a
    subject-level bootstrap or repeated-CV effect interval for uncertainty.
    """
    return harrell_c_index(y_time, y_event, risk_scores), None


def uno_c_index(
    train_time: np.ndarray,
    train_event: np.ndarray,
    test_time: np.ndarray,
    test_event: np.ndarray,
    risk_scores: np.ndarray,
    *,
    tau: float,
    min_censoring_survival: float = 0.0,
) -> float:
    """Uno IPCW concordance at a training-supported truncation time ``tau``."""
    train_t, train_e = _validate_survival(train_time, train_event, name="Training")
    test_t, test_e = _validate_survival(test_time, test_event, name="Evaluation")
    risk = _validate_estimate(risk_scores, len(test_t), name="risk_scores")
    tau_array = validate_ipcw_horizons(
        train_t,
        train_e,
        [tau],
        min_censoring_survival=min_censoring_survival,
    )
    try:
        result = concordance_index_ipcw(
            _as_structured(train_t, train_e),
            _as_structured(test_t, test_e),
            risk,
            tau=float(tau_array[0]),
        )
    except ValueError as exc:
        raise UnsupportedCensoringError(
            "Uno concordance could not be estimated with the supplied training "
            "censoring distribution and tau."
        ) from exc
    return float(result[0])


def integrated_brier(
    train_time: np.ndarray,
    train_event: np.ndarray,
    test_time: np.ndarray,
    test_event: np.ndarray,
    survival_probs: np.ndarray,
    eval_times: np.ndarray,
) -> float:
    """Reference IPCW integrated Brier score over supported horizons."""
    train_t, train_e = _validate_survival(train_time, train_event, name="Training")
    test_t, test_e = _validate_survival(test_time, test_event, name="Evaluation")
    times = validate_ipcw_horizons(train_t, train_e, eval_times)
    predictions = np.asarray(survival_probs, dtype=float)
    if predictions.shape != (len(test_t), len(times)):
        raise ValueError(
            "survival_probs must have shape "
            f"({len(test_t)}, {len(times)}), got {predictions.shape}."
        )
    if not np.isfinite(predictions).all() or np.any(
        (predictions < 0) | (predictions > 1)
    ):
        raise ValueError("survival_probs must be finite probabilities in [0, 1].")
    try:
        return float(
            integrated_brier_score(
                _as_structured(train_t, train_e),
                _as_structured(test_t, test_e),
                predictions,
                times,
            )
        )
    except ValueError as exc:
        raise UnsupportedCensoringError(
            "Integrated Brier score is unsupported for the supplied follow-up. "
            "Evaluation observations and horizons must be covered by the "
            "training censoring distribution."
        ) from exc


def time_dependent_auc(
    train_time: np.ndarray,
    train_event: np.ndarray,
    test_time: np.ndarray,
    test_event: np.ndarray,
    risk_scores: np.ndarray,
    eval_times: np.ndarray,
) -> tuple[np.ndarray, float]:
    """Reference cumulative/dynamic AUC at supported evaluation horizons."""
    train_t, train_e = _validate_survival(train_time, train_event, name="Training")
    test_t, test_e = _validate_survival(test_time, test_event, name="Evaluation")
    risk = _validate_estimate(risk_scores, len(test_t), name="risk_scores")
    times = validate_ipcw_horizons(train_t, train_e, eval_times)
    try:
        auc, mean_auc = cumulative_dynamic_auc(
            _as_structured(train_t, train_e),
            _as_structured(test_t, test_e),
            risk,
            times,
        )
    except ValueError as exc:
        raise UnsupportedCensoringError(
            "Cumulative/dynamic AUC is unsupported for the supplied follow-up. "
            "Choose earlier training-derived horizons."
        ) from exc
    return np.asarray(auc, dtype=float), float(mean_auc)


def evaluate_survival_model(
    y_time: np.ndarray,
    y_event: np.ndarray,
    risk_scores: np.ndarray,
    surv_prob_fn: Callable[[np.ndarray], np.ndarray] | None = None,
    eval_times: np.ndarray | None = None,
) -> dict[str, Any]:
    """Evaluate resampled predictions when no separate training sample exists.

    This compatibility function estimates censoring from the evaluated sample.
    Confirmatory train/test evaluation should call :func:`evaluate_model`.
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
        "c_index_se": None,
        "uno_c_index": result["uno_c_index"],
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
    """Compute confirmatory metrics without altering observed outcomes.

    Horizons are derived from training events when omitted. Unsupported IPCW
    support raises :class:`UnsupportedCensoringError`; this function never
    administratively censors evaluation outcomes on the caller's behalf.
    """
    train_t, train_e = _validate_survival(train_time, train_event, name="Training")
    test_t, test_e = _validate_survival(test_time, test_event, name="Evaluation")
    risk = _validate_estimate(risk_scores, len(test_t), name="risk_scores")
    times = (
        training_event_time_horizons(train_t, train_e)
        if eval_times is None
        else validate_ipcw_horizons(train_t, train_e, eval_times)
    )

    c_index = harrell_c_index(test_t, test_e, risk)
    tau = float(times[-1])
    results: dict[str, Any] = {
        "c_index": c_index,
        "c_index_se": None,
        "uno_c_index": uno_c_index(
            train_t, train_e, test_t, test_e, risk, tau=tau
        ),
        "uno_tau": tau,
        "eval_times": times.tolist(),
    }

    auc, mean_auc = time_dependent_auc(
        train_t, train_e, test_t, test_e, risk, times
    )
    results["auc_at_times"] = auc.tolist()
    results["mean_auc"] = mean_auc

    if survival_probs is not None:
        results["ibs"] = integrated_brier(
            train_t,
            train_e,
            test_t,
            test_e,
            survival_probs,
            times,
        )
    return results
