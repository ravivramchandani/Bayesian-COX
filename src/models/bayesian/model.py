"""Bayesian piecewise-exponential proportional-hazards model in PyMC.

The confirmatory pipeline fits this model once per training fold and
coefficient prior. The hazard of subject i in baseline interval m is
``lambda_m * exp(x_i beta)``. Follow-up is cut into intervals at training
event-time quantiles, and the likelihood is written in its equivalent Poisson
form: every subject-interval pair with positive exposure is one Poisson count
(1 if the subject's event falls in that interval, otherwise 0) with mean
``exposure * lambda_m * exp(x_i beta)``. This is a full likelihood with an
estimated piecewise-constant baseline hazard, not the Cox partial likelihood.
The class keeps the name ``BayesianCoxModel`` because ``beta`` has the Cox
meaning of log hazard ratios.
"""

from typing import NamedTuple

import numpy as np
import pandas as pd
import pymc as pm
from sksurv.nonparametric import kaplan_meier_estimator

from src.models.base import BaseSurvivalModel
from src.models.bayesian.diagnostics import check_convergence

SUPPORTED_PRIORS = ("normal", "horseshoe", "spike_slab")

# Bound on x beta before exponentiation in predictive summaries and
# predictions, so that extreme prior or posterior draws cannot overflow.
LINEAR_PREDICTOR_CLIP = 30.0

# Scaled times (multiples of the median training event time) at which the
# prior predictive survival is summarised.
PRIOR_PREDICTIVE_SCALED_TIMES = (0.25, 0.5, 1.0, 2.0)
MAX_PRIOR_PREDICTIVE_ROWS = 512

MAX_POSTERIOR_PREDICTIVE_DRAWS = 200
# Offset from ``random_state`` for the posterior predictive replication, so it
# never shares a stream with the sampler seed.
POSTERIOR_PREDICTIVE_SEED_OFFSET = 104729

# Posterior draws processed at once in the prediction loops, to bound memory.
DRAW_CHUNK_SIZE = 256


class _PoissonRows(NamedTuple):
    """Subject-interval rows of the Poisson likelihood with positive exposure."""

    covariates: np.ndarray
    exposures: np.ndarray
    log_exposure: np.ndarray
    interval_index: np.ndarray
    events: np.ndarray


def _validate_training_data(
    X_mat: np.ndarray, y_time: np.ndarray, y_event: np.ndarray
) -> None:
    """Raise ``ValueError`` unless the training arrays can be fitted."""
    if len(X_mat) != len(y_time) or len(y_time) != len(y_event):
        raise ValueError("X, y_time and y_event must contain the same rows")
    if not np.isfinite(X_mat).all() or not np.isfinite(y_time).all():
        raise ValueError("Bayesian model inputs must be finite after preprocessing")
    if np.any(y_time <= 0):
        raise ValueError("Survival durations must be strictly positive")
    if int(y_event.sum()) < 2:
        raise ValueError("Bayesian model requires at least two observed events")


def _poisson_rows(
    X_mat: np.ndarray,
    y_time_scaled: np.ndarray,
    y_event: np.ndarray,
    cutoffs_scaled: np.ndarray,
) -> _PoissonRows:
    """Expand subjects into subject-interval exposures and event counts.

    Subject i's exposure in interval m is ``max(0, min(t_i, end_m) -
    start_m)``, and its count is 1 only in the interval that contains an
    observed event time. Rows with zero exposure are dropped. Rows are kept
    in subject-major order.
    """
    starts = cutoffs_scaled[:-1]
    ends = cutoffs_scaled[1:]
    times = y_time_scaled[:, None]
    events = y_event[:, None]

    exposures = np.clip(np.minimum(times, ends) - starts, 0, None)
    events_matrix = ((events == 1) & (times > starts) & (times <= ends)).astype(float)

    has_exposure = exposures > 0
    subject_index, interval_index = np.where(has_exposure)
    row_exposures = exposures[has_exposure]
    return _PoissonRows(
        covariates=X_mat[subject_index],
        exposures=row_exposures,
        log_exposure=np.log(row_exposures),
        interval_index=interval_index,
        events=events_matrix[has_exposure],
    )


def _add_poisson_likelihood(rows: _PoissonRows, beta, log_lambda) -> None:
    """Add Poisson counts ``obs`` with log mean log(exposure) + log(lambda_m) + x beta."""
    linear_predictor = pm.math.dot(rows.covariates, beta)
    interval_log_hazard = log_lambda[rows.interval_index]
    poisson_mean = pm.math.exp(
        rows.log_exposure + interval_log_hazard + linear_predictor
    )
    pm.Poisson("obs", mu=poisson_mean, observed=rows.events)


def _kaplan_meier_at(
    y_time: np.ndarray, y_event: np.ndarray, horizons: np.ndarray
) -> np.ndarray:
    """Return right-continuous Kaplan-Meier survival at each horizon."""
    km_time, km_survival = kaplan_meier_estimator(
        y_event.astype(bool), y_time.astype(float)
    )
    km_indices = np.searchsorted(km_time, horizons, side="right") - 1
    observed = np.ones(len(horizons), dtype=float)
    valid = km_indices >= 0
    observed[valid] = km_survival[km_indices[valid]]
    return observed


def _replication_summary(
    replicated_values: np.ndarray, observed_value: float
) -> dict:
    """Compare an observed count with its posterior predictive replicates."""
    lower, upper = np.percentile(replicated_values, [2.5, 97.5])
    return {
        "observed": float(observed_value),
        "replicated_mean": float(np.mean(replicated_values)),
        "replicated_median": float(np.median(replicated_values)),
        "replicated_lower_95": float(lower),
        "replicated_upper_95": float(upper),
        "posterior_predictive_tail_probability": float(
            np.mean(replicated_values >= observed_value)
        ),
        "observed_covered": bool(lower <= observed_value <= upper),
    }


class BayesianCoxModel(BaseSurvivalModel):
    """Bayesian piecewise-exponential proportional-hazards model.

    Times are divided by the median training event time before fitting, so the
    baseline hazards ``lambda_m`` are per median event time. Their prior is
    ``log lambda_m ~ Normal(-2, 2)``, independently per interval. With
    ``noncentered_baseline=True`` the same prior is written as
    ``log lambda_m = -2 + 2 * log_lambda_offset_m`` with a standard normal
    offset; the confirmatory protocol uses this form only as its second
    refit after failed diagnostics.

    Coefficient priors (``coefficient_prior``), with the values the
    confirmatory configuration passes in ``prior_params``:

    - ``normal``: ``beta_j ~ Normal(mu, sigma)``, with mu = 0 and sigma = 1.
    - ``horseshoe``: a regularised horseshoe (Piironen and Vehtari, 2017) in
      non-centred form: global scale ``tau ~ half-t_2(tau0 = 0.1)``, local
      scales ``lam_j ~ half-t_2(1)``, slab ``c2 ~ InvGamma(slab_df / 2,
      slab_df * slab_scale^2 / 2) = InvGamma(2, 8)``,
      ``lam_tilde_j^2 = c2 lam_j^2 / (c2 + tau^2 lam_j^2)``, and
      ``beta_j = z_j * tau * lam_tilde_j`` with ``z_j ~ Normal(0, 1)``. The
      local scales are half-t with 2 degrees of freedom, not half-Cauchy, so
      in Piironen and Vehtari's terms this is regularised hierarchical
      shrinkage rather than a strict horseshoe. ``tau0`` is fixed, not set by
      their effective-number-of-parameters rule.
    - ``spike_slab``: a continuous relaxation of spike-and-slab, because NUTS
      cannot sample a discrete inclusion indicator. The weight
      ``gamma_j ~ Beta(alpha = 1, beta_conc = 1)`` mixes the spike and slab
      variances, ``sd_j^2 = (1 - gamma_j) spike_sd^2 + gamma_j slab_sd^2``
      with spike_sd = 0.05 and slab_sd = 2, and ``beta_j = z_j * sd_j`` with
      ``z_j ~ Normal(0, 1)``. The posterior mean of ``gamma_j`` is the
      inclusion signal.

    The priors define the PyMC variables ``beta``, ``tau``, ``lam``, ``c2``,
    ``gamma``, ``z``, ``log_lambda`` and ``log_lambda_offset``. Their names,
    shapes and creation order are part of the frozen protocol, because
    seeding and the stored traces depend on them.
    """

    def __init__(
        self,
        n_intervals: int = 6,
        inference_method: str = "nuts",
        n_advi_iterations: int = 10000,
        draws: int = 2000,
        tune: int = 1000,
        chains: int = 4,
        # Chains run sequentially. PyMC's parallel sampler is unreliable on
        # macOS/Apple silicon here, and each chain takes seconds at this model
        # size, so the parallel path is not worth the flakiness.
        cores: int = 1,
        target_accept: float = 0.95,
        random_state: int = 42,
        coefficient_prior: str = "normal",
        prior_params: dict | None = None,
        noncentered_baseline: bool = False,
    ):
        self.n_intervals = n_intervals
        self.inference_method = inference_method.lower()
        self.n_advi_iterations = n_advi_iterations
        self.draws = draws
        self.tune = tune
        self.chains = chains
        self.cores = cores
        self.target_accept = target_accept
        self.random_state = random_state
        self.coefficient_prior = coefficient_prior.lower()
        self.prior_params = prior_params if prior_params is not None else {}
        self.noncentered_baseline = bool(noncentered_baseline)

        self.feature_names = []
        self.cutoffs = np.array([])
        self.cutoffs_scaled = np.array([])
        self.time_scale = 1.0
        self.pymc_model = None
        self.idata = None
        self.summary_df = None
        self.diagnostics: dict = {}
        self.prior_predictive_summary: dict = {}
        self.posterior_predictive_summary: dict = {}

        self.beta_samples = None  # (n_draws, n_features)
        self.lambda_samples = None  # (n_draws, n_intervals), scaled-time hazards

    def fit(
        self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray
    ) -> "BayesianCoxModel":
        """Fit the model by NUTS (default) or ADVI and store posterior summaries.

        After fitting, ``diagnostics`` holds the convergence checks,
        ``prior_predictive_summary`` and ``posterior_predictive_summary`` hold
        the model checks, and ``beta_samples`` and ``lambda_samples`` hold
        the pooled posterior draws.

        Args:
            X: Preprocessed training covariates, one column per coefficient.
            y_time: Strictly positive follow-up times.
            y_event: Event indicators, 1 for an event and 0 for censoring.

        Returns:
            The fitted model.
        """
        self.feature_names = list(X.columns)
        X_mat = X.values.astype(float)
        y_time = np.asarray(y_time, dtype=float)
        y_event = np.asarray(y_event, dtype=int)
        _validate_training_data(X_mat, y_time, y_event)

        y_time_scaled = self._scale_times(y_time, y_event)
        self.cutoffs_scaled = self._cut_points(y_time_scaled, y_event)
        self.cutoffs = self.cutoffs_scaled * self.time_scale
        n_features = X_mat.shape[1]
        n_intervals = len(self.cutoffs_scaled) - 1
        rows = _poisson_rows(X_mat, y_time_scaled, y_event, self.cutoffs_scaled)

        # Keep this order of variable creation and sampling calls. PyMC
        # assigns each variable's random stream, the initial jitter and the
        # sampler's parameter layout by variable order, so the frozen draws
        # depend on it.
        with pm.Model() as model:
            beta = self._coefficient_prior(n_features)
            log_lambda = self._baseline_log_hazard(n_intervals)
            _add_poisson_likelihood(rows, beta, log_lambda)
            prior_idata = self._sample_prior_predictive()
            self.idata = self._sample_posterior()

        self.pymc_model = model
        self.prior_predictive_summary = self._summarise_prior_predictive(
            prior_idata, self.cutoffs_scaled, X_mat
        )
        self.diagnostics = self._compute_diagnostics()
        self._store_posterior_draws(n_features, n_intervals)
        self.posterior_predictive_summary = self._summarise_posterior_predictive(
            X_mat, y_time, y_event, rows
        )
        self.summary_df = self._hazard_ratio_summary()
        return self

    def _scale_times(self, y_time: np.ndarray, y_event: np.ndarray) -> np.ndarray:
        """Set ``time_scale`` to the median training event time; return scaled times."""
        event_times = y_time[y_event == 1]
        self.time_scale = float(np.median(event_times))
        if not np.isfinite(self.time_scale) or self.time_scale <= 0:
            raise ValueError("Could not derive a positive training-event time scale")
        return y_time / self.time_scale

    def _cut_points(self, y_time_scaled: np.ndarray, y_event: np.ndarray) -> np.ndarray:
        """Return ``n_intervals + 1`` baseline cut points on the scaled time axis.

        Cut points are event-time quantiles, with the first set to 0 and the
        last extended to at least the maximum follow-up plus one scaled unit.
        If tied quantiles leave fewer than ``n_intervals`` distinct intervals,
        equal-width intervals are used instead.
        """
        event_times = y_time_scaled[y_event == 1]
        percentiles = np.linspace(0, 100, self.n_intervals + 1)
        cutoffs = np.percentile(event_times, percentiles)
        cutoffs[0] = 0.0
        cutoffs[-1] = max(y_time_scaled.max() + 1.0, cutoffs[-1])
        cutoffs = np.unique(cutoffs)
        if len(cutoffs) - 1 < self.n_intervals:
            cutoffs = np.linspace(0, y_time_scaled.max() + 1.0, self.n_intervals + 1)
        return cutoffs

    def _coefficient_prior(self, n_features: int):
        """Create the configured coefficient prior and return ``beta``."""
        builders = {
            "normal": self._normal_prior,
            "horseshoe": self._regularised_horseshoe_prior,
            "spike_slab": self._spike_and_slab_prior,
        }
        if self.coefficient_prior not in builders:
            raise ValueError(
                f"Unknown coefficient prior: {self.coefficient_prior}. "
                f"Supported: {SUPPORTED_PRIORS}"
            )
        return builders[self.coefficient_prior](n_features)

    def _normal_prior(self, n_features: int):
        """Create ``beta ~ Normal(mu, sigma)``."""
        return pm.Normal(
            "beta",
            mu=self.prior_params.get("mu", 0.0),
            sigma=self.prior_params.get("sigma", 1.0),
            shape=n_features,
        )

    def _regularised_horseshoe_prior(self, n_features: int):
        """Create the non-centred regularised horseshoe; return ``beta``.

        The plain horseshoe funnels badly under NUTS. The slab ``c2`` bounds
        the tails of the local scales and can improve sampling geometry. The
        prespecified diagnostics, not the prior form, decide whether a fit is
        admissible.
        """
        tau0 = self.prior_params.get("tau0", 0.1)
        slab_df = self.prior_params.get("slab_df", 4.0)
        slab_scale = self.prior_params.get("slab_scale", 2.0)

        tau = pm.HalfStudentT("tau", nu=2, sigma=tau0)
        lam = pm.HalfStudentT("lam", nu=2, sigma=1.0, shape=n_features)
        c2 = pm.InverseGamma(
            "c2",
            alpha=slab_df / 2.0,
            beta=slab_df * slab_scale**2 / 2.0,
        )

        lam_sq = lam**2
        lam_tilde = pm.math.sqrt(c2 * lam_sq / (c2 + tau**2 * lam_sq))
        z = pm.Normal("z", mu=0.0, sigma=1.0, shape=n_features)
        return pm.Deterministic("beta", z * tau * lam_tilde)

    def _spike_and_slab_prior(self, n_features: int):
        """Create the continuous spike-and-slab relaxation; return ``beta``."""
        spike_sd = self.prior_params.get("spike_sd", 0.05)
        slab_sd = self.prior_params.get("slab_sd", 2.0)
        gamma = pm.Beta(
            "gamma",
            alpha=self.prior_params.get("alpha", 1.0),
            beta=self.prior_params.get("beta_conc", 1.0),
            shape=n_features,
        )
        sd = pm.math.sqrt((1.0 - gamma) * spike_sd**2 + gamma * slab_sd**2)
        z = pm.Normal("z", mu=0.0, sigma=1.0, shape=n_features)
        return pm.Deterministic("beta", z * sd)

    def _baseline_log_hazard(self, n_intervals: int):
        """Create ``log_lambda ~ Normal(-2, 2)``, centred or non-centred."""
        if self.noncentered_baseline:
            log_lambda_offset = pm.Normal(
                "log_lambda_offset", mu=0.0, sigma=1.0, shape=n_intervals
            )
            return pm.Deterministic("log_lambda", -2.0 + 2.0 * log_lambda_offset)
        return pm.Normal("log_lambda", mu=-2.0, sigma=2.0, shape=n_intervals)

    def _sample_prior_predictive(self):
        """Draw ``beta`` and ``log_lambda`` from the prior."""
        return pm.sample_prior_predictive(
            draws=min(200, max(50, self.draws)),
            var_names=["beta", "log_lambda"],
            random_seed=self.random_state,
            return_inferencedata=True,
        )

    def _sample_posterior(self):
        """Return posterior draws from NUTS, or from a fitted ADVI approximation."""
        if self.inference_method == "advi":
            approx = pm.fit(
                method="advi",
                n=self.n_advi_iterations,
                progressbar=False,
                random_seed=self.random_state,
            )
            return approx.sample(draws=self.draws, random_seed=self.random_state)
        return pm.sample(
            draws=self.draws,
            tune=self.tune,
            chains=self.chains,
            cores=self.cores,
            target_accept=self.target_accept,
            random_seed=self.random_state,
            progressbar=False,
            return_inferencedata=True,
        )

    def _store_posterior_draws(self, n_features: int, n_intervals: int) -> None:
        """Pool chains into ``beta_samples`` and ``lambda_samples``."""
        posterior = self.idata.posterior
        beta_raw = posterior["beta"].values  # (chains, draws, n_features)
        log_lambda_raw = posterior["log_lambda"].values  # (chains, draws, n_intervals)
        self.beta_samples = beta_raw.reshape(-1, n_features)
        self.lambda_samples = np.exp(log_lambda_raw.reshape(-1, n_intervals))

    def _hazard_ratio_summary(self) -> pd.DataFrame:
        """Tabulate posterior coefficient and hazard-ratio summaries per feature."""
        records = []
        for j, feature in enumerate(self.feature_names):
            coefficient = self.beta_samples[:, j]
            hazard_ratio = np.exp(coefficient)
            records.append(
                {
                    "feature": feature,
                    "coef (beta_mean)": float(np.mean(coefficient)),
                    "exp(coef) HR Mean": float(np.mean(hazard_ratio)),
                    "exp(coef) HR Median": float(np.median(hazard_ratio)),
                    "HR SD": float(np.std(hazard_ratio)),
                    "95% Credible Lower": float(np.percentile(hazard_ratio, 2.5)),
                    "95% Credible Upper": float(np.percentile(hazard_ratio, 97.5)),
                    "Prob(HR > 1)": float(np.mean(hazard_ratio > 1.0)),
                }
            )
        return (
            pd.DataFrame(records)
            .sort_values(by="exp(coef) HR Mean", ascending=False)
            .reset_index(drop=True)
        )

    @staticmethod
    def _baseline_cumulative_hazard(
        hazards: np.ndarray,
        cutoffs: np.ndarray,
        times: np.ndarray,
    ) -> np.ndarray:
        """Evaluate piecewise-constant cumulative hazards for many draws.

        Returns an array of shape ``(n_draws, n_times)``. Beyond the last cut
        point the last interval's hazard is extended.
        """
        hazards = np.asarray(hazards, dtype=float)
        cutoffs = np.asarray(cutoffs, dtype=float)
        times = np.asarray(times, dtype=float)
        durations = np.diff(cutoffs)
        completed = np.cumsum(hazards * durations[None, :], axis=1)
        completed = np.column_stack([np.zeros(len(hazards)), completed])
        result = np.zeros((len(hazards), len(times)), dtype=float)
        n_intervals = hazards.shape[1]
        for column, value in enumerate(times):
            interval = int(np.searchsorted(cutoffs, value, side="right") - 1)
            if interval < 0:
                continue
            if interval >= n_intervals:
                result[:, column] = completed[:, -1] + hazards[:, -1] * (
                    value - cutoffs[-1]
                )
            else:
                result[:, column] = completed[:, interval] + hazards[:, interval] * (
                    value - cutoffs[interval]
                )
        return result

    def _summarise_prior_predictive(
        self,
        prior_idata,
        cutoffs_scaled: np.ndarray,
        X_mat: np.ndarray,
    ) -> dict:
        """Summarise the survival implied by the prior.

        Baseline survival is kept for interpretation. The main check uses up
        to 512 evenly spaced training rows, so that extreme coefficient-prior
        predictions cannot hide behind a reasonable baseline hazard.
        """
        log_hazard = prior_idata.prior["log_lambda"].values
        hazards = np.exp(log_hazard.reshape(-1, log_hazard.shape[-1]))
        beta_raw = prior_idata.prior["beta"].values
        beta = beta_raw.reshape(-1, beta_raw.shape[-1])
        if len(beta) != len(hazards):
            raise RuntimeError("prior coefficient and baseline draws are not aligned")
        times = np.asarray(PRIOR_PREDICTIVE_SCALED_TIMES, dtype=float)
        cumulative = self._baseline_cumulative_hazard(hazards, cutoffs_scaled, times)
        baseline_survival = np.exp(-cumulative)

        covariates = np.asarray(X_mat, dtype=float)
        if covariates.ndim != 2 or covariates.shape[1] != beta.shape[1]:
            raise ValueError("prior predictive covariates do not match beta")
        selected_indices = np.linspace(
            0,
            len(covariates) - 1,
            min(MAX_PRIOR_PREDICTIVE_ROWS, len(covariates)),
            dtype=int,
        )
        selected = covariates[selected_indices]
        linear = np.clip(
            beta @ selected.T, -LINEAR_PREDICTOR_CLIP, LINEAR_PREDICTOR_CLIP
        )
        population_survival = np.exp(
            -np.exp(linear)[:, :, None] * cumulative[:, None, :]
        )
        return {
            "n_draws": int(len(hazards)),
            "time_scale": float(self.time_scale),
            "baseline_survival": [
                self._prior_baseline_row(scaled_time, baseline_survival[:, column])
                for column, scaled_time in enumerate(times)
            ],
            "covariate_population_survival": [
                self._prior_population_row(
                    scaled_time, population_survival[:, :, column]
                )
                for column, scaled_time in enumerate(times)
            ],
            "n_covariate_rows": int(len(selected)),
            "covariate_row_selection": "deterministic_evenly_spaced_training_rows",
            "finite": bool(
                np.isfinite(baseline_survival).all()
                and np.isfinite(population_survival).all()
            ),
        }

    def _prior_baseline_row(self, scaled_time: float, values: np.ndarray) -> dict:
        """Summarise prior baseline survival draws at one time."""
        return {
            "scaled_time": float(scaled_time),
            "time": float(scaled_time * self.time_scale),
            "median_survival": float(np.median(values)),
            "lower_95": float(np.percentile(values, 2.5)),
            "upper_95": float(np.percentile(values, 97.5)),
        }

    def _prior_population_row(self, scaled_time: float, survival: np.ndarray) -> dict:
        """Summarise prior survival over (draw, subject) pairs at one time."""
        subject_draw_values = survival.reshape(-1)
        draw_means = survival.mean(axis=1)
        return {
            "scaled_time": float(scaled_time),
            "time": float(scaled_time * self.time_scale),
            "subject_draw_median_survival": float(np.median(subject_draw_values)),
            "subject_draw_lower_95": float(np.percentile(subject_draw_values, 2.5)),
            "subject_draw_upper_95": float(np.percentile(subject_draw_values, 97.5)),
            "mean_survival_across_subjects_median": float(np.median(draw_means)),
            "proportion_subject_draws_below_0_01": float(
                np.mean(subject_draw_values < 0.01)
            ),
            "proportion_subject_draws_above_0_99": float(
                np.mean(subject_draw_values > 0.99)
            ),
        }

    def _summarise_posterior_predictive(
        self,
        X_mat: np.ndarray,
        y_time: np.ndarray,
        y_event: np.ndarray,
        rows: _PoissonRows,
    ) -> dict:
        """Archive posterior predictive checks on the training data.

        Uses up to 200 evenly spaced posterior draws for two checks:
        replicated Poisson event counts (a check on the likelihood scale) and
        mean fitted survival against Kaplan-Meier at the training event-time
        quartiles.
        """
        n_available = len(self.beta_samples)
        draw_indices = np.linspace(
            0,
            n_available - 1,
            min(MAX_POSTERIOR_PREDICTIVE_DRAWS, n_available),
            dtype=int,
        )
        beta = self.beta_samples[draw_indices]
        hazards = self.lambda_samples[draw_indices]
        replicated = self._replicated_event_counts(rows, beta, hazards)
        survival_rows = self._fitted_survival_check(
            X_mat, y_time, y_event, beta, hazards
        )
        return {
            "n_draws": int(len(draw_indices)),
            "replicated_event_counts": replicated,
            "fitted_survival_check": survival_rows,
            # Compatibility alias for pilot reporting code. This is a fitted-
            # survival comparison, not a replicated-data check.
            "survival_check": survival_rows,
        }

    def _replicated_event_counts(
        self, rows: _PoissonRows, beta: np.ndarray, hazards: np.ndarray
    ) -> dict:
        """Replicate the Poisson counts per draw and compare with the data."""
        n_intervals = hazards.shape[1]
        rng = np.random.default_rng(self.random_state + POSTERIOR_PREDICTIVE_SEED_OFFSET)
        replicated_interval_counts = np.zeros((len(beta), n_intervals), dtype=float)
        for row, (beta_draw, hazard_draw) in enumerate(
            zip(beta, hazards, strict=True)
        ):
            linear_predictor = np.clip(
                rows.covariates @ beta_draw,
                -LINEAR_PREDICTOR_CLIP,
                LINEAR_PREDICTOR_CLIP,
            )
            poisson_mean = (
                rows.exposures
                * hazard_draw[rows.interval_index]
                * np.exp(linear_predictor)
            )
            if not np.isfinite(poisson_mean).all():
                raise RuntimeError("posterior predictive Poisson means must be finite")
            replicated = rng.poisson(poisson_mean)
            replicated_interval_counts[row] = np.bincount(
                rows.interval_index,
                weights=replicated,
                minlength=n_intervals,
            )

        observed_interval_counts = np.bincount(
            rows.interval_index,
            weights=rows.events,
            minlength=n_intervals,
        )
        return {
            "likelihood": "expanded piecewise-Poisson event counts",
            "n_posterior_draws": int(len(beta)),
            "total": _replication_summary(
                replicated_interval_counts.sum(axis=1), float(rows.events.sum())
            ),
            "by_baseline_interval": [
                {
                    "interval": interval + 1,
                    **_replication_summary(
                        replicated_interval_counts[:, interval],
                        observed_interval_counts[interval],
                    ),
                }
                for interval in range(n_intervals)
            ],
        }

    def _fitted_survival_check(
        self,
        X_mat: np.ndarray,
        y_time: np.ndarray,
        y_event: np.ndarray,
        beta: np.ndarray,
        hazards: np.ndarray,
    ) -> list[dict]:
        """Compare mean fitted survival with Kaplan-Meier at event-time quartiles."""
        event_times = y_time[y_event == 1]
        horizons = np.quantile(event_times, [0.25, 0.5, 0.75]).astype(float)
        observed = _kaplan_meier_at(y_time, y_event, horizons)

        cumulative = self._baseline_cumulative_hazard(
            hazards, self.cutoffs_scaled, horizons / self.time_scale
        )
        linear = beta @ X_mat.T
        predicted = np.empty((len(beta), len(horizons)), dtype=float)
        for column in range(len(horizons)):
            survival = np.exp(-np.exp(linear) * cumulative[:, column][:, None])
            predicted[:, column] = survival.mean(axis=1)

        rows = []
        for column, horizon in enumerate(horizons):
            values = predicted[:, column]
            lower = float(np.percentile(values, 2.5))
            upper = float(np.percentile(values, 97.5))
            rows.append(
                {
                    "time": float(horizon),
                    "observed_km": float(observed[column]),
                    "predicted_mean": float(values.mean()),
                    "lower_95": lower,
                    "upper_95": upper,
                    "observed_covered": bool(lower <= observed[column] <= upper),
                }
            )
        return rows

    def _compute_diagnostics(self) -> dict:
        """Return convergence diagnostics for every posterior variable.

        NUTS fits report R-hat, bulk and tail ESS, MCSE, BFMI, divergences and
        tree-depth hits (see :func:`check_convergence`). ADVI produces no NUTS
        diagnostics and reports ``converged`` as ``None``.
        """
        if self.inference_method == "advi":
            return {"method": "advi", "converged": None}

        result = check_convergence(self.idata, var_names=None)
        result.update(
            {
                "method": "nuts",
                "n_chains": int(self.chains),
                "n_draws": int(self.draws),
            }
        )
        return result

    def inclusion_signal(self) -> pd.DataFrame | None:
        """Return the per-feature posterior signal used as built-in explanation.

        For the spike-and-slab prior this is the posterior mean of the
        continuous inclusion weight ``gamma``. For the horseshoe it is a
        local-scale shrinkage proxy, ``1 / (1 + lam^2)``. That is not the full
        posterior shrinkage factor, which also depends on the global scale,
        slab regularisation and likelihood. Returns ``None`` for the Normal
        prior.
        """
        if self.idata is None:
            raise RuntimeError("Model is not fitted. Call fit() first.")

        posterior = self.idata.posterior

        if self.coefficient_prior == "spike_slab":
            gamma = posterior["gamma"].values.reshape(-1, len(self.feature_names))
            return pd.DataFrame(
                {
                    "feature": self.feature_names,
                    "continuous_inclusion_weight": gamma.mean(axis=0),
                }
            ).sort_values(
                "continuous_inclusion_weight", ascending=False
            ).reset_index(drop=True)

        if self.coefficient_prior == "horseshoe":
            lam = posterior["lam"].values.reshape(-1, len(self.feature_names))
            shrinkage = 1.0 / (1.0 + lam**2)
            return pd.DataFrame(
                {
                    "feature": self.feature_names,
                    "local_scale_shrinkage_proxy": shrinkage.mean(axis=0),
                }
            ).sort_values("local_scale_shrinkage_proxy").reset_index(drop=True)

        return None

    def predict_risk(self, X: pd.DataFrame) -> np.ndarray:
        """Return the posterior-mean linear predictor ``x E[beta]``.

        The score is on the log hazard-ratio scale (not exponentiated), with
        no baseline term. Higher values mean higher hazard.
        """
        if self.beta_samples is None:
            raise ValueError("Model must be fitted before calling predict_risk().")
        X_mat = X[self.feature_names].values.astype(float)
        mean_beta = np.mean(self.beta_samples, axis=0)
        return np.dot(X_mat, mean_beta)

    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Return posterior-mean survival ``S(t | x)`` of shape (n_samples, n_times).

        Survival is averaged over all posterior draws and clipped to
        ``[1e-6, 1]``. ``eval_times`` are in the original time units.
        """
        if self.beta_samples is None or len(self.cutoffs) == 0:
            raise ValueError("Model must be fitted before calling predict_survival().")

        X_mat = X[self.feature_names].to_numpy(dtype=float, copy=True)
        scaled_times = np.asarray(eval_times, dtype=float) / self.time_scale
        if scaled_times.ndim != 1 or len(scaled_times) == 0:
            raise ValueError("eval_times must be a non-empty one-dimensional array")
        if not np.isfinite(scaled_times).all() or np.any(scaled_times < 0):
            raise ValueError("eval_times must be finite and non-negative")

        total = np.zeros((len(X_mat), len(scaled_times)), dtype=float)
        n_draws = len(self.beta_samples)
        for start in range(0, n_draws, DRAW_CHUNK_SIZE):
            stop = min(start + DRAW_CHUNK_SIZE, n_draws)
            beta = self.beta_samples[start:stop]
            hazards = self.lambda_samples[start:stop]
            cumulative = self._baseline_cumulative_hazard(
                hazards, self.cutoffs_scaled, scaled_times
            )
            exp_risk = np.exp(
                np.clip(beta @ X_mat.T, -LINEAR_PREDICTOR_CLIP, LINEAR_PREDICTOR_CLIP)
            )
            survival = np.exp(-exp_risk[:, :, None] * cumulative[:, None, :])
            total += survival.sum(axis=0)
        return np.clip(total / n_draws, 1e-6, 1.0)

    def posterior_expected_absolute_contribution(
        self, X: pd.DataFrame
    ) -> pd.DataFrame:
        """Return global feature importance ``mean_i |x_ij| * E|beta_j|``."""
        if self.beta_samples is None:
            raise ValueError("Model must be fitted before computing importance")
        x_abs_mean = np.abs(
            X[self.feature_names].to_numpy(dtype=float, copy=True)
        ).mean(axis=0)
        beta_abs_mean = np.abs(self.beta_samples).mean(axis=0)
        importance = x_abs_mean * beta_abs_mean
        return pd.DataFrame(
            {"feature": self.feature_names, "expected_abs_contribution": importance}
        ).sort_values("expected_abs_contribution", ascending=False).reset_index(drop=True)

    def posterior_expected_absolute_group_contribution(
        self,
        X: pd.DataFrame,
        feature_groups: dict[str, str],
    ) -> pd.DataFrame:
        """Return per-subject posterior ``E|sum_j x_j beta_j|`` for each feature group.

        Args:
            X: Covariates to explain, one row per subject.
            feature_groups: Source group of every model column, for example
                all indicator columns of one categorical variable.

        Returns:
            A frame indexed like ``X`` with one column per group, in order of
            first appearance.
        """
        if self.beta_samples is None:
            raise ValueError("Model must be fitted before computing importance")
        missing = [name for name in self.feature_names if name not in feature_groups]
        if missing:
            raise ValueError(f"feature groups are missing model terms: {missing}")
        X_mat = X[self.feature_names].to_numpy(dtype=float, copy=True)
        groups = list(
            dict.fromkeys(str(feature_groups[name]) for name in self.feature_names)
        )
        output = np.zeros((len(X_mat), len(groups)), dtype=float)
        for group_index, group in enumerate(groups):
            term_indices = np.asarray(
                [
                    index
                    for index, name in enumerate(self.feature_names)
                    if str(feature_groups[name]) == group
                ],
                dtype=int,
            )
            total = np.zeros(len(X_mat), dtype=float)
            for start in range(0, len(self.beta_samples), DRAW_CHUNK_SIZE):
                beta = self.beta_samples[start : start + DRAW_CHUNK_SIZE, term_indices]
                contributions = beta @ X_mat[:, term_indices].T
                total += np.abs(contributions).sum(axis=0)
            output[:, group_index] = total / len(self.beta_samples)
        return pd.DataFrame(output, columns=groups, index=X.index)

    def predict_survival_with_credible_intervals(
        self, X: pd.DataFrame, eval_times: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return posterior-mean survival with 95% credible bounds.

        Unlike :meth:`predict_survival`, this keeps every draw in memory and
        does not clip the linear predictor.

        Returns:
            ``(mean, lower_95, upper_95)``, each of shape (n_samples, n_times)
            and clipped to ``[1e-6, 1]``.
        """
        if self.beta_samples is None or len(self.cutoffs) == 0:
            raise ValueError("Model must be fitted before calling predict_survival().")

        X_mat = X[self.feature_names].values.astype(float)
        n_samples = len(X_mat)
        n_times = len(eval_times)
        n_draws = len(self.beta_samples)

        scaled_times = np.asarray(eval_times, dtype=float) / self.time_scale
        baseline_cumulative = self._baseline_cumulative_hazard(
            self.lambda_samples, self.cutoffs_scaled, scaled_times
        )
        exp_risk = np.exp(np.dot(self.beta_samples, X_mat.T))  # (n_draws, n_samples)

        survival_draws = np.zeros((n_draws, n_samples, n_times), dtype=float)
        for draw in range(n_draws):
            cumulative = np.outer(exp_risk[draw], baseline_cumulative[draw])
            survival_draws[draw] = np.exp(-cumulative)

        mean = np.clip(np.mean(survival_draws, axis=0), 1e-6, 1.0)
        lower = np.clip(np.percentile(survival_draws, 2.5, axis=0), 1e-6, 1.0)
        upper = np.clip(np.percentile(survival_draws, 97.5, axis=0), 1e-6, 1.0)
        return mean, lower, upper

    def get_summary(self) -> pd.DataFrame:
        """Return the posterior hazard-ratio summary, one row per feature."""
        return self.summary_df if self.summary_df is not None else pd.DataFrame()
