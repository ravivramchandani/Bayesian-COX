"""Tests for the result-blind protocol-freeze decision rule.

Covers ``scripts/freeze_protocol.py`` and ``verify_protocol_freeze`` from
``src/pipelines/confirmatory/provenance.py``. The checks cover the rule that
keeps five outer repeats unless the planned five-repeat runtime exceeds the cap
(ADR-029), the exact rehearsal workload, and the write-once, content-addressed
freeze of every executed input (ADR-022).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from src.pipelines.confirmatory import verify_protocol_freeze

PROJECT_ROOT = Path(__file__).resolve().parents[1]
# The script is not part of an importable package, so load it from its path.
SPEC = importlib.util.spec_from_file_location(
    "freeze_protocol", PROJECT_ROOT / "scripts" / "freeze_protocol.py"
)
assert SPEC is not None and SPEC.loader is not None
FREEZE_PROTOCOL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FREEZE_PROTOCOL)


@pytest.mark.parametrize(
    ("projected_hours", "expected"),
    # A projection of exactly 72 hours is not above the cap and keeps five.
    [(0.0, 5), (71.999, 5), (72.0, 5), (72.001, 3)],
)
def test_repeat_gate_uses_planned_five_repeat_projection(
    projected_hours: float, expected: int
) -> None:
    """Three repeats apply only when the five-repeat projection exceeds the cap (ADR-029)."""
    assert (
        FREEZE_PROTOCOL.required_repeat_decision(
            planned_five_repeat_hours=projected_hours,
            maximum_hours=72.0,
        )
        == expected
    )


@pytest.mark.parametrize(
    "arguments",
    [
        {"planned_five_repeat_hours": -1.0, "maximum_hours": 72.0},
        {"planned_five_repeat_hours": 1.0, "maximum_hours": 0.0},
        {
            "planned_five_repeat_hours": 1.0,
            "maximum_hours": 72.0,
            "planned_repeats": 5,
            "reduced_repeats": 5,
        },
    ],
)
def test_repeat_gate_rejects_invalid_declarations(arguments: dict[str, float]) -> None:
    """A negative projection, a non-positive cap or a reduction that is not smaller is rejected."""
    with pytest.raises(ValueError):
        FREEZE_PROTOCOL.required_repeat_decision(**arguments)


def test_relevant_inputs_freeze_every_local_source_module() -> None:
    """The frozen input list includes every Python module under src/ (ADR-022)."""
    inputs = set(FREEZE_PROTOCOL.relevant_input_files(PROJECT_ROOT, ("gbsg2",)))
    source_modules = {
        str(path.relative_to(PROJECT_ROOT))
        for path in PROJECT_ROOT.glob("src/**/*.py")
        if path.is_file()
    }

    assert source_modules
    assert source_modules <= inputs


def test_protocol_freeze_rejects_a_changed_source_module(tmp_path: Path) -> None:
    """Freeze verification fails once a frozen source module's bytes change (ADR-022)."""
    source = tmp_path / "src" / "module.py"
    source.parent.mkdir(parents=True)
    source.write_text("VALUE = 1\n", encoding="utf-8")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    freeze = {
        "frozen_input_sha256": {
            "src/module.py": FREEZE_PROTOCOL.sha256_file(source)
        },
        "no_comparative_effects_inspected_before_freeze": True,
    }
    freeze["freeze_content_sha256"] = FREEZE_PROTOCOL.canonical_json_hash(freeze)
    (config_dir / "protocol_freeze.json").write_text(
        json.dumps(freeze), encoding="utf-8"
    )

    verify_protocol_freeze(tmp_path, ["src/module.py"])
    source.write_text("VALUE = 2\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="src/module.py"):
        verify_protocol_freeze(tmp_path, ["src/module.py"])


def test_protocol_freeze_is_write_once(tmp_path: Path) -> None:
    """An existing protocol freeze is never overwritten (ADR-022)."""
    output = tmp_path / "protocol_freeze.json"
    record = {"freeze_content_sha256": "f" * 64}

    FREEZE_PROTOCOL.write_protocol_freeze_once(output, record)
    first = output.read_text(encoding="utf-8")

    with pytest.raises(FileExistsError, match="immutable"):
        FREEZE_PROTOCOL.write_protocol_freeze_once(output, {"changed": True})

    assert output.read_text(encoding="utf-8") == first


def test_expected_rehearsal_controls_are_exact() -> None:
    """The expected rehearsal controls equal the exact result-blind workload (ADR-029)."""
    config = {
        "datasets": ["a", "b", "c"],
        "validation": {"outer_splits": 5},
    }

    controls = FREEZE_PROTOCOL.expected_rehearsal_controls(config)

    assert controls == {
        "mode": "rehearsal",
        "datasets": ["a", "b", "c"],
        "models": list(FREEZE_PROTOCOL.MODEL_KEYS),
        "outer_splits": 5,
        "outer_repeats": 1,
        "fold_limit_per_dataset": 1,
        "bayes_draws": 300,
        "bayes_tune": 300,
        "bayes_chains": 2,
        "calibration_bootstraps": 30,
    }
