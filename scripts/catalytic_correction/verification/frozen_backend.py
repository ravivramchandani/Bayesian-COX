"""Actual byte-pinned reconstruction/diagnostic/scoring/reducer backend.

Importing this preparation module imports only stdlib. Scientific imports,
cohort loading and calculations occur only when root constructs FrozenBackend
after explicit manifest/source binding. Synthetic tests inject another backend.
No function calls generation, matrix rank/SVD, fitting or sampling.
"""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from verification_io import Pins, canonical, child, require


def array_witness(array: Any) -> dict[str, Any]:
    """Retain numeric dtype/shape/C-order elements, including scalar shape []."""
    require(not array.dtype.hasobject, "object-valued encoded array is forbidden")
    return {"dtype": array.dtype.str, "shape": list(array.shape),
            "values_sha256": hashlib.sha256(array.tobytes(order="C")).hexdigest()}


def load_verification_definitions(path: Path, namespace: dict[str, Any]) -> SimpleNamespace:
    """Compile the unchanged source-pinned855 pure verification definitions.

    Shared scientific dependencies are normally imported from119 and have
    identical855 bytes. This avoids competing project package namespaces.
    """
    selected = {"SavedForecast", "assert_scientific_equal", "verify_trace_diagnostics", "verify_cell_identity"}
    tree = ast.parse(path.read_bytes(), filename=str(path))
    definitions = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.ClassDef))
                   and node.name in selected]
    require({node.name for node in definitions} == selected, "frozen855 verification definitions unavailable")
    future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
    module = ast.fix_missing_locations(ast.Module(body=[future, *definitions], type_ignores=[]))
    scope = dict(namespace)
    exec(compile(module, str(path), "exec"), scope)
    return SimpleNamespace(**{name: scope[name] for name in selected})


class FrozenBackend:
    """Root-invoked scientific implementation with exact original source inputs."""

    def __init__(self, production: Path, analysis: Path, matched: Path,
                 original_manifest: dict[str, Any], source_pins: dict[str, Any], pins: Pins) -> None:
        require(not any(name == "src" or name.startswith("src.") for name in sys.modules),
                "fresh isolated project namespace is required")
        self.production, self.analysis, self.matched, self.pins = production, analysis, matched, pins
        self.manifest, self.source_pins = original_manifest, source_pins
        for role, root in (("production", production), ("analysis", analysis)):
            for name, expected in source_pins["files"][role].items():
                pins.bind(child(root, name), expected)
        for name, expected in original_manifest["input_sha256"].items():
            pins.bind(child(production, name), expected)
        pins.bind(matched, original_manifest["matched_sha256"])
        sys.path.insert(0, str(production))
        self.np = importlib.import_module("numpy")
        self.pd = importlib.import_module("pandas")
        self.az = importlib.import_module("arviz")
        self.io = importlib.import_module("src.utils.io")
        self.options = importlib.import_module("src.pipelines.confirmatory.options")
        self.evaluation = importlib.import_module("src.pipelines.confirmatory.evaluation")
        self.diagnostics = importlib.import_module("src.models.bayesian.diagnostics")
        self.runner = importlib.import_module("src.pipelines.extensions.runner")
        self.planning = importlib.import_module("src.pipelines.extensions.planning")
        self.preprocessing = importlib.import_module("src.pipelines.extensions.preprocessing")
        self.conditions = importlib.import_module("src.pipelines.robustness.conditions")
        self.reducers = importlib.import_module("src.pipelines.extensions.analysis")
        self.rq2 = importlib.import_module("src.pipelines.extensions.rq2")
        self.primary_verifier = importlib.import_module("src.rendering.verification")
        self.sampler_verifier = importlib.import_module("src.utils.posthoc_evidence")
        self.verify_module_origins()
        reference_path = analysis / "src/pipelines/extensions/verification.py"
        self.reference = load_verification_definitions(reference_path, {
            "np": self.np, "pd": self.pd, "az": self.az,
            "deterministic_seed": self.options.deterministic_seed,
            "canonical_json_hash": canonical,
        })
        self.config = self.io.read_mapping(production / "config/extensions.yaml")
        self.primary_config = self.io.read_mapping(production / "config/confirmatory.yaml")
        self.datasets = self.io.read_mapping(production / "config/datasets.yaml")
        require(self.config == original_manifest["run_config"], "frozen original configuration differs")
        self.cohorts = self.runner.load_extension_cohorts(production, matched)
        self.jobs = self.planning.build_extension_jobs(self.cohorts, self.config)
        rebuilt = [{"cell_id": job.cell_id,
                    "train_sha256": canonical(self.cohorts[job.dataset].subject_id.iloc[job.train].tolist()),
                    "validation_sha256": canonical(self.cohorts[job.dataset].subject_id.iloc[job.validation].tolist()),
                    "censoring_cutoff": job.censoring_cutoff} for job in self.jobs]
        require(rebuilt == original_manifest["plan"] and original_manifest["planned_fits"] == len(self.jobs) == 1625,
                "independently reconstructed original full plan differs")

    def verify_module_origins(self) -> None:
        """Reject imported project modules from changed or foreign namespaces."""
        for name, module in list(sys.modules.items()):
            if name == "src" or name.startswith("src."):
                path = Path(getattr(module, "__file__", "")).absolute()
                require(path.is_relative_to(self.production), "foreign imported project module")
                relative = str(path.relative_to(self.production))
                require(relative in self.source_pins["files"]["production"], "unbound imported project module")
                self.pins.bind(path, self.source_pins["files"]["production"][relative])

    def identity(self, cell: dict[str, Any], job: Any) -> None:
        self.reference.verify_cell_identity(cell, job, self.cohorts[job.dataset], self.config["base_seed"])

    def assert_equal(self, left: Any, right: Any, label: str) -> None:
        self.reference.assert_scientific_equal(left, right, label)

    def real_inputs(self, job: Any) -> dict[str, Any]:
        """Rebuild memberships/censored outcomes and actual encoded designs only."""
        np, raw = self.np, self.cohorts[job.dataset]
        training, validation = raw.iloc[job.train], raw.iloc[job.validation]
        tt, ee = self.conditions.apply_administrative_censoring(
            training.duration.to_numpy(float), training.event.to_numpy(int), job.censoring_cutoff)
        vt, ve = self.conditions.apply_administrative_censoring(
            validation.duration.to_numpy(float), validation.event.to_numpy(int), job.censoring_cutoff)
        base = {"training_time": tt.tolist(), "training_event": ee.tolist(),
                "observed_time": vt.tolist(), "observed_event": ve.tolist(), "events_train": int(ee.sum()),
                "training_membership_sha256": canonical(training.subject_id.tolist()),
                "validation_membership_sha256": canonical(validation.subject_id.tolist()),
                "training_outcomes_sha256": canonical({"time": tt.tolist(), "event": ee.tolist()}),
                "validation_outcomes_sha256": canonical({"time": vt.tolist(), "event": ve.tolist()})}
        if ee.sum() < 20:
            return {**base, "preprocessing_status": "unreached_original_training_event_rule"}
        dataset = "metabric" if job.dataset == "metabric_matched" else job.dataset
        specification = self.datasets[dataset]["primary_features"]
        try:
            processor = self.preprocessing.ExtensionPreprocessor(specification, job.gene_budget).fit(training)
            xt, xv = processor.transform(training), processor.transform(validation)
        except Exception as error:
            return {**base, "preprocessing_status": "original_preprocessing_execution_failure",
                    "exception_type": type(error).__name__, "message": str(error)}
        require(np.isfinite(xt.to_numpy(float)).all() and np.isfinite(xv.to_numpy(float)).all(),
                "independently reconstructed encoded design is nonfinite")
        return {**base, "preprocessing_status": "reconstructed", "preprocessing": processor.metadata(),
                "feature_spec": specification, "feature_names": list(processor.feature_names), "p": xt.shape[1],
                "encoded_training": array_witness(xt.to_numpy(float)),
                "encoded_validation": array_witness(xv.to_numpy(float)),
                "validation_frame": xv}

    def trace_diagnostics(self, path: Path, label: str, expected: dict[str, Any] | None,
                          identity: str) -> dict[str, Any]:
        """Recompute all-parameter855 diagnostics, closing one trace at a time."""
        idata = self.az.from_netcdf(str(path))
        try:
            observed = self.io.json_safe(self.diagnostics.check_convergence(idata))
            if expected is not None:
                self.reference.verify_trace_diagnostics(expected, observed, idata, label, identity)
            metadata = {"chain": int(idata.posterior.sizes["chain"]),
                        "draw": int(idata.posterior.sizes["draw"]),
                        "posterior_variables": sorted(idata.posterior.data_vars)}
            # The independently recomputed numerical values have already been
            # compared under the unchanged855 tolerance. Retain the stable
            # stored-record digest, not a new exact-float replay gate. Unstored
            # traces establish audit availability only, never original gates.
            return {"status": "diagnostics_recomputed", "actual_trace_metadata": metadata,
                    "stored_diagnostics_verified_sha256": None if expected is None else canonical(expected),
                    "stored_comparison_tolerance": None if expected is None else 1e-10,
                    "computation_scope": "frozen_check_convergence_all_parameters",
                    "unstored_diagnostic_scope": None if expected is not None else "availability_audit_only; raw_trace_retained"}
        finally:
            idata.close()

    def rescore(self, cell: dict[str, Any], job: Any, real: dict[str, Any]) -> dict[str, Any]:
        """Evaluate saved forecasts on independently reconstructed ordered outcomes."""
        np = self.np
        metrics, _ = self.evaluation.evaluate_predictions(
            self.reference.SavedForecast(cell["predictions"]), real["validation_frame"],
            np.asarray(real["training_time"], dtype=float), np.asarray(real["training_event"], dtype=int),
            np.asarray(real["observed_time"], dtype=float), np.asarray(real["observed_event"], dtype=int),
            evaluation_config=self.primary_config["evaluation"],
            calibration_bootstraps=self.config["calibration_bootstraps"], seed=cell["seed"])
        return self.io.json_safe(metrics)

    def references(self, primary: Path, sampler: Path, robustness: Path) -> dict[str, Any]:
        """Delegate the unchanged baseline verifiers and preserve original findings."""
        pinned = json.loads((self.analysis / "coordination/extension_sources/baseline_sources.json").read_text())
        roots = {"primary": primary, "sampler_adr032": sampler, "robustness": robustness}
        for role, root in roots.items():
            for name in ("manifest", "completion"):
                self.pins.bind(root / (name + ".json"), pinned[role][name + "_sha256"])
        original = self.primary_verifier.verify_frozen_run(primary)
        horse = self.sampler_verifier.verify_posthoc_run(sampler, primary)
        robust, robust_summary = self.primary_verifier.verify_robustness_run(robustness, original)
        original_cells = [cell for _, cell in original.cells]
        references = [cell for cell in original_cells if cell["model_key"] != "bayesian_horseshoe"] + horse["cells"]
        original_horse = [{**cell, "model_key": "bayesian_horseshoe_original"}
                          for cell in original_cells if cell["model_key"] == "bayesian_horseshoe"]
        # The frozen verifiers check their full completion-bound artifacts. Bind
        # every completion-recorded referenced artifact again for final recheck.
        for root in roots.values():
            completion = self.io.read_mapping(root / "completion.json")
            for field in ("cell_sha256", "all_stored_cell_hashes", "aggregate_sha256", "artifact_sha256"):
                for name, expected in completion.get(field, {}).items():
                    self.pins.bind(child(root, name), expected)
        return {"references": references, "original_horseshoe_for_dca": original_horse,
                "robustness": robust["cells"],
                "summary": {"source_bindings": pinned,
                    "verification_scope": "delegated_unchanged_frozen_baseline_verifiers",
                    "primary_status_counts": dict(Counter(cell["status"] for cell in original_cells)),
                    "primary_raw_record_preserved": True,
                    "primary_negative_or_incomplete_findings_not_reanalysed_or_promoted": True,
                    "adr032_horseshoe_is_separate_from_original_dca_arm": True,
                    "robustness_summary": {key: value for key, value in robust_summary.items() if key != "artifact"}}}

    def aggregate(self, cells: list[dict[str, Any]], references: dict[str, Any]) -> dict[str, Any]:
        """Delegate exact existing families/RQ2/DCA, with no new tests/estimands."""
        known_pairs = self.pd.read_csv(self.analysis / "tests/fixtures/extensions/metabric_known_accession_pairs.csv")
        results = {"paired_families.json": self.reducers.extension_families(cells, references["references"]),
                   "rq2_effects.json": self.rq2.rq2_effects(cells, references["robustness"], self.cohorts),
                   "decision_curves.json": self.reducers.curves_from_cells(
                       cells + references["references"] + references["original_horseshoe_for_dca"], self.config, known_pairs)}
        expected = {"penalized_vs_original_priors": 27, "calibrated_vs_adr032_horseshoe": 3,
                    "catalytic_vs_original_priors": 27, "expression_increment": 13}
        families = results["paired_families.json"]
        require(set(families) == set(expected) and all(len(families[key]["contrasts"]) == count
                and families[key]["expected_contrasts"] == count for key, count in expected.items()),
                "frozen four-family contrast scope changed")
        self.verify_module_origins()
        return self.io.json_safe(results)
