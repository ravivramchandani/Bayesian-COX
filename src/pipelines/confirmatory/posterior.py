"""Collect coefficients, posterior visualisation snapshots and model-specific details for stored cells.

:mod:`cells` calls :func:`_model_details` after a successful fit, and
:mod:`fitting` calls :func:`_posterior_trace_snapshot` for each
Bayesian attempt that fails the diagnostic gate. Both read the fitted model only; nothing is refitted.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.models.bayesian.model import BayesianCoxModel
from src.statistics.hypothesis_tests import holm_adjust


def _posterior_trace_snapshot(model: BayesianCoxModel) -> dict[str, Any]:
    """Archive a deterministic thinned trace for pure visual rendering.

    Numerical diagnostics always use every retained draw in ``model.idata``;
    this snapshot is only for trace and marginal plots in the supplement.
    It keeps every chain and at most 250 evenly spaced draw indices of every
    posterior variable.

    Returns:
        A mapping with the draw indices kept and, per variable, its dimension
        names and thinned values (chains first, then kept draws).
    """
    posterior = model.idata.posterior
    n_draws = int(posterior.sizes["draw"])
    draw_indices = np.linspace(0, n_draws - 1, min(250, n_draws), dtype=int)
    variables: dict[str, Any] = {}
    for name in posterior.data_vars:
        data = posterior[name]
        values = np.asarray(data.isel(draw=draw_indices).values, dtype=float)
        variables[name] = {
            "dims": list(data.dims),
            "values": values,
        }
    return {
        "purpose": "visualisation_only_full_trace_used_for_numeric_diagnostics",
        "draw_indices": draw_indices,
        "variables": variables,
    }


def _model_details(
    model: Any,
    model_key: str,
    x_train: pd.DataFrame,
    train_time: np.ndarray,
    train_event: np.ndarray,
    x_validation: pd.DataFrame,
    feature_groups: dict[str, str],
) -> dict[str, Any]:
    """Collect model-specific diagnostics and explanations without refitting.

    - Cox proportional hazards (PH): the coefficient table and a per-covariate
      PH test on scaled Schoenfeld residuals against rank-transformed time,
      with Holm-adjusted p-values across the covariates of this fit.
    - Random survival forest: the implementation name and feature count only;
      the fitted forest is not stored.
    - DeepSurv: the training configuration and per-epoch training log.
    - Bayesian models: sampler diagnostics, prior and posterior predictive
      summaries, the coefficient summary, posterior expected absolute
      contributions (per feature, and per source-variable group for every
      validation subject), the prior-specific auxiliary signal (``None`` for
      the normal prior), posterior-mean coefficients and a thinned trace.

    Args:
        model: The fitted model.
        model_key: One of :data:`~.options.MODEL_KEYS`.
        x_train: Preprocessed outer-training features (used by the PH test).
        train_time: Outer-training follow-up times (used by the PH test).
        train_event: Outer-training event indicators (used by the PH test).
        x_validation: Preprocessed validation features, the explanation target
            for the Bayesian contributions.
        feature_groups: Map from processed column to its source variable.

    Returns:
        A mapping for the cell writer, possibly containing NumPy arrays; empty
        for an unknown model key.
    """
    if model_key == "cox_ph":
        summary = model.summary().to_dict(orient="records")
        ph = model.proportional_hazards_test(x_train, train_time, train_event).to_dict(
            orient="records"
        )
        adjusted, rejected = holm_adjust([row["p"] for row in ph])
        for row, adjusted_p, reject in zip(ph, adjusted, rejected, strict=True):
            row["holm_adjusted_p"] = adjusted_p
            row["holm_reject_0_05"] = reject
        return {"coefficient_summary": summary, "ph_test": ph}
    if model_key == "random_survival_forest":
        return {
            "implementation": "sksurv.ensemble.RandomSurvivalForest",
            "n_features": len(model.feature_names),
        }
    if model_key == "deepsurv":
        return {
            "training_configuration": model.get_summary().to_dict(orient="records"),
            "training_log": model.training_log.to_dict(orient="records"),
        }
    if model_key.startswith("bayesian_"):
        inclusion = model.inclusion_signal()
        grouped_contribution = model.posterior_expected_absolute_group_contribution(
            x_validation, feature_groups
        )
        return {
            "diagnostics": model.diagnostics,
            "prior_predictive": model.prior_predictive_summary,
            "posterior_predictive": model.posterior_predictive_summary,
            "coefficient_summary": model.get_summary().to_dict(orient="records"),
            "posterior_expected_absolute_contribution": (
                model.posterior_expected_absolute_contribution(x_validation).to_dict(
                    orient="records"
                )
            ),
            "posterior_expected_absolute_group_contribution_by_subject": {
                "definition": (
                    "E_posterior(|sum of x_j beta_j within source group|) "
                    "for each outer-validation subject"
                ),
                "group_names": list(grouped_contribution.columns),
                "values": grouped_contribution.to_numpy(dtype=float),
            },
            "inclusion_signal": inclusion.to_dict(orient="records")
            if inclusion is not None
            else None,
            "posterior_mean_beta": dict(
                zip(
                    model.feature_names,
                    np.mean(model.beta_samples, axis=0).tolist(),
                    strict=True,
                )
            ),
            "posterior_trace_snapshot": _posterior_trace_snapshot(model),
        }
    return {}
