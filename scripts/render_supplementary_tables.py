"""Render supplementary LaTeX tables from the study's saved aggregate results."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COHORTS = {"gbsg2": "GBSG2", "whas500": "WHAS500", "metabric": "METABRIC"}
MODELS = {
    "cox_ph": "CoxPH",
    "random_survival_forest": "RSF",
    "deepsurv": "DeepSurv",
    "bayesian_normal": "Normal",
    "bayesian_horseshoe": "Horseshoe",
    "bayesian_spike_slab": "Spike-and-slab",
}


def verified_rows(folder: str, filename: str) -> list[dict[str, str]]:
    """Read a saved aggregate after checking its recorded checksum."""
    directory = ROOT / folder
    path = directory / filename
    manifest = json.loads((directory / "provenance.json").read_text())
    expected = manifest["outputs"][filename]["sha256"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"Changed aggregate: {filename}")
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def render_calibration() -> None:
    """Display all three calibration horizons for each model and cohort."""
    rows = verified_rows("generated", "calibration_all_horizons.csv")
    lookup = {
        (r["dataset"], r["model_key"], int(r["horizon_index"]), r["parameter"]): r
        for r in rows
    }
    if len(rows) != 162 or len(lookup) != 162:
        raise ValueError("Expected 162 unique calibration summaries")
    lines = []
    for cohort, label in COHORTS.items():
        lines.extend([
            r"\clearpage\begingroup\singlespacing\footnotesize",
            r"\setlength{\LTpre}{6pt}\setlength{\LTpost}{6pt}",
            r"\begin{longtable}{@{}>{\raggedright\arraybackslash}p{3.1cm}>{\raggedright\arraybackslash}p{1.3cm}p{0.5cm}p{2.9cm}p{2.9cm}p{2.9cm}@{}}",
            rf"\caption{{Calibration across the three evaluation horizons in {label}.}}\label{{tab:calibration-all-{cohort}}}\\",
            r"\toprule Model & \shortstack[l]{Time\\quantile} & $n$ & \shortstack[l]{Calibration\\in-the-large} & Intercept & Slope \\\midrule\endfirsthead",
            r"\multicolumn{6}{l}{\tablename\ \thetable\ (continued)}\\",
            r"\toprule Model & \shortstack[l]{Time\\quantile} & $n$ & \shortstack[l]{Calibration\\in-the-large} & Intercept & Slope \\\midrule\endhead",
            r"\midrule\multicolumn{6}{r}{Continued on next page}\\\endfoot",
            r"\bottomrule\endlastfoot",
        ])
        for model, model_label in MODELS.items():
            for horizon, percentile in enumerate(("25th", "50th", "75th"), 1):
                values = []
                for parameter in ("calibration_in_the_large", "intercept", "slope"):
                    row = lookup[(cohort, model, horizon, parameter)]
                    values.append(f"{float(row['mean']):.3f} ({float(row['standard_deviation']):.3f})")
                count = lookup[(cohort, model, horizon, "slope")]["n_folds"]
                lines.append(" & ".join([model_label, percentile, count, *values]) + r" \\")
        lines.extend([
            r"\end{longtable}",
            r"\noindent Horizon is the percentile of event times within each training fold. Entries are fold means (sample SD).\par\endgroup",
        ])
    (ROOT / "tables/table_calibration_all_horizons.tex").write_text("\n".join(lines) + "\n")


def render_secondary() -> None:
    """Display every saved secondary Bayesian--comparator IBS contrast."""
    rows = verified_rows("report_summaries", "secondary_benchmarks.csv")
    if len(rows) != 27:
        raise ValueError("Expected 27 secondary contrasts")
    labels = {
        "Bayesian Cox (normal)": "Normal",
        "Bayesian Cox (horseshoe)": "Horseshoe",
        "Bayesian Cox (spike-slab)": "Spike-and-slab",
        "Bayesian Cox (spike_slab)": "Spike-and-slab",
        "Cox PH": "CoxPH",
        "Random Survival Forest": "RSF",
        "DeepSurv": "DeepSurv",
    }
    lines = [
        r"\begingroup\singlespacing\small",
        r"\begin{longtable}{@{}lllr r r@{}}",
        r"\caption{Complete secondary IBS contrasts between Bayesian and comparator models.}\label{tab:full-secondary}\\",
        r"\toprule Cohort & Prior & Comparator & Pairs & $\Delta$IBS & 95\% interval\\\midrule\endfirsthead",
        r"\multicolumn{6}{l}{\tablename\ \thetable\ (continued)}\\",
        r"\toprule Cohort & Prior & Comparator & Pairs & $\Delta$IBS & 95\% interval\\\midrule\endhead",
        r"\midrule\multicolumn{6}{r}{Continued on next page}\\\endfoot",
        r"\bottomrule\endlastfoot",
    ]
    for row in rows:
        if row["mean_difference"]:
            effect = f"{float(row['mean_difference']):+.6f}"
            interval = f"[{float(row['confidence_lower']):+.6f}, {float(row['confidence_upper']):+.6f}]"
        else:
            effect = interval = "--"
        lines.append(" & ".join([
            COHORTS[row["dataset"]], labels[row["model_a"]], labels[row["model_b"]],
            row["n_paired_folds"] + "/" + row["expected_paired_folds"], effect, interval,
        ]) + r" \\")
    lines.extend([r"\end{longtable}", r"\noindent Inference uses 25 matched folds. A dash identifies a contrast with partial coverage.\par\endgroup"])
    (ROOT / "tables/table_secondary_complete.tex").write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    (ROOT / "tables").mkdir(exist_ok=True)
    render_calibration()
    render_secondary()
