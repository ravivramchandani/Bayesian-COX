"""Paired event-stratified inference and a legacy metric bootstrap.

:func:`paired_event_stratified_bootstrap` resamples aligned outcomes and
predictions to obtain a percentile interval for a signed metric difference.
:class:`BootstrapResampler` retains an unstratified compatibility interface
that returns metric samples using the evaluated sample for censoring weights.
"""

import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass

import numpy as np

from src.evaluation.metrics import evaluate_survival_model
from src.statistics.resampling import event_stratified_indices

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PairedBootstrapResult:
    """Signed metric difference and event-stratified bootstrap uncertainty.

    ``observed_difference`` is metric A minus metric B on the original sample.
    ``bootstrap_mean_difference`` and ``bootstrap_standard_error`` are the
    mean and sample standard deviation of successful bootstrap differences.
    ``confidence_lower``/``confidence_upper`` are percentile bounds at
    ``confidence_level``. ``n_bootstraps`` records attempts and ``n_successful``
    records finite, estimable replicates.
    """

    observed_difference: float
    bootstrap_mean_difference: float
    bootstrap_standard_error: float
    confidence_lower: float
    confidence_upper: float
    confidence_level: float
    n_bootstraps: int
    n_successful: int

    def to_dict(self) -> dict[str, float | int]:
        """Return the recorded bootstrap fields as a plain dictionary.

        Returns:
            JSON-serialisable scalar values keyed by the dataclass field names.
        """
        return asdict(self)


def _validate_paired_predictions(
    predictions_a: np.ndarray, predictions_b: np.ndarray, n_samples: int
) -> tuple[np.ndarray, np.ndarray]:
    """Return aligned finite one- or two-dimensional prediction arrays."""
    a = np.asarray(predictions_a, dtype=float)
    b = np.asarray(predictions_b, dtype=float)
    if a.shape != b.shape or a.ndim not in (1, 2) or a.shape[0] != n_samples:
        raise ValueError(
            "Predictions must have identical one- or two-dimensional shapes "
            f"with first dimension {n_samples}."
        )
    if not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError("Predictions must contain only finite values.")
    return a, b


_event_stratified_sample = event_stratified_indices


def paired_event_stratified_bootstrap(
    y_time: np.ndarray,
    y_event: np.ndarray,
    predictions_a: np.ndarray,
    predictions_b: np.ndarray,
    metric: Callable[[np.ndarray, np.ndarray, np.ndarray], float],
    *,
    n_bootstraps: int = 2000,
    confidence_level: float = 0.95,
    random_state: int = 42,
) -> PairedBootstrapResult:
    """Bootstrap a paired metric difference while preserving event counts.

    Subjects are sampled with replacement separately within observed-event
    and censored strata. Outcomes and both predictions use the same sampled
    indices. Failed or non-finite replicates are skipped. No model is refitted.

    Args:
        y_time: Finite non-negative follow-up times of shape (n_subjects,),
            in the cohort's own unit (days or months).
        y_event: Matching binary event indicators (0/1).
        predictions_a: Finite predictions from model A, of shape
            (n_subjects,) or (n_subjects, n_times).
        predictions_b: Model B predictions with exactly the same shape.
        metric: Function of ``(time, event, predictions)`` returning one
            finite scalar; it may capture a fixed training censoring
            distribution. The signed effect is metric A minus metric B.
        n_bootstraps: Number of attempted replicates, at least 20.
        confidence_level: Percentile interval level, strictly between 0 and 1.
        random_state: Seed for the event-stratified resampling stream.

    Returns:
        The observed signed difference, bootstrap mean and sample standard
        deviation, percentile bounds and attempted/successful counts.

    Raises:
        ValueError: Inputs, resampling settings or the original difference
            are invalid, or fewer than two observed events are supplied.
        RuntimeError: Fewer than ``max(20, ceil(0.8 * n_bootstraps))``
            finite, estimable replicates succeed.
    """
    time = np.asarray(y_time, dtype=float)
    event = np.asarray(y_event)
    if time.ndim != 1 or event.ndim != 1 or len(time) == 0 or len(time) != len(event):
        raise ValueError("y_time and y_event must be equal-length one-dimensional arrays.")
    if not np.isfinite(time).all() or np.any(time < 0):
        raise ValueError("y_time must contain finite non-negative values.")
    if not np.isin(event, (0, 1, False, True)).all():
        raise ValueError("y_event must contain only 0/1 values.")
    event = event.astype(int)
    if np.sum(event) < 2:
        raise ValueError("At least two observed events are required for bootstrapping.")
    if n_bootstraps < 20:
        raise ValueError("n_bootstraps must be at least 20.")
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must lie strictly between 0 and 1.")
    a, b = _validate_paired_predictions(predictions_a, predictions_b, len(time))

    observed = float(metric(time, event, a) - metric(time, event, b))
    if not np.isfinite(observed):
        raise ValueError("Observed paired metric difference is not finite.")

    rng = np.random.default_rng(random_state)
    differences: list[float] = []
    for _ in range(n_bootstraps):
        indices = _event_stratified_sample(event, rng)
        try:
            difference = float(
                metric(time[indices], event[indices], a[indices])
                - metric(time[indices], event[indices], b[indices])
            )
        except (RuntimeError, ValueError, ZeroDivisionError):
            continue
        if np.isfinite(difference):
            differences.append(difference)

    required = max(20, int(np.ceil(0.8 * n_bootstraps)))
    if len(differences) < required:
        raise RuntimeError(
            f"Only {len(differences)} of {n_bootstraps} paired bootstrap "
            f"replicates were estimable; at least {required} are required."
        )
    samples = np.asarray(differences, dtype=float)
    alpha = 1 - confidence_level
    lower, upper = np.quantile(samples, [alpha / 2, 1 - alpha / 2])
    return PairedBootstrapResult(
        observed_difference=observed,
        bootstrap_mean_difference=float(np.mean(samples)),
        bootstrap_standard_error=float(np.std(samples, ddof=1)),
        confidence_lower=float(lower),
        confidence_upper=float(upper),
        confidence_level=float(confidence_level),
        n_bootstraps=n_bootstraps,
        n_successful=len(samples),
    )


class BootstrapResampler:
    """Generate legacy metric samples by unstratified subject resampling.

    This interface resamples predictions rather than refitting models. Its
    censoring weights come from each resample, not a separate training fold.

    Args:
        n_bootstraps: Number of attempted resamples.
        random_state: Seed for NumPy's legacy ``RandomState`` generator.
    """

    def __init__(self, n_bootstraps: int = 100, random_state: int = 42):
        """Store the number of bootstrap attempts and resampling seed."""
        self.n_bootstraps = n_bootstraps
        self.random_state = random_state

    def bootstrap_metrics(
        self,
        y_time: np.ndarray,
        y_event: np.ndarray,
        risk_scores: np.ndarray,
        surv_prob_fn: Callable[[np.ndarray], np.ndarray] | None = None,
        eval_times: np.ndarray | None = None,
    ) -> dict[str, list[float]]:
        """Resample subjects and evaluate their aligned survival predictions.

        The full survival matrix is computed once, then sliced with each
        resample. Samples with fewer than two events or distinct times, and
        failed evaluations, are skipped; successful counts may differ by metric.

        Args:
            y_time: Follow-up times of shape (n_subjects,) in the cohort's unit.
            y_event: Matching binary event indicators (0/1).
            risk_scores: Scores of shape (n_subjects,); larger means greater risk.
            surv_prob_fn: Optional function of evaluation times returning
                survival of shape (n_subjects, n_times).
            eval_times: Fixed times for survival evaluation; when omitted,
                each resample derives its own horizons and no survival
                matrix is evaluated.

        Returns:
            ``c_index`` samples and, when available, ``integrated_brier_score``
            and ``auc`` samples. Each AUC sample is the unweighted arithmetic
            mean of its horizon-specific areas under the receiver operating characteristic curve.
        """
        rng = np.random.RandomState(self.random_state)
        n_samples = len(y_time)

        bootstrap_c_indices = []
        bootstrap_ibs = []
        bootstrap_aucs = []

        # Precompute the full survival matrix if survival function is provided
        if surv_prob_fn is not None and eval_times is not None and len(eval_times) > 0:
            S_mat_full = surv_prob_fn(eval_times)
        else:
            S_mat_full = None

        for _ in range(self.n_bootstraps):
            # Sample indices with replacement
            boot_idx = rng.choice(n_samples, size=n_samples, replace=True)

            # Slice data
            boot_time = y_time[boot_idx]
            boot_event = y_event[boot_idx]
            boot_risk = risk_scores[boot_idx]

            # Slice survival probability matrix
            if S_mat_full is not None:
                S_mat_boot = S_mat_full[boot_idx, :]

                def boot_surv_fn(times, S_mat_b=S_mat_boot):
                    """Return the resample's precomputed survival matrix on the fixed grid."""
                    return S_mat_b
            else:
                boot_surv_fn = None

            # Check if we have at least one event in the bootstrap sample to avoid division by zero/exceptions
            if np.sum(boot_event == 1) < 2 or len(np.unique(boot_time)) < 2:
                continue

            try:
                eval_res = evaluate_survival_model(
                    y_time=boot_time,
                    y_event=boot_event,
                    risk_scores=boot_risk,
                    surv_prob_fn=boot_surv_fn,
                    eval_times=eval_times,
                )

                bootstrap_c_indices.append(eval_res["c_index"])
                if "integrated_brier_score" in eval_res:
                    bootstrap_ibs.append(eval_res["integrated_brier_score"])
                if "time_dependent_auc" in eval_res:
                    auc_vals = list(eval_res["time_dependent_auc"].values())
                    if len(auc_vals) > 0:
                        bootstrap_aucs.append(float(np.mean(auc_vals)))
            except (ValueError, ZeroDivisionError, RuntimeError) as exc:
                logger.debug(
                    "Skipping bootstrap iteration because metric evaluation failed: %s",
                    exc,
                )
                continue

        results = {
            "c_index": bootstrap_c_indices,
        }
        if bootstrap_ibs:
            results["integrated_brier_score"] = bootstrap_ibs
        if bootstrap_aucs:
            results["auc"] = bootstrap_aucs

        return results
