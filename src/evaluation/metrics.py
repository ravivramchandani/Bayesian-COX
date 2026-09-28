"""Reference-matched metrics for right-censored survival predictions.

The confirmatory evaluation stage (``src/pipelines/confirmatory/evaluation.py``)
calls these functions for every fitted model and validation fold. Harrell
concordance, Uno concordance, the integrated Brier score (IBS) and
cumulative/dynamic AUC (area under the receiver operating characteristic
curve) delegate to scikit-survival, so the values match the reference
implementation (INV-004).
Evaluation horizons are derived from training outcomes only and are rejected
when the training censoring distribution cannot support them.

Inverse probability of censoring weighting (IPCW)
    A censored subject's outcome after censoring is unknown. IPCW lets the
    subjects whose outcome is known stand in for comparable subjects lost to
    censoring: each is weighted by ``1 / G(t)``, where ``G(t)`` is the
    probability of remaining uncensored beyond ``t``. ``G`` is estimated on
    the training fold by Kaplan-Meier with the roles of event and censoring
    swapped. IPCW is consistent when censoring is independent of the event
    process and the required positivity conditions hold. Estimated weights do not
    imply an exactly unbiased finite-sample estimate. Where ``G`` is small
    the weights become very large, so evaluation times need ``G(t)`` clearly
    above zero.

Harrell's C-index versus Uno's C-index
    Both estimate how often a model ranks subjects correctly. A pair is
    comparable when the subject with the shorter follow-up had an observed
    event; the pair is concordant when that subject has the higher risk
    score, and tied scores count one half. Harrell's C counts every
    comparable pair equally, so its value depends on the censoring pattern
    of the sample. Uno's C uses only pairs whose earlier time is before a
    truncation time ``tau`` and weights each pair by ``1 / G(T_i)^2`` at the
    earlier event time, which addresses censoring bias under independence
    and positivity.
    Both use risk comparisons with scikit-survival's default absolute
    tolerance of 1e-8 for tied scores.

Integrated Brier score
    The Brier score at time ``t`` is the mean, over all evaluated subjects,
    of the weighted squared difference between predicted survival
    ``S(t | x)`` and observed status: 0 for a subject whose event occurred by
    ``t`` (weight ``1 / G(T_i)``) and 1 for a subject still event-free after
    ``t`` (weight ``1 / G(t)``). Subjects censored by ``t`` have weight zero.
    The IBS is the trapezoidal integral of the Brier score over the supplied
    times, divided by the time span
    from the first to the last time. Lower is better. It reflects both
    calibration and discrimination, so it does not establish calibration by
    itself.

Cumulative/dynamic AUC
    ``AUC(t)`` is the probability that a subject whose event occurred by
    ``t`` (a cumulative case, weighted ``1 / G(T_i)``) has a higher risk
    score than a subject still event-free after ``t`` (a dynamic control).
    The summary ``mean_auc`` weights each ``AUC(t)`` by the drop in the
    evaluated sample's Kaplan-Meier survival up to that time, divided by the
    total drop, ``1 - S(t_last)``.

scikit-survival raises an error when it must evaluate ``G`` at a time beyond
the largest training time while ``G`` is still positive there. These
functions convert that error to :class:`UnsupportedCensoringError`.
They never alter the outcomes they are given; the confirmatory evaluation stage censors
validation follow-up after the last horizon before calling the IPCW metrics.
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
    """Return the structured (event, time) array that scikit-survival expects."""
    return Surv.from_arrays(
        event=np.asarray(event).astype(bool), time=np.asarray(time, dtype=float)
    )


def _validate_survival(
    time: np.ndarray, event: np.ndarray, *, name: str
) -> tuple[np.ndarray, np.ndarray]:
    """Return float times and boolean events, or raise ``ValueError`` if invalid."""
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
    """Return a finite one-dimensional score array of length ``n_samples``."""
    array = np.asarray(estimate, dtype=float)
    if array.ndim != 1 or len(array) != n_samples:
        raise ValueError(f"{name} must be one-dimensional with length {n_samples}.")
    if not np.isfinite(array).all():
        raise ValueError(f"{name} must contain only finite values.")
    return array


def _validate_times(times: Sequence[float] | np.ndarray) -> np.ndarray:
    """Return non-empty, finite, non-negative, strictly increasing evaluation times."""
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
    """Estimate training censoring survival ``G(t)`` at requested times.

    ``G`` is the reverse Kaplan-Meier estimate of remaining uncensored,
    fitted on training outcomes with censoring treated as the event.

    Args:
        train_time: Follow-up times of shape (n_train,), in the cohort's unit.
        train_event: Matching binary event indicators (0/1).
        times: Non-empty finite, non-negative, strictly increasing times
            of shape (n_times,), in the same unit as ``train_time``.

    Returns:
        Censoring probabilities of shape (n_times,), in time order.

    Raises:
        ValueError: Outcomes or evaluation times are invalid.
        UnsupportedCensoringError: A requested time lies beyond the last
            training time while ``G`` remains positive there.
    """
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
    """Require training censoring support at every evaluation horizon.

    The threshold can enforce stricter positivity than the mathematical
    minimum. Automatic horizon selection uses 0.1; explicit metric calls
    otherwise require only ``G(t) > 0``.

    Args:
        train_time: Follow-up times of shape (n_train,), in the cohort's unit.
        train_event: Matching binary event indicators (0/1).
        eval_times: Non-empty finite, non-negative, strictly increasing
            times of shape (n_times,), in the same unit as training times.
        min_censoring_survival: Required lower bound for ``G(t)``, in [0, 1).

    Returns:
        Validated evaluation times as a one-dimensional float array.

    Raises:
        ValueError: Outcomes, threshold or times are invalid.
        UnsupportedCensoringError: ``G(t)`` is at or below the threshold
            or cannot be evaluated at a requested time.
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
    """Choose horizons exclusively from observed training event times.

    Quantiles use NumPy's default linear interpolation, so validation
    outcomes cannot influence a horizon. Duplicate horizon values are
    removed; each retained time must have training censoring survival
    above ``min_censoring_survival``.

    Args:
        train_time: Follow-up times of shape (n_train,), in the cohort's unit.
        train_event: Matching binary event indicators (0/1).
        quantiles: Non-empty, finite, strictly increasing probabilities
            strictly between 0 and 1; defaults to the event-time quartiles.
        min_censoring_survival: Required lower bound for ``G(t)``, in [0, 1).

    Returns:
        At least two distinct increasing horizons in the training times' unit.

    Raises:
        ValueError: Inputs are invalid, fewer than two training events
            exist, or fewer than two distinct horizons remain.
        UnsupportedCensoringError: A horizon lacks censoring support.
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
    """Select equally spaced training event-time quantiles from 0.25 to 0.75.

    This compatibility interface requires training outcomes. New callers
    can specify probabilities directly with :func:`training_event_time_horizons`.

    Args:
        time: Training follow-up times of shape (n_train,), in the cohort's unit.
        event: Matching binary event indicators (0/1).
        n_times: Number of quantiles, at least two.
        min_censoring_survival: Required lower bound for ``G(t)``, in [0, 1).

    Returns:
        Distinct increasing horizons, with duplicate quantile values removed.

    Raises:
        ValueError: Inputs are invalid or fewer than two distinct horizons remain.
        UnsupportedCensoringError: A horizon lacks censoring support.
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
    """Return Harrell's concordance index from scikit-survival (INV-004).

    No censoring weights are used. A value of 0.5 indicates chance ranking
    and 1 perfect concordance. Risk ties use the reference tolerance 1e-8.

    Args:
        y_time: Follow-up times of shape (n_subjects,), in the cohort's unit.
        y_event: Matching binary event indicators (0/1).
        risk_scores: Finite scores of shape (n_subjects,); larger means
            greater risk. The score scale determines the absolute tie tolerance.

    Returns:
        Fraction of concordant comparable pairs, with risk ties counting one half.

    Raises:
        ValueError: Outcomes or scores are invalid, or concordance is
            undefined for the supplied sample.
    """
    time, event = _validate_survival(y_time, y_event, name="Evaluation")
    risk = _validate_estimate(risk_scores, len(time), name="risk_scores")
    result = concordance_index_censored(event, time, risk)
    return float(result[0])


def concordance_index(
    y_time: np.ndarray, y_event: np.ndarray, risk_scores: np.ndarray
) -> tuple[float, None]:
    """Return the compatibility Harrell concordance result.

    The former binomial uncertainty approximation treated dependent
    subject pairs as independent. Its value is now ``None``; uncertainty
    requires a subject bootstrap or repeated-cross-validation effect interval.

    Args:
        y_time: Follow-up times of shape (n_subjects,), in the cohort's unit.
        y_event: Matching binary event indicators (0/1).
        risk_scores: Finite scores of shape (n_subjects,); larger means greater risk.

    Returns:
        ``(Harrell concordance, None)``.

    Raises:
        ValueError: Inputs are invalid or concordance cannot be estimated.
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
    """Return Uno's IPCW concordance at truncation time ``tau``.

    Only comparable pairs whose earlier event time is before ``tau``
    count, weighted by ``1 / G(T_i)^2`` from the training censoring
    estimate. The reference risk-tie tolerance is 1e-8.

    Args:
        train_time: Training times of shape (n_train,), in the cohort's unit.
        train_event: Matching binary training event indicators (0/1).
        test_time: Evaluated times of shape (n_test,), in the same unit.
        test_event: Matching binary evaluated event indicators (0/1).
        risk_scores: Finite scores of shape (n_test,); larger means greater risk.
        tau: Non-negative truncation time in the same unit; the confirmatory
            pipeline uses its last horizon.
        min_censoring_survival: Required lower bound for ``G(tau)``, in [0, 1).

    Returns:
        The IPCW-weighted fraction of concordant comparable pairs.

    Raises:
        ValueError: Outcomes, scores, ``tau`` or the support threshold are invalid.
        UnsupportedCensoringError: Training support is insufficient, or
            the reference calculation raises a ``ValueError``.
    """
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
    """Return the reference IPCW integrated Brier score over supplied times.

    Args:
        train_time: Training times of shape (n_train,), in the cohort's unit.
        train_event: Matching binary training event indicators (0/1).
        test_time: Evaluated times of shape (n_test,), in the same unit.
        test_event: Matching binary evaluated event indicators (0/1).
        survival_probs: Finite probabilities in [0, 1], of shape
            (n_test, n_times), with columns aligned to ``eval_times``.
        eval_times: At least two strictly increasing times with ``G(t)>0``,
            satisfying ``min(test_time) <= t < max(test_time)``. Times use
            the same unit as the follow-up arrays.

    Returns:
        Time-normalised integrated prediction error; lower is better.

    Raises:
        ValueError: Outcomes, times or prediction probabilities are invalid.
        UnsupportedCensoringError: Support is insufficient, or the
            reference calculation raises a ``ValueError``.
    """
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
    """Return cumulative/dynamic areas under the curve at supported horizons.

    Args:
        train_time: Training times of shape (n_train,), in the cohort's unit.
        train_event: Matching binary training event indicators (0/1).
        test_time: Evaluated times of shape (n_test,), in the same unit.
        test_event: Matching binary evaluated event indicators (0/1).
        risk_scores: Finite time-constant scores of shape (n_test,);
            larger means greater risk. Risk ties use tolerance 1e-8.
        eval_times: Strictly increasing finite non-negative times of shape
            (n_times,), with ``G(t)>0`` and ``min(test_time) <= t < max(test_time)``.
            Times use the same unit as the follow-up arrays.

    Returns:
        ``(auc, mean_auc)``: an array of shape (n_times,) and the
        Kaplan-Meier-weighted summary described in the module docstring.

    Raises:
        ValueError: Outcomes, scores or evaluation times are invalid.
        UnsupportedCensoringError: Support is insufficient, or the
            reference calculation raises a ``ValueError``.
    """
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

    This compatibility function estimates censoring, and by default the
    evaluation times, from the evaluated sample itself. Confirmatory
    train/test evaluation should call :func:`evaluate_model`.

    Args:
        y_time: Evaluated times of shape (n_subjects,), in the cohort's unit.
        y_event: Matching binary event indicators (0/1).
        risk_scores: Finite scores of shape (n_subjects,); larger means greater risk.
        surv_prob_fn: Optional function mapping ``eval_times`` to predicted
            survival of shape (n_subjects, n_times); enables the IBS.
        eval_times: Increasing times in the same unit as ``y_time``;
            ``None`` uses :func:`evaluation_times`.

    Returns:
        ``c_index`` (Harrell), ``c_index_se`` (always ``None``),
        ``uno_c_index``, ``time_dependent_auc`` (time to AUC), ``mean_auc``
        and, when ``surv_prob_fn`` is given, ``integrated_brier_score``.

    Raises:
        ValueError: Inputs or predictions are invalid.
        UnsupportedCensoringError: The metric calculation lacks support.
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
    """Compute the standard metric set without altering observed outcomes.

    Horizons are derived from training events when omitted. Unsupported IPCW
    support raises :class:`UnsupportedCensoringError`; this function never
    administratively censors evaluation outcomes on the caller's behalf.
    Uno's C uses the last evaluation time as ``tau``, and the IBS, when
    ``survival_probs`` is given, is integrated over the same evaluation
    times. The confirmatory evaluation stage calls the individual metrics
    instead, with a separate 25-point IBS grid.

    Args:
        train_time: Training times of shape (n_train,), in the cohort's unit.
        train_event: Matching binary training event indicators (0/1).
        test_time: Evaluated times of shape (n_test,), in the same unit.
        test_event: Matching binary evaluated event indicators (0/1).
        risk_scores: Finite scores of shape (n_test,); larger means greater risk.
        survival_probs: Optional survival matrix of shape (n_test, n_times),
            with columns aligned to the evaluation horizons; enables the IBS.
        eval_times: Increasing evaluation times; ``None`` selects the
            supported training event-time quartiles.

    Returns:
        ``c_index`` (Harrell), ``c_index_se`` (always ``None``),
        ``uno_c_index``, ``uno_tau``, ``eval_times``, ``auc_at_times``,
        ``mean_auc`` and, when ``survival_probs`` is given, ``ibs``.

    Raises:
        ValueError: Inputs or predictions are invalid.
        UnsupportedCensoringError: A reference metric lacks support.
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
