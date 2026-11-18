"""Render thesis presentation copies of verified results, without model fitting."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

MODELS = ("cox_ph", "random_survival_forest", "deepsurv", "bayesian_normal",
          "bayesian_horseshoe", "bayesian_spike_slab")
LABELS = ("CoxPH", "RSF", "DeepSurv", "Normal", "Horseshoe", "Spike-and-Slab")
COLORS = ("#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9")
COHORTS = ("gbsg2", "metabric", "whas500")
DATE = datetime(2000, 1, 1, tzinfo=UTC)


def sha256(path: Path) -> str:
    """Return a file's SHA256 without altering its contents."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_verified(generated: Path, name: str) -> list[dict[str, str]]:
    """Reject changed input rather than plotting it under the frozen provenance."""
    provenance = json.loads((generated / "provenance.json").read_text())
    path = generated / name
    if sha256(path) != provenance["outputs"][name]["sha256"]:
        raise ValueError(f"Frozen input hash mismatch: {name}")
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def select_rows(rows: list[dict[str, str]], dataset: str,
                parameter: str | None = None) -> list[dict[str, str]]:
    """Require one correctly ordered value for every model in a cohort/panel."""
    selected = [r for r in rows if r["dataset"] == dataset and
                (parameter is None or
                 (r["parameter"] == parameter and r["horizon_index"] == "2"))]
    by_model = {r["model_key"]: r for r in selected}
    if len(selected) != len(MODELS) or set(by_model) != set(MODELS):
        raise ValueError(f"Incomplete or duplicate panel: {dataset}/{parameter}")
    return [by_model[model] for model in MODELS]


def draw_panel(ax, rows, mean: str, sd: str, count: str) -> None:
    """Plot means and sample SDs, distinguishing partial fold coverage."""
    for index, (row, color) in enumerate(zip(rows, COLORS, strict=True)):
        partial = int(row[count]) < 25
        ax.errorbar(float(row[mean]), index, xerr=float(row[sd]), fmt="o",
                    color=color, markerfacecolor="white" if partial else color,
                    markeredgewidth=1.3, markersize=5, capsize=2, linewidth=1.1)
    ax.set_yticks(range(6), [f"{label} ({row[count]}/25)"
                           for label, row in zip(LABELS, rows, strict=True)])
    ax.invert_yaxis()
    ax.grid(axis="x", alpha=0.20)
    ax.tick_params(labelsize=10)
    ax.spines[["top", "right"]].set_visible(False)


def render(thesis: Path, output: Path) -> None:
    """Create consistently labelled figures and a display-only posterior table."""
    output.mkdir(parents=True, exist_ok=True)
    generated = thesis / "generated"
    predictive = load_verified(generated, "predictive_metrics.csv")
    calibration = load_verified(generated, "calibration_all_horizons.csv")
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9,
                         "pdf.fonttype": 42})
    metadata = {"CreationDate": DATE, "ModDate": DATE}
    for kind in ("predictive", "calibration"):
        fig, axes = plt.subplots(3, 2, figsize=(7.3, 7.4), layout="constrained")
        for cohort_index, dataset in enumerate(COHORTS):
            if kind == "predictive":
                rows = select_rows(predictive, dataset)
                panels = (("uno_c_index", "Uno concordance\n(higher is better)"),
                          ("ibs", "Integrated Brier score\n(lower is better)"))
                for index, (metric, title) in enumerate(panels):
                    draw_panel(axes[cohort_index, index], rows, metric + "_mean",
                               metric + "_sd", "n_complete")
                    axes[cohort_index, index].set_xlabel(title, fontsize=10)
                name = "figure_predictive_primary.pdf"
            else:
                for index, (parameter, title, reference) in enumerate(
                    (("slope", "Calibration slope", 1),
                     ("calibration_in_the_large", "Calibration-in-the-large", 0))
                ):
                    rows = select_rows(calibration, dataset, parameter)
                    draw_panel(axes[cohort_index, index], rows, "mean", "standard_deviation", "n_folds")
                    axes[cohort_index, index].axvline(reference, color="0.35", ls="--", lw=0.8)
                    axes[cohort_index, index].set_xlabel(title, fontsize=10)
                name = "figure_calibration_summary.pdf"
            for ax in axes[cohort_index]:
                ax.set_title(dataset.upper(), fontsize=11, fontweight="bold")
        fig.savefig(output / name, metadata=metadata)
        plt.close(fig)
    # These are bounded displays of stored Monte Carlo estimates, not new probabilities.
    source = thesis / "tables/table_posterior_examples.tex"
    table = source.read_text().replace(" & 1.000 \\", " & $>0.999$ \\")
    table = table.replace(" & 0.000 \\", " & $<0.001$ \\")
    table = table.replace("first outer normal-prior fit", "first outer Normal-prior fit")
    (output / "table_posterior_examples.tex").write_text(table)
    calibration_source = thesis / "tables/table_calibration.tex"
    calibration_table = calibration_source.read_text().replace(
        "Calibration-in-large", "Calibration-in-the-large")
    (output / "table_calibration.tex").write_text(calibration_table)
    inputs = [generated / "predictive_metrics.csv", generated / "calibration_all_horizons.csv",
              generated / "provenance.json", source, calibration_source]
    provenance = {
        "fitting_performed": False, "simulation_performed": False,
        "inputs": {str(p.relative_to(thesis)): sha256(p) for p in inputs},
        "script_sha256": sha256(Path(__file__)),
        "rules": {"predictive": "Saved Uno C and IBS means plus sample fold SDs.",
                  "calibration": "Saved middle-horizon slope and fixed-slope intercept; sample fold SDs.",
                  "coverage": "All points labelled with accepted/25 folds; open points have partial coverage.",
                  "posterior_probability": "Rounded boundary values displayed as <0.001 or >0.999; no claim of exact probability zero or one."},
        "outputs": {p.name: sha256(p) for p in sorted(output.iterdir())
                    if p.is_file() and p.name != "provenance.json"},
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thesis-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    render(arguments.thesis_dir, arguments.output_dir)
