"""Transform survival predictors using state learned only from training rows.

The pipelines call ``FoldFeaturePreprocessor.fit_transform`` for training
data and ``transform`` for held-out data. ``metadata`` and ``from_metadata``
preserve the learned medians, scaling, category order and content hash for
saved predictions and explanation. No outcome-aware selection occurs here.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from src.utils.reproducibility import canonical_json_hash

MISSING_CATEGORY = "__MISSING__"
UNKNOWN_CATEGORY = "__UNKNOWN__"


def _as_category(series: pd.Series) -> pd.Series:
    """Replace missing categories with a sentinel and stringify all values."""
    values = series.astype("object")
    values = values.where(values.notna(), MISSING_CATEGORY)
    return values.astype(str)


class FoldFeaturePreprocessor:
    """Fit imputation, encoding and scaling on one training fold only.

    Numeric and engineered columns use training medians and population
    standard deviations. Ordinal columns use declared integer levels;
    categorical columns use all but the first sorted training level.

    Args:
        feature_spec: A feature-set declaration from ``config/datasets.yaml``
            with numeric/categorical names, ordered levels and optional
            engineered expressions with their source-feature names.
    """

    def __init__(self, feature_spec: dict[str, Any]) -> None:
        """Store the feature declaration and initialise empty learned state."""
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
        """Return source-column names once each, in declaration order.

        Returns:
            Numeric, categorical, ordinal and engineered-source names, without
            the derived columns created by the processor itself.
        """
        columns = self.numeric + self.categorical + list(self.ordinal)
        for declaration in self.engineered:
            columns.extend(declaration.get("source_features", []))
        return list(dict.fromkeys(columns))

    def _check_columns(self, frame: pd.DataFrame) -> None:
        """Reject frames missing any column declared as a source feature."""
        missing = [c for c in self.required_source_columns if c not in frame]
        if missing:
            raise ValueError(f"feature set requires missing source columns: {missing}")

    @staticmethod
    def _engineered_value(frame: pd.DataFrame, expression: str) -> pd.Series:
        """Evaluate one supported log, threshold or product expression.

        Args:
            frame: Source columns aligned by subject index.
            expression: Exact expression text from the feature declaration;
                expressions are pattern-matched rather than evaluated as code.
        """
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
        """Copy required sources and append declared derived features in order."""
        self._check_columns(frame)
        result = frame[self.required_source_columns].copy()
        for declaration in self.engineered:
            name = declaration["name"]
            if name in result.columns:
                raise ValueError(f"engineered feature would overwrite {name!r}")
            result[name] = self._engineered_value(result, declaration["expression"])
        return result

    def fit(self, frame: pd.DataFrame) -> FoldFeaturePreprocessor:
        """Learn imputation, scaling and category order from training rows.

        Missing or unknown ordinal levels receive -1 before scaling. Sorted
        categorical levels fix both the reference category and output order;
        a feature's encoded columns retain their source-group name.

        Args:
            frame: Training subjects as rows, with all required source columns.

        Returns:
            This processor with its learned state and content hash populated.

        Raises:
            ValueError: Sources are missing, an engineered expression is
                unsupported or overwrites a source, a log source is negative,
                a numeric median is non-finite, or ordinal levels repeat.
        """
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
            # A constant predictor keeps its centred value without dividing by zero.
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
        """Apply learned training-fold state without changing it.

        Unseen categorical levels produce zeros in every stored indicator
        column, as does the reference level. Missing categories are explicit
        only when the missing sentinel was present among training levels.

        Args:
            frame: New subjects with all required source columns.

        Returns:
            A float frame of shape ``(n_subjects, n_encoded_features)`` with
            the original index and the learned ``feature_names`` order.

        Raises:
            RuntimeError: ``fit`` or ``from_metadata`` has not populated state.
            ValueError: Sources or engineered-feature values are invalid.
        """
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
        """Fit on and transform the same training subjects.

        Args:
            frame: Training rows with all declared source columns.

        Returns:
            The encoded float frame returned by ``transform``.

        Raises:
            ValueError: ``fit`` or ``transform`` rejects the supplied features.
        """
        return self.fit(frame).transform(frame)

    @classmethod
    def from_metadata(
        cls, feature_spec: dict[str, Any], metadata: dict[str, Any]
    ) -> FoldFeaturePreprocessor:
        """Restore learned state and verify its hash with the feature declaration.

        Args:
            feature_spec: The same declaration used by the fitted processor.
            metadata: State returned by ``metadata``, including its hash.

        Returns:
            A fitted processor ready to transform rows without learning again.

        Raises:
            KeyError: A required state field is absent.
            ValueError: Stored values cannot be converted or the reconstructed
                state hash differs from ``training_state_sha256``.
        """
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
        """Return learned state for result lineage and leakage audits.

        Returns:
            A mapping of medians, scaling, levels, feature order/groups and
            the state hash. Its nested containers share this processor's state.

        Raises:
            RuntimeError: The processor has not been fitted or restored.
        """
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
