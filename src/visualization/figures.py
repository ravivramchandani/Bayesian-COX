"""Thesis figures generated from fitted models and result files."""

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

FIGSIZE_WIDE = (9, 5)
FIGSIZE_TALL = (7, 6)


def forest_plot(summary: pd.DataFrame, title: str, path: str) -> None:
    """Hazard ratios with credible or confidence intervals, sorted by effect."""
    data = summary.sort_values("hazard_ratio")
    y = np.arange(len(data))

    fig, ax = plt.subplots(figsize=FIGSIZE_TALL)
    ax.errorbar(
        data["hazard_ratio"],
        y,
        xerr=[
            data["hazard_ratio"] - data["ci_lower"],
            data["ci_upper"] - data["hazard_ratio"],
        ],
        fmt="o",
        color="#2b6cb0",
        ecolor="#a0aec0",
        capsize=3,
    )
    ax.axvline(1.0, color="#e53e3e", linestyle="--", linewidth=1)
    ax.set_yticks(y)
    ax.set_yticklabels(data["feature"])
    ax.set_xscale("log")
    ax.set_xlabel("Hazard ratio (log scale)")
    ax.set_title(title)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def posterior_survival_plot(
    times: np.ndarray,
    mean: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    title: str,
    path: str,
) -> None:
    """Posterior mean survival curve with a credible band."""
    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)
    ax.plot(times, mean, color="#2b6cb0", label="Posterior mean")
    ax.fill_between(
        times, lower, upper, color="#2b6cb0", alpha=0.2, label="95% credible interval"
    )
    ax.set_xlabel("Time")
    ax.set_ylabel("Survival probability")
    ax.set_ylim(0, 1)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def model_comparison_plot(
    results: dict, metric: str, title: str, path: str, higher_is_better: bool = True
) -> None:
    """Grouped bars comparing one metric across models and cohorts."""
    cohorts = list(results)
    models = list(next(iter(results.values()))["models"])

    fig, ax = plt.subplots(figsize=FIGSIZE_WIDE)
    width = 0.8 / len(models)
    x = np.arange(len(cohorts))

    for i, model in enumerate(models):
        values = [
            results[c]["models"][model].get(metric, np.nan) for c in cohorts
        ]
        ax.bar(x + i * width, values, width, label=model)

    ax.set_xticks(x + width * (len(models) - 1) / 2)
    ax.set_xticklabels([c.upper() for c in cohorts])
    ax.set_ylabel(metric.replace("_", " "))
    ax.set_title(title)
    if higher_is_better and metric.startswith("c_index"):
        ax.axhline(0.5, color="#e53e3e", linestyle="--", linewidth=1)
    ax.legend(fontsize=8, ncols=2)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def importance_comparison_plot(
    built_in: pd.DataFrame,
    post_hoc: pd.DataFrame,
    built_in_score: str,
    title: str,
    path: str,
    post_hoc_score: str = "mean_abs_shap",
    top_k: int = 10,
) -> None:
    """Built-in posterior ranking against SHAP, both rescaled to [0, 1]."""
    merged = built_in[["feature", built_in_score]].merge(
        post_hoc[["feature", post_hoc_score]], on="feature"
    )
    merged = merged.nlargest(top_k, built_in_score)

    def rescale(values):
        span = values.max() - values.min()
        return (values - values.min()) / span if span > 0 else values * 0

    y = np.arange(len(merged))
    fig, ax = plt.subplots(figsize=FIGSIZE_TALL)
    ax.barh(y - 0.2, rescale(merged[built_in_score]), 0.4, label="Posterior signal")
    ax.barh(y + 0.2, rescale(merged[post_hoc_score]), 0.4, label="SHAP")
    ax.set_yticks(y)
    ax.set_yticklabels(merged["feature"])
    ax.set_xlabel("Relative importance")
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
