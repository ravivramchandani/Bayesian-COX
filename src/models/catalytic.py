"""Cox catalytic kernels and the authors' weighted-mixture point estimator."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp

from src.models.base import BaseSurvivalModel


@dataclass(frozen=True)
class CatalyticData:
    """Explicit synthetic prior data, never evaluation observations."""

    design: np.ndarray
    time: np.ndarray
    hazard: float

    def __post_init__(self) -> None:
        x, t = self.design, self.time
        if x.ndim != 2 or len(x) != len(t) or x.shape[1] < 1:
            raise ValueError("invalid synthetic prior-data dimensions")
        if not np.isfinite(x).all() or not np.isfinite(t).all() or np.any(t <= 0):
            raise ValueError("synthetic prior data must be finite with positive times")
        if not np.isfinite(self.hazard) or self.hazard <= 0:
            raise ValueError("synthetic reference hazard must be positive")
        if np.linalg.matrix_rank(x) != x.shape[1]:
            raise ValueError("synthetic design is not full column rank")


def catalytic_kernel(beta: np.ndarray, data: CatalyticData) -> tuple[float, np.ndarray]:
    """Return mean synthetic exponential log likelihood and its gradient.

    The beta-independent log(hazard) is omitted in both this kernel and kappa.
    No linear-predictor clipping changes the density.
    """
    eta = data.design @ np.asarray(beta, dtype=float)
    with np.errstate(over="ignore"):
        cumulative = data.hazard * data.time * np.exp(eta)
    return float(np.mean(eta - cumulative)), data.design.T @ (1 - cumulative) / len(eta)


def catalytic_kappa(data: CatalyticData) -> tuple[float, np.ndarray]:
    """Compute the concave kernel's supremum with a checked finite optimum."""
    result = minimize(
        lambda b: tuple(-v for v in catalytic_kernel(b, data)),
        np.zeros(data.design.shape[1]), jac=True, method="L-BFGS-B",
        options={"gtol": 1e-8, "ftol": 1e-14, "maxiter": 5000, "maxls": 50},
    )
    value, gradient = catalytic_kernel(result.x, data)
    if not result.success or not np.isfinite(value) or np.max(np.abs(gradient)) > 1e-6:
        raise RuntimeError(f"catalytic kappa optimizer failed: {result.message}")
    return value, result.x


def adaptive_log_kernel(
    beta: np.ndarray, tau: float, data: CatalyticData, kappa: float,
    *, alpha: float = 2, gamma: float = 1,
) -> float:
    """Evaluate the joint adaptive prior, including its tau normalization."""
    if tau <= 0 or alpha <= 0 or gamma <= 0:
        return -np.inf
    q, _ = catalytic_kernel(beta, data)
    return float((data.design.shape[1] + alpha - 1) * np.log(tau)
                 + tau * (q - kappa - 1 / gamma))


def weighted_breslow_objective(
    beta: np.ndarray, design: np.ndarray, time: np.ndarray,
    event: np.ndarray, weight: np.ndarray,
) -> tuple[float, np.ndarray]:
    """Return weighted Cox Breslow log partial likelihood and score.

    Case weights enter both event counts and risk-set denominators, including
    at tied events. Sorting is stable and ties share one risk set.
    """
    order = np.argsort(time, kind="stable")
    x, t, d, w = design[order], time[order], event[order], weight[order]
    eta = x @ beta
    shift = float(np.max(eta))
    risk = w * np.exp(eta - shift)
    denominator = np.cumsum(risk[::-1])[::-1]
    numerator = np.cumsum((risk[:, None] * x)[::-1], axis=0)[::-1]
    starts = np.r_[0, np.flatnonzero(np.diff(t)) + 1]
    counts = np.add.reduceat(w * d, starts)
    used = counts > 0
    ix, counts = starts[used], counts[used]
    if np.any(denominator[ix] <= 0):
        raise FloatingPointError("weighted risk denominator underflow")
    value = np.sum(w * d * eta) - np.sum(counts * (np.log(denominator[ix]) + shift))
    score = x.T @ (w * d) - np.sum(counts[:, None] * numerator[ix] / denominator[ix, None], axis=0)
    return float(value), score


class WeightedMixtureCox(BaseSurvivalModel):
    """Breslow Cox fit on observed and synthetic rows with weights 1 and tau/M.

    Absolute survival uses a weighted merged-data Breslow baseline, an
    explicit extension to the authors' linear-risk prediction interface.
    """

    def __init__(self, synthetic: CatalyticData, tau: float, time_scale: float = 1) -> None:
        if not np.isfinite(tau) or tau <= 0:
            raise ValueError("mixture tau must be positive")
        if not np.isfinite(time_scale) or time_scale <= 0:
            raise ValueError("mixture time scale must be positive")
        self.synthetic, self.tau, self.time_scale = synthetic, float(tau), float(time_scale)
        self.details: dict = {}

    def fit(self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray) -> WeightedMixtureCox:
        """Fit without a penalty or a fabricated MCMC diagnostic."""
        x = np.vstack([X.to_numpy(float), self.synthetic.design])
        t = np.r_[y_time / self.time_scale, self.synthetic.time]
        d = np.r_[y_event, np.ones(len(self.synthetic.time), dtype=int)]
        w = np.r_[np.ones(len(X)), np.full(len(self.synthetic.time), self.tau / len(self.synthetic.time))]
        result = minimize(
            lambda b: tuple(-v for v in weighted_breslow_objective(b, x, t, d, w)),
            np.zeros(x.shape[1]), jac=True, method="L-BFGS-B",
            options={"gtol": 1e-7, "ftol": 1e-14, "maxiter": 5000, "maxls": 50},
        )
        value, score = weighted_breslow_objective(result.x, x, t, d, w)
        if not result.success or not np.isfinite(result.x).all() or np.max(np.abs(score)) > 1e-4:
            raise RuntimeError(f"weighted mixture optimizer failed: {result.message}")
        self.beta = result.x
        self.event_times = np.unique(t[d == 1])
        eta = x @ self.beta
        self.baseline = np.cumsum([
            np.sum(w[(t == u) & (d == 1)]) * np.exp(-logsumexp(eta[t >= u], b=w[t >= u]))
            for u in self.event_times
        ])
        self.details = {"tau": self.tau, "log_partial_likelihood": value,
                        "max_absolute_score": float(np.max(np.abs(score))),
                        "optimizer_success": bool(result.success), "iterations": int(result.nit),
                        "baseline": "weighted merged-data Breslow", "ties": "breslow"}
        return self

    def predict_risk(self, X: pd.DataFrame) -> np.ndarray:
        """Return the linear log-hazard score."""
        return X.to_numpy(float) @ self.beta

    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Evaluate the fitted weighted Breslow survival step function."""
        index = np.searchsorted(self.event_times, eval_times / self.time_scale, side="right")
        h = np.r_[0, self.baseline][index]
        with np.errstate(over="ignore"):
            return np.exp(-np.exp(self.predict_risk(X))[:, None] * h)
