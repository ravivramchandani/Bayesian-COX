"""Focused release must preserve fixed comparisons and require actual review."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.clinical_methods_release import qa, render
from scripts.clinical_methods_release.common import read_json, sha256_file, write_json_new
from scripts.clinical_methods_release.stage import _same_files, stage_release
from scripts.clinical_methods_release.verify_restored import _same_science, verify_restored
from src.utils.reproducibility import canonical_json_hash


def write_analysis(path: Path, *, incomplete: bool = False) -> None:
    """Create schema-complete but synthetic aggregate fixtures for release gates."""
    path.mkdir()
    rows = []
    for cohort in render.COHORTS:
        for method in render.PENALISED:
            for reference in render.REFERENCES:
                row = {"dataset": cohort, "left": method, "right": reference,
                       "status": "estimable", "n_pairs": 25, "expected_pairs": 25,
                       "horseshoe_reference": "ADR-032 post-hoc sampler" if reference == "bayesian_horseshoe" else None,
                       "effect": {"mean_difference": 0.02, "confidence_lower": -0.01,
                                  "confidence_upper": 0.05, "p_value": 0.3},
                       "holm_adjusted_p": 1.0, "holm_reject": False,
                       "superiority_language_permitted": False}
                rows.append(row)
    if incomplete:
        rows[0]["status"] = "incomplete_no_inference"
        rows[0]["n_pairs"] = 24
        rows[0].pop("effect")
    family = {"schema_version": 1, "evidence_status": "post_hoc_clinical_methods_subset",
              "family_name": "penalized_vs_original_priors", "family_complete": not incomplete,
              "expected_contrasts": 27, "contrasts": rows}
    cell_rows = []
    for cohort in render.COHORTS:
        for model in (*render.PENALISED, *render.REFERENCES):
            for fold in range(1, 26):
                cell_rows.append({"dataset": cohort, "model_key": model,
                                  "source": "synthetic_test", "repeat": (fold - 1) // 5 + 1,
                                  "fold": (fold - 1) % 5 + 1, "status": "complete",
                                  "metrics": {"ibs": 0.2}, "calibration": [],
                                  "cell_seconds": 1.0, "fit_attempts": 1})
    groups = []
    for cohort in render.COHORTS:
        for model in (*render.PENALISED, *render.REFERENCES, "bayesian_horseshoe"):
            source = "original_horseshoe_context" if model == "bayesian_horseshoe" and any(
                r["dataset"] == cohort and r["model_key"] == model for r in groups) else "synthetic_test"
            groups.append({"dataset": cohort, "model_key": model, "source": source,
                           "planned": 25, "accepted": 25,
                           "status_counts": {"complete": 25},
                           "metrics_accepted_only": {"ibs": {"median": 0.2, "q25": 0.2, "q75": 0.2}},
                           "runtime_all_outcomes_seconds": {"median": 1, "available": 25}})
    context = [{"dataset": cohort, "model_key": "bayesian_horseshoe",
                "repeat": (i - 1) // 5 + 1, "fold": (i - 1) % 5 + 1,
                "status": "complete"} for cohort in render.COHORTS for i in range(1, 26)]
    descriptive = {"evidence_status": "post_hoc_clinical_methods_subset",
                   "cell_rows": cell_rows, "original_horseshoe_context": context,
                   "group_rows": groups}
    ledger = {"full_extension_grid_verified": False}
    for name, value in (("paired_families.json", family), ("descriptive.json", descriptive),
                        ("source_ledger.json", ledger)):
        write_json_new(path / name, value)
    completion = {"schema_version": 1, "evidence_status": "post_hoc_clinical_methods_subset",
                  "status": "analysis_complete_release_pending", "full_extension_grid_verified": False,
                  "verified_source_cells": 225, "reference_cells": 225,
                  "original_horseshoe_context_cells": 75,
                  "family_complete": not incomplete,
                  "aggregate_sha256": {name: sha256_file(path / name) for name in
                                       ("paired_families.json", "descriptive.json", "source_ledger.json")}}
    completion["completion_content_sha256"] = canonical_json_hash(completion)
    write_json_new(path / "completion.json", completion)


def test_render_requires_complete_holm_gate_consistency(tmp_path: Path) -> None:
    """A partial 27-family must never carry a corrected rejection."""
    analysis = tmp_path / "analysis"
    write_analysis(analysis, incomplete=True)
    with pytest.raises(ValueError, match="incomplete Holm family"):
        render.render(analysis, tmp_path / "rendered")


def test_render_and_qa_need_named_explicit_review(tmp_path: Path) -> None:
    """Four actual PDFs are inspectable, but preparation alone cannot pass QA."""
    analysis = tmp_path / "analysis"
    rendered = tmp_path / "rendered"
    review_dir = tmp_path / "qa"
    write_analysis(analysis)
    lineage = render.render(analysis, rendered)
    assert [row["name"] for row in lineage["figures"]] == list(qa.FIGURES)
    qa.prepare(analysis, rendered, review_dir)
    with pytest.raises(ValueError, match="missing or linked file"):
        qa.verify_seal(analysis, rendered, review_dir)
    review = read_json(review_dir / "review_template.json")
    review.update({"reviewer": "Synthetic fixture reviewer",
                   "reviewed_at": datetime.now(UTC).isoformat(),
                   "figure_verdicts": dict.fromkeys(qa.FIGURES, "pass"),
                   "claim_checks": dict.fromkeys(qa.CLAIM_CHECKS, "pass")})
    write_json_new(review_dir / "review.json", review)
    qa.seal(analysis, rendered, review_dir)
    assert qa.verify_seal(analysis, rendered, review_dir)["visual_qa_status"] == "passed"
    (review_dir / "page_renders" / "paired_gbsg2.png").write_bytes(b"altered")
    with pytest.raises(ValueError, match="page render differs"):
        qa.verify_seal(analysis, rendered, review_dir)


def test_restored_science_comparison_ignores_only_optional_matched_source() -> None:
    """Clinical replay can omit expression data but no scientific field may drift."""
    original = {"verified_cells": 225, "rescored_cells": 225,
                "matched_source_file_verified": True}
    replay = {**original, "matched_source_file_verified": False}
    _same_science(original, replay)
    replay["rescored_cells"] = 224
    with pytest.raises(ValueError, match="scientific verification differs"):
        _same_science(original, replay)


def test_stage_rejects_an_extra_or_changed_scientific_output(tmp_path: Path) -> None:
    """A replay cannot match a release with extra or altered aggregate bytes."""
    source, repeated = tmp_path / "source", tmp_path / "repeated"
    source.mkdir()
    repeated.mkdir()
    (source / "completion.json").write_text("same")
    (repeated / "completion.json").write_text("same")
    _same_files(source, repeated)
    (source / "extra.json").write_text("unreviewed")
    with pytest.raises(ValueError, match="recomputed scientific output differs"):
        _same_files(source, repeated)


@pytest.mark.parametrize("root_name", (
    "production", "analysis_code", "run", "reproduction", "primary", "sampler",
    "analysed", "rendered", "qa_dir",
))
def test_stage_rejects_output_inside_preserved_input(tmp_path: Path, root_name: str) -> None:
    """Staging cannot write its new transfer tree inside a source or reviewed result."""
    roots = {}
    for name in ("production", "analysis_code", "run", "reproduction", "primary", "sampler",
                 "analysed", "rendered", "qa_dir"):
        roots[name] = tmp_path / name
        roots[name].mkdir()
    verification = tmp_path / "verification.json"
    verification.write_text("{}\n")
    with pytest.raises(ValueError, match=f"inside preserved input root: {root_name}"):
        stage_release(**roots, verification=verification,
                      output=roots[root_name] / "new_stage")


def test_restored_stage_member_tamper_fails_before_scientific_replay(tmp_path: Path) -> None:
    """Restored payload inventory is exact, even for supporting files."""
    restored = tmp_path / "restored"
    restored.mkdir()
    (restored / "study.txt").write_text("source")
    stage = {"schema_version": 1, "evidence_status": "post_hoc_clinical_methods_subset",
             "release_state": "scientifically_verified_and_visually_reviewed_unpublished",
             "full_extension_grid_verified": False, "selected_source_cells": 225,
             "selected_refits": 9, "member_sha256": {"study.txt": sha256_file(restored / "study.txt")}}
    write_json_new(restored / "release_stage.json", stage)
    (restored / "study.txt").write_text("tampered")
    production, primary = (tmp_path / name for name in ("production", "primary"))
    sampler = tmp_path / "programme/sampler_run"
    for path in (production, primary, sampler):
        path.mkdir(parents=True)
    with pytest.raises(ValueError, match="member inventory differs"):
        verify_restored(restored=restored, production=production,
                        analysis_code=Path(__file__).resolve().parents[1],
                        primary=primary, sampler=sampler,
                        report_path=tmp_path / "new-receipt.json")


@pytest.mark.parametrize("root_name", ("production", "analysis_code", "primary", "sampler", "programme"))
def test_restored_replay_receipt_stays_outside_preserved_inputs(tmp_path: Path, root_name: str) -> None:
    """Fresh scientific receipts cannot be written into code or baseline inputs."""
    roots = {name: tmp_path / name for name in ("restored", "production", "analysis_code", "primary")}
    roots["programme"] = tmp_path / "programme"
    roots["sampler"] = roots["programme"] / "sampler_run"
    for path in roots.values():
        path.mkdir(parents=True, exist_ok=True)
    with pytest.raises(ValueError, match=f"outside preserved input: {root_name}"):
        verify_restored(restored=roots["restored"], production=roots["production"],
                        analysis_code=roots["analysis_code"], primary=roots["primary"],
                        sampler=roots["sampler"], report_path=roots[root_name] / "receipt.json")
