"""Model behaviour tests.

Baselines are checked against the concordance range reported for these
cohorts in the literature. A model that lands at chance level indicates a
broken pipeline rather than a weak model.
"""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.evaluation.metrics import concordance_index
from src.models.bayesian.model import SUPPORTED_PRIORS, BayesianCoxModel
from src.models.cox import CoxPHModel
from src.models.random_survival_forest import RandomSurvivalForestModel

ROOT = Path(__file__).resolve().parent.parent
PROCESSED = ROOT / "data" / "processed"

# Lower bounds on test-set concordance. Published Cox baselines are about
# 0.67 (GBSG2), 0.75 (WHAS500) and 0.63 (METABRIC); these floors sit well
# below those values but far above chance.
BASELINE_FLOOR = {"gbsg2": 0.62, "whas500": 0.65, "metabric": 0.60}


def load(dataset):
    train = pd.read_csv(PROCESSED / dataset / "train.csv")
    test = pd.read_csv(PROCESSED / dataset / "test.csv")
    features = [c for c in train.columns if c not in ("time", "event")]
    return train, test, features


@pytest.mark.parametrize("dataset", sorted(BASELINE_FLOOR))
def test_cox_ph_reaches_published_range(dataset):
    train, test, features = load(dataset)
    model = CoxPHModel().fit(train[features], train["time"], train["event"])
    c, _ = concordance_index(
        test["time"], test["event"], model.predict_risk(test[features])
    )
    assert c >= BASELINE_FLOOR[dataset], (
        f"{dataset}: Cox PH concordance {c:.3f} is below the published range"
    )


@pytest.mark.parametrize("dataset", sorted(BASELINE_FLOOR))
def test_random_survival_forest_reaches_published_range(dataset):
    train, test, features = load(dataset)
    model = RandomSurvivalForestModel(n_estimators=100).fit(
        train[features], train["time"], train["event"]
    )
    c, _ = concordance_index(
        test["time"], test["event"], model.predict_risk(test[features])
    )
    assert c >= BASELINE_FLOOR[dataset]


def test_cox_survival_curves_are_monotone_and_bounded():
    train, test, features = load("gbsg2")
    model = CoxPHModel().fit(train[features], train["time"], train["event"])

    times = np.percentile(train["time"], [10, 30, 50, 70, 90])
    surv = model.predict_survival(test[features], times)

    assert surv.shape == (len(test), len(times))
    assert np.all((surv >= 0) & (surv <= 1))
    assert np.all(np.diff(surv, axis=1) <= 1e-9), "survival must be non-increasing"


def test_cox_hazard_ratios_have_expected_direction():
    """More positive lymph nodes must not reduce the hazard."""
    train, _, features = load("gbsg2")
    model = CoxPHModel().fit(train[features], train["time"], train["event"])

    summary = model.summary().set_index("feature")
    assert summary.loc["log_pnodes", "coef"] > 0


def test_cox_proportional_hazards_test_runs():
    train, _, features = load("gbsg2")
    model = CoxPHModel().fit(train[features], train["time"], train["event"])
    table = model.proportional_hazards_test(
        train[features], train["time"], train["event"]
    )
    assert set(table.columns) == {"feature", "test_statistic", "p", "ph_satisfied"}
    assert len(table) == len(features)


def test_rsf_permutation_importance_ranks_known_predictor():
    train, _, features = load("gbsg2")
    model = RandomSurvivalForestModel(n_estimators=100).fit(
        train[features], train["time"], train["event"]
    )
    importance = model.permutation_importance(
        train[features], train["time"], train["event"], n_repeats=3
    )
    top = set(importance.head(4)["feature"])
    assert {"log_pnodes", "pnodes"} & top


@pytest.mark.parametrize("prior", SUPPORTED_PRIORS)
def test_bayesian_cox_priors_fit_and_report_diagnostics(prior):
    train, test, features = load("gbsg2")
    model = BayesianCoxModel(
        coefficient_prior=prior,
        draws=300,
        tune=300,
        chains=2,
        target_accept=0.95,
    ).fit(train[features], train["time"], train["event"])

    c, _ = concordance_index(
        test["time"], test["event"], model.predict_risk(test[features])
    )
    assert c > 0.55

    diagnostics = model.diagnostics
    assert diagnostics["method"] == "nuts"
    # Diagnostics must be computed from the trace, not asserted.
    assert 0.9 < diagnostics["r_hat_max"] < 2.0
    assert diagnostics["ess_bulk_min"] > 0
    assert isinstance(diagnostics["converged"], bool)


def test_bayesian_cox_rejects_unknown_prior():
    train, _, features = load("gbsg2")
    model = BayesianCoxModel(coefficient_prior="laplace", draws=10, tune=10, chains=1)
    with pytest.raises(ValueError, match="Unknown coefficient prior"):
        model.fit(train[features], train["time"], train["event"])


def test_sparsity_priors_expose_an_inclusion_signal():
    train, _, features = load("gbsg2")

    for prior in ("horseshoe", "spike_slab"):
        model = BayesianCoxModel(
            coefficient_prior=prior, draws=300, tune=300, chains=2
        ).fit(train[features], train["time"], train["event"])
        signal = model.inclusion_signal()
        assert signal is not None
        assert len(signal) == len(features)

    normal = BayesianCoxModel(
        coefficient_prior="normal", draws=200, tune=200, chains=2
    ).fit(train[features], train["time"], train["event"])
    assert normal.inclusion_signal() is None
