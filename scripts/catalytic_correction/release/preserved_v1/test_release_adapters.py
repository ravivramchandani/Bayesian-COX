"""Tiny fictional files/injected children only; no actual science or transfer."""

from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import release_core as c
import stage_corrected_extensions as st
import verify_restored_correction as vr


def raw(path: Path, data: bytes) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return c.sha(path)


def save(path: Path, value: dict, field: str | None = "content_sha256") -> str:
    value = copy.deepcopy(value)
    if field is not None:
        value.pop(field, None)
        value[field] = c.canonical(value)
    return raw(path, (json.dumps(value, sort_keys=True, indent=2) + "\n").encode())


def binding(path: Path) -> dict:
    return {"sha256": c.sha(path), "bytes": path.stat().st_size}


def cap(directory: Path, name: str, status: str, summary: dict, completion: str | None = None) -> dict:
    """Fictional capture-shaped fixtures, never an executed scientific process."""
    directory.mkdir(parents=True, exist_ok=True)
    prefix = directory / name
    stdout, stderr, attempt, receipt = (prefix.with_name(prefix.name + suffix) for suffix in
                                      (".stdout.log", ".stderr.log", ".attempt.json", ".receipt.json"))
    raw(stdout, (json.dumps(summary) + "\n").encode())
    raw(stderr, b"fictional stderr\n")
    save(attempt, {"exit_code": 0, "launch_error": None, "argv": ["fictional_python", "fictional_read_only.py"],
                   "stdout_path": str(stdout), "stderr_path": str(stderr), "stdout_sha256": c.sha(stdout), "stderr_sha256": c.sha(stderr),
                   "fixture_only_no_actual_process": True})
    value = {"status": status, "exit_code": 0, "summary": summary,
             "stdout_path": str(stdout), "stderr_path": str(stderr), "stdout_sha256": c.sha(stdout), "stderr_sha256": c.sha(stderr),
             "invocation_attempt_sha256": c.sha(attempt), "artifacts": {path.name: binding(path) for path in (stdout, stderr, attempt)},
             "fixture_only_no_actual_process": True}
    if completion is not None:
        value["completion_sha256"] = completion
    save(receipt, value)
    return {"path": str(receipt), "sha256": c.sha(receipt)}


def command_cap(item: dict, script: Path, options: list[str], *, mixed_sources: dict | None = None,
                summary_fields: dict | None = None) -> None:
    """Rebind fictional capture bytes to a realistic immutable command carrier."""
    receipt_path = Path(item["path"])
    receipt = c.document(receipt_path, c.Pins())
    prefix = receipt_path.name.removesuffix(".receipt.json")
    attempt_path = receipt_path.with_name(prefix + ".attempt.json")
    attempt = c.document(attempt_path, c.Pins())
    attempt["argv"] = ["/fictional/locked_python", "-I", "-B", str(script), *options]
    if mixed_sources is not None:
        attempt.update(operation="actual_mixed_verifier_child_capture", implementation_source_sha256=mixed_sources)
    else:
        attempt.update(operation="actual_corrected_transfer_child_capture",
                       entrypoint={"historical_path": str(script), "sha256": c.sha(script)},
                       numeric_thread_environment={name: "1" for name in c.NUMERIC}, test_only_dependency_injection=False)
    if summary_fields:
        receipt["summary"].update(summary_fields)
        stdout = receipt_path.with_name(prefix + ".stdout.log")
        raw(stdout, (json.dumps(receipt["summary"]) + "\n").encode())
        attempt["stdout_sha256"] = receipt["stdout_sha256"] = c.sha(stdout)
        receipt["artifacts"][stdout.name] = binding(stdout)
    save(attempt_path, attempt)
    receipt["invocation_attempt_sha256"] = c.sha(attempt_path)
    receipt["artifacts"][attempt_path.name] = binding(attempt_path)
    item["sha256"] = save(receipt_path, receipt)


class Fixture:
    """Three logical cells/all three selected routes, two synthetic contexts."""

    def __init__(self, base: Path):
        self.base = base
        self.policy = c.Policy(cells=3, contexts=2, original_selected=2, figures=2, tables=1, comparisons=2, test_only=True)
        self.ids = ["x__r01f01__reuse", "x__r01f01__terminal", "x__r02f01__changed"]
        self.names, self.tables = ["fig_a", "fig_b"], [("fold_metrics", ["cells/*.json"])]
        self.source = base / "fictional_sources"
        self.source.mkdir()
        files = {"candidate_module", "contracts", "correction_addendum", "correction_config", "matched", "freeze",
                 "matched_manifest", "source_report", "source_verification_bindings", *("review_" + name for name in c.REVIEWS)}
        self.roots = {}
        self.kinds = {}
        for name in set(c.LAYOUT) - {"resolution_review", "pilot_review"}:
            path = self.source / (name + ".dat" if name in files else name)
            self.roots[name] = path
            self.kinds[name] = "file" if name in files else "tree"
            if name in files:
                raw(path, b"fictional non-array source bytes")
            else:
                path.mkdir()
        for name in c.EXTERNAL:
            path = self.source / name
            path.mkdir()
            self.roots[name] = path
        for name in ("primary", "sampler", "robustness"):
            save(self.roots[name] / "manifest.json", {"fictional": name})
            save(self.roots[name] / "completion.json", {"fictional": name})
        for name in ("production", "analysis"):
            raw(self.roots[name] / "source.py", b"# fictional source, never imported\n")
        raw(self.roots["analysis"] / "scripts/render_extensions.py", b"# fictional renderer; never imported or run\n")
        save(self.roots["primary"] / "explanation.json", {"fictional_frozen_explanation": True})
        for name in ("scripts/verify_environment.py", "conda-lock.yml", "conda-lock.yml.sha256"):
            raw(self.roots["production"] / name, b"fictional checker/lock bytes; never executed\n")
        self.environment = {"status": "ok", "package_count": 259, "fictional_no_environment_checker_executed": True}
        self.bindings = {"schema_version": 1, "roots": {name: str(self.roots[name]) for name in c.ROOTS}, "files": {},
                         "review_paths": {name: str(self.roots["review_" + name]) for name in c.REVIEWS}}
        for name in c.REVIEWS:
            save(self.roots["review_" + name], {"status": "reviewed_for_corrected_fit_execution", "role": name, "fictional": True})
        definitions = {"content_sha256": "not used until sealed", "fictional": True}
        save(self.roots["witness_root"] / "definition.json", definitions)
        save(self.roots["freeze"], {"status": "reviewed_corrected_fit_freeze", "fictional": True})
        manifest_path = self.roots["corrected_run"] / "manifest.json"
        save(manifest_path, {"status": "corrected_fit_manifest_frozen", "pilot_cells": [self.ids[-1]], "fictional": True})
        for name, path in (("definition", self.roots["witness_root"] / "definition.json"), ("freeze", self.roots["freeze"]), ("manifest", manifest_path)):
            self.bindings["files"][name] = {"path": str(path), "sha256": c.sha(path)}
        for name in ("original_run", "corrected_run", "reproduction"):
            (self.roots[name] / "claims").mkdir()
            (self.roots[name] / "cells").mkdir()
        old_hashes, envelopes, lineages, cell_hashes, checks, entries = {}, {}, {}, {}, {}, []
        operations = ["reuse_original_outcome", "retain_corrected_input_failure", "fit_corrected_inputs"]
        for identity, operation in zip(self.ids, operations, strict=True):
            trace = self.roots["original_run"] / "traces" / identity / "old.nc"
            orphan = trace.with_name("old_orphan.nc")
            raw(trace, b"fictional retained sample bytes")
            raw(orphan, b"fictional retained failed/orphan bytes")
            cell = {"cell_id": identity, "status": "complete" if operation == "reuse_original_outcome" else "failed",
                    "fit_attempts": [{"traces": {"posterior": {"filename": "old.nc", "sha256": c.sha(trace)}}}]}
            old_path = self.roots["original_run"] / "cells" / (identity + ".json")
            old_hashes[identity] = save(old_path, cell, "cell_content_sha256")
            artifacts = {}
            raw_cell = None
            if operation == "fit_corrected_inputs":
                raw_path = self.roots["corrected_run"] / "attempts" / identity / "cell.json"
                new_trace = raw_path.parent / "traces" / identity / "failed.nc"
                new_orphan = new_trace.with_name("unreferenced_failed.nc")
                raw(new_trace, b"fictional corrected failed-chain bytes")
                raw(new_orphan, b"fictional corrected orphan bytes")
                corrected_cell = {"cell_id": identity, "status": "failed_diagnostics", "fit_attempts": [{"traces":
                                  {"posterior": {"filename": "failed.nc", "sha256": c.sha(new_trace)}}}]}
                save(raw_path, corrected_cell, "cell_content_sha256")
                raw_cell = {"path": str(raw_path.relative_to(self.roots["corrected_run"])), "sha256": c.sha(raw_path)}
                artifacts = {str(path.relative_to(self.roots["corrected_run"])): binding(path) for path in (raw_path, new_trace, new_orphan)}
                cell = corrected_cell
            envelope_path = self.roots["corrected_run"] / "cells" / (identity + ".json")
            envelopes[identity] = save(envelope_path, {"original_cell_id": identity, "operation": operation,
                                                     "corrected_cell": raw_cell, "artifacts": artifacts})
            old_evidence = {"cell_byte_sha256": old_hashes[identity], "referenced_trace_sha256":
                            {str(trace.relative_to(self.roots["original_run"])): c.sha(trace)},
                            "unreferenced_trace_sha256": {str(orphan.relative_to(self.roots["original_run"])): c.sha(orphan)}}
            lp = self.roots["mixed_verified"] / "lineage" / (identity + ".json")
            lineages["lineage/" + identity + ".json"] = save(lp, {"original_cell_id": identity, "operation": operation,
                "original_record_preserved": True, "raw_bindings": {"original_cell_sha256": old_hashes[identity],
                "corrected_envelope_sha256": envelopes[identity], "corrected_raw_cell_sha256": None if raw_cell is None else raw_cell["sha256"]},
                "input_verification": {"original_source_evidence": old_evidence}})
            cp = self.roots["mixed_verified"] / "cells" / (identity + ".json")
            cell_hashes["cells/" + identity + ".json"] = save(cp, cell, "cell_content_sha256")
            for side in (["original", "corrected"] if operation == "fit_corrected_inputs" else ["original"]):
                path = self.roots["mixed_verified"] / "checks" / side / (identity + ".json")
                checks[str(path.relative_to(self.roots["mixed_verified"]))] = save(path, {"fictional": True})
            wp = self.roots["witness_root"] / "cells" / identity / "input_witness.json"
            sp = wp.parent / "snapshots" / "snapshot.json"
            save(wp, {"artifacts": {}, "proof_artifacts": {}, "fictional": True})
            save(sp, {"artifacts": {}, "fictional": True})
            entries.append({"original_cell_id": identity, "input_witness_path": str(wp.relative_to(self.roots["witness_root"])),
                            "input_witness_sha256": c.sha(wp), "snapshot_path": str(sp.relative_to(self.roots["witness_root"])), "snapshot_sha256": c.sha(sp)})
        save(self.roots["original_run"] / "manifest.json", {"plan": [{"cell_id": identity} for identity in self.ids]}, "manifest_content_sha256")
        preflight, replay = [], []
        for index in range(2):
            context = f"fictional_context_{index}"
            for namespace, rows in ((self.roots["preflight"], preflight), (self.roots["witness_root"] / "replay", replay)):
                path = namespace / "contexts" / context / "receipt.json"
                payload = path.parent / "attempt_000" / "proposal.npz"
                raw(payload, b"fictional NPZ-shaped byte fixture; no numpy arrays")
                save(path, {"status": "fictional_accounted", "artifacts": {str(payload.relative_to(path.parent)): binding(payload)}})
                relative = str(path.relative_to(self.roots["witness_root"])) if namespace != self.roots["preflight"] else str(path.relative_to(namespace))
                rows.append({"context_id": context, "receipt_path": relative, "receipt_sha256": c.sha(path)})
        save(self.roots["preflight"] / "completion.json", {"status": "all_scheduled_contexts_accounted", "scheduled_contexts": 2, "accounted_contexts": 2, "outcomes": preflight})
        save(self.roots["preflight"] / "manifest.json", {"environment_verification": self.environment, "fictional": True})
        rp = self.roots["witness_root"] / "replay/completion.json"
        save(rp, {"status": "all1650_independent_first_draw_contexts_accounted", "scheduled_contexts": 2, "accounted_contexts": 2, "outcomes": replay})
        ip = self.roots["witness_root"] / "inventories" / "fictional" / "inventory.json"
        save(ip, {"entries": entries, "replay_completion_sha256": c.sha(rp)})
        self.bindings["files"]["inventory"] = {"path": str(ip), "sha256": c.sha(ip)}
        ap = self.roots["arithmetic"] / "accounting.json"
        save(ap, {"status": "all_scheduled_arithmetic_outcomes_accounted", "artifacts": {}, "fictional": True})
        self.bindings["files"]["arithmetic_accounting"] = {"path": str(ap), "sha256": c.sha(ap)}
        selected = sorted(self.ids)
        sel = {"status": "reviewed_corrected_reproduction_selection", "original_selected_cells": sorted(self.ids[:2]),
               "pilot_cells": [self.ids[-1]], "selected_cells": selected,
               "correction_freeze_sha256": self.bindings["files"]["freeze"]["sha256"],
               "corrected_manifest_sha256": self.bindings["files"]["manifest"]["sha256"],
               "input_inventory_sha256": self.bindings["files"]["inventory"]["sha256"]}
        selection_sha = save(self.roots["reproduction"] / "selection.json", sel)
        statuses = dict(zip(self.ids, ("reused_verified_original_numerical_reproduction", "terminal_no_fit_recipe_replay", "new_corrected_numerical_reproduction"), strict=True))
        outcomes = []
        for identity in selected:
            path = self.roots["reproduction"] / "cells" / (identity + ".json")
            save(path, {"original_cell_id": identity, "status": statuses[identity], "selection_sha256": selection_sha,
                        "artifacts": {}, "external_artifacts": {str(self.roots["original_run"] / "cells" / (identity + ".json")):
                                                                binding(self.roots["original_run"] / "cells" / (identity + ".json"))}})
            outcomes.append({"original_cell_id": identity, "status": statuses[identity], "record_sha256": c.sha(path)})
        pass_path = self.roots["reproduction"] / "passes" / "fictional_complete.json"
        pass_sha = save(pass_path, {"status": "all_selected_reproduction_outcomes_accounted", "selection_sha256": selection_sha,
                                   "scheduled_selected_cells": 3, "accounted_selected_cells": 3, "outcomes": outcomes, "whole_1625_grid_numerically_reproduced": False})
        prep_shas = {}
        for name in ("verification_preparation", "reproduction_preparation", "receiving_reproduction_preparation", "release_adapter_preparation"):
            helper_name = {"verification_preparation": "verify_mixed_extensions.py",
                           "receiving_reproduction_preparation": "verify_restored_reproduction.py"}.get(name, "fictional.py")
            helper = self.roots[name] / helper_name
            raw(helper, b"# fictional, never imported\n")
            extra = {}
            if name == "verification_preparation":
                source_pins = {"files": {side: {"source.py": c.sha(self.roots[side] / "source.py")} for side in ("production", "analysis")}}
                source_pins["files"]["analysis"]["scripts/render_extensions.py"] = c.sha(self.roots["analysis"] / "scripts/render_extensions.py")
                source_path = self.roots[name] / "source_pins.json"
                save(source_path, source_pins, None)
                extra = {"source_pins_sha256": c.sha(source_path)}
            if name == "receiving_reproduction_preparation":
                extra = {"status": "corrected_reproduction_receiving_adapter_prepared", "no_fit_or_generator_dispatch": True}
            pp = self.roots[name] / "preparation_receipt.json"
            helpers = [helper]
            if name == "verification_preparation":
                renderer = self.roots[name] / "render_verified_mix.py"
                raw(renderer, b"# fictional corrected rendering adapter; never imported or run\n")
                helpers.append(renderer)
            prep_shas[name] = save(pp, {"status": "fictional_preparation", "artifacts": {helper.name: binding(helper)},
                                      "implementation_source_sha256": {path.name: c.sha(path) for path in helpers}, **extra})
        self.pins = {"mixed_verifier_preparation_sha256": prep_shas["verification_preparation"],
                     "original_reproduction_preparation_sha256": prep_shas["reproduction_preparation"],
                     "receiving_reproduction_preparation_sha256": prep_shas["receiving_reproduction_preparation"],
                     "transport_sources": {"qa_transfer.py": "a" * 64}}
        transport_code = self.source / "fictional_transport"
        for name in ("archive_common.py", "stage_extensions.py", "package.py", "verify.py", "qa_transfer.py"):
            raw(transport_code / name, b"# fictional transport source; never imported or packaged\n")
        self.pins["transport_sources"] = {path.name: c.sha(path) for path in transport_code.iterdir()}
        mm = self.roots["mixed_verified"] / "manifest.json"
        save(mm, {"plan": [{"cell_id": identity} for identity in self.ids]})
        aggregates = {}
        for name in ("paired_families", "rq2_effects", "decision_curves"):
            path = self.roots["mixed_verified"] / "aggregates" / (name + ".json")
            aggregates[str(path.relative_to(self.roots["mixed_verified"]))] = save(path, {"fictional_reducer": name})
        fixed = {}
        for name in ("reference_verification", "comparison_accounting", "render_input"):
            path = self.roots["mixed_verified"] / (name + ".json")
            fixed[name + "_sha256"] = save(path, {"fictional": True})
        self.source_summary = {"fictional_bound_definition": "b" * 64}
        completion = {"status": c.MIXED_STATUS, "evidence_status": c.EVIDENCE, "planned_logical_cells": 3, "verified_logical_cells": 3,
                      "programme_complete": False, "original855_certificate_inherited": False,
                      "stored_diagnostics_recomputed_and_complete_forecasts_rescored": True, "original_and_primary_negative_findings_preserved": True,
                      "manifest_sha256": c.sha(mm), "cell_sha256": cell_hashes, "lineage_sha256": lineages, "check_sha256": checks,
                      "aggregate_sha256": aggregates, "initial_invocation_metadata_sha256": {}, "source_bindings": self.source_summary, **fixed}
        bindings_path = self.roots["source_verification_bindings"]
        save(bindings_path, self.bindings)
        mixed_script = self.roots["verification_preparation"] / "verify_mixed_extensions.py"
        mixed_options = ["--preparation-receipt", str(self.roots["verification_preparation"] / "preparation_receipt.json"),
             "--preparation-receipt-sha256", prep_shas["verification_preparation"],
             "--input-bindings", str(bindings_path), "--input-bindings-sha256", c.sha(bindings_path),
             "--output", str(self.roots["mixed_verified"])]
        invocation_sha = save(self.roots["mixed_verified"] / "invocation.json", {"operation": "mixed_extensions_deep_verification",
            "argv": [str(mixed_script), *mixed_options], "input_bindings_sha256": c.sha(bindings_path),
            "preparation_receipt_sha256": prep_shas["verification_preparation"], "actual_input_locations": c.document(bindings_path, c.Pins()),
            "verify_existing": False, "actual_numeric_thread_environment": {name: "1" for name in c.NUMERIC}, "fictional": True})
        completion["initial_invocation_metadata_sha256"] = {"invocation.json": invocation_sha}
        completion_sha = save(self.roots["mixed_verified"] / "completion.json", completion)
        source_capture = cap(self.roots["source_capture"], "source", "mixed_verification_actual_rc0_captured",
                             {"status": c.MIXED_STATUS, "verified_logical_cells": 3, "programme_complete": False}, completion_sha)
        bindings_path = self.roots["source_verification_bindings"]
        save(bindings_path, self.bindings)
        mixed_script = self.roots["verification_preparation"] / "verify_mixed_extensions.py"
        verified_prep = c.document(self.roots["verification_preparation"] / "preparation_receipt.json", c.Pins())
        mixed_sources = {str(self.roots["verification_preparation"] / name): digest for name, digest in verified_prep["implementation_source_sha256"].items()}
        mixed_sources[str(self.roots["verification_preparation"] / "preparation_receipt.json")] = prep_shas["verification_preparation"]
        mixed_sources[str(bindings_path)] = c.sha(bindings_path)
        command_cap(source_capture, mixed_script, mixed_options, mixed_sources=mixed_sources)
        route_counts = {status: 1 for status in c.FINAL_REPRO}
        repro_cap = cap(self.roots["reproduction_capture"], "repro", "corrected_readonly_reproduction_actual_rc0_captured",
                        {"status": "corrected_selected_reproduction_restored_read_only_verified", "selection_sha256": selection_sha,
                         "selected_pass_sha256": pass_sha, "route_counts": route_counts, "scheduled_selected_cells": 3,
                         "accounted_selected_cells": 3, "no_new_numerical_fit": True})
        support_paths = {name: self.roots["support"] / (name + ".py") for name in ("qa_helper", "reporting_helper", "claim_helper", "report_replay")}
        for path in support_paths.values():
            raw(path, b"# fictional read-only support, never imported\n")
        support_shas = {name: c.sha(path) for name, path in support_paths.items()}
        support_preparation_path = self.roots["support"] / "preparation_receipt.json"
        self.pins["reporting_qa_preparation_sha256"] = save(support_preparation_path, {
            "status": "fictional_reporting_preparation", "artifacts": {path.name: binding(path) for path in support_paths.values()},
            "implementation_source_sha256": {path.name: c.sha(path) for path in support_paths.values()}})
        figure_rows, qa_rows = [], []
        for index, name in enumerate(self.names, 1):
            pdf, png = (self.roots["rendered"] / (name + ext) for ext in (".pdf", ".png"))
            raw(pdf, b"fictional PDF byte fixture; no renderer")
            raw(png, b"fictional PNG byte fixture; no renderer")
            page = self.roots["qa"] / "page_renders" / f"{index:02d}_{name}.png"
            raw(page, b"fictional full-page byte fixture")
            row = {"name": name, "source_files": ["cells/*.json"], "visual_review": "pending", "pdf_sha256": c.sha(pdf), "png_sha256": c.sha(png)}
            figure_rows.append(row)
            qa_rows.append({**row, "page_render": str(page.relative_to(self.roots["qa"])), "page_render_sha256": c.sha(page)})
        table = self.roots["rendered"] / "fold_metrics.csv"
        raw(table, b"fictional,only\n")
        table_rows = [{"name": "fold_metrics", "source_files": ["cells/*.json"], "csv_sha256": c.sha(table)}]
        lp = self.roots["rendered"] / "lineage.json"
        save(lp, {"figures": figure_rows, "tables": table_rows}, None)
        correction = {"evidence_status": c.EVIDENCE, "mixed_completion_sha256": completion_sha,
                      "actual_verifier_capture_sha256": source_capture["sha256"], "original_renderer_lineage_sha256": c.sha(lp),
                      "original_renderer_sha256": c.sha(self.roots["analysis"] / "scripts/render_extensions.py"),
                      "adapter_sha256": c.sha(self.roots["verification_preparation"] / "render_verified_mix.py"), "actual_visual_review": "pending; rendering is not QA"}
        cl = self.roots["rendered"] / "mixed_correction_lineage.json"
        save(cl, correction)
        qb = {"mixed_completion_sha256": completion_sha, "original_renderer_lineage_sha256": c.sha(lp), "mixed_correction_lineage_sha256": c.sha(cl),
              "renderer_sha256": correction["original_renderer_sha256"], "renderer_adapter_sha256": correction["adapter_sha256"],
              "actual_verifier_capture_sha256": source_capture["sha256"], "qa_helper_sha256": support_shas["qa_helper"]}
        sheets = []
        for index in range(1, 5):
            path = self.roots["qa"] / "contact_sheets" / f"sheet_{index:02d}.png"
            raw(path, b"fictional indexed sheet")
            sheets.append({"file": str(path.relative_to(self.roots["qa"])), "sha256": c.sha(path)})
        qi = self.roots["qa"] / "qa_inventory.json"
        save(qi, {"status": "corrected_automated_checks_passed_visual_review_pending", "source_bindings": qb,
                  "figures": qa_rows, "tables": table_rows, "contact_sheets": sheets, "figure_count": 2, "table_count": 1})
        qr = self.roots["qa"] / "review.json"
        review = {"inventory_sha256": c.sha(qi), "reviewer_name": "Fictional Fixture Reviewer", "attestation": c.ATTESTATION,
                  "reviewer_role": "root",
                  "reviewed_at_utc": "2026-01-01T00:00:00+00:00", "figures": [{"name": name, "verdict": "pass"} for name in self.names]}
        save(qr, review)
        qreceipt = self.roots["qa"] / "visual_qa_receipt.json"
        save(qreceipt, {**review, "source_bindings": qb, "visual_qa_status": "passed", "test_only": False,
                       "review_sha256": c.sha(qr), "figure_count": 2, "table_count": 1, "tables": [{"name": "fold_metrics", "csv_sha256": c.sha(table)}]})
        sb = {"mixed_completion_sha256": completion_sha, "selection_sha256": selection_sha, "selected_pass_sha256": pass_sha,
              "visual_qa_receipt_sha256": c.sha(qreceipt), "mixed_correction_lineage_sha256": c.sha(cl)}
        reporting_files = {}
        for name in ("dimension_ratios.csv", "descriptive_catalytic_pairs.csv"):
            path = self.roots["reporting"] / name
            raw(path, b"fictional table\n")
            reporting_files[name] = binding(path)
        report = self.roots["reporting"] / "report.json"
        save(report, {"dimension_ratios": [{"cell_id": identity} for identity in self.ids], "descriptive_catalytic_pairs": [{"fictional": 1}, {"fictional": 2}]}, None)
        reporting_files[report.name] = binding(report)
        rl = self.roots["reporting"] / "lineage.json"
        save(rl, {"fictional": True})
        reporting_files[rl.name] = binding(rl)
        sidecar = self.roots["reporting"] / "receipt.json"
        save(sidecar, {"status": "corrected_reporting_sidecar_generated", "source_bindings": sb, "scientific_completion_certified": False,
                        "artifacts": reporting_files, "helper_sha256": support_shas["reporting_helper"]})
        reporting_cap = cap(self.roots["source_reporting_capture"], "reporting", "corrected_reporting_replay_actual_rc0_captured",
                            {"status": "corrected_reporting_source_replay_verified", "source_bindings": sb,
                             "sidecar_receipt_sha256": c.sha(sidecar), "deterministic_bytes_reproduced_exactly": True})
        claim_cap = cap(self.roots["claim_capture"], "claim", "corrected_claim_review_actual_rc0_captured",
                        {"status": "corrected_factual_claim_inputs_verified", "source_bindings": sb,
                         "original_primary_negative_findings_preserved": True, "new_inferential_promotion": False})
        bindings_path = self.roots["source_verification_bindings"]
        save(bindings_path, self.bindings)
        self.request = {"schema_version": 1, "status": "corrected_release_staging_inputs_bound", "test_only": False,
                        "verification_bindings": {"path": str(bindings_path), "sha256": c.sha(bindings_path)},
                        "mixed_completion_sha256": completion_sha, "source_capture": source_capture, "selection_sha256": selection_sha,
                        "reproduction_pass": {"relative_path": "passes/fictional_complete.json", "sha256": pass_sha}, "reproduction_capture": repro_cap,
                        "receiving_reproduction_preparation_sha256": prep_shas["receiving_reproduction_preparation"],
                        "release_adapter_preparation_sha256": prep_shas["release_adapter_preparation"],
                        "support_source_sha256": support_shas, "support_paths": {name: str(path) for name, path in support_paths.items()},
                        "source_reporting_capture": reporting_cap, "claim_capture": claim_cap, "strict_native_clone": False,
                        "transport_code": str(self.source / "fictional_transport"), "external_baselines":
                            {name: {"trusted_release_inventory_canonical_sha256": "e" * 64, "files": {relative: binding(self.roots[name] / relative)
                             for relative in ("manifest.json", "completion.json")}} for name in ("primary", "sampler", "robustness")},
                        "retained_files": [], "historical_file_aliases": [],
                        "external_retained_file_bindings": {name: c.inventory_tree(self.roots[name], c.Pins())["files"] for name in c.EXTERNAL}}
        for role in ("source_reproduction_bindings", "source_reporting_request", "source_claim_request"):
            request_path = self.roots["support"] / (role + ".json")
            files = {"mixed_completion": self.roots["mixed_verified"] / "completion.json", "source_capture": Path(source_capture["path"]),
                "renderer": self.roots["analysis"] / "scripts/render_extensions.py", "renderer_adapter": self.roots["verification_preparation"] / "render_verified_mix.py",
                "selection": self.roots["reproduction"] / "selection.json", "selected_pass": pass_path,
                "correction_manifest": Path(self.bindings["files"]["manifest"]["path"]), "explanation": self.roots["primary"] / "explanation.json"}
            roots = {name: str(self.roots[name]) for name in ("mixed_verified", "reproduction", "rendered", "qa", "primary", "sampler", "robustness")}
            if role == "source_reporting_request":
                roots.update(sidecar=str(self.roots["reporting"]), payload=str(self.source))
                files["claim_stdout"] = Path(claim_cap["path"]).with_name("claim.stdout.log")
            save(request_path, {"fictional_request": role, "roots": roots,
                "preparation_receipt": {"path": str(support_preparation_path), "sha256": self.pins["reporting_qa_preparation_sha256"]},
                "files": {name: {"path": str(path), "sha256": c.sha(path)} for name, path in files.items()}})
            self.request[role] = {"path": str(request_path), "sha256": c.sha(request_path)}
        repro_proof = self.roots["source_reproduction_review"] / "receipt.json"
        save(repro_proof, {"status": "corrected_selected_reproduction_restored_read_only_verified",
                          "test_only_dependency_injection": False, "artifacts": {}})
        report_proof = self.roots["source_reporting_review"] / "reporting_replay_receipt.json"
        save(report_proof, {"status": "corrected_reporting_source_replay_verified", "source_bindings": sb,
                           "test_only": False, "artifacts": {}})
        mixed_script = self.roots["verification_preparation"] / "verify_mixed_extensions.py"
        command_cap(self.request["source_capture"], mixed_script, mixed_options, mixed_sources=mixed_sources)
        repro_script = self.roots["receiving_reproduction_preparation"] / "verify_restored_reproduction.py"
        item = self.request["source_reproduction_bindings"]
        command_cap(self.request["reproduction_capture"], repro_script,
            ["--bindings", item["path"], "--bindings-sha256", item["sha256"],
             "--output", str(self.roots["source_reproduction_review"]), "--python", "/fictional/locked_python"],
            summary_fields={"receipt_path": str(repro_proof), "receipt_sha256": c.sha(repro_proof)})
        item = self.request["source_reporting_request"]
        command_cap(self.request["source_reporting_capture"], support_paths["report_replay"],
            ["--request", item["path"], "--request-sha256", item["sha256"],
             "--output", str(self.roots["source_reporting_review"]), "--python", "/fictional/locked_python"],
            summary_fields={"receipt_path": str(report_proof), "receipt_sha256": c.sha(report_proof)})
        item = self.request["source_claim_request"]
        command_cap(self.request["claim_capture"], support_paths["claim_helper"],
            ["--request", item["path"], "--request-sha256", item["sha256"], "--python", "/fictional/locked_python"])
        self.refresh_assets()
        class Gates:
            def summary(_self):
                return self.source_summary
        def gate(*_args):
            return Gates()
        def copy_file(source, target, **_kwargs):
            shutil.copy2(source, target)
        def copy_tree(source, target, **_kwargs):
            shutil.copytree(source, target)
        def publish(source, destination):
            c.require(not destination.exists(), "fictional no-replace publisher")
            source.rename(destination)
        def archive(_root, target, _commit, _api):
            raw(target, b"fictional archive bytes; no git/package invoked")
        self.deps = {"structural_gates": gate, "source_gate": lambda *_args: None,
                     "source_tracking_gate": lambda *_args: None,
                     "qa_roster": lambda *_args: (self.names, self.tables), "recheck_gates": lambda _state: None,
                     "copy_api": {"copy_file": copy_file, "copy_tree": copy_tree, "publish": publish}, "archive_source": archive}

    def refresh_assets(self):
        self.request["assets"] = {}
        for name, kind in self.kinds.items():
            path = self.roots[name]
            item = {"kind": kind, "source": str(path), "target": c.LAYOUT[name]}
            item["binding" if kind == "file" else "inventory"] = binding(path) if kind == "file" else c.inventory_tree(path, c.Pins())
            self.request["assets"][name] = item

    def validate(self):
        return st.validate(self.request, c.Pins(), self.pins, self.policy, self.deps)

    def stage(self, name="payload"):
        request_path = self.base / (name + "_request.json")
        digest = save(request_path, self.request)
        output = self.base / name
        return output, st.stage(request_path, digest, output, self.pins, dependencies=self.deps, policy=self.policy)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="fictional-corrected-release-tests-")
        # macOS exposes the temporary root through /var -> /private/var.
        # Fixtures use its actual unlinked location; production safe() stays strict.
        self.base = Path(self.temporary.name).resolve(strict=True)

    def tearDown(self):
        self.temporary.cleanup()

    def test_complete_three_route_fixture_and_failure_bytes_stage(self):
        fixture = Fixture(self.base)
        state = fixture.validate()
        self.assertEqual(set(state["reproduction"]["route_counts"]), c.FINAL_REPRO)
        output, result = fixture.stage()
        self.assertTrue(result["test_only"])
        self.assertFalse(result["programme_complete"])
        orphan = output / c.LAYOUT["corrected_run"] / "attempts" / fixture.ids[-1] / "traces" / fixture.ids[-1] / "unreferenced_failed.nc"
        self.assertTrue(orphan.is_file())
        manifest = c.document(output / "corrected_release_stage.json", c.Pins())
        self.assertIn(str(orphan.relative_to(output)), manifest["payload_inventory"]["files"])

    def test_partial_grid_refuses_before_destination(self):
        fixture = Fixture(self.base)
        completion_path = fixture.roots["mixed_verified"] / "completion.json"
        completion = c.document(completion_path, c.Pins())
        completion["verified_logical_cells"] = 2
        fixture.request["mixed_completion_sha256"] = save(completion_path, completion)
        fixture.refresh_assets()
        with self.assertRaisesRegex(ValueError, "mixed deep"):
            fixture.stage()
        self.assertFalse((self.base / "payload").exists())
        self.assertFalse(list(self.base.glob(".corrected-stage-pending-*")))

    def test_missing_or_tampered_failed_trace_refuses(self):
        fixture = Fixture(self.base)
        orphan = fixture.roots["original_run"] / "traces" / fixture.ids[0] / "old_orphan.nc"
        orphan.unlink()
        fixture.refresh_assets()
        with self.assertRaises(ValueError):
            fixture.validate()

    def test_extra_actual_tree_file_refuses_even_when_all_declared_exist(self):
        fixture = Fixture(self.base)
        raw(fixture.roots["preflight"] / "residual.tmp", b"unrecorded failed attempt")
        with self.assertRaisesRegex(ValueError, "tree changed"):
            fixture.validate()

    def test_changed_byte_refuses(self):
        fixture = Fixture(self.base)
        raw(fixture.roots["candidate_module"], b"changed candidate")
        with self.assertRaises(ValueError):
            fixture.validate()

    def test_active_owner_refuses(self):
        fixture = Fixture(self.base)
        save(fixture.roots["original_run"] / "claims" / "owner.json", {"pid": 1})
        fixture.refresh_assets()
        with self.assertRaisesRegex(ValueError, "fit owner"):
            fixture.validate()

    def test_missing_source_gate_rc0_cannot_be_reconstructed(self):
        fixture = Fixture(self.base)
        receipt = Path(fixture.request["source_capture"]["path"])
        value = c.document(receipt, c.Pins())
        value["exit_code"] = 3
        fixture.request["source_capture"]["sha256"] = save(receipt, value)
        fixture.refresh_assets()
        with self.assertRaisesRegex(ValueError, "process capture"):
            fixture.validate()

    def test_malformed_stdout_capture_refuses(self):
        directory = self.base / "capture"
        receipt = cap(directory, "child", "captured", {"status": "done"})
        raw(directory / "child.stdout.log", b"not actual JSON\n")
        with self.assertRaises(ValueError):
            c.capture_record(Path(receipt["path"]), receipt["sha256"], c.Pins(), status="captured", summary_status="done")

    def test_partial_selected_or_failure_not_promoted(self):
        fixture = Fixture(self.base)
        selected = fixture.roots["reproduction"] / fixture.request["reproduction_pass"]["relative_path"]
        value = c.document(selected, c.Pins())
        value["outcomes"][0]["status"] = "retained_reproduction_failure"
        fixture.request["reproduction_pass"]["sha256"] = save(selected, value)
        fixture.refresh_assets()
        with self.assertRaisesRegex(ValueError, "pending or failed"):
            fixture.validate()

    def test_legacy_qa_or_missing_named_review_refuses(self):
        fixture = Fixture(self.base)
        qa_path = fixture.roots["qa"] / "visual_qa_receipt.json"
        value = c.document(qa_path, c.Pins())
        value["source_bindings"] = {"source_run_completion_sha256": fixture.request["mixed_completion_sha256"]}
        save(qa_path, value)
        fixture.refresh_assets()
        with self.assertRaisesRegex(ValueError, "corrected production QA"):
            fixture.validate()

    def test_unreviewed_figure_refuses(self):
        fixture = Fixture(self.base)
        qa_path = fixture.roots["qa"] / "review.json"
        value = c.document(qa_path, c.Pins())
        value["figures"][0]["verdict"] = "fail"
        save(qa_path, value)
        fixture.refresh_assets()
        with self.assertRaises(ValueError):
            fixture.validate()

    def test_missing_report_row_or_duplicate_cell_refuses(self):
        fixture = Fixture(self.base)
        report_path = fixture.roots["reporting"] / "report.json"
        report = c.document(report_path, c.Pins(), field=None)
        report["dimension_ratios"][1]["cell_id"] = report["dimension_ratios"][0]["cell_id"]
        save(report_path, report, None)
        receipt = fixture.roots["reporting"] / "receipt.json"
        value = c.document(receipt, c.Pins())
        value["artifacts"][report_path.name] = binding(report_path)
        save(receipt, value)
        fixture.refresh_assets()
        with self.assertRaisesRegex(ValueError, "row roster"):
            fixture.validate()

    def test_omitted_external_numerical_producer_bytes_refuse(self):
        fixture = Fixture(self.base)
        unknown = self.base / "unshipped_producer.log"
        raw(unknown, b"fictional real producer trace log")
        proof = fixture.roots["reproduction"] / "cells" / (sorted(fixture.ids)[0] + ".json")
        value = c.document(proof, c.Pins())
        value["external_artifacts"][str(unknown)] = binding(unknown)
        save(proof, value)
        pass_path = fixture.roots["reproduction"] / fixture.request["reproduction_pass"]["relative_path"]
        value = c.document(pass_path, c.Pins())
        value["outcomes"][0]["record_sha256"] = c.sha(proof)
        fixture.request["reproduction_pass"]["sha256"] = save(pass_path, value)
        fixture.refresh_assets()
        with self.assertRaisesRegex(ValueError, "bytes omitted"):
            fixture.validate()

    def test_alias_refused_distinct_retained_file_supported(self):
        fixture = Fixture(self.base)
        old = self.base / "historical_worker_trace.nc"
        target = fixture.roots["original_run"] / "traces" / fixture.ids[0] / "old.nc"
        raw(old, target.read_bytes())
        fixture.request["historical_file_aliases"] = [{"historical": str(old), "payload_relative": c.LAYOUT["original_run"] + "/" + str(target.relative_to(fixture.roots["original_run"])), "binding": binding(old)}]
        with self.assertRaisesRegex(ValueError, "receiving v1 refuses"):
            fixture.stage()
        self.assertFalse((self.base / "payload").exists())
        fixture.request["historical_file_aliases"] = []
        fixture.request["retained_files"] = [{"source": str(old), "target": "execution/retained_external/historical_trace.nc", "binding": binding(old)}]
        output, _ = fixture.stage()
        self.assertEqual((output / "execution/retained_external/historical_trace.nc").read_bytes(), target.read_bytes())

    def test_output_overlap_and_overwrite_refuse(self):
        fixture = Fixture(self.base)
        output, _ = fixture.stage()
        with self.assertRaises(ValueError):
            fixture.stage()
        with self.assertRaises(ValueError):
            c.no_overlap(fixture.roots["preflight"] / "nested", [fixture.roots["preflight"]])
        self.assertTrue(output.exists())

    def test_publication_failure_retains_pending_attempt_no_final_destination(self):
        fixture = Fixture(self.base)
        def fail(_source, _destination):
            raise OSError("fictional exclusive publication failure")
        fixture.deps["copy_api"]["publish"] = fail
        with self.assertRaises(OSError):
            fixture.stage()
        self.assertFalse((self.base / "payload").exists())
        self.assertEqual(len(list(self.base.glob(".corrected-stage-pending-payload-*"))), 1)

    def test_source_change_during_copy_refuses(self):
        fixture = Fixture(self.base)
        original = fixture.deps["copy_api"]["copy_tree"]
        def corrupt(source, target, **kwargs):
            original(source, target, **kwargs)
            if source == fixture.roots["preflight"]:
                raw(source / "late_write.json", b"new owner output")
        fixture.deps["copy_api"]["copy_tree"] = corrupt
        with self.assertRaises(ValueError):
            fixture.stage()
        self.assertFalse((self.base / "payload").exists())

    def test_symlink_duplicate_json_and_nonfinite_refuse(self):
        file = self.base / "small.json"
        raw(file, b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            c.document(file, c.Pins(), field=None)
        raw(file, b'{"a":NaN}')
        with self.assertRaises(ValueError):
            c.document(file, c.Pins(), field=None)
        (self.base / "alias").symlink_to(file)
        with self.assertRaises(ValueError):
            c.sha(self.base / "alias")

    def test_actual_capture_injected_rc0_and_nonzero_failure(self):
        script = self.base / "fictional_checker.py"
        raw(script, b"# never actually executed\n")
        def check(value):
            c.require(value == {"status": "fixture_checked"}, "summary mismatch")
        def ok(*_args, **_kwargs):
            return SimpleNamespace(returncode=0, stdout=b'{"status":"fixture_checked"}\n', stderr=b"fixture only\n")
        result = c.capture_process(["fictional", str(script)], self.base / "ok", c.Pins(), status="fixture_capture", validate_summary=check,
                                   entrypoint=script, entrypoint_sha=c.sha(script), invoke=ok)
        self.assertEqual(result["exit_code"], 0)
        def fail(*_args, **_kwargs):
            return SimpleNamespace(returncode=7, stdout=b'{"status":"fixture_checked"}\n', stderr=b"retained failure\n")
        with self.assertRaises(ValueError):
            c.capture_process(["fictional", str(script)], self.base / "failed", c.Pins(), status="fixture_capture", validate_summary=check,
                              entrypoint=script, entrypoint_sha=c.sha(script), invoke=fail)
        self.assertFalse((self.base / "failed.receipt.json").exists())
        self.assertEqual(c.document(self.base / "failed.attempt.json", c.Pins())["exit_code"], 7)

    def test_capture_link_failure_preserves_closed_temp(self):
        path = self.base / "receipt.json"
        with patch("verification_io.os.link", side_effect=OSError("injected hard-link failure")):
            with self.assertRaises(OSError):
                c.write_new(path, c.seal({"fictional": True}))
        self.assertFalse(path.exists())
        self.assertEqual(len(list(self.base.glob(".verification-pending-receipt.json-*"))), 1)

    def test_wrong_captured_producer_command_refuses_before_stage(self):
        fixture = Fixture(self.base)
        receipt_path = Path(fixture.request["source_capture"]["path"])
        attempt_path = receipt_path.with_name("source.attempt.json")
        attempt = c.document(attempt_path, c.Pins())
        attempt["argv"][3] = str(fixture.roots["reproduction_preparation"] / "run_reproduction.py")
        save(attempt_path, attempt)
        receipt = c.document(receipt_path, c.Pins())
        receipt["invocation_attempt_sha256"] = c.sha(attempt_path)
        receipt["artifacts"][attempt_path.name] = binding(attempt_path)
        fixture.request["source_capture"]["sha256"] = save(receipt_path, receipt)
        fixture.refresh_assets()
        with self.assertRaisesRegex(ValueError, "entrypoint/arguments"):
            fixture.stage()
        self.assertFalse((self.base / "payload").exists())

    def test_boolean_false_is_not_an_actual_zero_return_code(self):
        receipt = cap(self.base / "capture", "boolean", "fixture_capture", {"status": "fixture_ok"})
        path = Path(receipt["path"])
        attempt_path = path.with_name("boolean.attempt.json")
        attempt = c.document(attempt_path, c.Pins())
        attempt["exit_code"] = False
        save(attempt_path, attempt)
        value = c.document(path, c.Pins())
        value["invocation_attempt_sha256"] = c.sha(attempt_path)
        value["artifacts"][attempt_path.name] = binding(attempt_path)
        digest = save(path, value)
        with self.assertRaisesRegex(ValueError, "untyped"):
            c.capture_record(path, digest, c.Pins(), status="fixture_capture", summary_status="fixture_ok")

    def test_launch_error_retained_without_receipt(self):
        script = self.base / "fictional_script.py"
        raw(script, b"# fictional; never executed\n")
        def unavailable(*_args, **_kwargs):
            raise OSError("injected missing executable")
        with self.assertRaisesRegex(ValueError, "child failed"):
            c.capture_process(["/fictional/python", str(script)], self.base / "unavailable", c.Pins(), status="fixture_capture",
                validate_summary=lambda _value: None, entrypoint=script, entrypoint_sha=c.sha(script), invoke=unavailable)
        attempt = c.document(self.base / "unavailable.attempt.json", c.Pins())
        self.assertIsNone(attempt["exit_code"])
        self.assertIsNotNone(attempt["launch_error"])
        self.assertFalse((self.base / "unavailable.receipt.json").exists())

    def test_staged_test_payload_never_certifies_actual_restore(self):
        fixture = Fixture(self.base)
        output, _ = fixture.stage()
        with self.assertRaisesRegex(ValueError, "actual corrected staged"):
            vr.verify_payload(output, c.sha(output / "corrected_release_stage.json"), c.Pins())

    def test_relocated_role_mapping_exact_bytes_and_no_guessing(self):
        fixture = Fixture(self.base)
        output, _ = fixture.stage()
        manifest = c.document(output / "corrected_release_stage.json", c.Pins())
        receiving = copy.deepcopy(fixture.bindings)
        for name in c.ROOTS - c.EXTERNAL:
            receiving["roots"][name] = str(output / c.LAYOUT[name])
        for name, row in manifest["verified_input_file_locations"].items():
            receiving["files"][name] = {"path": str(output / row["relative_path"]), "sha256": row["sha256"]}
        receiving["review_paths"] = {name: str(output / row["relative_path"]) for name, row in manifest["verified_review_locations"].items()}
        vr.validate_remapping(output, manifest, receiving, c.Pins())
        receiving["roots"]["preflight"] = str(fixture.roots["preflight"])
        with self.assertRaisesRegex(ValueError, "remapping"):
            vr.validate_remapping(output, manifest, receiving, c.Pins())


if __name__ == "__main__":
    unittest.main(verbosity=2)
