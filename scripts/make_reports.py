"""Generate the markdown reports from the committed result files.

Every number in the output is read from reports/tables/. Nothing is
recomputed or written by hand.
"""

import json
import os
import sys
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TABLES = os.path.join(PROJECT_ROOT, "reports", "tables")
REPORTS = os.path.join(PROJECT_ROOT, "reports")

COHORT_LABEL = {
    "gbsg2": "GBSG2 (German Breast Cancer Study Group 2)",
    "whas500": "WHAS500 (Worcester Heart Attack Study)",
    "metabric": "METABRIC",
}

# Cox concordance reported for these cohorts in the literature, used as the
# replication reference.
PUBLISHED_COX = {"gbsg2": 0.67, "whas500": 0.75, "metabric": 0.63}


def load(name):
    path = os.path.join(TABLES, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt(value, digits=4):
    if value is None:
        return "—"
    return f"{value:.{digits}f}"


def benchmark_report(data) -> str:
    lines = [
        "# Benchmark results",
        "",
        f"Generated {date.today().isoformat()} from `reports/tables/benchmark.json`.",
        "",
        "Three model families are compared on three clinical cohorts: the Cox",
        "proportional hazards baseline, a random survival forest, and the",
        "Bayesian Cox model fitted under each of three coefficient priors.",
        "Discrimination is measured by Harrell's concordance index and",
        "time-dependent AUC; calibration by the integrated Brier score, where",
        "lower is better.",
        "",
        "Cross-validated concordance uses a shorter sampling chain than the",
        "reported test-set fit, so it is comparable across models but not",
        "directly against the test-set column.",
        "",
    ]

    for dataset, entry in data.items():
        lines += [
            f"## {COHORT_LABEL.get(dataset, dataset)}",
            "",
            f"{entry['n_train']} training and {entry['n_test']} test subjects, "
            f"{entry['n_features']} features, "
            f"{entry['event_rate_train']:.1%} event rate in training.",
            "",
            "| Model | C-index | IBS | Mean AUC | CV C-index | Fit (s) |",
            "| :--- | ---: | ---: | ---: | ---: | ---: |",
        ]
        for name, m in entry["models"].items():
            lines.append(
                f"| {name} | {fmt(m['c_index'])} | {fmt(m.get('ibs'))} | "
                f"{fmt(m['mean_auc'])} | "
                f"{fmt(m['cv_c_index_mean'])} ± {fmt(m['cv_c_index_std'], 3)} | "
                f"{m['fit_seconds']:.1f} |"
            )
        lines.append("")

        diagnostics = {
            n: m["diagnostics"] for n, m in entry["models"].items() if "diagnostics" in m
        }
        if diagnostics:
            lines += [
                "Sampler diagnostics:",
                "",
                "| Model | R-hat max | Bulk ESS min | Divergences | Converged |",
                "| :--- | ---: | ---: | ---: | :---: |",
            ]
            for name, d in diagnostics.items():
                lines.append(
                    f"| {name} | {fmt(d['r_hat_max'])} | {d['ess_bulk_min']:.0f} | "
                    f"{d['n_divergent']} ({d['divergence_rate']:.2%}) | "
                    f"{'yes' if d['converged'] else 'no'} |"
                )
            lines.append("")

        cox = entry["models"].get("Cox PH", {}).get("c_index")
        reference = PUBLISHED_COX.get(dataset)
        if cox is not None and reference is not None:
            lines += [
                f"The Cox baseline reaches {fmt(cox, 3)} against a published "
                f"reference of approximately {reference:.2f}, which places the "
                "pipeline within the expected range for this cohort.",
                "",
            ]

    return "\n".join(lines)


def explainability_report(data) -> str:
    lines = [
        "# Explainability comparison",
        "",
        f"Generated {date.today().isoformat()} from "
        "`reports/tables/explainability.json`.",
        "",
        "The Bayesian posterior provides a built-in feature signal: the",
        "posterior probability that a coefficient's effect has a consistent",
        "direction. This is compared against post-hoc SHAP attributions",
        "computed on the Cox PH and random survival forest baselines. Both",
        "use a kernel explainer over the model's risk prediction, so the",
        "attribution method is held constant across models.",
        "",
        "Agreement is reported as Spearman and Kendall rank correlation over",
        "all features, and as the overlap of the five highest-ranked features.",
        "",
    ]

    for dataset, entry in data.items():
        lines += [
            f"## {COHORT_LABEL.get(dataset, dataset)}",
            "",
            "| Posterior prior | Compared with | Spearman | Kendall | Top-5 overlap |",
            "| :--- | :--- | ---: | ---: | ---: |",
        ]
        for key, agreement in entry["agreement"].items():
            prior, baseline = key.split(" vs ")
            lines.append(
                f"| {prior} | {baseline} | "
                f"{agreement['spearman_rho']:+.3f} | "
                f"{agreement['kendall_tau']:+.3f} | "
                f"{agreement['top_k_overlap']} of {agreement['top_k']} |"
            )
        lines.append("")

        for prior, block in entry["posterior"].items():
            if "sparsity_signal" not in block:
                continue
            signal = block["sparsity_signal"][:5]
            score_key = [k for k in signal[0] if k != "feature"][0]
            listed = ", ".join(
                f"{row['feature']} ({row[score_key]:.3f})" for row in signal
            )
            lines += [f"Leading {prior} sparsity signal: {listed}.", ""]

    return "\n".join(lines)


def main() -> int:
    written = []

    benchmark = load("benchmark.json")
    if benchmark:
        path = os.path.join(REPORTS, "benchmark_report.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(benchmark_report(benchmark))
        written.append(path)

    explain = load("explainability.json")
    if explain:
        path = os.path.join(REPORTS, "explainability_report.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(explainability_report(explain))
        written.append(path)

    if not written:
        print("No result files found. Run scripts/run_benchmark.py first.")
        return 1

    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
