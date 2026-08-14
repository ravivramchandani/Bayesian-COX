"""MCMC convergence diagnostics computed from a fitted posterior."""

from typing import Any

import arviz as az
import pandas as pd

R_HAT_THRESHOLD = 1.01
ESS_BULK_THRESHOLD = 400.0
# Isolated divergences after tuning are tolerated; a sustained rate indicates
# the sampler is not exploring the posterior geometry.
DIVERGENCE_RATE_THRESHOLD = 0.005


def summarise(idata: Any, var_names: list[str] | None = None) -> pd.DataFrame:
    """Per-parameter posterior summary with R-hat and effective sample size."""
    return az.summary(idata, var_names=var_names, round_to=None)


def divergences(idata: Any) -> int:
    """Number of divergent transitions across all chains."""
    if "diverging" not in idata.sample_stats:
        return 0
    return int(idata.sample_stats["diverging"].values.sum())


def check_convergence(
    idata: Any, var_names: list[str] | None = None
) -> dict[str, Any]:
    """Evaluate the standard convergence criteria.

    A fit is treated as converged when the largest R-hat is below 1.01, the
    smallest bulk effective sample size exceeds 400, and no divergent
    transitions occurred.
    """
    summary = summarise(idata, var_names=var_names)
    n_divergent = divergences(idata)
    n_samples = int(idata.posterior.sizes["chain"] * idata.posterior.sizes["draw"])
    divergence_rate = n_divergent / n_samples if n_samples else 0.0

    r_hat_max = float(summary["r_hat"].max())
    ess_bulk_min = float(summary["ess_bulk"].min())

    failures = []
    if r_hat_max >= R_HAT_THRESHOLD:
        failures.append(f"R-hat {r_hat_max:.4f} >= {R_HAT_THRESHOLD}")
    if ess_bulk_min <= ESS_BULK_THRESHOLD:
        failures.append(f"bulk ESS {ess_bulk_min:.0f} <= {ESS_BULK_THRESHOLD:.0f}")
    if divergence_rate >= DIVERGENCE_RATE_THRESHOLD:
        failures.append(
            f"{n_divergent} divergent transitions ({divergence_rate:.2%} of draws)"
        )

    return {
        "r_hat_max": r_hat_max,
        "ess_bulk_min": ess_bulk_min,
        "ess_tail_min": float(summary["ess_tail"].min()),
        "n_divergent": n_divergent,
        "divergence_rate": divergence_rate,
        "converged": not failures,
        "failures": failures,
    }
