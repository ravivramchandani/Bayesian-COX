"""Config-backed CSV loader shared by all survival datasets."""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = PROJECT_ROOT / "config" / "datasets.yaml"


@lru_cache(maxsize=1)
def _dataset_specs() -> dict[str, dict[str, Any]]:
    with CONFIG_PATH.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def configured_primary_features(dataset_name: str) -> list[str]:
    """Return the authoritative primary raw-feature list from configuration."""
    try:
        spec = _dataset_specs()[dataset_name]
    except KeyError as exc:
        raise ValueError(f"Unknown configured dataset: {dataset_name}") from exc

    features = spec["primary_features"]
    columns = [
        *(features.get("numeric") or []),
        *(features.get("categorical") or []),
        *(features.get("ordinal") or {}).keys(),
    ]
    if len(columns) != len(set(columns)):
        raise ValueError(f"Duplicate primary features configured for {dataset_name}")
    return columns


class BaseDataset:
    """Load one configured cohort without duplicating its schema in Python."""

    def __init__(
        self, data_path: str | None = None, dataset_name: str | None = None
    ) -> None:
        self._dataset_name = dataset_name
        self._data: list[dict[str, Any]] = []
        self._feature_names: list[str] = []
        self._duration_col = "duration"
        self._event_col = "event"

        if dataset_name is None:
            self.data_path = data_path
            return

        try:
            spec = _dataset_specs()[dataset_name]
        except KeyError as exc:
            raise ValueError(f"Unknown configured dataset: {dataset_name}") from exc

        self.data_path = data_path or str(PROJECT_ROOT / spec["raw_file"])
        self._duration_col = spec["duration_col"]
        self._event_col = spec["event_col"]
        self._feature_names = configured_primary_features(dataset_name)

    def load(self) -> BaseDataset:
        """Load the configured CSV file."""
        if not self.data_path or not Path(self.data_path).exists():
            raise FileNotFoundError(f"Dataset file not found at '{self.data_path}'")

        with Path(self.data_path).open(encoding="utf-8") as stream:
            self._data = list(csv.DictReader(stream))
        return self

    def validate_schema(self) -> bool:
        """Require every configured feature and both survival outcomes."""
        if not self._data:
            raise ValueError("Dataset is empty. Call .load() first.")

        required = [*self._feature_names, self._duration_col, self._event_col]
        missing = [column for column in required if column not in self._data[0]]
        if missing:
            raise KeyError(f"Configured columns missing from dataset: {missing}")
        return True

    def get_features_and_target(
        self,
    ) -> tuple[list[dict[str, Any]], list[float], list[int]]:
        """Return primary feature mappings, durations and event indicators."""
        if not self._data:
            self.load()
        self.validate_schema()

        features = [
            {name: row[name] for name in self._feature_names} for row in self._data
        ]
        duration = [float(row[self._duration_col]) for row in self._data]
        event = [int(row[self._event_col]) for row in self._data]
        return features, duration, event
