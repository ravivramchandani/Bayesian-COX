"""Only fictional metadata counterexamples; no real controller/main/checker."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

CARRIER = Path("/Users/macuser/bayes-cox-runs/extensions-20260928/generator_correction_guarded_dispatch_v1")
spec = importlib.util.spec_from_file_location("_independent_fictional_guard_fixture", CARRIER / "test_guarded_dispatch.py")
assert spec is not None and spec.loader is not None
t = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = t
spec.loader.exec_module(t)
g, c = t.g, t.c


def rewrite(path, value):
    value = {key: item for key, item in value.items() if key != "content_sha256"}
    path.write_text(json.dumps(g.sealed(value), sort_keys=True, indent=2) + "\n")


def fictional_fixture():
    temporary = tempfile.TemporaryDirectory(prefix="independent-guard-counterexample-")
    return temporary, t.Fixture(Path(temporary.name).resolve(strict=True))


results = []
temporary, f = fictional_fixture()
try:
    cell = f.output / "cells/a.json"
    original = g.document(cell)
    additions = {"corrected_cell": {"logical_root": "corrected_fit_run", "path": "attempts/a/cells/a.json", "sha256": "0" * 64, "cell_content_sha256": "1" * 64},
                 "child_receipt_path": "attempts/a/child_receipt.json", "invocation_path": "attempts/a/invocation.json",
                 "observations_path": "attempts/a/observations.json", "child_exit_code": 0, "child_wall_seconds": 3.0}
    rewrite(cell, {**original, **additions})
    g.account_only(f.output, f.request, f.gates())
    results.append({"id": "GD-R2", "case": "no_fit_account_with_actual_corrected_numerical_field_names", "unexpectedly_accepted": True,
                    "injected_fields": sorted(additions), "real_controller_main_or_science_called": False})
finally:
    temporary.cleanup()

temporary, f = fictional_fixture()
try:
    f.put(f.output / "passes/account.json", {"phase": "account", "corrected_manifest_sha256": f.manifest["sha256"],
          "current_pass": [{"original_cell_id": "foreign_unknown", "status": "outcome_retained", "operation": "fit_corrected_inputs",
                            "scientific_status": "complete", "fit_dispatched": False, "record_sha256": "2" * 64}],
          "record_sha256": {"a": g.binding(f.output / "cells/a.json")["sha256"]}})
    g.account_only(f.output, f.request, f.gates())
    results.append({"id": "GD-R3", "case": "foreign_numeric_outcome_row_with_false_dispatch_flag", "unexpectedly_accepted": True,
                    "real_controller_main_or_science_called": False})
finally:
    temporary.cleanup()

temporary, f = fictional_fixture()
try:
    protected = f.root / "immutable_original_reproduction"
    protected.mkdir()
    (protected / "historical_proof.fake").write_text("FICTIONAL original reproduction metadata only\n")
    f.output = protected / "must_not_create"
    f.selection_value["paths"]["corrected_run"] = str(f.output)
    f.selection_value["paths"]["original_reproduction"] = str(protected)
    selection_path = Path(f.selection["path"])
    rewrite(selection_path, f.selection_value)
    f.selection = {"path": str(selection_path), "sha256": g.binding(selection_path)["sha256"]}
    f.request_path, f.request = f.make_request()
    f.args = f.arguments()
    before = g.tree(protected)
    calls = []
    def closed_fictional_return(argv, **kwargs):
        calls.append(argv)
        kwargs["stderr"].write(b"FICTIONAL no real child invocation\n")
        return SimpleNamespace(returncode=19)
    result = c.launch(g, f.args, f.gates(), invoke=closed_fictional_return, gates_factory=f.factory, testing=True)
    results.append({"id": "GD-R1", "case": "absent_corrected_run_inside_selection_original_reproduction", "unexpectedly_accepted": True,
                    "protected_directory_changed": before != g.tree(protected), "output_created": f.output.exists(),
                    "injected_child_call_count": len(calls), "injected_guard_returncode": result["guard_returncode"],
                    "real_controller_main_or_science_called": False})
    assert f.output.exists() and before != g.tree(protected)
finally:
    temporary.cleanup()

assert not any(name == "src" or name.startswith("src.") for name in sys.modules)
print(json.dumps({"status": "three_bounded_fictional_counterexamples_observed", "results": results,
                  "target_datasets_arrays_traces_process_queries_or_real_controller_dispatch": False}, sort_keys=True))
