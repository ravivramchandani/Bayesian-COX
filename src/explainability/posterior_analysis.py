"""Built-in explainability signals derived from the Bayesian posterior."""

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr


def posterior_importance(model) -> pd.DataFrame:
    """Rank features by the posterior evidence that their effect is non-zero.

    The score is |P(beta > 0) - 0.5| * 2, which is 0 when the posterior is
    centred on zero and approaches 1 when the sign of the effect is certain.
    Unlike a point estimate this accounts for the width of the posterior.
    """
    if model.beta_samples is None:
        raise RuntimeError("Model is not fitted. Call fit() first.")

    beta = model.beta_samples
    prob_positive = (beta > 0).mean(axis=0)

    return (
        pd.DataFrame(
            {
                "feature": model.feature_names,
                "posterior_mean": beta.mean(axis=0),
                "hazard_ratio": np.exp(beta.mean(axis=0)),
                "credible_lower": np.percentile(np.exp(beta), 2.5, axis=0),
                "credible_upper": np.percentile(np.exp(beta), 97.5, axis=0),
                "prob_direction": np.abs(prob_positive - 0.5) * 2,
                "excludes_null": (
                    (np.percentile(np.exp(beta), 2.5, axis=0) > 1.0)
                    | (np.percentile(np.exp(beta), 97.5, axis=0) < 1.0)
                ),
            }
        )
        .sort_values("prob_direction", ascending=False)
        .reset_index(drop=True)
    )


def compare_rankings(
    built_in: pd.DataFrame,
    post_hoc: pd.DataFrame,
    built_in_score: str,
    post_hoc_score: str = "mean_abs_shap",
    top_k: int = 5,
) -> dict:
    """Agreement between a built-in posterior ranking and a SHAP ranking.

    Returns Spearman and Kendall rank correlation over all features plus the
    overlap of the top-k sets, which is what a clinician reading a short list
    of risk factors would actually notice.
    """
    merged = built_in[["feature", built_in_score]].merge(
        post_hoc[["feature", post_hoc_score]], on="feature", how="inner"
    )
    if len(merged) < 3:
        raise ValueError("Need at least three shared features to compare rankings.")

    rho, rho_p = spearmanr(merged[built_in_score], merged[post_hoc_score])
    tau, tau_p = kendalltau(merged[built_in_score], merged[post_hoc_score])

    top_built_in = set(
        built_in.nlargest(top_k, built_in_score)["feature"]
    )
    top_post_hoc = set(post_hoc.nlargest(top_k, post_hoc_score)["feature"])

    return {
        "n_features": len(merged),
        "spearman_rho": float(rho),
        "spearman_p": float(rho_p),
        "kendall_tau": float(tau),
        "kendall_p": float(tau_p),
        "top_k": top_k,
        "top_k_overlap": len(top_built_in & top_post_hoc),
        "top_k_jaccard": len(top_built_in & top_post_hoc)
        / len(top_built_in | top_post_hoc),
        "built_in_top_k": sorted(top_built_in),
        "post_hoc_top_k": sorted(top_post_hoc),
    }
