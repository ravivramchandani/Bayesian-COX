"""Build processed train/val/test splits and CV folds for every dataset.

Dataset schemas are read from config/datasets.yaml.
"""

import os
import sys
from typing import Any

import pandas as pd
import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.data.feature_engineering import FeatureEngineer
from src.data.loader import DatasetLoader
from src.data.preprocessing import SurvivalDataPipeline

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "datasets.yaml")


class DeclaredFeatureEngineer:
    """Expose only engineered columns named in the selected feature specification."""

    def __init__(self, dataset_name: str, declared: list[dict[str, Any]]):
        self._delegate = FeatureEngineer(dataset_name)
        self._declared_names = [item["name"] for item in declared]

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        transformed = self._delegate.transform(frame)
        missing = [name for name in self._declared_names if name not in transformed.columns]
        if missing:
            raise ValueError(f"Configured engineered features were not produced: {missing}")
        return transformed[[*frame.columns, *self._declared_names]].copy()


def primary_feature_columns(cfg: dict[str, Any]) -> list[str]:
    """Return the unique raw predictors declared for the primary feature set."""
    feature_spec = cfg["primary_features"]
    columns = [
        *(feature_spec.get("numeric") or []),
        *(feature_spec.get("categorical") or []),
        *(feature_spec.get("ordinal") or {}).keys(),
    ]

    duplicates = sorted({column for column in columns if columns.count(column) > 1})
    if duplicates:
        raise ValueError(f"Primary feature specification contains duplicates: {duplicates}")

    reserved = {cfg["duration_col"], cfg["event_col"]}
    if cfg.get("id_col"):
        reserved.add(cfg["id_col"])
    invalid = sorted(set(columns) & reserved)
    if invalid:
        raise ValueError(f"Outcome/identifier columns cannot be model features: {invalid}")
    return columns


def select_primary_columns(
    raw_df: pd.DataFrame, cfg: dict[str, Any]
) -> tuple[pd.DataFrame, pd.Series | None]:
    """Select primary predictors/outcomes and keep identifiers out of the model.

    The returned identifier series preserves subject identity for audit and
    future fold manifests. It is intentionally separate so it cannot be
    encoded as a predictor by the legacy preprocessing pipeline.
    """
    features = primary_feature_columns(cfg)
    outcomes = [cfg["duration_col"], cfg["event_col"]]
    id_col = cfg.get("id_col")
    required = [*features, *outcomes, *([id_col] if id_col else [])]
    missing = [column for column in required if column not in raw_df.columns]
    if missing:
        raise ValueError(f"Raw dataset is missing configured columns: {missing}")

    identifiers = raw_df[id_col].copy() if id_col else None
    return raw_df[[*features, *outcomes]].copy(), identifiers


def main() -> int:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        datasets = yaml.safe_load(f)

    for name, cfg in datasets.items():
        raw_df = DatasetLoader.load_raw(DATA_DIR, name)
        model_df, _identifiers = select_primary_columns(raw_df, cfg)
        feature_spec = cfg["primary_features"]

        pipeline = SurvivalDataPipeline(
            dataset_name=name,
            time_col=cfg["duration_col"],
            event_col=cfg["event_col"],
            categorical_cols=feature_spec.get("categorical") or [],
            ordinal_cols=feature_spec.get("ordinal") or {},
            random_state=42,
        )
        pipeline.feature_engineer = DeclaredFeatureEngineer(
            name, feature_spec.get("engineered") or []
        )

        metadata = pipeline.run(model_df, output_dir=DATA_DIR)

        print(
            f"{name}: {raw_df.shape[0]} raw rows -> "
            f"train {metadata['train_samples']} / "
            f"val {metadata['val_samples']} / "
            f"test {metadata['test_samples']}, "
            f"{metadata['num_features']} features, "
            f"{metadata['train_censoring_rate']}% censored in train"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
