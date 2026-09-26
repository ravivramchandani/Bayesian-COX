# Brief: readability refactor without behaviour change

## Role

Implementer. One work package per implementer, in its own git worktree
branch.

## Goal

Make the pipeline code easy for a new master's student to read, with small
modules, clear names and accurate docstrings. Every output the code produces
must stay identical.

## Why

The owner reports that the student cannot follow the current code. The
largest files are:
- `scripts/render_confirmatory.py`: 2,280 lines
- `src/pipelines/robustness.py`: 1,952 lines
- `src/pipelines/confirmatory.py`: 1,515 lines
- `src/explainability/frozen_cells.py`: 1,353 lines

The frozen confirmatory evidence is verified separately, against the
checkpoint commit, so the working-tree code may now change. It must still
reproduce the frozen results exactly.

## Environment

- Python: `/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/python`
- Tests: `$PY -m pytest -q`
- Lint: `$PY -m ruff check .` and `$PY -m ruff format <touched files>`
- The frozen run lives at
  `reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651/` in the
  main checkout. It is not tracked by git, so a worktree must reference it by
  absolute path:
  `/Users/macuser/Documents/Github/bayesian_survival_for_prediction-disease/project/reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651`.
- A robustness production run is using six cores under `~/bayes-cox-runs/`.
  Do not touch it. Use at most two worker processes for any check.

## Behaviour that must not change

- Numerical operations and their order, including reductions and the order
  of array construction.
- Random seeds, and the order in which each random generator is consumed.
- PyMC model variable names, shapes, transforms and the order in which they
  are created.
- Every output file name, JSON key, JSON structure and value, CSV column and
  column order.
- CLI flags and their defaults.
- Exception types that tests check.
- Public import paths. When a module becomes a package, its `__init__.py`
  re-exports every name that other modules, scripts or tests import.
  Robustness imports 12 names from `src.pipelines.confirmatory`, including
  private ones.

Seed helpers `deterministic_seed` (confirmatory) and `_stable_seed`
(explainability) are not interchangeable. They may be renamed or moved, but
never merged.

## Files not to edit

- `config/*.yaml` and `config/protocol_freeze.json`
- `data/`
- `docs/study_protocol.md` and `docs/claim_evidence_register.md`
- `coordination/DECISIONS.md`, `HANDOFF.md`, `TODO.md` and `JOURNAL.md`
  (the coordinator updates these)
- the Overleaf thesis

## Style

- **Module docstring:** one short paragraph saying what the module does and
  where it sits in the pipeline.
- **Public function or class:** a one-line summary, a short plain-language
  explanation of the method when it is not obvious, then `Args:` and
  `Returns:` sections (Google style) for parameters whose meaning is not
  clear from the name and type.
- **Private helper:** a one-line docstring.
- **Accuracy:** every docstring must be true of the code. Check scales and
  units. For example, `predictions.risk` is exp(linear predictor) for Cox,
  cumulative hazard for RSF, log-risk for DeepSurv, and the linear predictor
  for the Bayesian model.
- **Comments** explain why, never what. They matter most where an ordering is
  kept for reproducibility. No banners, decorative rules, process narration
  or references to this refactor.
- **Structure:** aim for functions under about 50 lines and nesting depth
  under 4. Use descriptive names instead of abbreviations (for example
  `evaluation_horizons_and_grid`, not `_ibs_times`), keeping the old name as
  an alias where other code imports it.
- **Spelling:** British English (normalise, artefact), matching the
  repository.
- **Dead code:** delete code only if it is unused in the whole repository
  (search scripts, tests and src). Report every deletion.
- **Shared JSON and YAML I/O:** use `src/utils/io.py` (`json_safe`,
  `write_json_atomic`, `read_mapping`).

## Equivalence gates

Run the gate for your package, and record the command output in your final
report.

| Package | Gate |
|---|---|
| Confirmatory pipeline | `scripts/reproduce_confirmatory_cells.py --selection quick --workers 2` reports 6/6 identical, and also `--selection whas500:cox_ph:1:1,whas500:bayesian_normal:1:1,metabric:deepsurv:1:1,metabric:random_survival_forest:1:1`. Rebuilding `fold_metrics.csv`, `out_of_fold_predictions.csv.gz` and `inference.json` from the 450 stored cells with the new aggregation and inference code gives byte-identical files. |
| Models, evaluation, statistics | The same quick selection is 6/6 identical, and the full test suite passes. |
| Explanation | Running `scripts/run_confirmatory_explainability.py` on the frozen run gives SHA-256 `120984c7edfac468f471b9f500470623689b2647e4bde56d271cc9623346ecd5`. |
| Rendering | Render with the old and the new code into two scratch directories and compare every file. Report each file that differs, and why the difference is intended. |
| Robustness | `~/bayes-cox-runs/harness/check_robustness_cell.py`, adapted to the new import paths, reproduces three stored production cells exactly. |

Every package must also pass the full test suite and `ruff check .`.

## Report

Keep the report under 600 words. Include:
- the new module layout, with line counts;
- deleted code;
- renamed public names and their aliases;
- gate results;
- anything that looked wrong but was left unchanged because it affects
  results (describe it; do not fix it).

Commit on your branch with a plain descriptive message and no co-author
trailer.
