"""Byte-bound correction reporting prerequisites; no scientific verification or fits."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

EVIDENCE = "post_hoc_rank_conditioned_correction_after_original_failures_known"
MIXED_STATUS = "mixed_original_corrected_grid_deep_verified_and_frozen_analysis_recomputed"
REPRO_ROUTES = {
    "reused_verified_original_numerical_reproduction",
    "new_corrected_numerical_reproduction",
    "terminal_no_fit_recipe_replay",
}
NUMERIC = ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS")
ARTIFACTS = {"dimension_ratios.csv", "descriptive_catalytic_pairs.csv", "report.json", "lineage.json"}
IMPLEMENTATION_FILES = {"support_core.py", "reporting.py", "corrected_pdf_qa.py",
                        "generate_corrected_reporting.py", "summarize_corrected_claims.py",
                        "replay_corrected_reporting.py"}
DEPENDENCY_PINS = {
    "frozen_reporting.py": "e8930fc49b1d5f81ae85d98fd1492a6a2209d31ddb8b66b7ff828d7d36bf89f8",
    "frozen_claims.py": "378861de7036344e0272da8b27701f1c96bad3558e88247dd18e00ac795d338d",
    "frozen_repeated_cv.py": "2cc04e2af5f3685c07cee5e79ce83fe5fd7df2f772dba3d84f43562236ab8004",
    "scope.json": "1cbdacdbd29a51b00011be33933efd84448b28afc58386ac90b5d31142e8f59f",
    "frozen_pdf_qa.py": "be849a4090be1505a17b4ebcd6c07fa3919ca5e82dc38431ad5ad83c53eca1f2",
    "frozen_qa_transfer.py": "49be829acf5efd8e18500bf59c6c4ba619d5f730c52d8f76e74e13b4cff95506",
}
RENDERER_SHA = "2155dbe1e1f54603f3711deadd79c6e1aed3917b07a3fe8e58e08f4a6ad85cd2"
RENDER_ADAPTER_SHA = "a166ded834ec7feefcf105303724c6d649147e3e6062a76fed3f71bed6022332"


def require(condition: bool, message: str) -> None:
    """Reject missing or inconsistent evidence before successful publication."""
    if not condition:
        raise ValueError(message)


def safe(path: Path) -> Path:
    """Require an absolute path with no symlink ancestor or traversal component."""
    value = path.absolute()
    require(".." not in value.parts, "path traversal is forbidden")
    for parent in (value, *value.parents):
        require(not parent.is_symlink(), "linked evidence or output path: " + str(parent))
    return value


def sha_bytes(value: bytes) -> str:
    """Hash exact bytes, distinguishing byte pins from internal JSON seals."""
    return hashlib.sha256(value).hexdigest()


def json_bytes(value: Any) -> bytes:
    """Encode deterministic strict JSON with a trailing newline."""
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode()


def canonical(value: Any) -> str:
    """Mirror frozen canonical scientific-content encoding."""
    return sha_bytes(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode())


def seal(value: dict[str, Any]) -> dict[str, Any]:
    """Seal an unsealed mapping without mutating its caller."""
    require("content_sha256" not in value, "cannot silently replace an existing content seal")
    return {**value, "content_sha256": canonical(value)}


def strict_json(raw: bytes) -> Any:
    """Reject duplicate keys, nonstandard constants and overflowing numbers."""
    def unique(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        output = {}
        for key, value in rows:
            require(key not in output, "duplicate JSON key: " + key)
            output[key] = value
        return output

    def number(text: str) -> float:
        value = float(text)
        require(math.isfinite(value), "nonfinite JSON number")
        return value

    def invalid(text: str) -> None:
        raise ValueError("nonstandard JSON constant: " + text)
    return json.loads(raw, object_pairs_hook=unique, parse_float=number, parse_constant=invalid)


def content(value: dict[str, Any], field: str = "content_sha256") -> None:
    """Require an exact stored internal content seal."""
    require(isinstance(value, dict) and value.get(field) == canonical({k: v for k, v in value.items() if k != field}),
            "stored internal content seal differs: " + field)


def child(root: Path, relative: str) -> Path:
    """Resolve only a strictly relative inventory member inside its explicit root."""
    require(isinstance(relative, str), "inventory path must be a string")
    member = Path(relative)
    require(relative and not member.is_absolute() and ".." not in member.parts, "unsafe inventory member")
    path = safe(root / member)
    require(path.is_relative_to(safe(root)), "inventory member escapes root")
    return path


class Snapshot:
    """Bind portable logical roles to actual bytes and recheck before success."""

    def __init__(self) -> None:
        self.bindings: dict[str, dict[str, Any]] = {}

    def capture(self, logical: str, path: Path, expected: str | None = None) -> bytes:
        """Read a unique regular-file role and optionally check a byte pin."""
        require(logical not in self.bindings, "duplicate input logical role: " + logical)
        path = safe(path)
        require(path.is_file(), "missing regular input: " + str(path))
        before = path.stat()
        raw = path.read_bytes()
        after = path.stat()
        require((before.st_size, before.st_mtime_ns, before.st_ino) ==
                (after.st_size, after.st_mtime_ns, after.st_ino), "input changed while reading")
        digest = sha_bytes(raw)
        require(expected is None or digest == expected, "input byte pin differs: " + logical)
        self.bindings[logical] = {"path": path, "sha256": digest, "bytes": len(raw)}
        return raw

    def read(self, logical: str, path: Path, expected: str | None = None, *, field: str | None = None) -> Any:
        """Read strict JSON and optionally validate its internal seal."""
        value = strict_json(self.capture(logical, path, expected))
        if field is not None:
            content(value, field)
        return value

    def portable(self) -> dict[str, str]:
        """Return host-independent logical role hashes."""
        return {name: value["sha256"] for name, value in sorted(self.bindings.items())
                if not name.startswith("invocation/")}

    def recheck(self) -> None:
        """Refuse changed bytes even if a result file already exists."""
        for name, value in self.bindings.items():
            require(safe(value["path"]).is_file() and sha_bytes(value["path"].read_bytes()) == value["sha256"],
                    "input changed before successful return: " + name)


def bind_map(snapshot: Snapshot, logical: str, root: Path, records: dict[str, Any]) -> None:
    """Check every declared artifact using its relative portable location."""
    require(isinstance(records, dict), "artifact inventory is not a mapping")
    for name, binding in sorted(records.items()):
        digest = binding if isinstance(binding, str) else binding["sha256"]
        raw = snapshot.capture(logical + "/" + name, child(root, name), digest)
        if isinstance(binding, dict):
            require(type(binding.get("bytes")) is int and len(raw) == binding["bytes"], "artifact size differs")


def supplied(request: dict[str, Any], name: str, snapshot: Snapshot, *, field: str | None = "content_sha256") -> Any:
    """Read an explicitly selected file role, never a historical absolute path."""
    item = request["files"][name]
    require(set(item) == {"path", "sha256"}, "file role has unsupported fields: " + name)
    return snapshot.read("inputs/" + name, Path(item["path"]), item["sha256"], field=field)


def bind_preparation(request: dict[str, Any], snapshot: Snapshot) -> None:
    """Pin and recheck the tested own implementation and dependency inventory."""
    item = request["preparation_receipt"]
    own = Path(__file__).absolute().parent
    receipt = snapshot.read("preparation/receipt.json", Path(item["path"]), item["sha256"], field="content_sha256")
    require(receipt["status"] == "corrected_reporting_qa_adapters_prepared"
            and receipt["actual_scientific_or_visual_execution"] is False, "tested reporting/QA preparation required")
    require(set(receipt["implementation_source_sha256"]) == IMPLEMENTATION_FILES
            and set(receipt["dependency_source_sha256"]) == set(DEPENDENCY_PINS), "preparation source scope differs")
    for name, digest in receipt["implementation_source_sha256"].items():
        require(Path(name).name == name, "unsafe preparation source name")
        snapshot.capture("preparation/implementation/" + name, own / name, digest)
    for name, digest in DEPENDENCY_PINS.items():
        require(receipt["dependency_source_sha256"][name] == digest, "frozen support dependency pin differs")
        snapshot.capture("preparation/dependency/" + name, own / name, digest)


def runtime(python: Path) -> None:
    """Check the actual interpreter and all five single-thread environment values."""
    require(python.is_file() and os.path.samefile(python, sys.executable), "actual locked interpreter differs")
    require(all(os.environ.get(name) == "1" for name in NUMERIC), "five numeric thread variables must equal one")


def load_module(path: Path, expected: str, name: str, snapshot: Snapshot) -> ModuleType:
    """Execute only captured pinned support bytes under a private module name."""
    raw = snapshot.capture("preparation/" + path.name, path, expected)
    require(name not in sys.modules, "private support module namespace occupied")
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None, "cannot load support module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        exec(compile(raw, str(path), "exec"), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def dependencies(snapshot: Snapshot, *, interval: bool = False, qa_render: bool = False) -> dict[str, Any]:
    """Load frozen reporting/claim routines; image/math imports are explicit."""
    own = Path(__file__).absolute().parent
    require(not any(name == "src" or name.startswith("src.") for name in sys.modules), "foreign scientific namespace")
    result = {}
    names = {"reporting": "frozen_reporting.py", "claims": "frozen_claims.py", "roster": "frozen_qa_transfer.py"}
    if interval:
        names["interval"] = "frozen_repeated_cv.py"
    if qa_render:
        names["qa"] = "frozen_pdf_qa.py"
    for role, filename in names.items():
        # Every actual CLI runs in a fresh process; fixture callers remove their
        # own private modules after each synthetic test.
        result[role] = load_module(own / filename, DEPENDENCY_PINS[filename], "_corrected_support_" + role, snapshot)
    result["scope"] = snapshot.read("preparation/scope.json", own / "scope.json", DEPENDENCY_PINS["scope.json"])
    return result


def validate_capture(request: dict[str, Any], completion_sha: str, snapshot: Snapshot) -> dict[str, Any]:
    """Require actual rc0 raw logs/capture, rather than a self-written science marker."""
    receipt = supplied(request, "source_capture", snapshot)
    path = safe(Path(request["files"]["source_capture"]["path"]))
    require(path.name.endswith(".receipt.json"), "capture receipt filename differs")
    prefix = path.name.removesuffix(".receipt.json")
    require(receipt["status"] == "mixed_verification_actual_rc0_captured" and type(receipt["exit_code"]) is int
            and receipt["exit_code"] == 0 and receipt["completion_sha256"] == completion_sha
            and receipt["summary"]["status"] == MIXED_STATUS and receipt["summary"]["verified_logical_cells"] == 1625
            and receipt["summary"]["programme_complete"] is False, "actual complete mixed-verifier rc0 capture missing")
    wanted = {prefix + suffix for suffix in (".stdout.log", ".stderr.log", ".attempt.json")}
    require(set(receipt["artifacts"]) == wanted and
            {p.name for p in path.parent.glob(prefix + ".*")} == wanted | {path.name}, "capture file inventory differs")
    bind_map(snapshot, "source_capture", path.parent, receipt["artifacts"])
    attempt = strict_json((path.parent / (prefix + ".attempt.json")).read_bytes())
    content(attempt)
    require(type(attempt["exit_code"]) is int and attempt["exit_code"] == 0 and attempt["launch_error"] is None
            and sha_bytes((path.parent / (prefix + ".attempt.json")).read_bytes()) == receipt["invocation_attempt_sha256"],
            "actual mixed invocation does not attest successful execution")
    for role in ("stdout", "stderr"):
        name = prefix + "." + role + ".log"
        require(Path(receipt[role + "_path"]).name == name and receipt[role + "_sha256"] ==
                attempt[role + "_sha256"] == receipt["artifacts"][name]["sha256"], "actual captured log bytes differ")
    require(strict_json((path.parent / (prefix + ".stdout.log")).read_bytes().splitlines()[-1]) == receipt["summary"],
            "actual raw stdout summary differs")
    return receipt


def load_mixed(request: dict[str, Any], snapshot: Snapshot, reporting: Any) -> dict[str, Any]:
    """Bind the own complete1625 mixed certificate and every small reporting source."""
    root = safe(Path(request["roots"]["mixed_verified"]))
    require(root.is_dir(), "mixed verified root missing")
    require(Path(request["files"]["mixed_completion"]["path"]) == root / "completion.json", "completion root differs")
    completion = supplied(request, "mixed_completion", snapshot)
    require(completion["status"] == MIXED_STATUS and completion["evidence_status"] == EVIDENCE
            and completion["planned_logical_cells"] == completion["verified_logical_cells"] == 1625
            and completion["own_mixed_lineage_certificate"] is True
            and completion["original855_certificate_inherited"] is False
            and completion["original_and_primary_negative_findings_preserved"] is True
            and completion["programme_complete"] is False, "own complete mixed certificate absent")
    completion_sha = request["files"]["mixed_completion"]["sha256"]
    validate_capture(request, completion_sha, snapshot)
    manifest = snapshot.read("mixed/manifest.json", root / "manifest.json", completion["manifest_sha256"], field="content_sha256")
    require(manifest["evidence_status"] == EVIDENCE and manifest["planned_fits"] == 1625
            and manifest["source_bindings"] == completion["source_bindings"], "mixed manifest lineage differs")
    expected = {"cells/" + identity + ".json" for identity in reporting.expected_extension()}
    require(set(completion["cell_sha256"]) == expected
            and {str(p.relative_to(root)) for p in (root / "cells").iterdir()} == expected, "mixed compatible-cell grid differs")
    cells = [snapshot.read("mixed/" + name, child(root, name), digest, field="cell_content_sha256")
             for name, digest in sorted(completion["cell_sha256"].items())]
    refs = reporting.extension_refs(cells, manifest)
    require(dict(Counter(cell["status"] for cell in cells)) == completion["mixed_view_status_counts"], "mixed status accounting differs")
    require(set(completion["aggregate_sha256"]) == {"aggregates/paired_families.json", "aggregates/rq2_effects.json",
                                                   "aggregates/decision_curves.json"}, "mixed aggregates differ")
    aggregates = {Path(name).name: snapshot.read("mixed/" + name, child(root, name), digest)
                  for name, digest in sorted(completion["aggregate_sha256"].items())}
    for role in ("lineage_sha256", "check_sha256", "initial_invocation_metadata_sha256"):
        bind_map(snapshot, "mixed", root, completion[role])
    for name, key in (("comparison_accounting.json", "comparison_accounting_sha256"),
                      ("reference_verification.json", "reference_verification_sha256"),
                      ("render_input.json", "render_input_sha256")):
        snapshot.read("mixed/" + name, root / name, completion[key], field="content_sha256")
    accounting = strict_json((root / "comparison_accounting.json").read_bytes())
    require(accounting["all_original_findings_retained_separately"] is True
            and len(accounting["cells"]) == 1625
            and {row["original_cell_id"] for row in accounting["cells"]} == set(refs)
            and accounting["counts"]["original_status_counts"] == completion["original_status_counts"]
            and accounting["counts"]["corrected_status_counts"] == completion["mixed_view_status_counts"]
            and accounting["counts"]["operation_counts"] == completion["operation_counts"], "original/corrected accounting missing")
    return {"root": root, "completion": completion, "completion_sha256": completion_sha,
            "manifest": manifest, "cells": cells, "refs": refs, "aggregates": aggregates, "accounting": accounting}


def validate_reproduction(request: dict[str, Any], mixed: dict[str, Any], snapshot: Snapshot) -> dict[str, Any]:
    """Bind actual selected-union outcomes without claiming all1625 numerical refits."""
    root = safe(Path(request["roots"]["reproduction"]))
    selection = supplied(request, "selection", snapshot)
    selected_pass = supplied(request, "selected_pass", snapshot)
    require(Path(request["files"]["selection"]["path"]) == root / "selection.json"
            and Path(request["files"]["selected_pass"]["path"]).parent == root / "passes", "selected proof root differs")
    manifest = supplied(request, "correction_manifest", snapshot)
    source = mixed["completion"]["source_bindings"]
    require(request["files"]["correction_manifest"]["sha256"] == source["corrected_manifest_sha256"], "correction manifest byte pin differs")
    original = sorted(identity for identity in mixed["refs"] if "__r01f01__" in identity)
    selected = sorted(set(original) | set(manifest["pilot_cells"]))
    selection_sha = request["files"]["selection"]["sha256"]
    require(len(original) == 92 and selection["status"] == "reviewed_corrected_reproduction_selection"
            and selection["original_selected_cells"] == original and selection["pilot_cells"] == manifest["pilot_cells"]
            and selection["selected_cells"] == selected
            and selection["corrected_manifest_sha256"] == source["corrected_manifest_sha256"]
            and selection["correction_freeze_sha256"] == source["freeze_sha256"]
            and selection["input_inventory_sha256"] == source["input_inventory_sha256"], "frozen selected union differs")
    require(selected_pass["status"] == "all_selected_reproduction_outcomes_accounted"
            and selected_pass["selection_sha256"] == selection_sha
            and selected_pass["scheduled_selected_cells"] == selected_pass["accounted_selected_cells"] == len(selected)
            and selected_pass["whole_1625_grid_numerically_reproduced"] is False
            and [row["original_cell_id"] for row in selected_pass["outcomes"]] == selected, "selected production pass incomplete")
    require(not (root / "controller.claim.json").exists() and (root / "claims").is_dir()
            and not any((root / "claims").iterdir()), "selected reproduction still owned")
    require({p.name for p in (root / "cells").iterdir()} == {identity + ".json" for identity in selected}, "selected record scope differs")
    counts = dict.fromkeys(sorted(REPRO_ROUTES), 0)
    for row in selected_pass["outcomes"]:
        require(row["status"] in REPRO_ROUTES, "pending/failed selected reproduction is not complete")
        record = snapshot.read("reproduction/cells/" + row["original_cell_id"], root / "cells" / (row["original_cell_id"] + ".json"),
                               row["record_sha256"], field="content_sha256")
        require(record["status"] == row["status"] and record["selection_sha256"] == selection_sha, "selected outcome/record differs")
        bind_map(snapshot, "reproduction", root, record["artifacts"])
        counts[row["status"]] += 1
    if selected_pass.get("controller_environment_artifacts"):
        bind_map(snapshot, "reproduction/environment", root, selected_pass["controller_environment_artifacts"])
    return {"selection_sha256": selection_sha, "selected_pass_sha256": request["files"]["selected_pass"]["sha256"],
            "scheduled_selected_cells": len(selected), "accounted_selected_cells": len(selected), "route_counts": counts,
            "whole_1625_grid_numerically_reproduced": False,
            "boundary": "actual recorded selected pass and artifact bytes; deep numerical comparison is a separate receiving gate"}


def write_bytes_new(path: Path, raw: bytes) -> None:
    """Fsync/close an exclusive temporary file, then publish without overwrite."""
    safe(path)
    require(path.parent.is_dir(), "output parent missing")
    fd, temporary = tempfile.mkstemp(prefix=".support-pending-", dir=path.parent)
    pending = Path(temporary)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(pending, path)
    finally:
        pending.unlink(missing_ok=True)


def write_new(path: Path, value: Any) -> None:
    """Publish one exact JSON file, retaining existing files on collision."""
    write_bytes_new(path, json_bytes(value))


def new_directory(output: Path, immutable: list[Path]) -> None:
    """Refuse collisions and overlaps before creating a new external directory."""
    output = safe(output)
    require(output.parent.is_dir() and not output.exists()
            and all(not output.is_relative_to(safe(root)) and not safe(root).is_relative_to(output) for root in immutable),
            "output exists or overlaps immutable evidence/source")
    output.mkdir()


def timestamp(text: str) -> str:
    """Validate a timezone-aware real named-review timestamp."""
    require(isinstance(text, str), "review timestamp is not text")
    value = datetime.fromisoformat(text.replace("Z", "+00:00"))
    require(value.tzinfo is not None and value.utcoffset() is not None, "review timestamp needs timezone")
    return value.isoformat()


def invocation(request_sha: str) -> dict[str, Any]:
    """Keep actual host command metadata separate from portable reporting artifacts."""
    return {"request_sha256": request_sha, "argv": list(sys.argv), "completed_at_utc": datetime.now(UTC).isoformat(),
            "python_executable": sys.executable, "numeric_thread_environment": {name: os.environ.get(name) for name in NUMERIC},
            "actual_cli_rc0": "caller_must_capture_actual_process_return_code"}
