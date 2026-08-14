"""Compare built-in posterior explainability against post-hoc SHAP.

For each dataset the Bayesian Cox model is fitted under each prior and its
posterior signal is compared with SHAP attributions computed on the Cox PH
and random survival forest baselines. Writes
reports/tables/explainability.json.
"""

import argparse
import json
import os
import sys
import warnings

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.explainability import compare_rankings, posterior_importance, shap_importance
from src.models.bayesian.model import BayesianCoxModel
from src.models.cox import CoxPHModel
from src.models.random_survival_forest import RandomSurvivalForestModel

warnings.filterwarnings("ignore")

DATASETS = ["gbsg2", "whas500", "metabric"]
PROCESSED = os.path.join(PROJECT_ROOT, "data", "processed")
OUT_DIR = os.path.join(PROJECT_ROOT, "reports", "tables")

PRIORS = {"normal": 0.95, "horseshoe": 0.99, "spike_slab": 0.95}

# Column holding each prior's built-in ranking score.
BUILT_IN_SCORE = {
    "normal": "prob_direction",
    "horseshoe": "prob_direction",
    "spike_slab": "prob_direction",
}


def load(dataset):
    train = pd.read_csv(os.path.join(PROCESSED, dataset, "train.csv"))
    test = pd.read_csv(os.path.join(PROCESSED, dataset, "test.csv"))
    features = [c for c in train.columns if c not in ("time", "event")]
    return train, test, features


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draws", type=int, default=2000)
    parser.add_argument("--tune", type=int, default=2000)
    parser.add_argument("--chains", type=int, default=4)
    parser.add_argument("--n-explain", type=int, default=40)
    parser.add_argument("--shap-samples", type=int, default=256)
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    results = {}

    for dataset in args.datasets:
        train, test, features = load(dataset)
        explain_set = test[features].head(args.n_explain)

        cox = CoxPHModel().fit(
            train[features], train["time"].to_numpy(), train["event"].to_numpy()
        )
        rsf = RandomSurvivalForestModel(n_estimators=200).fit(
            train[features], train["time"].to_numpy(), train["event"].to_numpy()
        )

        shap_tables = {
            "Cox PH": shap_importance(
                cox, train[features], explain_set, nsamples=args.shap_samples
            ),
            "Random Survival Forest": shap_importance(
                rsf, train[features], explain_set, nsamples=args.shap_samples
            ),
        }

        entry = {
            "n_features": len(features),
            "shap": {k: v.to_dict("records") for k, v in shap_tables.items()},
            "posterior": {},
            "agreement": {},
        }

        for prior, target_accept in PRIORS.items():
            model = BayesianCoxModel(
                coefficient_prior=prior,
                draws=args.draws,
                tune=args.tune,
                chains=args.chains,
                target_accept=target_accept,
            ).fit(train[features], train["time"].to_numpy(), train["event"].to_numpy())

            built_in = posterior_importance(model)
            entry["posterior"][prior] = {
                "importance": built_in.to_dict("records"),
                "diagnostics": model.diagnostics,
            }

            sparsity = model.inclusion_signal()
            if sparsity is not None:
                entry["posterior"][prior]["sparsity_signal"] = sparsity.to_dict(
                    "records"
                )

            for baseline, shap_table in shap_tables.items():
                agreement = compare_rankings(
                    built_in, shap_table, BUILT_IN_SCORE[prior]
                )
                entry["agreement"][f"{prior} vs {baseline}"] = agreement
                print(
                    f"{dataset:9s} {prior:11s} vs {baseline:24s} "
                    f"rho={agreement['spearman_rho']:+.3f} "
                    f"tau={agreement['kendall_tau']:+.3f} "
                    f"top{agreement['top_k']}_overlap={agreement['top_k_overlap']}",
                    flush=True,
                )

        results[dataset] = entry

    out_path = os.path.join(OUT_DIR, "explainability.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
