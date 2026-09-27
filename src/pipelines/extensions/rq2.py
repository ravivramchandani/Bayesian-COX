"""Descriptive catalytic information-regime effects on matched frozen folds."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from src.pipelines.extensions.fitting import CATALYTIC_MODELS
from src.pipelines.robustness.conditions import apply_administrative_censoring
from src.statistics.repeated_cv import nadeau_bengio_paired_effect
from src.utils.reproducibility import canonical_json_hash


def rq2_effects(cells: list[dict[str, Any]], references: list[dict[str, Any]],
               cohorts: dict[str, pd.DataFrame]) -> list[dict[str, Any]]:
    """Report bounded direct and interaction effects with exact paired coverage."""
    lookup = {}
    for cell in cells:
        if cell["dataset"] != "metabric_matched" and cell["fold"] in (1, 2):
            lookup[(cell["dataset"], cell["model_key"], cell["repeat"], cell["fold"], cell["condition"])] = cell
    for cell in references:
        condition = cell["condition"]
        if not any(a["component"] == "rq2" for a in condition["analyses"]):
            continue
        if condition["censoring_quantile"] is not None:
            label = f"admin_q{condition['censoring_quantile']:.2f}"
        elif condition["training_fraction"] == 1:
            label = "full"
        else:
            label = f"fraction_{condition['training_fraction']:.2f}"
        derived = cell
        if cell["status"] == "complete":
            raw = cohorts[cell["dataset"]].set_index("subject_id", verify_integrity=True)
            training = raw.loc[cell["train_subject_ids"]]
            validation = raw.loc[cell["validation_subject_ids"]]
            tt, ee = apply_administrative_censoring(training.duration.to_numpy(float), training.event.to_numpy(int), cell["administrative_cutoff"])
            vt, ve = apply_administrative_censoring(validation.duration.to_numpy(float), validation.event.to_numpy(int), cell["administrative_cutoff"])
            outcome = {"train_time": tt.tolist(), "train_event": ee.tolist(),
                       "validation_time": vt.tolist(), "validation_event": ve.tolist()}
            if canonical_json_hash(outcome) != cell["modified_outcomes_sha256"]:
                raise ValueError("frozen RQ2 training/outcome reconstruction differs")
            derived = {**cell, "predictions": {**cell["predictions"], "training_time": tt.tolist(), "training_event": ee.tolist()}}
        lookup[(cell["dataset"], cell["model_key"], cell["repeat"], cell["fold"], label)] = derived
    rows = []
    conditions = ("fraction_0.25", "fraction_0.50", "fraction_0.75", "admin_q0.75", "admin_q0.50")
    for dataset in ("gbsg2", "whas500", "metabric"):
        for model in CATALYTIC_MODELS:
            for prior in ("bayesian_normal", "bayesian_horseshoe", "bayesian_spike_slab"):
                for condition in conditions:
                    differences: dict[str, list[float]] = defaultdict(list)
                    ratios = []
                    for repeat in range(1, 6):
                        for fold in (1, 2):
                            a = lookup.get((dataset, model, repeat, fold, condition))
                            b = lookup.get((dataset, prior, repeat, fold, condition))
                            af = lookup.get((dataset, model, repeat, fold, "full"))
                            bf = lookup.get((dataset, prior, repeat, fold, "full"))
                            if a is None or b is None or a["status"] != "complete" or b["status"] != "complete":
                                continue
                            for field in ("train_subject_ids", "validation_subject_ids"):
                                if a[field] != b[field]:
                                    raise ValueError(f"RQ2 patients differ at {field}")
                            for field in ("training_time", "training_event", "observed_time", "observed_event", "ibs_grid"):
                                if a["predictions"][field] != b["predictions"][field]:
                                    raise ValueError(f"RQ2 evaluation differs at {field}")
                            value = a["metrics"]["ibs"] - b["metrics"]["ibs"]
                            differences["direct"].append(value)
                            ratios.append(a["n_validation"] / a["n_train"])
                            if af is not None and bf is not None and af["status"] == bf["status"] == "complete":
                                for field in ("train_subject_ids", "validation_subject_ids"):
                                    if af[field] != bf[field] or af["validation_subject_ids"] != a["validation_subject_ids"]:
                                        raise ValueError("RQ2 full anchors do not share planned memberships")
                                for field in ("training_time", "training_event", "observed_time", "observed_event", "ibs_grid"):
                                    if af["predictions"][field] != bf["predictions"][field]:
                                        raise ValueError(f"RQ2 full-anchor evaluation differs at {field}")
                                differences["difference_in_differences"].append(value - (af["metrics"]["ibs"] - bf["metrics"]["ibs"]))
                    for kind in ("direct", "difference_in_differences"):
                        values = differences[kind]
                        row: dict[str, Any] = {"dataset": dataset, "model": model, "prior": prior,
                                                "condition": condition, "kind": kind, "n_pairs": len(values),
                                                "expected_pairs": 10, "role": "descriptive_no_significance_claim",
                                                "mean_difference": float(np.mean(values)) if values else None}
                        if len(values) == 10:
                            effect = nadeau_bengio_paired_effect(np.array(values), np.zeros(10), n_repeats=5, n_folds=2,
                                                                 test_train_ratio=float(np.mean(ratios))).to_dict()
                            effect.pop("p_value")
                            row["corrected_descriptive_interval"] = effect
                        rows.append(row)
    return rows
