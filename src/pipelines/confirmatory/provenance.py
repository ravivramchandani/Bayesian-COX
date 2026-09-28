"""Check the original live inputs and content-addressed protocol before confirmatory execution.

:mod:`runner` uses these functions to record every input file's SHA-256 hash
in the run manifest, to refuse a resumed run whose inputs changed, and in
confirmatory mode to check the protocol freeze (``config/protocol_freeze.json``,
ADR-022) before the first fit and again around aggregation.

These checks compare the live working tree with the recorded hashes. Under
ADR-030 code and documentation may change after the freeze, so they pass only
for a checkout whose inputs still match it: an unfinished confirmatory run can
continue only on its original inputs. A completed run is verified instead
against the blobs stored in the checkpoint commit, by
:func:`src.utils.frozen_evidence.verify_frozen_evidence`.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.utils.reproducibility import canonical_json_hash, sha256_file

from .storage import _load_yaml


def relevant_input_files(project_root: Path, datasets: tuple[str, ...]) -> list[str]:
    """Return every code, configuration, environment and data input used here.

    The fixed list mirrors the inventory recorded by the protocol freeze. It
    still names the single-file modules ``src/pipelines/confirmatory.py`` and
    ``src/pipelines/robustness.py``, which exist only at the checkpoint; a new
    manifest records them as ``"MISSING"``. The current package modules are
    covered by the ``src/**/*.py`` glob.

    Args:
        project_root: Repository root.
        datasets: Cohort keys whose raw CSV files are added.

    Returns:
        Sorted, de-duplicated paths relative to ``project_root``.
    """
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
    """Verify the content-addressed protocol freeze before confirmatory fitting.

    The freeze record must match its own content hash, every listed input
    must still have its frozen hash in the live tree, and the record must
    attest that no comparative effect was inspected before the freeze.

    Args:
        project_root: Repository root.
        inputs: Input paths from :func:`relevant_input_files`.

    Returns:
        The freeze record.

    Raises:
        RuntimeError: The freeze file is missing, altered or lacks the
            attestation, or any input differs from its frozen hash.
    """
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
    """Fail if any content-addressed run input changed since it was recorded.

    Missing files hash as ``"MISSING"``, so a file that was recorded as
    missing must still be missing.

    Args:
        project_root: Repository root.
        expected: Recorded map from relative path to SHA-256 hash.
        inputs: Paths to hash now; the resulting map must equal ``expected``
            exactly, so an added or removed path also fails.
        label: Name of the record, used in the error message.

    Returns:
        None when the complete input mapping agrees.

    Raises:
        RuntimeError: Any path differs; the message lists them.
    """
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
