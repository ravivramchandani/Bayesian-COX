"""Protect refit checkpoints from stale code, corrupted cells and source writes.

Covers the checkpoint, resume and output checks of
``scripts/reproduce_confirmatory_cells.py``, which refits frozen confirmatory
cells with the current code and compares every stored field except wall-clock
timings. Each test uses the toy two-cell source run built by ``_make_run`` in
``tests/test_confirmatory_rendering.py`` and a temporary project root; no model
is fitted. The checks keep frozen evidence and current refits apart (INV-008).
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.utils.io import write_json_atomic
from src.utils.reproducibility import canonical_json_hash
from tests.test_confirmatory_rendering import _make_run


@pytest.fixture
def driver(tmp_path, monkeypatch):
    """Load the reproduction script with its project root moved to a temporary copy."""
    path = Path(__file__).resolve().parents[1] / "scripts/reproduce_confirmatory_cells.py"
    spec = importlib.util.spec_from_file_location("reproduction_driver_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # With PROJECT_ROOT and __file__ pointing at this temporary root, the
    # recorded code identity covers only ``src/fit.py`` and the copied script,
    # so a test can change the code by editing ``src/fit.py``.
    root = tmp_path / "code"
    (root / "src").mkdir(parents=True)
    (root / "src/fit.py").write_text("original\n")
    script = root / "scripts/reproduce_confirmatory_cells.py"
    script.parent.mkdir()
    script.write_bytes(path.read_bytes())
    monkeypatch.setattr(module, "PROJECT_ROOT", root)
    monkeypatch.setattr(module, "__file__", str(script))
    (root / "config").mkdir()
    # JSON is valid YAML; this is the protocol that ``_make_run`` records.
    write_json_atomic(
        root / "config/confirmatory.yaml", {"design_status": "frozen_after_rehearsal"}
    )
    # The toy run records an empty dependency set and has no Git checkpoint, so
    # the environment probe and the frozen-evidence check are replaced.
    monkeypatch.setattr("src.utils.reproducibility.dependency_versions", lambda: {})
    monkeypatch.setattr("src.utils.frozen_evidence.verify_frozen_evidence", lambda *args: {})
    return module


def test_verified_resume_reuses_only_original_code_and_selection(driver, tmp_path):
    """A checkpoint is resumed only with unchanged code and an unchanged cell selection (INV-008)."""
    run = _make_run(tmp_path / "source")
    keep = tmp_path / "refits"
    keys = [("toy", "cox_ph", 1, 1)]
    initial = driver.prepare_reproduction_checkpoint(run, keys, keep, resume=False)
    assert driver.prepare_reproduction_checkpoint(run, keys, keep, resume=True) == initial
    with pytest.raises(RuntimeError, match="selection changed"):
        driver.prepare_reproduction_checkpoint(
            run, [("toy", "bayesian_normal", 1, 1)], keep, resume=True
        )
    (driver.PROJECT_ROOT / "src/fit.py").write_text("altered\n")
    with pytest.raises(RuntimeError, match="code, source evidence"):
        driver.prepare_reproduction_checkpoint(run, keys, keep, resume=True)
    # The same edit is caught by the final check if it happens while cells refit.
    with pytest.raises(RuntimeError, match="source code changed"):
        driver.verify_reproduction_inputs(initial, run)


def test_changed_environment_is_rejected_before_resume(driver, tmp_path, monkeypatch):
    """Dependency versions that differ from the source run's environment are refused (ADR-026)."""
    run = _make_run(tmp_path / "source")
    keep = tmp_path / "refits"
    keys = [("toy", "cox_ph", 1, 1)]
    driver.prepare_reproduction_checkpoint(run, keys, keep, resume=False)
    monkeypatch.setattr(
        "src.utils.reproducibility.dependency_versions", lambda: {"numpy": "changed"}
    )
    with pytest.raises(RuntimeError, match="environment"):
        driver.prepare_reproduction_checkpoint(run, keys, keep, resume=True)


def test_corrupted_original_evidence_is_rejected_before_resume(driver, tmp_path):
    """A stored source cell whose bytes no longer match its recorded hash is refused (INV-008)."""
    run = _make_run(tmp_path / "source")
    keep = tmp_path / "refits"
    keys = [("toy", "cox_ph", 1, 1)]
    driver.prepare_reproduction_checkpoint(run, keys, keep, resume=False)
    original = driver.stored_cell_path(run, *keys[0])
    original.write_text(original.read_text() + " ")
    with pytest.raises(RuntimeError, match="file hash"):
        driver.prepare_reproduction_checkpoint(run, keys, keep, resume=True)


def test_saved_refit_has_valid_content_hash_and_can_only_ignore_timings(driver, tmp_path):
    """A saved refit must pass its own content hash, and only timing fields may differ (INV-008)."""
    run = _make_run(tmp_path / "source")
    key = ("toy", "cox_ph", 1, 1)
    # A re-hashed copy of the stored cell that differs only in wall-clock time.
    refit = json.loads(driver.stored_cell_path(run, *key).read_text())
    refit["total_seconds"] = 99.0
    refit.pop("cell_content_sha256")
    refit["cell_content_sha256"] = canonical_json_hash(refit)
    saved = tmp_path / "refit.json"
    write_json_atomic(saved, refit)
    assert driver.check_saved_refit(run, saved, key)["identical"]
    # Changing the integrated Brier score (IBS) without re-hashing breaks the
    # saved cell's own hash.
    refit["metrics"]["ibs"] += 0.1
    write_json_atomic(saved, refit)
    with pytest.raises(RuntimeError, match="cell hash is invalid"):
        driver.check_saved_refit(run, saved, key)
    # Once re-hashed, the same change is reported as a real difference.
    refit.pop("cell_content_sha256")
    refit["cell_content_sha256"] = canonical_json_hash(refit)
    write_json_atomic(saved, refit)
    assert not driver.check_saved_refit(run, saved, key)["identical"]


def test_saved_refit_layout_matches_write_resume_and_verification(driver, tmp_path, monkeypatch):
    """A refit is saved under --keep-cells at the path that resume verification reads."""
    run = _make_run(tmp_path / "source")
    key = ("toy", "cox_ph", 1, 1)
    keep = tmp_path / "refits"
    original = json.loads(driver.stored_cell_path(run, *key).read_text())
    # Stand in for fitting: the "refit" is the stored cell itself.
    monkeypatch.setattr(driver, "refit_cell", lambda *args: original)
    driver.prepare_reproduction_checkpoint(run, [key], keep, resume=False)
    assert driver.check_cell(run, key, keep)["identical"]
    saved = driver.saved_refit_path(keep, *key)
    assert saved.is_file()
    assert saved == keep / "toy/repeat_01_fold_01/cox_ph.json"
    assert driver.check_saved_refit(run, saved, key)["identical"]


@pytest.mark.parametrize("destination", ["keep_cells", "report"])
def test_cli_refuses_to_write_inside_original_evidence(driver, tmp_path, monkeypatch, destination):
    """The command-line entry point refuses refit or report output inside the source run (INV-008)."""
    run = _make_run(tmp_path / "source")
    # Parsed arguments in which only the chosen destination lies inside the run.
    args = SimpleNamespace(
        run_dir=run, selection="all", workers=1, resume=False, keep_cells=None, report=None
    )
    setattr(args, destination, run / "new-output.json")
    monkeypatch.setattr(driver, "parse_args", lambda: args)
    with pytest.raises(ValueError, match="outside the immutable source run"):
        driver.main()


def test_resume_requires_original_checkpoint_manifest(driver, tmp_path):
    """Resume is refused when the output directory has no original checkpoint record (INV-008)."""
    run = _make_run(tmp_path / "source")
    with pytest.raises(RuntimeError, match="original checkpoint manifest"):
        driver.prepare_reproduction_checkpoint(
            run, [("toy", "cox_ph", 1, 1)], tmp_path / "missing", resume=True
        )
