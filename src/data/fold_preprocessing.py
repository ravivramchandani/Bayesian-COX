"""Fold-local preprocessing for the confirmatory survival analysis."""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from src.utils.reproducibility import canonical_json_hash

MISSING_CATEGORY = "__MISSING__"
UNKNOWN_CATEGORY = "__UNKNOWN__"


def _as_category(series: pd.Series) -> pd.Series:
    values = series.astype("object")
    values = values.where(values.notna(), MISSING_CATEGORY)
    return values.astype(str)


class FoldFeaturePreprocessor:
    """Fit imputation, encoding and scaling on one training fold only.

    The input ``feature_spec`` is one complete feature-set entry from
    ``config/datasets.yaml``. No outcome-aware selection occurs here.
    """

    def __init__(self, feature_spec: dict[str, Any]) -> None:
        self.feature_spec = feature_spec
        self.numeric = list(feature_spec.get("numeric", []))
        self.categorical = list(feature_spec.get("categorical", []))
        self.ordinal = {
            name: list(levels)
            for name, levels in feature_spec.get("ordinal", {}).items()
        }
        self.engineered = list(feature_spec.get("engineered", []))

        self.imputation_values: dict[str, float] = {}
        self.scaling: dict[str, dict[str, float]] = {}
        self.category_levels: dict[str, list[str]] = {}
        self.ordinal_maps: dict[str, dict[str, int]] = {}
        self.feature_names: list[str] = []
        self.feature_groups: dict[str, str] = {}
        self.training_state_sha256: str | None = None
        self._fitted = False

    @property
    def required_source_columns(self) -> list[str]:
        columns = self.numeric + self.categorical + list(self.ordinal)
        for declaration in self.engineered:
            columns.extend(declaration.get("source_features", []))
        return list(dict.fromkeys(columns))

    def _check_columns(self, frame: pd.DataFrame) -> None:
        missing = [c for c in self.required_source_columns if c not in frame]
        if missing:
            raise ValueError(f"feature set requires missing source columns: {missing}")

    @staticmethod
    def _engineered_value(frame: pd.DataFrame, expression: str) -> pd.Series:
        log_match = re.fullmatch(r"log1p\(([^)]+)\)", expression)
        if log_match:
            source = pd.to_numeric(frame[log_match.group(1)], errors="coerce")
            if bool((source.dropna() < 0).any()):
                raise ValueError(f"{expression} is undefined for negative source values")
            return np.log1p(source)

        threshold_match = re.fullmatch(
            r"indicator\(([^ ]+) < (-?[0-9]+(?:\.[0-9]+)?)\)", expression
        )
        if threshold_match:
            source = pd.to_numeric(frame[threshold_match.group(1)], errors="coerce")
            threshold = float(threshold_match.group(2))
            return (source < threshold).where(source.notna()).astype(float)

        numeric_product = re.fullmatch(
            r"([^ ]+) \* as_numeric\(([^)]+)\)", expression
        )
        if numeric_product:
            left = pd.to_numeric(frame[numeric_product.group(1)], errors="coerce")
            right = pd.to_numeric(frame[numeric_product.group(2)], errors="coerce")
            return left * right

        plain_product = re.fullmatch(r"([^ ]+) \* ([^ ]+)", expression)
        if plain_product:
            left = pd.to_numeric(frame[plain_product.group(1)], errors="coerce")
            right = pd.to_numeric(frame[plain_product.group(2)], errors="coerce")
            return left * right

        indicator_product = re.fullmatch(
            r"([^ ]+) \* indicator\(lower\(([^)]+)\) in \{'yes', '1'\}\)",
            expression,
        )
        if indicator_product:
            left = pd.to_numeric(frame[indicator_product.group(1)], errors="coerce")
            right = (
                frame[indicator_product.group(2)]
                .astype(str)
                .str.lower()
                .isin({"yes", "1"})
                .astype(float)
            )
            return left * right

        raise ValueError(f"unsupported engineered-feature expression: {expression!r}")

    def _add_engineered(self, frame: pd.DataFrame) -> pd.DataFrame:
        self._check_columns(frame)
        result = frame[self.required_source_columns].copy()
        for declaration in self.engineered:
            name = declaration["name"]
            if name in result.columns:
                raise ValueError(f"engineered feature would overwrite {name!r}")
            result[name] = self._engineered_value(result, declaration["expression"])
        return result

    def fit(self, frame: pd.DataFrame) -> FoldFeaturePreprocessor:
        """Learn all preprocessing state from the supplied training rows."""
        work = self._add_engineered(frame)
        engineered_names = [item["name"] for item in self.engineered]
        numeric_outputs = self.numeric + engineered_names

        for name in numeric_outputs:
            values = pd.to_numeric(work[name], errors="coerce")
            median = float(values.median())
            if not np.isfinite(median):
                raise ValueError(f"numeric feature {name!r} has no finite training value")
            filled = values.fillna(median).to_numpy(dtype=float)
            mean = float(np.mean(filled))
            scale = float(np.std(filled, ddof=0))
            if not np.isfinite(scale) or scale <= 1e-12:
                scale = 1.0
            self.imputation_values[name] = median
            self.scaling[name] = {"mean": mean, "scale": scale}

        for name, levels in self.ordinal.items():
            mapping = {str(level): index for index, level in enumerate(levels)}
            if len(mapping) != len(levels):
                raise ValueError(f"ordinal feature {name!r} contains duplicate levels")
            self.ordinal_maps[name] = mapping
            encoded = _as_category(work[name]).map(mapping).fillna(-1).to_numpy(float)
            mean = float(np.mean(encoded))
            scale = float(np.std(encoded, ddof=0))
            if not np.isfinite(scale) or scale <= 1e-12:
                scale = 1.0
            self.scaling[name] = {"mean": mean, "scale": scale}

        for name in self.categorical:
            levels = sorted(_as_category(work[name]).unique().tolist())
            if not levels:
                levels = [MISSING_CATEGORY]
            self.category_levels[name] = levels

        feature_names = numeric_outputs + list(self.ordinal)
        groups = {name: name for name in self.numeric}
        groups.update({name: name for name in self.ordinal})
        for declaration in self.engineered:
            sources = declaration.get("source_features", [])
            groups[declaration["name"]] = " + ".join(sources) or declaration["name"]
        for name in self.categorical:
            reference, *non_reference = self.category_levels[name]
            del reference
            for level in non_reference:
                encoded_name = f"{name}={level}"
                feature_names.append(encoded_name)
                groups[encoded_name] = name

        self.feature_names = feature_names
        self.feature_groups = groups
        state = {
            "feature_spec": self.feature_spec,
            "imputation_values": self.imputation_values,
            "scaling": self.scaling,
            "category_levels": self.category_levels,
            "ordinal_maps": self.ordinal_maps,
            "feature_names": self.feature_names,
            "feature_groups": self.feature_groups,
        }
        self.training_state_sha256 = canonical_json_hash(state)
        self._fitted = True
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Apply frozen training-fold state to new rows."""
        if not self._fitted:
            raise RuntimeError("preprocessor is not fitted")
        work = self._add_engineered(frame)
        output: dict[str, np.ndarray] = {}

        numeric_outputs = self.numeric + [item["name"] for item in self.engineered]
        for name in numeric_outputs:
            values = pd.to_numeric(work[name], errors="coerce")
            values = values.fillna(self.imputation_values[name]).to_numpy(dtype=float)
            params = self.scaling[name]
            output[name] = (values - params["mean"]) / params["scale"]

        for name, mapping in self.ordinal_maps.items():
            values = _as_category(work[name]).map(mapping).fillna(-1).to_numpy(float)
            params = self.scaling[name]
            output[name] = (values - params["mean"]) / params["scale"]

        for name in self.categorical:
            observed = _as_category(work[name])
            known = set(self.category_levels[name])
            observed = observed.where(observed.isin(known), UNKNOWN_CATEGORY)
            _reference, *non_reference = self.category_levels[name]
            for level in non_reference:
                output[f"{name}={level}"] = (observed == level).to_numpy(float)

        result = pd.DataFrame(output, index=frame.index)
        return result[self.feature_names].astype(float)

    def fit_transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Fit on and transform a training fold."""
        return self.fit(frame).transform(frame)

    @classmethod
    def from_metadata(
        cls, feature_spec: dict[str, Any], metadata: dict[str, Any]
    ) -> FoldFeaturePreprocessor:
        """Restore a frozen transformer and verify its recorded state hash."""
        processor = cls(feature_spec)
        processor.imputation_values = {
            str(name): float(value)
            for name, value in metadata["imputation_values"].items()
        }
        processor.scaling = {
            str(name): {"mean": float(value["mean"]), "scale": float(value["scale"])}
            for name, value in metadata["scaling"].items()
        }
        processor.category_levels = {
            str(name): [str(level) for level in levels]
            for name, levels in metadata["category_levels"].items()
        }
        processor.ordinal_maps = {
            str(name): {str(level): int(index) for level, index in mapping.items()}
            for name, mapping in metadata["ordinal_maps"].items()
        }
        processor.feature_names = [str(name) for name in metadata["feature_names"]]
        processor.feature_groups = {
            str(name): str(group)
            for name, group in metadata["feature_groups"].items()
        }
        state = {
            "feature_spec": processor.feature_spec,
            "imputation_values": processor.imputation_values,
            "scaling": processor.scaling,
            "category_levels": processor.category_levels,
            "ordinal_maps": processor.ordinal_maps,
            "feature_names": processor.feature_names,
            "feature_groups": processor.feature_groups,
        }
        observed = canonical_json_hash(state)
        expected = str(metadata["training_state_sha256"])
        if observed != expected:
            raise ValueError("preprocessing metadata does not match its state hash")
        processor.training_state_sha256 = observed
        processor._fitted = True
        return processor

    def metadata(self) -> dict[str, Any]:
        """Return serialisable state for result lineage and leakage audits."""
        if not self._fitted:
            raise RuntimeError("preprocessor is not fitted")
        return {
            "imputation_values": self.imputation_values,
            "scaling": self.scaling,
            "category_levels": self.category_levels,
            "ordinal_maps": self.ordinal_maps,
            "feature_names": self.feature_names,
            "feature_groups": self.feature_groups,
            "training_state_sha256": self.training_state_sha256,
        }
