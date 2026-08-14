"""Package-level integration checks.

Every package must import, and the analysis modules that the later phases
depend on must run against real data. These modules are not yet wired into a
script, so nothing else would catch them breaking.
"""

import importlib
from pathlib import Path

import pandas as pd
import pytest

from src.evaluation.cross_validation import CrossValidationEvaluator
from src.evaluation.metrics import evaluate_survival_model
from src.evaluation.ranking import time_dependent_auc_at
from src.models.cox import CoxPHModel
from src.statistics.bootstrap import BootstrapResampler

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"

PACKAGES = [
    "src.data",
    "src.datasets",
    "src.evaluation",
    "src.explainability",
    "src.losses",
    "src.models",
    "src.models.bayesian",
    "src.pipelines",
    "src.statistics",
    "src.utils",
    "src.visualization",
]


@pytest.fixture(scope="module")
def fitted():
    train = pd.read_csv(PROCESSED / "gbsg2" / "train.csv")
    features = [c for c in train.columns if c not in ("time", "event")]
    model = CoxPHModel().fit(
        train[features], train["time"].to_numpy(), train["event"].to_numpy()
    )
    return model, train, features


@pytest.mark.parametrize("package", PACKAGES)
def test_package_imports(package):
    importlib.import_module(package)


def test_single_sample_evaluation(fitted):
    model, train, features = fitted
    result = evaluate_survival_model(
        train["time"].to_numpy(),
        train["event"].to_numpy(),
        model.predict_risk(train[features]),
        surv_prob_fn=lambda t: model.predict_survival(train[features], t),
    )
    assert 0.6 < result["c_index"] < 0.85
    assert 0 < result["integrated_brier_score"] < 0.3
    assert result["time_dependent_auc"]


def test_time_dependent_auc_at_single_time(fitted):
    model, train, features = fitted
    median = float(train["time"].median())
    auc = time_dependent_auc_at(
        train["time"].to_numpy(),
        train["event"].to_numpy(),
        model.predict_risk(train[features]),
        median,
    )
    assert 0.5 < auc < 1.0


def test_bootstrap_resampler_runs(fitted):
    model, train, features = fitted
    resampler = BootstrapResampler(n_bootstraps=20, random_state=42)
    result = resampler.bootstrap_metrics(
        y_time=train["time"].to_numpy(),
        y_event=train["event"].to_numpy(),
        risk_scores=model.predict_risk(train[features]),
    )
    assert len(result["c_index"]) > 0
    assert all(0 < c < 1 for c in result["c_index"])


def test_cross_validation_evaluator_runs():
    evaluator = CrossValidationEvaluator(
        processed_dir=str(PROCESSED), dataset_name="gbsg2"
    )

    def trainer(df_train, _df_val):
        features = [c for c in df_train.columns if c not in ("time", "event")]
        return CoxPHModel().fit(
            df_train[features],
            df_train["time"].to_numpy(),
            df_train["event"].to_numpy(),
        )

    result = evaluator.evaluate_model(trainer)
    assert result["n_splits"] == 5
    assert 0.5 < result["mean_c_index"] < 0.85
