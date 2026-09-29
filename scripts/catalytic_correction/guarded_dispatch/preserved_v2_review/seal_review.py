"""Seal this independent engineering review without importing target runtimes."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).absolute().parent
CARRIER = OUT.parent / "generator_correction_guarded_dispatch_v2"
PREP_SHA = "46a95785348e9f54379178caaf728fd863cccef3d133b2f5a3c8116aa5d9e9cc"
ORIGINAL = Path("/Users/macuser/bayes-cox-runs/ravi-main-integration-20260929/scripts/catalytic_correction")


def binding(path):
    assert path.is_absolute() and ".." not in path.parts
    assert not any(item.is_symlink() for item in (path, *path.parents))
    assert path.is_file()
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def read(path, expected=None):
    if expected is not None:
        assert binding(path)["sha256"] == expected
    value = json.loads(path.read_text())
    if "content_sha256" in value:
        assert value["content_sha256"] == digest({key: item for key, item in value.items() if key != "content_sha256"})
    return value


def write(name, value):
    assert "content_sha256" not in value
    raw = (json.dumps({**value, "content_sha256": digest(value)}, sort_keys=True, indent=2, allow_nan=False) + "\n").encode()
    with (OUT / name).open("xb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())


def evidence(path, first, last):
    lines = path.read_text().splitlines()
    return {"path": str(path), **binding(path), "line_start": first, "line_end": last,
            "lines": [{"line": n, "text": lines[n - 1]} for n in range(first, last + 1)]}


prep = read(CARRIER / "preparation_receipt.json", PREP_SHA)
assert len(prep["artifacts"]) == 78
assert {str(path.relative_to(CARRIER)) for path in CARRIER.rglob("*") if path.is_file()} == set(prep["artifacts"]) | {"preparation_receipt.json"}
assert sorted(str(path.relative_to(CARRIER)) for path in CARRIER.rglob("*") if path.is_dir()) == prep["artifact_directories"] == ["preserved_v1", "preserved_v1_review"]
for name, expected in prep["artifacts"].items():
    assert binding(CARRIER / name) == expected
initial = read(OUT / "delta_ast_and_initial_inventory.json")
expected_sources = initial["source_before"]
assert len(expected_sources) == 154
observed_sources = {path: binding(Path(path)) for path in expected_sources}
assert observed_sources == expected_sources
unit = read(OUT / "unit.invocation.json")
probe = read(OUT / "reuse_probe.invocation.json")
for label, capture in (("unit", unit), ("reuse_probe", probe)):
    assert type(capture["exit_code"]) is int and capture["exit_code"] == 0
    assert capture["source_before"] == capture["source_after"] == expected_sources
    assert capture["all_sources_unchanged"] is True
    for stream in ("stdout", "stderr"):
        assert binding(OUT / f"{label}.{stream}.log") == capture[f"raw_{stream}"]
assert "Ran 34 tests" in (OUT / "unit.stderr.log").read_text() and (OUT / "unit.stderr.log").read_text().endswith("\nOK\n")
observed = json.loads((OUT / "reuse_probe.stdout.log").read_text())
assert observed["fictional_only"] is True and observed["actual_controller_scientific_or_checker_calls"] == 0
assert len(observed["results"]) == 4 and all(row["unexpectedly_accepted"] is True and row["rejected"] is False for row in observed["results"])
producer = {}
for name in ("unit_attempt2", "ruff_attempt2", "compile_attempt1"):
    value = read(CARRIER / f"{name}.invocation.json")
    assert type(value["exit_code"]) is int and value["exit_code"] == 0
    assert value["source_start"] == value["source_finish"]
    assert value["actual_numerical_or_guarded_controller_dispatch"] is False
    for source, expected in value["source_finish"].items():
        assert binding(CARRIER / source) == expected
    for stream in ("stdout", "stderr"):
        assert binding(CARRIER / f"{name}.{stream}.log") == value[f"raw_{stream}"]
    producer[name] = {"invocation": binding(CARRIER / f"{name}.invocation.json"), "exit_code": value["exit_code"],
                      "argv": value["argv"], "raw_stdout": value["raw_stdout"], "raw_stderr": value["raw_stderr"],
                      "final_source_pins_match": True}
write("findings.json", {"schema_version": 1, "status": "independent_v2_delta_review_one_material_residual",
      "subject_preparation_receipt_sha256": PREP_SHA, "material_finding_count": 1,
      "findings": [{"id": "GD-R2a", "relation": "residual dependent decision consistency within original GD-R2",
          "severity": "material_before_guarded_dispatch_adoption", "observed_entry_point": "account_only on disposable fictional metadata",
          "guard_lines": [397, 444], "original_classifier_lines": [238, 255],
          "observed_counterexamples": observed["results"], "probe_invocation": binding(OUT / "reuse_probe.invocation.json"),
          "recommended_bounded_correction": {"reuse_missing_roles": [], "reuse_changed_roles": [], "reuse_generator_failures": {},
              "reuse_tuning_record_reused_sha256": None, "terminal_tuning_record_reused_sha256": None},
          "terminal_null_marker_conclusion": "source_only_not_independently_probed",
          "preserve_legitimate_terminal_missing_changed_roles": True,
          "preserve_original_reused_statuses": ["complete", "failed", "failed_diagnostics"],
          "actual_scientific_corruption_or_execution_claimed": False}],
      "v1_three_demonstrated_counterexamples_closed": True, "actual_scientific_or_adoption_approval": False})
write("source_evidence.json", {"schema_version": 1, "status": "exact_pinned_source_line_evidence",
      "evidence": [evidence(CARRIER / "guard_fit_dispatch.py", 343, 394),
                   evidence(CARRIER / "guard_fit_dispatch.py", 397, 444),
                   evidence(CARRIER / "guard_fit_dispatch.py", 447, 520),
                   evidence(CARRIER / "capture_guarded_dispatch.py", 60, 85),
                   evidence(CARRIER / "guard_fit_dispatch.py", 983, 1038),
                   evidence(ORIGINAL / "correction_fit_contracts.py", 191, 255),
                   evidence(ORIGINAL / "fit_controller.py", 187, 229),
                   evidence(ORIGINAL / "fit_controller.py", 272, 306),
                   evidence(CARRIER / "test_guarded_dispatch_regressions.py", 144, 184)]})
write("final_verification.json", {"schema_version": 1, "status": "all_captured_subject_sources_preserved_review_complete",
      "checked_at_utc": datetime.now(UTC).isoformat(), "subject_full_file_count": 79, "subject_bound_file_count": 78,
      "subject_directories": prep["artifact_directories"], "source_before": expected_sources, "source_after": observed_sources,
      "all154_sources_unchanged": True, "independent_unit_actual_exit_code": unit["exit_code"], "independent_unit_method_count": 34,
      "independent_reuse_probe_actual_exit_code": probe["exit_code"], "independent_reuse_probe_all_four_accepted": True,
      "producer_final_captures_checked": producer, "original23_method_ASTs": initial["original23_method_ASTs"],
      "changed_original_core_nodes": initial["changed_original_core_nodes"], "new_core_nodes": initial["new_core_nodes"],
      "changed_original_capture_nodes": initial["changed_original_capture_nodes"],
      "readonly_cli_byte_unchanged": True, "old6_import_pins_unchanged": True,
      "old20_source_pins_current_exact": True, "all_v1_41_and_prior_review_11_preserved_exact": True,
      "read_attempt_notes": [{"requested_name": "V2_DELTA.md", "observed_read_exit_code": 1, "actual_document_read_after": "V2_DELTA.json"},
                             {"requested_name": "test_guarded_dispatch_v2_regressions.py", "observed_read_exit_code": 1,
                              "actual_document_read_after": "test_guarded_dispatch_regressions.py"},
                             {"operation": "diff -u of differing V1/V2 sources", "observed_exit_code": 1, "meaning": "differences_found"}],
      "scope": {"new_external_review_writes_only": True, "fictional_import_tests_only": True,
                "actual_controller_scientific_or_checker_execution": False, "datasets_arrays_traces_read": False,
                "process_owner_queries": False, "resident_original_or_carrier_changes": False,
                "scientific_freeze_scope_release_retry_or_adoption_approval": False}})
assert {path: binding(Path(path)) for path in expected_sources} == expected_sources
artifacts = {str(path.relative_to(OUT)): binding(path) for path in sorted(OUT.rglob("*")) if path.is_file()}
assert len(artifacts) == 14 and not any(path.is_dir() for path in OUT.rglob("*"))
write("receipt.json", {"schema_version": 1, "status": "independent_v2_delta_review_sealed_one_material_residual",
      "sealed_at_utc": datetime.now(UTC).isoformat(), "owner": str(OUT), "subject": str(CARRIER),
      "subject_preparation_receipt": binding(CARRIER / "preparation_receipt.json"), "artifacts": artifacts,
      "artifact_directories": [], "material_finding_count": 1, "scientific_or_adoption_approval": False})
assert {str(path.relative_to(OUT)) for path in OUT.rglob("*")} == set(artifacts) | {"receipt.json"}
for name, expected in artifacts.items():
    assert binding(OUT / name) == expected
read(OUT / "receipt.json")
print(json.dumps({"receipt": str(OUT / "receipt.json"), **binding(OUT / "receipt.json"), "bound_files": len(artifacts),
                  "all_files": len(artifacts) + 1, "unchanged_sources": len(expected_sources), "material_findings": 1}, sort_keys=True))
