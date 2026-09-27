"""Real-cohort fixtures prepared with the active outer-fold data path."""

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
    """Source rows, outcomes and training-only transformations for one real outer fold."""

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
        return self.folds[0]

    def model_frames(self) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
        """Return feature frames with positional outcome columns for model tests."""
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
    """Load the pinned raw cohort and prepare its first frozen-design outer fold."""
    dataset_config = read_mapping(PROJECT_ROOT / "config/datasets.yaml")[dataset]
    protocol = read_mapping(PROJECT_ROOT / "config/confirmatory.yaml")
    raw, time, event, subject_ids = load_analysis_dataset(PROJECT_ROOT, dataset, dataset_config)
    design = protocol["validation"]
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
