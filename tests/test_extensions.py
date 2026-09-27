"""Reference parity, outcome-independent transforms and survival utility tests."""

import json
import warnings
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pymc as pm
import pytest
from numpy.testing import assert_allclose, assert_array_equal
from sklearn.exceptions import ConvergenceWarning

from src.models.bayesian.extensions import (
    ExtensionBayesianCox,
    _add_compact_likelihood,
    survival_horseshoe_scale,
)
from src.models.bayesian.piecewise import _add_poisson_likelihood, _poisson_rows
from src.models.catalytic import (
    CatalyticData,
    WeightedMixtureCox,
    adaptive_log_kernel,
    catalytic_kappa,
    catalytic_kernel,
)
from src.models.penalized_cox import PenalizedCox
from src.pipelines.confirmatory.options import deterministic_seed
from src.pipelines.extensions.analysis import extension_families, paired_effect
from src.pipelines.extensions.decision_curves import (
    decision_contributions,
    ipcw_state_weights,
    patient_cluster_intervals,
)
from src.pipelines.extensions.fitting import (
    FitExecutionFailure,
    fit_with_attempts,
    select_parameters,
)
from src.pipelines.extensions.genomics import collapse_expression
from src.pipelines.extensions.planning import build_extension_jobs
from src.pipelines.extensions.preprocessing import ExtensionPreprocessor, generate_catalytic_data
from src.pipelines.extensions.runner import verified_cell
from src.pipelines.extensions.verification import (
    SavedForecast,
    assert_scientific_equal,
    verify_cell_identity,
    verify_trace_diagnostics,
)
from src.utils.io import read_mapping, write_json_atomic
from src.utils.reproducibility import canonical_json_hash

FIXTURE = json.loads((Path(__file__).parent / "fixtures/extensions/catalytic_r_reference.json").read_text())


def test_cell_identity_checks_condition_seed_and_missing_nullable_metadata() -> None:
    raw = pd.DataFrame({"subject_id": ["a", "b", "c"]})
    job = SimpleNamespace(cell_id="fixture", dataset="gbsg2", model="ridge", repeat=1, fold=1,
                          setting="clinical", condition="full", gene_budget=0, censoring_cutoff=None,
                          train=np.array([0, 1]), validation=np.array([2]))
    cell = {"cell_id": "fixture", "dataset": "gbsg2", "model_key": "ridge", "repeat": 1, "fold": 1,
            "setting": "clinical", "condition": "full", "gene_budget": 0, "censoring_cutoff": None,
            "n_train": 2, "n_validation": 1, "train_subject_ids": ["a", "b"],
            "validation_subject_ids": ["c"], "training_membership_sha256": canonical_json_hash(["a", "b"]),
            "seed": deterministic_seed(123, "extensions", "fixture"), "evidence_status": "post_hoc_extension"}
    verify_cell_identity(cell, job, raw, 123)
    changed = [{**cell, "condition": "fraction_0.50"}, {**cell, "seed": cell["seed"] + 1},
               {k: v for k, v in cell.items() if k != "censoring_cutoff"}]
    for altered in changed:
        with pytest.raises(ValueError, match="identity/membership"):
            verify_cell_identity(altered, job, raw, 123)


def test_trace_verifier_accepts_recorded_nuts_metadata_but_rejects_alterations() -> None:
    trace = SimpleNamespace(posterior=SimpleNamespace(sizes={"chain": 4, "draw": 2000}))
    observed = {"converged": True, "max_rhat": 1.001}
    recorded = {**observed, "method": "nuts", "n_chains": 4, "n_draws": 2000}
    verify_trace_diagnostics(recorded, observed, trace, "posterior", "cell")
    verify_trace_diagnostics(observed, observed, trace, "prior", "cell")
    for changed in ({**recorded, "n_draws": 1999}, {**recorded, "max_rhat": 1.05},
                    {**recorded, "method": "advi"}):
        with pytest.raises(ValueError):
            verify_trace_diagnostics(changed, observed, trace, "posterior", "cell")


def prior_data() -> CatalyticData:
    i = FIXTURE["inputs"]
    return CatalyticData(np.array(i["synthetic"]["X"]), np.array(i["synthetic"]["time"]),
                        i["prior"]["hazard_constant"])


def test_catalytic_prior_matches_executed_R() -> None:
    data = prior_data()
    kappa, _ = catalytic_kappa(data)
    assert_allclose(kappa, FIXTURE["prior"]["kappa_without_log_h0"], atol=1e-9)
    for row in FIXTURE["prior"]["probes"]:
        q, gradient = catalytic_kernel(np.array(row["beta"]), data)
        assert_allclose(q * row["tau"], row["fixed_log_density_kernel"], atol=1e-12)
        assert_allclose(gradient * row["tau"], row["beta_gradient"], atol=1e-12)
        assert_allclose(adaptive_log_kernel(np.array(row["beta"]), row["tau"], data, kappa,
                                          alpha=2, gamma=1.4),
                        row["adaptive_joint_log_density_kernel"], atol=1e-12)


def test_weighted_mixture_matches_executed_R_and_valid_survival() -> None:
    i = FIXTURE["inputs"]
    model = WeightedMixtureCox(prior_data(), i["wme"]["tau"])
    model.fit(pd.DataFrame(i["observed"]["X"]), np.array(i["observed"]["time"]), np.array(i["observed"]["event"]))
    assert_allclose(model.beta, FIXTURE["wme"]["coefficients"], atol=2e-8)
    assert_allclose(model.details["log_partial_likelihood"], FIXTURE["wme"]["optimum_log_likelihood"], atol=1e-9)
    survival = model.predict_survival(pd.DataFrame(i["observed"]["X"]), np.arange(0, 8))
    assert np.isfinite(survival).all() and np.all(np.diff(survival, axis=1) <= 0)
    assert_array_equal(survival[:, 0], np.ones(10))
    scaled = WeightedMixtureCox(prior_data(), i["wme"]["tau"], time_scale=10).fit(
        pd.DataFrame(i["observed"]["X"]), np.array(i["observed"]["time"]) * 10,
        np.array(i["observed"]["event"]))
    assert_allclose(scaled.beta, model.beta, atol=1e-12)
    assert_allclose(scaled.predict_survival(pd.DataFrame(i["observed"]["X"]), np.arange(0, 8) * 10), survival)


@pytest.mark.parametrize("variant", ["catalytic_fixed", "catalytic_adaptive"])
def test_pymc_joint_prior_matches_density_differences(variant: str) -> None:
    model = ExtensionBayesianCox(variant, synthetic=prior_data())
    with pm.Model() as graph:
        model._coefficient_prior(3)
    logp = graph.compile_logp(jacobian=False)
    points = [(np.array([0.3, -0.2, 0.4]), 0.7), (np.array([-0.5, 0.6, -0.1]), 3.5)]
    compiled, expected = [], []
    for beta, tau in points:
        point = {"beta": beta}
        if variant == "catalytic_adaptive":
            point["tau_log__"] = np.log(tau)
            expected.append(adaptive_log_kernel(beta, tau, prior_data(), model.kappa))
        else:
            expected.append(3 * catalytic_kernel(beta, prior_data())[0])
        compiled.append(logp(point))
    assert_allclose(np.diff(compiled), np.diff(expected), atol=1e-10)


def test_synthetic_source_categories_and_training_only_gene_selection() -> None:
    frame = pd.DataFrame({"z": np.arange(30), "group": ["A", "B", "C"] * 10,
                          "gene:1": np.arange(30) * 2, "gene:2": np.arange(30) / 5})
    p = ExtensionPreprocessor({"numeric": ["z"], "categorical": ["group"]}, 1).fit(frame)
    assert p.genes == ["gene:1"]
    state = p.metadata()
    held_out = frame.copy()
    held_out["gene:2"] = 1e20 * np.arange(30)
    p.transform(held_out)
    assert p.metadata() == state
    t, e = np.arange(1, 31, dtype=float), np.array([0, 1] * 15)
    data, metadata = generate_catalytic_data(frame, p, t, e, 937)
    columns = p.feature_names
    assert np.all(data.design[:, [columns.index("group=B"), columns.index("group=C")]].sum(axis=1) <= 1)
    other, other_meta = generate_catalytic_data(frame, p, t, e, 937)
    assert_array_equal(data.design, other.design)
    assert metadata == other_meta
    assert metadata["M"] == 1000 and data.hazard == e.sum() / (t / np.median(t[e == 1])).sum()


def test_prior_data_rejects_dependent_columns() -> None:
    with pytest.raises(ValueError, match="rank"):
        CatalyticData(np.ones((20, 2)), np.ones(20), 1)


def test_duplicate_gene_collapse_is_within_sample() -> None:
    raw = pd.DataFrame({"Hugo_Symbol": ["A", "alias", "B"], "Entrez_Gene_Id": [1, 1, 2],
                        "sample1": [2, 4, 8], "sample2": [4, np.nan, 12]})
    result = collapse_expression(raw)
    assert_allclose(result.to_numpy(), [[3, 8], [4, 12]])
    raw["sample2"] = [100, 1000, 12]
    assert_allclose(collapse_expression(raw).loc["sample1"], result.loc["sample1"])


def test_survival_scale_uses_actual_information_and_is_deterministic() -> None:
    rng = np.random.default_rng(37)
    x, t, e = rng.normal(size=(50, 4)), np.linspace(0.2, 4, 50), np.array([0, 1] * 25)
    scale = survival_horseshoe_scale(x, t, e, np.array([0, 1, 2, 5]))
    diagonal = np.array(scale["information_diagonal"])
    s = scale["tau0"] * np.sqrt(diagonal)
    assert_allclose(np.sum(s / (1 + s)), 2, atol=1e-10)
    assert survival_horseshoe_scale(x, t, e, np.array([0, 1, 2, 5])) == scale
    doubled = survival_horseshoe_scale(x * 2, t, e, np.array([0, 1, 2, 5]))
    assert_allclose(doubled["tau0"], scale["tau0"] / 2, atol=1e-10)


@pytest.mark.parametrize("kind", ["ridge", "lasso", "elastic_net"])
def test_penalized_cox_produces_finite_survival(kind: str) -> None:
    i = FIXTURE["inputs"]["observed"]
    x, t, e = pd.DataFrame(i["X"]), np.array(i["time"], float), np.array(i["event"])
    model = PenalizedCox(kind, 0.1).fit(x, t, e)
    assert np.isfinite(model.predict_risk(x)).all()
    survival = model.predict_survival(x, np.array([1, 3, 5]))
    assert np.isfinite(survival).all() and np.all(np.diff(survival, axis=1) <= 0)


def test_decision_curve_reduces_to_binary_utility_without_censoring() -> None:
    training_t = np.arange(1, 31, dtype=float)
    u, v, _ = ipcw_state_weights(training_t, np.ones(30, int), np.array([2, 12, 15]),
                                np.ones(3, int), 10)
    utility, all_utility = decision_contributions(np.array([0.8, 0.7, 0.1]), u, v, np.array([0.5]))
    assert_allclose(utility[:, 0], [1, -1, 0])
    assert_allclose(all_utility[:, 0], [1, -1, -1])


def test_decision_curve_censoring_retains_denominator_and_support_gate() -> None:
    t, e = np.arange(1, 31, dtype=float), np.ones(30, int)
    u, v, meta = ipcw_state_weights(t, e, np.array([2, 12, 3]), np.array([1, 0, 0]), 10)
    _, all_utility = decision_contributions(np.ones(3), u, v, np.array([0.5]))
    assert_allclose(all_utility[:, 0], [1, -1, 0])
    assert meta["early_censored"] == 1
    with pytest.raises(ValueError, match="support"):
        ipcw_state_weights(t, np.zeros(30, int), np.array([2]), np.array([1]), 29)


def test_decision_bootstrap_clusters_repeats_and_pairs_defaults() -> None:
    v = np.array([[[1], [0]], [[0], [-1]], [[1], [1]]], dtype=float)
    result = patient_cluster_intervals({"model": v, "all": v, "none": np.zeros_like(v)},
                                      n_bootstraps=100, seed=51)
    assert result["n_patients"] == 3 and result["n_repeats"] == 2
    assert_array_equal(result["models"]["model"]["differences"]["all"]["pointwise_lower"], [0])
    assert result == patient_cluster_intervals({"model": v, "all": v, "none": np.zeros_like(v)},
                                             n_bootstraps=100, seed=51)


def test_compact_likelihood_and_gradient_equal_frozen_interval_expansion() -> None:
    x = np.array(FIXTURE["inputs"]["observed"]["X"], float)
    t = np.array(FIXTURE["inputs"]["observed"]["time"], float)
    e = np.array(FIXTURE["inputs"]["observed"]["event"])
    cuts = np.array([0, 2, 4, 8])
    rows = _poisson_rows(x, t, e, cuts)
    exposure = np.clip(np.minimum(t[:, None], cuts[1:]) - cuts[:-1], 0, None)
    subject, interval = np.where(exposure > 0)
    graphs = []
    for compact in (False, True):
        with pm.Model() as graph:
            beta = pm.Normal("beta", shape=3)
            baseline = pm.Normal("log_lambda", shape=3)
            if compact:
                _add_compact_likelihood(x, rows, subject, interval, beta, baseline)
            else:
                _add_poisson_likelihood(rows, beta, baseline)
        graphs.append(graph)
    point = {"beta": np.array([0.7, -0.3, 0.5]), "log_lambda": np.array([-1.2, -0.9, -1.4])}
    assert_allclose(graphs[0].compile_logp()(point), graphs[1].compile_logp()(point), atol=1e-12)
    assert_allclose(graphs[0].compile_dlogp()(point), graphs[1].compile_dlogp()(point), atol=1e-12)


def test_catalytic_prior_sampler_has_no_real_likelihood_and_no_parent_collision(monkeypatch) -> None:
    import arviz as az
    model = ExtensionBayesianCox("catalytic_adaptive", synthetic=prior_data())
    model.feature_names = ["a", "b", "c"]
    model.cutoffs_scaled = np.array([0, 1, 2])
    def fake_sample(**kwargs):
        current = pm.modelcontext(None)
        assert current.parent is None and not current.observed_RVs
        return az.from_dict(posterior={"beta": np.zeros((4, 10, 3)), "log_lambda": np.zeros((4, 10, 2))})
    monkeypatch.setattr(pm, "sample", fake_sample)
    monkeypatch.setattr("src.models.bayesian.extensions.check_convergence", lambda _: {"converged": True})
    monkeypatch.setattr(pm, "sample_prior_predictive", lambda **_: pytest.fail("forward sampler ignores Potential"))
    with pm.Model():
        model._coefficient_prior(3)
        prior = model._sample_prior_predictive()
    assert prior.prior.beta.shape == (4, 10, 3)


def test_full_grid_has_correct_distinct_fits_and_reuses_full_rq2_anchors() -> None:
    from src.data.cohorts import load_analysis_dataset
    root = Path(__file__).resolve().parents[1]
    specs = read_mapping(root / "config/datasets.yaml")
    cohorts = {}
    for key in ("gbsg2", "whas500", "metabric"):
        raw, times, events, ids = load_analysis_dataset(root, key, specs[key])
        raw["duration"], raw["event"], raw["subject_id"] = times, events, ids
        cohorts[key] = raw
    cohorts["metabric_matched"] = cohorts["metabric"]
    jobs = build_extension_jobs(cohorts, read_mapping(root / "config/extensions.yaml"))
    assert len(jobs) == len({j.cell_id for j in jobs}) == 1625
    assert sum(j.dataset == "metabric_matched" for j in jobs) == 650
    assert sum(j.condition != "full" for j in jobs) == 450
    assert all(not set(j.train) & set(j.validation) for j in jobs)


def test_checkpoint_rejects_tampering(tmp_path: Path) -> None:
    cell = {"cell_id": "unit_fixture", "status": "failed", "message": "known failure"}
    cell["cell_content_sha256"] = canonical_json_hash(cell)
    path = tmp_path / "cell.json"
    write_json_atomic(path, cell)
    assert verified_cell(path) == cell
    cell["message"] = "altered"
    write_json_atomic(path, cell)
    with pytest.raises(ValueError, match="changed"):
        verified_cell(path)


def test_incomplete_families_never_gain_holm_rejection_claims() -> None:
    families = extension_families([], [])
    assert {k: v["expected_contrasts"] for k, v in families.items()} == {
        "penalized_vs_original_priors": 27, "calibrated_vs_adr032_horseshoe": 3,
        "catalytic_vs_original_priors": 27, "expression_increment": 13}
    assert all(not v["family_complete"] for v in families.values())
    assert all("holm_reject" not in r for v in families.values() for r in v["contrasts"])


def test_pairing_rejects_different_patient_order() -> None:
    a = {"repeat": 1, "fold": 1, "status": "complete", "predictions": {"subject_ids": ["a", "b"]}}
    b = {**a, "predictions": {"subject_ids": ["b", "a"]}}
    with pytest.raises(ValueError, match="subject_ids"):
        paired_effect([a], [b])


def test_saved_forecast_requires_shared_time_agreement() -> None:
    p = {"risk": [1], "ibs_grid": [1, 2], "horizons": [1, 3],
         "survival_on_ibs_grid": [[0.8, 0.7]], "survival_at_horizons": [[0.8, 0.5]]}
    forecast = SavedForecast(p)
    assert_allclose(forecast.predict_survival(pd.DataFrame(), np.array([1, 2, 3])), [[0.8, 0.7, 0.5]])
    p["survival_at_horizons"][0][0] = 0.9
    with pytest.raises(ValueError, match="disagree"):
        forecast.predict_survival(pd.DataFrame(), np.array([1]))
    with pytest.raises(ValueError, match="number"):
        assert_scientific_equal({"x": [0.1]}, {"x": [0.2]})


def test_later_fit_exception_retains_earlier_failed_diagnostics(monkeypatch) -> None:
    def factory(*args, **kwargs):
        attempt = kwargs["attempt"]
        def fit(*args):
            if attempt == 1:
                raise RuntimeError("sampler crashed on second attempt")
        return SimpleNamespace(fit=fit, diagnostics={"converged": False}, target_accept=0.999,
                               tune=2000, noncentered_baseline=False)
    monkeypatch.setattr("src.pipelines.extensions.fitting.make_model", factory)
    with pytest.raises(FitExecutionFailure) as caught:
        fit_with_attempts("pv_horseshoe", {}, pd.DataFrame(), np.array([]), np.array([]), None,
                          primary={}, config={}, seed=123)
    assert len(caught.value.attempts) == 2
    assert caught.value.attempts[0]["diagnostics"] == {"converged": False}
    assert caught.value.attempts[1]["error_type"] == "RuntimeError"


def test_nested_tuning_rejects_early_termination_warning_by_category(monkeypatch) -> None:
    i = FIXTURE["inputs"]["observed"]
    frame = pd.DataFrame(i["X"], columns=["x", "b", "c"])
    class Model:
        def __init__(self, penalty):
            self.penalty = penalty
        def fit(self, *args):
            if self.penalty == 0.1:
                warnings.warn("Optimization terminated early", ConvergenceWarning, stacklevel=2)
        def predict_survival(self, x, grid):
            return np.ones((len(x), len(grid))) * 0.8
    monkeypatch.setattr("src.pipelines.extensions.fitting.make_model",
                        lambda key, params, *a, **kw: Model(params["penalty"]))
    monkeypatch.setattr("src.pipelines.extensions.fitting.evaluation_horizons_and_grid",
                        lambda *a: (np.array([1, 2]), np.array([1, 2])))
    monkeypatch.setattr("src.pipelines.extensions.fitting.integrated_brier", lambda *a: 0.1)
    selected, tuning = select_parameters("lasso", frame, np.array(i["time"], float), np.array(i["event"]),
        {"numeric": ["x", "b", "c"]}, 0, primary={"evaluation": {}}, config={"penalties": [0.1, 0.2]}, seed=133)
    assert selected == {"penalty": 0.2}
    assert tuning["candidates"][0]["mean_ibs"] is None
    assert len(tuning["candidates"][0]["failures"]) == 3


def test_biological_aliases_are_bootstrapped_together() -> None:
    values = np.array([[[1]], [[-1]], [[0.3]], [[0.3]]])
    result = patient_cluster_intervals({"model": values, "all": values, "none": np.zeros_like(values)},
                                      n_bootstraps=100, seed=61, cluster_ids=["same", "same", "other", "other"])
    assert result["n_biological_clusters"] == 2
    assert_allclose(result["models"]["model"]["differences"]["all"]["estimate"], [0])


def test_initializer_creates_nested_output_before_exclusive_manifest_claim(tmp_path: Path, monkeypatch) -> None:
    import src.pipelines.extensions.runner as runner
    from src.pipelines.extensions.runner import initialize_extension_run
    freeze = {"sha256": {}}
    freeze["content_sha256"] = canonical_json_hash(freeze)
    config = {"base_seed": 260817}
    def mappings(path):
        if path.name == "extension_protocol_freeze.json":
            return freeze
        if path.name == "extensions.yaml":
            return config
        if path.name == "datasets.yaml":
            return {k: {"raw_file": f"{k}.csv"} for k in ("gbsg2", "whas500", "metabric")}
        return read_mapping(path)
    monkeypatch.setattr(runner, "read_mapping", mappings)
    monkeypatch.setattr(runner, "load_extension_cohorts", lambda *a: {})
    monkeypatch.setattr(runner, "build_extension_jobs", lambda *a: [])
    monkeypatch.setattr(runner, "build_run_manifest", lambda *a, **k: {"code": {"git_dirty": False}})
    matched = tmp_path / "fixture_input"
    matched.write_bytes(b"unit fixture")
    output = tmp_path / "new" / "nested" / "run"
    initialize_extension_run(tmp_path, matched, output)
    assert (output / "manifest.json").exists() and not (output / "manifest.claim").exists()
