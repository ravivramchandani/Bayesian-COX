"""DeepSurv comparator implemented with the reference pycox CoxPH model."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.models.base import BaseSurvivalModel


class DeepSurvModel(BaseSurvivalModel):
    """Neural proportional-hazards model backed by ``pycox.models.CoxPH``.

    The validation subset is drawn only from the data passed to :meth:`fit`.
    Outer validation/test observations therefore cannot influence early
    stopping. Inputs are expected to have been imputed, encoded and scaled by
    the enclosing training-fold preprocessor.
    """

    def __init__(
        self,
        hidden_dims: list[int] | None = None,
        dropout: float = 0.2,
        activation: str = "relu",
        batch_norm: bool = True,
        learning_rate: float = 1e-3,
        l2_reg: float = 1e-3,
        batch_size: int = 64,
        epochs: int = 100,
        patience: int = 15,
        min_delta: float = 1e-4,
        validation_fraction: float = 0.2,
        random_state: int = 42,
    ) -> None:
        self.hidden_dims = list(hidden_dims or [32, 16])
        self.dropout = float(dropout)
        self.activation = activation.lower()
        self.batch_norm = bool(batch_norm)
        self.learning_rate = float(learning_rate)
        self.l2_reg = float(l2_reg)
        self.batch_size = int(batch_size)
        self.epochs = int(epochs)
        self.patience = int(patience)
        self.min_delta = float(min_delta)
        self.validation_fraction = float(validation_fraction)
        self.random_state = int(random_state)

        self.feature_names: list[str] = []
        self.model: Any | None = None
        self.training_log: pd.DataFrame = pd.DataFrame()
        self.feature_importances_: dict[str, float] | None = None

    @staticmethod
    def _dependencies() -> tuple[Any, Any, Any]:
        try:
            import torch
            import torchtuples as tt
            from pycox.models import CoxPH
        except ImportError as exc:  # pragma: no cover - exercised in clean-env checks
            raise ImportError(
                "DeepSurv requires pinned torch, torchtuples and pycox dependencies"
            ) from exc
        return torch, tt, CoxPH

    def _split_training_validation(
        self, events: np.ndarray
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return deterministic event-stratified train/validation indices."""
        n = len(events)
        if n < 20 or not 0.0 < self.validation_fraction < 0.5:
            return np.arange(n), np.array([], dtype=int)

        rng = np.random.default_rng(self.random_state)
        validation: list[int] = []
        training: list[int] = []
        for label in np.unique(events):
            indices = np.flatnonzero(events == label)
            rng.shuffle(indices)
            n_val = max(1, int(round(len(indices) * self.validation_fraction)))
            n_val = min(n_val, max(0, len(indices) - 2))
            validation.extend(indices[:n_val].tolist())
            training.extend(indices[n_val:].tolist())

        if not validation or len(training) < 4:
            return np.arange(n), np.array([], dtype=int)
        return np.asarray(training, dtype=int), np.asarray(validation, dtype=int)

    def fit(
        self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray
    ) -> DeepSurvModel:
        """Fit the neural Cox partial-likelihood model and Breslow baseline."""
        torch, tt, CoxPH = self._dependencies()
        if len(X) == 0:
            raise ValueError("DeepSurv requires at least one training observation")

        self.feature_names = list(X.columns)
        x_all = X[self.feature_names].to_numpy(dtype="float32", copy=True)
        durations = np.asarray(y_time, dtype="float32")
        events = np.asarray(y_event, dtype="float32")
        if len(x_all) != len(durations) or len(durations) != len(events):
            raise ValueError("X, y_time and y_event must contain the same rows")
        if not np.isfinite(x_all).all() or not np.isfinite(durations).all():
            raise ValueError("DeepSurv inputs must be finite after fold preprocessing")
        if np.any(durations <= 0):
            raise ValueError("Survival durations must be strictly positive")
        if int(events.sum()) < 2:
            raise ValueError("DeepSurv requires at least two observed events")

        np.random.seed(self.random_state)
        torch.manual_seed(self.random_state)
        torch.use_deterministic_algorithms(True, warn_only=True)
        torch.set_num_threads(1)

        activation_map = {
            "relu": torch.nn.ReLU,
            "selu": torch.nn.SELU,
            "tanh": torch.nn.Tanh,
        }
        if self.activation not in activation_map:
            raise ValueError(
                f"Unsupported activation {self.activation!r}; use one of "
                f"{sorted(activation_map)}"
            )

        net = tt.practical.MLPVanilla(
            in_features=x_all.shape[1],
            num_nodes=self.hidden_dims,
            out_features=1,
            batch_norm=self.batch_norm,
            dropout=self.dropout,
            activation=activation_map[self.activation],
            output_bias=False,
        )
        optimizer = tt.optim.Adam(
            lr=self.learning_rate,
            weight_decay=self.l2_reg,
        )
        model = CoxPH(net, optimizer, device="cpu")

        train_idx, val_idx = self._split_training_validation(events)
        train_input = x_all[train_idx]
        train_target = (durations[train_idx], events[train_idx])
        val_data = None
        callbacks: list[Any] = []
        if len(val_idx):
            val_data = (x_all[val_idx], (durations[val_idx], events[val_idx]))
            callbacks.append(
                tt.callbacks.EarlyStopping(
                    patience=self.patience,
                    min_delta=self.min_delta,
                    checkpoint_model=True,
                    load_best=True,
                )
            )

        log = model.fit(
            train_input,
            train_target,
            batch_size=min(self.batch_size, len(train_idx)),
            epochs=self.epochs,
            callbacks=callbacks,
            verbose=False,
            val_data=val_data,
            shuffle=True,
        )
        model.compute_baseline_hazards(x_all, (durations, events))

        self.model = model
        try:
            self.training_log = log.to_pandas()
        except (AttributeError, TypeError):
            self.training_log = pd.DataFrame()
        return self

    def predict_risk(self, X: pd.DataFrame) -> np.ndarray:
        """Return neural log-risk; larger values imply higher hazard."""
        self._check_fitted()
        x = X[self.feature_names].to_numpy(dtype="float32", copy=True)
        return np.asarray(self.model.predict(x), dtype=float).reshape(-1)

    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Return right-continuous Breslow survival estimates at given times."""
        self._check_fitted()
        times = np.asarray(eval_times, dtype=float)
        if times.ndim != 1 or len(times) == 0 or np.any(np.diff(times) < 0):
            raise ValueError("eval_times must be a non-empty sorted vector")

        x = X[self.feature_names].to_numpy(dtype="float32", copy=True)
        surv_df = self.model.predict_surv_df(x)
        grid = surv_df.index.to_numpy(dtype=float)
        grid_surv = surv_df.to_numpy(dtype=float).T
        result = np.ones((len(x), len(times)), dtype=float)
        indices = np.searchsorted(grid, times, side="right") - 1
        valid = indices >= 0
        if np.any(valid):
            bounded = np.minimum(indices[valid], len(grid) - 1)
            result[:, valid] = grid_surv[:, bounded]
        return np.clip(result, 1e-8, 1.0)

    def permutation_importance(
        self,
        X: pd.DataFrame,
        y_time: np.ndarray,
        y_event: np.ndarray,
        n_repeats: int = 5,
    ) -> pd.DataFrame:
        """Estimate validation-set concordance loss after feature permutation."""
        from src.evaluation.metrics import concordance_index

        baseline, _ = concordance_index(y_time, y_event, self.predict_risk(X))
        rng = np.random.default_rng(self.random_state)
        rows = []
        for feature in self.feature_names:
            drops = []
            for _ in range(n_repeats):
                permuted = X.copy()
                permuted[feature] = rng.permutation(permuted[feature].to_numpy())
                score, _ = concordance_index(
                    y_time, y_event, self.predict_risk(permuted)
                )
                drops.append(baseline - score)
            rows.append(
                {
                    "feature": feature,
                    "importance_mean": float(np.mean(drops)),
                    "importance_std": float(np.std(drops, ddof=1))
                    if n_repeats > 1
                    else 0.0,
                }
            )
        self.feature_importances_ = {
            row["feature"]: row["importance_mean"] for row in rows
        }
        return pd.DataFrame(rows).sort_values(
            "importance_mean", ascending=False
        ).reset_index(drop=True)

    def get_summary(self) -> pd.DataFrame:
        """Return the fitted architecture and training configuration."""
        rows = [
            {"component": "input_features", "value": len(self.feature_names)},
            {"component": "hidden_dims", "value": str(self.hidden_dims)},
            {"component": "activation", "value": self.activation},
            {"component": "dropout", "value": self.dropout},
            {"component": "batch_norm", "value": self.batch_norm},
            {"component": "learning_rate", "value": self.learning_rate},
            {"component": "weight_decay", "value": self.l2_reg},
            {"component": "epochs_requested", "value": self.epochs},
            {"component": "epochs_completed", "value": len(self.training_log)},
        ]
        return pd.DataFrame(rows)

    def _check_fitted(self) -> None:
        if self.model is None:
            raise RuntimeError("Model is not fitted. Call fit() first.")
