"""Bayesian piecewise-exponential proportional-hazards model in PyMC.

The implementation uses the Poisson representation of a piecewise-exponential
full likelihood. It is Cox-like through its proportional-hazards linear
predictor, but it is not a Bayesian Cox partial-likelihood implementation.
"""

import arviz as az
import numpy as np
import pandas as pd
import pymc as pm

from src.models.base import BaseSurvivalModel

SUPPORTED_PRIORS = ("normal", "horseshoe", "spike_slab")


class BayesianCoxModel(BaseSurvivalModel):
    """Bayesian piecewise-exponential PH model with ADVI or NUTS inference."""

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

        self.beta_samples = None  # (S_draws, p_features)
        self.lambda_samples = None  # (S_draws, M_intervals)

    def _prepare_piecewise_data(
        self, X_mat: np.ndarray, y_time: np.ndarray, y_event: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Converts survival data to sample-interval exposures and event counts using fast 2D NumPy operations.
        """
        _n_samples, _n_features = X_mat.shape

        event_times = y_time[y_event == 1]
        if len(event_times) == 0:
            event_times = y_time

        percentiles = np.linspace(0, 100, self.n_intervals + 1)
        cutoffs = np.percentile(event_times, percentiles)
        cutoffs[0] = 0.0
        cutoffs[-1] = max(y_time.max() + 1.0, cutoffs[-1])
        cutoffs = np.unique(cutoffs)
        if len(cutoffs) - 1 < self.n_intervals:
            cutoffs = np.linspace(0, y_time.max() + 1.0, self.n_intervals + 1)

        t_starts = cutoffs[:-1]  # (M,)
        t_ends = cutoffs[1:]  # (M,)

        t_i = y_time[:, None]  # (N, 1)
        e_i = y_event[:, None]  # (N, 1)

        # Vectorized exposure calculation: max(0, min(t_i, t_end) - t_start)
        exposures = np.clip(np.minimum(t_i, t_ends) - t_starts, 0, None)

        # Vectorized event matrix: 1 if event and t_start < t_i <= t_end
        events_matrix = ((e_i == 1) & (t_i > t_starts) & (t_i <= t_ends)).astype(float)

        return cutoffs, exposures, events_matrix

    def fit(
        self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray
    ) -> "BayesianCoxModel":
        """Fits Bayesian Cox Model using PyMC ADVI Variational Inference or MCMC Sampling."""
        self.feature_names = list(X.columns)
        X_mat = X.values.astype(float)
        y_time = np.asarray(y_time, dtype=float)
        y_event = np.asarray(y_event, dtype=int)

        if len(X_mat) != len(y_time) or len(y_time) != len(y_event):
            raise ValueError("X, y_time and y_event must contain the same rows")
        if not np.isfinite(X_mat).all() or not np.isfinite(y_time).all():
            raise ValueError("Bayesian model inputs must be finite after preprocessing")
        if np.any(y_time <= 0):
            raise ValueError("Survival durations must be strictly positive")
        if int(y_event.sum()) < 2:
            raise ValueError("Bayesian model requires at least two observed events")

        event_times = y_time[y_event == 1]
        self.time_scale = float(np.median(event_times))
        if not np.isfinite(self.time_scale) or self.time_scale <= 0:
            raise ValueError("Could not derive a positive training-event time scale")
        y_time_scaled = y_time / self.time_scale

        _n_samples, n_features = X_mat.shape

        cutoffs_scaled, exposures, events_matrix = self._prepare_piecewise_data(
            X_mat, y_time_scaled, y_event
        )
        self.cutoffs_scaled = cutoffs_scaled
        self.cutoffs = cutoffs_scaled * self.time_scale
        M = len(cutoffs_scaled) - 1

        valid_mask = exposures > 0
        obs_events = events_matrix[valid_mask]
        obs_exposures = exposures[valid_mask]

        sample_idx, interval_idx = np.where(valid_mask)
        obs_X = X_mat[sample_idx]
        log_exposure = np.log(obs_exposures)

        with pm.Model() as model:
            if self.coefficient_prior == "normal":
                # Weakly-informative baseline.
                beta = pm.Normal(
                    "beta",
                    mu=self.prior_params.get("mu", 0.0),
                    sigma=self.prior_params.get("sigma", 1.0),
                    shape=n_features,
                )

            elif self.coefficient_prior == "horseshoe":
                # Regularised horseshoe (Piironen and Vehtari, 2017) in
                # non-centred form. The plain horseshoe funnels badly under
                # NUTS; the slab term c2 bounds the tails of the local scales
                # and can improve sampling geometry. The prespecified
                # diagnostics, rather than the prior form, determine whether a
                # fitted cell is admissible.
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
                lam_tilde = pm.math.sqrt(
                    c2 * lam_sq / (c2 + tau**2 * lam_sq)
                )
                z = pm.Normal("z", mu=0.0, sigma=1.0, shape=n_features)
                beta = pm.Deterministic("beta", z * tau * lam_tilde)

            elif self.coefficient_prior == "spike_slab":
                # Continuous relaxation of spike-and-slab: a discrete inclusion
                # indicator cannot be sampled by NUTS, so the indicator is
                # replaced by a continuous weight on [0, 1] mixing a narrow
                # spike variance with a wide slab variance. The posterior mean
                # of `gamma` is the inclusion signal.
                spike_sd = self.prior_params.get("spike_sd", 0.05)
                slab_sd = self.prior_params.get("slab_sd", 2.0)
                gamma = pm.Beta(
                    "gamma",
                    alpha=self.prior_params.get("alpha", 1.0),
                    beta=self.prior_params.get("beta_conc", 1.0),
                    shape=n_features,
                )
                sd = pm.math.sqrt(
                    (1.0 - gamma) * spike_sd**2 + gamma * slab_sd**2
                )
                z = pm.Normal("z", mu=0.0, sigma=1.0, shape=n_features)
                beta = pm.Deterministic("beta", z * sd)

            else:
                raise ValueError(
                    f"Unknown coefficient prior: {self.coefficient_prior}. "
                    f"Supported: {SUPPORTED_PRIORS}"
                )

            # Log-Normal priors for baseline hazards. The non-centred form is
            # distributionally identical and is reserved as the frozen second
            # diagnostic remedy when the centred parameterisation fails.
            if self.noncentered_baseline:
                log_lambda_offset = pm.Normal(
                    "log_lambda_offset", mu=0.0, sigma=1.0, shape=M
                )
                log_lambda = pm.Deterministic(
                    "log_lambda", -2.0 + 2.0 * log_lambda_offset
                )
            else:
                log_lambda = pm.Normal("log_lambda", mu=-2.0, sigma=2.0, shape=M)

            # Poisson Log-Linear Predictor
            eta = pm.math.dot(obs_X, beta)
            lambda_m = log_lambda[interval_idx]
            mu = pm.math.exp(log_exposure + lambda_m + eta)

            # Poisson Likelihood
            pm.Poisson("obs", mu=mu, observed=obs_events)

            prior_idata = pm.sample_prior_predictive(
                draws=min(200, max(50, self.draws)),
                var_names=["beta", "log_lambda"],
                random_seed=self.random_state,
                return_inferencedata=True,
            )

            if self.inference_method == "advi":
                approx = pm.fit(
                    method="advi",
                    n=self.n_advi_iterations,
                    progressbar=False,
                    random_seed=self.random_state,
                )
                self.idata = approx.sample(
                    draws=self.draws, random_seed=self.random_state
                )
            else:
                self.idata = pm.sample(
                    draws=self.draws,
                    tune=self.tune,
                    chains=self.chains,
                    cores=self.cores,
                    target_accept=self.target_accept,
                    random_seed=self.random_state,
                    progressbar=False,
                    return_inferencedata=True,
                )

        self.pymc_model = model
        self.prior_predictive_summary = self._summarise_prior_predictive(
            prior_idata, cutoffs_scaled, X_mat
        )
        self.diagnostics = self._compute_diagnostics()

        # Extract posterior samples
        posterior = self.idata.posterior
        beta_raw = posterior["beta"].values  # (chains, draws, p)
        log_lambda_raw = posterior["log_lambda"].values  # (chains, draws, M)

        self.beta_samples = beta_raw.reshape(-1, n_features)
        self.lambda_samples = np.exp(log_lambda_raw.reshape(-1, M))
        self.posterior_predictive_summary = self._summarise_posterior_predictive(
            X_mat,
            y_time,
            y_event,
            obs_X=obs_X,
            obs_exposures=obs_exposures,
            interval_idx=interval_idx,
            obs_events=obs_events,
        )

        # Build Summary DataFrame for Hazard Ratios
        summary_records = []
        for j, feat in enumerate(self.feature_names):
            b_j = self.beta_samples[:, j]
            hr_j = np.exp(b_j)

            summary_records.append(
                {
                    "feature": feat,
                    "coef (beta_mean)": float(np.mean(b_j)),
                    "exp(coef) HR Mean": float(np.mean(hr_j)),
                    "exp(coef) HR Median": float(np.median(hr_j)),
                    "HR SD": float(np.std(hr_j)),
                    "95% Credible Lower": float(np.percentile(hr_j, 2.5)),
                    "95% Credible Upper": float(np.percentile(hr_j, 97.5)),
                    "Prob(HR > 1)": float(np.mean(hr_j > 1.0)),
                }
            )

        self.summary_df = (
            pd.DataFrame(summary_records)
            .sort_values(by="exp(coef) HR Mean", ascending=False)
            .reset_index(drop=True)
        )
        return self

    @staticmethod
    def _baseline_cumulative_hazard(
        hazards: np.ndarray,
        cutoffs: np.ndarray,
        times: np.ndarray,
    ) -> np.ndarray:
        """Evaluate piecewise-constant cumulative hazards for many draws."""
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
        """Summarise full-model survival implied by the prior.

        Baseline survival is retained for interpretation. The primary check is
        conditional on a deterministic subset of processed training
        covariates, so extreme coefficient-prior predictions cannot be hidden
        by inspecting the baseline hazard alone.
        """
        log_hazard = prior_idata.prior["log_lambda"].values
        hazards = np.exp(log_hazard.reshape(-1, log_hazard.shape[-1]))
        beta_raw = prior_idata.prior["beta"].values
        beta = beta_raw.reshape(-1, beta_raw.shape[-1])
        if len(beta) != len(hazards):
            raise RuntimeError("prior coefficient and baseline draws are not aligned")
        times = np.asarray([0.25, 0.5, 1.0, 2.0], dtype=float)
        cumulative = self._baseline_cumulative_hazard(
            hazards, cutoffs_scaled, times
        )
        baseline_survival = np.exp(-cumulative)
        baseline_rows = []
        for column, scaled_time in enumerate(times):
            values = baseline_survival[:, column]
            baseline_rows.append(
                {
                    "scaled_time": float(scaled_time),
                    "time": float(scaled_time * self.time_scale),
                    "median_survival": float(np.median(values)),
                    "lower_95": float(np.percentile(values, 2.5)),
                    "upper_95": float(np.percentile(values, 97.5)),
                }
            )

        covariates = np.asarray(X_mat, dtype=float)
        if covariates.ndim != 2 or covariates.shape[1] != beta.shape[1]:
            raise ValueError("prior predictive covariates do not match beta")
        selected_indices = np.linspace(
            0, len(covariates) - 1, min(512, len(covariates)), dtype=int
        )
        selected = covariates[selected_indices]
        linear = np.clip(beta @ selected.T, -30.0, 30.0)
        population_survival = np.exp(
            -np.exp(linear)[:, :, None] * cumulative[:, None, :]
        )
        population_rows = []
        for column, scaled_time in enumerate(times):
            subject_draw_values = population_survival[:, :, column].reshape(-1)
            draw_means = population_survival[:, :, column].mean(axis=1)
            population_rows.append(
                {
                    "scaled_time": float(scaled_time),
                    "time": float(scaled_time * self.time_scale),
                    "subject_draw_median_survival": float(
                        np.median(subject_draw_values)
                    ),
                    "subject_draw_lower_95": float(
                        np.percentile(subject_draw_values, 2.5)
                    ),
                    "subject_draw_upper_95": float(
                        np.percentile(subject_draw_values, 97.5)
                    ),
                    "mean_survival_across_subjects_median": float(
                        np.median(draw_means)
                    ),
                    "proportion_subject_draws_below_0_01": float(
                        np.mean(subject_draw_values < 0.01)
                    ),
                    "proportion_subject_draws_above_0_99": float(
                        np.mean(subject_draw_values > 0.99)
                    ),
                }
            )
        return {
            "n_draws": int(len(hazards)),
            "time_scale": float(self.time_scale),
            "baseline_survival": baseline_rows,
            "covariate_population_survival": population_rows,
            "n_covariate_rows": int(len(selected)),
            "covariate_row_selection": "deterministic_evenly_spaced_training_rows",
            "finite": bool(
                np.isfinite(baseline_survival).all()
                and np.isfinite(population_survival).all()
            ),
        }

    def _summarise_posterior_predictive(
        self,
        X_mat: np.ndarray,
        y_time: np.ndarray,
        y_event: np.ndarray,
        *,
        obs_X: np.ndarray,
        obs_exposures: np.ndarray,
        interval_idx: np.ndarray,
        obs_events: np.ndarray,
    ) -> dict:
        """Archive likelihood-scale replication and fitted-survival checks."""
        from sksurv.nonparametric import kaplan_meier_estimator

        event_times = y_time[y_event == 1]
        horizons = np.quantile(event_times, [0.25, 0.5, 0.75]).astype(float)
        km_time, km_survival = kaplan_meier_estimator(
            y_event.astype(bool), y_time.astype(float)
        )
        km_indices = np.searchsorted(km_time, horizons, side="right") - 1
        observed = np.ones(len(horizons), dtype=float)
        valid = km_indices >= 0
        observed[valid] = km_survival[km_indices[valid]]

        n_available = len(self.beta_samples)
        draw_indices = np.linspace(
            0, n_available - 1, min(200, n_available), dtype=int
        )
        beta = self.beta_samples[draw_indices]
        hazards = self.lambda_samples[draw_indices]

        rng = np.random.default_rng(self.random_state + 104729)
        replicated_interval_counts = np.zeros(
            (len(draw_indices), hazards.shape[1]), dtype=float
        )
        for row, (beta_draw, hazard_draw) in enumerate(
            zip(beta, hazards, strict=True)
        ):
            linear_predictor = np.clip(obs_X @ beta_draw, -30.0, 30.0)
            poisson_mean = (
                obs_exposures
                * hazard_draw[interval_idx]
                * np.exp(linear_predictor)
            )
            if not np.isfinite(poisson_mean).all():
                raise RuntimeError(
                    "posterior predictive Poisson means must be finite"
                )
            replicated = rng.poisson(poisson_mean)
            replicated_interval_counts[row] = np.bincount(
                interval_idx,
                weights=replicated,
                minlength=hazards.shape[1],
            )

        observed_interval_counts = np.bincount(
            interval_idx,
            weights=obs_events,
            minlength=hazards.shape[1],
        )
        replicated_total = replicated_interval_counts.sum(axis=1)
        observed_total = float(obs_events.sum())

        def replication_summary(
            replicated_values: np.ndarray, observed_value: float
        ) -> dict:
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

        replicated_event_counts = {
            "likelihood": "expanded piecewise-Poisson event counts",
            "n_posterior_draws": int(len(draw_indices)),
            "total": replication_summary(replicated_total, observed_total),
            "by_baseline_interval": [
                {
                    "interval": interval + 1,
                    **replication_summary(
                        replicated_interval_counts[:, interval],
                        observed_interval_counts[interval],
                    ),
                }
                for interval in range(hazards.shape[1])
            ],
        }

        scaled_horizons = horizons / self.time_scale
        cumulative = self._baseline_cumulative_hazard(
            hazards, self.cutoffs_scaled, scaled_horizons
        )
        linear = beta @ X_mat.T
        predicted = np.empty((len(draw_indices), len(horizons)), dtype=float)
        for column in range(len(horizons)):
            survival = np.exp(
                -np.exp(linear) * cumulative[:, column][:, None]
            )
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
        return {
            "n_draws": int(len(draw_indices)),
            "replicated_event_counts": replicated_event_counts,
            "fitted_survival_check": rows,
            # Compatibility alias for pilot reporting code. This is a fitted-
            # survival comparison, not a replicated-data check.
            "survival_check": rows,
        }

    def _compute_diagnostics(self) -> dict:
        """Convergence diagnostics for the fitted posterior.

        Returns R-hat, bulk/tail ESS, MCSE, BFMI, divergences and tree-depth
        checks across all posterior variables. Variational inference does not
        produce NUTS diagnostics and is reported separately.
        """
        if self.inference_method == "advi":
            return {"method": "advi", "converged": None}

        from src.models.bayesian.diagnostics import check_convergence

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
        """Per-feature posterior signal used as the built-in explainability output.

        For the spike-and-slab prior this is the posterior mean of the
        continuous inclusion weight. For the horseshoe it is a local-scale
        shrinkage proxy, ``1 / (1 + lam^2)``; it is not the full posterior
        shrinkage factor because that also depends on the global scale, slab
        regularisation and likelihood. Returns ``None`` for the Normal prior.
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
        """Predicts posterior mean linear risk score eta = X * mean(beta)."""
        if self.beta_samples is None:
            raise ValueError("Model must be fitted before calling predict_risk().")
        X_mat = X[self.feature_names].values.astype(float)
        mean_beta = np.mean(self.beta_samples, axis=0)
        return np.dot(X_mat, mean_beta)

    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Predicts posterior mean survival probability matrix S(t | X_i)."""
        if self.beta_samples is None or len(self.cutoffs) == 0:
            raise ValueError("Model must be fitted before calling predict_survival().")

        X_mat = X[self.feature_names].to_numpy(dtype=float, copy=True)
        scaled_times = np.asarray(eval_times, dtype=float) / self.time_scale
        if scaled_times.ndim != 1 or len(scaled_times) == 0:
            raise ValueError("eval_times must be a non-empty one-dimensional array")
        if not np.isfinite(scaled_times).all() or np.any(scaled_times < 0):
            raise ValueError("eval_times must be finite and non-negative")

        total = np.zeros((len(X_mat), len(scaled_times)), dtype=float)
        chunk_size = 256
        n_draws = len(self.beta_samples)
        for start in range(0, n_draws, chunk_size):
            stop = min(start + chunk_size, n_draws)
            beta = self.beta_samples[start:stop]
            hazards = self.lambda_samples[start:stop]
            cumulative = self._baseline_cumulative_hazard(
                hazards, self.cutoffs_scaled, scaled_times
            )
            exp_risk = np.exp(np.clip(beta @ X_mat.T, -30.0, 30.0))
            survival = np.exp(
                -exp_risk[:, :, None] * cumulative[:, None, :]
            )
            total += survival.sum(axis=0)
        return np.clip(total / n_draws, 1e-6, 1.0)

    def posterior_expected_absolute_contribution(
        self, X: pd.DataFrame
    ) -> pd.DataFrame:
        """Return global posterior ``E(|x_j beta_j|)`` feature importance."""
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
        """Return per-subject posterior ``E(|sum_j x_j beta_j|)`` by group."""
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
            for start in range(0, len(self.beta_samples), 256):
                beta = self.beta_samples[start : start + 256, term_indices]
                contributions = beta @ X_mat[:, term_indices].T
                total += np.abs(contributions).sum(axis=0)
            output[:, group_index] = total / len(self.beta_samples)
        return pd.DataFrame(output, columns=groups, index=X.index)

    def predict_survival_with_credible_intervals(
        self, X: pd.DataFrame, eval_times: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Computes Posterior Mean Survival Probability Matrix along with 95% Credible Interval Bounds.
        Returns: (surv_mean, surv_lower_95, surv_upper_95)
        """
        if self.beta_samples is None or len(self.cutoffs) == 0:
            raise ValueError("Model must be fitted before calling predict_survival().")

        X_mat = X[self.feature_names].values.astype(float)
        n_samples = len(X_mat)
        m_times = len(eval_times)
        S_draws = len(self.beta_samples)

        scaled_times = np.asarray(eval_times, dtype=float) / self.time_scale
        H0_draws = self._baseline_cumulative_hazard(
            self.lambda_samples, self.cutoffs_scaled, scaled_times
        )

        risk_draws = np.dot(self.beta_samples, X_mat.T)  # (S_draws, N_samples)
        exp_risk_draws = np.exp(risk_draws)

        surv_draws = np.zeros((S_draws, n_samples, m_times), dtype=float)

        for s in range(S_draws):
            cum_h_si = np.outer(exp_risk_draws[s], H0_draws[s])
            surv_draws[s] = np.exp(-cum_h_si)

        surv_mean = np.clip(np.mean(surv_draws, axis=0), 1e-6, 1.0)
        surv_lower = np.clip(np.percentile(surv_draws, 2.5, axis=0), 1e-6, 1.0)
        surv_upper = np.clip(np.percentile(surv_draws, 97.5, axis=0), 1e-6, 1.0)

        return surv_mean, surv_lower, surv_upper

    def get_mcmc_diagnostics(self) -> pd.DataFrame:
        """
        Computes Gelman-Rubin (R-hat) and Effective Sample Size (ESS) diagnostics for regression parameters.
        Only valid if inference_method == 'mcmc' or if MCMC chains exist.
        """
        import re


        if self.idata is None:
            return pd.DataFrame()
        if "posterior" not in self.idata:
            return pd.DataFrame()

        summary = az.summary(self.idata)
        summary = summary.reset_index()
        summary.columns = ["parameter"] + list(summary.columns[1:])

        def map_param_name(param_str):
            match = re.search(r"beta\[(\d+)\]", param_str)
            if match:
                idx = int(match.group(1))
                if 0 <= idx < len(self.feature_names):
                    return self.feature_names[idx]
            return param_str

        summary["feature"] = summary["parameter"].apply(map_param_name)
        return summary

    def get_summary(self) -> pd.DataFrame:
        """Returns Posterior Summary DataFrame for Hazard Ratios and Coefficients."""
        return self.summary_df if self.summary_df is not None else pd.DataFrame()
