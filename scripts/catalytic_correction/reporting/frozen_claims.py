"""Read-only factual counts for the completed post-hoc extension evidence.

This is a summary of hash-bound stored records, not a scientific verifier,
visual reviewer, new hypothesis test, or programme-completion certificate.
It refuses partial numerical, reproduction, rendering, and visual-QA inputs.
Only stdout is written; no result, receipt, source file, or fitted cell changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

PRODUCTION_COMMIT = "119476fef55b1eeb690527f234c1423440720d45"
ANALYSIS_COMMIT = "8551d326b02bfe88915cfd9eb50c6ca8e5690e3a"
RENDERER_SHA256 = "2155dbe1e1f54603f3711deadd79c6e1aed3917b07a3fe8e58e08f4a6ad85cd2"
QA_HELPER_SHA256 = "f56cf8149bf6a97848e6bf212449c5980c9c65059abb7f0543a285c7d920c7c0"
ANALYSIS_ONLY_HASHES = {
    "src/pipelines/extensions/verification.py": "cce2909369ade51d442d30d16fccf2bed3476a9666598e41d91a716a0d4ad0fd",
    "scripts/finalize_extensions.py": "d6b53c7ee23fccc90e773cb47b4d40048fe00bd1240a23ce78c827d8f8cd6feb",
    "scripts/render_extensions.py": RENDERER_SHA256,
}
EXPLANATION_SHA256 = "120984c7edfac468f471b9f500470623689b2647e4bde56d271cc9623346ecd5"
BASELINE_PINS = {
    "primary": (
        "2a1817365675aa179174b5edf5b3da67bbcb2be1b2eb4143347e4b295052ce02",
        "44d5d6e2c3cf4d0350c3bc8cb27291436c9934b219c4c895cb139525e6fa25f6",
    ),
    "sampler": (
        "76acf071cf41f5456538799625979775ad00a5ab699b55b88987fee7ed6c5d00",
        "0684ca1e61ef8492f27c79f486ea8e57cc75e139808f9a15535f426e82d4833a",
    ),
    "robustness": (
        "0fc556b803da4f37daa9a63dbddc5ce5ffd350aa2b2831b0a6546b634c36139f",
        "8f136a6b2f9cf0a18308db71d63a69b1b145b0c767548cc7465d4af73e781152",
    ),
}
FAMILY_SIZES = {
    "penalized_vs_original_priors": 27,
    "calibrated_vs_adr032_horseshoe": 3,
    "catalytic_vs_original_priors": 27,
    "expression_increment": 13,
}
NEW_MODELS = ("ridge", "lasso", "elastic_net", "pv_horseshoe", "catalytic_fixed", "catalytic_adaptive", "catalytic_wme")
ORIGINAL_MODELS = (
    "cox_ph",
    "random_survival_forest",
    "deepsurv",
    "bayesian_normal",
    "bayesian_horseshoe",
    "bayesian_spike_slab",
)
SETTINGS = (
    ("gbsg2", "clinical"),
    ("metabric", "clinical"),
    ("metabric_matched", "clinical"),
    ("metabric_matched", "expression"),
    ("whas500", "clinical"),
)
RQ2_CONDITIONS = ("fraction_0.25", "fraction_0.50", "fraction_0.75", "admin_q0.75", "admin_q0.50")
TABLES = (
    "fold_metrics",
    "decision_curve_points",
    "decision_curve_support",
    "decision_curve_unavailable",
    "paired_families",
    "rq2_effects",
)
ATTESTATION = "I examined every rendered PDF page at full size and the indexed contact sheets."


def require(condition: bool, message: str) -> None:
    """Refuse incomplete or inconsistent stored evidence."""
    if not condition:
        raise ValueError(message)


def digest(path: Path) -> str:
    """Hash an existing regular file in bounded memory."""
    require(path.is_file() and not path.is_symlink(), f"missing or linked file: {path}")
    result = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def read(path: Path):
    """Read JSON without admitting non-standard NaN or infinity literals."""

    def invalid(value):
        raise ValueError(f"non-standard JSON number {value} in {path}")

    return json.loads(path.read_text(encoding="utf-8"), parse_constant=invalid)


def canonical(value) -> str:
    """Mirror the sealed repository's canonical JSON encoding."""
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode(
        "utf-8"
    )
    return hashlib.sha256(payload).hexdigest()


def content(record: dict, field: str) -> None:
    """Check a stored internal content digest."""
    require(
        record.get(field) == canonical({k: v for k, v in record.items() if k != field}),
        f"content digest mismatch: {field}",
    )


def bound(root: Path, relative: str, expected: str) -> Path:
    """Resolve an inventory entry within its root and verify its exact bytes."""
    path = root / relative
    require(path.resolve().is_relative_to(root.resolve()), f"inventory path escapes root: {relative}")
    require(digest(path) == expected, f"changed evidence file: {path}")
    return path


def figure_names() -> list[str]:
    """Return the sealed renderer's 32-name inventory order."""
    names = [f"{d}_{s}_{kind}" for d, s in SETTINGS for kind in ("ibs", "calibration")]
    names += [f"decision_{d}__{s}__h{h}" for d, s in SETTINGS for h in (1, 2, 3)]
    names += [f"paired_{name}" for name in sorted(FAMILY_SIZES)]
    return names + [f"rq2_{d}" for d in ("gbsg2", "whas500", "metabric")]


def load_numerical(run: Path) -> tuple[list[dict], dict, dict]:
    """Require the exact complete, deeply verified numerical record."""
    manifest, completion, verification = (
        read(run / f"{name}.json") for name in ("manifest", "completion", "verification")
    )
    content(manifest, "manifest_content_sha256")
    content(completion, "completion_content_sha256")
    require(
        manifest.get("planned_fits") == 1625 and len(manifest.get("plan", [])) == 1625,
        "incomplete or unexpected manifest plan",
    )
    require(
        manifest.get("code", {}).get("git_commit") == PRODUCTION_COMMIT
        and manifest["code"].get("git_dirty") is False
        and not manifest.get("test_only"),
        "not the sealed clean production programme",
    )
    require(
        manifest.get("evidence_status") == completion.get("evidence_status") == "post_hoc_extension",
        "extension evidence label is missing",
    )
    require(
        completion.get("planned") == completion.get("stored") == 1625 and completion.get("verification") == "deep",
        "numerical programme is incomplete or not deep verified",
    )
    require(completion.get("manifest_sha256") == digest(run / "manifest.json"), "manifest byte binding differs")
    for name, value in verification.items():
        require(completion.get(name) == value, f"verification/completion differs: {name}")
    require(verification.get("verification") == "deep", "verification is not deep")
    require(
        verification.get("production_code_commit") == PRODUCTION_COMMIT
        and verification.get("analysis_only_sha256") == ANALYSIS_ONLY_HASHES,
        "verification does not bind the sealed production/analysis sources",
    )
    planned = {row["cell_id"] for row in manifest["plan"]}
    inventory = completion.get("cell_sha256", {})
    require(len(planned) == len(inventory) == 1625, "cell inventory is incomplete")
    require(
        set(inventory) == {f"cells/{identity}.json" for identity in planned}
        and {p.stem for p in (run / "cells").glob("*.json")} == planned,
        "stored cells differ from plan",
    )
    cells = [read(bound(run, name, sha)) for name, sha in sorted(inventory.items())]
    for cell in cells:
        content(cell, "cell_content_sha256")
        require(cell["status"] in {"complete", "failed", "failed_diagnostics"}, "unrecognized cell outcome")
    counts = dict(Counter(c["status"] for c in cells))
    require(counts == completion.get("status_counts"), "stored status counts differ from completion")
    require(
        verification.get("independently_rescored") == counts.get("complete", 0),
        "deep rescoring count differs from accepted cells",
    )
    aggregates = completion.get("aggregate_sha256", {})
    require(
        set(aggregates) == {"paired_families.json", "rq2_effects.json", "decision_curves.json"},
        "aggregate inventory is incomplete or unexpected",
    )
    for name, sha in aggregates.items():
        bound(run, name, sha)
    return cells, completion, verification


def summarize_cells(cells: list[dict]) -> dict:
    """Separate execution failures from diagnostic rejection in each planned group."""
    groups, failures = defaultdict(list), Counter()
    for cell in cells:
        groups[(cell["dataset"], cell["setting"], cell["model_key"], cell["condition"])].append(cell)
        if cell["status"] == "failed":
            failures[(cell.get("error_type"), cell.get("message"), bool(cell.get("fit_attempts")))] += 1
    rows = [
        {
            "dataset": d,
            "setting": s,
            "model": m,
            "condition": c,
            "planned_stored": len(records),
            "accepted": sum(r["status"] == "complete" for r in records),
            "execution_failures": sum(r["status"] == "failed" for r in records),
            "diagnostic_failures": sum(r["status"] == "failed_diagnostics" for r in records),
        }
        for (d, s, m, c), records in sorted(groups.items())
    ]
    return {
        "status_counts": dict(Counter(c["status"] for c in cells)),
        "groups": rows,
        "execution_error_groups": [
            {"error_type": e, "message": m, "has_recorded_fit_attempts": a, "cells": n}
            for (e, m, a), n in sorted(failures.items(), key=lambda item: repr(item[0]))
        ],
    }


def summarize_families(families: dict) -> dict:
    """Report stored pairing and multiplicity availability without computing tests."""
    require(set(families) == set(FAMILY_SIZES), "unexpected comparison families")
    output = {}
    for name, expected in FAMILY_SIZES.items():
        family, missing = families[name], []
        rows = family["contrasts"]
        require(family["expected_contrasts"] == len(rows) == expected, f"incomplete contrast inventory: {name}")
        for row in rows:
            n = row["n_pairs"]
            require(row["expected_pairs"] == 25 and 0 <= n <= 25, "unexpected paired coverage")
            require(row["status"] == ("estimable" if n == 25 else "incomplete_no_inference"), "pair/status mismatch")
            require(("effect" in row) == (n == 25), "effect is missing or attached to incomplete pairs")
            if n < 25:
                missing.append(
                    {
                        k: row[k]
                        for k in ("dataset", "model", "left", "right", "n_pairs", "expected_pairs", "status")
                        if k in row
                    }
                )
        complete = all(row["status"] == "estimable" for row in rows)
        require(family["family_complete"] is complete, f"family-complete flag mismatch: {name}")
        for row in rows:
            require(
                ("holm_adjusted_p" in row) == complete
                and ("holm_reject" in row) == complete
                and ("superiority_language_permitted" in row) == complete,
                "Holm fields contradict family coverage",
            )
        output[name] = {
            "expected_contrasts": expected,
            "estimable_contrasts": expected - len(missing),
            "incomplete_contrasts": missing,
            "missing_fold_pairs": sum(25 - r["n_pairs"] for r in rows),
            "family_complete": complete,
            "stored_holm_reject_count": sum(bool(r["holm_reject"]) for r in rows) if complete else None,
            "stored_superiority_language_permitted_count": sum(bool(r["superiority_language_permitted"]) for r in rows)
            if complete
            else None,
        }
    return output


def summarize_rq2(rows: list[dict]) -> dict:
    """Count direct/interaction pairs and intervals, retaining partial descriptive means."""
    expected = {
        (d, m, p, c, k)
        for d in ("gbsg2", "whas500", "metabric")
        for m in NEW_MODELS[-3:]
        for p in ORIGINAL_MODELS[-3:]
        for c in RQ2_CONDITIONS
        for k in ("direct", "difference_in_differences")
    }
    actual = {(r["dataset"], r["model"], r["prior"], r["condition"], r["kind"]) for r in rows}
    require(len(rows) == 270 and actual == expected, "RQ2 row inventory is incomplete or unexpected")
    for row in rows:
        n = row["n_pairs"]
        require(
            row["expected_pairs"] == 10 and 0 <= n <= 10 and row["role"] == "descriptive_no_significance_claim",
            "RQ2 coverage/role differs",
        )
        require((row["mean_difference"] is None) == (n == 0), "RQ2 unavailable mean differs from pairing")
        require(("corrected_descriptive_interval" in row) == (n == 10), "RQ2 interval attached to partial pairs")
        require(
            "p_value" not in row and "p_value" not in row.get("corrected_descriptive_interval", {}),
            "RQ2 record unexpectedly contains a significance-test p-value",
        )
    return {
        "row_count": len(rows),
        "role": "descriptive_no_significance_claim",
        "full_coverage_rows": sum(r["n_pairs"] == 10 for r in rows),
        "partial_coverage_rows": sum(0 < r["n_pairs"] < 10 for r in rows),
        "zero_pair_rows": sum(r["n_pairs"] == 0 for r in rows),
        "corrected_interval_rows": sum("corrected_descriptive_interval" in r for r in rows),
        "missing_pair_slots": sum(10 - r["n_pairs"] for r in rows),
        "coverage": [
            {k: r[k] for k in ("dataset", "model", "prior", "condition", "kind", "n_pairs", "expected_pairs")}
            for r in rows
        ],
    }


def summarize_dca(groups: dict) -> dict:
    """Retain every specified unavailable model/horizon and its stored reason."""
    expected = {f"{d}__{s}__h{h}" for d, s in SETTINGS for h in (1, 2, 3)}
    require(set(groups) == expected, "decision-curve group inventory is incomplete or unexpected")
    output, exclusions = [], Counter()
    for key, group in sorted(groups.items()):
        dataset = key.split("__")[0]
        models = set(ORIGINAL_MODELS + NEW_MODELS)
        if dataset != "metabric_matched":
            models.add("bayesian_horseshoe_original")
        curves = group.get("curves", {})
        available = set(curves.get("models", {})) - {"all", "none"}
        unavailable = group["unavailable"]
        require(
            not available.intersection(unavailable) and available | set(unavailable) == models,
            f"decision-curve model accounting differs: {key}",
        )
        require(set(group["support"]) == available, f"decision-curve support inventory differs: {key}")
        require(not available or {"all", "none"}.issubset(curves["models"]), "decision defaults are missing")
        require(
            len(group["thresholds"]) == 50 and group["thresholds"][0] == 0.01 and group["thresholds"][-1] == 0.5,
            "decision threshold grid differs",
        )
        for reason in unavailable.values():
            exclusions[reason] += 1
        output.append(
            {
                "group": key,
                "horizon_rule": group["horizon_rule"],
                "specified_models": len(models),
                "available_models": sorted(available),
                "unavailable_models": unavailable,
                "defaults_available": bool(available),
                "conditional_uncertainty": curves.get("uncertainty"),
                "n_patients": curves.get("n_patients"),
                "n_biological_clusters": curves.get("n_biological_clusters"),
                "support_fold_records": {model: len(records) for model, records in group["support"].items()},
            }
        )
    return {
        "groups": output,
        "specified_model_horizon_slots": 204,
        "available_model_horizon_slots": sum(len(r["available_models"]) for r in output),
        "unavailable_model_horizon_slots": sum(len(r["unavailable_models"]) for r in output),
        "exclusion_reason_counts": dict(sorted(exclusions.items())),
        "interpretation": (
            "Exploratory conditional pointwise utility; fold-specific training horizons; no deployment claim."
        ),
    }


def separate_receipts(args, cells: list[dict]) -> dict:
    """Bind selected reproduction and passed rendering/QA records separately."""
    selected = {c["cell_id"]: c for c in cells if c["repeat"] == c["fold"] == 1}
    receipts = {p.stem: p for p in (args.reproduction / "receipts").glob("*.json")}
    require(len(selected) == 92 and set(receipts) == set(selected), "official 92-cell reproduction is incomplete")
    receipt_hashes = {}
    for identity, path in sorted(receipts.items()):
        receipt, refit = read(path), read(args.reproduction / "cells" / f"{identity}.json")
        content(refit, "cell_content_sha256")
        require(
            receipt.get("cell_id") == identity
            and receipt.get("status") == "scientific_match"
            and receipt.get("source_content_sha256") == selected[identity]["cell_content_sha256"]
            and receipt.get("refit_content_sha256") == refit["cell_content_sha256"]
            and receipt.get("trace_sample_arrays") == "exact; timing/NetCDF metadata excluded",
            f"official selected receipt binding differs: {identity}",
        )
        receipt_hashes[identity] = digest(path)
    lineage = read(args.rendered / "lineage.json")
    require(
        lineage.get("evidence_status") == "post_hoc_extension"
        and lineage.get("source_manifest_sha256") == digest(args.run / "manifest.json")
        and lineage.get("source_completion_sha256") == digest(args.run / "completion.json")
        and lineage.get("renderer_sha256") == RENDERER_SHA256,
        "render lineage source binding differs",
    )
    require(
        [r["name"] for r in lineage["figures"]] == figure_names()
        and [r["name"] for r in lineage["tables"]] == list(TABLES),
        "render inventory is incomplete",
    )
    for suffix in ("pdf", "png"):
        require(
            {p.stem for p in args.rendered.glob(f"*.{suffix}")} == set(figure_names()),
            f"actual {suffix} inventory differs from 32 figures",
        )
    require({p.stem for p in args.rendered.glob("*.csv")} == set(TABLES), "actual six-table inventory differs")
    for record in lineage["figures"]:
        for suffix in ("pdf", "png"):
            bound(args.rendered, f"{record['name']}.{suffix}", record[f"{suffix}_sha256"])
    for record in lineage["tables"]:
        bound(args.rendered, f"{record['name']}.csv", record["csv_sha256"])
    inventory = read(args.qa_dir / "qa_inventory.json")
    review, qa = read(args.qa_review), read(args.qa_dir / "visual_qa_receipt.json")
    require(
        inventory.get("status") == "automated_checks_passed_visual_review_pending"
        and inventory.get("figure_count") == 32
        and inventory.get("table_count") == 6
        and [r["name"] for r in inventory["figures"]] == figure_names()
        and inventory["tables"] == lineage["tables"]
        and len(inventory["contact_sheets"]) == 4,
        "automated QA inventory is incomplete or differs from rendering",
    )
    require(
        qa.get("visual_qa_status") == "passed"
        and qa.get("test_only") is False
        and qa.get("figure_count") == 32
        and qa.get("table_count") == 6,
        "final visual QA is incomplete or failed",
    )
    require(
        qa.get("inventory_sha256") == review.get("inventory_sha256") == digest(args.qa_dir / "qa_inventory.json")
        and qa.get("review_sha256") == digest(args.qa_review)
        and qa.get("source_lineage_sha256") == inventory.get("lineage_sha256") == digest(args.rendered / "lineage.json")
        and qa.get("source_run_completion_sha256")
        == inventory.get("run_completion_sha256")
        == digest(args.run / "completion.json")
        and inventory.get("qa_helper_sha256") == QA_HELPER_SHA256
        and inventory.get("renderer_sha256") == RENDERER_SHA256
        and inventory.get("run_manifest_sha256") == digest(args.run / "manifest.json"),
        "visual QA source binding differs",
    )
    require(
        qa.get("attestation") == review.get("attestation") == ATTESTATION
        and qa.get("reviewer_name") == review.get("reviewer_name", "").strip()
        and bool(qa["reviewer_name"]),
        "named review binding differs",
    )
    reviewed_at = datetime.fromisoformat(review["reviewed_at_utc"].replace("Z", "+00:00"))
    require(
        reviewed_at.tzinfo is not None and qa.get("reviewed_at_utc") == reviewed_at.isoformat(),
        "review time binding differs",
    )
    require(
        qa["figures"] == review["figures"]
        and [r["name"] for r in qa["figures"]] == figure_names()
        and all(r["verdict"] == "pass" for r in qa["figures"]),
        "32 actual-review verdicts are incomplete or failed",
    )
    require(
        qa.get("tables") == [{"name": r["name"], "csv_sha256": r["csv_sha256"]} for r in lineage["tables"]],
        "visual QA table receipt differs from exact table bytes",
    )
    for record in inventory["figures"]:
        bound(args.qa_dir, record["page_render"], record["page_render_sha256"])
    for record in inventory["contact_sheets"]:
        bound(args.qa_dir, record["file"], record["sha256"])
    return {
        "official_selected_reproduction_receipts": 92,
        "receipt_sha256": receipt_hashes,
        "render_lineage_sha256": digest(args.rendered / "lineage.json"),
        "visual_qa_receipt_sha256": digest(args.qa_dir / "visual_qa_receipt.json"),
        "visual_qa_status_as_recorded": qa["visual_qa_status"],
        "visual_reviewer_as_recorded": qa["reviewer_name"],
        "scope": (
            "Receipt/content bindings only; this helper does not recompute sampled arrays or perform visual inspection."
        ),
    }


def unchanged_baseline(args) -> dict:
    """Read original negative findings only after checking their frozen pins."""
    completions = {}
    for name, (manifest_sha, completion_sha) in BASELINE_PINS.items():
        root = getattr(args, name)
        bound(root, "manifest.json", manifest_sha)
        completion = read(bound(root, "completion.json", completion_sha))
        completions[name] = completion
        for relative, sha in completion["aggregate_sha256"].items():
            bound(root, relative, sha)
    original = read(args.primary / "inference.json")
    sampler = read(args.sampler / "inference.json")
    primary_cells = [
        read(bound(args.primary, path, sha)) for path, sha in completions["primary"]["all_stored_cell_hashes"].items()
    ]
    require(
        len(primary_cells) == 450
        and dict(Counter(c["status"] for c in primary_cells)) == completions["primary"]["status_counts"],
        "primary cell accounting differs",
    )
    failure_groups = Counter(
        (c["dataset"], c["model_key"], c["status"]) for c in primary_cells if c["status"] != "complete"
    )
    explanation = read(args.explanation)
    require(digest(args.explanation) == EXPLANATION_SHA256, "original explanation bytes changed")
    return {
        "primary_status_counts": completions["primary"]["status_counts"],
        "primary_failure_groups": [
            {"dataset": d, "model": m, "status": s, "cells": n} for (d, m, s), n in sorted(failure_groups.items())
        ],
        "primary_inference_status": original["status"],
        "primary_holm_family_complete": original["holm_family_complete"],
        "primary_pairing": [
            {
                k: r[k]
                for k in ("dataset", "model_a", "model_b", "n_paired_folds", "expected_paired_folds", "status")
                if k in r
            }
            for r in original["primary"]
        ],
        "adr032_status_counts": completions["sampler"]["status_counts"],
        "adr032_holm_family_complete": sampler["holm_family_complete"],
        "adr032_confirmatory_outcome_replaced": sampler["confirmatory_outcome_replaced"],
        "adr032_stored_holm_adjusted_p_values": [r["holm_adjusted_p"] for r in sampler["primary"]],
        "adr032_corrected_intervals_including_zero": sum(
            r["ibs"]["confidence_lower"] <= 0 <= r["ibs"]["confidence_upper"] for r in sampler["primary"]
        ),
        "robustness_status_counts": completions["robustness"]["status_counts"],
        "original_explanation_sha256": EXPLANATION_SHA256,
        "original_explanation_comparisons": len(explanation["comparisons"]),
        "original_explanation_convergence_summary": explanation["convergence"]["summary"],
        "boundary": (
            "Original primary failures, unavailable primary contrasts, and failed RQ3 claim gate remain unchanged."
        ),
    }


def main() -> None:
    """Emit a factual summary only after all stored pre-transfer claim inputs exist."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "run",
        "reproduction",
        "rendered",
        "qa-dir",
        "qa-review",
        "primary",
        "sampler",
        "robustness",
        "explanation",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    cells, completion, verification = load_numerical(args.run)
    result = {
        "schema_version": 1,
        "evidence_status": "post_hoc_extension",
        "summary_role": "factual stored claim-input counts; no newly computed inference",
        "overall_programme_completion": (
            "not_assessed; publication, transfer, fresh scientific restore and task closure remain root-owned"
        ),
        "production_code_commit": PRODUCTION_COMMIT,
        "analysis_code_commit": ANALYSIS_COMMIT,
        "source_manifest_sha256": digest(args.run / "manifest.json"),
        "source_completion_sha256": digest(args.run / "completion.json"),
        "source_verification_sha256": digest(args.run / "verification.json"),
        "aggregate_sha256": completion["aggregate_sha256"],
        "stored_verification": verification,
        "sealed_completion_later_stage_fields": {
            k: completion[k] for k in ("selected_reproduction_status", "render_status")
        },
        "cell_accounting": summarize_cells(cells),
        "comparison_families": summarize_families(read(args.run / "paired_families.json")),
        "rq2": summarize_rq2(read(args.run / "rq2_effects.json")),
        "decision_curves": summarize_dca(read(args.run / "decision_curves.json")),
        "separate_receipts": separate_receipts(args, cells),
        "unchanged_baseline": unchanged_baseline(args),
    }
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, TypeError, OSError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        sys.exit(2)
