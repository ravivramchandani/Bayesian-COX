"""Explainability: built-in posterior signals and post-hoc SHAP attribution."""

from .posterior_analysis import compare_rankings, posterior_importance
from .shap_analysis import shap_importance

__all__ = ["compare_rankings", "posterior_importance", "shap_importance"]
