"""Real-cohort fixtures prepared with the active outer-fold data path.

Shared by the data, model and pipeline tests. A cohort is loaded with
``src.data.cohorts``, split with the frozen outer-fold design from
``config/confirmatory.yaml`` (``src.data.survival_folds``), and its primary
feature set is preprocessed by ``src.data.fold_preprocessing`` fitted on the
first fold's training rows only.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.data.cohorts import load_analysis_dataset, select_feature_spec
from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.data.survival_folds import SurvivalFold, repeated_survival_folds
from src.utils.io import read_mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass
class PreparedFold:
    """Source rows, outcomes and training-only transformations for one real outer fold.

    Attributes:
        raw: The unmodified cohort CSV, one row per subject.
        time: Follow-up times for every subject, in the cohort's own unit.
        event: Event indicators for every subject (1 = event, 0 = censored).
        subject_ids: One unique string identifier per subject.
        dataset_config: The cohort's entry in ``config/datasets.yaml``.
        folds: The outer folds of the first repeat.
        processor: Primary-feature preprocessor fitted on the first fold's
            training rows.
        train: Preprocessed first-fold training features, indexed like ``raw``.
        validation: Preprocessed first-fold validation features, indexed like ``raw``.
    """

    raw: pd.DataFrame
    time: np.ndarray
    event: np.ndarray
    subject_ids: np.ndarray
    dataset_config: dict[str, Any]
    folds: list[SurvivalFold]
    processor: FoldFeaturePreprocessor
    train: pd.DataFrame
    validation: pd.DataFrame

    @property
    def fold(self) -> SurvivalFold:
        """The first outer fold, from which ``train`` and ``validation`` were built."""
        return self.folds[0]

    def model_frames(self) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
        """Return copies of the fold frames with outcomes added, plus the feature names.

        ``time`` and ``event`` are taken from the cohort arrays at the fold's
        row positions. The returned feature list excludes those two columns.

        Returns:
            Training and validation frames with ``time`` and ``event`` columns,
            followed by the ordered predictor-column names.
        """
        train = self.train.copy()
        validation = self.validation.copy()
        for frame, indices in (
            (train, self.fold.train_indices),
            (validation, self.fold.validation_indices),
        ):
            frame["time"] = self.time[indices]
            frame["event"] = self.event[indices]
        return train, validation, list(self.train.columns)


def prepare_real_fold(dataset: str) -> PreparedFold:
    """Load the pinned raw cohort and prepare its first frozen-design outer fold.

    Args:
        dataset: Cohort key in ``config/datasets.yaml``: ``"gbsg2"``,
            ``"whas500"`` or ``"metabric"``.

    Returns:
        Cohort arrays, fold memberships and the first fold's transformed frames.
    """
    dataset_config = read_mapping(PROJECT_ROOT / "config/datasets.yaml")[dataset]
    protocol = read_mapping(PROJECT_ROOT / "config/confirmatory.yaml")
    raw, time, event, subject_ids = load_analysis_dataset(PROJECT_ROOT, dataset, dataset_config)
    design = protocol["validation"]
    # Each repeat's seed depends only on base_seed and the repeat number, so
    # one repeat reproduces the first repeat of the confirmatory design.
    folds = repeated_survival_folds(
        time,
        event,
        n_splits=int(design["outer_splits"]),
        n_repeats=1,
        base_seed=int(design["base_seed"]),
        max_time_bins=int(design["followup_time_bins"]),
    )
    fold = folds[0]
    processor = FoldFeaturePreprocessor(select_feature_spec(dataset_config, "primary"))
    processor.fit(raw.iloc[fold.train_indices])
    return PreparedFold(
        raw,
        time,
        event,
        subject_ids,
        dataset_config,
        folds,
        processor,
        processor.transform(raw.iloc[fold.train_indices]),
        processor.transform(raw.iloc[fold.validation_indices]),
    )
