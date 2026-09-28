"""Model-conditional explanation agreement and stability for research question 3 (RQ3).

The package reads a completed, immutable confirmatory run and, for every
interpretable Bayesian Cox cell, compares two grouped global importance
rankings of the clinical source variables:

- the intrinsic ranking, posterior expected absolute group contribution
  ``E_s|sum_{j in g} x_ij beta_j^(s)|`` averaged over the explained subjects,
  which the confirmatory run stored from every posterior draw; and
- the post-hoc ranking, grouped mean absolute SHAP (SHapley Additive
  exPlanations) attribution computed on the same model's posterior-mean
  linear risk score.

A secondary comparison replaces the post-hoc ranking with SHAP on the paired
frozen Cox proportional-hazards (PH) model. No model is fitted or refitted.

``scripts/run_confirmatory_explainability.py`` calls :func:`analyze_frozen_run`
and saves its result with :func:`write_explainability_result`;
``src/rendering`` later reads that result. The stages, in call order, are
``source_run`` (verify and load), ``sampling`` (choose subjects and
background), ``cell_explanation`` (compute SHAP and read stored
contributions), ``stability`` (convergence gates), ``uncertainty``
(three-stage bootstrap) and ``result`` (assemble). ``protocol`` holds the
frozen settings.

:func:`posterior_importance`, :func:`compare_rankings` and
:func:`shap_importance` are older feature-level entry points that the
confirmatory analysis does not call.
"""

from .frozen_cells import (
    ExplanationProtocol,
    SamplingBudget,
    analyze_frozen_run,
    write_explainability_result,
)
from .posterior_analysis import (
    compare_group_rankings,
    compare_rankings,
    grouped_posterior_contribution,
    posterior_importance,
    recover_posterior_mean_abs_beta,
)
from .shap_analysis import (
    exact_linear_shap_values,
    grouped_shap_importance,
    shap_importance,
)

__all__ = [
    "ExplanationProtocol",
    "SamplingBudget",
    "analyze_frozen_run",
    "compare_group_rankings",
    "compare_rankings",
    "exact_linear_shap_values",
    "grouped_posterior_contribution",
    "grouped_shap_importance",
    "posterior_importance",
    "recover_posterior_mean_abs_beta",
    "shap_importance",
    "write_explainability_result",
]
