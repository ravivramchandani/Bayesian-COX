"""Generate thesis figures from the result files and refitted models.

Writes to reports/figures/. Requires scripts/run_benchmark.py and
scripts/run_explainability.py to have run first.
"""

import argparse
import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.models.bayesian.model import BayesianCoxModel
from src.models.cox import CoxPHModel
from src.visualization.figures import (
    forest_plot,
    importance_comparison_plot,
    model_comparison_plot,
    posterior_survival_plot,
)

warnings.filterwarnings("ignore")

PROCESSED = os.path.join(PROJECT_ROOT, "data", "processed")
TABLES = os.path.join(PROJECT_ROOT, "reports", "tables")
FIGURES = os.path.join(PROJECT_ROOT, "reports", "figures")

DATASETS = ["gbsg2", "whas500", "metabric"]


def load_split(dataset):
    train = pd.read_csv(os.path.join(PROCESSED, dataset, "train.csv"))
    test = pd.read_csv(os.path.join(PROCESSED, dataset, "test.csv"))
    features = [c for c in train.columns if c not in ("time", "event")]
    return train, test, features


def bayesian_summary(model) -> pd.DataFrame:
    beta = model.beta_samples
    return pd.DataFrame(
        {
            "feature": model.feature_names,
            "hazard_ratio": np.exp(beta.mean(axis=0)),
            "ci_lower": np.percentile(np.exp(beta), 2.5, axis=0),
            "ci_upper": np.percentile(np.exp(beta), 97.5, axis=0),
        }
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draws", type=int, default=1000)
    parser.add_argument("--tune", type=int, default=1000)
    parser.add_argument("--chains", type=int, default=2)
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    args = parser.parse_args()

    os.makedirs(FIGURES, exist_ok=True)
    written = []

    benchmark_path = os.path.join(TABLES, "benchmark.json")
    if os.path.exists(benchmark_path):
        with open(benchmark_path, encoding="utf-8") as f:
            benchmark = json.load(f)
        for metric, title, higher in [
            ("c_index", "Concordance index by model and cohort", True),
            ("ibs", "Integrated Brier score by model and cohort", False),
            ("mean_auc", "Mean time-dependent AUC by model and cohort", True),
        ]:
            path = os.path.join(FIGURES, f"comparison_{metric}.png")
            model_comparison_plot(benchmark, metric, title, path, higher)
            written.append(path)

    for dataset in args.datasets:
        train, test, features = load_split(dataset)
        time = train["time"].to_numpy()
        event = train["event"].to_numpy()

        cox = CoxPHModel().fit(train[features], time, event)
        path = os.path.join(FIGURES, f"cox_forest_{dataset}.png")
        forest_plot(cox.summary(), f"Cox PH hazard ratios — {dataset.upper()}", path)
        written.append(path)

        bayes = BayesianCoxModel(
            coefficient_prior="horseshoe",
            draws=args.draws,
            tune=args.tune,
            chains=args.chains,
            target_accept=0.99,
        ).fit(train[features], time, event)

        path = os.path.join(FIGURES, f"bayes_forest_{dataset}.png")
        forest_plot(
            bayesian_summary(bayes),
            f"Bayesian Cox posterior hazard ratios (horseshoe) — {dataset.upper()}",
            path,
        )
        written.append(path)

        grid = np.linspace(time.min(), np.percentile(time, 95), 60)
        mean, lower, upper = bayes.predict_survival_with_credible_intervals(
            test[features].head(1), grid
        )
        path = os.path.join(FIGURES, f"bayes_survival_{dataset}.png")
        posterior_survival_plot(
            grid,
            np.ravel(mean),
            np.ravel(lower),
            np.ravel(upper),
            f"Posterior survival with credible band — {dataset.upper()}",
            path,
        )
        written.append(path)

    explain_path = os.path.join(TABLES, "explainability.json")
    if os.path.exists(explain_path):
        with open(explain_path, encoding="utf-8") as f:
            explain = json.load(f)
        for dataset, entry in explain.items():
            for prior, block in entry["posterior"].items():
                built_in = pd.DataFrame(block["importance"])
                shap_table = pd.DataFrame(entry["shap"]["Cox PH"])
                path = os.path.join(FIGURES, f"importance_{dataset}_{prior}.png")
                importance_comparison_plot(
                    built_in,
                    shap_table,
                    "prob_direction",
                    f"Posterior signal versus SHAP ({prior}) — {dataset.upper()}",
                    path,
                )
                written.append(path)

    for path in written:
        print(f"wrote {os.path.relpath(path, PROJECT_ROOT)}")
    print(f"\n{len(written)} figures")
    return 0


if __name__ == "__main__":
    sys.exit(main())
