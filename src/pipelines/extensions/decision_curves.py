"""Decision curve analysis for the stored survival predictions (ADR-035, T-184).

Decision curve analysis asks whether acting on a model's predicted risk,
for example treating every patient whose risk of an event by the horizon
exceeds a threshold ``p_t``, does more good than harm. It compares this with
two defaults: treat everyone ("all") and treat no one ("none"). The measure
is **net benefit**:

    net benefit = (true positives - false positives * p_t / (1 - p_t)) / n

The weight ``p_t / (1 - p_t)`` is the harm of an unnecessary treatment
relative to the benefit of a necessary one, as implied by the threshold.

Survival data add censoring: some patients leave follow-up before the
horizon, so their true status is unknown. Inverse probability of censoring
weighting (IPCW) handles this. Patients whose status is known are
up-weighted by 1 / (probability of remaining uncensored), estimated from the
*training* fold with the reverse Kaplan–Meier method. Patients censored
at or before the horizon get weight 0 but stay in the denominator n.

Everything is computed from the saved out-of-fold predictions; no model is
refitted. The intervals are descriptive: they are conditional on the saved
predictions, horizons and censoring estimates.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from sksurv.nonparametric import kaplan_meier_estimator


def ipcw_state_weights(
    training_time: np.ndarray, training_event: np.ndarray,
    observed_time: np.ndarray, observed_event: np.ndarray, horizon: float,
    *, minimum_g: float = 0.1, minimum_at_risk: int = 10,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Return the IPCW weights for patients with an event and patients event-free at the horizon.

    G(t) is the training-fold probability of still being uncensored at t
    (the reverse Kaplan–Meier estimate). A validation patient with an event
    at time Y <= horizon gets event weight 1 / G(Y-), using G just before Y.
    A patient still event-free after the horizon gets event-free weight
    1 / G(horizon). A patient censored at or before the horizon gets 0 in both.

    Args:
        training_time, training_event: Training-fold follow-up, used only to
            estimate G.
        observed_time, observed_event: Validation-fold follow-up.
        horizon: Decision time point, inside the training follow-up.
        minimum_g: Smallest acceptable G, which caps the largest weight at
            1 / minimum_g.
        minimum_at_risk: Minimum number of training patients still at risk
            at the horizon.

    Returns:
        ``(event_weight, event_free_weight, metadata)``: two per-patient
        arrays and a summary that includes the weights' effective sample size.

    Raises:
        ValueError: The horizon is not supported by the training follow-up,
            G falls below ``minimum_g``, or fewer than ``minimum_at_risk``
            training patients remain at risk at the horizon.
    """
    if horizon <= 0 or horizon >= np.max(training_time):
        raise ValueError("decision horizon outside training follow-up support")
    km_t, km_g = kaplan_meier_estimator(training_event.astype(bool), training_time, reverse=True)
    def evaluate(values: np.ndarray, side: str) -> np.ndarray:
        """Look up the reverse-KM step function; ``side="left"`` gives G(t-)."""
        index = np.searchsorted(km_t, values, side=side)
        return np.r_[1.0, km_g][index]
    gh = float(evaluate(np.array([horizon]), "right")[0])
    at_risk = int(np.sum(training_time >= horizon))
    if gh < minimum_g or at_risk < minimum_at_risk:
        raise ValueError("insufficient decision-curve censoring/at-risk support")
    known_event = (observed_event == 1) & (observed_time <= horizon)
    known_free = observed_time > horizon
    g_event = evaluate(observed_time[known_event], "left")
    if np.any(g_event < minimum_g):
        raise ValueError("insufficient training censoring survival at observed event")
    u, v = np.zeros(len(observed_time)), np.zeros(len(observed_time))
    u[known_event], v[known_free] = 1 / g_event, 1 / gh
    weights = u + v
    metadata = {"horizon": horizon, "G_horizon": gh, "training_at_risk": at_risk,
                "known_events": int(known_event.sum()), "known_event_free": int(known_free.sum()),
                "early_censored": int((~(known_event | known_free)).sum()),
                "maximum_weight": float(weights.max()),
                "weight_ess": float(weights.sum()**2 / np.sum(weights**2)) if np.any(weights) else 0}
    return u, v, metadata


def decision_contributions(
    risk: np.ndarray, event_weight: np.ndarray, free_weight: np.ndarray, thresholds: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Return each patient's net-benefit contribution at each threshold.

    If treated, a patient contributes ``event_weight - p_t / (1 - p_t) *
    free_weight``. The model's strategy treats a patient when their
    predicted risk (probability of an event by the horizon) is at least the
    threshold, and contributes 0 otherwise. Averaging contributions over
    patients gives net benefit.

    Args:
        risk: Predicted absolute risk by the horizon, one value per patient,
            in [0, 1].
        event_weight, free_weight: IPCW weights from
            :func:`ipcw_state_weights`.
        thresholds: Risk thresholds strictly between 0 and 1.

    Returns:
        ``(model_contributions, treat_all_contributions)``, each of shape
        (n_patients, n_thresholds).
    """
    if not np.isfinite(risk).all() or np.any((risk < 0) | (risk > 1)):
        raise ValueError("decision risk must be an absolute probability")
    if np.any((thresholds <= 0) | (thresholds >= 1)):
        raise ValueError("ordinary decision thresholds must lie in (0,1)")
    all_actions = event_weight[:, None] - thresholds / (1 - thresholds) * free_weight[:, None]
    actions = risk[:, None] >= thresholds
    return actions * all_actions, all_actions


def patient_cluster_intervals(
    contributions: dict[str, np.ndarray], *, n_bootstraps: int, seed: int,
    cluster_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Return net benefit with bootstrap intervals, resampling whole patients.

    Every patient appears once in each of the 5 cross-validation repeats, so
    their contributions are first averaged over repeats. Patients (or
    ``cluster_ids`` groups) are then resampled with replacement. The same
    resampled patients are used for every strategy, which keeps the
    differences between strategies paired. The intervals are pointwise
    2.5%–97.5% percentiles for each threshold.

    Args:
        contributions: Strategy name to array of shape
            (n_patients, n_repeats, n_thresholds), all in the same patient
            and repeat order. When any model strategy is present, both
            ``"all"`` and ``"none"`` are required because both paired
            differences are always constructed.
        n_bootstraps: Number of bootstrap draws (at least 20).
        seed: Random seed.
        cluster_ids: Optional labels; rows with the same label are resampled
            together.

    Returns:
        Per strategy: net benefit and its interval, plus (for model
        strategies) its difference from "all" and "none", with intervals.
    """
    if not contributions or n_bootstraps < 20:
        raise ValueError("decision bootstrap requires models and at least 20 draws")
    shape = next(iter(contributions.values())).shape
    if len(shape) != 3 or any(v.shape != shape for v in contributions.values()):
        raise ValueError("decision records are not paired patients/repeats/thresholds")
    if not all(np.isfinite(v).all() for v in contributions.values()):
        raise ValueError("nonfinite decision contributions")
    rng = np.random.default_rng(seed)
    weights = np.zeros((n_bootstraps, shape[0]), dtype=float)
    labels = list(range(shape[0])) if cluster_ids is None else cluster_ids
    if len(labels) != shape[0]:
        raise ValueError("biological cluster IDs do not align with forecast rows")
    _, inverse = np.unique(labels, return_inverse=True)
    n_clusters = int(inverse.max()) + 1
    for i in range(n_bootstraps):
        multiplicity = np.bincount(rng.integers(n_clusters, size=n_clusters), minlength=n_clusters)
        row_weights = multiplicity[inverse].astype(float)
        weights[i] = row_weights / row_weights.sum()
    records: dict[str, Any] = {}
    means = {k: v.mean(axis=1) for k, v in contributions.items()}
    for name, values in means.items():
        sampled = weights @ values
        row: dict[str, Any] = {"net_benefit": values.mean(axis=0).tolist(),
                              "pointwise_lower": np.quantile(sampled, 0.025, axis=0).tolist(),
                              "pointwise_upper": np.quantile(sampled, 0.975, axis=0).tolist()}
        if name not in {"all", "none"}:
            row["differences"] = {}
            for default in ("all", "none"):
                difference = values - means[default]
                samples = weights @ difference
                row["differences"][default] = {
                    "estimate": difference.mean(axis=0).tolist(),
                    "pointwise_lower": np.quantile(samples, 0.025, axis=0).tolist(),
                    "pointwise_upper": np.quantile(samples, 0.975, axis=0).tolist(),
                }
        records[name] = row
    return {"models": records, "n_patients": shape[0], "n_biological_clusters": n_clusters, "n_repeats": shape[1],
            "n_bootstraps": n_bootstraps, "seed": seed, "resampling_unit": "paired patient IDs",
            "uncertainty": "conditional descriptive pointwise intervals; no model refitting"}
