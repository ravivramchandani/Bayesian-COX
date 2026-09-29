"""Seal an external engineering review after immutable small-source rechecks."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

OUT = Path(__file__).absolute().parent


def binding(path):
    assert path.is_absolute() and ".." not in path.parts
    assert not any(item.is_symlink() for item in (path, *path.parents))
    raw = path.read_bytes()
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def read_sealed(path, expected):
    assert binding(path)["sha256"] == expected
    value = json.loads(path.read_text())
    assert value["content_sha256"] == digest({k: v for k, v in value.items() if k != "content_sha256"})
    return value


def write(name, value):
    assert "content_sha256" not in value
    value = {**value, "content_sha256": digest(value)}
    with (OUT / name).open("xb") as stream:
        stream.write((json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n").encode())


probe = json.loads((OUT / "probe.invocation.json").read_text())
assert probe["content_sha256"] == digest({k: v for k, v in probe.items() if k != "content_sha256"})
assert type(probe["exit_code"]) is int and probe["exit_code"] == 0 and probe["all_sources_unchanged"] is True
assert binding(OUT / "probe.stdout.log") == probe["raw_stdout"] and binding(OUT / "probe.stderr.log") == probe["raw_stderr"]
source_now = {path: binding(Path(path)) for path in probe["source_after"]}
assert source_now == probe["source_before"] == probe["source_after"]
references = {
    "generator_correction_dispatch_guard_design_v1": ("receipt.json", "be9b8f6346b796e7b44f7935a12808669a00e8dbd99c822b99ae794fc572fb82"),
    "generator_correction_dispatch_guard_independent_design_review_v1": ("receipt.json", "13983de7393b0bf5ae878a3a8324f6e70e4f3ccc377eb30b0265a0aa493bc264"),
    "generator_correction_dispatch_guard_transfer_compatibility_review_v1": ("receipt.json", "c53553f635dccd53c5725d88ca11b7bdc4187dd4db66ebbeafbe8759a6438c83"),
}
reference_files = {}
for directory, (receipt_name, expected) in references.items():
    root = OUT.parent / directory
    receipt = read_sealed(root / receipt_name, expected)
    expected_files = {str(root / name): value for name, value in receipt["artifacts"].items()}
    expected_files[str(root / receipt_name)] = binding(root / receipt_name)
    assert {str(path) for path in root.rglob("*") if path.is_file()} == set(expected_files)
    for path, value in expected_files.items():
        assert binding(Path(path)) == value, f"sealed reference artifact changed: {path}"
    reference_files.update(expected_files)
extra = {
    "/Users/macuser/bayes-cox-runs/ravi-main-integration-20260929/scripts/catalytic_correction/correction_fit_contracts.py": "83cb84002cd9dc447f70d9346baaba16197fa04d5a43e8b2fb500c2ce38f7fef",
    "/Users/macuser/bayes-cox-runs/ravi-main-integration-20260929/scripts/catalytic_correction/receiving/receiving_core.py": "9da62601b7f482be97f62de30566fe52eb916fa59d09995fe13654f700e20f3f",
}
for path, expected in extra.items():
    actual = binding(Path(path))
    assert actual["sha256"] == expected
    source_now[path] = actual
write("source_and_reference_recheck.json", {"schema_version": 1, "status": "sealed_subject_and_reference_bytes_rechecked", "captured_source_before_after_current_identical": True,
      "captured_source_files": probe["source_after"], "additional_pinned_stdlib_sources": {path: source_now[path] for path in extra},
      "sealed_reference_files": reference_files, "reference_file_count": len(reference_files),
      "actual_scientific_dispatch_or_target_metadata_read": False})
write("read_attempt_note.json", {"schema_version": 1, "status": "small_source_read_path_error_preserved", "actual_tool_exit_code": 2,
      "incorrect_guessed_path": "/Users/macuser/bayes-cox-runs/ravi-main-integration-20260929/scripts/catalytic_correction/contracts.py",
      "raw_error": "rg: /Users/macuser/bayes-cox-runs/ravi-main-integration-20260929/scripts/catalytic_correction/contracts.py: IO error for operation on /Users/macuser/bayes-cox-runs/ravi-main-integration-20260929/scripts/catalytic_correction/contracts.py: No such file or directory (os error 2)",
      "resolution": "rg --files located correction_fit_contracts.py; exact pinned source read and verified", "scientific_failure": False})
facts = json.loads((OUT / "probe.stdout.log").read_text())
assert facts["status"] == "three_bounded_fictional_counterexamples_observed" and len(facts["results"]) == 3
write("findings.json", {"schema_version": 1, "status": "material_contract_gaps_observed_requires_separate_corrected_carrier",
      "reviewed_preparation_sha256": "54b1eaa4b4da20719a63c55c2ad67b91fbd936b650dba16dfa52091ba1b5942b",
      "findings": [{"id": "GD-R1", "title": "Pre-write separation omits selection-only immutable roles", "source_lines": {"capture_guarded_dispatch.py": [[68,78]], "guard_fit_dispatch.py": [[276,279]], "reproduction_core.py": [[94,97]]}},
                   {"id": "GD-R2", "title": "Nominal account envelopes retain actual corrected-fit fields", "source_lines": {"guard_fit_dispatch.py": [[335,344]], "fit_controller.py": [[261,269]]}},
                   {"id": "GD-R3", "title": "False dispatch flag admits foreign or unbound account-pass rows", "source_lines": {"guard_fit_dispatch.py": [[351,355]], "fit_controller.py": [[191,204],[226,229],[272,276]]}}],
      "actual_probe_returncode": probe["exit_code"], "fictional_counterexamples": facts["results"],
      "actual_scientific_or_scope_freeze_adoption_release_approval": False})
for path, expected in {**source_now, **reference_files}.items():
    assert binding(Path(path)) == expected, f"review input changed before final seal: {path}"
artifacts = {str(path.relative_to(OUT)): binding(path) for path in sorted(OUT.iterdir()) if path.is_file()}
write("receipt.json", {"schema_version": 1, "status": "independent_guarded_dispatch_v1_implementation_review_sealed_with_material_findings", "created_at_utc": datetime.now(UTC).isoformat(),
      "reviewer_agent": "/root/dispatch_guard_independent_design_review", "reviewed_preparation_sha256": "54b1eaa4b4da20719a63c55c2ad67b91fbd936b650dba16dfa52091ba1b5942b",
      "findings": ["GD-R1", "GD-R2", "GD-R3"], "review_scope": "full static source review plus three disposable fictional metadata counterexamples",
      "actual_probe_returncode": probe["exit_code"], "actual_probe_invocation_binding": binding(OUT / "probe.invocation.json"),
      "all_49_captured_input_and_helper_files_unchanged": True, "all_reference_and_additional_pinned_sources_unchanged": True,
      "real_controller_scientific_checker_dataset_array_trace_process_git_remote_access": False,
      "main_original_or_carrier_edits": False, "actual_scientific_scope_freeze_adoption_or_release_approval": False,
      "artifacts": artifacts, "artifact_count": len(artifacts), "archival_file_count_including_receipt": len(artifacts)+1})
print(json.dumps({"receipt_path": str(OUT / "receipt.json"), "receipt_binding": binding(OUT / "receipt.json"),
                  "archival_file_count_including_receipt": len(artifacts)+1, "findings": ["GD-R1", "GD-R2", "GD-R3"],
                  "actual_probe_rc": probe["exit_code"], "captured_source_files_unchanged": len(probe["source_after"])}, sort_keys=True))
