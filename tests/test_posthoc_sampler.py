"""The sampler sensitivity changes acceptance only and preserves its separate label.

Covers ``src/pipelines/posthoc_sampler.py``, which refits every horseshoe cell
with the No-U-Turn Sampler (NUTS) target acceptance raised to 0.999 (ADR-032),
and the confirmatory remedy ladder in ``src/pipelines/confirmatory/fitting.py``
that it reuses. No model is fitted: the checks concern the protocol copy, the
settings and seeds of each fit attempt, and the checks on a saved cell before
resume (INV-009).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
import yaml

from src.pipelines import confirmatory
from src.pipelines.posthoc_sampler import (
    EVIDENCE_STATUS,
    TARGET_ACCEPT,
    _cell_path,
    _options,
    _verify_saved_cell,
    sensitivity_protocol,
)
from src.utils.reproducibility import canonical_json_hash, sha256_file

ROOT = Path(__file__).resolve().parents[1]


def test_sensitivity_changes_only_two_acceptance_controls() -> None:
    """Only the two acceptance settings change, and the frozen protocol is not mutated (INV-009)."""
    original = yaml.safe_load((ROOT / "config/confirmatory.yaml").read_text())
    unchanged = copy.deepcopy(original)
    changed = sensitivity_protocol(original)
    assert original == unchanged
    bayesian = changed["models"]["bayesian_cox"]
    assert bayesian["priors"]["horseshoe"]["target_accept"] == TARGET_ACCEPT
    assert bayesian["failed_fit_rule"]["refit_target_accept"] == TARGET_ACCEPT
    # Restoring the two settings must give back the frozen protocol exactly.
    bayesian["priors"]["horseshoe"]["target_accept"] = original["models"]["bayesian_cox"]["priors"][
        "horseshoe"
    ]["target_accept"]
    bayesian["failed_fit_rule"]["refit_target_accept"] = original["models"]["bayesian_cox"][
        "failed_fit_rule"
    ]["refit_target_accept"]
    assert changed == original


def test_every_attempt_retains_acceptance_tuning_and_seed_ladder(
    monkeypatch, tmp_path: Path
) -> None:
    """Every attempt uses 0.999 while the tuning, baseline and seed ladder stay frozen (INV-009)."""
    original = yaml.safe_load((ROOT / "config/confirmatory.yaml").read_text())
    protocol = sensitivity_protocol(original)
    # Confirmatory-scale controls; of these, the fake model reads only the
    # tuning length that each attempt passes in.
    controls = {
        "datasets": ["gbsg2", "whas500", "metabric"],
        "models": list(confirmatory.MODEL_KEYS),
        "outer_splits": 5,
        "outer_repeats": 5,
        "fold_limit_per_dataset": None,
        "bayes_draws": 2000,
        "bayes_tune": 2000,
        "bayes_chains": 4,
        "calibration_bootstraps": 1000,
    }
    calls = []

    class Model:
        """Fake model that records its attempt settings and converges on the third attempt.

        Failing the diagnostic gate twice makes the full three-attempt ladder run.
        """

        def __init__(self, kwargs):
            """Store the attempt's acceptance, tuning length and baseline parameterisation."""
            # With no override (the first attempt), fall back to the protocol's
            # horseshoe acceptance, as ``_model_from_parameters`` does.
            self.target_accept = (
                kwargs["target_accept_override"]
                or protocol["models"]["bayesian_cox"]["priors"]["horseshoe"]["target_accept"]
            )
            self.tune = kwargs["bayes_tune"]
            self.noncentered_baseline = kwargs["noncentered_baseline"]
            self.diagnostics = {"converged": len(calls) == 3}
            self.prior_predictive_summary = {}
            self.posterior_predictive_summary = {}

        def fit(self, *_):
            """Skip sampling and return the model."""
            return self

    def factory(*_, **kwargs):
        """Record the keyword arguments of each attempt and build a fake model."""
        calls.append(kwargs)
        return Model(kwargs)

    monkeypatch.setattr(confirmatory, "_model_from_parameters", factory)
    monkeypatch.setattr(confirmatory, "_posterior_trace_snapshot", lambda _: {})
    _, attempts = confirmatory._fit_with_diagnostic_rule(
        "bayesian_horseshoe",
        {},
        None,
        None,
        None,
        seed=19,
        config=protocol,
        options=_options(controls, tmp_path),
    )
    # The frozen ladder: refits double the tuning length, and the last attempt
    # also switches to the non-centred baseline.
    assert len(attempts) == 3
    assert [row["target_accept"] for row in attempts] == [TARGET_ACCEPT] * 3
    assert [row["tune"] for row in attempts] == [2000, 4000, 4000]
    assert [row["noncentered_baseline"] for row in attempts] == [False, False, True]
    assert [row["seed"] for row in calls] == [
        confirmatory.deterministic_seed(19, "fit_attempt", attempt) for attempt in range(3)
    ]


@pytest.mark.parametrize(
    "corruption", ["confirmatory_label", "target_accept", "source_hash", "content_hash"]
)
def test_resume_rejects_wrong_evidence_or_sampler_lineage(tmp_path: Path, corruption: str) -> None:
    """Saved cells with a wrong label, acceptance, source or content hash are refused (INV-009)."""
    key = ("gbsg2", 1, 1)
    source = _cell_path(tmp_path / "source", key)
    source.parent.mkdir(parents=True)
    source.write_text('{"source": true}\n')
    # The base record has no ``status`` field and its ``sampler_sensitivity``
    # lacks ``scope``, so verification rejects it even without corruption. The
    # "target_accept" and "source_hash" cases therefore fail at the status check,
    # before their own checks are reached.
    record = {
        "model_key": "bayesian_horseshoe",
        "dataset": key[0],
        "repeat": key[1],
        "fold": key[2],
        "analysis_mode": EVIDENCE_STATUS,
        "evidence_status": EVIDENCE_STATUS,
        "source_confirmatory_cell_sha256": sha256_file(source),
        "sampler_sensitivity": {"target_accept": TARGET_ACCEPT},
        "fit_attempts": [{"target_accept": TARGET_ACCEPT}],
    }
    if corruption == "confirmatory_label":
        record["evidence_status"] = "confirmatory"
    elif corruption == "target_accept":
        record["fit_attempts"][0]["target_accept"] = 0.99
    elif corruption == "source_hash":
        record["source_confirmatory_cell_sha256"] = "0" * 64
    record["cell_content_sha256"] = canonical_json_hash(record)
    # Changing a field after hashing leaves a stale content hash.
    if corruption == "content_hash":
        record["fold"] = 2
    path = tmp_path / "resume.json"
    path.write_text(json.dumps(record))
    with pytest.raises(RuntimeError):
        _verify_saved_cell(path, tmp_path / "source", key)
