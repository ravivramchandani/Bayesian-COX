"""Check incomplete-family bounds against explicit hypothetical completions."""

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
    missing = 2
    bounds = incomplete_holm_bounds(_primary(p_values, missing))
    by_model = {row.model_a: row for row in bounds.itertuples(index=False)}
    for completion in product([0.0, 0.003, 0.018, 0.2, 1.0], repeat=missing):
        adjusted, rejected = holm_adjust(p_values + list(completion))
        for index in range(len(p_values)):
            row = by_model[f"prior{index}"]
            assert row.best_case_adjusted_p_bound <= adjusted[index] + 1e-15
            assert adjusted[index] <= row.worst_case_adjusted_p_bound + 1e-15
            assert not rejected[index] or row.rejection_possible
            assert not row.rejection_guaranteed or rejected[index]


def test_no_available_rejection_for_observed_minimum_p() -> None:
    bounds = incomplete_holm_bounds(_primary([0.4934248731, 0.693, 0.732, 0.760, 0.833], 4))
    assert not bounds.rejection_possible.any()
    assert not bounds.rejection_guaranteed.any()


def test_renderer_retains_unavailable_contrasts() -> None:
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
    rows = _paired_ibs_rows(SimpleNamespace(inference={"primary": primary}))
    assert len(rows) == 1
    assert rows.mean_ibs_difference.isna().all()
    assert rows.status.iloc[0] == "incomplete_no_confirmatory_inference"


def test_failed_explanation_gate_is_explicit_in_rendered_package(tmp_path: Path) -> None:
    result = {"convergence": {"summary": {"status": "failed"}}}
    registry = OutputRegistry(tmp_path, SimpleNamespace())
    _render_explanation(result, {"artifact": "fixture", "sha256": "0" * 64}, registry)
    notice = (tmp_path / "EXPLANATION_GATE_NOTICE.txt").read_text()
    assert "gate failed" in notice
    assert "No RQ3" in notice
    assert any(row["path"] == "EXPLANATION_GATE_NOTICE.txt" for row in registry.outputs)


def test_renderer_rejects_source_change_during_a_render(tmp_path: Path, monkeypatch) -> None:
    script = tmp_path / "scripts/render_confirmatory.py"
    script.parent.mkdir()
    script.write_text("original\n")
    monkeypatch.setattr("src.rendering.outputs.PROJECT_ROOT", tmp_path)
    registry = OutputRegistry(tmp_path / "outputs", SimpleNamespace())
    script.write_text("changed\n")
    with pytest.raises(RuntimeError, match="source changed during rendering"):
        registry.write_lineage(optional_sources=[], renderer_path=script)


def test_rendering_package_has_no_model_or_pipeline_import_or_fit_call() -> None:
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
