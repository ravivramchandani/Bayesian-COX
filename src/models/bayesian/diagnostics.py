"""MCMC convergence diagnostics for fitted Bayesian survival models.

``BayesianCoxModel`` calls :func:`check_convergence` after every NUTS fit.
The confirmatory pipeline admits a fit only when every gate below passes,
and otherwise refits under its frozen diagnostic rule.

ArviZ 0.23 rounds its summary even with ``round_to=None``: R-hat to two
decimals, bulk and tail ESS to whole numbers, and MCSE to three decimals.
The gates are applied to these rounded values, which is part of the frozen
protocol. The R-hat gate therefore fails from a true R-hat of about 1.005,
not 1.01.
"""

from __future__ import annotations

from typing import Any

import arviz as az
import numpy as np
import pandas as pd

# A fit fails when rounded R-hat >= R_HAT_THRESHOLD, rounded bulk ESS <=
# ESS_BULK_THRESHOLD, divergences > MAX_DIVERGENCES, minimum BFMI <
# BFMI_THRESHOLD, or any draw reaches the maximum tree depth.
R_HAT_THRESHOLD = 1.01
ESS_BULK_THRESHOLD = 400.0
MAX_DIVERGENCES = 0
BFMI_THRESHOLD = 0.30
# PyMC's default NUTS maximum tree depth, used when the trace records only
# the depth reached and not whether the limit was hit.
DEFAULT_MAX_TREE_DEPTH = 10


def summarise(idata: Any, var_names: list[str] | None = None) -> pd.DataFrame:
    """Return rank-normalised diagnostics for selected or all parameters.

    ``round_to=None`` keeps ArviZ's default rounding (see the module
    docstring); it does not return unrounded values.
    """
    return az.summary(
        idata,
        var_names=var_names,
        kind="diagnostics",
        round_to=None,
    )


def divergences(idata: Any) -> int:
    """Return the number of divergent transitions across post-warmup chains."""
    if "diverging" not in idata.sample_stats:
        return 0
    return int(idata.sample_stats["diverging"].values.sum())


def _tree_depth_summary(idata: Any) -> tuple[int | None, int]:
    """Return the maximum tree depth reached and the number of limit hits."""
    stats = idata.sample_stats
    if "reached_max_treedepth" in stats:
        reached = np.asarray(stats["reached_max_treedepth"].values, dtype=bool)
        depth = np.asarray(stats.get("tree_depth", []))
        return (int(depth.max()) if depth.size else None, int(reached.sum()))
    if "tree_depth" not in stats:
        return None, 0
    depth = np.asarray(stats["tree_depth"].values)
    max_depth = int(depth.max())
    # A lower observed maximum is not a failure, so only draws at the default
    # limit count as hits.
    return max_depth, int((depth >= DEFAULT_MAX_TREE_DEPTH).sum())


def check_convergence(idata: Any, var_names: list[str] | None = None) -> dict[str, Any]:
    """Evaluate the convergence gates for all requested stochastic and derived values.

    A confirmatory fit passes only with rank-normalised R-hat below 1.01,
    bulk ESS above 400, no divergences, BFMI of at least 0.30 and no
    maximum-tree-depth hits. R-hat and ESS are compared after ArviZ rounding.
    Every value is computed from the trace and can be written to result
    files.

    Args:
        idata: ArviZ ``InferenceData`` with ``posterior`` and ``sample_stats``.
        var_names: Variables to check; ``None`` checks every posterior
            variable, including deterministics such as ``beta``.

    Returns:
        The diagnostic values, ``converged`` and the list of failed gates.
    """
    summary = summarise(idata, var_names=var_names)
    required = {"r_hat", "ess_bulk", "ess_tail", "mcse_mean", "mcse_sd"}
    missing = required.difference(summary.columns)
    if missing:
        raise ValueError(f"ArviZ summary is missing diagnostics: {sorted(missing)}")

    n_divergent = divergences(idata)
    n_samples = int(idata.posterior.sizes["chain"] * idata.posterior.sizes["draw"])
    divergence_rate = n_divergent / n_samples if n_samples else 0.0
    r_hat_max = float(summary["r_hat"].max())
    ess_bulk_min = float(summary["ess_bulk"].min())
    ess_tail_min = float(summary["ess_tail"].min())
    mcse_mean_max = float(summary["mcse_mean"].abs().max())
    mcse_sd_max = float(summary["mcse_sd"].abs().max())

    bfmi_values = np.asarray(az.bfmi(idata), dtype=float)
    bfmi_min = float(np.nanmin(bfmi_values)) if bfmi_values.size else float("nan")
    max_tree_depth, n_max_tree_depth = _tree_depth_summary(idata)

    failures: list[str] = []
    if not np.isfinite(r_hat_max) or r_hat_max >= R_HAT_THRESHOLD:
        failures.append(f"R-hat {r_hat_max:.4f} >= {R_HAT_THRESHOLD}")
    if not np.isfinite(ess_bulk_min) or ess_bulk_min <= ESS_BULK_THRESHOLD:
        failures.append(f"bulk ESS {ess_bulk_min:.0f} <= {ESS_BULK_THRESHOLD:.0f}")
    if n_divergent > MAX_DIVERGENCES:
        failures.append(f"{n_divergent} divergent transitions ({divergence_rate:.2%} of draws)")
    if not np.isfinite(bfmi_min) or bfmi_min < BFMI_THRESHOLD:
        failures.append(f"minimum BFMI {bfmi_min:.3f} < {BFMI_THRESHOLD:.2f}")
    if n_max_tree_depth:
        failures.append(f"{n_max_tree_depth} maximum-tree-depth hits")

    checked = list(var_names or idata.posterior.data_vars)
    return {
        "variables_checked": checked,
        "n_parameters_checked": int(len(summary)),
        "r_hat_max": r_hat_max,
        "ess_bulk_min": ess_bulk_min,
        "ess_tail_min": ess_tail_min,
        "mcse_mean_max": mcse_mean_max,
        "mcse_sd_max": mcse_sd_max,
        "n_divergent": n_divergent,
        "divergence_rate": divergence_rate,
        "bfmi_min": bfmi_min,
        "max_tree_depth": max_tree_depth,
        "n_max_tree_depth": n_max_tree_depth,
        "converged": not failures,
        "failures": failures,
    }
