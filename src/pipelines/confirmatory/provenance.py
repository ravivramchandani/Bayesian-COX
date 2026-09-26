"""Check the original live inputs and content-addressed protocol before confirmatory execution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.utils.reproducibility import canonical_json_hash, sha256_file

from .storage import _load_yaml


def relevant_input_files(project_root: Path, datasets: tuple[str, ...]) -> list[str]:
    """Return every code, configuration, environment and data input used here."""
    files = [
        "Makefile",
        "config/confirmatory.yaml",
        "config/datasets.yaml",
        "coordination/DECISIONS.md",
        "data/manifest.yaml",
        "docs/claim_evidence_register.md",
        "docs/study_protocol.md",
        "environment.yml",
        "pyproject.toml",
        "conda-lock.yml",
        "conda-lock.yml.sha256",
        "conda-lock-virtual-packages.yml",
        "scripts/verify_environment.py",
        "scripts/run_confirmatory_explainability.py",
        "scripts/run_confirmatory.py",
        "scripts/run_robustness.py",
        "scripts/freeze_protocol.py",
        "scripts/render_confirmatory.py",
        "src/data/fold_preprocessing.py",
        "src/data/survival_folds.py",
        "src/evaluation/calibration.py",
        "src/evaluation/metrics.py",
        "src/explainability/__init__.py",
        "src/explainability/frozen_cells.py",
        "src/explainability/posterior_analysis.py",
        "src/explainability/shap_analysis.py",
        "src/models/base.py",
        "src/models/cox.py",
        "src/models/deepsurv.py",
        "src/models/random_survival_forest.py",
        "src/models/bayesian/diagnostics.py",
        "src/models/bayesian/model.py",
        "src/pipelines/confirmatory.py",
        "src/pipelines/robustness.py",
        "src/statistics/bootstrap.py",
        "src/statistics/hypothesis_tests.py",
        "src/statistics/repeated_cv.py",
        "src/utils/reproducibility.py",
    ]
    # Importing a submodule executes its parent packages' ``__init__.py`` files,
    # and several compatibility initialisers import additional local modules.
    # Freeze every source module so no executed or transitively imported project
    # code can change while an otherwise valid content freeze still passes.
    files.extend(
        str(path.relative_to(project_root))
        for path in project_root.glob("src/**/*.py")
        if path.is_file()
    )
    dataset_config = _load_yaml(project_root / "config" / "datasets.yaml")
    files.extend(dataset_config[name]["raw_file"] for name in datasets)
    return sorted(set(files))


def verify_protocol_freeze(project_root: Path, inputs: list[str]) -> dict[str, Any]:
    """Verify the content-addressed protocol freeze before confirmatory fitting."""
    freeze_path = project_root / "config" / "protocol_freeze.json"
    if not freeze_path.is_file():
        raise RuntimeError("config/protocol_freeze.json is required for confirmatory mode")
    freeze = json.loads(freeze_path.read_text(encoding="utf-8"))
    claimed = freeze.get("freeze_content_sha256")
    unhashed = dict(freeze)
    unhashed.pop("freeze_content_sha256", None)
    if claimed != canonical_json_hash(unhashed):
        raise RuntimeError("protocol freeze content hash is invalid")
    expected = freeze.get("frozen_input_sha256", {})
    verify_run_inputs_unchanged(project_root, expected, inputs, label="protocol freeze")
    if not freeze.get("no_comparative_effects_inspected_before_freeze", False):
        raise RuntimeError("protocol freeze lacks the result-blind rehearsal attestation")
    return freeze


def verify_run_inputs_unchanged(
    project_root: Path,
    expected: dict[str, str],
    inputs: list[str],
    *,
    label: str = "run manifest",
) -> None:
    """Fail if any content-addressed run input changed since it was recorded."""
    current = {
        relative: sha256_file(project_root / relative)
        if (project_root / relative).is_file()
        else "MISSING"
        for relative in inputs
    }
    if expected != current:
        changed = sorted(
            name for name in set(expected) | set(current) if expected.get(name) != current.get(name)
        )
        raise RuntimeError(f"confirmatory inputs differ from the {label}: " + ", ".join(changed))
