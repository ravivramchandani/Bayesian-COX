"""Invented/injected guards only; no actual cohort, generator, SVD or fits."""

from __future__ import annotations

import atexit
import copy
import hashlib
import importlib.util
import inspect
import json
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pandas as pd
import pytest

sys.dont_write_bytecode = True
REPO = Path(__file__).resolve().parents[1]
SUPPORT = REPO / "scripts/catalytic_correction"
HERE = SUPPORT / "reproduction"
PREFLIGHT = SUPPORT / "preflight_core.py"
PRESTAGE = REPO / "tests/fixtures/extensions/prestage_refits_source.txt"
# Read exact historical blobs as fixtures; never import their module top levels.
ORIGINAL_FIXTURE = tempfile.TemporaryDirectory(prefix="original-reproduction-source-")
atexit.register(ORIGINAL_FIXTURE.cleanup)
SOURCE = Path(ORIGINAL_FIXTURE.name).resolve()
for relative in (
    "scripts/reproduce_extensions.py",
    "src/pipelines/extensions/verification.py",
    "src/pipelines/extensions/planning.py",
    "tests/test_extensions.py",
):
    target = SOURCE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(
        subprocess.check_output(
            ["git", "show", "119476fef55b1eeb690527f234c1423440720d45:" + relative], cwd=REPO
        )
    )


def load(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


common = load(SUPPORT / "fit_common.py", "_reproduction_bound_common")
rc = load(HERE / "reproduction_core.py", "_fixture_reproduction_core")
cli = load(HERE / "run_reproduction.py", "_fixture_reproduction_cli")
terminal = load(HERE / "terminal_replay_child.py", "_fixture_terminal_child")
pf = load(PREFLIGHT, "_fixture_reproduction_pf")


def cell_id(index: int, repeat: int = 1, fold: int = 1, model: str = "cox") -> str:
    return f"d{index}__clinical__r{repeat:02d}f{fold:02d}__{model}__full"


def base_selection() -> tuple[Any, Any, Any]:
    ids = [cell_id(i) for i in range(92)]
    pilots = [ids[7], cell_id(93, repeat=2)]
    original = {"plan": [{"cell_id": identity} for identity in [*ids, pilots[1]]]}
    manifest = {"pilot_cells": sorted(pilots)}
    selection = {
        "scope_rule": rc.SCOPE_RULE,
        "original_selected_cells": sorted(ids),
        "pilot_cells": sorted(pilots),
        "selected_cells": sorted(set(ids) | set(pilots)),
    }
    return selection, original, manifest


def write_cell(
    root: Path,
    identity: str,
    *,
    metric: float = 0.6,
    status: str = "complete",
    traces: Any = None,
    seconds: float = 1.0,
    **extra: Any,
) -> Path:
    (root / "cells").mkdir(exist_ok=True)
    value = {
        "cell_id": identity,
        "status": status,
        "metric": metric,
        "seconds": seconds,
        "fit_attempts": [{"status": status, "traces": traces or {}}],
        **extra,
    }
    value["cell_content_sha256"] = common.digest(value)
    path = root / "cells" / f"{identity}.json"
    common.write_new(path, value)
    return path


def comparators(az: Any = None) -> Any:
    return rc.original_comparators(
        SOURCE, np, az or SimpleNamespace(from_netcdf=lambda _: pytest.fail("no traces expected"))
    )


def history(*statuses: str) -> tuple[Any, Any]:
    saved, actual = [], []
    for index, status in enumerate(statuses):
        item = {
            "attempt_index": index,
            "seed": 50 + index,
            "status": status,
            "array_witnesses": {"design": "actual"},
            "constructor_inputs": {"hash": "actual"},
            "actual_metadata": {"processor_metadata": {"state": 7}, "processor_origin": "old"},
            "legacy_metadata": None
            if status != "accepted_original_constructor"
            else {"hash": "accepted"},
            "error": {"type": "builtins.ValueError", "message": "real failure"},
        }
        saved.append(item)
        actual.append(
            {
                **copy.deepcopy(item),
                "actual_metadata": {
                    **item["actual_metadata"],
                    "processor_origin": "normal fitted training",
                },
            }
        )
    accepted = len(statuses) - 1 if statuses[-1] == "accepted_original_constructor" else None
    status = (
        "accepted_original_first_draw"
        if accepted == 0
        else "accepted_rank_conditioned_redraw"
        if accepted is not None
        else "nonrank_failure"
        if statuses[-1] == "nonrank_error"
        else "exhausted_rank_cap"
    )
    return (
        {
            "status": status,
            "accepted_attempt_index": accepted,
            "request": {"input_witness_sha256": "actualinput"},
            "attempts": saved,
        },
        {
            "status": status,
            "accepted_attempt_index": accepted,
            "input_witness_sha256": "actualinput",
            "attempts": actual,
        },
    )


def test_fixed_original92_union_pilots():
    selection, original, manifest = base_selection()
    rc.validate_scope(selection, original, manifest)
    assert len(selection["selected_cells"]) == 93


@pytest.mark.parametrize(
    "change", ["drop", "duplicate", "foreign", "order", "pilot", "count", "grammar"]
)
def test_scope_rejects_changed_recipe(change):
    selection, original, manifest = base_selection()
    if change == "drop":
        selection["selected_cells"].pop()
    elif change == "duplicate":
        selection["selected_cells"].append(selection["selected_cells"][0])
    elif change == "foreign":
        manifest["pilot_cells"] = [cell_id(999)]
    elif change == "order":
        selection["selected_cells"].reverse()
    elif change == "pilot":
        selection["pilot_cells"] = []
    elif change == "count":
        original["plan"].pop(0)
    else:
        original["plan"][0]["cell_id"] = "unknown"
    with pytest.raises(common.InvalidBinding):
        rc.validate_scope(selection, original, manifest)


def test_wme_all_unreached_inner_recipes_required():
    identity = cell_id(1, model="catalytic_wme")
    rows = [
        {"outer_cell_id": identity, "context_id": f"{identity}::{name}"}
        for name in ("outer", "inner_01", "inner_02", "inner_03")
    ]
    assert len(rc.selected_contexts(rows, identity, "catalytic_wme")) == 4
    with pytest.raises(common.InvalidBinding):
        rc.selected_contexts(rows[:-1], identity, "catalytic_wme")


def test_publication_pending_not_whole_grid_reproduction():
    ids = ["a", "b"]
    value = rc.publication_status(
        [
            {"original_cell_id": "a", "status": "terminal_no_fit_recipe_replay"},
            {"original_cell_id": "b", "status": "pending_original_numerical_reproduction"},
        ],
        ids,
    )
    assert (
        value["status"] == "selected_reproduction_pending"
        and value["accounted_selected_cells"] == 1
    )
    assert not value["whole_1625_grid_numerically_reproduced"] and not value["reporting_certified"]


def test_publication_requires_exact_order_and_ids():
    with pytest.raises(common.InvalidBinding):
        rc.publication_status(
            [{"original_cell_id": "b", "status": "new_corrected_numerical_reproduction"}], ["a"]
        )


def test_original_functions_are_source_pinned(tmp_path):
    tmp_path = tmp_path.resolve()
    path = tmp_path / "fake.py"
    path.write_text("def f(value):\n    return value\n")
    with pytest.raises(common.InvalidBinding):
        rc.extract_functions(path, "0" * 64, ("f",), {})
    assert rc.extract_functions(path, common.sha(path), ("f",), {})["f"](4) == 4


def test_original_scientific_exclusions_and_tolerance():
    funcs = comparators()
    left = {"metric": 0.6, "seconds": 1.0, "traces": "a", "nested": {"traceback": "old", "seed": 2}}
    right = {
        "metric": 0.6 + 1e-12,
        "seconds": 99.0,
        "traces": "b",
        "nested": {"traceback": "new", "seed": 2},
    }
    funcs["assert_scientific_equal"](
        funcs["scientific_content"](left), funcs["scientific_content"](right)
    )
    right["metric"] = 0.61
    with pytest.raises(ValueError):
        funcs["assert_scientific_equal"](
            funcs["scientific_content"](left), funcs["scientific_content"](right)
        )
    assert funcs["scientific_content"]({"seed": 5, "feature_names": ["a"]}) == {
        "seed": 5,
        "feature_names": ["a"],
    }


def test_actual_cells_compare_failures_and_clock_fields(tmp_path):
    tmp_path = tmp_path.resolve()
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    a = write_cell(left, "a", status="failed", seconds=1.0, traceback="old")
    b = write_cell(right, "a", status="failed", seconds=2.0, traceback="new")
    proof = rc.compare_cells(a, b, left, right, comparators())
    assert proof["status"] == "original_scientific_and_sample_array_semantics_match"
    assert not proof["new_numerical_fit_executed_by_comparison"]


def test_actual_sample_arrays_compared_and_closed(tmp_path):
    tmp_path = tmp_path.resolve()
    left, right = tmp_path / "left", tmp_path / "right"
    left.mkdir()
    right.mkdir()
    for root, payload in ((left, b"old container"), (right, b"new container")):
        (root / "traces/a").mkdir(parents=True)
        (root / "traces/a/posterior.nc").write_bytes(payload)
    cells = [
        write_cell(
            root,
            "a",
            traces={
                "posterior": {
                    "filename": "posterior.nc",
                    "sha256": common.sha(root / "traces/a/posterior.nc"),
                }
            },
        )
        for root in (left, right)
    ]
    opened = []
    values = [np.array([1.0, np.nan]), np.array([1.0, np.nan])]

    class Dataset:
        def __init__(self, value):
            self.data_vars = {
                "beta": SimpleNamespace(values=value),
                "perf_counter_start": SimpleNamespace(values=np.array([9.0])),
            }

        def __getitem__(self, key):
            return self.data_vars[key]

    class Trace:
        def __init__(self, value):
            self.posterior = Dataset(value)
            self.sample_stats = Dataset(value)
            self.closed = False

        def close(self):
            self.closed = True

    def reader(path):
        trace = Trace(values[0 if Path(path).is_relative_to(left) else 1])
        opened.append(trace)
        return trace

    funcs = comparators(SimpleNamespace(from_netcdf=reader))
    rc.compare_cells(*cells, left, right, funcs)
    assert len(opened) == 2 and all(trace.closed for trace in opened)
    values[1] = np.array([2.0, np.nan])
    with pytest.raises(ValueError, match="sampled values differ"):
        rc.compare_cells(*cells, left, right, funcs)
    assert all(trace.closed for trace in opened)


def test_orphan_trace_retained_in_inventory(tmp_path):
    tmp_path = tmp_path.resolve()
    (tmp_path / "traces/a").mkdir(parents=True)
    (tmp_path / "traces/a/orphan.nc").write_bytes(b"unreturned old attempt")
    inventory = rc.trace_inventory(tmp_path, {"cell_id": "a", "fit_attempts": []})
    assert "traces/a/orphan.nc" in inventory["unreferenced"]


@pytest.mark.parametrize(
    "field",
    [
        "status",
        "seed",
        "array_witnesses",
        "constructor_inputs",
        "legacy_metadata",
        "actual_metadata",
        "input_witness",
    ],
)
def test_recipe_history_rejects_changed_actual_input(field):
    saved, actual = history("frozen_rank_rejected", "accepted_original_constructor")
    assert rc.compare_context_history(saved, actual)["attempts_compared"] == 2
    if field == "input_witness":
        actual["input_witness_sha256"] = "different"
    elif field == "actual_metadata":
        actual["attempts"][0][field]["processor_metadata"] = {"state": 8}
    else:
        actual["attempts"][0][field] = "different"
    with pytest.raises(common.InvalidBinding):
        rc.compare_context_history(saved, actual)


def test_input_failure_is_actual_no_generator_replay():
    saved = {
        "status": "input_failure",
        "accepted_attempt_index": None,
        "attempts": [],
        "input_error": {"type": "builtins.ValueError", "message": "events"},
    }
    actual = copy.deepcopy(saved)
    result = rc.compare_context_history(saved, actual)
    assert not result["generator_called"]
    actual["input_error"]["message"] = "different"
    with pytest.raises(common.InvalidBinding):
        rc.compare_context_history(saved, actual)


def test_nonrank_failure_stops_without_fabricated_historical_constructor():
    saved, actual = history("nonrank_error")
    result = rc.compare_context_history(saved, actual)
    assert result["nonrank_constructor_identity"] == "historically_unavailable"
    actual["attempts"][0]["error"]["message"] = "different"
    with pytest.raises(common.InvalidBinding):
        rc.compare_context_history(saved, actual)


@pytest.mark.parametrize(
    "statuses,expected",
    [
        (["accepted_original_constructor"], "accepted_original_first_draw"),
        (
            ["frozen_rank_rejected", "accepted_original_constructor"],
            "accepted_rank_conditioned_redraw",
        ),
        (
            ["frozen_rank_rejected", "nonrank_error", "accepted_original_constructor"],
            "nonrank_failure",
        ),
        (["frozen_rank_rejected"] * 256, "exhausted_rank_cap"),
    ],
)
def test_actual_recipe_rank_only_full_cap_and_seed_law(statuses, expected):
    calls, saved = [], []

    def draw(_inputs, seed):
        index = len(calls)
        calls.append(seed)
        return {"status": statuses[index], "seed": seed}, None

    def seed_function(original, label, index):
        return (
            original + 100 * index
            if label == "rank_conditioned_retry"
            else pytest.fail("wrong label")
        )

    result = terminal.replay_recipe(
        None,
        {"generation_seed": 3},
        draw,
        seed_function,
        lambda record, arrays: saved.append(record),
    )
    assert result["status"] == expected and len(saved) == len(calls)
    assert calls == [3] + [3 + 100 * i for i in range(1, len(calls))]
    if expected == "nonrank_failure":
        assert len(calls) == 2


def test_cap_cannot_be_reduced_for_terminal_replay():
    with pytest.raises(ValueError, match="cap"):
        terminal.replay_recipe(None, {"generation_seed": 3}, None, None, None, cap=2)


def test_normal_draw_exact_single_call_alias_restoration_no_svd(monkeypatch):
    monkeypatch.setattr(
        np.linalg, "svd", lambda *a, **k: pytest.fail("SVD forbidden in this invented test")
    )
    monkeypatch.setattr(
        np.linalg,
        "matrix_rank",
        lambda *a, **k: pytest.fail("rank computation forbidden in this invented test"),
    )

    class Processor:
        feature_names = ["a"]
        genes = []
        clinical = SimpleNamespace(required_source_columns=["a"])

        def metadata(self):
            return {"state": 2}

    calls = []

    def constructor(design, time, hazard):
        calls.append("constructor")
        return SimpleNamespace(design=design, time=time, hazard=hazard)

    module = SimpleNamespace(CatalyticData=constructor)

    def generator(training, processor, time, event, seed):
        assert training.columns.tolist() == ["subject_id", "a", "unused_gene"]
        calls.append(seed)
        return module.CatalyticData(np.array([[1.0], [2.0]]), np.array([0.5, 1.0]), 2.0), {
            "legacy": seed
        }

    module.generate_catalytic_data = generator
    inputs = SimpleNamespace(
        training=pd.DataFrame(
            {"subject_id": ["t1", "t2"], "a": [1.0, 2.0], "unused_gene": [9.0, 10.0]}
        ),
        time=np.array([1.0, 2.0]),
        event=np.array([1, 1]),
        processor=Processor(),
    )
    options = SimpleNamespace(deterministic_seed=lambda *args: 8)
    actual, arrays = terminal.original_draw(
        module, inputs, 7, pf, options, {"file": "actualpin"}, np
    )
    assert calls == [7, "constructor"] and module.CatalyticData is constructor
    assert (
        actual["legacy_metadata"] == {"legacy": 7}
        and actual["status"] == "accepted_original_constructor"
    )
    assert actual["array_witnesses"]["hazard"]["shape"] == [] and arrays is not None


def test_message_alone_is_nonrank_and_alias_restored():
    class Processor:
        feature_names = ["a"]
        genes = []
        clinical = SimpleNamespace(required_source_columns=["a"])

        def metadata(self):
            return {"state": 2}

    def constructor(*args):
        return None

    def wrong(*args):
        raise ValueError("synthetic design is not full column rank")

    module = SimpleNamespace(CatalyticData=constructor, generate_catalytic_data=wrong)
    inputs = SimpleNamespace(
        training=None, time=np.array([1.0]), event=np.array([1]), processor=Processor()
    )
    record, arrays = terminal.original_draw(module, inputs, 7, pf, SimpleNamespace(), {}, np)
    assert (
        record["status"] == "nonrank_error"
        and arrays is None
        and module.CatalyticData is constructor
    )


def test_terminal_scope_censorship_before_inner_split_and_no_heldout_generator():
    raw = pd.DataFrame(
        {
            "subject_id": [f"s{i}" for i in range(42)],
            "duration": np.arange(1.0, 43.0),
            "event": np.ones(42, dtype=int),
            "a": np.arange(42.0),
        }
    )
    job = SimpleNamespace(
        train=np.arange(40),
        validation=np.array([40, 41]),
        censoring_cutoff=30.0,
        gene_budget=0,
        dataset="d",
    )
    row = {
        "context_id": "a::inner_01",
        "context": "inner",
        "model": "catalytic_wme",
        "inner_fold": 1,
        "inner_cv_seed": 7,
        "inner_split_seed": 7,
        "gene_budget": 0,
        "censoring_cutoff_from_manifest": 30.0,
        "outer_train_sha256_from_manifest": pf.canonical_hash(
            raw.subject_id.iloc[job.train].tolist()
        ),
        "outer_validation_sha256_from_manifest": pf.canonical_hash(
            raw.subject_id.iloc[job.validation].tolist()
        ),
        "generation_seed": 8,
        "cell_seed": 9,
        "original_outer_fit_attempt_seeds": [1, 2, 3],
        "outer_evaluation_seed": 10,
        "shared_tau_candidate_uses": [],
    }

    class Processor:
        feature_names = ["a"]
        genes = []
        clinical = SimpleNamespace(required_source_columns=["a"])

        def metadata(self):
            return {"state": 2}

        def transform(self, training):
            return training[["a"]]

    calls = []

    class Backend:
        def apply_censor(self, times, events, cutoff):
            return np.minimum(times, cutoff), events * (times <= cutoff)

        def inner_folds(self, times, events, seed):
            calls.append((times.copy(), events.copy()))
            return [
                SimpleNamespace(
                    fold=i,
                    seed=7,
                    train_indices=np.arange(20),
                    validation_indices=np.arange(20, 40),
                )
                for i in (1, 2, 3)
            ]

        def feature_spec(self, dataset):
            return {"a": "continuous"}

        def preprocess(self, spec, budget, training):
            assert len(training) == 20 and not set(training.subject_id) & {"s40", "s41"}
            return Processor()

    inputs = pf.build_context(row, job, raw, Backend())
    assert np.max(calls[0][0]) == 30.0 and calls[0][1].sum() == 30
    assert not set(inputs.training.subject_id) & {"s40", "s41"}


def test_runtime_samefile_and_numeric_env_rejected_before_execution(tmp_path):
    tmp_path = tmp_path.resolve()
    python = Path(sys.executable).resolve()
    with pytest.raises(common.InvalidBinding):
        common.validate_runtime(python, {name: "2" for name in common.NUMERIC_THREAD_VARIABLES})
    fake = tmp_path / "python"
    fake.write_bytes(b"unrelated interpreter")
    with pytest.raises(common.InvalidBinding):
        common.validate_runtime(fake, {name: "1" for name in common.NUMERIC_THREAD_VARIABLES})


def test_write_once_output_resume_and_overlap(tmp_path):
    tmp_path = tmp_path.resolve()
    selection = tmp_path / "selection.json"
    common.write_new(selection, common.seal({"status": "invented"}))
    output = tmp_path / "out"
    cli.prepare_output(common, output, selection, common.sha(selection), [])
    cli.prepare_output(common, output, selection, common.sha(selection), [])
    (output / "unexpected.txt").write_text("not owned")
    with pytest.raises(common.InvalidBinding):
        cli.prepare_output(common, output, selection, common.sha(selection), [])
    with pytest.raises(common.InvalidBinding):
        cli.prepare_output(
            common, tmp_path / "nested", selection, common.sha(selection), [tmp_path]
        )


def test_nonzero_child_retains_stderr_and_invocation(tmp_path):
    tmp_path = tmp_path.resolve()

    def failed(argv, stdout, stderr, **kwargs):
        stderr.write(b"actual injected nonzero")
        return SimpleNamespace(returncode=9)

    with pytest.raises(common.InvalidBinding, match="nonzero"):
        cli.capture_child(common, ["owned", "-I", "-B"], tmp_path, failed)
    receipt = common.read_json(tmp_path / "invocation.json")
    assert (
        receipt["exit_code"] == 9
        and (tmp_path / "stderr.log").read_bytes() == b"actual injected nonzero"
    )


def test_launch_exception_retained(tmp_path):
    tmp_path = tmp_path.resolve()

    def failed(*args, **kwargs):
        raise OSError("invented launch failure")

    with pytest.raises(common.InvalidBinding):
        cli.capture_child(common, ["owned"], tmp_path, failed)
    assert (
        common.read_json(tmp_path / "invocation.json")["launch_error"]["message"]
        == "invented launch failure"
    )


def test_modified_checkpoint_artifact_rejected(tmp_path):
    tmp_path = tmp_path.resolve()
    (tmp_path / "cells").mkdir()
    (tmp_path / "attempts").mkdir()
    log = tmp_path / "attempts/log"
    log.write_bytes(b"old")
    record = common.seal(
        {
            "original_cell_id": "a",
            "selection_sha256": "scope",
            "status": "retained_reproduction_failure",
            "artifacts": {"attempts/log": common.file_binding(log)},
            "external_artifacts": {},
        }
    )
    path = tmp_path / "cells/a.json"
    common.write_new(path, record)
    cli.verify_record(common, path, "scope", "a", tmp_path)
    log.write_bytes(b"new")
    with pytest.raises(common.InvalidBinding):
        cli.verify_record(common, path, "scope", "a", tmp_path)


def test_replay_rank_guard_exact_type_frame_and_line():
    class Constructor:
        def __post_init__(self):
            raise ValueError("synthetic design is not full column rank")

    line = inspect.getsourcelines(Constructor.__post_init__)[1] + 1
    try:
        Constructor().__post_init__()
    except ValueError as error:
        assert terminal.rank_rejection(error, Constructor, line)
        assert not terminal.rank_rejection(error, Constructor, line + 1)
    try:
        raise ValueError("synthetic design is not full column rank")
    except ValueError as error:
        assert not terminal.rank_rejection(error, Constructor, line)


def test_original_numerical_resolution_cannot_replace_known_evidence(tmp_path):
    tmp_path = tmp_path.resolve()
    base = {"entries": {"a": {"status": "verified_original_numerical_reproduction_evidence"}}}
    selection = {"original_selected_cells": ["a"]}
    fake_rc = SimpleNamespace(scope_definition=lambda value: "scope")
    path = tmp_path / "resolution.json"
    common.write_new(
        path,
        common.seal(
            {
                "status": "reviewed_original_numerical_evidence_resolution",
                "scope_definition_sha256": "scope",
                "original_manifest_sha256": common.ORIGINAL_MANIFEST_SHA,
                "entries": {"a": {"status": "verified_original_numerical_reproduction_evidence"}},
            }
        ),
    )
    with pytest.raises(common.InvalidBinding):
        cli.numerical_inventory(common, fake_rc, selection, base, path, common.sha(path))


def test_original_comparison_source_bytes_not_modified():
    before = {name for name in sys.modules if name == "src" or name.startswith("src.")}
    for name, expected in rc.COMPARISON_PINS.items():
        assert hashlib.sha256((SOURCE / name).read_bytes()).hexdigest() == expected
    assert {name for name in sys.modules if name == "src" or name.startswith("src.")} == before


def controller_fixture(tmp_path, action="fit_changed_inputs", *, pilot=True):
    tmp_path = tmp_path.resolve()
    output = tmp_path / "reproduction"
    output.mkdir()
    for name in ("cells", "claims", "attempts", "passes"):
        (output / name).mkdir()
    corrected = tmp_path / "corrected"
    corrected.mkdir()
    baseline = corrected / "envelope.json"
    common.write_new(baseline, common.seal({"fixture": "actualcorrected"}))
    original_reproduction = tmp_path / "original_reproduction"
    original_reproduction.mkdir()
    (original_reproduction / "claims").mkdir()
    identity = "a"
    entry = {
        "original_cell_id": identity,
        "input_witness_sha256": "input",
        "model": "catalytic_fixed",
    }
    decision = {"action": action, "source_evidence": None}
    witness = SimpleNamespace(corrected_seeds={"cell": 7})
    value = cli.Controller.__new__(cli.Controller)
    value.common = common
    value.rc = SimpleNamespace(
        scope_definition=lambda _: "scopesha",
        FIT_SOURCE_PINS=rc.FIT_SOURCE_PINS,
        compare_cells=rc.compare_cells,
    )
    value.args = SimpleNamespace(
        output=output,
        selection_sha256="selection",
        python=Path(sys.executable).resolve(),
        pilot_review=None,
        pilot_review_sha256=None,
    )
    value.selection = {
        "corrected_manifest_sha256": "manifest",
        "correction_freeze_sha256": "freeze",
    }
    value.freeze = {"definition_content_sha256": "definition"}
    value.paths = {"original_run": tmp_path / "original"}
    value.repro_paths = {"corrected_run": corrected, "original_reproduction": original_reproduction}
    value.manifest = {"pilot_cells": ["a"] if pilot else []}
    value.numerical = {}
    value.input_controller = SimpleNamespace(
        current=lambda _: ({}, decision, {"status": "complete"}, witness)
    )
    operation = (
        "reuse_original_outcome"
        if action == "reuse_original_outcome"
        else "retain_corrected_input_failure"
        if action == "retain_input_failure"
        else "fit_corrected_inputs"
    )
    value.baseline = lambda *args: (baseline, {"operation": operation, "decision": decision})
    return value, entry, decision, witness


def test_original_owner_pending_does_not_touch_baseline_or_attempt(tmp_path):
    tmp_path = tmp_path.resolve()
    value, entry, _, _ = controller_fixture(tmp_path, "await_original_owner_or_outcome")
    value.baseline = lambda *args: pytest.fail("pending owner must stop before baseline")
    result = value.record(entry)
    assert result["status"] == "pending_original_owner_or_input_proof"
    assert not list((value.args.output / "attempts").iterdir())


def test_unchanged_without_official_numerical_receipt_stays_pending(tmp_path):
    tmp_path = tmp_path.resolve()
    value, entry, _, _ = controller_fixture(tmp_path, "reuse_original_outcome")
    value.numerical = {"a": {"status": "pending_original_numerical_reproduction"}}
    result = value.record(entry)
    assert result["status"] == "pending_original_numerical_reproduction"
    assert not list((value.args.output / "attempts").iterdir())


def test_nonpilot_waits_for_actual_pilot_review_without_failed_attempt(tmp_path):
    tmp_path = tmp_path.resolve()
    value, entry, _, _ = controller_fixture(tmp_path, pilot=False)
    result = value.record(entry)
    assert result["status"] == "pending_full_budget_pilot_review"
    assert not list((value.args.output / "attempts").iterdir())


def test_unrecorded_orphan_attempt_never_retried(tmp_path):
    tmp_path = tmp_path.resolve()
    value, entry, _, _ = controller_fixture(tmp_path)
    (value.args.output / "attempts/a.old").mkdir()
    with pytest.raises(common.InvalidBinding, match="orphan"):
        value.record(entry)


def test_failed_reproduction_retained_and_not_retried(tmp_path):
    tmp_path = tmp_path.resolve()
    value, entry, _, _ = controller_fixture(tmp_path)
    calls = []

    def failed(*args):
        calls.append(1)
        raise ValueError("invented numeric mismatch")

    value.execute_changed = failed
    result = value.record(entry)
    assert result["status"] == "retained_reproduction_failure"
    resumed = value.record(entry)
    assert resumed["status"] == "retained_reproduction_failure" and calls == [1]
    record = common.read_json(value.args.output / "cells/a.json")
    assert any(name.endswith("failure.json") for name in record["artifacts"])


def test_terminal_action_cannot_dispatch_fit(tmp_path):
    tmp_path = tmp_path.resolve()
    value, entry, _, _ = controller_fixture(tmp_path, "retain_input_failure")
    value.execute_changed = lambda *args: pytest.fail("terminal must not fit")
    calls = []

    def terminal_outcome(*args):
        calls.append(1)
        return {"status": "terminal_no_fit_recipe_replay", "new_numerical_fit_executed": False}

    value.execute_terminal = terminal_outcome
    assert value.record(entry)["status"] == "terminal_no_fit_recipe_replay" and calls == [1]


def test_same_sealed_fit_child_request_in_new_owned_attempt(tmp_path):
    tmp_path = tmp_path.resolve()
    value, entry, decision, witness = controller_fixture(tmp_path)
    value.repro_paths.update(
        fit_code=SUPPORT, freeze=tmp_path / "freeze.json", manifest=tmp_path / "manifest.json"
    )
    corrected = value.repro_paths["corrected_run"]
    old_attempt = corrected / "old_attempt"
    old_attempt.mkdir()
    old_cell = write_cell(old_attempt, "a")
    baseline = {
        "corrected_cell": {
            "path": str(old_cell.relative_to(corrected)),
            "sha256": common.sha(old_cell),
        }
    }
    value.comparators = comparators()
    observed = []

    def fake_child(argv, **kwargs):
        assert argv[1:3] == ["-I", "-B"] and Path(argv[3]) == SUPPORT / "fit_child.py"
        request = common.read_json(Path(argv[argv.index("--request") + 1]))
        observed.append(request)
        assert request["entry"] == entry and request["source_evidence"] is None
        assert request["action"] == "fit_changed_inputs" and request["freeze_sha256"] == "freeze"
        assert request["implementation_source_sha256"] == rc.FIT_SOURCE_PINS
        assert all(kwargs["env"][name] == "1" for name in common.NUMERIC_THREAD_VARIABLES)
        target = Path(request["attempt_path"])
        cell = write_cell(target, "a", seconds=99.0)
        common.write_new(
            target / "child_receipt.json",
            common.seal(
                {
                    "status": "original_cell_delegated_with_verified_corrected_inputs",
                    "original_cell_id": "a",
                    "corrected_manifest_sha256": "manifest",
                    "input_witness_sha256": "input",
                    "action": "fit_changed_inputs",
                    "original_seed_namespace": witness.corrected_seeds,
                    "cell": common.file_binding(cell),
                    "scientific_status": "complete",
                }
            ),
        )
        return SimpleNamespace(returncode=0)

    value.invoke = fake_child
    attempt = value.args.output / "attempts/a.new"
    attempt.mkdir()
    result = value.execute_changed(entry, decision, witness, baseline, attempt)
    assert len(observed) == 1 and result["status"] == "new_corrected_numerical_reproduction"
    assert (attempt / "comparison.json").exists() and old_cell.read_bytes() != (
        attempt / "cells/a.json"
    ).read_bytes()


def test_final_gate_failure_prevents_pass_certificate(tmp_path):
    tmp_path = tmp_path.resolve()
    value, entry, _, _ = controller_fixture(tmp_path)
    value.inventory = {"entries": [entry]}
    value.selection["selected_cells"] = ["a"]
    value.record = lambda _: {
        "original_cell_id": "a",
        "status": "new_corrected_numerical_reproduction",
    }
    value.final_gates = lambda: (_ for _ in ()).throw(common.InvalidBinding("late binding changed"))
    with pytest.raises(common.InvalidBinding, match="late binding"):
        value.run()
    assert not list((value.args.output / "passes").iterdir())


def selection_fixture(tmp_path, monkeypatch):
    tmp_path = tmp_path.resolve()
    selection, original, manifest = base_selection()
    preflight = tmp_path / "preflight"
    preflight.mkdir()
    rows = [{"context_id": f"invented{i}"} for i in range(1650)]
    recipe = tmp_path / "recipe.jsonl"
    recipe.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    preflight_path = preflight / "manifest.json"
    common.write_new(preflight_path, common.seal({"contexts_jsonl_sha256": common.sha(recipe)}))
    completion = {"outcomes": [{"context_id": row["context_id"]} for row in rows]}
    freeze = {
        "original_manifest_sha256": common.ORIGINAL_MANIFEST_SHA,
        "definition_content_sha256": "definition",
        "input_inventory_sha256": "inventory",
        "preflight_manifest_sha256": common.sha(preflight_path),
        "paths": {
            "original_run": str(tmp_path / "original"),
            "source": str(SOURCE),
            "preflight": str(preflight),
        },
    }
    monkeypatch.setattr(common, "load_gates", lambda *args: (freeze, manifest, {}, completion))
    monkeypatch.setattr(common, "read_original_manifest", lambda *args: original)
    evidence = {
        "status": "reviewed_original_92_numerical_reproduction_evidence",
        "original_manifest_sha256": common.ORIGINAL_MANIFEST_SHA,
        "comparison_source_sha256": rc.COMPARISON_PINS,
        "entries": {
            identity: {"status": "pending_original_numerical_reproduction"}
            for identity in selection["original_selected_cells"]
        },
    }
    evidence_path = tmp_path / "evidence.json"
    common.write_new(evidence_path, common.seal(evidence))
    selection.update(
        schema_version=1,
        status="reviewed_corrected_reproduction_selection",
        original_manifest_sha256=common.ORIGINAL_MANIFEST_SHA,
        correction_freeze_sha256="freeze",
        corrected_manifest_sha256="manifest",
        definition_content_sha256="definition",
        input_inventory_sha256="inventory",
        implementation_source_sha256={name: common.sha(HERE / name) for name in rc.OWN_SOURCES},
        fit_implementation_source_sha256=rc.FIT_SOURCE_PINS,
        comparison_source_sha256=rc.COMPARISON_PINS,
        recipe_inventory_sha256=common.sha(recipe),
        original_numerical_evidence_sha256=common.sha(evidence_path),
        execution={
            "workers": 1,
            "numeric_threads": 1,
            "original_full_budget": True,
            "terminal_recipe": "normal_full_raw_preprocessing_original_generator_rank_only_cap256",
            "comparison": "original_scientific_content_tolerance1e-10_and_exact_posterior_sample_stats",
            "pending_original_policy": "await_reviewed_original_numerical_evidence_and_finished_owner",
        },
        paths={
            "freeze": str(tmp_path / "freeze.json"),
            "manifest": str(tmp_path / "fit_manifest.json"),
            "fit_code": str(SUPPORT),
            "corrected_run": str(tmp_path / "corrected"),
            "original_reproduction": str(tmp_path / "original_reproduction"),
            "original_numerical_evidence": str(evidence_path),
            "recipe_inventory": str(recipe),
            "scope_review": str(tmp_path / "scope_review.json"),
        },
    )
    review = {
        "status": "reproduction_scope_frozen_before_corrected_score",
        "scope_definition_sha256": rc.scope_definition(selection),
        "corrected_manifest_sha256": "manifest",
        "frozen_before_any_corrected_score": True,
    }
    return selection, review


def finish_selection_fixture(tmp_path, selection, review):
    tmp_path = tmp_path.resolve()
    path = tmp_path / "scope_review.json"
    common.write_new(path, common.seal(review))
    selection["scope_review_sha256"] = common.sha(path)
    result = tmp_path / "selection.json"
    common.write_new(result, common.seal(selection))
    return result


def test_selection_requires_separate_bound_prospective_scope_review(tmp_path, monkeypatch):
    tmp_path = tmp_path.resolve()
    selection, review = selection_fixture(tmp_path, monkeypatch)
    path = finish_selection_fixture(tmp_path, selection, review)
    value, *_ = rc.load_selection(path, common.sha(path), HERE)
    assert len(value["selected_cells"]) == 93


@pytest.mark.parametrize(
    "change",
    [
        "review_status",
        "review_digest",
        "after_score",
        "scope",
        "own_source",
        "fit_source",
        "original_source",
        "budget",
        "definition",
        "recipe",
    ],
)
def test_selection_root_gates_reject_unfrozen_or_foreign_inputs(tmp_path, monkeypatch, change):
    tmp_path = tmp_path.resolve()
    selection, review = selection_fixture(tmp_path, monkeypatch)
    if change == "review_status":
        review["status"] = "draft"
    elif change == "review_digest":
        review["scope_definition_sha256"] = "wrong"
    elif change == "after_score":
        review["frozen_before_any_corrected_score"] = False
    elif change == "scope":
        selection["selected_cells"].pop()
    elif change == "own_source":
        selection["implementation_source_sha256"]["run_reproduction.py"] = "wrong"
    elif change == "fit_source":
        selection["fit_implementation_source_sha256"] = {
            **rc.FIT_SOURCE_PINS,
            "fit_child.py": "wrong",
        }
    elif change == "original_source":
        selection["comparison_source_sha256"] = {
            **rc.COMPARISON_PINS,
            "scripts/reproduce_extensions.py": "wrong",
        }
    elif change == "budget":
        selection["execution"]["original_full_budget"] = False
    elif change == "definition":
        selection["definition_content_sha256"] = "wrong"
    else:
        selection["recipe_inventory_sha256"] = "wrong"
    path = finish_selection_fixture(tmp_path, selection, review)
    with pytest.raises(common.InvalidBinding):
        rc.load_selection(path, common.sha(path), HERE)


def test_bootstrap_rejects_support_bytes_before_import(tmp_path):
    tmp_path = tmp_path.resolve()
    fake = tmp_path / "fit"
    fake.mkdir()
    (fake / "fit_common.py").write_text("raise RuntimeError('must not execute')\n")
    path = tmp_path / "selection.json"
    path.write_text(
        json.dumps(
            {
                "paths": {"fit_code": str(fake)},
                "fit_implementation_source_sha256": {"fit_common.py": "wrong"},
            }
        )
    )
    with pytest.raises(ValueError, match="common source"):
        cli.bootstrap(path, common.sha(path))


def producer_fixture(tmp_path):
    tmp_path = tmp_path.resolve()
    source = tmp_path / "producer"
    source.mkdir()
    (source / "scripts").mkdir()
    # Read-only source bytes copied into a temporary invented provenance fixture;
    # this file is never imported/executed and no data files are read.
    (source / "scripts/reproduce_extensions.py").write_bytes(
        (SOURCE / "scripts/reproduce_extensions.py").read_bytes()
    )
    (source / "other.py").write_text("# invented unused source\n")
    hashes = {
        name: common.sha(source / name) for name in ("scripts/reproduce_extensions.py", "other.py")
    }
    matched = tmp_path / "matched.bin"
    matched.write_bytes(b"invented matched input; not a cohort")
    original = {
        "input_sha256": hashes,
        "matched_sha256": common.sha(matched),
        "plan": [{"cell_id": cell_id(i)} for i in range(92)],
    }
    environment = {"status": "ok", "package_count": 259, "scope": "invented test report"}
    env_path = tmp_path / "environment.json"
    env_path.write_text(json.dumps(environment))
    original_run, reproduction = tmp_path / "original", tmp_path / "original_reproduction"
    commit = "8551d326b02bfe88915cfd9eb50c6ca8e5690e3a"
    invocation = {
        "status": "actual_original_numerical_worker_invocation_recorded",
        "source_path": str(source),
        "git_commit": commit,
        "original_manifest_sha256": common.ORIGINAL_MANIFEST_SHA,
        "original_run": str(original_run),
        "reproduction_output": str(reproduction),
        "source_input_sha256": hashes,
        "environment_report_sha256": common.sha(env_path),
        "original_full_budget": True,
        "actual_numerical_refit_execution": True,
        "exit_code": 0,
        "owner_finished": True,
        "cached_comparison_only": False,
        "numerically_refitted_cell_ids": [cell_id(0)],
        "numeric_thread_environment": {name: "1" for name in common.NUMERIC_THREAD_VARIABLES},
        "cwd": str(source),
        "script_index": 2,
        "python_executable": sys.executable,
        "argv": [
            sys.executable,
            "-B",
            str(source / "scripts/reproduce_extensions.py"),
            "--source",
            str(original_run),
            "--output",
            str(reproduction),
            "--matched",
            str(matched),
        ],
    }
    invocation_path = tmp_path / "invocation.json"
    common.write_new(invocation_path, common.seal(invocation))
    official = {
        "status": "actual_official_original_92_comparison_recorded",
        "source_path": str(source),
        "git_commit": commit,
        "original_manifest_sha256": common.ORIGINAL_MANIFEST_SHA,
        "source_input_sha256": hashes,
        "environment_report_sha256": common.sha(env_path),
        "exit_code": 0,
        "owner_finished": True,
        "scientifically_compared_cell_ids": [cell_id(0)],
        "numeric_thread_environment": {name: "1" for name in common.NUMERIC_THREAD_VARIABLES},
        "python_executable": sys.executable,
        "argv": invocation["argv"],
        "cwd": str(source),
        "script_index": 2,
        "cached_comparison_only": False,
    }
    official_path = tmp_path / "official_comparison.json"
    common.write_new(official_path, common.seal(official))
    lineage = {
        "status": "original_numerical_execution_input_and_algorithm_lineage_reviewed",
        "original_manifest_sha256": common.ORIGINAL_MANIFEST_SHA,
        "producer_git_commit": commit,
        "producer_input_sha256": hashes,
        "original_input_sha256": hashes,
        "invocation_record_sha256": common.sha(invocation_path),
        "official_comparison_record_sha256": common.sha(official_path),
        "producer_route": "official_fresh_refit",
        "frozen_primary_scientific_inputs_algorithms_seeds_budgets_and_gates_identical": True,
    }
    lineage_path = tmp_path / "lineage.json"
    common.write_new(lineage_path, common.seal(lineage))
    producer = {
        "source_path": str(source),
        "git_commit": commit,
        "input_sha256": hashes,
        "route": "official_fresh_refit",
        "matched_input": {"path": str(matched), "binding": common.file_binding(matched)},
        "environment_report": {"path": str(env_path), "binding": common.file_binding(env_path)},
        "invocation_record": {
            "path": str(invocation_path),
            "binding": common.file_binding(invocation_path),
        },
        "official_comparison_record": {
            "path": str(official_path),
            "binding": common.file_binding(official_path),
        },
        "scientific_lineage_review": {
            "path": str(lineage_path),
            "binding": common.file_binding(lineage_path),
        },
    }

    def git(argv, **kwargs):
        assert kwargs["cwd"] == source
        return SimpleNamespace(stdout=commit if "rev-parse" in argv else "")

    return producer, original, environment, original_run, reproduction, git


def test_actual_producer_environment_invocation_and_lineage_required(tmp_path):
    tmp_path = tmp_path.resolve()
    values = producer_fixture(tmp_path)
    result = rc.verify_old_numerical_producer(
        *values[:-1], original_cell_id=cell_id(0), invoke=values[-1]
    )
    assert len(result) == 7


@pytest.mark.parametrize(
    "change",
    [
        "commit",
        "input_coverage",
        "source_byte",
        "matched",
        "environment",
        "numeric",
        "argv",
        "exit",
        "lineage",
    ],
)
def test_old_numerical_producer_cannot_be_certified_by_cell_hash_alone(tmp_path, change):
    tmp_path = tmp_path.resolve()
    producer, original, environment, old, reproduction, git = producer_fixture(tmp_path)
    if change == "commit":
        producer["git_commit"] = "unknown"
    elif change == "input_coverage":
        producer["input_sha256"] = {"other.py": producer["input_sha256"]["other.py"]}
    elif change == "source_byte":
        (Path(producer["source_path"]) / "other.py").write_text("changed\n")
    elif change == "matched":
        Path(producer["matched_input"]["path"]).write_bytes(b"changed input")
    elif change == "environment":
        environment["package_count"] = 258
    else:
        role = "scientific_lineage_review" if change == "lineage" else "invocation_record"
        path = Path(producer[role]["path"])
        value = common.read_json(path)
        value.pop("content_sha256")
        if change == "numeric":
            value["numeric_thread_environment"]["OMP_NUM_THREADS"] = "2"
        elif change == "argv":
            value["argv"][-1] = "wrong"
        elif change == "exit":
            value["exit_code"] = 9
        else:
            value[
                "frozen_primary_scientific_inputs_algorithms_seeds_budgets_and_gates_identical"
            ] = False
        path.unlink()
        common.write_new(path, common.seal(value))
        producer[role]["binding"] = common.file_binding(path)
        if role == "invocation_record":
            lineage_path = Path(producer["scientific_lineage_review"]["path"])
            lineage = common.read_json(lineage_path)
            lineage.pop("content_sha256")
            lineage["invocation_record_sha256"] = common.sha(path)
            lineage_path.unlink()
            common.write_new(lineage_path, common.seal(lineage))
            producer["scientific_lineage_review"]["binding"] = common.file_binding(lineage_path)
    with pytest.raises(common.InvalidBinding):
        rc.verify_old_numerical_producer(
            producer,
            original,
            environment,
            old,
            reproduction,
            original_cell_id=cell_id(0),
            invoke=git,
        )


def replace_fixture_record(path, value):
    path.unlink()
    common.write_new(
        path, common.seal({key: item for key, item in value.items() if key != "content_sha256"})
    )


def prestaged_producer_fixture(tmp_path):
    tmp_path = tmp_path.resolve()
    producer, original, environment, old, reproduction, _ = producer_fixture(tmp_path)
    producer["route"] = "reviewed_external_prestage"
    producer["git_commit"] = common.ORIGINAL_COMMIT
    source = Path(producer["source_path"])
    helper = tmp_path / "prestage_refits.py"
    helper.write_bytes(PRESTAGE.read_bytes())
    producer["helper"] = {"path": str(helper), "binding": common.file_binding(helper)}
    helper_review = {
        "status": "actual_prestage_helper_scientific_delegation_reviewed",
        "helper_sha256": rc.PRESTAGE_HELPER_SHA,
        "original_manifest_sha256": common.ORIGINAL_MANIFEST_SHA,
        "production_source_commit": common.ORIGINAL_COMMIT,
        "unchanged_run_extension_cell_inputs_seeds_budget_and_guards": True,
        "issues_official_final_receipts": False,
    }
    review_path = tmp_path / "helper_review.json"
    common.write_new(review_path, common.seal(helper_review))
    producer["helper_scientific_delegation_review"] = {
        "path": str(review_path),
        "binding": common.file_binding(review_path),
    }
    stdout = tmp_path / "prestage.log"
    stdout.write_text(cell_id(0) + " prestaged_exact\n")
    path = Path(producer["invocation_record"]["path"])
    invocation = common.read_json(path)
    invocation.update(
        git_commit=common.ORIGINAL_COMMIT,
        worker=0,
        workers=2,
        argv=[
            sys.executable,
            "-B",
            str(helper),
            "--production-code",
            str(source),
            "--matched",
            str(Path(producer["matched_input"]["path"])),
            "--source",
            str(old),
            "--output",
            str(reproduction),
            "--workers",
            "2",
            "--worker",
            "0",
        ],
        stdout={"path": str(stdout), "binding": common.file_binding(stdout)},
    )
    replace_fixture_record(path, invocation)
    producer["invocation_record"]["binding"] = common.file_binding(path)
    path = Path(producer["official_comparison_record"]["path"])
    official = common.read_json(path)
    official.update(git_commit=common.ORIGINAL_COMMIT, cached_comparison_only=True)
    official["argv"][2] = "scripts/reproduce_extensions.py"
    replace_fixture_record(path, official)
    producer["official_comparison_record"]["binding"] = common.file_binding(path)
    path = Path(producer["scientific_lineage_review"]["path"])
    lineage = common.read_json(path)
    lineage.update(
        producer_git_commit=common.ORIGINAL_COMMIT,
        producer_route="reviewed_external_prestage",
        invocation_record_sha256=producer["invocation_record"]["binding"]["sha256"],
        official_comparison_record_sha256=producer["official_comparison_record"]["binding"][
            "sha256"
        ],
    )
    replace_fixture_record(path, lineage)
    producer["scientific_lineage_review"]["binding"] = common.file_binding(path)

    def git(argv, **kwargs):
        return SimpleNamespace(stdout=common.ORIGINAL_COMMIT if "rev-parse" in argv else "")

    return producer, original, environment, old, reproduction, git


def test_actual_prestage_numerical_producer_separate_from_cached_official_comparator(tmp_path):
    tmp_path = tmp_path.resolve()
    values = prestaged_producer_fixture(tmp_path)
    proof = rc.verify_old_numerical_producer(
        *values[:-1], original_cell_id=cell_id(0), invoke=values[-1]
    )
    assert len(proof) == 10


@pytest.mark.parametrize(
    "change",
    [
        "helper_bytes",
        "checkout",
        "production_argv",
        "worker_argv",
        "cell_log",
        "cached_only_producer",
        "missing_actual_refit",
        "official_argv",
    ],
)
def test_prestage_or_cached_comparison_cannot_manufacture_numerical_refit(tmp_path, change):
    tmp_path = tmp_path.resolve()
    producer, original, environment, old, reproduction, git = prestaged_producer_fixture(tmp_path)
    if change == "helper_bytes":
        Path(producer["helper"]["path"]).write_text("# changed helper\n")
    elif change == "checkout":

        def git(*args, **kwargs):
            return SimpleNamespace(stdout="wrong" if "rev-parse" in args[0] else "")
    else:
        role = "official_comparison_record" if change == "official_argv" else "invocation_record"
        path = Path(producer[role]["path"])
        value = common.read_json(path)
        if change == "production_argv":
            value["argv"][value["argv"].index("--production-code") + 1] = "wrong"
        elif change == "worker_argv":
            value["argv"][-1] = "1"
        elif change == "cell_log":
            stdout = Path(value["stdout"]["path"])
            stdout.write_text("no fresh refit event\n")
            value["stdout"]["binding"] = common.file_binding(stdout)
        elif change == "cached_only_producer":
            value["cached_comparison_only"] = True
        elif change == "missing_actual_refit":
            value["numerically_refitted_cell_ids"] = []
        else:
            value["argv"][2] = "changed_comparator.py"
        replace_fixture_record(path, value)
        producer[role]["binding"] = common.file_binding(path)
    with pytest.raises(common.InvalidBinding):
        rc.verify_old_numerical_producer(
            producer,
            original,
            environment,
            old,
            reproduction,
            original_cell_id=cell_id(0),
            invoke=git,
        )


@dataclass(frozen=True)
class TerminalWitness:
    original_evidence: Any
    corrected_seeds: dict[str, int]


def pending_terminal_fixture(tmp_path):
    tmp_path = tmp_path.resolve()
    value, entry, _, _ = controller_fixture(tmp_path, "retain_input_failure")
    source = {"original_cell_id": "a", "finished": "actual_injected_source_evidence"}

    def classify(witness):
        return {
            "action": "retain_input_failure",
            "source_evidence": witness.original_evidence,
            "identity": "a",
            "failure_contexts": ["outer"],
        }

    witness = TerminalWitness(source, {"cell": 7})
    pending = classify(TerminalWitness(None, {"cell": 7}))
    current = classify(witness)
    value.contracts = SimpleNamespace(classify=classify)
    root = value.repro_paths["corrected_run"]
    manifest = root / "manifest.json"
    common.write_new(manifest, common.seal({"status": "invented immutable manifest"}))
    value.selection["corrected_manifest_sha256"] = common.sha(manifest)
    (root / "cells").mkdir()
    envelope = {
        "operation": "retain_corrected_input_failure",
        "original_outcome_pending": True,
        "correction_freeze_sha256": "freeze",
        "definition_content_sha256": "definition",
        "input_witness_sha256": "input",
        "original_seed_namespace": witness.corrected_seeds,
        "decision": pending,
        "source_evidence": None,
    }
    path = root / "cells/a.json"
    common.write_new(path, common.seal(envelope))
    value.fit_controller = SimpleNamespace(verify_record=lambda path, *args: common.read_json(path))
    snapshots = tmp_path / "witnesses"
    snapshots.mkdir()
    value.paths["witness_root"] = snapshots
    snapshot_path = snapshots / "finished.json"
    common.write_new(
        snapshot_path,
        common.seal(
            {
                "source_evidence": source,
                "decision": current,
                "input_witness_sha256": "input",
                "definition_content_sha256": "definition",
            }
        ),
    )
    resolution = {"snapshot_path": "finished.json", "snapshot_sha256": common.sha(snapshot_path)}
    value.input_controller = SimpleNamespace(
        resolutions={"a": resolution},
        current=lambda _: ({}, current, {"status": "complete"}, witness),
    )
    return value, entry, current, witness, path


def test_immutable_pending_terminal_envelope_accepts_later_reviewed_source_resolution(tmp_path):
    tmp_path = tmp_path.resolve()
    value, entry, current, witness, path = pending_terminal_fixture(tmp_path)
    before = path.read_bytes()
    verified_path, envelope = cli.Controller.baseline(value, entry, current, witness)
    assert (
        verified_path == path
        and envelope["source_evidence"] is None
        and path.read_bytes() == before
    )
    assert (
        value.acquisition_binding(entry, current)["snapshot_sha256"]
        == value.input_controller.resolutions["a"]["snapshot_sha256"]
    )


@pytest.mark.parametrize(
    "change",
    [
        "missing_review",
        "different_pending_decision",
        "different_input",
        "different_source",
        "not_pending",
        "not_terminal",
    ],
)
def test_terminal_source_resolution_does_not_strip_differing_lineage(tmp_path, change):
    tmp_path = tmp_path.resolve()
    value, entry, current, witness, path = pending_terminal_fixture(tmp_path)
    if change == "missing_review":
        value.input_controller.resolutions = {}
    elif change in {"different_pending_decision", "not_pending", "not_terminal"}:
        envelope = common.read_json(path)
        if change == "different_pending_decision":
            envelope["decision"]["identity"] = "changed"
        elif change == "not_pending":
            envelope["original_outcome_pending"] = False
        else:
            envelope["operation"] = "fit_corrected_inputs"
        replace_fixture_record(path, envelope)
    else:
        snapshot_path = value.paths["witness_root"] / "finished.json"
        snapshot = common.read_json(snapshot_path)
        if change == "different_input":
            snapshot["input_witness_sha256"] = "changed"
        else:
            snapshot["source_evidence"] = {"changed": True}
        replace_fixture_record(snapshot_path, snapshot)
        value.input_controller.resolutions["a"]["snapshot_sha256"] = common.sha(snapshot_path)
    with pytest.raises(common.InvalidBinding):
        cli.Controller.baseline(value, entry, current, witness)


def test_prior_actual_terminal_replay_resumes_with_append_only_finished_acquisition(tmp_path):
    tmp_path = tmp_path.resolve()
    value, entry, current, witness, path = pending_terminal_fixture(tmp_path)
    pending = value.contracts.classify(TerminalWitness(None, {"cell": 7}))
    common.write_new(
        value.args.output / "cells/a.json",
        common.seal(
            {
                "original_cell_id": "a",
                "selection_sha256": "selection",
                "status": "terminal_no_fit_recipe_replay",
                "artifacts": {},
                "external_artifacts": {},
                "corrected_outcome_sha256": common.sha(path),
                "input_witness_sha256": "input",
                "current_input_decision": pending,
            }
        ),
    )
    value.baseline = lambda *args: cli.Controller.baseline(value, *args)
    value.execute_terminal = lambda *args: pytest.fail(
        "cached actual terminal replay must not execute twice"
    )
    record_path = value.args.output / "cells/a.json"
    before = record_path.read_bytes()
    result = value.record(entry)
    assert (
        result["status"] == "terminal_no_fit_recipe_replay"
        and "later_reviewed_original_acquisition" in result
    )
    assert record_path.read_bytes() == before


def test_controller_imports_are_stdlib_only_in_fresh_process():
    script = r"""
import importlib.util
import sys
from pathlib import Path
support = Path(sys.argv[1])
own = support / "reproduction"
def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
load(support / "fit_common.py", "_reproduction_bound_common")
load(own / "reproduction_core.py", "_fresh_core")
load(own / "run_reproduction.py", "_fresh_cli")
load(own / "terminal_replay_child.py", "_fresh_terminal")
assert not any(name == "src" or name.startswith("src.") for name in sys.modules)
assert "numpy" not in sys.modules and "pandas" not in sys.modules
"""
    subprocess.run([sys.executable, "-I", "-B", "-c", script, str(SUPPORT)], check=True)
