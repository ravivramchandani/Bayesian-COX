"""Check incomplete-family bounds against explicit hypothetical completions.

Protects ``incomplete_holm_bounds`` in ``src/rendering/holm_bounds.py``, the
ADR-033 post-hoc bound on a Holm family with missing p-values, by comparing it
with ``holm_adjust`` over enumerated completions. The other tests check that the
``src/rendering`` package keeps unavailable contrasts and failed explanation
gates for RQ3 (the explanation research question) explicit, refuses a source
change during a render, and imports no model or pipeline code (INV-007).
"""

from __future__ import annotations

import ast
from itertools import product
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.rendering.holm_bounds import incomplete_holm_bounds
from src.rendering.metrics import _paired_ibs_rows
from src.rendering.outputs import OutputRegistry
from src.rendering.supplemental import _render_explanation
from src.statistics.hypothesis_tests import holm_adjust


def _primary(p_values: list[float], missing: int) -> list[dict]:
    """Return primary contrasts with the given p-values followed by unestimated ones.

    Args:
        p_values: Available IBS (integrated Brier score) p-values; contrast ``i``
            is named ``prior{i}``.
        missing: Number of contrasts without an ``ibs`` record, as for a family
            with non-estimable contrasts.
    """
    return [
        {
            "dataset": "cohort",
            "model_a": f"prior{index}",
            "model_b": "reference",
            "ibs": {"p_value": value},
        }
        for index, value in enumerate(p_values)
    ] + [
        {"dataset": "cohort", "model_a": f"missing{index}", "model_b": "reference"}
        for index in range(missing)
    ]


@pytest.mark.parametrize("p_values", [[0.001, 0.03], [0.03, 0.001], [0.02, 0.8], [0.0, 1.0]])
def test_bounds_contain_every_enumerated_completion(p_values: list[float]) -> None:
    """Holm results for every enumerated completion lie within the two bounds (ADR-033)."""
    # Holm step-down over m p-values sorted ascending: the k-th is adjusted to
    # max_{j <= k} (m - j + 1) p_(j), capped at 1, and rejected when at most alpha.
    # Missing p-values of 0 rank first (best case); missing p-values of 1 rank
    # last (worst case). The parameter cases include reversed input order and the
    # boundary values 0 and 1.
    missing = 2
    bounds = incomplete_holm_bounds(_primary(p_values, missing))
    by_model = {row.model_a: row for row in bounds.itertuples(index=False)}
    # Candidate missing p-values include both extremes the bounds assume; the
    # 1e-15 slack absorbs rounding differences between the two implementations.
    for completion in product([0.0, 0.003, 0.018, 0.2, 1.0], repeat=missing):
        adjusted, rejected = holm_adjust(p_values + list(completion))
        for index in range(len(p_values)):
            row = by_model[f"prior{index}"]
            assert row.best_case_adjusted_p_bound <= adjusted[index] + 1e-15
            assert adjusted[index] <= row.worst_case_adjusted_p_bound + 1e-15
            assert not rejected[index] or row.rejection_possible
            assert not row.rejection_guaranteed or rejected[index]


def test_no_available_rejection_for_observed_minimum_p() -> None:
    """Five p-values from 0.493 upwards with four missing allow no rejection (ADR-033)."""
    # Even in the best case the smallest p-value is multiplied by the five
    # available hypotheses, giving 1 after capping, far above 0.05.
    bounds = incomplete_holm_bounds(_primary([0.4934248731, 0.693, 0.732, 0.760, 0.833], 4))
    assert not bounds.rejection_possible.any()
    assert not bounds.rejection_guaranteed.any()


def test_renderer_retains_unavailable_contrasts() -> None:
    """A contrast with no IBS estimate stays in the contrast table with its status (INV-007)."""
    primary = [
        {
            "dataset": "cohort",
            "model_a": "horseshoe",
            "model_b": "normal",
            "contrast_direction": "A minus B",
            "n_paired_folds": 7,
            "status": "incomplete_no_confirmatory_inference",
        }
    ]
    # SimpleNamespace stands in for a verified FrozenRun; only its inference is read.
    rows = _paired_ibs_rows(SimpleNamespace(inference={"primary": primary}))
    assert len(rows) == 1
    assert rows.mean_ibs_difference.isna().all()
    assert rows.status.iloc[0] == "incomplete_no_confirmatory_inference"


def test_failed_explanation_gate_is_explicit_in_rendered_package(tmp_path: Path) -> None:
    """A failed explanation gate adds a registered notice that bars RQ3 claims (INV-007)."""
    # A result holding only a failed convergence summary; this rendering path never
    # reads the registry's run, so an empty stand-in suffices.
    result = {"convergence": {"summary": {"status": "failed"}}}
    registry = OutputRegistry(tmp_path, SimpleNamespace())
    _render_explanation(result, {"artifact": "fixture", "sha256": "0" * 64}, registry)
    notice = (tmp_path / "EXPLANATION_GATE_NOTICE.txt").read_text()
    assert "gate failed" in notice
    assert "No RQ3" in notice
    assert any(row["path"] == "EXPLANATION_GATE_NOTICE.txt" for row in registry.outputs)


def test_renderer_rejects_source_change_during_a_render(tmp_path: Path, monkeypatch) -> None:
    """Lineage is not written if renderer source changed after the registry hashed it (INV-007)."""
    # A stand-in project root, so the hashed entry script can be edited safely.
    script = tmp_path / "scripts/render_confirmatory.py"
    script.parent.mkdir()
    script.write_text("original\n")
    monkeypatch.setattr("src.rendering.outputs.PROJECT_ROOT", tmp_path)
    registry = OutputRegistry(tmp_path / "outputs", SimpleNamespace())
    # The registry hashed the script when it was created; this edit mimics a code
    # change part-way through a render.
    script.write_text("changed\n")
    with pytest.raises(RuntimeError, match="source changed during rendering"):
        registry.write_lineage(optional_sources=[], renderer_path=script)


def test_rendering_package_has_no_model_or_pipeline_import_or_fit_call() -> None:
    """No ``src/rendering`` module imports model or pipeline code or calls a ``fit`` method."""
    root = Path(__file__).resolve().parents[1] / "src/rendering"
    for path in root.glob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith(("src.models", "src.pipelines")), path
            elif isinstance(node, ast.Import):
                assert not any(
                    alias.name.startswith(("src.models", "src.pipelines")) for alias in node.names
                ), path
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert node.func.attr != "fit", path
