"""Paired event-stratified inference and the legacy metric bootstrap interface."""

import logging
from collections.abc import Callable
from dataclasses import asdict, dataclass

import numpy as np

from src.evaluation.metrics import evaluate_survival_model
from src.statistics.resampling import event_stratified_indices

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PairedBootstrapResult:
    """Paired metric difference from an event-stratified subject bootstrap."""

    observed_difference: float
    bootstrap_mean_difference: float
    bootstrap_standard_error: float
    confidence_lower: float
    confidence_upper: float
    confidence_level: float
    n_bootstraps: int
    n_successful: int

    def to_dict(self) -> dict[str, float | int]:
        """Return a JSON-serialisable representation."""
        return asdict(self)


def _validate_paired_predictions(
    predictions_a: np.ndarray, predictions_b: np.ndarray, n_samples: int
) -> tuple[np.ndarray, np.ndarray]:
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

    Subjects are sampled with replacement separately within observed-event and
    censored strata. Outcomes and both models' predictions use the same sampled
    indices. ``metric`` receives ``(time, event, predictions)`` and may capture
    a fixed training censoring distribution in a closure.
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
    """Performs repeated bootstrap resampling to estimate uncertainty in survival metrics."""

    def __init__(self, n_bootstraps: int = 100, random_state: int = 42):
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
        """
        Samples with replacement and evaluates metrics repeatedly.
        Returns a dict mapping metric names to lists of bootstrap scores.
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
