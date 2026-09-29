"""Write-once descriptive reporting supplement from complete, byte-bound evidence.

No fitting, trace hashing, metric rescoring, formal testing, result modification,
visual review or release certification occurs here.  All 1,625 extension cells
and the unchanged 450-cell original primary record are prerequisites.  Replay
recomputes deterministic reporting bytes and writes a new receipt only to stdout.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Callable, Sequence

sys.dont_write_bytecode = True

Json = dict[str, Any]
Effect = Callable[..., Any]
PRODUCTION_COMMIT = "119476fef55b1eeb690527f234c1423440720d45"
ANALYSIS_COMMIT = "8551d326b02bfe88915cfd9eb50c6ca8e5690e3a"
CLAIM_SHA = "378861de7036344e0272da8b27701f1c96bad3558e88247dd18e00ac795d338d"
INTERVAL_SHA = "2cc04e2af5f3685c07cee5e79ce83fe5fd7df2f772dba3d84f43562236ab8004"
SCOPE_SHA = "1cbdacdbd29a51b00011be33933efd84448b28afc58386ac90b5d31142e8f59f"
PRIMARY_PINS = {
    "manifest.json": "2a1817365675aa179174b5edf5b3da67bbcb2be1b2eb4143347e4b295052ce02",
    "completion.json": "44d5d6e2c3cf4d0350c3bc8cb27291436c9934b219c4c895cb139525e6fa25f6",
}
DATASETS = ("gbsg2", "whas500", "metabric")
CATALYTIC = ("catalytic_fixed", "catalytic_adaptive", "catalytic_wme")
ORIGINAL = (
    "cox_ph",
    "random_survival_forest",
    "deepsurv",
    "bayesian_normal",
    "bayesian_horseshoe",
    "bayesian_spike_slab",
)
EXTRA = ("ridge", "lasso", "elastic_net", "pv_horseshoe")
NEW = EXTRA + CATALYTIC
CONDITIONS = ("fraction_0.25", "fraction_0.50", "fraction_0.75", "admin_q0.75", "admin_q0.50")
STATUSES = {"complete", "failed", "failed_diagnostics"}
CORE_FILES = ("dimension_ratios.csv", "descriptive_catalytic_pairs.csv", "report.json")
ARTIFACT_FILES = CORE_FILES + ("lineage.json", "receipt.json")
DIMENSION_FIELDS = (
    "cell_id",
    "dataset",
    "setting",
    "model",
    "condition",
    "repeat",
    "fold",
    "status",
    "n_train",
    "n_validation",
    "events_train",
    "p",
    "p_available",
    "p_over_n_train",
    "events_over_p",
    "ratio_availability",
)
COMPARISON_FIELDS = (
    "comparison_id",
    "dataset",
    "setting",
    "left",
    "right",
    "left_source_role",
    "right_source_role",
    "right_identity",
    "expected_pairs",
    "n_pairs",
    "missing_pairs",
    "coverage",
    "interval_status",
    "mean_difference",
    "standard_deviation",
    "corrected_standard_error",
    "confidence_lower",
    "confidence_upper",
    "confidence_level",
    "degrees_of_freedom",
    "test_train_ratio",
)


def require(condition: bool, message: str) -> None:
    """Reject an incomplete or inconsistent prerequisite before publication."""
    if not condition:
        raise ValueError(message)


def sha_bytes(data: bytes) -> str:
    """Hash exact UTF-8 or file bytes."""
    return hashlib.sha256(data).hexdigest()


def json_bytes(value: Any) -> bytes:
    """Encode stable, strict, human-readable JSON with one trailing newline."""
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def canonical_sha(value: Any) -> str:
    """Mirror the frozen source's canonical internal-content encoding."""
    return sha_bytes(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    )


def strict_json(data: bytes, label: str) -> Any:
    """Reject duplicate keys, nonstandard constants and overflowing JSON floats."""

    def unique(pairs: list[tuple[str, Any]]) -> Json:
        result: Json = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key in {label}: {key}")
            result[key] = value
        return result

    def number(value: str) -> float:
        result = float(value)
        require(math.isfinite(result), f"nonfinite JSON number in {label}")
        return result

    def constant(value: str) -> None:
        raise ValueError(f"nonstandard JSON constant in {label}: {value}")

    return json.loads(data.decode("utf-8"), object_pairs_hook=unique, parse_float=number, parse_constant=constant)


def verify_content(record: Json, field: str) -> None:
    """Verify an embedded content digest without mutating its record."""
    require(
        record.get(field) == canonical_sha({k: v for k, v in record.items() if k != field}),
        f"content digest mismatch: {field}",
    )


def file_bytes(path: Path) -> bytes:
    """Read a regular non-symlink input; never follow a file alias."""
    require(path.is_file() and not path.is_symlink(), f"missing or linked input: {path}")
    return path.read_bytes()


@dataclass(frozen=True)
class Binding:
    """A stable logical file ID paired with a host-local read location."""

    logical: str
    path: Path
    sha256: str


class Snapshot:
    """Bind every small input byte and recheck it before any output creation."""

    def __init__(self) -> None:
        self.bindings: dict[str, Binding] = {}

    def capture(self, logical: str, path: Path, expected: str | None = None) -> bytes:
        """Capture a unique logical role, optionally enforcing a frozen byte pin."""
        require(logical not in self.bindings, f"duplicate source role: {logical}")
        data = file_bytes(path)
        digest = sha_bytes(data)
        require(expected is None or digest == expected, f"changed input bytes: {logical}")
        self.bindings[logical] = Binding(logical, path, digest)
        return data

    def read(self, logical: str, path: Path, expected: str | None = None) -> Any:
        """Capture and parse strict JSON without trusting a filename alone."""
        return strict_json(self.capture(logical, path, expected), logical)

    def recheck(self) -> None:
        """Fail if an input changed while the read-only report was calculated."""
        for binding in self.bindings.values():
            require(
                sha_bytes(file_bytes(binding.path)) == binding.sha256,
                f"input changed during reporting: {binding.logical}",
            )

    def portable(self) -> Json:
        """Return deterministic logical IDs and hashes, never absolute paths."""
        return {name: binding.sha256 for name, binding in sorted(self.bindings.items())}


def inventory_path(root: Path, relative: str) -> Path:
    """Resolve a strictly relative inventory member contained in its root."""
    item = Path(relative)
    require(not item.is_absolute() and ".." not in item.parts, f"unsafe inventory member: {relative}")
    path = root / item
    require(path.resolve().is_relative_to(root.resolve()), f"inventory member escapes root: {relative}")
    return path


def load_pinned_module(path: Path, data: bytes, name: str) -> ModuleType:
    """Import precisely the already captured source bytes, without bytecode writes."""
    spec = importlib.util.spec_from_file_location(name, path)
    require(spec is not None, f"cannot import pinned dependency: {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(data, str(path), "exec"), module.__dict__)
    return module


def cell_id(dataset: str, setting: str, repeat: int, fold: int, model: str, condition: str) -> str:
    """Reproduce the exact sealed extension job identity."""
    return f"{dataset}__{setting}__r{repeat:02}f{fold:02}__{model}__{condition}"


def expected_extension() -> dict[str, tuple[str, str, int, int, str, str]]:
    """Build the frozen 1,625 identities without datasets, fitting or random draws."""
    result = {}
    for dataset in DATASETS + ("metabric_matched",):
        settings = ("clinical", "expression") if dataset == "metabric_matched" else ("clinical",)
        models = ORIGINAL + NEW if dataset == "metabric_matched" else NEW
        for repeat in range(1, 6):
            for fold in range(1, 6):
                for setting in settings:
                    for model in models:
                        values = dataset, setting, repeat, fold, model, "full"
                        result[cell_id(*values)] = values
                if dataset != "metabric_matched" and fold <= 2:
                    for condition in CONDITIONS:
                        for model in CATALYTIC:
                            values = dataset, "clinical", repeat, fold, model, condition
                            result[cell_id(*values)] = values
    require(len(result) == 1625, "internal extension roster is not 1,625")
    return result


def expected_scope_rows() -> list[Json]:
    """Freeze 63 clinical plus 60 matched comparator rows in the agreed order."""
    rows = []
    settings = [(d, "clinical") for d in DATASETS] + [("metabric_matched", s) for s in ("clinical", "expression")]
    for dataset, setting in settings:
        comparators = ORIGINAL + EXTRA if dataset == "metabric_matched" else ORIGINAL[:3] + EXTRA
        for left in CATALYTIC:
            for right in comparators:
                role = "primary" if dataset != "metabric_matched" and right in ORIGINAL[:3] else "extension"
                identity = (
                    "unchanged_original_primary_benchmark"
                    if role == "primary"
                    else "matched_extension_arm"
                    if dataset == "metabric_matched"
                    else "full_clinical_extension_arm"
                )
                rows.append(
                    {
                        "comparison_id": f"{dataset}__{setting}__{left}__vs__{right}",
                        "dataset": dataset,
                        "setting": setting,
                        "left": left,
                        "right": right,
                        "left_source_role": "extension",
                        "right_source_role": role,
                        "right_identity": identity,
                        "condition": "full",
                    }
                )
    return rows


def check_scope(scope: Json) -> None:
    """Check the byte-pinned reporting roster against its independent definition."""
    require(scope.get("rows") == expected_scope_rows() and len(scope["rows"]) == 123, "reporting roster changed")
    require(
        scope.get("production_commit") == PRODUCTION_COMMIT and scope.get("analysis_commit") == ANALYSIS_COMMIT,
        "reporting source commits changed",
    )
    require(
        scope.get("expected_extension_cells") == 1625 and scope.get("expected_primary_cells") == 450,
        "reporting prerequisites changed",
    )


def count(value: Any, label: str, *, minimum: int = 0) -> int:
    """Require an actual integer count, rejecting booleans and invented denominators."""
    require(type(value) is int and value >= minimum, f"invalid count {label}: {value!r}")
    return value


def finite(value: Any, label: str, *, positive: bool = False) -> float:
    """Validate a reported scalar without silently coercing strings or nulls."""
    require(type(value) in (int, float) and math.isfinite(value), f"nonfinite or nonnumeric {label}")
    require(not positive or value > 0, f"nonpositive {label}")
    return float(value)


def patients(value: Any, label: str) -> list[Any]:
    """Require exact, unique patient identifiers, retaining their original order/type."""
    require(
        isinstance(value, list) and all(type(v) in (str, int) and v != "" for v in value),
        f"invalid patient identifiers: {label}",
    )
    require(len(value) == len(set(value)), f"duplicate patient identifiers: {label}")
    return value


def numeric_vector(value: Any, label: str, length: int, *, binary: bool = False) -> list[Any]:
    """Validate finite outcome/evaluation arrays and their observed lengths."""
    require(isinstance(value, list) and len(value) == length, f"missing or wrong length: {label}")
    for item in value:
        finite(item, label, positive=not binary)
        require(not binary or item in (0, 1), f"nonbinary event: {label}")
    return value


def validate_record(cell: Json, label: str) -> None:
    """Check memberships/counts for failures and saved outcome/grids for accepted cells."""
    require(cell.get("status") in STATUSES, f"unexpected status: {label}")
    n_train = count(cell.get("n_train"), f"{label}/n_train", minimum=1)
    n_validation = count(cell.get("n_validation"), f"{label}/n_validation", minimum=1)
    events = count(cell.get("events_train"), f"{label}/events_train")
    require(events <= n_train, f"events exceed training count: {label}")
    train = patients(cell.get("train_subject_ids"), f"{label}/train")
    validation = patients(cell.get("validation_subject_ids"), f"{label}/validation")
    require(len(train) == n_train and len(validation) == n_validation, f"membership count mismatch: {label}")
    require(set(train).isdisjoint(validation), f"training/validation patient overlap: {label}")
    if cell.get("training_membership_sha256") is not None:
        require(cell["training_membership_sha256"] == canonical_sha(train), f"training digest mismatch: {label}")
    if cell.get("p") is not None:
        count(cell["p"], f"{label}/p", minimum=1)
        if cell.get("events_per_coefficient") is not None:
            recorded = finite(cell["events_per_coefficient"], f"{label}/events_per_coefficient")
            require(recorded == events / cell["p"], f"stored events/p differs from counts: {label}")
    if cell["status"] != "complete":
        return
    score = finite(cell.get("metrics", {}).get("ibs"), f"{label}/IBS")
    require(score >= 0, f"negative IBS: {label}")
    pred = cell.get("predictions", {})
    require(
        patients(pred.get("subject_ids"), f"{label}/predictions") == validation,
        f"prediction patient order differs from validation membership: {label}",
    )
    for name, length in (
        ("training_time", n_train),
        ("training_event", n_train),
        ("observed_time", n_validation),
        ("observed_event", n_validation),
    ):
        numeric_vector(pred.get(name), f"{label}/{name}", length, binary=name.endswith("event"))
    require(sum(pred["training_event"]) == events, f"training events differ from saved outcomes: {label}")
    for name in ("horizons", "ibs_grid"):
        length = len(pred.get(name, []))
        require(length >= 2, f"missing evaluation grid: {label}/{name}")
        vector = numeric_vector(pred.get(name), f"{label}/{name}", length)
        require(all(b > a for a, b in zip(vector, vector[1:])), f"evaluation grid is not increasing: {label}/{name}")


@dataclass(frozen=True)
class CellRef:
    """An unmodified source cell with its stable logical location and explicit role."""

    role: str
    relative: str
    record: Json

    @property
    def logical(self) -> str:
        """Return a portable lineage link independent of the original Mac path."""
        return f"{self.role}/{self.relative}"


def extension_refs(cells: list[Json], manifest: Json) -> dict[str, CellRef]:
    """Require every frozen identity exactly once and match manifest memberships."""
    expected = expected_extension()
    plan = manifest.get("plan", [])
    require(len(plan) == 1625 and len({r["cell_id"] for r in plan}) == 1625, "missing or duplicate planned cells")
    plans = {r["cell_id"]: r for r in plan}
    require(set(plans) == set(expected), "manifest differs from frozen extension grid")
    require(len(cells) == 1625, "partial extension input")
    refs: dict[str, CellRef] = {}
    for cell in cells:
        identity = cell.get("cell_id")
        require(identity in expected and identity not in refs, f"unexpected or duplicate extension cell: {identity}")
        observed = tuple(cell.get(k) for k in ("dataset", "setting", "repeat", "fold", "model_key", "condition"))
        require(observed == expected[identity], f"extension cell fields differ from its identity: {identity}")
        require(type(cell["repeat"]) is int and type(cell["fold"]) is int, f"noninteger fold identity: {identity}")
        require(cell.get("evidence_status") == "post_hoc_extension", f"extension evidence label missing: {identity}")
        verify_content(cell, "cell_content_sha256")
        validate_record(cell, identity)
        planned = plans[identity]
        require(
            planned.get("train_sha256") == canonical_sha(cell["train_subject_ids"])
            and planned.get("validation_sha256") == canonical_sha(cell["validation_subject_ids"]),
            f"manifest patient membership differs: {identity}",
        )
        require(
            planned.get("censoring_cutoff") == cell.get("censoring_cutoff"), f"censoring cutoff differs: {identity}"
        )
        refs[identity] = CellRef("extension", f"cells/{identity}.json", cell)
    require(set(refs) == set(expected), "extension grid is incomplete")
    return refs


def expected_primary() -> dict[str, tuple[str, str, int, int]]:
    """Enumerate the unchanged 450-cell primary record, including failed horseshoes."""
    return {
        f"cells/{d}/repeat_{r:02}_fold_{f:02}/{m}.json": (d, m, r, f)
        for d in DATASETS
        for r in range(1, 6)
        for f in range(1, 6)
        for m in ORIGINAL
    }


def primary_refs(root: Path, snapshot: Snapshot) -> dict[tuple[str, str, int, int], CellRef]:
    """Verify original primary bytes, every cell and unchanged 430/20 status accounting."""
    snapshot.read("primary/manifest.json", root / "manifest.json", PRIMARY_PINS["manifest.json"])
    completion = snapshot.read("primary/completion.json", root / "completion.json", PRIMARY_PINS["completion.json"])
    verify_content(completion, "completion_content_sha256")
    require(
        completion.get("stored_cells") == completion.get("planned_cells_in_this_invocation") == 450,
        "original primary record is incomplete",
    )
    inventory = completion.get("all_stored_cell_hashes", {})
    expected = expected_primary()
    require(set(inventory) == set(expected), "primary cell inventory differs from frozen grid")
    actual = {p.relative_to(root).as_posix() for p in (root / "cells").rglob("*.json")}
    require(actual == set(expected), "unexpected or missing original primary cells")
    refs = {}
    for relative, identity in sorted(expected.items()):
        cell = snapshot.read(f"primary/{relative}", inventory_path(root, relative), inventory[relative])
        verify_content(cell, "cell_content_sha256")
        observed = tuple(cell.get(k) for k in ("dataset", "model_key", "repeat", "fold"))
        require(observed == identity, f"primary identity differs from filename: {relative}")
        require(type(cell["repeat"]) is int and type(cell["fold"]) is int, f"noninteger primary identity: {relative}")
        validate_record(cell, relative)
        refs[identity] = CellRef("primary", relative, cell)
    counts = dict(Counter(ref.record["status"] for ref in refs.values()))
    require(
        counts == completion.get("status_counts") == {"complete": 430, "failed_diagnostics": 20},
        "original primary negative/failure evidence changed",
    )
    return refs


def dimension_rows(refs: dict[str, CellRef]) -> list[Json]:
    """Report actual encoded p/n_train and training events/p for all attempted cells."""
    rows = []
    for identity, ref in sorted(refs.items()):
        c = ref.record
        p = c.get("p")
        rows.append(
            {
                "cell_id": identity,
                "dataset": c["dataset"],
                "setting": c["setting"],
                "model": c["model_key"],
                "condition": c["condition"],
                "repeat": c["repeat"],
                "fold": c["fold"],
                "status": c["status"],
                "n_train": c["n_train"],
                "n_validation": c["n_validation"],
                "events_train": c["events_train"],
                "p": p,
                "p_available": p is not None,
                "p_over_n_train": p / c["n_train"] if p is not None else None,
                "events_over_p": c["events_train"] / p if p is not None else None,
                "ratio_availability": "available" if p is not None else "actual_encoded_p_not_recorded",
            }
        )
    return rows


def assert_pair_alignment(left: CellRef, right: CellRef) -> None:
    """Check exact ordered patient/train identities and all accepted prediction grids."""
    a, b = left.record, right.record
    for field in (
        "repeat",
        "fold",
        "n_train",
        "n_validation",
        "events_train",
        "train_subject_ids",
        "validation_subject_ids",
    ):
        require(a[field] == b[field], f"pair mismatch at {field}: {left.logical} vs {right.logical}")
    if a["status"] == b["status"] == "complete":
        for field in (
            "subject_ids",
            "observed_time",
            "observed_event",
            "training_time",
            "training_event",
            "horizons",
            "ibs_grid",
        ):
            require(
                a["predictions"][field] == b["predictions"][field],
                f"pair mismatch at {field}: {left.logical} vs {right.logical}",
            )


def descriptive_row(
    spec: Json, extension: dict[str, CellRef], primary: dict[tuple[str, str, int, int], CellRef], effect: Effect
) -> Json:
    """Calculate one prespecified descriptive contrast, retaining every exclusion."""
    pairs, left_scores, right_scores = [], [], []
    for repeat in range(1, 6):
        for fold in range(1, 6):
            left_id = cell_id(spec["dataset"], spec["setting"], repeat, fold, spec["left"], "full")
            left = extension[left_id]
            if spec["right_source_role"] == "primary":
                right = primary[(spec["dataset"], spec["right"], repeat, fold)]
            else:
                right = extension[cell_id(spec["dataset"], spec["setting"], repeat, fold, spec["right"], "full")]
            assert_pair_alignment(left, right)
            a, b = left.record, right.record
            accepted = a["status"] == b["status"] == "complete"
            score_a = a["metrics"]["ibs"] if a["status"] == "complete" else None
            score_b = b["metrics"]["ibs"] if b["status"] == "complete" else None
            delta = float(score_a - score_b) if accepted else None
            reasons = [f"{role}_{c['status']}" for role, c in (("left", a), ("right", b)) if c["status"] != "complete"]
            pairs.append(
                {
                    "repeat": repeat,
                    "fold": fold,
                    "left_source": left.logical,
                    "right_source": right.logical,
                    "left_status": a["status"],
                    "right_status": b["status"],
                    "included": accepted,
                    "exclusions": reasons,
                    "left_ibs": score_a,
                    "right_ibs": score_b,
                    "difference": delta,
                }
            )
            if accepted:
                left_scores.append(float(score_a))
                right_scores.append(float(score_b))
    n = len(left_scores)
    row = {
        **spec,
        "direction": "left IBS minus right IBS",
        "interpretation": "descriptive only",
        "expected_pairs": 25,
        "n_pairs": n,
        "missing_pairs": 25 - n,
        "coverage": n / 25,
        "interval_status": (
            "complete_25_pair_corrected_interval"
            if n == 25
            else "partial_observed_pairs_no_interval"
            if n
            else "zero_pairs_no_interval"
        ),
        "mean_difference": math.fsum(a - b for a, b in zip(left_scores, right_scores)) / n if n else None,
        "standard_deviation": None,
        "corrected_standard_error": None,
        "confidence_lower": None,
        "confidence_upper": None,
        "confidence_level": None,
        "degrees_of_freedom": None,
        "test_train_ratio": None,
        "paired_records": pairs,
        "left_status_counts": dict(sorted(Counter(p["left_status"] for p in pairs).items())),
        "right_status_counts": dict(sorted(Counter(p["right_status"] for p in pairs).items())),
    }
    if n == 25:
        full = effect(
            left_scores, right_scores, n_repeats=5, n_folds=5, test_train_ratio=1 / 4, confidence_level=0.95
        ).to_dict()
        for name in (
            "mean_difference",
            "standard_deviation",
            "corrected_standard_error",
            "confidence_lower",
            "confidence_upper",
            "confidence_level",
            "degrees_of_freedom",
            "test_train_ratio",
        ):
            finite(full[name], f"{spec['comparison_id']}/{name}")
            row[name] = full[name]
    return row


def formal_links(families: Json, family_summary: Json) -> Json:
    """Link all 27 existing clinical-prior contrasts, without copying tests/effects."""
    name = "catalytic_vs_original_priors"
    rows = families[name]["contrasts"]
    expected = [(d, m, p) for d in DATASETS for m in CATALYTIC for p in ORIGINAL[3:]]
    require([(r["dataset"], r["left"], r["right"]) for r in rows] == expected, "formal clinical-prior roster differs")
    linked = []
    for row in rows:
        horse = row.get("horseshoe_reference")
        require(
            horse == ("ADR-032 post-hoc sampler" if row["right"] == "bayesian_horseshoe" else None),
            "original versus ADR-032 horseshoe identity is ambiguous",
        )
        linked.append({k: row[k] for k in ("dataset", "left", "right", "n_pairs", "expected_pairs", "status")})
        linked[-1]["right_identity"] = "ADR032_post_hoc_sampler" if horse else "unchanged_original_primary_prior"
    return {
        "logical_source": "extension/paired_families.json",
        "family": name,
        "expected_contrasts": 27,
        "policy": "existing formal family linked only; no duplicate descriptive effects or tests",
        "estimable_contrasts": family_summary[name]["estimable_contrasts"],
        "missing_fold_pairs": family_summary[name]["missing_fold_pairs"],
        "contrasts": linked,
    }


def reporting_counts(dimensions: list[Json], contrasts: list[Json]) -> Json:
    """Retain status-specific ratio availability and complete/partial/zero pair coverage."""
    groups: dict[tuple[str, str, str, str, str], list[Json]] = defaultdict(list)
    for row in dimensions:
        groups[tuple(row[k] for k in ("dataset", "setting", "model", "condition", "status"))].append(row)
    records = []
    for values, rows in sorted(groups.items()):
        records.append(
            {
                **dict(zip(("dataset", "setting", "model", "condition", "status"), values)),
                "cells": len(rows),
                "ratios_available": sum(r["p_available"] for r in rows),
                "ratios_unavailable": sum(not r["p_available"] for r in rows),
            }
        )
    return {
        "extension_cells": len(dimensions),
        "primary_cells_required": 450,
        "extension_status_counts": dict(sorted(Counter(r["status"] for r in dimensions).items())),
        "ratios_available": sum(r["p_available"] for r in dimensions),
        "ratios_unavailable": sum(not r["p_available"] for r in dimensions),
        "dimension_availability_groups": records,
        "descriptive_rows": len(contrasts),
        "clinical_rows": sum(r["dataset"] != "metabric_matched" for r in contrasts),
        "matched_rows": sum(r["dataset"] == "metabric_matched" for r in contrasts),
        "contrast_coverage_counts": dict(sorted(Counter(r["interval_status"] for r in contrasts).items())),
        "included_fold_pairs": sum(r["n_pairs"] for r in contrasts),
        "excluded_fold_pairs": sum(r["missing_pairs"] for r in contrasts),
        "planned_fold_pairs": len(contrasts) * 25,
    }


def build_report(
    extension: dict[str, CellRef],
    primary: dict[tuple[str, str, int, int], CellRef],
    scope: Json,
    families: Json,
    family_summary: Json,
    effect: Effect,
) -> Json:
    """Build reporting only after validated complete input grids are available."""
    check_scope(scope)
    require(set(extension) == set(expected_extension()) and len(primary) == 450, "complete grids are required")
    dimensions = dimension_rows(extension)
    contrasts = [descriptive_row(spec, extension, primary, effect) for spec in scope["rows"]]
    return {
        "schema_version": 1,
        "evidence_status": "post_hoc_extension",
        "report_kind": "descriptive_reporting_sidecar",
        "scope_sha256": SCOPE_SHA,
        "production_commit": PRODUCTION_COMMIT,
        "analysis_commit": ANALYSIS_COMMIT,
        "direction": "catalytic left IBS minus comparator right IBS",
        "dimension_denominator": "actual training n",
        "interpretation": "descriptive effects and frozen complete-pair 95% uncertainty only; no significance claims",
        "primary_finding": "original primary bytes and 430 accepted/20 diagnostic-failure counts are preserved; "
        "these supplementary extension comparisons do not change its findings",
        "completion_scope": (
            "reporting only; refit, rank provenance, trace, visual, release and restore gates are separate"
        ),
        "counts": reporting_counts(dimensions, contrasts),
        "formal_clinical_prior_family": formal_links(families, family_summary),
        "dimension_ratios": dimensions,
        "descriptive_catalytic_pairs": contrasts,
    }


def csv_bytes(rows: list[Json], fields: Sequence[str]) -> bytes:
    """Encode deterministic CSV; empty fields represent explicit JSON nulls."""
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(fields), lineterminator="\n", extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: (str(row[k]).lower() if type(row[k]) is bool else row[k]) for k in fields})
    return output.getvalue().encode("utf-8")


def payloads(report: Json, snapshot: Snapshot) -> dict[str, bytes]:
    """Produce stable scientific artifacts and source-bound lineage without host metadata."""
    output = {
        "dimension_ratios.csv": csv_bytes(report["dimension_ratios"], DIMENSION_FIELDS),
        "descriptive_catalytic_pairs.csv": csv_bytes(report["descriptive_catalytic_pairs"], COMPARISON_FIELDS),
        "report.json": json_bytes(report),
    }
    lineage = {
        "schema_version": 1,
        "evidence_status": "post_hoc_extension",
        "source_roles": snapshot.portable(),
        "source_binding_sha256": canonical_sha(snapshot.portable()),
        "scope_sha256": SCOPE_SHA,
        "production_commit": PRODUCTION_COMMIT,
        "analysis_commit": ANALYSIS_COMMIT,
        "interval_source_sha256": INTERVAL_SHA,
        "numerical_prerequisite_helper_sha256": CLAIM_SHA,
        "artifacts_sha256": {name: sha_bytes(data) for name, data in sorted(output.items())},
        "policy": "logical IDs only; host paths/time belong to separate invocation or replay receipts",
    }
    output["lineage.json"] = json_bytes(lineage)
    return output


def load_inputs(
    args: argparse.Namespace, snapshot: Snapshot
) -> tuple[dict[str, CellRef], dict[tuple[str, str, int, int], CellRef], Json, Json, Json, Effect]:
    """Bind pinned dependencies, full/deep numerical evidence and original primary cells."""
    source = Path(__file__).resolve()
    snapshot.capture("preparation/generate_reporting_sidecar.py", source)
    scope = snapshot.read("preparation/scope.json", args.scope_file, SCOPE_SHA)
    check_scope(scope)
    claim_bytes = snapshot.capture("preparation/summarize_verified_claim_inputs.py", args.claim_helper, CLAIM_SHA)
    interval_bytes = snapshot.capture("preparation/frozen_repeated_cv.py", args.interval_source, INTERVAL_SHA)
    claim = load_pinned_module(args.claim_helper, claim_bytes, "_sidecar_pinned_claim")
    interval = load_pinned_module(args.interval_source, interval_bytes, "_sidecar_pinned_interval")
    manifest = snapshot.read("extension/manifest.json", args.run / "manifest.json")
    completion = snapshot.read("extension/completion.json", args.run / "completion.json")
    snapshot.read("extension/verification.json", args.run / "verification.json")
    require(
        completion.get("planned") == completion.get("stored") == 1625 and completion.get("verification") == "deep",
        "partial/unverified extension programme; no destination may be created",
    )
    records = [
        snapshot.read(f"extension/{name}", inventory_path(args.run, name), digest)
        for name, digest in sorted(completion.get("cell_sha256", {}).items())
    ]
    families = None
    for name, digest in sorted(completion.get("aggregate_sha256", {}).items()):
        aggregate = snapshot.read(f"extension/{name}", inventory_path(args.run, name), digest)
        if name == "paired_families.json":
            families = aggregate
    verified_cells, verified_completion, _ = claim.load_numerical(args.run)
    require(
        records == verified_cells and completion == verified_completion, "inputs changed between prerequisite reads"
    )
    require(families is not None, "paired-family evidence missing")
    family_summary = claim.summarize_families(families)
    extension = extension_refs(records, manifest)
    primary = primary_refs(args.primary, snapshot)
    return extension, primary, scope, families, family_summary, interval.nadeau_bengio_paired_effect


def write_new(output: Path, artifacts: dict[str, bytes], receipt: Json) -> None:
    """Create one new directory only; retain an incomplete IO attempt for investigation."""
    require(not output.exists() and not output.is_symlink(), f"output already exists: {output}")
    require(output.parent.is_dir(), "output parent must already exist")
    output.mkdir(exist_ok=False)
    for name, data in artifacts.items():
        with (output / name).open("xb") as handle:
            handle.write(data)
    # Publish no final receipt until its write, flush, sync and close all succeed.
    # The exclusive hard-link install cannot replace a pre-existing final receipt.
    pending = output / "receipt.pending"
    with pending.open("xb") as handle:
        handle.write(json_bytes(receipt))
        handle.flush()
        os.fsync(handle.fileno())
    os.link(pending, output / "receipt.json")
    pending.unlink()
    require(
        {p.name for p in output.iterdir()} == set(artifacts) | {"receipt.json"},
        "new sidecar inventory retains incomplete or unexpected files",
    )
    for name, data in artifacts.items():
        require(file_bytes(output / name) == data, f"newly written artifact bytes differ: {name}")
    require(file_bytes(output / "receipt.json") == json_bytes(receipt), "newly written receipt bytes differ")


def verify_existing(output: Path, artifacts: dict[str, bytes], snapshot: Snapshot) -> tuple[Json, str]:
    """Replay all deterministic bytes and bind, without rewriting, the original receipt."""
    require(output.is_dir() and not output.is_symlink(), "existing sidecar directory is missing or linked")
    require({p.name for p in output.iterdir()} == set(ARTIFACT_FILES), "sidecar inventory differs from five artifacts")
    for name, expected in artifacts.items():
        require(file_bytes(output / name) == expected, f"replayed artifact differs: {name}")
    original_bytes = file_bytes(output / "receipt.json")
    original = strict_json(original_bytes, "original sidecar receipt")
    verify_content(original, "receipt_content_sha256")
    require(
        original.get("status") == "reporting_sidecar_generated" and original.get("operation") == "generate",
        "original receipt is not a generation receipt",
    )
    require(
        original.get("artifact_sha256") == {name: sha_bytes(data) for name, data in sorted(artifacts.items())},
        "original receipt artifact binding changed",
    )
    require(
        original.get("source_binding_sha256") == canonical_sha(snapshot.portable()),
        "original receipt source binding changed",
    )
    return original, sha_bytes(original_bytes)


def invocation_metadata(args: argparse.Namespace, started: str) -> Json:
    """Keep host paths, timing and argument strings separate from scientific artifacts."""
    return {
        "started_utc": started,
        "completed_utc": datetime.now(UTC).isoformat(),
        "argv": list(sys.argv[1:]),
        "resolved_roots": {
            "extension": str(args.run.resolve()),
            "primary": str(args.primary.resolve()),
            "sidecar": str(args.output.resolve()),
        },
        "resolved_inputs": {
            "scope": str(args.scope_file.resolve()),
            "claim_helper": str(args.claim_helper.resolve()),
            "interval_source": str(args.interval_source.resolve()),
            "helper": str(Path(__file__).resolve()),
        },
        "python_version": sys.version,
        "python_executable": sys.executable,
    }


def run(args: argparse.Namespace) -> Json:
    """Validate every prerequisite before publishing or replaying the reporting supplement."""
    started = datetime.now(UTC).isoformat()
    for root in (args.run, args.primary):
        require(root.is_dir() and not root.is_symlink(), f"missing or linked evidence root: {root}")
        require(
            not args.output.resolve().is_relative_to(root.resolve()),
            "sidecar destination must be outside evidence roots",
        )
    require(
        not args.output.resolve().is_relative_to(Path(__file__).resolve().parent),
        "sidecar destination must be outside the sealed preparation directory",
    )
    if not args.verify_existing:
        require(not args.output.exists() and not args.output.is_symlink(), f"output already exists: {args.output}")
    snapshot = Snapshot()
    extension, primary, scope, families, summary, effect = load_inputs(args, snapshot)
    report = build_report(extension, primary, scope, families, summary, effect)
    artifacts = payloads(report, snapshot)
    snapshot.recheck()
    receipt = {
        "schema_version": 1,
        "status": "reporting_sidecar_generated",
        "operation": "generate",
        "evidence_status": "post_hoc_extension",
        "scientific_completion_certified": False,
        "artifact_sha256": {name: sha_bytes(data) for name, data in sorted(artifacts.items())},
        "source_binding_sha256": canonical_sha(snapshot.portable()),
        "counts": {k: v for k, v in report["counts"].items() if k != "dimension_availability_groups"},
        "helper_sha256": snapshot.bindings["preparation/generate_reporting_sidecar.py"].sha256,
        "invocation": invocation_metadata(args, started),
    }
    if args.verify_existing:
        original, original_sha = verify_existing(args.output, artifacts, snapshot)
        require(
            original.get("counts") == receipt["counts"] and original.get("helper_sha256") == receipt["helper_sha256"],
            "original receipt helper/count binding changed",
        )
        receipt.update(
            {
                "status": "reporting_sidecar_replayed",
                "operation": "verify_existing",
                "original_receipt_sha256": original_sha,
                "deterministic_artifacts_compared": 4,
                "policy": "new stdout receipt only; preserved evidence and sidecar bytes unchanged",
            }
        )
    receipt["receipt_content_sha256"] = canonical_sha(receipt)
    if not args.verify_existing:
        write_new(args.output, artifacts, receipt)
    return receipt


def arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse portable evidence roots and write-once generation versus read-only replay."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run", "primary", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--verify-existing", action="store_true", help="compare existing bytes; receipt only to stdout")
    base = Path(__file__).resolve().parent
    parser.add_argument("--scope-file", type=Path, default=base / "scope.json")
    parser.add_argument("--claim-helper", type=Path, default=base / "summarize_verified_claim_inputs.py")
    parser.add_argument("--interval-source", type=Path, default=base / "frozen_repeated_cv.py")
    return parser.parse_args(argv)


def main() -> None:
    """Emit a successful receipt only after generation or exact replay has completed."""
    receipt = run(arguments())
    sys.stdout.buffer.write(json_bytes(receipt))


if __name__ == "__main__":
    main()
