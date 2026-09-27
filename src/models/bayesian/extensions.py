"""Survival-calibrated horseshoe and correctly normalized catalytic priors.

These subclasses do not change the frozen model's sampling or variable order.
The catalytic likelihood-free prior is sampled by NUTS: PyMC forward sampling
ignores Potentials and would yield invalid prior predictive draws here.
"""

from __future__ import annotations

from typing import Any

import arviz as az
import numpy as np
import pandas as pd
import pymc as pm
from scipy.optimize import brentq

from src.models.bayesian.diagnostics import check_convergence
from src.models.bayesian.model import BayesianCoxModel, _validate_training_data
from src.models.bayesian.piecewise import _poisson_rows
from src.models.catalytic import CatalyticData, catalytic_kappa


def _add_compact_likelihood(x, rows, subject, interval, beta, log_lambda) -> None:
    eta = pm.math.dot(x, beta)
    mu = pm.math.exp(rows.log_exposure + log_lambda[interval] + eta[subject])
    pm.Poisson("obs", mu=mu, observed=rows.events)


def survival_horseshoe_scale(
    design: np.ndarray, time: np.ndarray, event: np.ndarray, cutoffs: np.ndarray,
) -> dict[str, Any]:
    """Calibrate the underlying HS with diagonal profiled PWE information.

    The Schur complement includes the specified baseline prior precision 1/4.
    Its diagonal approximation omits correlations; this is a declared survival
    adaptation, not the Gaussian noise formula or an exact survival theorem.
    """
    exposure = np.clip(np.minimum(time[:, None], cutoffs[1:]) - cutoffs[:-1], 0, None)
    counts = np.sum((event[:, None] == 1) & (time[:, None] > cutoffs[:-1])
                    & (time[:, None] <= cutoffs[1:]), axis=0)
    total = exposure.sum(axis=0)
    reference = np.array([brentq(lambda theta, d=d, a=a: d - a * np.exp(theta) - (theta + 2) / 4,
                                 -100, 50) for d, a in zip(counts, total, strict=True)])
    mu = exposure * np.exp(reference)
    cross = design.T @ mu
    diagonal = np.sum(mu.sum(axis=1)[:, None] * design**2, axis=0)
    diagonal -= np.sum(cross**2 / (mu.sum(axis=0) + 0.25), axis=1)
    if not np.isfinite(diagonal).all() or np.any(diagonal <= 1e-12):
        raise ValueError("horseshoe calibration has zero or invalid training information")
    p = design.shape[1]
    p0 = float(p / 2 if p <= 5 else 5)
    tau0 = float(np.exp(brentq(
        lambda logtau: np.sum(np.exp(logtau) * np.sqrt(diagonal)
                              / (1 + np.exp(logtau) * np.sqrt(diagonal))) - p0,
        -30, 30, xtol=1e-12,
    )))
    h = diagonal
    slab_dimension = np.sum(h / (h + 0.25) * tau0 * np.sqrt(h + 0.25)
                            / (1 + tau0 * np.sqrt(h + 0.25)))
    return {"tau0": tau0, "p0": p0, "p": p, "slab_c": 2.0,
            "fixed_tau0_regularized_expected_dimension": float(slab_dimension),
            "information_diagonal": diagonal.tolist(), "baseline_reference": reference.tolist(),
            "method": "diagonal profiled PWE curvature; predictor correlations omitted",
            "baseline_prior_precision": 0.25}


class CompactBayesianCox(BayesianCoxModel):
    """The same PWE model with one design product per subject, not interval.

    Only new post-hoc fits use this algebraically equivalent implementation.
    Original likelihood code and all frozen source hashes stay unchanged.
    """

    def fit(self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray) -> CompactBayesianCox:
        """Fit the common PWE likelihood without repeated dense design products."""
        self.feature_names = list(X.columns)
        x = X.to_numpy(float)
        t, e = np.asarray(y_time, float), np.asarray(y_event, int)
        _validate_training_data(x, t, e)
        scaled = self._scale_times(t, e)
        self.cutoffs_scaled = self._cut_points(scaled, e)
        self.cutoffs = self.cutoffs_scaled * self.time_scale
        n_features, n_intervals = x.shape[1], len(self.cutoffs_scaled) - 1
        rows = _poisson_rows(x, scaled, e, self.cutoffs_scaled)
        exposure = np.clip(np.minimum(scaled[:, None], self.cutoffs_scaled[1:])
                           - self.cutoffs_scaled[:-1], 0, None)
        subject, interval = np.where(exposure > 0)
        with pm.Model() as model:
            beta = self._coefficient_prior(n_features)
            log_lambda = self._baseline_log_hazard(n_intervals)
            _add_compact_likelihood(x, rows, subject, interval, beta, log_lambda)
            prior = self._sample_prior_predictive()
            self.idata = self._sample_posterior()
        self.pymc_model = model
        self.prior_predictive_summary = self._summarise_prior_predictive(prior, self.cutoffs_scaled, x)
        self.diagnostics = self._compute_diagnostics()
        self._store_posterior_draws(n_features, n_intervals)
        self.posterior_predictive_summary = self._summarise_posterior_predictive(x, t, e, rows)
        self.summary_df = self._hazard_ratio_summary()
        return self


class ExtensionBayesianCox(CompactBayesianCox):
    """Keep the common PWE likelihood while changing only its coefficient prior."""

    def __init__(self, variant: str, *, synthetic: CatalyticData | None = None, **kwargs: Any) -> None:
        if variant not in {"pv_horseshoe", "catalytic_fixed", "catalytic_adaptive"}:
            raise ValueError("unknown extension Bayesian prior")
        super().__init__(**kwargs)
        self.variant, self.synthetic = variant, synthetic
        self.details: dict[str, Any] = {}
        self.prior_diagnostics: dict[str, Any] = {}

    def fit(self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray) -> ExtensionBayesianCox:
        """Prepare training-only prior calibration and fit the common likelihood."""
        self.training_design = X.to_numpy(float)
        self.training_time = np.asarray(y_time, float)
        self.training_event = np.asarray(y_event, int)
        super().fit(X, y_time, y_event)
        return self

    def _coefficient_prior(self, n_features: int):
        if self.variant == "pv_horseshoe":
            self.details = survival_horseshoe_scale(
                self.training_design, self.training_time / self.time_scale,
                self.training_event, self.cutoffs_scaled,
            )
            tau = pm.HalfCauchy("tau", beta=self.details["tau0"])
            lam = pm.HalfCauchy("lam", beta=1, shape=n_features)
            variance = tau**2 * 4 * lam**2 / (4 + tau**2 * lam**2)
            z = pm.Normal("z", mu=0, sigma=1, shape=n_features)
            return pm.Deterministic("beta", z * pm.math.sqrt(variance))
        if self.synthetic is None or self.synthetic.design.shape[1] != n_features:
            raise ValueError("catalytic prior requires matching synthetic training design")
        if not hasattr(self, "kappa"):
            self.kappa, self.prior_mode = catalytic_kappa(self.synthetic)
        beta = pm.Flat("beta", shape=n_features, initval=self.prior_mode)
        eta = pm.math.dot(self.synthetic.design, beta)
        q = pm.math.sum(eta - self.synthetic.hazard * self.synthetic.time * pm.math.exp(eta))
        q /= len(self.synthetic.time)
        if self.variant == "catalytic_adaptive":
            # Gamma(p+alpha, rate=1/gamma) plus this potential gives the
            # (p+alpha-1) log(tau) joint kernel, not an ordinary Gamma(2,1).
            tau = pm.Gamma("tau", alpha=n_features + 2, beta=1)
            pm.Potential("catalytic_prior", tau * (q - self.kappa))
        else:
            pm.Potential("catalytic_prior", n_features * q)
        self.details = {"variant": self.variant, "p": n_features, "kappa": self.kappa,
                        "fixed_tau": n_features if self.variant == "catalytic_fixed" else None,
                        "alpha": 2, "gamma_scale": 1, "M": len(self.synthetic.time),
                        "hazard_scaled": self.synthetic.hazard,
                        "likelihood": "common PWE adaptation; not authors' grouped baseline"}
        return beta

    def _sample_prior_predictive(self):
        if self.variant == "pv_horseshoe":
            prior = super()._sample_prior_predictive()
            return prior
        # A separate model contains the actual joint prior but no real-data
        # likelihood. It is deliberately not pm.sample_prior_predictive.
        with pm.Model(model=None):
            self._coefficient_prior(len(self.feature_names))
            self._baseline_log_hazard(len(self.cutoffs_scaled) - 1)
            idata = pm.sample(
                draws=self.draws, tune=self.tune, chains=self.chains, cores=1,
                target_accept=self.target_accept, random_seed=self.random_state + 7919,
                progressbar=False, return_inferencedata=True,
            )
        self.prior_diagnostics = check_convergence(idata)
        self.prior_idata = idata
        return az.InferenceData(prior=idata.posterior)
