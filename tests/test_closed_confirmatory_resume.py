"""Completed confirmatory resume verifies evidence and never reruns the analysis."""

from __future__ import annotations

import json

import pytest

from src.pipelines.confirmatory import RunOptions
from src.pipelines.confirmatory.runner import _actual_run_config, execute_confirmatory_run
from src.utils.io import write_json_atomic
from src.utils.reproducibility import canonical_json_hash, sha256_file
from tests.test_confirmatory_rendering import _make_run


@pytest.fixture
def closed_run(tmp_path, monkeypatch):
    run = _make_run(tmp_path / "results")
    options = RunOptions(
        mode="confirmatory",
        datasets=("toy",),
        models=("cox_ph", "bayesian_normal"),
        outer_splits=1,
        outer_repeats=1,
        fold_limit_per_dataset=None,
        bayes_draws=2,
        bayes_tune=2,
        bayes_chains=2,
        calibration_bootstraps=30,
        resume=True,
        output_root=run.parent,
    )
    config = {"analysis_id": "toy", "design_status": "frozen_after_rehearsal"}
    manifest = json.loads((run / "manifest.json").read_text())
    manifest["run_config"] = _actual_run_config(config, options)
    manifest["config_sha256"] = canonical_json_hash(manifest["run_config"])
    manifest.pop("manifest_content_sha256")
    manifest["manifest_content_sha256"] = canonical_json_hash(manifest)
    write_json_atomic(run / "manifest.json", manifest)
    destination = run.parent / f"toy_confirmatory_{manifest['config_sha256'][:12]}"
    run.rename(destination)
    root = tmp_path / "code"
    (root / "config").mkdir(parents=True)
    write_json_atomic(root / "config/datasets.yaml", {"toy": {"raw_file": "toy.csv"}})
    dataset_config = {"toy": {"raw_file": "toy.csv"}}
    monkeypatch.setattr(
        "src.utils.frozen_evidence.verify_frozen_evidence",
        lambda *args: {"freeze_content_sha256": "f" * 64},
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("completed-run resume must not fit or aggregate")

    monkeypatch.setattr("src.pipelines.confirmatory.runner._prepare_run", forbidden)
    return root, destination, config, dataset_config, options


def test_completed_resume_is_read_only(closed_run):
    root, run, config, datasets, options = closed_run
    before = {str(path): sha256_file(path) for path in run.rglob("*") if path.is_file()}
    assert execute_confirmatory_run(root, config, datasets, options) == run
    after = {str(path): sha256_file(path) for path in run.rglob("*") if path.is_file()}
    assert before == after


def test_corrupted_completion_is_rejected_without_execution(closed_run):
    root, run, config, datasets, options = closed_run
    completion = run / "completion.json"
    data = json.loads(completion.read_text())
    data["stored_cells"] = 1
    write_json_atomic(completion, data)
    with pytest.raises(RuntimeError, match="content hash"):
        execute_confirmatory_run(root, config, datasets, options)


def test_changed_study_inputs_remain_a_blocker_for_closed_resume(closed_run, monkeypatch):
    root, _, config, datasets, options = closed_run

    def changed(*args):
        raise RuntimeError("protected study input changed")

    monkeypatch.setattr("src.utils.frozen_evidence.verify_frozen_evidence", changed)
    with pytest.raises(RuntimeError, match="protected study input"):
        execute_confirmatory_run(root, config, datasets, options)


def test_changed_dataset_argument_cannot_be_silently_ignored(closed_run):
    root, _, config, _, options = closed_run
    with pytest.raises(RuntimeError, match="dataset settings"):
        execute_confirmatory_run(root, config, {"toy": {"raw_file": "altered.csv"}}, options)
