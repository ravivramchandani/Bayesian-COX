# Architecture

```
config/         dataset schemas and model hyperparameters
coordination/   decisions, invariants, glossary, protocol, task list
data/
  external/     source files not produced by this repository
  raw/          exported cohorts, one CSV per dataset
  processed/    train/val/test splits, CV folds, preprocessing metadata
scripts/        entry points, one per stage
src/
  data/         loading, validation, feature engineering, preprocessing, EDA
  datasets/     per-cohort schema definitions
  models/       Cox PH, random survival forest, DeepSurv
    bayesian/   Bayesian Cox model and convergence diagnostics
  evaluation/   metrics, calibration, cross-validation, ranking
  explainability/ posterior signals and SHAP attribution
  statistics/   bootstrap, hypothesis tests, confidence intervals
  visualization/ EDA plots and thesis figures
  losses/       Cox partial likelihood for the neural model
  utils/        configuration loading and seeding
tests/          test suite
reports/
  tables/       result files written by the scripts
  figures/      generated figures
```

## Stage responsibilities

**`scripts/download_datasets.py`** exports GBSG2 and WHAS500 from
scikit-survival and derives the METABRIC clinical cohort from
`data/external/`. A missing source raises; no code path generates data.

**`scripts/prepare_dataset.py`** reads schemas from `config/datasets.yaml`,
then imputes, encodes, scales, splits, and writes CV folds. Transformers are
fitted on the training split only.

**`scripts/run_benchmark.py`** fits every model on every cohort and writes
`reports/tables/benchmark.json`.

**`scripts/run_explainability.py`** compares the Bayesian posterior signal
against SHAP attributions on the baselines, writing
`reports/tables/explainability.json`.

**`scripts/make_figures.py`** and **`scripts/make_reports.py`** render
figures and markdown from those result files. Neither recomputes anything.

## Model layer

Cox PH wraps lifelines and the random survival forest wraps scikit-survival,
so the baselines match published implementations. The Bayesian Cox model is
implemented directly in PyMC as a piecewise-exponential baseline hazard
expressed as Poisson regression over subject-interval exposures, and is the
project's own contribution.
