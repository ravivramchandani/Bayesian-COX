"""Model behaviour tests.

Baselines are checked against the concordance range reported for these
cohorts in the literature, using the active raw-cohort loader and training-only
outer-fold preprocessing. A model at chance level indicates a pipeline defect.

Covers ``src/models/cox.py`` (Cox proportional hazards, PH),
``random_survival_forest.py`` (random survival forest, RSF), ``deepsurv.py``
and ``bayesian/model.py``. Verifies INV-003, that both baselines reach their
published range, and INV-005, that the Bayesian model's No-U-Turn Sampler
(NUTS) diagnostics are computed from the trace: R-hat, bulk effective sample
size (ESS) and the Bayesian fraction of missing information (BFMI).
"""

import numpy as np
import pandas as pd
import pytest

from src.evaluation.metrics import concordance_index
from src.models.bayesian.model import SUPPORTED_PRIORS, BayesianCoxModel
from src.models.cox import CoxPHModel
from src.models.deepsurv import DeepSurvModel
from src.models.random_survival_forest import RandomSurvivalForestModel
from tests.cohort_fixtures import prepare_real_fold

# Lower bounds on test-set concordance. Published Cox baselines are about
# 0.67 (GBSG2), 0.75 (WHAS500) and 0.63 (METABRIC); these floors sit well
# below those values but far above chance.
BASELINE_FLOOR = {"gbsg2": 0.62, "whas500": 0.65, "metabric": 0.60}


def load(dataset):
    """Return first-fold training and validation frames with outcomes, and the feature names."""
    return prepare_real_fold(dataset).model_frames()


@pytest.mark.parametrize("dataset", sorted(BASELINE_FLOOR))
def test_cox_ph_reaches_published_range(dataset):
    """Cox PH validation concordance on the first outer fold reaches the cohort floor (INV-003)."""
    train, test, features = load(dataset)
    model = CoxPHModel().fit(train[features], train["time"], train["event"])
    c, _ = concordance_index(test["time"], test["event"], model.predict_risk(test[features]))
    assert c >= BASELINE_FLOOR[dataset], (
        f"{dataset}: Cox PH concordance {c:.3f} is below the published range"
    )


@pytest.mark.parametrize("dataset", sorted(BASELINE_FLOOR))
def test_random_survival_forest_reaches_published_range(dataset):
    """RSF validation concordance on the first outer fold reaches the cohort floor (INV-003)."""
    train, test, features = load(dataset)
    model = RandomSurvivalForestModel(n_estimators=100, n_jobs=1).fit(
        train[features], train["time"], train["event"]
    )
    c, _ = concordance_index(test["time"], test["event"], model.predict_risk(test[features]))
    assert c >= BASELINE_FLOOR[dataset]


def test_cox_survival_curves_are_monotone_and_bounded():
    """Cox PH survival predictions have one row per subject, lie in [0, 1] and never increase."""
    train, test, features = load("gbsg2")
    model = CoxPHModel().fit(train[features], train["time"], train["event"])

    times = np.percentile(train["time"], [10, 30, 50, 70, 90])
    surv = model.predict_survival(test[features], times)

    assert surv.shape == (len(test), len(times))
    assert np.all((surv >= 0) & (surv <= 1))
    assert np.all(np.diff(surv, axis=1) <= 1e-9), "survival must be non-increasing"


def test_cox_hazard_ratios_have_expected_direction():
    """The GBSG2 Cox coefficient for positive lymph nodes (pnodes) is positive, raising the hazard."""
    train, _, features = load("gbsg2")
    model = CoxPHModel().fit(train[features], train["time"], train["event"])

    summary = model.summary().set_index("feature")
    assert summary.loc["pnodes", "coef"] > 0


def test_cox_proportional_hazards_test_runs():
    """The Schoenfeld-residual PH test returns one row per feature with its standard columns."""
    train, _, features = load("gbsg2")
    model = CoxPHModel().fit(train[features], train["time"], train["event"])
    table = model.proportional_hazards_test(train[features], train["time"], train["event"])
    assert set(table.columns) == {"feature", "test_statistic", "p", "ph_satisfied"}
    assert len(table) == len(features)


def test_rsf_permutation_importance_ranks_known_predictor():
    """RSF permutation importance places a lymph-node feature among the top four on GBSG2."""
    train, _, features = load("gbsg2")
    model = RandomSurvivalForestModel(n_estimators=100, n_jobs=1).fit(
        train[features], train["time"], train["event"]
    )
    importance = model.permutation_importance(
        train[features], train["time"], train["event"], n_repeats=3
    )
    top = set(importance.head(4)["feature"])
    # The primary GBSG2 set has no engineered columns, so only pnodes can match.
    assert {"log_pnodes", "pnodes"} & top


def test_deepsurv_reference_fit_is_deterministic_and_predictive():
    """DeepSurv learns a simulated risk, gives valid pycox survival curves and refits identically."""
    # Exponential event times with hazard exp(1.5 x1 - 0.8 x2); x3 is noise.
    # The 0.01 shift keeps every duration strictly positive, as DeepSurv requires.
    rng = np.random.default_rng(17)
    x = rng.normal(size=(100, 3))
    linear_predictor = 1.5 * x[:, 0] - 0.8 * x[:, 1]
    event_time = rng.exponential(scale=np.exp(-linear_predictor)) + 0.01
    censor_time = rng.exponential(scale=2.0, size=len(x)) + 0.01
    time = np.minimum(event_time, censor_time)
    event = (event_time <= censor_time).astype(int)
    frame = pd.DataFrame(x, columns=["x1", "x2", "x3"])

    kwargs = {
        "hidden_dims": [8],
        "dropout": 0.0,
        "batch_norm": False,
        "epochs": 40,
        "patience": 8,
        "random_state": 23,
    }
    model = DeepSurvModel(**kwargs).fit(frame, time, event)
    risk = model.predict_risk(frame)
    # In-sample concordance: the fitted rows are also the evaluated rows.
    c_index, _ = concordance_index(time, event, risk)
    assert c_index > 0.65

    horizons = np.quantile(time, [0.25, 0.5, 0.75])
    survival = model.predict_survival(frame.iloc[:10], horizons)
    assert survival.shape == (10, 3)
    assert np.all((survival >= 0.0) & (survival <= 1.0))
    assert np.all(np.diff(survival, axis=1) <= 1e-9)
    assert model.model.__class__.__module__.startswith("pycox.models")

    repeated = DeepSurvModel(**kwargs).fit(frame, time, event)
    np.testing.assert_allclose(
        risk,
        repeated.predict_risk(frame),
        rtol=1e-5,
        atol=1e-5,
    )


@pytest.mark.parametrize("prior", SUPPORTED_PRIORS)
def test_bayesian_cox_priors_fit_and_report_diagnostics(prior):
    """Each prior fits by NUTS, ranks better than chance and reports trace-derived checks (INV-005)."""
    train, test, features = load("gbsg2")
    model = BayesianCoxModel(
        coefficient_prior=prior,
        draws=300,
        tune=300,
        chains=2,
        target_accept=0.95,
    ).fit(train[features], train["time"], train["event"])

    c, _ = concordance_index(test["time"], test["event"], model.predict_risk(test[features]))
    assert c > 0.55

    diagnostics = model.diagnostics
    assert diagnostics["method"] == "nuts"
    # Diagnostics must be computed from the trace, not asserted.
    assert 0.9 < diagnostics["r_hat_max"] < 2.0
    assert diagnostics["ess_bulk_min"] > 0
    assert isinstance(diagnostics["converged"], bool)
    assert "log_lambda" in diagnostics["variables_checked"]
    assert diagnostics["n_parameters_checked"] > len(features)
    assert np.isfinite(diagnostics["bfmi_min"])
    # The prior check uses at most 512 training rows at four scaled times; the
    # fitted-survival check uses the three training event-time quartiles.
    assert model.prior_predictive_summary["finite"]
    assert model.prior_predictive_summary["n_covariate_rows"] == min(512, len(train))
    assert len(model.prior_predictive_summary["covariate_population_survival"]) == 4
    assert len(model.posterior_predictive_summary["survival_check"]) == 3
    replication = model.posterior_predictive_summary["replicated_event_counts"]
    # Two chains of 300 draws pool to 600; replication uses at most 200 of them.
    assert replication["n_posterior_draws"] == 200
    assert replication["total"]["observed"] == train["event"].sum()
    assert np.isfinite(replication["total"]["replicated_mean"])
    assert len(replication["by_baseline_interval"]) == model.n_intervals


def test_bayesian_cox_rejects_unknown_prior():
    """An unsupported coefficient prior such as Laplace raises ValueError before sampling (ADR-008)."""
    train, _, features = load("gbsg2")
    model = BayesianCoxModel(coefficient_prior="laplace", draws=10, tune=10, chains=1)
    with pytest.raises(ValueError, match="Unknown coefficient prior"):
        model.fit(train[features], train["time"], train["event"])


def test_bayesian_noncentered_baseline_remedy_preserves_predictions():
    """The non-centred baseline remedy samples an offset and yields valid survival curves (ADR-023)."""
    train, test, features = load("gbsg2")
    model = BayesianCoxModel(
        coefficient_prior="normal",
        noncentered_baseline=True,
        draws=100,
        tune=100,
        chains=2,
        random_state=91,
    ).fit(train[features], train["time"], train["event"])

    assert "log_lambda_offset" in model.idata.posterior
    assert "log_lambda" in model.idata.posterior
    survival = model.predict_survival(
        test[features].iloc[:5], np.quantile(train["time"], [0.25, 0.5, 0.75])
    )
    assert survival.shape == (5, 3)
    assert np.isfinite(survival).all()
    assert np.all(np.diff(survival, axis=1) <= 1e-9)


def test_sparsity_priors_expose_an_inclusion_signal():
    """Only sparsity priors give inclusion signals; group contributions equal E|group linear term|."""
    train, _, features = load("gbsg2")

    for prior in ("horseshoe", "spike_slab"):
        model = BayesianCoxModel(coefficient_prior=prior, draws=300, tune=300, chains=2).fit(
            train[features], train["time"], train["event"]
        )
        signal = model.inclusion_signal()
        assert signal is not None
        assert len(signal) == len(features)

    normal = BayesianCoxModel(coefficient_prior="normal", draws=200, tune=200, chains=2).fit(
        train[features], train["time"], train["event"]
    )
    assert normal.inclusion_signal() is None

    contribution = normal.posterior_expected_absolute_contribution(train[features])
    assert list(contribution.columns) == ["feature", "expected_abs_contribution"]
    assert len(contribution) == len(features)

    # Group the first two model columns together; the expected value is the
    # per-subject posterior mean of |x_1 beta_1 + x_2 beta_2|.
    selected = train[features].iloc[:4]
    feature_groups = {
        feature: "first_two" if index < 2 else feature for index, feature in enumerate(features)
    }
    grouped = normal.posterior_expected_absolute_group_contribution(selected, feature_groups)
    first_two = [0, 1]
    expected = np.abs(
        normal.beta_samples[:, first_two] @ selected.iloc[:, first_two].to_numpy(dtype=float).T
    ).mean(axis=0)
    np.testing.assert_allclose(grouped["first_two"], expected)
