"""Render separately labelled ADR-032 results after exhaustive evidence checks."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from src.rendering.constants import FIXED_PDF_DATE, PRIOR_DISPLAY_LABELS
from src.utils.io import write_json_atomic
from src.utils.posthoc_evidence import EVIDENCE_STATUS, verify_posthoc_run
from src.utils.reproducibility import canonical_json_hash, sha256_file


def primary_rows(inference: dict) -> pd.DataFrame:
    """Retain all nine contrasts, including any unavailable post-hoc tests."""
    rows = []
    for contrast in inference["primary"]:
        ibs = contrast.get("ibs") or {}
        rows.append(
            {
                "dataset": contrast["dataset"],
                "model_a": contrast["model_a"],
                "model_b": contrast["model_b"],
                "n_paired_folds": contrast["n_paired_folds"],
                "status": contrast.get("status", "complete"),
                "delta_ibs": ibs.get("mean_difference"),
                "lower_95": ibs.get("confidence_lower"),
                "upper_95": ibs.get("confidence_upper"),
                "p_value": ibs.get("p_value"),
                "holm_adjusted_p": contrast.get("holm_adjusted_p"),
                "evidence_status": EVIDENCE_STATUS,
            }
        )
    return pd.DataFrame(rows)


def render(run_dir: Path, source_dir: Path, destination: Path) -> Path:
    """Create CSV, LaTeX and figures from a completed sensitivity only."""
    records = verify_posthoc_run(run_dir, source_dir)
    code_paths = [Path(__file__).resolve()]
    code_paths += sorted((PROJECT_ROOT / "src/rendering").glob("*.py"))
    code_paths += sorted((PROJECT_ROOT / "src/utils").glob("*.py"))
    code_hashes = {str(path.relative_to(PROJECT_ROOT)): sha256_file(path) for path in code_paths}
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"render destination must be empty: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    table = primary_rows(records["inference"])
    table.to_csv(destination / "posthoc_primary_contrasts.csv", index=False)
    compact = pd.DataFrame(
        [
            {
                "Cohort": row.dataset.upper(),
                "Contrast": PRIOR_DISPLAY_LABELS.get(row.model_a, row.model_a)
                + " - "
                + PRIOR_DISPLAY_LABELS.get(row.model_b, row.model_b),
                "Paired folds": row.n_paired_folds,
                "Delta IBS": f"{row.delta_ibs:+.6f}" if pd.notna(row.delta_ibs) else "Unavailable",
                "95% interval": f"[{row.lower_95:+.6f}, {row.upper_95:+.6f}]"
                if pd.notna(row.delta_ibs)
                else "--",
                "p": f"{row.p_value:.3f}" if pd.notna(row.p_value) else "--",
                "Holm p": f"{row.holm_adjusted_p:.3f}" if pd.notna(row.holm_adjusted_p) else "--",
            }
            for row in table.itertuples(index=False)
        ]
    )
    compact.to_latex(destination / "posthoc_primary_contrasts.tex", index=False, escape=True)
    cell_rows = []
    for cell in records["cells"]:
        diagnostics = (cell.get("model_details") or {}).get("diagnostics") or {}
        if not diagnostics and cell["fit_attempts"]:
            diagnostics = cell["fit_attempts"][-1].get("diagnostics") or {}
        cell_rows.append(
            {
                "dataset": cell["dataset"],
                "repeat": cell["repeat"],
                "fold": cell["fold"],
                "status": cell["status"],
                "n_attempts": len(cell["fit_attempts"]),
                "r_hat_max": diagnostics.get("r_hat_max"),
                "ess_bulk_min": diagnostics.get("ess_bulk_min"),
                "ess_tail_min": diagnostics.get("ess_tail_min"),
                "n_divergent": diagnostics.get("n_divergent"),
                "bfmi_min": diagnostics.get("bfmi_min"),
                "evidence_status": EVIDENCE_STATUS,
            }
        )
    pd.DataFrame(cell_rows).to_csv(destination / "posthoc_fit_diagnostics.csv", index=False)
    fig, axis = plt.subplots(figsize=(8.2, 5.0))
    labels = []
    for index, row in enumerate(table.itertuples(index=False)):
        labels.append(
            row.dataset.upper()
            + ": "
            + PRIOR_DISPLAY_LABELS.get(row.model_a, row.model_a)
            + " - "
            + PRIOR_DISPLAY_LABELS.get(row.model_b, row.model_b)
        )
        if pd.notna(row.delta_ibs):
            axis.errorbar(
                row.delta_ibs,
                index,
                xerr=[[row.delta_ibs - row.lower_95], [row.upper_95 - row.delta_ibs]],
                fmt="o",
                color="#265f93",
                capsize=3,
            )
        else:
            axis.text(
                0.02,
                index,
                f"Unavailable ({row.n_paired_folds}/25 paired folds)",
                transform=axis.get_yaxis_transform(),
                color="0.4",
                fontsize=8,
            )
    axis.axvline(0, color="0.5", linewidth=0.8)
    axis.set_yticks(range(len(labels)), labels)
    axis.set_ylim(len(labels) - 0.5, -0.5)
    axis.set_xlabel("Delta IBS (model A minus model B)")
    axis.set_title("Post-hoc sampler sensitivity: target acceptance 0.999", fontsize=10)
    fig.tight_layout()
    fig.savefig(
        destination / "posthoc_ibs_effects.pdf",
        metadata={"CreationDate": FIXED_PDF_DATE, "ModDate": FIXED_PDF_DATE},
    )
    fig.savefig(destination / "posthoc_ibs_effects.png", dpi=240)
    plt.close(fig)
    notice = (
        "POST-HOC SAMPLER SENSITIVITY — ADR-032\n\n"
        "All 75 horseshoe folds were refitted with target acceptance 0.999 on every attempt. "
        "Other models retain their frozen confirmatory cells. The original confirmatory "
        "diagnostic failures and incomplete Holm family are unchanged. These are separate "
        "post-hoc estimates; they do not establish confirmatory superiority or equivalence.\n"
        f"Sensitivity status counts: {records['completion']['status_counts']}\n"
        f"Sensitivity Holm family complete: {records['inference'].get('holm_family_complete')}\n"
    )
    (destination / "POSTHOC_EVIDENCE_NOTICE.txt").write_text(notice)
    verify_posthoc_run(run_dir, source_dir)
    if any(sha256_file(PROJECT_ROOT / name) != digest for name, digest in code_hashes.items()):
        raise RuntimeError("sensitivity renderer source changed during execution")
    lineage = {
        "evidence_status": EVIDENCE_STATUS,
        "source_run": run_dir.name,
        "source_manifest_sha256": sha256_file(run_dir / "manifest.json"),
        "source_completion_sha256": sha256_file(run_dir / "completion.json"),
        "source_inference_sha256": sha256_file(run_dir / "inference.json"),
        "source_cell_sha256": records["completion"]["cell_sha256"],
        "renderer_input_sha256": code_hashes,
        "outputs": {
            path.name: sha256_file(path) for path in sorted(destination.iterdir()) if path.is_file()
        },
    }
    lineage["lineage_content_sha256"] = canonical_json_hash(lineage)
    write_json_atomic(destination / "lineage.json", lineage, overwrite=False)
    return destination


def main() -> int:
    """Parse three explicit directories and render verified results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--source-dir", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    print(
        f"posthoc_rendered_artifact={render(args.run_dir.resolve(), args.source_dir.resolve(), args.output_dir.resolve())}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
