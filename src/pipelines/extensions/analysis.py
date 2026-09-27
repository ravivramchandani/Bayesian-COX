"""Bounded paired effects and dependency-aware curves from verified forecasts."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd

from src.pipelines.confirmatory.options import deterministic_seed
from src.pipelines.extensions.decision_curves import (
    decision_contributions,
    ipcw_state_weights,
    patient_cluster_intervals,
)
from src.pipelines.extensions.fitting import CATALYTIC_MODELS, NEW_MODELS
from src.statistics.hypothesis_tests import holm_adjust
from src.statistics.repeated_cv import nadeau_bengio_paired_effect


def paired_effect(left: list[dict[str, Any]], right: list[dict[str, Any]], *, folds: int = 5) -> dict[str, Any]:
    """Compare complete aligned fold pairs, retaining incomplete coverage."""
    lookup = {(c["repeat"], c["fold"]): c for c in right if c["status"] == "complete"}
    pairs = [(c, lookup[(c["repeat"], c["fold"])]) for c in left
             if c["status"] == "complete" and (c["repeat"], c["fold"]) in lookup]
    for a, b in pairs:
        for key in ("subject_ids", "observed_time", "observed_event", "ibs_grid", "training_time", "training_event"):
            if a["predictions"][key] != b["predictions"][key]:
                raise ValueError(f"paired forecasts disagree at {key}")
        if a["train_subject_ids"] != b["train_subject_ids"]:
            raise ValueError("paired fits do not contain identical training patients")
    row: dict[str, Any] = {"n_pairs": len(pairs), "expected_pairs": 5 * folds,
                           "direction": "left IBS minus right IBS"}
    if len(pairs) != 5 * folds:
        row["status"] = "incomplete_no_inference"
        return row
    result = nadeau_bengio_paired_effect(
        np.array([a["metrics"]["ibs"] for a, _ in pairs]),
        np.array([b["metrics"]["ibs"] for _, b in pairs]), n_repeats=5, n_folds=folds,
        test_train_ratio=1 / 4,
    ).to_dict()
    return {**row, "status": "estimable", "effect": result}


def extension_families(cells: list[dict[str, Any]], references: list[dict[str, Any]]) -> dict[str, Any]:
    """Build exactly four separate, complete-or-unavailable post-hoc Holm families."""
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for c in cells:
        if c["condition"] == "full":
            groups[(c["dataset"], c["setting"], c["model_key"])].append(c)
    originals: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for c in references:
        originals[(c["dataset"], c["model_key"])].append(c)
    families: dict[str, list[dict[str, Any]]] = {
        "penalized_vs_original_priors": [], "calibrated_vs_adr032_horseshoe": [],
        "catalytic_vs_original_priors": [], "expression_increment": [],
    }
    inherited = ("bayesian_normal", "bayesian_horseshoe", "bayesian_spike_slab")
    for dataset in ("gbsg2", "whas500", "metabric"):
        for family, models in (("penalized_vs_original_priors", ("ridge", "lasso", "elastic_net")),
                               ("catalytic_vs_original_priors", CATALYTIC_MODELS)):
            for model in models:
                for prior in inherited:
                    families[family].append({"dataset": dataset, "left": model, "right": prior,
                                             "horseshoe_reference": "ADR-032 post-hoc sampler" if prior == "bayesian_horseshoe" else None,
                                             **paired_effect(groups[(dataset, "clinical", model)], originals[(dataset, prior)])})
        families["calibrated_vs_adr032_horseshoe"].append({"dataset": dataset, "left": "pv_horseshoe", "right": "ADR032_horseshoe",
            **paired_effect(groups[(dataset, "clinical", "pv_horseshoe")], originals[(dataset, "bayesian_horseshoe")])})
    for model in ("cox_ph", "random_survival_forest", "deepsurv") + inherited + NEW_MODELS:
        families["expression_increment"].append({"dataset": "metabric_matched", "model": model,
            "left": "expression", "right": "clinical",
            **paired_effect(groups[("metabric_matched", "expression", model)], groups[("metabric_matched", "clinical", model)])})
    output = {}
    expected = {"penalized_vs_original_priors": 27, "calibrated_vs_adr032_horseshoe": 3,
                "catalytic_vs_original_priors": 27, "expression_increment": 13}
    for name, rows in families.items():
        complete = len(rows) == expected[name] and all(r["status"] == "estimable" for r in rows)
        if complete:
            adjusted, rejected = holm_adjust([r["effect"]["p_value"] for r in rows])
            for row, p, reject in zip(rows, adjusted, rejected, strict=True):
                effect = row["effect"]
                row.update({"holm_adjusted_p": p, "holm_reject": reject,
                            "superiority_language_permitted": bool(reject and
                             (effect["confidence_upper"] < 0 or effect["confidence_lower"] > 0))})
        output[name] = {"family_complete": complete, "expected_contrasts": expected[name], "contrasts": rows}
    return output


def curves_from_cells(
    cells: list[dict[str, Any]], config: dict[str, Any], known_pairs: pd.DataFrame,
) -> dict[str, Any]:
    """Assemble common complete patient/repeat curves without model refitting."""
    dc = config["decision_curves"]
    thresholds = np.array(dc["thresholds"])
    grouped: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for cell in cells:
        if cell.get("condition", "full") == "full":
            grouped[(cell["dataset"], cell.get("setting", "clinical"))][cell["model_key"]].append(cell)
    alias = {}
    for a, b in zip(known_pairs.accession_a, known_pairs.accession_b, strict=True):
        alias[a] = alias[b] = min(a, b)
    output = {}
    for (dataset, setting), model_cells in grouped.items():
        model_cells = {k: sorted(v, key=lambda c: (c["repeat"], c["fold"])) for k, v in model_cells.items()}
        for hindex in range(3):
            unavailable, utilities, default_values, patient_ids = {}, {}, None, None
            support_records = {}
            common_identity = None
            for model, records in model_cells.items():
                if len(records) != 25 or any(c["status"] != "complete" for c in records):
                    unavailable[model] = "not all 25 planned folds have accepted predictions"
                    continue
                try:
                    by_patient: dict[str, dict[int, tuple[np.ndarray, np.ndarray]]] = defaultdict(dict)
                    supports = []
                    identities = []
                    for cell in records:
                        p = cell["predictions"]
                        horizon = float(p["horizons"][hindex])
                        identities.append((cell["repeat"], cell["fold"], horizon, cell["train_subject_ids"],
                                           p["subject_ids"], p["training_time"], p["training_event"],
                                           p["observed_time"], p["observed_event"]))
                        u, v, support = ipcw_state_weights(
                            np.array(p["training_time"]), np.array(p["training_event"]),
                            np.array(p["observed_time"]), np.array(p["observed_event"]), horizon,
                            minimum_g=dc["minimum_G"], minimum_at_risk=dc["minimum_training_at_risk"],
                        )
                        utility, defaults = decision_contributions(1 - np.array(p["survival_at_horizons"])[:, hindex], u, v, thresholds)
                        supports.append({"repeat": cell["repeat"], "fold": cell["fold"], **support})
                        for i, pid in enumerate(p["subject_ids"]):
                            if cell["repeat"] in by_patient[pid]:
                                raise ValueError("patient appears twice in one validation repeat")
                            by_patient[pid][cell["repeat"]] = utility[i], defaults[i]
                    ids = sorted(by_patient)
                    if any(set(by_patient[pid]) != set(range(1, 6)) for pid in ids):
                        raise ValueError("patient does not have all five validation repeats")
                    values = np.array([[by_patient[pid][r][0] for r in range(1, 6)] for pid in ids])
                    defaults = np.array([[by_patient[pid][r][1] for r in range(1, 6)] for pid in ids])
                    if patient_ids is not None and (ids != patient_ids or not np.array_equal(default_values, defaults)):
                        raise ValueError("decision models do not share identical patients/horizons/weights")
                    if common_identity is not None and common_identity != identities:
                        raise ValueError("decision fold horizons/training identities differ across models")
                    common_identity = identities
                    patient_ids, default_values = ids, defaults
                    utilities[model], support_records[model] = values, supports
                except (ValueError, IndexError) as exc:
                    unavailable[model] = str(exc)
            key = f"{dataset}__{setting}__h{hindex + 1}"
            result: dict[str, Any] = {"thresholds": thresholds.tolist(), "unavailable": unavailable,
                                      "horizon_rule": dc["horizon_event_quantiles"][hindex], "support": support_records}
            if utilities:
                utilities["all"], utilities["none"] = default_values, np.zeros_like(default_values)
                result["curves"] = patient_cluster_intervals(utilities, n_bootstraps=dc["bootstrap_replicates"],
                    seed=deterministic_seed(config["base_seed"], "decision_curves", key),
                    cluster_ids=[alias.get(pid, pid) for pid in patient_ids])
            output[key] = result
    return output
