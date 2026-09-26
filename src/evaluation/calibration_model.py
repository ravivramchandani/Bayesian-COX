"""Weighted complementary-log-log fits used by fixed-horizon calibration.

The offset fit estimates calibration-in-the-large with slope fixed at one.
The joint fit estimates an intercept and slope. The caller constructs the
IPCW outcomes and weights from its training censoring distribution.
"""

import numpy as np
from scipy.optimize import minimize


def _cloglog_probability(eta: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return event probability and cumulative hazard on the complementary-log-log scale."""
    cumulative_hazard = np.exp(np.clip(eta, -30.0, 30.0))
    probability = -np.expm1(-cumulative_hazard)
    return np.clip(probability, 1e-12, 1 - 1e-12), cumulative_hazard


def _fit_weighted_calibration(
    x: np.ndarray, y: np.ndarray, weights: np.ndarray
) -> dict[str, float]:
    """Fit the offset and joint models using positive IPCW weights."""
    known = weights > 0
    if known.sum() < 10 or len(np.unique(y[known])) < 2:
        raise ValueError(
            "Calibration requires at least ten known horizon outcomes and both classes."
        )
    x_known = x[known]
    y_known = y[known]
    weight_known = weights[known]
    weight_known = weight_known / np.mean(weight_known)

    def negative_log_likelihood(parameters: np.ndarray, *, offset: bool) -> float:
        eta = parameters[0] + x_known if offset else parameters[0] + parameters[1] * x_known
        probability, cumulative_hazard = _cloglog_probability(eta)
        log_likelihood = y_known * np.log(probability) - (1 - y_known) * cumulative_hazard
        return float(-np.sum(weight_known * log_likelihood))

    offset_fit = minimize(
        lambda value: negative_log_likelihood(value, offset=True),
        x0=np.asarray([0.0]),
        method="L-BFGS-B",
        bounds=[(-20.0, 20.0)],
        options={"ftol": 1e-12, "maxiter": 1000},
    )
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
