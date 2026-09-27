"""IPCW decision curves for saved fold-specific survival forecasts."""

from __future__ import annotations

from typing import Any

import numpy as np
from sksurv.nonparametric import kaplan_meier_estimator


def ipcw_state_weights(
    training_time: np.ndarray, training_event: np.ndarray,
    observed_time: np.ndarray, observed_event: np.ndarray, horizon: float,
    *, minimum_g: float = 0.1, minimum_at_risk: int = 10,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    """Estimate event/event-free utility weights using training reverse KM.

    Event weights use G(Y-); event-free weights use G(h). Reverse KM applies
    the censoring/event tie convention from the reference survival library.
    Early-censored patients contribute zero and remain in the denominator.
    """
    if horizon <= 0 or horizon >= np.max(training_time):
        raise ValueError("decision horizon outside training follow-up support")
    km_t, km_g = kaplan_meier_estimator(training_event.astype(bool), training_time, reverse=True)
    def evaluate(values: np.ndarray, side: str) -> np.ndarray:
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
    """Threshold absolute risk before computing patient utility contributions."""
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
    """Bootstrap matched patients, after averaging all their repeat utilities.

    Each input is patient × repeat × threshold in identical ID/repeat order.
    The same patient draw is used for every model/default strategy. Intervals
    are conditional on saved forecasts, horizons and censoring estimates.
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
