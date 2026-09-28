"""New coefficient priors for the post-hoc extension experiments (ADR-037, ADR-038).

All models here keep the frozen piecewise-exponential (PWE) likelihood and
baseline-hazard prior of ``BayesianCoxModel``. Only the prior on the
coefficients ``beta`` changes:

- ``pv_horseshoe``: a regularised horseshoe in the form recommended by
  Piironen and Vehtari (2017), with half-Cauchy scales and a global scale
  ``tau0`` calibrated from the training fold (``survival_horseshoe_scale``);
- ``catalytic_fixed``: the Cox catalytic prior with total synthetic weight
  ``tau = p``;
- ``catalytic_adaptive``: the catalytic prior with ``tau`` itself given a
  prior (Li and Huang's adaptive version).

``CompactBayesianCox`` evaluates the same likelihood faster; the frozen class
and its source are left untouched.

The catalytic prior has no simple sampling formula. It enters PyMC as a
``Potential`` (an extra log-density term), and PyMC's forward
``sample_prior_predictive`` ignores Potentials. So prior predictive draws for
the catalytic variants are made by running NUTS on a model that holds only
the priors.
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
    """Add the PWE Poisson likelihood, computing ``x beta`` once per subject.

    The frozen implementation multiplies the covariates of every
    subject-interval row by ``beta``. Here the product is computed once per
    subject and indexed, which gives the same values with less work.
    ``subject`` and ``interval`` come from ``np.where`` on the same exposure
    matrix as ``_poisson_rows``, so they line up with ``rows`` element by
    element.
    """
    eta = pm.math.dot(x, beta)
    mu = pm.math.exp(rows.log_exposure + log_lambda[interval] + eta[subject])
    pm.Poisson("obs", mu=mu, observed=rows.events)


def survival_horseshoe_scale(
    design: np.ndarray, time: np.ndarray, event: np.ndarray, cutoffs: np.ndarray,
) -> dict[str, Any]:
    """Choose the horseshoe global scale ``tau0`` from the training data.

    Piironen and Vehtari choose ``tau0`` so that the prior expects about
    ``p0`` clearly non-zero coefficients. Their formula is written for
    Gaussian regression, where each coefficient's information is n / sigma^2.
    This survival adaptation replaces that with the curvature (Fisher
    information) of the PWE log-likelihood for each coefficient, as follows:

    1. For each baseline interval, find the posterior-mode log hazard at
       ``beta = 0`` under the frozen N(-2, 2^2) baseline prior. That is the
       root of ``d - a * exp(theta) - (theta + 2) / 4 = 0``, where d is the
       interval's event count and a its total exposure.
    2. Compute each coefficient's information, subtracting the part explained
       by the baseline hazards (a Schur complement that includes the
       baseline prior precision 1/4). Only the diagonal is kept; correlations
       between predictors are ignored.
    3. Solve ``sum_j tau0 * sqrt(h_j) / (1 + tau0 * sqrt(h_j)) = p0`` for
       ``tau0``, with ``p0 = p / 2`` when p <= 5, otherwise 5.

    This is a declared approximation, not an exact survival result.

    Args:
        design: Preprocessed training covariates, shape (n, p).
        time: Training follow-up times on the model's scaled axis.
        event: Training event indicators.
        cutoffs: Scaled interval cut points, starting at 0.

    Returns:
        ``tau0``, ``p0``, the fixed slab scale (2.0), the per-coefficient
        information and diagnostics describing the calibration.

    Raises:
        ValueError: A coefficient has zero or invalid training information.
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
    """``BayesianCoxModel`` with a faster, algebraically identical likelihood.

    Only the new post-hoc fits use this class. The frozen confirmatory model
    and its source files are unchanged, so the original evidence still
    verifies.
    """

    def fit(self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray) -> CompactBayesianCox:
        """Fit the PWE model with the compact likelihood.

        The steps follow ``BayesianCoxModel.fit``: scale times, set cut
        points, build the priors and likelihood, then draw prior predictive
        samples, sample the posterior, compute diagnostics and store the
        posterior summaries.
        """
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
    """The PWE model with one of the extension coefficient priors.

    Args:
        variant: ``"pv_horseshoe"``, ``"catalytic_fixed"`` or
            ``"catalytic_adaptive"``.
        synthetic: Synthetic prior data; required by the catalytic variants.
        **kwargs: Passed to ``BayesianCoxModel`` (sampler settings, seed).
    """

    def __init__(self, variant: str, *, synthetic: CatalyticData | None = None, **kwargs: Any) -> None:
        """Validate the variant and keep the synthetic data for the catalytic priors."""
        if variant not in {"pv_horseshoe", "catalytic_fixed", "catalytic_adaptive"}:
            raise ValueError("unknown extension Bayesian prior")
        super().__init__(**kwargs)
        self.variant, self.synthetic = variant, synthetic
        self.details: dict[str, Any] = {}
        self.prior_diagnostics: dict[str, Any] = {}

    def fit(self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray) -> ExtensionBayesianCox:
        """Keep the training data for prior calibration, then fit.

        The horseshoe calibration needs the training design, times and
        events. They are stored before fitting because the prior is built
        inside the parent ``fit``.
        """
        self.training_design = X.to_numpy(float)
        self.training_time = np.asarray(y_time, float)
        self.training_event = np.asarray(y_event, int)
        super().fit(X, y_time, y_event)
        return self

    def _coefficient_prior(self, n_features: int):
        """Create the ``beta`` prior for the chosen variant inside the active PyMC model.

        pv_horseshoe: ``beta_j = z_j * tau * lambda_tilde_j`` (non-centred),
        with tau ~ HalfCauchy(tau0) and lambda_j ~ HalfCauchy(1). The slab is
        fixed at c = 2, so c^2 = 4 in
        ``lambda_tilde^2 = c^2 lambda^2 / (c^2 + tau^2 lambda^2)``.

        Catalytic: ``beta`` gets a flat base measure plus a Potential equal to
        ``tau * q(beta)``, which gives the catalytic density ``exp(tau * q)``.
        Fixed variant: tau = p. Adaptive variant: tau gets its own prior.
        """
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
        # kappa and the prior mode depend only on the synthetic data, so they
        # are computed once and reused if the prior is built again.
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
        """Draw from the prior; NUTS is used for the catalytic variants.

        The horseshoe variant uses the parent's forward sampling. The
        catalytic priors are defined through a Potential, so their draws come
        from NUTS on a separate model that contains the priors but no data.
        That run's convergence diagnostics are kept in ``prior_diagnostics``.
        """
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
