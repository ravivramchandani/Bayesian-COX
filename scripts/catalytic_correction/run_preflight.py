"""Execute only the frozen-grid training-input feasibility preflight."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

if __package__:
    from .preflight_core import (  # noqa: E402
        Claim,
        InvalidCheckpoint,
        PreflightEngine,
        canonical_hash,
        read_sealed,
        seal,
        sha256_file,
        write_json_new,
    )
else:
    from preflight_core import (  # noqa: E402
        Claim,
        InvalidCheckpoint,
        PreflightEngine,
        canonical_hash,
        read_sealed,
        seal,
        sha256_file,
        write_json_new,
    )

MANIFEST_SHA = "83b9049fb6aaaadab576b34de0741e4f510344dcefba9f96198d15b5ab4f49b9"
MANIFEST_CONTENT_SHA = "4577c615486ee871d508837aa812f59539b59338c63834716453a8b03ea394a3"
PRODUCTION_COMMIT = "119476fef55b1eeb690527f234c1423440720d45"
CANDIDATE_SHA = "64963c33b067c3c67f5406037a3782820d99c1d687598a9536c72225e6939f11"
CELL_RE = re.compile(r"(gbsg2|whas500|metabric|metabric_matched)__(clinical|expression)__r(\d{2})f(\d{2})__(catalytic_fixed|catalytic_adaptive|catalytic_wme)__(full|fraction_0\.(?:25|50|75)|admin_q0\.(?:50|75))")


def safe_absolute(path: Path) -> Path:
    """Reject linked input/output paths before normalizing an explicit argument."""
    path = path.absolute()
    if ".." in path.parts or any(item.is_symlink() for item in (path, *path.parents)):
        raise InvalidCheckpoint(f"unsafe linked or parent-relative path: {path}")
    return path


def locked_interpreter(path: Path) -> Path:
    """Allow a conda Python symlink only when its target is this interpreter."""
    supplied = path.absolute()
    if ".." in supplied.parts or not supplied.is_file():
        raise InvalidCheckpoint("an explicit existing lock interpreter is required")
    resolved = safe_absolute(supplied.resolve(strict=True))
    if not resolved.samefile(Path(sys.executable)):
        raise InvalidCheckpoint("controller and proposal child must use the same explicit lock interpreter")
    return resolved


def load_candidate(path: Path, expected_sha256: str = CANDIDATE_SHA) -> Any:
    """Import only the reviewed candidate bytes from an explicit module path."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256) or sha256_file(path) != expected_sha256:
        raise InvalidCheckpoint("candidate source differs from the reviewed candidate")
    spec = importlib.util.spec_from_file_location("_reviewed_rank_candidate", path)
    if spec is None or spec.loader is None:
        raise InvalidCheckpoint("cannot import reviewed candidate")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def verify_bindings(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    """Verify frozen bytes and the entire recipe inventory before cohort loading."""
    manifest_path = args.run / "manifest.json"
    if sha256_file(manifest_path) != MANIFEST_SHA:
        raise InvalidCheckpoint("original manifest bytes differ")
    manifest = json.loads(manifest_path.read_text())
    if manifest["manifest_content_sha256"] != MANIFEST_CONTENT_SHA or canonical_hash({key: value for key, value in manifest.items() if key != "manifest_content_sha256"}) != MANIFEST_CONTENT_SHA:
        raise InvalidCheckpoint("original manifest canonical content differs")
    if manifest["code"]["git_commit"] != PRODUCTION_COMMIT or manifest["code"]["git_dirty"]:
        raise InvalidCheckpoint("original manifest code identity differs")
    git_executable = shutil.which("git")
    if git_executable is None:
        raise InvalidCheckpoint("Git is required to verify the sealed source checkout")
    commit = subprocess.run([git_executable, "rev-parse", "HEAD"], cwd=args.source, capture_output=True, text=True, check=True).stdout.strip()  # noqa: S603 - resolved local Git, fixed read-only arguments
    status = subprocess.run([git_executable, "status", "--porcelain"], cwd=args.source, capture_output=True, text=True, check=True).stdout  # noqa: S603 - resolved local Git, fixed read-only arguments
    if commit != PRODUCTION_COMMIT or status:
        raise InvalidCheckpoint("scientific source must be clean sealed 119476f")
    for name, expected in manifest["input_sha256"].items():
        path = safe_absolute(args.source / name)
        if sha256_file(path) != expected:
            raise InvalidCheckpoint(f"original source/input bytes differ: {name}")
    if not re.fullmatch(r"[0-9a-f]{64}", args.candidate_sha256) or sha256_file(args.matched) != manifest["matched_sha256"] or sha256_file(args.candidate_module) != args.candidate_sha256:
        raise InvalidCheckpoint("matched parquet or candidate bytes differ")
    receipt = json.loads((args.inventory / "preparation_receipt.json").read_text())
    if receipt["content_sha256"] != canonical_hash({key: value for key, value in receipt.items() if key != "content_sha256"}):
        raise InvalidCheckpoint("recipe inventory receipt content differs")
    for name, binding in receipt["artifacts"].items():
        path = safe_absolute(args.inventory / name)
        if path.stat().st_size != binding["bytes"] or sha256_file(path) != binding["sha256"]:
            raise InvalidCheckpoint("recipe inventory artifact differs")
    rows = [json.loads(line) for line in (args.inventory / "contexts.jsonl").read_text().splitlines()]
    validate_inventory(rows, manifest)
    import yaml
    correction = yaml.safe_load(args.correction_config.read_text())
    expected_proposal = {"first_seed": "original_generation_seed", "retry_seed_label": "rank_conditioned_retry",
                         "retry_seed_indices": [1, 255], "attempt_cap_including_first": 256,
                         "redraw": "complete_original_covariate_and_time_proposal",
                         "retry_only": "exact_original_constructor_rank_rejection",
                         "rank_rule": "original_numpy_matrix_rank_default", "exhaustion": "explicit_execution_failure"}
    if correction.get("original_production_commit") != PRODUCTION_COMMIT or correction.get("outer_contexts") != 825 or correction.get("inner_contexts") != 825 or correction.get("proposal") != expected_proposal or args.cap != 256:
        raise InvalidCheckpoint("correction proposal/configuration differs from the reviewed preflight candidate")
    if correction.get("execution", {}).get("preflight_workers") != 1 or correction["execution"].get("numeric_threads") != 1:
        raise InvalidCheckpoint("preflight execution must be serial with numeric threads one")
    binding = {"schema_version": 1, "scope": "training_only_candidate_feasibility_no_fits",
               "source_path": str(args.source), "original_run_path": str(args.run), "matched_path": str(args.matched),
               "candidate_module_path": str(args.candidate_module), "original_production_commit": commit,
               "original_manifest_sha256": MANIFEST_SHA, "original_manifest_content_sha256": MANIFEST_CONTENT_SHA,
               "original_input_sha256": manifest["input_sha256"], "matched_sha256": manifest["matched_sha256"],
               "candidate_source_sha256": args.candidate_sha256, "inventory_receipt_sha256": sha256_file(args.inventory / "preparation_receipt.json"),
               "contexts_jsonl_sha256": sha256_file(args.inventory / "contexts.jsonl"), "candidate_cap_including_first": args.cap,
               "correction_config_sha256": sha256_file(args.correction_config), "correction_addendum_sha256": sha256_file(args.correction_addendum),
               "runner_source_sha256": {name: sha256_file(Path(__file__).parent / name) for name in ("run_preflight.py", "preflight_core.py")},
               "scheduled_outer_contexts": 825, "scheduled_inner_contexts": 825, "scheduled_contexts": 1650,
               "proposal_child_policy": "one_new_isolated_child_per_new_proposal; exact_verified_attempt_checkpoints_only_on_resume",
               "processor_mode": "restored_verified_metadata_and_narrow_source_columns" if args.restore_processor_state else "independent_full_training_fit_in_each_proposal_child",
               "numeric_threads": 1, "validation_arrays_saved_or_generated": False,
               "fit_reuse_certified": False, "scientific_method_approved": False, "corrected_fit_freeze_created": False}
    return manifest, rows, binding


def validate_inventory(rows: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    """Verify every context, candidate-use seed and frozen manifest position."""
    def candidate_seed(base: int, *parts: object) -> int:
        payload = "|".join([str(base), *(str(part) for part in parts)])
        return int.from_bytes(hashlib.sha256(payload.encode()).digest()[:4], "big") % (2**31 - 1)
    if len(rows) != 1650 or len({row["context_id"] for row in rows}) != 1650:
        raise InvalidCheckpoint("recipe context coverage differs")
    plan = {item["cell_id"]: item for item in manifest["plan"]}
    outer = {row["outer_cell_id"] for row in rows if row["context"] == "outer"}
    expected = {name for name in plan if CELL_RE.fullmatch(name)}
    if len(outer) != 825 or outer != expected:
        raise InvalidCheckpoint("outer generator coverage differs")
    for row in rows:
        match = CELL_RE.fullmatch(row["outer_cell_id"])
        if match is None:
            raise InvalidCheckpoint("invalid context cell ID")
        dataset, setting, repeat, fold, model, condition = match.groups()
        if (row["dataset"], row["setting"], row["repeat"], row["fold"], row["model"], row["condition"]) != (dataset, setting, int(repeat), int(fold), model, condition):
            raise InvalidCheckpoint("context labels differ from original cell ID")
        source = plan[row["outer_cell_id"]]
        if (row["outer_train_sha256_from_manifest"], row["outer_validation_sha256_from_manifest"], row["censoring_cutoff_from_manifest"]) != (source["train_sha256"], source["validation_sha256"], source["censoring_cutoff"]):
            raise InvalidCheckpoint("context manifest membership reference differs")
        cell_seed = candidate_seed(260817, "extensions", row["outer_cell_id"])
        inner_seed = candidate_seed(cell_seed, "inner_cv")
        generation_seed = candidate_seed(cell_seed, "outer_prior") if row["context"] == "outer" else candidate_seed(inner_seed, "inner_prior", row["inner_fold"])
        if row["cell_seed"] != cell_seed or row["inner_cv_seed"] != inner_seed or row["generation_seed"] != generation_seed or row["outer_evaluation_seed"] != cell_seed:
            raise InvalidCheckpoint("original stochastic seed namespace differs")
        if row["base_seed"] != 260817 or row["outer_split_seed"] != 260817 + 1009 * (int(repeat) - 1):
            raise InvalidCheckpoint("outer fold seed differs")
        expected_subset = candidate_seed(260817, "robustness_subset", dataset, int(repeat), int(fold)) if condition.startswith("fraction_") else None
        if row["robustness_subset_seed"] != expected_subset or row["gene_budget"] != (512 if setting == "expression" else 0):
            raise InvalidCheckpoint("training subset seed or gene budget differs")
        if row["original_outer_fit_attempt_seeds"] != [candidate_seed(cell_seed, "fit_attempt", index) for index in range(1 if model == "catalytic_wme" else 3)]:
            raise InvalidCheckpoint("original fit-attempt seeds differ")
        if row["context"] == "inner":
            if model != "catalytic_wme" or row["inner_fold"] not in {1, 2, 3} or row["inner_split_seed"] != inner_seed:
                raise InvalidCheckpoint("unexpected inner context")
            expected_uses = [{"candidate_index_zero_based": index, "tau_multiplier": value,
                              "inner_fit_seed": candidate_seed(inner_seed, "inner_fit", row["inner_fold"], index)} for index, value in enumerate((0.25, 1.0, 4.0))]
            if row["shared_tau_candidate_uses"] != expected_uses:
                raise InvalidCheckpoint("shared WME candidate uses differ")
    for cell_id in outer:
        relevant = [row for row in rows if row["outer_cell_id"] == cell_id]
        required = {"outer", "inner_01", "inner_02", "inner_03"} if "__catalytic_wme__" in cell_id else {"outer"}
        if {row["context_id"].split("::")[-1] for row in relevant} != required or len(relevant) != len(required):
            raise InvalidCheckpoint("outer/inner context grouping differs")


class FrozenBackend:
    """Call original input functions by normal import, never fit/evaluate helpers."""

    def __init__(self, args: argparse.Namespace, manifest: dict[str, Any]) -> None:
        if any(name == "src" or name.startswith("src.") for name in sys.modules):
            raise InvalidCheckpoint("foreign src modules already loaded")
        self.initial_binding = verify_bindings(args)[2]
        sys.path.insert(0, str(args.source))
        runner = importlib.import_module("src.pipelines.extensions.runner")
        planning = importlib.import_module("src.pipelines.extensions.planning")
        preprocessing = importlib.import_module("src.pipelines.extensions.preprocessing")
        folds = importlib.import_module("src.data.survival_folds")
        conditions = importlib.import_module("src.pipelines.robustness.conditions")
        io = importlib.import_module("src.utils.io")
        for name, module in list(sys.modules.items()):
            if name == "src" or name.startswith("src."):
                path = Path(module.__file__).absolute()
                if not path.is_relative_to(args.source):
                    raise InvalidCheckpoint("scientific normal import came from a different checkout")
                relative = str(path.relative_to(args.source))
                if relative not in manifest["input_sha256"] or sha256_file(path) != manifest["input_sha256"][relative]:
                    raise InvalidCheckpoint("scientific imported source bytes differ")
        self.args, self.manifest = args, manifest
        self.runner, self.planning, self.preprocessing, self.folds = runner, planning, preprocessing, folds
        self.conditions, self.specs = conditions, io.read_mapping(args.source / "config/datasets.yaml")
        self.cohorts = runner.load_extension_cohorts(args.source, args.matched)
        all_jobs = planning.build_extension_jobs(self.cohorts, manifest["run_config"])
        plan = [{"cell_id": job.cell_id,
                 "train_sha256": canonical_hash(self.cohorts[job.dataset].subject_id.iloc[job.train].tolist()),
                 "validation_sha256": canonical_hash(self.cohorts[job.dataset].subject_id.iloc[job.validation].tolist()),
                 "censoring_cutoff": job.censoring_cutoff} for job in all_jobs]
        if plan != manifest["plan"] or len(all_jobs) != 1625:
            raise InvalidCheckpoint("independently rebuilt original job plan differs")
        self.jobs = {job.cell_id: job for job in all_jobs}

    def feature_spec(self, dataset: str) -> dict[str, Any]:
        return self.specs["metabric" if dataset == "metabric_matched" else dataset]["primary_features"]

    def apply_censor(self, times: Any, events: Any, cutoff: float | None) -> Any:
        return self.conditions.apply_administrative_censoring(times, events, cutoff)

    def inner_folds(self, times: Any, events: Any, seed: int) -> Any:
        return self.folds.repeated_survival_folds(times, events, n_splits=3, n_repeats=1, base_seed=seed, max_time_bins=4)

    def preprocess(self, specification: dict[str, Any], budget: int, training: Any) -> Any:
        return self.preprocessing.ExtensionPreprocessor(specification, budget).fit(training)

    def original_cell(self, cell_id: str) -> tuple[dict[str, Any], str] | None:
        path = safe_absolute(self.args.run / "cells" / f"{cell_id}.json")
        if not path.exists():
            return None
        before = sha256_file(path)
        value = json.loads(path.read_text())
        if value.get("cell_id") != cell_id or value["cell_content_sha256"] != canonical_hash({key: item for key, item in value.items() if key != "cell_content_sha256"}) or sha256_file(path) != before:
            raise InvalidCheckpoint("original cell identity/content changed")
        return value, before

    def verify_boundary(self) -> None:
        if verify_bindings(self.args)[2] != self.initial_binding:
            raise InvalidCheckpoint("source/input/method bytes changed during preflight")


def parse_args() -> argparse.Namespace:
    """Require explicit data, candidate, method and external-output arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "run", "matched", "inventory", "candidate-module", "correction-config", "correction-addendum", "output", "python"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--cap", type=int, required=True)
    parser.add_argument("--candidate-sha256", required=True, help="explicit reviewed active candidate byte digest")
    parser.add_argument("--restore-processor-state", action="store_true", help="use root-verified metadata restoration and narrow source inputs")
    parser.add_argument("--limit", type=int, help="process only the first N inventory positions; full coverage stays pending")
    parser.add_argument("--recover-stale-claims", action="store_true", help="archive only proven dead claims from this host")
    return parser.parse_args()


def main() -> int:
    """Run the training-only preflight; no fitting/evaluation API is invoked."""
    args = parse_args()
    for name in ("source", "run", "matched", "inventory", "candidate_module", "correction_config", "correction_addendum", "output"):
        setattr(args, name, safe_absolute(getattr(args, name)))
    args.python = locked_interpreter(args.python)
    for forbidden in (args.source, args.run, args.inventory, args.candidate_module.parent):
        if args.output.is_relative_to(forbidden) or forbidden.is_relative_to(args.output):
            raise InvalidCheckpoint("output must be separate from scientific/preparation inputs")
    args.output.mkdir(parents=True, exist_ok=True)
    for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        if os.environ.get(name) != "1":
            raise InvalidCheckpoint("set every numeric thread environment variable to1 before invoking Python")
    os.environ.update(MPLCONFIGDIR=str(args.output / "cache" / "matplotlib"),
                      NUMBA_CACHE_DIR=str(args.output / "cache" / "numba"),
                      XDG_CACHE_HOME=str(args.output / "cache" / "xdg"),
                      PYTHONPYCACHEPREFIX=str(args.output / "cache" / "environment_python"),
                      PYTENSOR_FLAGS=f"compiledir={args.output / 'cache' / 'pytensor'}")
    sys.pycache_prefix = str(args.output / "cache" / "controller_python")
    manifest, rows, binding = verify_bindings(args)
    with Claim(args.output / "launcher.claim.json", canonical_hash(binding), recover_stale=args.recover_stale_claims):
        return run_verified(args, manifest, rows, binding)


def make_adapter(candidate: Any, args: argparse.Namespace, inputs: Any) -> Any:
    """Select explicit rebuild or verified-state restoration without changing draws."""
    keywords = {"gene_budget": inputs.witness["gene_budget"], "python": args.python}
    training = inputs.training
    if args.restore_processor_state:
        sources = inputs.witness["source_values"]["ordered_source_columns"]
        training = inputs.training[sources]
        keywords["processor_metadata"] = inputs.processor.metadata()
    return candidate.IsolatedOriginalAdapter(args.source, training, inputs.feature_spec, inputs.time, inputs.event, **keywords)


def run_verified(args: argparse.Namespace, manifest: dict[str, Any], rows: list[dict[str, Any]], binding: dict[str, Any]) -> int:
    """Keep the launcher claim across environment checks and cohort construction."""
    environment = subprocess.run([str(args.python), "-B", str(args.source / "scripts/verify_environment.py"),  # noqa: S603 - explicit same interpreter and byte-verified source
                                  "--lock-file", str(args.source / "conda-lock.yml"),
                                  "--hash-file", str(args.source / "conda-lock.yml.sha256")],
                                 capture_output=True, text=True, check=True, env=os.environ.copy())
    environment_report = json.loads(environment.stdout)
    if environment_report["status"] != "ok" or environment_report["lock_sha256"] != manifest["input_sha256"]["conda-lock.yml"] or environment_report["package_count"] != 259:
        raise InvalidCheckpoint("exact lock verification failed")
    binding.update(environment_verification=environment_report, explicit_python=str(args.python),
                   environment_verifier_sha256=sha256_file(args.source / "scripts/verify_environment.py"))
    sealed_binding = seal(binding)
    binding_path = args.output / "manifest.json"
    if binding_path.exists():
        if read_sealed(binding_path) != sealed_binding:
            raise InvalidCheckpoint("preflight resume source/input/method/environment request changed")
    else:
        if any(args.output.iterdir()):
            permitted = {"cache", "launcher.claim.json", "abandoned_claims"}
            if {path.name for path in args.output.iterdir()} - permitted:
                raise InvalidCheckpoint("output contains unbound evidence; choose a new directory")
        write_json_new(binding_path, sealed_binding)
    candidate = load_candidate(args.candidate_module, args.candidate_sha256)
    backend = FrozenBackend(args, manifest)

    def adapter_factory(inputs: Any) -> Any:
        return make_adapter(candidate, args, inputs)

    engine = PreflightEngine(args.output, sealed_binding["content_sha256"], candidate, backend, adapter_factory,
                             cap=args.cap, recover_stale=args.recover_stale_claims)
    result = engine.execute(rows, backend.jobs, backend.cohorts, limit=args.limit)
    print(json.dumps({"status": result["status"], "accounted_contexts": result["accounted_contexts"],
                      "outcomes": result["outcome_counts"], "fit_reuse_certified": False}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
