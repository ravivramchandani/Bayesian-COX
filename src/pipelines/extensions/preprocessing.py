"""Training-only expression selection and valid source-variable prior resampling."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.data.fold_preprocessing import FoldFeaturePreprocessor
from src.models.catalytic import CatalyticData
from src.utils.reproducibility import canonical_json_hash


class ExtensionPreprocessor:
    """Compose unchanged clinical preprocessing with train-selected expression.

    Genes are ranked by pre-standardization variance, with identifier ties.
    Constant encoded columns are removed using training rows alone.
    """

    def __init__(self, feature_spec: dict[str, Any], gene_budget: int = 0) -> None:
        """Set up the clinical preprocessor and the number of expression genes to keep.

        Args:
            feature_spec: Clinical feature specification, as used by the
                confirmatory ``FoldFeaturePreprocessor``.
            gene_budget: Number of highest-variance genes, ranked on training
                rows, to add as predictors; 0 means clinical predictors only.
        """
        self.clinical = FoldFeaturePreprocessor(feature_spec)
        self.gene_budget = int(gene_budget)
        self.genes: list[str] = []

    def fit(self, frame: pd.DataFrame) -> ExtensionPreprocessor:
        """Learn imputation, gene rank and scaling without validation rows."""
        clinical = self.clinical.fit_transform(frame)
        self.keep_clinical = [c for c in clinical if np.std(clinical[c]) > 1e-12]
        self.gene_state: dict[str, dict[str, float]] = {}
        if self.gene_budget:
            names = sorted(c for c in frame if c.startswith("gene:"))
            values = frame[names].replace([np.inf, -np.inf], np.nan)
            available = values.columns[values.isna().mean() <= 0.2]
            medians = values[available].median()
            filled = values[available].fillna(medians)
            variance = filled.var(ddof=0)
            ranked = sorted((c for c in available if variance[c] > 1e-12),
                            key=lambda c: (-float(variance[c]), c))
            self.genes = ranked[:self.gene_budget]
            if len(self.genes) != self.gene_budget:
                raise ValueError("fewer informative genes than the frozen budget")
            self.gene_state = {c: {"median": float(medians[c]), "mean": float(filled[c].mean()),
                                   "scale": float(np.sqrt(variance[c]))} for c in self.genes}
        self.feature_names = self.keep_clinical + self.genes
        if not self.feature_names:
            raise ValueError("no informative training features")
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Apply exactly the training-selected columns and transformations."""
        result = self.clinical.transform(frame)[self.keep_clinical].copy()
        genes = {}
        for c in self.genes:
            state = self.gene_state[c]
            values = pd.to_numeric(frame[c], errors="coerce").replace([np.inf, -np.inf], np.nan)
            genes[c] = (values.fillna(state["median"]) - state["mean"]) / state["scale"]
        return pd.concat([result, pd.DataFrame(genes, index=frame.index)], axis=1)[self.feature_names]

    def metadata(self) -> dict[str, Any]:
        """Record the complete training-derived preprocessing state."""
        state = {"clinical": self.clinical.metadata(), "keep_clinical": self.keep_clinical,
                 "gene_budget": self.gene_budget, "gene_state": self.gene_state,
                 "feature_names": self.feature_names}
        return {**state, "state_sha256": canonical_json_hash(state)}


def generate_catalytic_data(
    training: pd.DataFrame, processor: ExtensionPreprocessor,
    time: np.ndarray, event: np.ndarray, seed: int,
) -> tuple[CatalyticData, dict[str, Any]]:
    """Generate prior rows from source marginals, retaining whole category levels.

    The rate is the training censored-exponential MLE on the model's scaled
    time axis. The caller passes only its current (outer or inner) training.
    Derived clinical features are recomputed by the training transformer.
    """
    rng = np.random.default_rng(seed)
    p = len(processor.feature_names)
    count = max(1000, 4 * p)
    sources = list(dict.fromkeys(processor.clinical.required_source_columns + processor.genes))
    synthetic = pd.DataFrame({c: rng.choice(training[c].to_numpy(), size=count, replace=True)
                              for c in sources})
    scale = float(np.median(time[event == 1]))
    hazard = float(np.sum(event) / np.sum(time / scale))
    if not np.isfinite(hazard) or hazard <= 0:
        raise ValueError("cannot fit the training exponential reference")
    synthetic_time = rng.exponential(1 / hazard, size=count)
    data = CatalyticData(processor.transform(synthetic).to_numpy(float), synthetic_time, hazard)
    metadata = {"seed": seed, "M": count, "p": p, "time_scale": scale,
                "hazard_scaled": hazard, "source_variables": sources,
                "synthetic_sha256": canonical_json_hash({"X": data.design.tolist(), "time": data.time.tolist()}),
                "purpose": "synthetic prior data; no real or evaluation observations"}
    return data, metadata
