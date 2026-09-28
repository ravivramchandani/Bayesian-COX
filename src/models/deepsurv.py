"""DeepSurv comparator implemented with the reference pycox CoxPH model.

DeepSurv replaces the Cox linear predictor ``x beta`` with a neural network
``g(x)`` and trains it by minimising the negative Cox partial likelihood, so
it keeps the proportional-hazards form ``h(t | x) = h0(t) exp(g(x))``. After
training, the baseline hazard ``h0`` is estimated by Breslow's method.
The confirmatory pipeline chooses among four architectures and
regularisation settings by inner cross-validation.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.models.base import BaseSurvivalModel


class DeepSurvModel(BaseSurvivalModel):
    """Neural proportional-hazards model backed by ``pycox.models.CoxPH``.

    The validation subset is drawn only from data passed to :meth:`fit`.
    When callers supply only their training fold, outer validation/test
    observations cannot influence early stopping. Inputs are expected to
    have been imputed, encoded and scaled by the training-fold preprocessor.

    Args:
        hidden_dims: Hidden-layer widths; ``None`` or an empty list
            gives [32, 16].
        dropout: Dropout probability after each hidden layer.
        activation: ``"relu"``, ``"selu"`` or ``"tanh"``.
        batch_norm: Apply batch normalisation in each hidden layer.
        learning_rate: Adam learning rate.
        l2_reg: Adam weight decay.
        batch_size: Mini-batch size, capped at the training-subset size.
        epochs: Maximum training epochs.
        patience: Epochs without validation-loss improvement before
            early stopping.
        min_delta: Smallest loss decrease that counts as an improvement.
        validation_fraction: Share of each event group held out for
            early stopping; values outside (0, 0.5) disable it.
        random_state: Seed for NumPy, PyTorch and the early-stopping split.
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
        """Store network and training settings and initialise unfitted state."""
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
        """Load the optional torch, torchtuples and pycox CoxPH dependencies."""
        try:
            import torch
            import torchtuples as tt
            from pycox.models import CoxPH
        except ImportError as exc:  # pragma: no cover - exercised in clean-env checks
            raise ImportError(
                "DeepSurv requires pinned torch, torchtuples and pycox dependencies"
            ) from exc
        return torch, tt, CoxPH

    def _split_training_validation(self, events: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Return deterministic event-stratified train/validation indices.

        About ``validation_fraction`` of each event group is held out: at
        least one subject, but always leaving two in training, so a group of
        two or fewer contributes none. With fewer than 20 subjects, an
        out-of-range fraction, no held-out subject, or fewer than four
        training subjects, every subject trains and the validation set is
        empty.
        """
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

    def _reference_model(self, x_all: np.ndarray, torch: Any, tt: Any, CoxPH: Any) -> Any:
        """Construct the reference network and Adam optimiser after seeds are set."""
        activation_map = {
            "relu": torch.nn.ReLU,
            "selu": torch.nn.SELU,
            "tanh": torch.nn.Tanh,
        }
        if self.activation not in activation_map:
            raise ValueError(
                f"Unsupported activation {self.activation!r}; use one of {sorted(activation_map)}"
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
        return CoxPH(net, optimizer, device="cpu")

    def _early_stopping_data(
        self, x_all: np.ndarray, durations: np.ndarray, events: np.ndarray, tt: Any
    ) -> tuple[np.ndarray, np.ndarray, tuple[np.ndarray, np.ndarray], Any, list[Any]]:
        """Build training inputs and an inner-training validation subset for early stopping.

        Early stopping restores the weights of the best validation epoch. When
        the split is empty, training runs for all ``epochs`` without it.
        """
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

        return train_idx, train_input, train_target, val_data, callbacks

    def fit(self, X: pd.DataFrame, y_time: np.ndarray, y_event: np.ndarray) -> DeepSurvModel:
        """Fit the neural Cox partial likelihood and Breslow baseline.

        The network trains on the training part of the early-stopping split;
        the Breslow baseline is then estimated from all rows passed in.
        Covariates, times and event indicators are converted to float32.

        Args:
            X: Preprocessed covariates of shape (n_subjects, n_features).
            y_time: Strictly positive follow-up times of shape (n_subjects,),
                in the cohort's own unit (days or months).
            y_event: Indicators of shape (n_subjects,), 1 for an observed
                event and 0 for censoring.

        Returns:
            The fitted model. ``training_log`` records completed epochs when
            the reference library supplies a convertible log.

        Raises:
            ImportError: A required reference-model dependency is missing.
            ValueError: Inputs are empty or misaligned, covariates or times
                are non-finite, a time is non-positive, the event-indicator
                sum is below two, or the activation is unsupported.
        """
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

        # Configure PyTorch before the network is built: the seeds fix weight
        # initialisation and mini-batch order, and deterministic kernels on
        # one thread remove run-to-run numerical variation where supported.
        np.random.seed(self.random_state)
        torch.manual_seed(self.random_state)
        torch.use_deterministic_algorithms(True, warn_only=True)
        torch.set_num_threads(1)

        model = self._reference_model(x_all, torch, tt, CoxPH)
        train_idx, train_input, train_target, val_data, callbacks = self._early_stopping_data(
            x_all, durations, events, tt
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
        """Return network output ``g(x)`` on the log partial-hazard scale.

        Scores are not exponentiated or centred, and the network has no
        output bias. Prediction uses evaluation mode with dropout disabled.
        Larger values mean greater hazard.

        Args:
            X: Preprocessed covariates containing every fitted feature column.

        Returns:
            Log partial hazards of shape (n_subjects,).

        Raises:
            RuntimeError: The model has not been fitted.
        """
        self._check_fitted()
        x = X[self.feature_names].to_numpy(dtype="float32", copy=True)
        return np.asarray(self.model.predict(x), dtype=float).reshape(-1)

    def predict_survival(self, X: pd.DataFrame, eval_times: np.ndarray) -> np.ndarray:
        """Return right-continuous Breslow survival estimates at requested times.

        pycox provides survival on the training-time grid. Each requested
        time uses the last grid value not after it: 1 before the grid, and
        the last value beyond it. Results are clipped to ``[1e-8, 1]``.

        Args:
            X: Preprocessed covariates containing every fitted feature column.
            eval_times: Non-empty, non-decreasing times of shape (n_times,),
                in the cohort's own unit. Callers should supply finite times.

        Returns:
            Survival probabilities of shape (n_subjects, n_times).

        Raises:
            RuntimeError: The model has not been fitted.
            ValueError: Times are empty, not one-dimensional or decrease.
        """
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
        """Measure drops in Harrell's concordance index after feature shuffling.

        Each feature is shuffled ``n_repeats`` times with ``random_state``.
        Mean drops are also stored in ``feature_importances_``. Negative
        importance means that shuffling improved the score.

        Args:
            X: Covariates to score, containing every fitted feature column.
            y_time: Matching follow-up times in the cohort's own unit.
            y_event: Matching event indicators (0/1).
            n_repeats: Positive number of shuffles per fitted feature.

        Returns:
            A frame with ``feature``, ``importance_mean`` and
            ``importance_std`` (sample standard deviation for more than one
            shuffle, otherwise zero), sorted by descending mean drop.

        Raises:
            RuntimeError: The model has not been fitted.
            ValueError: The outcomes are invalid for concordance evaluation.
        """
        from src.evaluation.metrics import concordance_index

        baseline, _ = concordance_index(y_time, y_event, self.predict_risk(X))
        rng = np.random.default_rng(self.random_state)
        rows = []
        for feature in self.feature_names:
            drops = []
            for _ in range(n_repeats):
                permuted = X.copy()
                permuted[feature] = rng.permutation(permuted[feature].to_numpy())
                score, _ = concordance_index(y_time, y_event, self.predict_risk(permuted))
                drops.append(baseline - score)
            rows.append(
                {
                    "feature": feature,
                    "importance_mean": float(np.mean(drops)),
                    "importance_std": float(np.std(drops, ddof=1)) if n_repeats > 1 else 0.0,
                }
            )
        self.feature_importances_ = {row["feature"]: row["importance_mean"] for row in rows}
        return (
            pd.DataFrame(rows)
            .sort_values("importance_mean", ascending=False)
            .reset_index(drop=True)
        )

    def get_summary(self) -> pd.DataFrame:
        """Return configuration and currently recorded training counts.

        This method is available before fitting; feature and completed-epoch
        counts then start at zero.

        Returns:
            A data frame with ``component`` and ``value`` columns for the
            architecture, optimiser settings and training counts.
        """
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
        """Raise ``RuntimeError`` if :meth:`fit` has not been called."""
        if self.model is None:
            raise RuntimeError("Model is not fitted. Call fit() first.")
