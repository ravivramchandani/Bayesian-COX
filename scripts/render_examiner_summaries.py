"""Summarise archived fits and checks without fitting models or drawing samples."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
import tarfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from src.rendering.verification import (  # noqa: E402
    FrozenRun,
    canonical_json_hash,
    sha256_file,
    verify_explainability_artifact,
    verify_frozen_run,
)

RUN_NAME = "confirmatory_v1_confirmatory_cdcdcee84651"
COHORTS = {"gbsg2": "GBSG2", "whas500": "WHAS500", "metabric": "METABRIC"}
PRIORS = {"bayesian_normal": "N", "bayesian_horseshoe": "H", "bayesian_spike_slab": "S"}
MATCHED_COUNTS = {"gbsg2": 7, "whas500": 25, "metabric": 23}
SELECTED = {
    "gbsg2": ("age", "pnodes"),
    "whas500": ("age", "hr"),
    "metabric": ("age_at_diagnosis", "nottingham_prognostic_index"),
}
FEATURE_NAMES = {
    "age": "Age",
    "pnodes": "Positive nodes",
    "hr": "Heart rate",
    "age_at_diagnosis": "Age",
    "nottingham_prognostic_index": "NPI",
}
ARCHIVES = {
    "programme-confirmatory-reports.tar.gz": "008f31e2b6d5c33930a79156a850a31afc574f53909d8a1d67c4f1d93662ce15",
    "programme-robustness.tar.gz": "05918c159acf84367cdcbb8d9fdd5cf8a6ceeb1bf6d72fb56d9a4ab09f7ea7e4",
}
EXPLANATION_SHA = "120984c7edfac468f471b9f500470623689b2647e4bde56d271cc9623346ecd5"
ROBUSTNESS_SHAS = {
    "completion.json": "8f136a6b2f9cf0a18308db71d63a69b1b145b0c767548cc7465d4af73e781152",
    "manifest.json": "0fc556b803da4f37daa9a63dbddc5ce5ffd350aa2b2831b0a6546b634c36139f",
}


def _seal(record: dict[str, Any], field: str) -> None:
    if record.get(field) != canonical_json_hash({k: v for k, v in record.items() if k != field}):
        raise ValueError(f"Invalid stored {field}")


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("")
        return
    with path.open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _mean(values: list[float]) -> float:
    if not values or any(not math.isfinite(x) for x in values):
        raise ValueError("Non-finite or empty numerical summary")
    return statistics.mean(values)


def _coding(cell: dict[str, Any], feature: str) -> tuple[str, str, str, str]:
    preprocessing = cell["preprocessing"]
    source = preprocessing["feature_groups"][feature]
    if source in preprocessing.get("category_levels", {}):
        levels = preprocessing["category_levels"][source]
        if "=" not in feature or feature.split("=", 1)[0] != source:
            raise ValueError(f"Unrecognised categorical encoding: {feature}")
        return (
            source,
            "binary contrast",
            str(levels[0]),
            json.dumps({"level": feature.split("=", 1)[1], "reference": levels[0]}, sort_keys=True),
        )
    if source in preprocessing.get("ordinal_maps", {}):
        encoding = json.dumps(preprocessing["ordinal_maps"][source], sort_keys=True)
        return source, "one fold-specific training SD of ordinal score", "", encoding
    if feature not in preprocessing["scaling"]:
        raise ValueError(f"Missing numerical scale: {feature}")
    return source, "one fold-specific training SD", "", "numeric"


def _posterior_rows(
    cells: list[tuple[str, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    indexed = {
        (c["dataset"], c["model_key"], c["repeat"], c["fold"]): (p, c)
        for p, c in cells
        if c["status"] == "complete" and c["model_key"] in PRIORS
    }
    if len(indexed) != sum(
        c["status"] == "complete" and c["model_key"] in PRIORS for _, c in cells
    ):
        raise ValueError("Duplicate posterior cell identity")
    rows, per_fold, excluded, selections = [], [], [], {}
    for dataset in COHORTS:
        available = [
            {(r, f) for d, m, r, f in indexed if d == dataset and m == model} for model in PRIORS
        ]
        matched = sorted(set.intersection(*available))
        if len(matched) != MATCHED_COUNTS[dataset]:
            raise ValueError(f"Changed matched posterior coverage: {dataset}")
        selections[dataset] = [list(x) for x in matched]
        groups = []
        for repeat, fold in matched:
            triplet = [indexed[dataset, model, repeat, fold] for model in PRIORS]
            if len({canonical_json_hash(c["preprocessing"]) for _, c in triplet}) != 1:
                raise ValueError(f"Unmatched preprocessing: {dataset}/{repeat}/{fold}")
            if len({tuple(c["train_subject_ids"]) for _, c in triplet}) != 1:
                raise ValueError("Unmatched posterior training subjects")
            if len({tuple(c["validation_subject_ids"]) for _, c in triplet}) != 1:
                raise ValueError("Unmatched posterior validation subjects")
            groups.append(triplet)
        all_features = sorted(
            set.union(
                *(set(c["preprocessing"]["feature_names"]) for group in groups for _, c in group)
            )
        )
        for feature in all_features:
            codings = set()
            present = all(
                feature in c["preprocessing"]["feature_names"] for group in groups for _, c in group
            )
            if present:
                codings = {_coding(c, feature) for group in groups for _, c in group}
            if not present or len(codings) != 1:
                excluded.append(
                    {
                        "dataset": dataset,
                        "feature": feature,
                        "reason": "not present in every matched fit"
                        if not present
                        else "coding or reference differs across folds",
                    }
                )
                continue
            source, unit, reference, encoding = next(iter(codings))
            for model in PRIORS:
                values = []
                for (repeat, fold), group in zip(matched, groups, strict=True):
                    path, cell = indexed[dataset, model, repeat, fold]
                    record = next(
                        x
                        for x in cell["model_details"]["coefficient_summary"]
                        if x["feature"] == feature
                    )
                    normal = next(
                        x
                        for x in group[0][1]["model_details"]["coefficient_summary"]
                        if x["feature"] == feature
                    )
                    lower, upper = (
                        float(record["95% Credible Lower"]),
                        float(record["95% Credible Upper"]),
                    )
                    if not 0 <= lower <= upper or not math.isfinite(upper):
                        raise ValueError("Invalid archived HR credible limits")
                    probability = float(record["Prob(HR > 1)"])
                    if not 0 <= probability <= 1:
                        raise ValueError("Invalid archived directional probability")
                    signal = cell["model_details"].get("inclusion_signal") or []
                    weights = [
                        x["continuous_inclusion_weight"]
                        for x in signal
                        if x["feature"] == feature and "continuous_inclusion_weight" in x
                    ]
                    weight = float(weights[0]) if weights else None
                    if model == "bayesian_spike_slab" and (weight is None or not 0 <= weight <= 1):
                        raise ValueError("Missing continuous-mixture variance weight")
                    value = {
                        "dataset": dataset,
                        "model_key": model,
                        "repeat": repeat,
                        "fold": fold,
                        "feature": feature,
                        "source_feature": source,
                        "unit": unit,
                        "reference": reference,
                        "encoding": encoding,
                        "beta_mean": float(record["coef (beta_mean)"]),
                        "hr_lower_95": lower,
                        "hr_upper_95": upper,
                        "hr_interval_width": upper - lower,
                        "hr_interval_excludes_one": int(upper < 1 or lower > 1),
                        "prob_beta_positive": probability,
                        "absolute_beta_difference_from_normal": abs(
                            float(record["coef (beta_mean)"]) - float(normal["coef (beta_mean)"])
                        ),
                        "continuous_mixture_variance_weight": weight,
                        "training_scale": cell["preprocessing"]["scaling"]
                        .get(feature, {})
                        .get("scale"),
                        "preprocessing_sha256": cell["preprocessing"]["training_state_sha256"],
                        "source_cell": path,
                        "cell_content_sha256": cell["cell_content_sha256"],
                    }
                    values.append(value)
                    per_fold.append(value)
                rows.append(
                    {
                        "dataset": dataset,
                        "model_key": model,
                        "feature": feature,
                        "source_feature": source,
                        "unit": unit,
                        "reference": reference,
                        "encoding": encoding,
                        "n_matched_folds": len(values),
                        "mean_beta": _mean([v["beta_mean"] for v in values]),
                        "mean_hr_interval_width": _mean([v["hr_interval_width"] for v in values]),
                        "n_hr_intervals_excluding_one": sum(
                            v["hr_interval_excludes_one"] for v in values
                        ),
                        "fraction_hr_intervals_excluding_one": _mean(
                            [v["hr_interval_excludes_one"] for v in values]
                        ),
                        "mean_probability_beta_positive": _mean(
                            [v["prob_beta_positive"] for v in values]
                        ),
                        "mean_absolute_beta_difference_from_normal": _mean(
                            [v["absolute_beta_difference_from_normal"] for v in values]
                        ),
                        "mean_continuous_mixture_variance_weight": _mean(
                            [v["continuous_mixture_variance_weight"] for v in values]
                        )
                        if model == "bayesian_spike_slab"
                        else None,
                    }
                )
    return rows, per_fold, excluded, selections


def _prior_rows(
    cells: list[tuple[str, dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw = []
    for path, cell in cells:
        if cell["status"] != "complete" or cell["model_key"] not in PRIORS:
            continue
        prior = cell["model_details"]["prior_predictive"]
        for kind, field in (
            ("baseline", "baseline_survival"),
            ("covariate_population", "covariate_population_survival"),
        ):
            for value in prior[field]:
                population = kind == "covariate_population"
                raw.append(
                    {
                        "dataset": cell["dataset"],
                        "model_key": cell["model_key"],
                        "repeat": cell["repeat"],
                        "fold": cell["fold"],
                        "check": kind,
                        "scaled_time": value["scaled_time"],
                        "time": value["time"],
                        "time_scale": prior["time_scale"],
                        "n_draws": prior["n_draws"],
                        "n_covariate_rows": prior.get("n_covariate_rows") if population else None,
                        "median_survival": value[
                            "subject_draw_median_survival" if population else "median_survival"
                        ],
                        "lower_95": value["subject_draw_lower_95" if population else "lower_95"],
                        "upper_95": value["subject_draw_upper_95" if population else "upper_95"],
                        "mass_survival_below_0_01": value.get(
                            "proportion_subject_draws_below_0_01"
                        ),
                        "mass_survival_above_0_99": value.get(
                            "proportion_subject_draws_above_0_99"
                        ),
                        "source_cell": path,
                    }
                )
    if len(raw) != 1640:
        raise ValueError("Changed saved prior predictive coverage")
    grouped = defaultdict(list)
    for row in raw:
        if not math.isclose(row["time"], row["scaled_time"] * row["time_scale"], rel_tol=1e-12):
            raise ValueError("Unmatched prior predictive time scale")
        grouped[row["dataset"], row["model_key"], row["check"], row["scaled_time"]].append(row)
    summary = []
    for (dataset, model, kind, scaled_time), values in sorted(grouped.items()):
        result = {
            "dataset": dataset,
            "model_key": model,
            "check": kind,
            "scaled_time": scaled_time,
            "n_fits": len(values),
            "mean_foldwise_median_survival": _mean([v["median_survival"] for v in values]),
            "mean_foldwise_lower_95": _mean([v["lower_95"] for v in values]),
            "mean_foldwise_upper_95": _mean([v["upper_95"] for v in values]),
            "mean_mass_survival_below_0_01": None,
            "mean_mass_survival_above_0_99": None,
        }
        if kind == "covariate_population":
            for name in ("mass_survival_below_0_01", "mass_survival_above_0_99"):
                result[f"mean_{name}"] = _mean([v[name] for v in values])
        summary.append(result)
    return summary, raw


def _compact_cell(path: str, cell: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": path,
        "dataset": cell["dataset"],
        "model_key": cell["model_key"],
        "repeat": cell["repeat"],
        "fold": cell["fold"],
        "status": cell["status"],
        "condition": cell.get("condition", {}),
        "metrics": cell.get("metrics", {}),
        "validation_subject_ids": cell.get("validation_subject_ids", []),
        "fit_attempts": cell.get("fit_attempts", []),
        "cell_content_sha256": cell["cell_content_sha256"],
    }


def _release_inputs(
    assets: Path, run: FrozenRun
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    for name, expected in ARCHIVES.items():
        if sha256_file(assets / name) != expected:
            raise ValueError(f"Frozen release archive differs: {name}")
    xai_path = assets / "archived_explainability.json"
    with tarfile.open(assets / "programme-confirmatory-reports.tar.gz", "r|gz") as archive:
        member = archive.next()
        assert member is not None
        if member.name != f"explanation/{RUN_NAME}_explainability_v1.json":
            raise ValueError("Unexpected first explanation archive member")
        stream = archive.extractfile(member)
        assert stream is not None
        content = stream.read()
        if hashlib.sha256(content).hexdigest() != EXPLANATION_SHA:
            raise ValueError("Frozen explanation file differs")
        xai_path.write_bytes(content)
    xai, xai_source = verify_explainability_artifact(xai_path, run)
    records, byte_hashes, metadata, aggregates = [], {}, {}, {}
    with tarfile.open(assets / "programme-robustness.tar.gz", "r|gz") as archive:
        for member in archive:
            if not member.isfile():
                continue
            if not member.name.startswith("robustness/"):
                raise ValueError("Unexpected robustness archive member")
            relative = member.name.removeprefix("robustness/")
            stream = archive.extractfile(member)
            assert stream is not None
            content = stream.read()
            digest = hashlib.sha256(content).hexdigest()
            value = json.loads(content)
            if relative.startswith("cells/"):
                _seal(value, "cell_content_sha256")
                if relative in byte_hashes or value.get("analysis_mode") != "robustness":
                    raise ValueError("Duplicate or wrongly labelled robustness cell")
                byte_hashes[relative] = digest
                records.append(_compact_cell(relative, value))
            elif relative in ROBUSTNESS_SHAS:
                if digest != ROBUSTNESS_SHAS[relative]:
                    raise ValueError("Changed frozen robustness metadata")
                _seal(value, relative.removesuffix(".json") + "_content_sha256")
                metadata[relative] = value
            else:
                aggregates[relative] = (digest, value)
    completion, manifest = metadata["completion.json"], metadata["manifest.json"]
    if byte_hashes != completion["cell_sha256"] or len(records) != 825:
        raise ValueError("Robustness cell inventory differs")
    if dict(Counter(c["status"] for c in records)) != completion["status_counts"]:
        raise ValueError("Robustness status counts differ")
    if completion["status_counts"] != {"complete": 770, "failed_diagnostics": 55}:
        raise ValueError("Changed robustness outcome coverage")
    if completion["stored_cells"] != 825 or completion["planned_cells_in_this_invocation"] != 825:
        raise ValueError("Robustness completion count differs")
    if canonical_json_hash(manifest["run_config"]) != manifest["config_sha256"]:
        raise ValueError("Robustness configuration seal differs")
    if (
        manifest["run_config"]["mode"] != "robustness"
        or manifest["run_config"]["confirmatory_run"] != RUN_NAME
    ):
        raise ValueError("Robustness source run differs")
    for name in ("manifest.json", "completion.json"):
        links = [
            v for k, v in manifest["input_sha256"].items() if k.endswith(f"/{RUN_NAME}/{name}")
        ]
        if links != [sha256_file(run.run_dir / name)]:
            raise ValueError("Robustness confirmatory lineage differs")
    if set(aggregates) != set(completion["aggregate_sha256"]):
        raise ValueError("Robustness aggregate inventory differs")
    for name, expected in completion["aggregate_sha256"].items():
        digest, value = aggregates[name]
        if digest != expected:
            raise ValueError("Robustness aggregate differs")
        for field in ("result_content_sha256", "feasibility_content_sha256"):
            if field in value:
                _seal(value, field)
    provenance = {
        "archives": ARCHIVES,
        "explanation": xai_source,
        "robustness_metadata": ROBUSTNESS_SHAS,
        "verified_robustness_cells": len(records),
        "robustness_aggregate_sha256": completion["aggregate_sha256"],
    }
    return xai, records, provenance


def _diagnostic_rows(
    cells: list[dict[str, Any]], programme: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw = []
    for cell in cells:
        if cell["status"] != "failed_diagnostics":
            continue
        diagnostics = cell["fit_attempts"][-1]["diagnostics"]
        flags = diagnostics["failures"]
        if diagnostics["converged"] or not flags:
            raise ValueError("Failed outcome has no recorded final diagnostic failure")
        categories = set()
        for flag in flags:
            text = flag.lower()
            if "divergent" in text:
                categories.add("divergences")
            elif "r_hat" in text or "r-hat" in text:
                categories.add("rhat")
            elif "ess" in text:
                categories.add("ess")
            elif "bfmi" in text:
                categories.add("bfmi")
            elif "tree" in text:
                categories.add("tree_depth")
            else:
                raise ValueError(f"Unknown recorded diagnostic failure: {flag}")
        raw.append(
            {
                "programme": programme,
                "dataset": cell["dataset"],
                "model_key": cell["model_key"],
                "repeat": cell["repeat"],
                "fold": cell["fold"],
                "condition": json.dumps(cell.get("condition", {}), sort_keys=True),
                "n_attempts": len(cell["fit_attempts"]),
                "n_divergent": diagnostics["n_divergent"],
                "n_max_tree_depth": diagnostics["n_max_tree_depth"],
                "max_tree_depth_reached": diagnostics["max_tree_depth"],
                "r_hat_max": diagnostics["r_hat_max"],
                "ess_bulk_min": diagnostics["ess_bulk_min"],
                "ess_tail_min": diagnostics["ess_tail_min"],
                "bfmi_min": diagnostics["bfmi_min"],
                "failure_categories": ";".join(sorted(categories)),
                "recorded_failures": json.dumps(flags),
                "source_cell": cell["path"],
                "cell_content_sha256": cell["cell_content_sha256"],
            }
        )
    summary = []
    for dataset in COHORTS:
        values = [r for r in raw if r["dataset"] == dataset]
        evaluated = sum(c["dataset"] == dataset for c in cells)
        result = {
            "programme": programme,
            "dataset": dataset,
            "evaluated_outcomes": evaluated,
            "failed_outcomes": len(values),
            "divergence_only_failures": sum(
                r["failure_categories"] == "divergences" for r in values
            ),
            **{
                f"failures_involving_{key}": sum(
                    key in r["failure_categories"].split(";") for r in values
                )
                for key in ("divergences", "rhat", "ess", "bfmi", "tree_depth")
            },
            "minimum_final_divergences": min((r["n_divergent"] for r in values), default=0),
            "maximum_final_divergences": max((r["n_divergent"] for r in values), default=0),
            "maximum_tree_depth_reached_among_failures": max(
                (r["max_tree_depth_reached"] for r in values), default=None
            ),
        }
        summary.append(result)
    return summary, raw


def _attribution_rows(xai: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    raw = []
    for kind in ("budget_comparisons", "successive_seed_comparisons"):
        for record in xai["convergence"][kind]:
            agreement = record["agreement"]
            if agreement["status"] not in ("passed", "failed"):
                raise ValueError("Unexpected attribution comparison status")
            rho, overlap = agreement["spearman_rho"], agreement["top_k_overlap"]
            failed_rho = rho < agreement["required_spearman"]
            failed_overlap = overlap < agreement["required_top_five_overlap"]
            if (failed_rho or failed_overlap) != (agreement["status"] == "failed"):
                raise ValueError("Saved stability status differs from archived rule")
            comparison = (
                f"budget_{record['lower_budget_index']}_to_{record['upper_budget_index']}"
                if kind == "budget_comparisons"
                else f"seed_{record['left_seed']}_to_{record['right_seed']}"
            )
            raw.append(
                {
                    "dataset": record["dataset"],
                    "model_key": record["model_key"],
                    "repeat": record["repeat"],
                    "fold": record["fold"],
                    "comparison_type": kind,
                    "comparison": comparison,
                    "seed": record.get("seed"),
                    "budget_index": record.get("budget_index"),
                    "spearman_rho": rho,
                    "top_five_overlap": overlap,
                    "status": agreement["status"],
                    "failed_spearman": int(failed_rho),
                    "failed_top_five_overlap": int(failed_overlap),
                }
            )
    counts = Counter(r["status"] for r in raw)
    if (
        counts != {"passed": 1538, "failed": 102}
        or len(raw) != xai["convergence"]["summary"]["n_evaluable"]
    ):
        raise ValueError("Changed attribution comparison coverage")
    grouped = defaultdict(list)
    for row in raw:
        grouped[row["dataset"], row["model_key"], row["comparison_type"], row["comparison"]].append(
            row
        )
    summary = []
    for (dataset, model, kind, comparison), values in sorted(grouped.items()):
        summary.append(
            {
                "dataset": dataset,
                "model_key": model,
                "comparison_type": kind,
                "comparison": comparison,
                "n_evaluable": len(values),
                "n_failed": sum(v["status"] == "failed" for v in values),
                "spearman_only_failures": sum(
                    v["failed_spearman"] and not v["failed_top_five_overlap"] for v in values
                ),
                "top_five_only_failures": sum(
                    v["failed_top_five_overlap"] and not v["failed_spearman"] for v in values
                ),
                "both_rule_failures": sum(
                    v["failed_spearman"] and v["failed_top_five_overlap"] for v in values
                ),
            }
        )
    return summary, raw


def _reduced_training_rows(
    robustness: list[dict[str, Any]], original: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reduced = {
        (c["model_key"], c["repeat"], c["fold"]): c
        for c in robustness
        if c["dataset"] == "whas500"
        and c["condition"].get("condition_id") == "rq2_fraction_025_observed"
        and c["status"] == "complete"
    }
    full = {
        (c["model_key"], c["repeat"], c["fold"]): c
        for c in original
        if c["dataset"] == "whas500" and c["status"] == "complete"
    }
    pairs = sorted(
        set.intersection(*[{(r, f) for m, r, f in reduced if m == model} for model in PRIORS])
    )
    if not pairs:
        raise ValueError("No matched WHAS500 quarter-training outcomes")
    raw, summary = [], []
    for model in PRIORS:
        for fraction, indexed in ((1.0, full), (0.25, reduced)):
            values = []
            for repeat, fold in pairs:
                c = indexed[model, repeat, fold]
                if (
                    c["validation_subject_ids"]
                    != full[model, repeat, fold]["validation_subject_ids"]
                ):
                    raise ValueError("Reduced-training evaluation subjects differ")
                value = float(c["metrics"]["ibs"])
                if not 0 <= value <= 1:
                    raise ValueError("Invalid reduced-training stored IBS")
                values.append(value)
                raw.append(
                    {
                        "dataset": "whas500",
                        "model_key": model,
                        "repeat": repeat,
                        "fold": fold,
                        "training_fraction": fraction,
                        "ibs": value,
                        "source_cell": c["path"],
                        "cell_content_sha256": c["cell_content_sha256"],
                    }
                )
            summary.append(
                {
                    "dataset": "whas500",
                    "model_key": model,
                    "training_fraction": fraction,
                    "n_matched_folds": len(values),
                    "mean_ibs": _mean(values),
                    "sd_ibs": statistics.stdev(values),
                    "matching": "all three priors complete under quarter training; full training uses the same folds",
                }
            )
    return summary, raw


def _table(caption: str, label: str, columns: str, header: str, rows: list[str], note: str) -> str:
    return "\n".join(
        [
            r"\begin{table}[htbp]",
            r"\centering",
            r"\begingroup\singlespacing\footnotesize",
            r"\setlength{\tabcolsep}{3pt}",
            rf"\caption{{{caption}}}\label{{{label}}}",
            r"\begin{adjustbox}{max width=\textwidth}",
            rf"\begin{{tabular}}{{@{{}}{columns}@{{}}}}",
            r"\toprule " + header + r"\\\midrule",
            *rows,
            r"\bottomrule",
            r"\end{tabular}",
            r"\end{adjustbox}",
            r"\par\smallskip",
            r"\begin{minipage}{\textwidth}",
            note,
            r"\end{minipage}",
            r"\endgroup",
            r"\end{table}",
            "",
        ]
    )


def _probability(value: float) -> str:
    if value < 0.001:
        return r"$<0.001$"
    if value > 0.999:
        return r"$>0.999$"
    return f"{value:.3f}"


def _tables(
    posterior: list[dict[str, Any]],
    prior: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    attribution: list[dict[str, Any]],
) -> dict[str, str]:
    selected = [r for r in posterior if r["feature"] in SELECTED[r["dataset"]]]
    selected.sort(
        key=lambda r: (
            list(COHORTS).index(r["dataset"]),
            SELECTED[r["dataset"]].index(r["feature"]),
            list(PRIORS).index(r["model_key"]),
        )
    )
    rows = [
        f"{COHORTS[r['dataset']]} & {FEATURE_NAMES[r['feature']]} & {PRIORS[r['model_key']]} & {r['mean_beta']:.3f} & {r['mean_hr_interval_width']:.3f} & {r['n_hr_intervals_excluding_one']}/{r['n_matched_folds']} & {r['mean_absolute_beta_difference_from_normal']:.3f}\\\\"
        for r in selected
    ]
    tables = {
        "table_posterior_summary.tex": _table(
            "Posterior coefficient summaries across matched accepted folds.",
            "tab:exam-posterior-summary",
            "lllrrrr",
            r"Cohort & Predictor & Prior & Mean $\beta$ & HR width & Excludes 1 & $|\Delta\beta_N|$",
            rows,
            r"N: Normal; H: Horseshoe; S: continuous Spike-and-Slab. Each numeric coefficient refers to one training-fold standard deviation. Values are equally weighted summaries of 7 GBSG2, 25 WHAS500 and 23 METABRIC matched fits. HR width is the mean of the stored 95\% HR interval widths; it is not a pooled credible interval. Excludes 1 gives the number of those intervals excluding unity. $|\Delta\beta_N|$ is the mean absolute difference from the Normal posterior mean in the same fold, a descriptive measure of prior sensitivity.",
        )
    }
    direction = [
        f"{COHORTS[r['dataset']]} & {FEATURE_NAMES[r['feature']]} & {PRIORS[r['model_key']]} & {_probability(r['mean_probability_beta_positive'])} & {format(r['mean_continuous_mixture_variance_weight'], '.3f') if r['mean_continuous_mixture_variance_weight'] is not None else '--'}\\\\"
        for r in selected
    ]
    tables["table_posterior_direction.tex"] = _table(
        "Directional posterior probabilities and continuous-mixture weights across matched folds.",
        "tab:exam-posterior-direction",
        "lllrr",
        r"Cohort & Predictor & Prior & Mean $P(\beta>0)$ & Mean weight",
        direction,
        r"All entries average the separate matched-fold posterior summaries; they do not define a pooled posterior. Probabilities at the displayed bounds are rounded conservatively. The weight is the stored continuous-mixture variance weight, available for S only; it is not a probability of a non-zero coefficient. N: Normal; H: Horseshoe; S: continuous Spike-and-Slab. Fold counts and scales match Table~\ref{tab:exam-posterior-summary}.",
    )
    rows = []
    for dataset in COHORTS:
        for model in PRIORS:
            for time in (1.0, 2.0):
                r = next(
                    v
                    for v in prior
                    if v["dataset"] == dataset
                    and v["model_key"] == model
                    and v["scaled_time"] == time
                    and v["check"] == "covariate_population"
                )
                quantiles = f"{r['mean_foldwise_median_survival']:.3f} [{_probability(r['mean_foldwise_lower_95'])}, {_probability(r['mean_foldwise_upper_95'])}]"
                rows.append(
                    f"{COHORTS[dataset]} & {PRIORS[model]} & {int(time)} & {r['n_fits']} & {quantiles} & {100 * r['mean_mass_survival_below_0_01']:.1f} & {100 * r['mean_mass_survival_above_0_99']:.1f}\\\\"
                )
    tables["table_prior_predictive.tex"] = _table(
        "Stored full-model prior predictive survival summaries.",
        "tab:exam-prior-predictive",
        "llrrlrr",
        r"Cohort & Prior & $t^*$ & Fits & Median [2.5\%, 97.5\%] & $S<0.01$ (\%) & $S>0.99$ (\%)",
        rows,
        r"$t^*=1$ denotes the median observed event time in each outer-training fold; $t^*=2$ denotes twice that time. Entries average each accepted fit's stored subject-by-prior-draw summaries over up to 512 training subjects; bracketed numbers average foldwise quantiles, not a pooled interval. Percentages give the mean share of subject--draw survival values near 0 or 1. These checks condition on training-derived preprocessing, time scaling and baseline intervals. N: Normal; H: Horseshoe; S: continuous Spike-and-Slab. Fit counts include all accepted fits for each prior.",
    )
    rows = [
        f"{r['programme']} & {COHORTS[r['dataset']]} & {r['evaluated_outcomes']} & {r['failed_outcomes']} & {r['divergence_only_failures']} & {r['minimum_final_divergences']}--{r['maximum_final_divergences']} & {r['failures_involving_rhat']}/{r['failures_involving_ess']}/{r['failures_involving_bfmi']}/{r['failures_involving_tree_depth']}\\\\"
        for r in diagnostics
    ]
    tables["table_diagnostic_failures.tex"] = _table(
        "Recorded final-attempt causes of diagnostic rejection.",
        "tab:exam-diagnostic-failures",
        "llrrrrl",
        r"Analysis & Cohort & Outcomes & Rejected & Divergence only & Divergences & Other gates",
        rows,
        r"Outcomes count all three Bayesian priors; every rejected outcome was a Horseshoe fit. Divergences are the range in the final attempt among rejected outcomes (0--0 denotes no rejections). Other gates report counts of rejections involving $\widehat R$/ESS/BFMI/tree depth, in that order. Failures are classified from the recorded diagnostic flags, rather than from the thresholds alone. The configured default tree-depth ceiling was 10; maximum reached depth and ceiling-hit counts are retained separately in the supporting summary.",
    )
    rows = []
    keys = ("budget_1_to_2", "budget_2_to_3", "seed_104729_to_130363", "seed_130363_to_155921")
    for dataset in COHORTS:
        for model in PRIORS:
            values = [r for r in attribution if r["dataset"] == dataset and r["model_key"] == model]
            entries = [next(r for r in values if r["comparison"] == key) for key in keys]
            ratios = [f"{r['n_failed']}/{r['n_evaluable']}" for r in entries]
            rows.append(
                f"{COHORTS[dataset]} & {PRIORS[model]} & "
                + " & ".join(ratios)
                + f" & {sum(r['n_failed'] for r in entries)}/{sum(r['n_evaluable'] for r in entries)}\\\\"
            )
    tables["table_attribution_failures.tex"] = _table(
        "Attribution sampling-stability comparisons that did not meet the specified criterion.",
        "tab:exam-attribution-failures",
        "lllllll",
        r"Cohort & Prior & Budget 1--2 & Budget 2--3 & Seed 1--2 & Seed 2--3 & Total",
        rows,
        r"Entries are failed/evaluable comparisons. Budgets use 25/50, 50/100 and 100/200 validation/background subjects, respectively, with three seeds (104729, 130363 and 155921). Seed comparisons use the largest budget. The rule requires Spearman correlation at least 0.95 and at least four shared top-five groups. Comparisons share fitted models and are not independent experiments. There were 102 failures among 1640 evaluable comparisons; all involved Spearman correlation alone, and none failed the top-five overlap criterion. N: Normal; H: Horseshoe; S: continuous Spike-and-Slab.",
    )
    return tables


def build_report(run_dir: Path, assets: Path, output: Path) -> dict[str, Any]:
    """Verify frozen inputs and write descriptive summaries of existing evidence.

    Args:
        run_dir: Restored original confirmatory run.
        assets: Directory with the two pinned programme release archives.
        output: New output directory; no existing frozen result is modified.

    Returns:
        Provenance including verified counts, source identities and output hashes.
    """
    run = verify_frozen_run(run_dir)
    if run.run_dir.name != RUN_NAME or run.completion["status_counts"] != {
        "complete": 430,
        "failed_diagnostics": 20,
    }:
        raise ValueError("Expected the unchanged original confirmatory run")
    cells = list(run.cells)
    posterior, fold_posterior, excluded, matched = _posterior_rows(cells)
    prior, fold_prior = _prior_rows(cells)
    xai, robustness, supplementary = _release_inputs(assets, run)
    original = [_compact_cell(p, c) for p, c in cells if c["model_key"] in PRIORS]
    diagnostic_summary, diagnostic_raw = [], []
    for name, records in (("Original", original), ("Robustness", robustness)):
        summary, raw = _diagnostic_rows(records, name)
        diagnostic_summary.extend(summary)
        diagnostic_raw.extend(raw)
    attribution, attribution_raw = _attribution_rows(xai)
    reduced_training, reduced_training_raw = _reduced_training_rows(robustness, original)
    tables = _tables(posterior, prior, diagnostic_summary, attribution)
    output.mkdir(parents=True, exist_ok=True)
    files = {
        "posterior_matched_all_features.csv": posterior,
        "posterior_matched_by_fold.csv": fold_posterior,
        "posterior_excluded_features.csv": excluded,
        "prior_predictive_summary.csv": prior,
        "prior_predictive_by_fold.csv": fold_prior,
        "diagnostic_failure_summary.csv": diagnostic_summary,
        "diagnostic_failures_by_outcome.csv": diagnostic_raw,
        "attribution_failure_summary.csv": attribution,
        "attribution_comparisons.csv": attribution_raw,
        "whas500_training_fraction_ibs.csv": reduced_training,
        "whas500_training_fraction_ibs_by_fold.csv": reduced_training_raw,
    }
    for name, rows in files.items():
        _csv(output / name, rows)
    for name, text in tables.items():
        (output / name).write_text(text)
    provenance = {
        "schema_version": "1.0.0",
        "fitting_performed": False,
        "simulation_performed": False,
        "verified_original_cells": len(cells),
        "matched_fold_counts": MATCHED_COUNTS,
        "matched_fold_identities": matched,
        "posterior_feature_rows": len(posterior),
        "posterior_excluded_features": excluded,
        "original_failure_count": 20,
        "robustness_failure_count": 55,
        "attribution_evaluable": len(attribution_raw),
        "attribution_failure_count": 102,
        "original_source_hashes": run.source_hashes,
        "supplementary_sources": supplementary,
        "generator_sha256": sha256_file(Path(__file__)),
        "aggregation": {
            "fold_weighting": "equal within matched cohort/feature/prior",
            "pooled_posterior": False,
            "hr_width": "mean stored HR upper95 minus lower95 per fit",
            "beta_sensitivity": "mean absolute same-fold posterior beta-mean difference from Normal",
            "prior_predictive": "mean of stored fold summaries conditional on training-derived design",
            "diagnostic_failures": "final attempt archived failures, not inferred causal explanation",
        },
        "outputs": {name: sha256_file(output / name) for name in sorted(set(files) | set(tables))},
    }
    (output / "provenance.json").write_text(
        json.dumps(provenance, indent=2, allow_nan=False) + "\n"
    )
    return provenance


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, default=ROOT / "reports/confirmatory" / RUN_NAME)
    parser.add_argument(
        "--assets",
        type=Path,
        default=ROOT.parent / "thesis-overleaf/build/examiner-polish-20261119/source_assets",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT.parent / "thesis-overleaf/report_summaries/examiner_polish",
    )
    args = parser.parse_args()
    result = build_report(args.run_dir, args.assets, args.output)
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "verified_original_cells",
                    "matched_fold_counts",
                    "original_failure_count",
                    "robustness_failure_count",
                    "attribution_evaluable",
                    "attribution_failure_count",
                )
            }
        )
    )
