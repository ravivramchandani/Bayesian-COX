"""Load a study cohort and choose the feature set its models use.

Every confirmatory and robustness cell starts here. The cohort CSV named in
``config/datasets.yaml`` is read unchanged, its survival outcome and subject
identifiers are checked, and one feature-set declaration is selected for the
fold-local preprocessor (``src.data.fold_preprocessing``).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def load_analysis_dataset(
    project_root: Path,
    dataset_key: str,
    dataset_config: dict[str, Any],
) -> tuple[pd.DataFrame, np.ndarray, np.ndarray, np.ndarray]:
    """Read one cohort CSV and validate its outcome and subject identifiers.

    Args:
        project_root: Repository root; ``dataset_config["raw_file"]`` is relative to it.
        dataset_key: Cohort key in ``config/datasets.yaml``, for example ``"gbsg2"``.
        dataset_config: That cohort's entry in ``config/datasets.yaml``. It names
            the CSV (``raw_file``), the outcome columns (``duration_col``,
            ``event_col``) and, optionally, a subject ID column (``id_col``).

    Returns:
        ``(frame, times, events, subject_ids)``: the unmodified CSV, follow-up
        times as floats, event indicators as integers (1 = event, 0 =
        censored), and one unique string identifier per row. A cohort without
        ``id_col`` gets identifiers ``"<dataset_key>-<row number>"``,
        zero-padded to equal width.

    Raises:
        FileNotFoundError: The CSV does not exist.
        ValueError: An outcome or ID column is missing, a time is missing or not
            positive, the event indicator is not 0/1, there are fewer than two
            events or two censored subjects, or identifiers are not unique.
    """
    path = project_root / dataset_config["raw_file"]
    if not path.is_file():
        raise FileNotFoundError(f"authoritative raw dataset is missing: {path}")
    frame = pd.read_csv(path)
    time_values, events = _survival_outcome(
        frame, dataset_key, dataset_config["duration_col"], dataset_config["event_col"]
    )
    subject_ids = _subject_identifiers(frame, dataset_key, dataset_config.get("id_col"))
    return frame, time_values, events, subject_ids


def _survival_outcome(
    frame: pd.DataFrame, dataset_key: str, duration_col: str, event_col: str
) -> tuple[np.ndarray, np.ndarray]:
    """Return validated follow-up times (float) and event indicators (int)."""
    missing = [name for name in (duration_col, event_col) if name not in frame]
    if missing:
        raise ValueError(f"{dataset_key} is missing outcome columns {missing}")

    time_values = pd.to_numeric(frame[duration_col], errors="coerce").to_numpy(float)
    event_values = pd.to_numeric(frame[event_col], errors="coerce").to_numpy(float)
    if not np.isfinite(time_values).all() or np.any(time_values <= 0):
        raise ValueError(f"{dataset_key} contains non-positive or missing survival time")
    if not np.isin(event_values, [0.0, 1.0]).all():
        raise ValueError(f"{dataset_key} event indicator is not binary")
    events = event_values.astype(int)
    if events.sum() < 2 or (len(events) - events.sum()) < 2:
        raise ValueError(f"{dataset_key} requires both events and censoring")
    return time_values, events


def _subject_identifiers(frame: pd.DataFrame, dataset_key: str, id_col: str | None) -> np.ndarray:
    """Return one unique string identifier per row, generated when ``id_col`` is unset."""
    if id_col:
        if id_col not in frame:
            raise ValueError(f"{dataset_key} is missing ID column {id_col!r}")
        subject_ids = frame[id_col].astype(str).to_numpy()
    else:
        width = len(str(len(frame)))
        subject_ids = np.asarray(
            [f"{dataset_key}-{index:0{width}d}" for index in range(len(frame))]
        )
    if len(set(subject_ids)) != len(subject_ids):
        raise ValueError(f"{dataset_key} subject identifiers are not unique")
    return subject_ids


def select_feature_spec(dataset_config: dict[str, Any], feature_set: str) -> dict[str, Any]:
    """Return a copy of one feature-set declaration for a cohort.

    ``"primary"`` selects ``primary_features``. Any other name selects the
    complete specification of that name under ``sensitivity_feature_sets``.

    Raises:
        ValueError: The cohort declares no feature set with that name.
    """
    if feature_set == "primary":
        return dict(dataset_config["primary_features"])
    sensitivities = dataset_config.get("sensitivity_feature_sets", {})
    if feature_set not in sensitivities:
        raise ValueError(f"dataset {dataset_config['name']} has no feature set {feature_set!r}")
    return dict(sensitivities[feature_set])
