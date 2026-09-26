# Architecture

The repository has two separate evidence lanes. The current confirmatory lane
is content-addressed, fold-local and checkpointed. The legacy lane is retained
only for the inspected pilot artefacts and cannot supply confirmatory evidence.

## Current confirmatory lane

```text
data/manifest.yaml + data/raw/*.csv
              |
config/datasets.yaml + config/confirmatory.yaml
              |
      result-blind rehearsal
              |
config/protocol_freeze.json
              |
src/pipelines/confirmatory.py
              |
reports/confirmatory/<run>/
          /                 \
robustness pipeline        frozen-cell explanation
          \                 /
       pure confirmatory renderer
              |
reports/rendered/<run>/
```

- `scripts/download_datasets.py` retrieves or derives the authoritative
  cohorts. `data/manifest.yaml` records upstream and derived hashes, and
  `data/raw/` contains the exact CSVs consumed by confirmatory analysis.
- `src/data/fold_preprocessing.py` and `src/data/survival_folds.py` create
  paired event/time-stratified folds and fit every transformation inside its
  analysis-training fold. Production does not consume pilot processed splits.
- `scripts/run_confirmatory.py` delegates to
  `src/pipelines/confirmatory.py`. Rehearsal output is `rehearsal_only`.
  Confirmatory mode refuses overrides, requires `frozen_after_rehearsal`,
  verifies the content-addressed freeze, and stores immutable cells and
  out-of-fold predictions.
- The comparator layer wraps lifelines Cox PH, scikit-survival forest and
  pinned pycox DeepSurv. `src/models/bayesian/model.py` implements the full
  subject-interval Poisson likelihood for a Bayesian piecewise-exponential
  proportional-hazards model; it is not a Cox partial-likelihood model.
- `scripts/run_robustness.py` and `src/pipelines/robustness.py` reuse frozen
  fold identities for prespecified RQ2, design, feature/missingness and
  proportional-hazards checks. They introduce no time interactions.
- `scripts/run_confirmatory_explainability.py` reads immutable fitted-cell
  state. It compares full-posterior grouped Bayesian contribution with exact
  linear SHAP for the same Bayesian score, with frozen Cox secondary.
  Confirmatory forest SHAP and DeepSurv explanation are absent; no model is
  refitted.
- `scripts/render_confirmatory.py` validates hashes and purely renders tables,
  figures, CSV and LaTeX fragments. Rehearsals can produce only labelled
  runtime/diagnostic packages; scientific outputs require production data.

`src/evaluation/` contains survival metrics and calibration estimators.
`src/statistics/` contains paired repeated-CV and bootstrap estimators.
`src/utils/reproducibility.py` supplies hashes, manifests and runtime metadata.
Exact dependency identity comes from `conda-lock.yml` and its SHA-256 file,
not from an environment name.

## Legacy pilot lane

- `scripts/prepare_dataset.py` and `data/processed/` create historical
  train/validation/test inputs. Their exploratory internal CV is not fold-
  local confirmatory evidence.
- `scripts/run_benchmark.py`, `scripts/run_explainability.py`,
  `scripts/make_reports.py` and `scripts/make_figures.py` produce inspected
  pilot results, Kernel-SHAP comparisons and figures. The figure script may
  refit and is exposed only through `pilot-figures`.
- `reports/tables/benchmark.json`, `reports/tables/explainability.json`, the
  top-level pilot reports and existing `reports/figures/` are hypothesis-
  generating artefacts only.

No pilot or rehearsal metric may enter confirmatory results, the abstract or
conclusions. A current pipeline or passing test establishes implementation
readiness, not a scientific result.
