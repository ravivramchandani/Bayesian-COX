"""Nested training-only comparator selection and recorded Bayesian attempts."""

from __future__ import annotations

import time
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning

from src.data.survival_folds import repeated_survival_folds
from src.evaluation.metrics import integrated_brier
from src.models.bayesian.extensions import CompactBayesianCox, ExtensionBayesianCox
from src.models.catalytic import CatalyticData, WeightedMixtureCox
from src.models.penalized_cox import PenalizedCox
from src.pipelines.confirmatory.evaluation import (
    administratively_truncate_for_ipcw,
    evaluation_horizons_and_grid,
    validate_survival_prediction_matrix,
)
from src.pipelines.confirmatory.fitting import _model_candidates, _model_from_parameters
from src.pipelines.confirmatory.options import DiagnosticFailure, deterministic_seed
from src.pipelines.extensions.preprocessing import ExtensionPreprocessor, generate_catalytic_data
from src.utils.reproducibility import sha256_file

NEW_MODELS = ("ridge", "lasso", "elastic_net", "pv_horseshoe", "catalytic_fixed",
              "catalytic_adaptive", "catalytic_wme")
CATALYTIC_MODELS = ("catalytic_fixed", "catalytic_adaptive", "catalytic_wme")
BAYESIAN_MODELS = ("bayesian_normal", "bayesian_horseshoe", "bayesian_spike_slab",
                   "pv_horseshoe", "catalytic_fixed", "catalytic_adaptive")


def candidates_for(key: str, config: dict[str, Any], primary: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the frozen candidate ordering, without outer-test selection."""
    if key in {"ridge", "lasso", "elastic_net"}:
        return [{"penalty": v} for v in config["penalties"]]
    if key == "catalytic_wme":
        return [{"tau_multiplier": v} for v in config["catalytic"]["wme_tau_multipliers"]]
    if key in NEW_MODELS:
        return [{}]
    return _model_candidates(key, primary)


def make_model(
    key: str, parameters: dict[str, Any], synthetic: CatalyticData | None,
    train_time: np.ndarray, train_event: np.ndarray,
    *, primary: dict[str, Any], config: dict[str, Any], seed: int, attempt: int = 0,
) -> Any:
    """Construct one model from the frozen sampling and training prior rules."""
    if key in {"ridge", "lasso", "elastic_net"}:
        return PenalizedCox(key, parameters["penalty"])
    if key == "catalytic_wme":
        if synthetic is None:
            raise ValueError("missing mixture prior data")
        return WeightedMixtureCox(synthetic, synthetic.design.shape[1] * parameters["tau_multiplier"],
                                  time_scale=float(np.median(train_time[train_event == 1])))
    sampler = config["sampling"]
    tune = sampler["tune"] * (2 if attempt else 1)
    if key in {"pv_horseshoe", "catalytic_fixed", "catalytic_adaptive"}:
        return ExtensionBayesianCox(
            key, synthetic=synthetic, draws=sampler["draws"], tune=tune,
            chains=sampler["chains"], cores=1, target_accept=sampler["target_accept"],
            random_state=seed, n_intervals=6, noncentered_baseline=attempt >= 2,
        )
    if key.startswith("bayesian_"):
        prior = key.removeprefix("bayesian_")
        return CompactBayesianCox(
            coefficient_prior=prior,
            prior_params=primary["models"]["bayesian_cox"]["priors"][prior]["prior_params"],
            draws=sampler["draws"], tune=tune, chains=sampler["chains"], cores=1,
            n_intervals=6, target_accept=sampler["target_accept"], random_state=seed,
            noncentered_baseline=attempt >= 2,
        )
    return _model_from_parameters(
        key, parameters, seed=seed, confirmatory_config=primary,
        bayes_draws=sampler["draws"], bayes_tune=tune, bayes_chains=sampler["chains"],
        target_accept_override=sampler["target_accept"] if key in BAYESIAN_MODELS else None,
        noncentered_baseline=attempt >= 2,
    )


def select_parameters(
    key: str, raw: pd.DataFrame, times: np.ndarray, events: np.ndarray,
    feature_spec: dict[str, Any], gene_budget: int,
    *, primary: dict[str, Any], config: dict[str, Any], seed: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Select mean IPCW IBS on three inner folds with every transform refitted."""
    candidates = candidates_for(key, config, primary)
    if len(candidates) == 1:
        return candidates[0], {"tuned": False, "candidates": []}
    folds = repeated_survival_folds(times, events, n_splits=3, n_repeats=1,
                                   base_seed=seed, max_time_bins=4)
    rows = [{"parameters": c, "scores": [], "failures": []} for c in candidates]
    for fold in folds:
        tr, va = fold.train_indices, fold.validation_indices
        processor = ExtensionPreprocessor(feature_spec, gene_budget).fit(raw.iloc[tr])
        xt, xv = processor.transform(raw.iloc[tr]), processor.transform(raw.iloc[va])
        synthetic = None
        if key == "catalytic_wme":
            synthetic, _ = generate_catalytic_data(raw.iloc[tr], processor, times[tr], events[tr],
                                                  deterministic_seed(seed, "inner_prior", fold.fold))
        for ci, row in enumerate(rows):
            try:
                model = make_model(key, row["parameters"], synthetic, times[tr], events[tr],
                                   primary=primary, config=config,
                                   seed=deterministic_seed(seed, "inner_fit", fold.fold, ci))
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always")
                    model.fit(xt, times[tr], events[tr])
                convergence = [str(w.message) for w in caught if issubclass(w.category, ConvergenceWarning)
                               or "converg" in w.category.__name__.lower()]
                if convergence:
                    raise RuntimeError("; ".join(convergence))
                _, grid = evaluation_horizons_and_grid(times[tr], events[tr], primary["evaluation"])
                survival = model.predict_survival(xv, grid)
                validate_survival_prediction_matrix(survival, n_samples=len(va), n_times=len(grid))
                tv, ev = administratively_truncate_for_ipcw(times[va], events[va], float(grid[-1]))
                score = integrated_brier(times[tr], events[tr], tv, ev, survival, grid)
                row["scores"].append(float(score))
            except Exception as exc:
                row["failures"].append({"fold": fold.fold, "type": type(exc).__name__, "message": str(exc)})
    for row in rows:
        row["mean_ibs"] = float(np.mean(row["scores"])) if len(row["scores"]) == 3 else None
    eligible = [i for i, row in enumerate(rows) if row["mean_ibs"] is not None]
    if not eligible:
        raise RuntimeError(f"no {key} candidate passed all inner folds")
    selected = min(eligible, key=lambda i: (rows[i]["mean_ibs"], i))
    return candidates[selected], {"tuned": True, "selected_index": selected, "candidates": rows,
                                  "selection": "three-inner-fold mean IPCW IBS; stable candidate-order ties"}


class FitExecutionFailure(RuntimeError):
    """A fit/write failure carrying every earlier and current attempt record."""

    def __init__(self, message: str, attempts: list[dict[str, Any]]) -> None:
        """Keep the error message and the records of every fit attempt made so far."""
        super().__init__(message)
        self.attempts = attempts


def fit_with_attempts(
    key: str, parameters: dict[str, Any], x: pd.DataFrame, times: np.ndarray, events: np.ndarray,
    synthetic: CatalyticData | None, *, primary: dict[str, Any], config: dict[str, Any], seed: int,
    trace_dir: Path | None = None,
) -> tuple[Any, list[dict[str, Any]]]:
    """Retain diagnostics and available traces even when a later attempt crashes."""
    attempts: list[dict[str, Any]] = []
    maximum = 3 if key in BAYESIAN_MODELS else 1
    for attempt in range(maximum):
        row: dict[str, Any] = {"attempt": attempt + 1, "warnings": []}
        model = make_model(key, parameters, synthetic, times, events, primary=primary, config=config,
                           seed=deterministic_seed(seed, "fit_attempt", attempt), attempt=attempt)
        started = time.perf_counter()
        error: Exception | None = None
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                model.fit(x, times, events)
            except Exception as exc:
                error = exc
        row.update({"seconds": time.perf_counter() - started, "warnings": [str(w.message) for w in caught]})
        convergence = [str(w.message) for w in caught if issubclass(w.category, ConvergenceWarning)
                       or "converg" in w.category.__name__.lower()]
        if key in BAYESIAN_MODELS:
            row.update({"diagnostics": model.diagnostics,
                        "prior_diagnostics": getattr(model, "prior_diagnostics", {}),
                        "target_accept": model.target_accept, "tune": model.tune,
                        "noncentered_baseline": model.noncentered_baseline})
            if trace_dir is not None:
                trace_dir.mkdir(parents=True, exist_ok=True)
                traces = {label: idata for label, idata in
                          (("posterior", getattr(model, "idata", None)),
                           ("prior", getattr(model, "prior_idata", None))) if idata is not None}
                row["traces"] = {}
                for label, idata in traces.items():
                    path = trace_dir / f"attempt_{attempt + 1}_{label}.nc"
                    try:
                        if path.exists():
                            raise FileExistsError(path)
                        idata.to_netcdf(str(path), compress=True)
                        row["traces"][label] = {"filename": path.name, "sha256": sha256_file(path)}
                    except Exception as exc:
                        row.setdefault("trace_write_errors", []).append({"label": label, "message": str(exc)})
                        error = exc
            prior_ok = not row["prior_diagnostics"] or row["prior_diagnostics"].get("converged", False)
            valid = bool(model.diagnostics.get("converged", False) and prior_ok)
        else:
            row["optimizer"] = getattr(model, "details", {})
            if convergence:
                error = RuntimeError("; ".join(convergence))
            valid = error is None
        if error is not None:
            row.update({"error_type": type(error).__name__, "message": str(error)})
        attempts.append(row)
        if error is not None:
            raise FitExecutionFailure(str(error), attempts) from error
        if valid:
            return model, attempts
    raise DiagnosticFailure(attempts)
