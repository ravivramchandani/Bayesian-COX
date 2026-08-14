"""Fit every model on every dataset and write the benchmark results.

Produces reports/tables/benchmark.json with test-set and cross-validated
metrics for the Cox PH and random survival forest baselines and for the
Bayesian Cox model under each prior.
"""

import argparse
import json
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd
import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.evaluation.metrics import concordance_index, evaluate_model, evaluation_times
from src.models.bayesian.model import BayesianCoxModel
from src.models.cox import CoxPHModel
from src.models.random_survival_forest import RandomSurvivalForestModel

warnings.filterwarnings("ignore")

DATASETS = ["gbsg2", "whas500", "metabric"]
PROCESSED = os.path.join(PROJECT_ROOT, "data", "processed")
OUT_DIR = os.path.join(PROJECT_ROOT, "reports", "tables")
MODEL_CONFIG = os.path.join(PROJECT_ROOT, "config", "model.yaml")


def load_priors():
    """Prior hyperparameters from config/model.yaml, keyed by prior name."""
    with open(MODEL_CONFIG, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config["bayesian_cox"]["priors"]


def load(dataset):
    train = pd.read_csv(os.path.join(PROCESSED, dataset, "train.csv"))
    test = pd.read_csv(os.path.join(PROCESSED, dataset, "test.csv"))
    features = [c for c in train.columns if c not in ("time", "event")]
    return train, test, features


def build_models(draws, tune, chains, n_estimators):
    """Return {name: (test_factory, cv_factory)}.

    Cross-validation refits each model five times, so the Bayesian fits use a
    shorter chain there. The reported test-set fit always uses the full
    sampling budget, and CV concordance is only used for relative comparison.
    """
    models = {
        "Cox PH": (lambda: CoxPHModel(), lambda: CoxPHModel()),
        "Random Survival Forest": (
            lambda: RandomSurvivalForestModel(n_estimators=n_estimators),
            lambda: RandomSurvivalForestModel(n_estimators=n_estimators),
        ),
    }

    cv_draws = max(400, draws // 4)
    cv_tune = max(400, tune // 4)

    for prior, params in load_priors().items():
        params = dict(params)
        target_accept = params.pop("target_accept", 0.95)

        models[f"Bayesian Cox ({prior})"] = (
            lambda p=prior, ta=target_accept, pp=params: BayesianCoxModel(
                coefficient_prior=p,
                prior_params=pp,
                draws=draws,
                tune=tune,
                chains=chains,
                target_accept=ta,
            ),
            lambda p=prior, ta=target_accept, pp=params: BayesianCoxModel(
                coefficient_prior=p,
                prior_params=pp,
                draws=cv_draws,
                tune=cv_tune,
                chains=2,
                target_accept=ta,
            ),
        )
    return models


def fit_and_score(factory, train, test, features):
    model = factory()
    start = time.perf_counter()
    model.fit(train[features], train["time"].to_numpy(), train["event"].to_numpy())
    fit_seconds = time.perf_counter() - start

    times = evaluation_times(test["time"].to_numpy(), test["event"].to_numpy())
    risk = model.predict_risk(test[features])
    surv = model.predict_survival(test[features], times)

    result = evaluate_model(
        train["time"].to_numpy(),
        train["event"].to_numpy(),
        test["time"].to_numpy(),
        test["event"].to_numpy(),
        risk,
        survival_probs=surv,
        eval_times=times,
    )
    result["fit_seconds"] = round(fit_seconds, 2)
    if hasattr(model, "diagnostics") and model.diagnostics:
        result["diagnostics"] = model.diagnostics
    return model, result


def cross_validate(factory, train, features, n_splits=5, seed=42):
    """Stratified K-fold concordance on the training split."""
    rng = np.random.default_rng(seed)
    events = train["event"].to_numpy()

    folds = np.empty(len(train), dtype=int)
    for label in (0, 1):
        idx = np.where(events == label)[0]
        rng.shuffle(idx)
        folds[idx] = np.arange(len(idx)) % n_splits

    scores = []
    for k in range(n_splits):
        tr = train.iloc[folds != k]
        va = train.iloc[folds == k]
        if va["event"].sum() < 2 or tr["event"].sum() < 2:
            continue
        model = factory()
        model.fit(tr[features], tr["time"].to_numpy(), tr["event"].to_numpy())
        c_index, _ = concordance_index(
            va["time"].to_numpy(),
            va["event"].to_numpy(),
            model.predict_risk(va[features]),
        )
        scores.append(c_index)

    return {
        "cv_c_index_mean": float(np.mean(scores)),
        "cv_c_index_std": float(np.std(scores)),
        "cv_folds": len(scores),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--draws", type=int, default=2000)
    parser.add_argument("--tune", type=int, default=2000)
    parser.add_argument("--chains", type=int, default=4)
    parser.add_argument("--n-estimators", type=int, default=300)
    parser.add_argument("--cv-splits", type=int, default=5)
    parser.add_argument("--datasets", nargs="*", default=DATASETS)
    args = parser.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    models = build_models(args.draws, args.tune, args.chains, args.n_estimators)
    results = {}

    for dataset in args.datasets:
        train, test, features = load(dataset)
        results[dataset] = {
            "n_train": len(train),
            "n_test": len(test),
            "n_features": len(features),
            "event_rate_train": float(train["event"].mean()),
            "models": {},
        }

        for name, (test_factory, cv_factory) in models.items():
            _, scored = fit_and_score(test_factory, train, test, features)
            scored.update(cross_validate(cv_factory, train, features, args.cv_splits))
            results[dataset]["models"][name] = scored

            line = (
                f"{dataset:9s} {name:26s} "
                f"C={scored['c_index']:.4f} "
                f"IBS={scored.get('ibs', float('nan')):.4f} "
                f"AUC={scored['mean_auc']:.4f} "
                f"CV={scored['cv_c_index_mean']:.4f}"
            )
            if "diagnostics" in scored:
                d = scored["diagnostics"]
                line += f"  rhat={d['r_hat_max']:.4f} div={d['n_divergent']}"
            print(line, flush=True)

    out_path = os.path.join(OUT_DIR, "benchmark.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\nwrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
