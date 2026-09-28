"""Building blocks of the Cox catalytic prior (Li and Huang, 2026, ADR-038).

A catalytic prior expresses prior belief through *synthetic data* instead of
a formula on the coefficients. Synthetic patients are generated from a very
simple model: resampled covariates and exponential survival times with one
constant hazard. Their likelihood, down-weighted to a total weight ``tau``,
then acts as the prior on the Cox coefficients ``beta``. With little real
data, the fit is pulled towards the simple model; with more real data, the
synthetic rows matter less and less.

This module provides:

- ``CatalyticData``: the synthetic rows for one training fold;
- ``catalytic_kernel``: the average synthetic log-likelihood that defines
  the prior density (Li and Huang, Eq. 7);
- ``catalytic_kappa``: its maximum, needed by the adaptive-tau prior;
- ``adaptive_log_kernel``: the joint prior on (tau, beta) (their Eq. 10–11);
- ``WeightedMixtureCox``: the authors' weighted mixture estimator, a Cox fit
  on the real rows (weight 1) plus the synthetic rows (weight tau / M each).

Reference: Li W., Huang D. (2026) Bayesian inference for Cox regression
models using catalytic prior distributions. Biometrics 82(1), ujag004,
doi:10.1093/biomtc/ujag004.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp

from src.models.base import BaseSurvivalModel


@dataclass(frozen=True)
class CatalyticData:
    """Synthetic prior data for one training fold; never used for evaluation.

    Attributes:
        design: Synthetic covariates, shape (M, p), on the same preprocessed
            scale as the real training design.
        time: Synthetic uncensored survival times, shape (M,), on the model's
            scaled time axis.
        hazard: The constant "surrogate" baseline hazard h0+ used to write the
            synthetic exponential likelihood (fitted to the training fold).
    """

    design: np.ndarray
    time: np.ndarray
    hazard: float

    def __post_init__(self) -> None:
        """Reject shapes and values that would make the prior improper or undefined.

        A full-column-rank synthetic design is what makes the catalytic prior
        proper (integrable) in Li and Huang's Theorem 2.
        """
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
    """Return the average synthetic log-likelihood and its gradient in ``beta``.

    Each synthetic row is an uncensored exponential observation with hazard
    ``h0+ * exp(x beta)``, so its log-likelihood is
    ``x beta + log(h0+) - h0+ * t * exp(x beta)``. The mean over the M rows,
    ``q(beta)``, is the kernel: the catalytic prior density is proportional to
    ``exp(tau * q(beta))``. The constant ``log(h0+)`` does not depend on
    ``beta`` and is left out here and in ``catalytic_kappa`` alike.

    Args:
        beta: Coefficient vector, shape (p,).
        data: The synthetic prior data.

    Returns:
        ``(q, gradient)``: the mean log-likelihood and its gradient, shape (p,).
    """
    eta = data.design @ np.asarray(beta, dtype=float)
    with np.errstate(over="ignore"):
        cumulative = data.hazard * data.time * np.exp(eta)
    return float(np.mean(eta - cumulative)), data.design.T @ (1 - cumulative) / len(eta)


def catalytic_kappa(data: CatalyticData) -> tuple[float, np.ndarray]:
    """Return the maximum of the kernel and the ``beta`` that attains it.

    ``kappa = max_beta q(beta)`` appears in the adaptive prior's
    normalisation (Li and Huang, Eq. 11). The kernel is concave, so a
    gradient optimiser finds the global maximum; the result is rejected
    unless the optimiser reports success and the gradient is essentially zero.

    Returns:
        ``(kappa, beta_mode)``. ``beta_mode`` is also the prior mode, used as
        the NUTS starting point.

    Raises:
        RuntimeError: The optimiser did not converge to a finite optimum.
    """
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
    """Return the log density (up to a constant) of the adaptive prior on (tau, beta).

    Instead of fixing the synthetic weight, the adaptive version treats
    ``tau`` as unknown with density proportional to
    ``tau**(p + alpha - 1) * exp(-tau * (kappa + 1/gamma))`` times the
    catalytic kernel ``exp(tau * q(beta))``. Here p is the number of
    coefficients. Li and Huang use ``(alpha, gamma) = (2, 1)``, the defaults.

    Returns:
        The log density, or ``-inf`` outside the valid parameter range.
    """
    if tau <= 0 or alpha <= 0 or gamma <= 0:
        return -np.inf
    q, _ = catalytic_kernel(beta, data)
    return float((data.design.shape[1] + alpha - 1) * np.log(tau)
                 + tau * (q - kappa - 1 / gamma))


def weighted_breslow_objective(
    beta: np.ndarray, design: np.ndarray, time: np.ndarray,
    event: np.ndarray, weight: np.ndarray,
) -> tuple[float, np.ndarray]:
    """Return the weighted Cox log partial likelihood (Breslow ties) and its gradient.

    Each row's weight multiplies both its contribution as an event and its
    contribution to the risk sets of earlier event times. Rows with tied
    times share one risk set (the Breslow approximation). The linear predictor
    is shifted by its maximum before exponentiating to avoid overflow; the
    shift cancels mathematically.

    Args:
        beta: Coefficients, shape (p,).
        design: Covariates, shape (n, p).
        time: Follow-up times, shape (n,).
        event: Event indicators (1 event, 0 censored), shape (n,).
        weight: Non-negative case weights, shape (n,).

    Returns:
        ``(log partial likelihood, score vector)``.
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
    """The authors' weighted mixture estimator (WME) as a survival model.

    The real training rows (weight 1 each) and the M synthetic rows (weight
    ``tau / M`` each, so ``tau`` in total) are pooled into one weighted Cox
    fit. With ``tau`` near 0 this is ordinary Cox regression; a larger
    ``tau`` pulls the coefficients towards the simple synthetic model.

    Li and Huang define only the coefficient estimate. To produce survival
    curves for evaluation, this class adds a weighted Breslow baseline hazard
    estimated from the same pooled rows.
    """

    def __init__(self, synthetic: CatalyticData, tau: float, time_scale: float = 1) -> None:
        """Store the synthetic rows, the total synthetic weight and the time scale.

        Args:
            synthetic: Synthetic prior data on the scaled time axis.
            tau: Total weight given to all synthetic rows together.
            time_scale: Divisor that puts real follow-up times on the same
                scaled axis as the synthetic times.
        """
        if not np.isfinite(tau) or tau <= 0:
            raise ValueError("mixture tau must be positive")
        if not np.isfinite(time_scale) or time_scale <= 0:
            raise ValueError("mixture time scale must be positive")
        self.synthetic, self.tau, self.time_scale = synthetic, float(tau), float(time_scale)
        self.details: dict = {}

    def fit(self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray) -> WeightedMixtureCox:
        """Maximise the pooled weighted partial likelihood and build the baseline.

        There is no penalty term and no sampling; the fit is accepted only if
        the optimiser succeeds and the score is close to zero.

        Raises:
            RuntimeError: The optimiser failed to converge.
        """
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
        # Weighted Breslow increments: weighted events at u divided by the
        # weighted risk-set sum at u, accumulated over event times.
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
        """Return the linear predictor ``x beta`` (log relative hazard); higher is riskier."""
        return X.to_numpy(float) @ self.beta

    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Return survival probabilities S(t | x) = exp(-H0(t) * exp(x beta)).

        Args:
            X: Covariates, shape (n, p).
            eval_times: Times in the cohort's original unit; they are scaled
                before looking up the step-function baseline H0.

        Returns:
            Array of shape (n, len(eval_times)).
        """
        index = np.searchsorted(self.event_times, eval_times / self.time_scale, side="right")
        h = np.r_[0, self.baseline][index]
        with np.errstate(over="ignore"):
            return np.exp(-np.exp(self.predict_risk(X))[:, None] * h)
