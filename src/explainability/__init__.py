"""Model-conditional explanation agreement and stability."""

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
