"""Render separately verified post-hoc extension tables and scientific figures."""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipelines.extensions.runner import verified_cell
from src.utils.io import read_mapping, write_json_atomic
from src.utils.reproducibility import sha256_file

LABELS = {"cox_ph": "Cox PH", "random_survival_forest": "Random survival forest", "deepsurv": "DeepSurv",
          "bayesian_normal": "Bayesian normal", "bayesian_horseshoe": "Horseshoe (.999 sampler)",
          "bayesian_horseshoe_original": "Original horseshoe", "bayesian_spike_slab": "Continuous spike/slab",
          "ridge": "Ridge Cox", "lasso": "Lasso Cox", "elastic_net": "Elastic-net Cox",
          "pv_horseshoe": "Calibrated horseshoe", "catalytic_fixed": "Catalytic fixed",
          "catalytic_adaptive": "Catalytic adaptive", "catalytic_wme": "Catalytic weighted mixture",
          "ADR032_horseshoe": "ADR-032 horseshoe",
          "all": "Assess all", "none": "Assess none"}


def save_figure(fig: plt.Figure, output: Path, name: str, sources: list[str]) -> dict:
    """Save inspectable PDF/PNG pairs and exact evidence-file lineage."""
    fig.text(0.01, 0.012, "Post-hoc extension | Frozen primary evidence retained separately", fontsize=8)
    fig.savefig(output / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(output / f"{name}.png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return {"name": name, "source_files": sources, "pdf_sha256": sha256_file(output / f"{name}.pdf"),
            "png_sha256": sha256_file(output / f"{name}.png"), "visual_review": "pending"}


def save_table(rows: list[dict], output: Path, name: str, sources: list[str]) -> dict:
    """Preserve the table bytes and source lineage alongside the figures."""
    path = output / f"{name}.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    return {"name": name, "source_files": sources, "csv_sha256": sha256_file(path)}


def main() -> None:
    """Render stored verified evidence, without creating new fitted results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    completion = read_mapping(args.run / "completion.json")
    for relative, digest in {**completion["cell_sha256"], **completion["aggregate_sha256"]}.items():
        if sha256_file(args.run / relative) != digest:
            raise ValueError(f"renderer input changed: {relative}")
    if args.output.exists():
        raise FileExistsError("choose a new renderer output directory")
    args.output.mkdir(parents=True)
    cells = [verified_cell(p) for p in sorted((args.run / "cells").glob("*.json"))]
    groups = defaultdict(list)
    metrics_rows = []
    for c in cells:
        metrics_rows.append({k: c.get(k) for k in ("cell_id", "dataset", "setting", "model_key", "repeat", "fold", "condition", "status", "p", "events_train", "n_train", "seconds")}
                            | {k: c.get("metrics", {}).get(k) for k in ("ibs", "harrell_c_index", "uno_c_index", "mean_auc")})
        if c["condition"] == "full":
            groups[(c["dataset"], c["setting"])].append(c)
    tables = [save_table(metrics_rows, args.output, "fold_metrics", ["cells/*.json"])]
    figures = []
    for (dataset, setting), records in sorted(groups.items()):
        models = sorted({c["model_key"] for c in records})
        fig, ax = plt.subplots(figsize=(11, max(5, len(models) * 0.43)))
        for i, model in enumerate(models):
            values = [c["metrics"]["ibs"] for c in records if c["model_key"] == model and c["status"] == "complete"]
            if values:
                lower, middle, upper = np.quantile(values, [0.25, 0.5, 0.75])
                ax.errorbar(middle, i, xerr=[[middle-lower], [upper-middle]], fmt="o", color="navy", capsize=4)
            ax.text(1.015, i, f"{len(values)}/25 accepted", transform=ax.get_yaxis_transform(), fontsize=9, va="center")
        ax.set_yticks(range(len(models)), [LABELS[m] for m in models])
        ax.invert_yaxis()
        ax.set_xlabel("IBS (lower is better); median and fold interquartile range")
        ax.set_title(f"{dataset.upper()} | {setting} | predictive error and diagnostic coverage")
        fig.tight_layout(rect=[0, 0.035, 0.83, 1])
        sources = [f"cells/{c['cell_id']}.json" for c in records]
        figures.append(save_figure(fig, args.output, f"{dataset}_{setting}_ibs", sources))
        fig, axes = plt.subplots(2, 3, figsize=(14, 8))
        for h in range(3):
            for row, parameter in enumerate(("intercept", "slope")):
                ax = axes[row, h]
                for i, model in enumerate(models):
                    values = [c["metrics"]["calibration"][h]["summary"][parameter]["estimate"]
                              for c in records if c["model_key"] == model and c["status"] == "complete"]
                    values = [v for v in values if v is not None and np.isfinite(v)]
                    if values:
                        lo, mid, hi = np.quantile(values, [0.25, 0.5, 0.75])
                        ax.errorbar(i, mid, yerr=[[mid-lo], [hi-mid]], fmt="o", markersize=4)
                ax.axhline(0 if parameter == "intercept" else 1, color="grey", linestyle="--")
                ax.set_title(f"Training event quantile {(0.25,0.5,0.75)[h]}: {parameter}")
                ax.set_xticks(range(len(models)), [LABELS[m] for m in models], rotation=90, fontsize=7)
                ax.set_ylabel("Median and fold IQR")
        fig.suptitle(f"{dataset.upper()} | {setting} | calibration of accepted fits")
        fig.tight_layout(rect=[0, 0.04, 1, 0.95])
        figures.append(save_figure(fig, args.output, f"{dataset}_{setting}_calibration", sources))
    curves = read_mapping(args.run / "decision_curves.json")
    point_rows, support_rows, unavailable_rows = [], [], []
    for key, result in sorted(curves.items()):
        for model, reason in result["unavailable"].items():
            unavailable_rows.append({"group": key, "model_key": model, "reason": reason})
        for model, supports in result["support"].items():
            support_rows.extend({"group": key, "model_key": model, **support} for support in supports)
        for model, row in result.get("curves", {}).get("models", {}).items():
            for i, threshold in enumerate(result["thresholds"]):
                point = {"group": key, "model_key": model, "threshold": threshold,
                         "net_benefit": row["net_benefit"][i],
                         "pointwise_lower": row["pointwise_lower"][i],
                         "pointwise_upper": row["pointwise_upper"][i]}
                for default in ("all", "none"):
                    difference = row.get("differences", {}).get(default)
                    for field in ("estimate", "pointwise_lower", "pointwise_upper"):
                        point[f"minus_{default}_{field}"] = difference[field][i] if difference else None
                point_rows.append(point)
        fig, ax = plt.subplots(figsize=(12, 6.5))
        for model, row in result.get("curves", {}).get("models", {}).items():
            ax.plot(result["thresholds"], row["net_benefit"], label=LABELS[model],
                    linestyle="--" if model in {"all", "none"} else "-")
        if "curves" not in result:
            ax.text(0.5, 0.5, "No model has complete supported forecasts", ha="center", transform=ax.transAxes)
        else:
            ax.legend(loc="center left", bbox_to_anchor=(1.01,0.5), fontsize=8)
        ax.set_xlabel("Exploratory assessment threshold probability")
        ax.set_ylabel("IPCW net benefit per patient")
        ax.set_title(f"{key.replace('__',' | ')}\nAdaptive training-horizon estimates; pointwise intervals in accompanying table")
        fig.tight_layout(rect=[0, 0.04, 0.82, 1])
        figures.append(save_figure(fig, args.output, f"decision_{key}", ["decision_curves.json"]))
    for name, rows in (("decision_curve_points", point_rows), ("decision_curve_support", support_rows),
                       ("decision_curve_unavailable", unavailable_rows)):
        tables.append(save_table(rows, args.output, name, ["decision_curves.json"]))
    families = read_mapping(args.run / "paired_families.json")
    family_rows = []
    for name, family in families.items():
        rows = family["contrasts"]
        fig, ax = plt.subplots(figsize=(11, max(5, 0.33*len(rows))))
        labels = []
        for i, row in enumerate(rows):
            dataset = "METABRIC matched" if row["dataset"] == "metabric_matched" else row["dataset"].upper()
            if "model" in row:
                labels.append(f"{dataset}: {LABELS[row['model']]} (clinical+expression - clinical)")
            else:
                labels.append(f"{dataset}: {LABELS[row['left']]} - {LABELS[row['right']]}")
            effect = row.get("effect")
            if effect:
                mid, lo, hi = effect["mean_difference"], effect["confidence_lower"], effect["confidence_upper"]
                ax.errorbar(mid, i, xerr=[[mid-lo], [hi-mid]], fmt="o", color="navy", capsize=3)
            family_rows.append({"family": name, **{k:v for k,v in row.items() if k != "effect"}, **(effect or {})})
        ax.set_yticks(range(len(rows)), labels, fontsize=8)
        ax.invert_yaxis()
        ax.axvline(0, color="grey", linestyle="--")
        ax.set_xlabel("Paired mean IBS difference and corrected 95% interval")
        ax.set_title(f"{name.replace('_',' ')}\nHolm family complete: {family['family_complete']}; unavailable contrasts have no point")
        fig.tight_layout(rect=[0, 0.03, 1, 1])
        figures.append(save_figure(fig, args.output, f"paired_{name}", ["paired_families.json"]))
    tables.append(save_table(family_rows, args.output, "paired_families", ["paired_families.json"]))
    rq2 = json.loads((args.run / "rq2_effects.json").read_text())
    rq2_rows = [{k:v for k,v in row.items() if k != "corrected_descriptive_interval"}
                | row.get("corrected_descriptive_interval", {}) for row in rq2]
    tables.append(save_table(rq2_rows, args.output, "rq2_effects", ["rq2_effects.json"]))
    conditions = ["fraction_0.25", "fraction_0.50", "fraction_0.75", "admin_q0.75", "admin_q0.50"]
    for dataset in ("gbsg2", "whas500", "metabric"):
        fig, axes = plt.subplots(1, 3, figsize=(14, 5))
        for ax, prior in zip(axes, ("bayesian_normal", "bayesian_horseshoe", "bayesian_spike_slab"), strict=True):
            for model in ("catalytic_fixed", "catalytic_adaptive", "catalytic_wme"):
                rows = [r for r in rq2 if r["dataset"] == dataset and r["model"] == model and r["prior"] == prior and r["kind"] == "direct"]
                lookup = {r["condition"]: r["mean_difference"] for r in rows}
                ax.plot(range(5), [lookup.get(c) for c in conditions], "o-", label=LABELS[model])
            ax.axhline(0, color="grey", linestyle="--")
            ax.set_title(LABELS[prior])
            ax.set_xticks(range(5), ["25% train", "50% train", "75% train", "Admin 75%", "Admin 50%"], rotation=35)
            ax.set_ylabel("Mean paired IBS difference; descriptive")
        axes[-1].legend(fontsize=8)
        fig.suptitle(f"{dataset.upper()} | information regimes | partial paired coverage is in the table")
        fig.tight_layout(rect=[0, 0.05, 1, 0.93])
        figures.append(save_figure(fig, args.output, f"rq2_{dataset}", ["rq2_effects.json"]))
    lineage = {"evidence_status": "post_hoc_extension", "source_manifest_sha256": sha256_file(args.run / "manifest.json"),
               "source_completion_sha256": sha256_file(args.run / "completion.json"),
               "renderer_sha256": sha256_file(Path(__file__)), "figures": figures, "tables": tables,
               "actual_visual_review": "pending; creation does not constitute QA"}
    write_json_atomic(args.output / "lineage.json", lineage, overwrite=False)
    print(len(figures), "figure pairs written; actual visual review remains required")


if __name__ == "__main__":
    main()
