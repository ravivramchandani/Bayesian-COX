"""Render complete matched posterior tables and exact training-information counts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
from fractions import Fraction
from pathlib import Path

COHORTS = {"gbsg2": "GBSG2", "whas500": "WHAS500", "metabric": "METABRIC"}
PRIORS = {"bayesian_normal": "N", "bayesian_horseshoe": "H", "bayesian_spike_slab": "S"}
COUNTS = {"gbsg2": (8, 7), "whas500": (9, 25), "metabric": (15, 23)}
NAMES = {
    "age": "Age", "estrec": "Oestrogen receptor", "horTh=yes": "Hormonal therapy (yes/no)",
    "menostat=Pre": "Menopause (pre/post)", "pnodes": "Positive nodes",
    "progrec": "Progesterone receptor", "tgrade": "Tumour grade", "tsize": "Tumour size",
    "bmi": "Body mass index", "cvd=1": "Cardiovascular disease (1/0)",
    "diasbp": "Diastolic blood pressure", "gender=1": "Sex (1/0)", "hr": "Heart rate",
    "miord=1": "Infarction order (1/0)", "mitype=1": "Infarction type (1/0)",
    "sysbp": "Systolic blood pressure", "age_at_diagnosis": "Age",
    "cellularity=Low": "Cellularity (low/high)",
    "cellularity=Moderate": "Cellularity (moderate/high)",
    "cellularity=__MISSING__": "Cellularity (missing/high)",
    "er_status=Positive": "ER status (positive/negative)",
    "her2_status=Positive": "HER2 status (positive/negative)",
    "inferred_menopausal_state=Pre": "Menopause (pre/post)",
    "nottingham_prognostic_index": "NPI",
    "pam50_+_claudin-low_subtype=Her2": "Subtype (Her2/Basal)",
    "pam50_+_claudin-low_subtype=LumA": "Subtype (LumA/Basal)",
    "pam50_+_claudin-low_subtype=LumB": "Subtype (LumB/Basal)",
    "pam50_+_claudin-low_subtype=NC": "Subtype (NC/Basal)",
    "pam50_+_claudin-low_subtype=Normal": "Subtype (Normal-like/Basal)",
    "pam50_+_claudin-low_subtype=claudin-low": "Subtype (claudin-low/Basal)",
    "pr_status=Positive": "PR status (positive/negative)",
}


def read_verified(path: Path, expected: str) -> list[dict[str, str]]:
    """Load a CSV only when its exact bytes match the recorded source hash."""
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError(f"Source hash mismatch: {path.name}")
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def add_absolute_means(rows: list[dict[str, str]], folds: list[dict[str, str]]) -> list[dict[str, str]]:
    """Average absolute posterior means before combining folds, checking source agreement."""
    enriched = []
    for row in rows:
        selected = [r for r in folds if all(r[k] == row[k]
                    for k in ("dataset", "feature", "model_key"))]
        identities = {(r["repeat"], r["fold"]) for r in selected}
        values = [float(r["beta_mean"]) for r in selected]
        if len(selected) != int(row["n_matched_folds"]) or len(identities) != len(selected):
            raise ValueError("Incomplete or repeated posterior folds")
        if not math.isclose(statistics.mean(values), float(row["mean_beta"]), abs_tol=1e-12):
            raise ValueError("Fold summaries disagree with aggregate coefficient mean")
        enriched.append({**row, "mean_absolute_beta": str(statistics.mean(abs(x) for x in values))})
    return enriched


def posterior_table(rows: list[dict[str, str]], cohort: str) -> str:
    """Render every consistently coded coefficient, requiring three matched priors."""
    selected = [r for r in rows if r["dataset"] == cohort]
    expected_features, expected_folds = COUNTS[cohort]
    features = sorted({r["feature"] for r in selected})
    keyed = {(r["feature"], r["model_key"]): r for r in selected}
    if (len(features) != expected_features or len(selected) != 3 * expected_features
            or len(keyed) != len(selected)):
        raise ValueError(f"Incomplete or duplicate coefficient coverage: {cohort}")
    for feature in features:
        group = [keyed[(feature, prior)] for prior in PRIORS]
        if any(int(r["n_matched_folds"]) != expected_folds for r in group):
            raise ValueError(f"Unequal matched-fold coverage: {cohort}/{feature}")
        if len({(r["unit"], r["reference"], r["encoding"]) for r in group}) != 1:
            raise ValueError(f"Unmatched coefficient coding: {cohort}/{feature}")
    header = (r"Predictor contrast & Prior & Mean $\beta$ & $|\beta|$ & HR width & Excludes 1 & "
              r"$|\Delta\beta_N|$ & $P(\beta>0)$ & Weight\\")
    lines = [r"\begingroup\singlespacing\footnotesize",
             r"\setlength{\tabcolsep}{3pt}", r"\setlength{\LTcapwidth}{\textwidth}",
             r"\begin{longtable}{@{}>{\raggedright\arraybackslash}p{0.23\textwidth}lrrrrrrr@{}}",
             rf"\caption{{Complete matched-fold posterior comparison for {COHORTS[cohort]}.}}"
             rf"\label{{tab:posterior-all-{cohort}}}\\", r"\toprule", header,
             r"\midrule\endfirsthead", r"\multicolumn{9}{l}{\tablename\ \thetable\ (continued)}\\",
             r"\toprule", header, r"\midrule\endhead", r"\midrule",
             r"\multicolumn{9}{r}{Continued on next page}\\\endfoot",
             r"\bottomrule\endlastfoot"]
    for feature in features:
        for index, (prior, short) in enumerate(PRIORS.items()):
            row = keyed[(feature, prior)]
            probability = float(row["mean_probability_beta_positive"])
            p_text = (r"$>0.999$" if probability > 0.999 else
                      r"$<0.001$" if probability < 0.001 else f"{probability:.3f}")
            weight = row["mean_continuous_mixture_variance_weight"]
            cells = [NAMES[feature] if index == 0 else "", short,
                     f'{float(row["mean_beta"]):.3f}',
                     f'{float(row["mean_absolute_beta"]):.3f}',
                     f'{float(row["mean_hr_interval_width"]):.3f}',
                     f'{row["n_hr_intervals_excluding_one"]}/{expected_folds}',
                     f'{float(row["mean_absolute_beta_difference_from_normal"]):.3f}',
                     p_text, f"{float(weight):.3f}" if weight else "--"]
            lines.append(" & ".join(cells) + (r"\\*" if index < 2 else r"\\[2pt]"))
    lines.extend([r"\end{longtable}", r"\noindent\begin{minipage}{\textwidth}",
                  "N: Normal; H: Horseshoe; S: continuous Spike-and-Slab. "
                  f"Each entry averages {expected_folds} separate accepted fits with equal weight. " +
                  ("Numeric predictors and the ordinal tumour-grade score are expressed per "
                   if cohort == "gbsg2" else "Numeric predictors are expressed per ") +
                  "training-fold standard deviation; categorical contrasts show the level/reference. "
                  "The $|\\beta|$ column averages the absolute posterior coefficient mean in each fold. "
                  "HR width is the mean 95\\% hazard-ratio interval width. Excludes 1 counts those "
                  "intervals excluding unity. $|\\Delta\\beta_N|$ is the mean same-fold absolute "
                  "difference from the Normal posterior mean. Directional probabilities are "
                  "averaged across folds; the weight is the continuous variance-mixture weight "
                  "for S. Comparisons use unrounded values. These summaries do not form a pooled posterior interval.",
                  r"\end{minipage}\endgroup", ""])
    return "\n".join(lines)


def information_rows(primary: list[dict[str, str]], quarter: list[dict[str, str]]) -> list[dict]:
    """Count actual events and encoded columns, retaining each fold's exact ratio."""
    output = []
    for condition, rows, n_folds, n_priors in (("Primary", primary, 25, 1),
                                              ("25\\% training", quarter, 10, 3)):
        for cohort in COHORTS:
            selected = [r for r in rows if r["dataset"] == cohort]
            folded: dict[tuple[int, int], tuple[int, int, int]] = {}
            for row in selected:
                key = (int(row["repeat"]), int(row["fold"]))
                p = int(row.get("p_encoded_covariate_coefficients")
                        or row["n_encoded_preprocessing"])
                values = (int(row["n_train"]), int(row["events_train"]), p)
                if key in folded and folded[key] != values:
                    raise ValueError(f"Unmatched training subset: {cohort}/{key}")
                folded[key] = values
            if len(folded) != n_folds or len(selected) != n_folds * n_priors:
                raise ValueError(f"Incomplete training-fold coverage: {condition}/{cohort}")
            values = list(folded.values())
            ratios = [Fraction(e, p) for _, e, p in values]
            output.append({"condition": condition, "dataset": cohort, "n_folds": n_folds,
                           "n_train": sorted({n for n, _, _ in values}),
                           "events": sorted({e for _, e, _ in values}),
                           "p": sorted({p for _, _, p in values}),
                           "minimum_exact": str(min(ratios)), "maximum_exact": str(max(ratios))})
    return output


def information_table(rows: list[dict]) -> str:
    """Render primary and reduced-training counts with clearly defined denominators."""
    def span(values: list[int]) -> str:
        return str(values[0]) if len(values) == 1 else f"{values[0]}--{values[-1]}"

    lines = [r"\begin{table}[htbp]\centering\begingroup\singlespacing\small",
             r"\setlength{\tabcolsep}{5pt}",
             r"\caption{Observed training events per encoded covariate coefficient.}"
             r"\label{tab:training-information}",
             r"\begin{tabular}{@{}llrrrr@{}}\toprule",
             r"Condition & Cohort & Patients & Events & Coefficients & Events/coefficient\\\midrule"]
    for index, row in enumerate(rows):
        low, high = Fraction(row["minimum_exact"]), Fraction(row["maximum_exact"])
        ratio = f"{float(low):.3f}" + (f"--{float(high):.3f}" if low != high else "")
        p = ", ".join(str(x) for x in row["p"])
        lines.append(" & ".join([row["condition"], COHORTS[row["dataset"]],
                                  span(row["n_train"]), span(row["events"]), p, ratio]) + r"\\")
        if index == 2:
            lines.append(r"\midrule")
    lines.extend([r"\bottomrule\end{tabular}", r"\par\smallskip\begin{minipage}{\textwidth}",
                  "Primary counts cover 25 outer-training folds per cohort; the 25\\% condition "
                  "covers ten nested training subsets per cohort, shared across priors. "
                  "Ratios are computed within each subset before taking their range and are rounded "
                  "to three decimals. Coefficients count encoded covariate columns, including "
                  "categorical contrasts, but exclude baseline hazards and prior hyperparameters. "
                  "They do not measure effective model complexity under shrinkage.",
                  r"\end{minipage}\endgroup\end{table}", ""])
    return "\n".join(lines)


def render(thesis: Path, evidence: Path, output: Path) -> None:
    """Create presentation tables only from hash-matching saved numerical summaries."""
    posterior_dir = thesis / "report_summaries/examiner_polish"
    provenance = json.loads((posterior_dir / "provenance.json").read_text())
    name = "posterior_matched_all_features.csv"
    posterior = read_verified(posterior_dir / name, provenance["outputs"][name])
    fold_name = "posterior_matched_by_fold.csv"
    posterior = add_absolute_means(posterior, read_verified(
        posterior_dir / fold_name, provenance["outputs"][fold_name]))
    pins = json.loads((evidence / "source_hashes.json").read_text())
    primary = read_verified(evidence / "outer_training_epc.csv", pins["outer_training_epc.csv"])
    quarter = read_verified(evidence / "quarter_training_cells_epc.csv",
                            pins["quarter_training_cells_epc.csv"])
    information = information_rows(primary, quarter)
    output.mkdir(parents=True, exist_ok=True)
    for cohort in COHORTS:
        (output / f"table_posterior_all_{cohort}.tex").write_text(posterior_table(posterior, cohort))
    (output / "table_training_information.tex").write_text(information_table(information))
    record = {"fitting_performed": False, "simulation_performed": False,
              "source_hashes": {**pins, name: provenance["outputs"][name],
                                fold_name: provenance["outputs"][fold_name]},
              "information_summary": information,
              "outputs": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(output.glob("*.tex"))}}
    (output / "provenance.json").write_text(json.dumps(record, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--thesis", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render(args.thesis, args.evidence, args.output)
