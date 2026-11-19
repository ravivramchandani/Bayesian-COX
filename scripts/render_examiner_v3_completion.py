"""Summarise saved sensitivities and render wording/layout copies without fitting."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
COHORTS = {"gbsg2": "GBSG2", "metabric": "METABRIC", "whas500": "WHAS500"}


def verified(path: Path, expected: str) -> bytes:
    """Return source bytes only when they agree with the recorded frozen input."""
    value = path.read_bytes()
    if hashlib.sha256(value).hexdigest() != expected:
        raise ValueError(f"Source hash mismatch: {path.name}")
    return value


def sensitivity_summary(rows: list[dict[str, str]]) -> dict:
    """Summarise complete Normal-reference contrasts without repeated anchor rows."""
    selected = [r for r in rows if r["effect_type"] == "Direct"
                and r["component"] in ("design", "feature")
                and r["condition"] not in ("primary", "prior_primary")
                and r["model_a"] == "Normal"]
    identities = [(r["dataset"], r["component"], r["condition"], r["model_b"])
                  for r in selected]
    if len(identities) != len(set(identities)):
        raise ValueError("Repeated sensitivity contrast")
    complete = [r for r in selected if int(r["n_paired_folds"]) == int(r["expected_paired_folds"])]
    result = {"eligible_contrasts": len(selected), "complete_contrasts": len(complete), "priors": {}}
    for prior in ("Horseshoe", "Spike-and-slab"):
        block = [r for r in complete if r["model_b"] == prior]
        values = [float(r["observed"]) for r in block]
        result["priors"][prior] = {
            "complete_contrasts": len(block),
            "minimum": min(values) if values else None,
            "maximum": max(values) if values else None,
            "nominal_intervals_excluding_zero": [r for r in block
                if float(r["confidence_lower"]) > 0 or float(r["confidence_upper"]) < 0],
        }
    result["single_pair_nonzero_intervals"] = [r for r in rows
        if r["effect_type"] != "Direct" and int(r["n_paired_folds"]) == 1
        and (float(r["confidence_lower"]) > 0 or float(r["confidence_upper"]) < 0)]
    return result


def calibration_figure(rows: list[dict[str, str]], output: Path) -> None:
    """Replot the same saved grouped calibration points with separated axis labels."""
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "pdf.fonttype": 42})
    figure, axes = plt.subplots(1, 3, figsize=(7.6, 3.0), sharex=True, sharey=True,
                                layout="constrained")
    figure.get_layout_engine().set(w_pad=0.06, h_pad=0.05, wspace=0.12)
    for axis, (cohort, label) in zip(axes, COHORTS.items(), strict=True):
        block = sorted([r for r in rows if r["dataset"] == cohort], key=lambda r: int(r["bin"]))
        if len(block) != 5:
            raise ValueError(f"Expected five saved calibration groups: {cohort}")
        predicted = [float(r["mean_predicted_survival"]) for r in block]
        observed = [float(r["observed_survival"]) for r in block]
        lower = [float(r["observed_lower"]) for r in block]
        upper = [float(r["observed_upper"]) for r in block]
        axis.plot([0, 1], [0, 1], color="#777777", linestyle="--", linewidth=1)
        axis.errorbar(predicted, observed,
                      yerr=[[y - lo for y, lo in zip(observed, lower, strict=True)],
                            [hi - y for hi, y in zip(upper, observed, strict=True)]],
                      color="#23628A", ecolor="#8CAFC4", marker="o", markersize=4,
                      capsize=3, linewidth=1.2)
        horizon = float(block[0]["horizon"])
        unit = "months" if cohort == "metabric" else "days"
        time = f"{horizon:.2f}" if cohort == "metabric" else f"{horizon:g}"
        axis.set_title(f"{label}: {time} {unit}")
        axis.set(xlim=(0, 1), ylim=(0, 1), xlabel="Mean predicted survival",
                 xticks=[0, 0.5, 1], xticklabels=["0.0", "0.5", "1.0"])
        axis.grid(alpha=0.18)
        axis.set_aspect("equal", adjustable="box")
    axes[0].set_ylabel("Observed Kaplan-Meier survival")
    figure.savefig(output, metadata={"Creator": None, "Producer": None,
                                     "CreationDate": None, "ModDate": None})
    plt.close(figure)


def render(thesis: Path, pins: Path, output: Path) -> None:
    """Write new presentation copies, retaining the original scientific source files."""
    inputs = json.loads(pins.read_text())
    content = {name: verified(thesis / name, sha) for name, sha in inputs.items()}
    output.mkdir(parents=True, exist_ok=True)
    mapping = {}
    for name, value in content.items():
        if not name.endswith(".tex"):
            continue
        text = value.decode().replace("Spike-and-slab", "Spike-and-Slab")
        text = text.replace("accepted horseshoe fits", "accepted Horseshoe fits")
        text = text.replace("continuous spike-and-slab predictions", "continuous Spike-and-Slab predictions")
        text = text.replace("Published full predictors", "All 14 supplied predictors")
        text = text.replace("MI order", "Infarction order").replace("MI type", "Infarction type")
        text = text.replace("86.0667 months", "86.07 months")
        if name.endswith("table_attribution_failures.tex"):
            text = text.replace(r"\caption{", r"\caption[Attribution sampling-stability comparisons]{", 1)
        if name.endswith("table_robustness_effects.tex"):
            text = text.replace(r"Counts show the available paired folds.\par",
                r"Counts show the available paired folds. Nominal intervals are exploratory and "
                r"not multiplicity-adjusted. Partial-coverage rows concern the retained accepted "
                r"comparisons; with one pair, the interval describes patient resampling for that "
                r"fitted partition rather than variation across fitted partitions.\par")
        if text.encode() == value:
            continue
        target = output / Path(name).name
        if target.name in [Path(p).name for p in mapping.values()]:
            raise ValueError("Ambiguous presentation filename")
        target.write_text(text)
        mapping[name] = str(target.relative_to(thesis))
    curve_name = "report_summaries/supervisor_checks/calibration_curve_examples.csv"
    with (thesis / curve_name).open(newline="") as stream:
        curves = list(csv.DictReader(stream))
    figure = output / "figure_calibration_examples.pdf"
    calibration_figure(curves, figure)
    mapping["report_summaries/supervisor_checks/figure_calibration_examples.pdf"] = str(
        figure.relative_to(thesis))
    with (thesis / "generated/robustness_effects.csv").open(newline="") as stream:
        summary = sensitivity_summary(list(csv.DictReader(stream)))
    (output / "sensitivity_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    record = {"fitting_performed": False, "simulation_performed": False,
              "source_sha256": inputs, "presentation_inputs": mapping,
              "calibration_points_unchanged": True,
              "outputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(output.iterdir()) if p.name != "provenance.json"}}
    (output / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thesis", type=Path, required=True)
    parser.add_argument("--pins", type=Path, default=ROOT / "reports/tables/examiner_v3_completion/source_hashes.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.thesis, args.pins, args.output)
