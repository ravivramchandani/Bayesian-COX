"""Weighted complementary-log-log fits used by fixed-horizon calibration.

:func:`src.evaluation.calibration.survival_calibration_summary` calls this
module once per horizon and bootstrap replicate. The caller constructs the
IPCW (inverse probability of censoring weighted) outcomes and weights from
its training censoring distribution.

For validation subject i at horizon h, the predictor is
``x_i = log(-log S_hat(h | x_i))``, the log of the predicted cumulative
hazard, and the outcome is ``y_i = 1`` if the event occurred by h. The
calibration model is

``P(y_i = 1) = 1 - exp(-exp(a + b * x_i))``,

the complementary log-log (cloglog) link. With ``a = 0`` and ``b = 1`` it
reproduces the predicted event probability ``1 - S_hat(h | x_i)`` before
numerical clipping,
so these are the ideal values.

- The offset fit fixes ``b = 1`` and estimates ``a``, the
  calibration-in-the-large. ``exp(a)`` multiplies every predicted cumulative
  hazard: ``a > 0`` means more events were observed than predicted (risk
  underpredicted), ``a < 0`` fewer (risk overpredicted).
- The joint fit estimates an intercept and slope. A slope below 1 suggests
  excessive prediction spread after accounting for the intercept; a slope
  above 1 suggests insufficient spread. The joint intercept is the
  calibration line at ``x = 0``, where the predicted cumulative hazard is 1
  (predicted survival about 0.37), so it is read together with the slope.

Both fits minimise a numerically clipped IPCW-weighted Bernoulli
negative log-likelihood using limited-memory Broyden-Fletcher-Goldfarb-
Shanno optimisation with bounds (L-BFGS-B). The offset
intercept is bounded to [-20, 20]; the joint fit uses this intercept bound
and a slope bound of [-10, 10].
"""

import numpy as np
from scipy.optimize import minimize


def _cloglog_probability(eta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return event probability and cumulative hazard on the complementary-log-log scale.

    ``eta`` is clipped to [-30, 30] and the probability to
    [1e-12, 1 - 1e-12], so the log-likelihood stays finite.
    """
    cumulative_hazard = np.exp(np.clip(eta, -30.0, 30.0))
    probability = -np.expm1(-cumulative_hazard)
    return np.clip(probability, 1e-12, 1 - 1e-12), cumulative_hazard


def _fit_weighted_calibration(
    x: np.ndarray, y: np.ndarray, weights: np.ndarray
) -> dict[str, float]:
    """Fit the offset and joint models using positive IPCW weights.

    Args:
        x: Predicted log cumulative hazard at the horizon, one per subject.
        y: 1.0 if the event occurred by the horizon, else 0.0.
        weights: IPCW weights; zero marks an unknown outcome (censored
            before the horizon), and those subjects are excluded.

    Returns:
        ``calibration_in_the_large``, ``intercept``, ``slope``, ``n_known``
        (subjects with positive weight) and ``effective_weight`` (the sum of
        the unnormalised weights).

    Raises:
        ValueError: Fewer than ten known outcomes, or only one outcome class.
        RuntimeError: Either optimisation did not converge.
    """
    known = weights > 0
    if known.sum() < 10 or len(np.unique(y[known])) < 2:
        raise ValueError(
            "Calibration requires at least ten known horizon outcomes and both classes."
        )
    x_known = x[known]
    y_known = y[known]
    weight_known = weights[known]
    # Rescaling to mean one leaves the maximiser unchanged and keeps the
    # objective on a stable numerical scale.
    weight_known = weight_known / np.mean(weight_known)

    def negative_log_likelihood(parameters: np.ndarray, *, offset: bool) -> float:
        """Return the weighted negative log-likelihood of the offset or joint model."""
        eta = parameters[0] + x_known if offset else parameters[0] + parameters[1] * x_known
        probability, cumulative_hazard = _cloglog_probability(eta)
        # log(1 - p) = -H under the cloglog link, which avoids log(1 - p)
        # losing precision when p is small.
        log_likelihood = y_known * np.log(probability) - (1 - y_known) * cumulative_hazard
        return float(-np.sum(weight_known * log_likelihood))

    offset_fit = minimize(
        lambda value: negative_log_likelihood(value, offset=True),
        x0=np.asarray([0.0]),
        method="L-BFGS-B",
        bounds=[(-20.0, 20.0)],
        options={"ftol": 1e-12, "maxiter": 1000},
    )
    # The joint fit starts from the offset estimate with slope 1.
    joint_fit = minimize(
        lambda value: negative_log_likelihood(value, offset=False),
        x0=np.asarray([float(offset_fit.x[0]), 1.0]),
        method="L-BFGS-B",
        bounds=[(-20.0, 20.0), (-10.0, 10.0)],
        options={"ftol": 1e-12, "maxiter": 1000},
    )
    if not offset_fit.success or not joint_fit.success:
        raise RuntimeError("Fixed-horizon calibration model did not converge.")
    return {
        "calibration_in_the_large": float(offset_fit.x[0]),
        "intercept": float(joint_fit.x[0]),
        "slope": float(joint_fit.x[1]),
        "n_known": int(known.sum()),
        "effective_weight": float(np.sum(weights)),
    }
