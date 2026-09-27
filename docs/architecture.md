# Architecture

The active study starts with authoritative raw cohorts, creates paired folds,
fits preprocessing on each training fold, and stores a separate result for
each model/fold. Historical pilot artefacts remain evidence of earlier work;
their execution lane is retired under ADR-034.

For a guided first read, see `docs/code_guide.md`.

```text
data/manifest.yaml + data/raw/*.csv
config/datasets.yaml + config/confirmatory.yaml
                    |
       paired survival folds and fold-local preprocessing
                    |
       confirmatory cells and frozen completion inventory
          /                  |                 \
prespecified robustness  frozen-cell explanation  separate post-hoc sampler refits
          \                  |                 /
          pure, hash-verified tables and figures
```

## Entry points and modules

- `scripts/download_datasets.py` retrieves or verifies the pinned cohorts.
  `src/data/cohorts.py` is the shared analysis loader and feature selector.
  `survival_folds.py` defines paired event/time-stratified folds;
  `fold_preprocessing.py` fits all transformations on training subjects.
- `scripts/run_confirmatory.py` delegates to
  `src/pipelines/confirmatory/runner.py`. The package separates run options,
  model fitting/remedies, evaluation, cell construction, posterior snapshots,
  aggregation, paired inference and provenance. Its package initializer keeps
  the original imports available, including those used by robustness.
- The model layer wraps lifelines Cox PH, scikit-survival forest and pycox
  DeepSurv. `src/models/bayesian/model.py` fits a piecewise-exponential
  proportional-hazards model with the expanded Poisson likelihood. It does
  not fit a Cox partial likelihood. `piecewise.py` constructs the same
  subject/interval arrays; `predictive_checks.py` holds prior/posterior checks.
  PyMC variable construction and random-generator ordering remain fixed.
- `src/evaluation/` supplies IPCW metrics and calibration estimators.
  `src/statistics/` supplies corrected paired repeated-CV inference and
  resampling. The event-stratified resampler has one shared implementation;
  original private import aliases remain available.
- `scripts/run_robustness.py` delegates to `src/pipelines/robustness/`.
  It preserves the planned sample-size/censoring, design/feature/missingness
  and proportional-hazards checks, their original folds, seeds and remedy
  rules. The original production workers run the frozen checkpoint outside
  this checkout; refactoring never changes their code.
- `scripts/run_confirmatory_explainability.py` reads stored fitted-cell state
  through `src/explainability/`. Separate modules verify the source run,
  select posterior/background samples, construct grouped explanations,
  assess stability and compute uncertainty. No model is refitted. The
  historical production artefact is preserved byte for byte, including its
  failed convergence gate and historical estimand label.
- `scripts/run_horseshoe_sampler_sensitivity.py` implements ADR-032 in
  `src/pipelines/posthoc_sampler.py`: all 75 horseshoe cells, only target
  acceptance changed to 0.999 on every original attempt. The other 375 cells
  retain their frozen results. Every new cell and aggregate is explicitly
  post-hoc and has its own code/configuration/source manifest.
- `scripts/render_confirmatory.py` delegates to `src/rendering/`: evidence
  verification, deterministic outputs/lineage, metrics, diagnostics,
  supplemental analyses and orchestration. It includes all nine primary
  contrasts, marks four unavailable estimates, and labels the separate
  ADR-033 mathematical bound. `scripts/render_horseshoe_sensitivity.py`
  produces a separate post-hoc bundle. Neither renderer imports a model or
  fits one.

## Evidence and execution identity

`src/utils/reproducibility.py` supplies canonical hashes and environment/run
metadata. `src/utils/io.py` supplies shared JSON/YAML conversion and atomic
writes. Exact dependency identity comes from `conda-lock.yml` and its hash,
not the environment name.

`src/utils/frozen_evidence.py` verifies the original 80 blobs at checkpoint
`44b608572a5e1006a05ed5e3c4985471b2ba594d`, then checks that live protocol,
cohort/manifest and lock inputs retain their frozen bytes. Code and ordinary
documentation can change under ADR-030. Completed confirmatory resume is a
read-only verification; it does not refit, aggregate or rewrite anything.
An unfinished historical confirmatory execution still requires its original
live input identity. The full refit reproduction is a separate verification
output, not a reopened confirmatory analysis.

`scripts/reproduce_confirmatory_cells.py` refits stored cells and compares
every field except wall-clock values and the hash containing those values.
Its resumable checkpoint records actual source-module hashes and original
evidence hashes. A saved refit must pass its own content hash before reuse;
changed code, selection or original evidence requires a separate checkpoint.

`src/utils/posthoc_evidence.py` verifies all 75 sensitivity cells, their
original fold/seed identities, acceptance-only change, nine-contrast family,
completion and inference. Both renderers record code and source hashes and
reject source edits made during a render.

`scripts/complete_results_programme.py` orchestrates the full reproduction,
completed frozen robustness verification, separate sampler sensitivity and
both renderers from sealed code. Its output lock is retained by child stages,
so a crashed coordinator cannot overlap a surviving fit on restart.

`scripts/package_programme_release.py` requires the final visual-QA-backed
`release_ready` seal, verifies all seven evidence inventories against committed
code and creates five deterministic private archives. The original confirmatory
release is referenced unchanged. `scripts/restore_programme_release.py` verifies
the package and its separately restored original run; optional extraction uses
a new directory and rejects unsafe entries, collisions and overwrites.

## Historical artefacts

`data/external/`, `data/processed/`, `reports/tables/benchmark.json`,
`reports/tables/explainability.json`, old reports and figures remain in place.
Retired source is available in Git history. Pilot or rehearsal effects cannot
enter confirmatory findings. A passing test or a completed implementation is
not evidence that a scientific claim passed its prespecified gate.
