"""Run result-blind rehearsal or frozen robustness analyses.

This is the entry point for the prespecified robustness plan, which refits the
three Bayesian Cox priors on the frozen confirmatory folds under controlled
perturbations. The work is done by
``src.pipelines.robustness.execute_robustness_run``. There are four
components:

- ``rq2``: the information-regime analysis for research question 2 (RQ2):
  25/50/75/100 per cent training subsets and two training-derived
  administrative censoring cut-offs, not crossed with each other (ADR-023);
- ``design``: prior-scale scenarios and alternative numbers of
  baseline-hazard intervals, one factor at a time;
- ``feature``: the primary and every sensitivity feature set declared in
  ``config/datasets.yaml``, plus multiple imputation for the METABRIC
  ``npi_plus_stage`` set;
- ``ph``: an aggregate of the proportional-hazards (PH) tests already stored
  in the confirmatory Cox cells. It fits nothing and needs the confirmatory
  run.

Modes:
    ``rehearsal`` (the default) is a small result-blind workload (one outer
    fold per cohort, 300 draws, 300 tuning steps, two chains, 30 bootstraps)
    whose output is not evidence. ``robustness`` uses the frozen settings,
    refuses any analysis override flag and requires ``design_status`` to be
    ``frozen_after_rehearsal``.

Reads:
    ``config/confirmatory.yaml``, ``config/datasets.yaml``, the raw cohorts and
    the completed confirmatory run. When ``--confirmatory-run`` is omitted the
    script uses the only ``confirmatory_v1_confirmatory_*`` run with a
    ``completion.json`` under ``reports/confirmatory/``; with none or several,
    no run is supplied and the PH component records itself as unavailable.

Writes:
    A run directory ``<output-root>/<analysis_id>_robustness_<mode>_<hash>/``
    with ``manifest.json``, one JSON file per cell under ``cells/``,
    ``paired_ibs_inference.json``, ``analysis_availability.json``,
    ``feasibility_plan.json``, ``ph_assessment.json`` when the PH component is
    selected, and ``completion.json``. The path is printed as
    ``run_artifact=<path relative to the repository>``.

``--resume`` continues an unfinished run from the same code and settings, or
verifies a completed one without refitting.

Make targets: ``robustness`` and ``robustness-resume`` (both need
``CONFIRMATORY_RUN``).

Example:
    python scripts/run_robustness.py --mode robustness --confirmatory-run reports/confirmatory/<run>
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipelines.robustness import RobustnessOptions, execute_robustness_run

COMPONENTS = ("rq2", "design", "feature", "ph")


def _yaml(path: Path) -> dict:
    """Return a YAML file's top-level mapping, rejecting any other content."""
    with path.open(encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return value


def _discover_confirmatory_run() -> Path | None:
    """Return the single completed confirmatory run, or ``None`` if not exactly one exists."""
    candidates = sorted(
        path.parent
        for path in (PROJECT_ROOT / "reports" / "confirmatory").glob(
            "confirmatory_v1_confirmatory_*/completion.json"
        )
    )
    if len(candidates) == 1:
        return candidates[0]
    return None


def parse_args() -> argparse.Namespace:
    """Parse the command line.

    Analysis flags default to ``None`` so that robustness mode can reject any
    supplied override.

    Returns:
        Parsed command-line option namespace.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Checkpointed Bayesian sensitivity analyses using the frozen "
            "confirmatory folds. Rehearsal output is not evidence."
        )
    )
    parser.add_argument("--mode", choices=("rehearsal", "robustness"), default="rehearsal")
    parser.add_argument("--datasets", nargs="+", default=None)
    parser.add_argument("--components", nargs="+", choices=COMPONENTS, default=None)
    parser.add_argument("--outer-splits", type=int, default=None)
    parser.add_argument("--outer-repeats", type=int, default=None)
    parser.add_argument("--fold-limit-per-dataset", type=int, default=None)
    parser.add_argument("--bayes-draws", type=int, default=None)
    parser.add_argument("--bayes-tune", type=int, default=None)
    parser.add_argument("--bayes-chains", type=int, default=None)
    parser.add_argument("--sensitivity-bootstraps", type=int, default=None)
    parser.add_argument("--confirmatory-run", type=Path, default=None)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "reports" / "robustness",
    )
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Build the run options, execute the run and print its directory.

    Returns:
        Exit status 0 on success.

    Raises:
        ValueError: If robustness mode receives an analysis override, a cohort
            is unknown, or the resolved settings have fewer than 20 bootstraps,
            fewer than three outer folds or no repeat.
        RuntimeError: If robustness mode is requested before the protocol is
            frozen.
    """
    args = parse_args()
    config = _yaml(PROJECT_ROOT / "config" / "confirmatory.yaml")
    datasets = _yaml(PROJECT_ROOT / "config" / "datasets.yaml")
    validation = config["validation"]
    bayesian = config["models"]["bayesian_cox"]

    if args.mode == "robustness":
        forbidden = {
            "--datasets": args.datasets,
            "--components": args.components,
            "--outer-splits": args.outer_splits,
            "--outer-repeats": args.outer_repeats,
            "--fold-limit-per-dataset": args.fold_limit_per_dataset,
            "--bayes-draws": args.bayes_draws,
            "--bayes-tune": args.bayes_tune,
            "--bayes-chains": args.bayes_chains,
            "--sensitivity-bootstraps": args.sensitivity_bootstraps,
        }
        supplied = [flag for flag, value in forbidden.items() if value is not None]
        if supplied:
            raise ValueError(
                "robustness mode forbids analysis overrides; supplied " + ", ".join(supplied)
            )
        if config["design_status"] != "frozen_after_rehearsal":
            raise RuntimeError("robustness mode is locked until the result-blind protocol freeze")

    rehearsal = args.mode == "rehearsal"
    options = RobustnessOptions(
        mode=args.mode,
        datasets=tuple(args.datasets or config["datasets"]),
        components=tuple(args.components or COMPONENTS),
        outer_splits=int(args.outer_splits or validation["outer_splits"]),
        outer_repeats=int(args.outer_repeats or (1 if rehearsal else validation["outer_repeats"])),
        fold_limit_per_dataset=(
            args.fold_limit_per_dataset
            if args.fold_limit_per_dataset is not None
            else (1 if rehearsal else None)
        ),
        bayes_draws=int(args.bayes_draws or (300 if rehearsal else bayesian["draws"])),
        bayes_tune=int(args.bayes_tune or (300 if rehearsal else bayesian["tune"])),
        bayes_chains=int(args.bayes_chains or (2 if rehearsal else bayesian["chains"])),
        sensitivity_bootstraps=int(args.sensitivity_bootstraps or (30 if rehearsal else 2000)),
        resume=bool(args.resume),
        output_root=args.output_root.resolve(),
        confirmatory_run_dir=(
            args.confirmatory_run.resolve()
            if args.confirmatory_run is not None
            else _discover_confirmatory_run()
        ),
    )
    if options.sensitivity_bootstraps < 20:
        raise ValueError("sensitivity bootstrap count must be at least 20")
    if options.outer_splits < 3 or options.outer_repeats < 1:
        raise ValueError("outer validation requires at least 3 folds and 1 repeat")
    unknown_datasets = sorted(set(options.datasets) - set(datasets))
    if unknown_datasets:
        raise ValueError(f"unknown datasets: {unknown_datasets}")

    run_dir = execute_robustness_run(PROJECT_ROOT, config, datasets, options)
    print(f"run_artifact={os.path.relpath(run_dir, PROJECT_ROOT)}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
