"""Independent reconstruction of extension identities, diagnostics and scores."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import arviz as az
import numpy as np
import pandas as pd

from src.models.bayesian.diagnostics import check_convergence
from src.pipelines.confirmatory.evaluation import evaluate_predictions
from src.pipelines.extensions.fitting import BAYESIAN_MODELS
from src.pipelines.extensions.planning import build_extension_jobs
from src.pipelines.extensions.runner import load_extension_cohorts, verified_cell
from src.pipelines.robustness.conditions import apply_administrative_censoring
from src.utils.io import json_safe, read_mapping
from src.utils.reproducibility import canonical_json_hash, sha256_file


class SavedForecast:
    """Read exactly saved grid/horizon forecasts for independent rescoring."""

    def __init__(self, predictions: dict[str, Any]) -> None:
        self.p = predictions

    def predict_risk(self, X: pd.DataFrame) -> np.ndarray:
        """Return saved risk in its verified patient order."""
        return np.array(self.p["risk"], dtype=float)

    def predict_survival(self, X: pd.DataFrame, times: np.ndarray) -> np.ndarray:
        """Reject times not present in saved horizon/grid forecasts."""
        grid, horizon = self.p["ibs_grid"], self.p["horizons"]
        values = {}
        for t, v in zip(grid, np.array(self.p["survival_on_ibs_grid"]).T, strict=True):
            values[t] = v
        for t, v in zip(horizon, np.array(self.p["survival_at_horizons"]).T, strict=True):
            if t in values and not np.array_equal(values[t], v):
                raise ValueError("grid and horizon forecasts disagree at a shared time")
            values[t] = v
        return np.column_stack([values[float(t)] for t in times])


def assert_scientific_equal(left: Any, right: Any, path: str = "", *, tolerance: float = 1e-10) -> None:
    """Compare nested scientific records, rejecting missing fields and altered values."""
    if isinstance(left, dict):
        if not isinstance(right, dict) or set(left) != set(right):
            raise ValueError(f"scientific record fields differ at {path}")
        for key in left:
            assert_scientific_equal(left[key], right[key], f"{path}/{key}", tolerance=tolerance)
    elif isinstance(left, list):
        if not isinstance(right, list) or len(left) != len(right):
            raise ValueError(f"scientific record length differs at {path}")
        for i, (a, b) in enumerate(zip(left, right, strict=True)):
            assert_scientific_equal(a, b, f"{path}/{i}", tolerance=tolerance)
    elif isinstance(left, (float, int)) and not isinstance(left, bool):
        if not isinstance(right, (float, int)) or not np.isclose(left, right, rtol=tolerance, atol=tolerance):
            raise ValueError(f"scientific number differs at {path}: {left} vs {right}")
    elif left != right:
        raise ValueError(f"scientific value differs at {path}")


def verify_trace_diagnostics(expected: dict[str, Any], observed: dict[str, Any], idata: az.InferenceData,
                             label: str, identity: str) -> None:
    """Check sampler metadata against the trace, then compare every diagnostic."""
    if label == "posterior":
        metadata = {"method": "nuts", "n_chains": int(idata.posterior.sizes["chain"]),
                    "n_draws": int(idata.posterior.sizes["draw"])}
        for name, value in metadata.items():
            if expected.get(name) != value:
                raise ValueError(f"sampler metadata differs at {identity}/{name}")
        expected = {key: value for key, value in expected.items() if key not in metadata}
    assert_scientific_equal(expected, observed, f"{identity}/{label}_diagnostics")


def verify_extension_run(root: Path, matched: Path, run: Path, *, deep: bool = True,
                         production_root: Path | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Require the exact grid and independently rescore every accepted cell."""
    production_root = production_root or root
    manifest = read_mapping(run / "manifest.json")
    if canonical_json_hash({k: v for k, v in manifest.items() if k != "manifest_content_sha256"}) != manifest["manifest_content_sha256"]:
        raise ValueError("extension manifest content changed")
    if sha256_file(matched) != manifest["matched_sha256"]:
        raise ValueError("extension matched input changed")
    for name, digest in manifest["input_sha256"].items():
        if sha256_file(production_root / name) != digest:
            raise ValueError(f"extension code/input changed: {name}")
    analysis_only = {"src/pipelines/extensions/verification.py", "scripts/finalize_extensions.py",
                     "scripts/render_extensions.py"}
    analysis_sha256 = {}
    for name, digest in manifest["input_sha256"].items():
        current = sha256_file(root / name)
        if current != digest and name not in analysis_only:
            raise ValueError(f"analysis checkout differs in a production input: {name}")
        if name in analysis_only:
            analysis_sha256[name] = current
    config = read_mapping(root / "config/extensions.yaml")
    if manifest["run_config"] != config:
        raise ValueError("manifest does not use the frozen extension configuration")
    cohorts = load_extension_cohorts(root, matched)
    jobs = build_extension_jobs(cohorts, config)
    planned = {j.cell_id: j for j in jobs}
    actual = {p.stem: p for p in (run / "cells").glob("*.json")}
    if set(actual) != set(planned):
        raise ValueError(f"extension grid differs: {len(actual)} stored, {len(planned)} planned")
    primary = read_mapping(root / "config/confirmatory.yaml")
    cells, rescored, diagnostic_traces = [], 0, 0
    for identity, job in planned.items():
        cell = verified_cell(actual[identity])
        raw = cohorts[job.dataset]
        for field, expected in (("cell_id", identity), ("dataset", job.dataset), ("model_key", job.model),
                                ("repeat", job.repeat), ("fold", job.fold), ("setting", job.setting),
                                ("train_subject_ids", raw.subject_id.iloc[job.train].tolist()),
                                ("validation_subject_ids", raw.subject_id.iloc[job.validation].tolist())):
            if cell[field] != expected:
                raise ValueError(f"extension identity/membership differs at {identity}/{field}")
        if cell["status"] not in {"complete", "failed", "failed_diagnostics"}:
            raise ValueError("unrecognized extension outcome status")
        if job.model in BAYESIAN_MODELS and cell["status"] in {"complete", "failed_diagnostics"}:
            for recorded in cell.get("fit_attempts", []):
                required = {"posterior", "prior"} if job.model.startswith("catalytic_") else {"posterior"}
                if set(recorded.get("traces", {})) != required:
                    raise ValueError("Bayesian attempted fit lacks required actual traces")
                if job.model.startswith("catalytic_") and not recorded.get("prior_diagnostics"):
                    raise ValueError("catalytic fit lacks actual joint-prior diagnostics")
        if deep:
            for attempt in cell.get("fit_attempts", []):
                for label, trace in attempt.get("traces", {}).items():
                    idata = az.from_netcdf(str(run / "traces" / identity / trace["filename"]))
                    try:
                        observed = json_safe(check_convergence(idata))
                        expected = attempt["diagnostics" if label == "posterior" else "prior_diagnostics"]
                        verify_trace_diagnostics(expected, observed, idata, label, identity)
                    finally:
                        idata.close()
                    diagnostic_traces += 1
        if cell["status"] == "complete":
            if job.model in BAYESIAN_MODELS:
                attempt = cell["fit_attempts"][-1]
                for recorded in cell["fit_attempts"]:
                    required_traces = {"posterior", "prior"} if job.model.startswith("catalytic_") else {"posterior"}
                    if set(recorded.get("traces", {})) != required_traces:
                        raise ValueError("accepted Bayesian cell lacks its actual required traces")
                if not attempt["diagnostics"]["converged"] or (attempt["prior_diagnostics"] and not attempt["prior_diagnostics"]["converged"]):
                    raise ValueError("accepted extension fit fails a posterior/prior diagnostic gate")
            tt, ee = apply_administrative_censoring(raw.duration.iloc[job.train].to_numpy(float), raw.event.iloc[job.train].to_numpy(int), job.censoring_cutoff)
            vt, ve = apply_administrative_censoring(raw.duration.iloc[job.validation].to_numpy(float), raw.event.iloc[job.validation].to_numpy(int), job.censoring_cutoff)
            p = cell["predictions"]
            if p["subject_ids"] != cell["validation_subject_ids"]:
                raise ValueError("forecast patient order differs from the planned validation order")
            for name, expected in (("training_time", tt), ("training_event", ee), ("observed_time", vt), ("observed_event", ve)):
                if not np.array_equal(p[name], expected):
                    raise ValueError(f"stored extension outcome differs: {identity}/{name}")
            if deep:
                metrics, _ = evaluate_predictions(SavedForecast(p), pd.DataFrame(index=range(len(vt))), tt, ee, vt, ve,
                    evaluation_config=primary["evaluation"], calibration_bootstraps=config["calibration_bootstraps"], seed=cell["seed"])
                assert_scientific_equal(cell["metrics"], json_safe(metrics), f"{identity}/metrics")
                rescored += 1
        cells.append(cell)
    return cells, {"planned": len(jobs), "stored": len(cells), "status_counts": dict(Counter(c["status"] for c in cells)),
                    "independently_rescored": rescored, "independently_checked_traces": diagnostic_traces,
                    "verification": "deep" if deep else "hash_membership_gate_only",
                    "production_code_commit": manifest["code"]["git_commit"],
                    "analysis_only_sha256": analysis_sha256}
