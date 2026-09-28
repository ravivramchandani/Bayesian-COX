"""Run the result-blind rehearsal or the frozen confirmatory nested CV.

This is the entry point for the primary analysis: repeated nested
cross-validation (CV) of six survival models on the GBSG2, WHAS500 and
METABRIC cohorts. The work is done by
``src.pipelines.confirmatory.execute_confirmatory_run``; this script only reads
the study configuration, applies the mode's defaults and checks the command
line.

Modes:
    ``rehearsal`` (the default) is a result-blind compute check. It fits one
    outer fold per cohort with 300 draws, 300 tuning steps, two chains and 30
    calibration bootstraps, unless flags override these. Its cells are
    labelled ``rehearsal_only`` and are never confirmatory evidence.

    ``confirmatory`` runs every setting from ``config/confirmatory.yaml``
    (five repeats of five outer folds). It refuses any analysis override flag
    and refuses to start unless ``design_status`` is
    ``frozen_after_rehearsal``. The runner then checks every input against
    ``config/protocol_freeze.json`` before fitting.

Reads:
    ``config/confirmatory.yaml``, ``config/datasets.yaml`` and the raw cohort
    files in ``data/raw/``.

Writes:
    A run directory ``<output-root>/<analysis_id>_<mode>_<hash>/``, where the
    12-character hash is taken from the resolved run settings. It holds
    ``manifest.json``, one JSON file per (cohort, repeat, fold, model) cell
    under ``cells/``, ``fold_metrics.csv``, ``out_of_fold_predictions.csv.gz``,
    ``inference.json`` and ``completion.json``. The path is printed as
    ``run_artifact=<path relative to the repository>``.

``--resume`` continues an unfinished run with the same settings and inputs,
skipping cells whose files already exist. For a completed confirmatory run it only
verifies the stored evidence and rewrites nothing. Without ``--resume`` an
existing run directory is an error.

Make targets: ``confirmatory-rehearsal``, ``confirmatory`` and
``confirmatory-resume``.

Example:
    python scripts/run_confirmatory.py --mode rehearsal --datasets gbsg2
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

from src.pipelines.confirmatory import MODEL_KEYS, RunOptions, execute_confirmatory_run


def _yaml(path: Path):
    """Return the parsed contents of a YAML file."""
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def parse_args() -> argparse.Namespace:
    """Parse the command line.

    Every analysis flag defaults to ``None`` so that ``main`` can tell a
    supplied override from an omitted one; confirmatory mode rejects any
    supplied override.

    Returns:
        Parsed command-line option namespace.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Checkpointed repeated nested-CV analysis. Rehearsal outputs are "
            "never confirmatory evidence."
        )
    )
    parser.add_argument(
        "--mode", choices=("rehearsal", "confirmatory"), default="rehearsal"
    )
    parser.add_argument("--datasets", nargs="+", default=None)
    parser.add_argument("--models", nargs="+", choices=MODEL_KEYS, default=None)
    parser.add_argument("--outer-splits", type=int, default=None)
    parser.add_argument("--outer-repeats", type=int, default=None)
    parser.add_argument("--fold-limit-per-dataset", type=int, default=None)
    parser.add_argument("--bayes-draws", type=int, default=None)
    parser.add_argument("--bayes-tune", type=int, default=None)
    parser.add_argument("--bayes-chains", type=int, default=None)
    parser.add_argument("--calibration-bootstraps", type=int, default=None)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=PROJECT_ROOT / "reports" / "confirmatory",
    )
    parser.add_argument("--resume", action="store_true")
    return parser.parse_args()


def main() -> int:
    """Build the run options, execute the run and print its directory.

    Returns:
        Exit status 0 on success.

    Raises:
        ValueError: If confirmatory mode receives an analysis override, or if
            the resolved settings have fewer than 20 calibration bootstraps,
            fewer than three outer folds or no repeat.
        RuntimeError: If confirmatory mode is requested before the protocol
            is frozen.
    """
    args = parse_args()
    config = _yaml(PROJECT_ROOT / "config" / "confirmatory.yaml")
    datasets = _yaml(PROJECT_ROOT / "config" / "datasets.yaml")
    validation = config["validation"]
    bayesian = config["models"]["bayesian_cox"]
    evaluation = config["evaluation"]

    if args.mode == "confirmatory":
        forbidden = {
            "--datasets": args.datasets,
            "--models": args.models,
            "--outer-splits": args.outer_splits,
            "--outer-repeats": args.outer_repeats,
            "--fold-limit-per-dataset": args.fold_limit_per_dataset,
            "--bayes-draws": args.bayes_draws,
            "--bayes-tune": args.bayes_tune,
            "--bayes-chains": args.bayes_chains,
            "--calibration-bootstraps": args.calibration_bootstraps,
        }
        supplied = [flag for flag, value in forbidden.items() if value is not None]
        if supplied:
            raise ValueError(
                "confirmatory mode forbids analysis overrides; supplied "
                + ", ".join(supplied)
            )
        if config["design_status"] != "frozen_after_rehearsal":
            raise RuntimeError(
                "confirmatory mode is locked until the result-blind rehearsal "
                "sets design_status to frozen_after_rehearsal"
            )

    # Rehearsal defaults are a small, fixed workload for timing the pipeline;
    # confirmatory defaults are the frozen protocol settings.
    default_rehearsal_limit = 1 if args.mode == "rehearsal" else None
    default_rehearsal_repeats = 1 if args.mode == "rehearsal" else int(
        validation["outer_repeats"]
    )
    default_draws = 300 if args.mode == "rehearsal" else int(bayesian["draws"])
    default_tune = 300 if args.mode == "rehearsal" else int(bayesian["tune"])
    default_chains = 2 if args.mode == "rehearsal" else int(bayesian["chains"])
    default_bootstraps = 30 if args.mode == "rehearsal" else int(
        evaluation["calibration_bootstraps"]
    )

    options = RunOptions(
        mode=args.mode,
        datasets=tuple(args.datasets or config["datasets"]),
        models=tuple(args.models or MODEL_KEYS),
        outer_splits=int(args.outer_splits or validation["outer_splits"]),
        outer_repeats=int(args.outer_repeats or default_rehearsal_repeats),
        fold_limit_per_dataset=(
            args.fold_limit_per_dataset
            if args.fold_limit_per_dataset is not None
            else default_rehearsal_limit
        ),
        bayes_draws=int(args.bayes_draws or default_draws),
        bayes_tune=int(args.bayes_tune or default_tune),
        bayes_chains=int(args.bayes_chains or default_chains),
        calibration_bootstraps=int(
            args.calibration_bootstraps or default_bootstraps
        ),
        resume=bool(args.resume),
        output_root=args.output_root.resolve(),
    )
    if options.calibration_bootstraps < 20:
        raise ValueError("calibration bootstraps must be at least 20")
    if options.outer_splits < 3 or options.outer_repeats < 1:
        raise ValueError("outer validation requires at least 3 folds and 1 repeat")

    run_dir = execute_confirmatory_run(PROJECT_ROOT, config, datasets, options)
    relative = os.path.relpath(run_dir, PROJECT_ROOT)
    print(f"run_artifact={relative}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
