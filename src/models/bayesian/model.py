"""Bayesian piecewise-exponential proportional-hazards model in PyMC.

The confirmatory pipeline fits this model once per outer-training fold and
coefficient prior; ``src.pipelines`` builds it from
``config/confirmatory.yaml``. The model has four parts.

Time scale
    Follow-up times are divided by the median training event time, so one
    scaled unit is one median event time. The baseline prior is expressed in
    the same relative time unit for cohorts measured in days (GBSG2, WHAS500)
    and in months (METABRIC).

Baseline hazard
    The scaled axis is cut into ``n_intervals`` intervals (6 in the
    confirmatory run) at quantiles of the training event times. The hazard
    is constant within interval m, with ``log lambda_m ~ Normal(-2, 2^2)``
    independently per interval (standard deviation 2, prior median hazard
    ``exp(-2)``, about 0.14 per median event time).

Proportional hazards
    Subject i's hazard in interval m is ``lambda_m * exp(x_i beta)``. The
    coefficient prior on ``beta`` is Normal, regularised horseshoe or
    continuous spike-and-slab; :class:`BayesianCoxModel` gives each exactly.

Likelihood
    The likelihood is written in its equivalent Poisson form (see
    ``piecewise.py``): every subject-interval pair with positive exposure is
    one Poisson count (1 if the subject's event falls in that interval,
    otherwise 0) with mean ``exposure * lambda_m * exp(x_i beta)``. This is a
    full likelihood with an estimated piecewise-constant baseline hazard, not
    the Cox partial likelihood. The class keeps the name ``BayesianCoxModel``
    because ``beta`` has the Cox meaning of log hazard ratios.

Markov chain Monte Carlo (MCMC) draws are obtained with the No-U-Turn
Sampler (NUTS). Automatic
differentiation variational inference (ADVI) is available for exploration
and reports no convergence diagnostics.
"""

import numpy as np
import pandas as pd
import pymc as pm

from src.models.base import BaseSurvivalModel
from src.models.bayesian.diagnostics import check_convergence
from src.models.bayesian.piecewise import _add_poisson_likelihood, _poisson_rows
from src.models.bayesian.predictive_checks import LINEAR_PREDICTOR_CLIP, _PredictiveChecksMixin

SUPPORTED_PRIORS = ("normal", "horseshoe", "spike_slab")

# Posterior draws processed at once in the prediction loops, to bound memory.
DRAW_CHUNK_SIZE = 256


def _validate_training_data(X_mat: np.ndarray, y_time: np.ndarray, y_event: np.ndarray) -> None:
    """Check row counts, finite covariates/times, positive times and event count."""
    if len(X_mat) != len(y_time) or len(y_time) != len(y_event):
        raise ValueError("X, y_time and y_event must contain the same rows")
    if not np.isfinite(X_mat).all() or not np.isfinite(y_time).all():
        raise ValueError("Bayesian model inputs must be finite after preprocessing")
    if np.any(y_time <= 0):
        raise ValueError("Survival durations must be strictly positive")
    if int(y_event.sum()) < 2:
        raise ValueError("Bayesian model requires at least two observed events")


class BayesianCoxModel(_PredictiveChecksMixin, BaseSurvivalModel):
    """Bayesian piecewise-exponential proportional-hazards model.

    Times are divided by the median training event time before fitting, so the
    baseline hazards ``lambda_m`` are per median event time. Their prior is
    ``log lambda_m ~ Normal(-2, 2^2)`` (mean -2, standard deviation 2),
    independently per interval. With ``noncentered_baseline=True`` the same
    prior is written as ``log lambda_m = -2 + 2 * log_lambda_offset_m`` with a
    standard normal offset; the confirmatory protocol uses this form only as
    its second refit after failed diagnostics.

    Coefficient priors (``coefficient_prior``). The code defaults for
    ``prior_params`` equal the primary values in ``config/confirmatory.yaml``,
    which are the values shown. ``Normal(m, s^2)`` has standard deviation s.

    - ``normal``: ``beta_j ~ Normal(mu, sigma^2)``, with mu = 0 and sigma = 1.
    - ``horseshoe``: a regularised horseshoe (Piironen and Vehtari, 2017) in
      non-centred form:

      - global scale ``tau ~ half-Student-t(2 df, scale tau0 = 0.1)``;
      - local scales ``lam_j ~ half-Student-t(2 df, scale 1)``;
      - slab ``c2 ~ InvGamma(slab_df / 2, slab_df * slab_scale^2 / 2)``, which
        is ``InvGamma(2, 8)`` with slab_df = 4 and slab_scale = 2;
      - ``lam_tilde_j^2 = c2 lam_j^2 / (c2 + tau^2 lam_j^2)``;
      - ``beta_j = z_j * tau * lam_tilde_j`` with ``z_j ~ Normal(0, 1)``.

      Small ``tau * lam_j`` leaves ``lam_tilde_j`` close to ``lam_j``, as in
      the plain horseshoe; large ``tau * lam_j`` caps the coefficient scale
      at ``sqrt(c2)``, so large coefficients are regularised by the slab.
      The local scales are half-t with 2 degrees of freedom, not half-Cauchy,
      so in Piironen and Vehtari's terms this is regularised hierarchical
      shrinkage rather than a strict horseshoe. ``tau0`` is fixed, not set by
      their effective-number-of-parameters rule.
    - ``spike_slab``: a continuous relaxation of spike-and-slab, because NUTS
      cannot sample a discrete inclusion indicator. The weight
      ``gamma_j ~ Beta(alpha = 1, beta_conc = 1)`` (uniform on [0, 1]) mixes
      the spike and slab variances,
      ``sd_j^2 = (1 - gamma_j) spike_sd^2 + gamma_j slab_sd^2`` with
      spike_sd = 0.05 and slab_sd = 2, and ``beta_j = z_j * sd_j`` with
      ``z_j ~ Normal(0, 1)``. The posterior mean of ``gamma_j`` is the
      auxiliary mixing signal; it is not a discrete inclusion probability.

    The non-centred forms sample the standard normal ``z`` rather than
    ``beta`` itself. This makes ``z`` independent of its prior scale and can
    reduce the funnel-shaped geometry that NUTS explores poorly.

    The priors define the PyMC variables ``beta``, ``tau``, ``lam``, ``c2``,
    ``gamma``, ``z``, ``log_lambda`` and ``log_lambda_offset``. Their names,
    shapes and creation order are part of the frozen protocol, because
    seeding and the stored traces depend on them.

    Args:
        n_intervals: Number of baseline-hazard intervals; the confirmatory
            run uses 6 and the robustness analysis also 4 and 10.
        inference_method: ``"advi"`` selects ADVI; any other value runs NUTS.
        n_advi_iterations: ADVI optimisation steps.
        draws: Retained draws per chain (after warm-up).
        tune: NUTS warm-up (tuning) iterations per chain, discarded.
        chains: Number of MCMC chains.
        cores: Number of chains run in parallel; 1 runs them sequentially.
        target_accept: NUTS target acceptance probability. Higher values
            encourage smaller steps and can reduce divergent transitions.
        random_state: Seed for the prior predictive draws, the sampler and
            the posterior predictive replicates.
        coefficient_prior: ``"normal"``, ``"horseshoe"`` or ``"spike_slab"``
            (case-insensitive).
        prior_params: Hyperparameter overrides; absent keys use the defaults
            above.
        noncentered_baseline: Use the non-centred baseline form.

    After :meth:`fit`, ``beta_samples`` has shape (n_pooled_draws,
    n_features) and ``lambda_samples`` shape (n_pooled_draws, n_intervals),
    with hazards on the scaled time axis. NUTS pools chains * draws
    retained draws; ADVI produces draws from its approximation. ``cutoffs``
    holds cut points in the cohort's own unit and ``cutoffs_scaled`` on the
    scaled axis.
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
    ) -> None:
        """Store prior/sampling settings and initialise posterior state."""
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

    def fit(self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray) -> "BayesianCoxModel":
        """Fit NUTS (default) or ADVI and store posterior summaries.

        After fitting, ``diagnostics`` holds the convergence checks,
        ``prior_predictive_summary`` and ``posterior_predictive_summary`` hold
        the model checks, and ``beta_samples``/``lambda_samples`` hold pooled
        posterior draws. ADVI reports ``converged=None``. This method records
        failed diagnostics; the enclosing pipeline decides on refits or exclusion.

        Args:
            X: Preprocessed covariates of shape (n_subjects, n_features).
            y_time: Strictly positive follow-up times of shape (n_subjects,),
                in the cohort's own unit (days or months).
            y_event: Indicators of shape (n_subjects,), 1 for an observed
                event and 0 for censoring; converted to integers internally.

        Returns:
            The fitted model with stored summaries and prediction arrays.

        Raises:
            ValueError: Row counts differ, covariates or times are non-finite,
                times are non-positive, the integer event-indicator sum is
                below two, the time scale cannot be derived, or the prior
                name is unsupported.
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
        """Create ``beta ~ Normal(mu, sigma^2)`` independently per coefficient."""
        return pm.Normal(
            "beta",
            mu=self.prior_params.get("mu", 0.0),
            sigma=self.prior_params.get("sigma", 1.0),
            shape=n_features,
        )

    def _regularised_horseshoe_prior(self, n_features: int):
        """Create the non-centred regularised horseshoe and return ``beta``.

        The slab caps the conditional coefficient scale, regularising large
        coefficients while small coefficients retain local/global shrinkage.
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
        """Create the continuous spike-and-slab relaxation; return ``beta``.

        A weight near 0 gives the coefficient the narrow spike scale
        (concentrated near zero); a weight near 1 gives it the wide slab scale.
        """
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
        """Create ``log_lambda ~ Normal(-2, 2^2)``, centred or non-centred."""
        if self.noncentered_baseline:
            log_lambda_offset = pm.Normal("log_lambda_offset", mu=0.0, sigma=1.0, shape=n_intervals)
            return pm.Deterministic("log_lambda", -2.0 + 2.0 * log_lambda_offset)
        return pm.Normal("log_lambda", mu=-2.0, sigma=2.0, shape=n_intervals)

    def _sample_prior_predictive(self):
        """Draw ``beta`` and ``log_lambda`` from the prior (between 50 and 200 draws)."""
        return pm.sample_prior_predictive(
            draws=min(200, max(50, self.draws)),
            var_names=["beta", "log_lambda"],
            random_seed=self.random_state,
            return_inferencedata=True,
        )

    def _sample_posterior(self):
        """Return posterior draws from NUTS, or from a fitted ADVI approximation.

        NUTS warm-up draws are discarded, so the returned trace and its
        sampler statistics hold only the retained draws.
        """
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
        """Tabulate posterior coefficient and hazard-ratio summaries per feature.

        The 95% credible bounds are percentiles of the hazard-ratio draws.
        Rows are sorted by posterior mean hazard ratio, largest first.
        """
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

    def _compute_diagnostics(self) -> dict:
        """Return the all-variable convergence gate, or ``converged=None`` for ADVI.

        NUTS diagnostics are defined in :mod:`src.models.bayesian.diagnostics`.
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
        """Return the per-feature prior-specific auxiliary signal.

        For the spike-and-slab prior this is the posterior mean of the
        continuous inclusion weight ``gamma``, sorted from largest to
        smallest. For the horseshoe it is the posterior mean of the
        local-scale shrinkage proxy ``1 / (1 + lam^2)``, sorted from smallest
        to largest proxy value. That proxy is not the full posterior
        shrinkage factor, which also depends on the global scale, slab
        regularisation and likelihood. The Normal prior has no auxiliary signal.

        Returns:
            A frame with ``feature`` and ``continuous_inclusion_weight`` or
            ``local_scale_shrinkage_proxy``, according to the prior;
            ``None`` for the Normal prior.

        Raises:
            RuntimeError: The model has not been fitted.
        """
        if self.idata is None:
            raise RuntimeError("Model is not fitted. Call fit() first.")

        posterior = self.idata.posterior

        if self.coefficient_prior == "spike_slab":
            gamma = posterior["gamma"].values.reshape(-1, len(self.feature_names))
            return (
                pd.DataFrame(
                    {
                        "feature": self.feature_names,
                        "continuous_inclusion_weight": gamma.mean(axis=0),
                    }
                )
                .sort_values("continuous_inclusion_weight", ascending=False)
                .reset_index(drop=True)
            )

        if self.coefficient_prior == "horseshoe":
            lam = posterior["lam"].values.reshape(-1, len(self.feature_names))
            shrinkage = 1.0 / (1.0 + lam**2)
            return (
                pd.DataFrame(
                    {
                        "feature": self.feature_names,
                        "local_scale_shrinkage_proxy": shrinkage.mean(axis=0),
                    }
                )
                .sort_values("local_scale_shrinkage_proxy")
                .reset_index(drop=True)
            )

        return None

    def predict_risk(self, X: pd.DataFrame) -> np.ndarray:
        """Return the posterior-mean linear predictor ``x E[beta]``, one per row.

        The score is on the log hazard-ratio scale (not exponentiated), with
        no baseline term: it compares each subject with one whose
        preprocessed covariates are all zero. Because the predictor is linear
        it equals the posterior mean of ``x beta``. Higher values mean higher
        hazard.

        Args:
            X: Preprocessed covariates containing every fitted feature column.

        Returns:
            Log hazard-ratio scores of shape (n_subjects,).

        Raises:
            ValueError: The model has not been fitted.
        """
        if self.beta_samples is None:
            raise ValueError("Model must be fitted before calling predict_risk().")
        X_mat = X[self.feature_names].values.astype(float)
        mean_beta = np.mean(self.beta_samples, axis=0)
        return np.dot(X_mat, mean_beta)

    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Return posterior-mean survival ``S(t | x)`` of shape (n_samples, n_times).

        For each posterior draw, ``S(t | x) = exp(-H0(t) exp(x beta))``, where
        ``H0`` is the piecewise-linear baseline cumulative hazard; beyond the
        last cut point the last interval's hazard continues. The survival
        curves, not the parameters, are averaged over all draws, and the
        result is clipped to ``[1e-6, 1]``. The linear predictor is clipped to
        ``[-30, 30]`` before exponentiation to avoid overflow. Draws are
        processed in chunks of ``DRAW_CHUNK_SIZE`` to bound memory.

        Args:
            X: Preprocessed covariates containing every fitted feature column.
            eval_times: Non-empty finite, non-negative times of shape
                (n_times,) in the cohort's own unit; their order is retained.

        Returns:
            Mean survival probabilities of shape (n_subjects, n_times).

        Raises:
            ValueError: The model is not fitted, or ``eval_times`` is empty,
                not one-dimensional, non-finite or negative.
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

    def posterior_expected_absolute_contribution(self, X: pd.DataFrame) -> pd.DataFrame:
        """Return mean absolute posterior contribution for each model term.

        For term j, ``|x_ij beta_j| = |x_ij| |beta_j|``, so the mean over
        subjects of ``E|x_ij beta_j|`` is ``mean_i |x_ij| * E|beta_j|``.
        Grouped importance is provided by
        :meth:`posterior_expected_absolute_group_contribution`.

        Args:
            X: Preprocessed covariates to explain, containing all fitted columns.

        Returns:
            A frame with ``feature`` and ``expected_abs_contribution`` on
            the log hazard-ratio scale, sorted by descending contribution.

        Raises:
            ValueError: The model has not been fitted.
        """
        if self.beta_samples is None:
            raise ValueError("Model must be fitted before computing importance")
        x_abs_mean = np.abs(X[self.feature_names].to_numpy(dtype=float, copy=True)).mean(axis=0)
        beta_abs_mean = np.abs(self.beta_samples).mean(axis=0)
        importance = x_abs_mean * beta_abs_mean
        return (
            pd.DataFrame({"feature": self.feature_names, "expected_abs_contribution": importance})
            .sort_values("expected_abs_contribution", ascending=False)
            .reset_index(drop=True)
        )

    def posterior_expected_absolute_group_contribution(
        self,
        X: pd.DataFrame,
        feature_groups: dict[str, str],
    ) -> pd.DataFrame:
        """Return per-subject posterior ``E|sum_j x_j beta_j|`` for each feature group.

        The signed contributions of a group's terms are summed within each
        draw before the absolute value is taken, so indicator columns of one
        categorical variable count as one source variable.

        Args:
            X: Covariates to explain, one row per subject.
            feature_groups: Source group of every model column, for example
                all indicator columns of one categorical variable. Extra
                keys are ignored.

        Returns:
            A frame indexed like ``X`` with one column per group, in order of
            first appearance.

        Raises:
            ValueError: The model is not fitted, or a model column has no group.
        """
        if self.beta_samples is None:
            raise ValueError("Model must be fitted before computing importance")
        missing = [name for name in self.feature_names if name not in feature_groups]
        if missing:
            raise ValueError(f"feature groups are missing model terms: {missing}")
        X_mat = X[self.feature_names].to_numpy(dtype=float, copy=True)
        groups = list(dict.fromkeys(str(feature_groups[name]) for name in self.feature_names))
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
        """Return posterior-mean survival with pointwise 95% credible bounds.

        The bounds are the 2.5th and 97.5th percentiles of the per-draw
        survival at each subject and time. Unlike :meth:`predict_survival`,
        this keeps every draw in memory (n_draws * n_samples * n_times values)
        and does not clip the linear predictor.

        Args:
            X: Preprocessed covariates containing every fitted feature column.
            eval_times: Finite, non-negative times of shape (n_times,) in
                the cohort's own unit. This compatibility interface relies
                on callers to supply valid times.

        Returns:
            ``(mean, lower_95, upper_95)``, each of shape (n_samples, n_times)
            and clipped to ``[1e-6, 1]``.

        Raises:
            ValueError: The model has not been fitted.
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

    def get_mcmc_diagnostics(self) -> pd.DataFrame:
        """Return the legacy all-parameter summary with readable feature names.

        ``diagnostics`` is the confirmatory all-parameter gate. This method
        retains the table interface used by older callers: the full ArviZ
        summary (posterior statistics and diagnostics, with ArviZ's default
        rounding) plus a ``feature`` column that names each ``beta[j]`` row.
        Returns an empty frame before fitting.

        Returns:
            A full ArviZ summary with ``parameter`` and ``feature`` columns,
            or an empty data frame when no posterior is available.
        """
        import re

        import arviz as az

        if self.idata is None:
            return pd.DataFrame()
        if "posterior" not in self.idata:
            return pd.DataFrame()

        summary = az.summary(self.idata)
        summary = summary.reset_index()
        summary.columns = ["parameter"] + list(summary.columns[1:])

        def map_param_name(param_str):
            """Return the feature name for ``beta[j]``, or the label unchanged."""
            match = re.search(r"beta\[(\d+)\]", param_str)
            if match:
                idx = int(match.group(1))
                if 0 <= idx < len(self.feature_names):
                    return self.feature_names[idx]
            return param_str

        summary["feature"] = summary["parameter"].apply(map_param_name)
        return summary

    def get_summary(self) -> pd.DataFrame:
        """Return the stored posterior hazard-ratio summary.

        Returns:
            One row per feature with coefficient means, hazard-ratio means,
            medians and standard deviations, percentile 95% credible bounds
            and ``Prob(HR > 1)``. An empty frame is returned before fitting.
        """
        return self.summary_df if self.summary_df is not None else pd.DataFrame()
