"""Prior and posterior predictive checks for the Bayesian survival model.

``BayesianCoxModel.fit`` runs these checks after sampling and stores them in
``prior_predictive_summary`` and ``posterior_predictive_summary``. They use
the fitted model's time scale, cut points and draws, and do not change the
fit or its diagnostics.

- Prior predictive check: the survival implied by prior draws at 0.25, 0.5,
  1 and 2 median event times, for the baseline alone and for training
  subjects' covariates. The draws are not updated by the likelihood, but their time scale,
  interval cut points and covariates are derived from the training data.
  These checks are therefore conditional on that training-derived setup.
- Posterior predictive checks: event counts replicated from the Poisson
  likelihood, in total and per baseline interval, compared with the observed
  counts; and mean fitted survival compared with the Kaplan-Meier estimate
  at the training event-time quartiles.
"""

import numpy as np
from sksurv.nonparametric import kaplan_meier_estimator

from src.models.bayesian.piecewise import _PoissonRows

# Bound on |x beta| before exponentiation; exp(30) is about 1e13, so the clip
# prevents overflow without affecting plausible fits.
LINEAR_PREDICTOR_CLIP = 30.0
# Prior predictive times, in median training event times.
PRIOR_PREDICTIVE_SCALED_TIMES = (0.25, 0.5, 1.0, 2.0)
MAX_PRIOR_PREDICTIVE_ROWS = 512
MAX_POSTERIOR_PREDICTIVE_DRAWS = 200
# Added to the model seed so the replicate stream is separate from the sampler's.
POSTERIOR_PREDICTIVE_SEED_OFFSET = 104729


def _kaplan_meier_at(y_time: np.ndarray, y_event: np.ndarray, horizons: np.ndarray) -> np.ndarray:
    """Return right-continuous Kaplan-Meier survival at each horizon (1 before the first time)."""
    km_time, km_survival = kaplan_meier_estimator(y_event.astype(bool), y_time.astype(float))
    km_indices = np.searchsorted(km_time, horizons, side="right") - 1
    observed = np.ones(len(horizons), dtype=float)
    valid = km_indices >= 0
    observed[valid] = km_survival[km_indices[valid]]
    return observed


def _replication_summary(replicated_values: np.ndarray, observed_value: float) -> dict:
    """Compare an observed count with its posterior predictive replicates.

    The tail probability is the share of replicates at least as large as
    the observed count; ``observed_covered`` reports whether the observed
    count lies in the central 95% replicate interval.
    """
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


class _PredictiveChecksMixin:
    """Predictive checks using the arrays stored by ``BayesianCoxModel.fit``."""

    time_scale: float
    cutoffs_scaled: np.ndarray
    beta_samples: np.ndarray
    lambda_samples: np.ndarray
    random_state: int

    @staticmethod
    def _baseline_cumulative_hazard(
        hazards: np.ndarray,
        cutoffs: np.ndarray,
        times: np.ndarray,
    ) -> np.ndarray:
        """Evaluate piecewise-constant cumulative hazards for many draws.

        ``H0(t)`` is the hazard-weighted length of the completed intervals
        plus ``lambda_m * (t - c_m)`` within the current interval m. Beyond
        the last cut point the last interval's hazard is extended.

        Args:
            hazards: Baseline hazards, shape (n_draws, n_intervals).
            cutoffs: Cut points on the same time axis, length n_intervals + 1.
            times: Evaluation times on that axis.

        Returns:
            An array of shape ``(n_draws, n_times)``.
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
                result[:, column] = completed[:, -1] + hazards[:, -1] * (value - cutoffs[-1])
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
        to 512 evenly spaced training rows, to examine coefficient-prior
        predictions alongside baseline survival.

        Raises:
            RuntimeError: The coefficient and baseline draws differ in number.
            ValueError: ``X_mat`` does not match the length of ``beta``.
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
        linear = np.clip(beta @ selected.T, -LINEAR_PREDICTOR_CLIP, LINEAR_PREDICTOR_CLIP)
        population_survival = np.exp(-np.exp(linear)[:, :, None] * cumulative[:, None, :])
        return {
            "n_draws": int(len(hazards)),
            "time_scale": float(self.time_scale),
            "baseline_survival": [
                self._prior_baseline_row(scaled_time, baseline_survival[:, column])
                for column, scaled_time in enumerate(times)
            ],
            "covariate_population_survival": [
                self._prior_population_row(scaled_time, population_survival[:, :, column])
                for column, scaled_time in enumerate(times)
            ],
            "n_covariate_rows": int(len(selected)),
            "covariate_row_selection": "deterministic_evenly_spaced_training_rows",
            "finite": bool(
                np.isfinite(baseline_survival).all() and np.isfinite(population_survival).all()
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
            "proportion_subject_draws_below_0_01": float(np.mean(subject_draw_values < 0.01)),
            "proportion_subject_draws_above_0_99": float(np.mean(subject_draw_values > 0.99)),
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
        survival_rows = self._fitted_survival_check(X_mat, y_time, y_event, beta, hazards)
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
        """Replicate the Poisson counts per draw and compare with the data.

        Each draw simulates one count per likelihood row from its fitted
        Poisson mean; counts are summed in total and per baseline interval.

        Raises:
            RuntimeError: A fitted Poisson mean is non-finite.
        """
        n_intervals = hazards.shape[1]
        rng = np.random.default_rng(self.random_state + POSTERIOR_PREDICTIVE_SEED_OFFSET)
        replicated_interval_counts = np.zeros((len(beta), n_intervals), dtype=float)
        for row, (beta_draw, hazard_draw) in enumerate(zip(beta, hazards, strict=True)):
            linear_predictor = np.clip(
                rows.covariates @ beta_draw,
                -LINEAR_PREDICTOR_CLIP,
                LINEAR_PREDICTOR_CLIP,
            )
            poisson_mean = (
                rows.exposures * hazard_draw[rows.interval_index] * np.exp(linear_predictor)
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
        """Compare mean fitted survival with Kaplan-Meier at event-time quartiles.

        For each draw, fitted survival is averaged over the training
        subjects; the interval is the central 95% of those averages across
        draws. Times here are in the cohort's own unit.
        """
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
