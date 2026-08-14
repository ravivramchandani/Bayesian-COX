"""Build processed train/val/test splits and CV folds for every dataset.

Dataset schemas are read from config/datasets.yaml.
"""

import os
import sys

import yaml

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.data.loader import DatasetLoader
from src.data.preprocessing import SurvivalDataPipeline

DATA_DIR = os.path.join(PROJECT_ROOT, "data")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config", "datasets.yaml")


def main() -> int:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        datasets = yaml.safe_load(f)

    for name, cfg in datasets.items():
        raw_df = DatasetLoader.load_raw(DATA_DIR, name)

        pipeline = SurvivalDataPipeline(
            dataset_name=name,
            time_col=cfg["duration_col"],
            event_col=cfg["event_col"],
            categorical_cols=cfg.get("categorical_features") or [],
            ordinal_cols=cfg.get("ordinal_features") or {},
            random_state=42,
        )

        metadata = pipeline.run(raw_df, output_dir=DATA_DIR)

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
