# Reading guide to the code

A guided tour for a new reader. `docs/architecture.md` gives the complete
module map. `docs/study_protocol.md` is the analysis plan. Formal terms are
defined in `coordination/GLOSSARY.md`.

## The study in one paragraph

Three real cohorts are analysed: GBSG2 (breast cancer), WHAS500 (heart
attack) and METABRIC (breast cancer). Each is split into five folds, five
times over, giving 25 training/validation pairs per cohort. On every pair,
six models are fitted:

- Cox proportional hazards;
- a random survival forest (RSF);
- DeepSurv;
- a Bayesian proportional-hazards model under three coefficient priors
  (normal, regularised horseshoe and spike-and-slab).

Each fitted model is scored on the validation fold. One cohort × fold ×
model result is a **cell**, stored as a JSON file. The cells are then pooled
to compare the models, with statistics that account for the folds sharing
patients.

## The life of one cell

Follow these steps in order. They are the core of the code.

1. **Entry point.** `scripts/run_confirmatory.py` reads the configuration and
   calls `execute_confirmatory_run` in
   `src/pipelines/confirmatory/runner.py`.
2. **Load the cohort.** `load_analysis_dataset` and `select_feature_spec` in
   `src/data/cohorts.py` return the raw table, follow-up times, event
   indicators, subject IDs and the predictors to use.
3. **Make the folds.** `repeated_survival_folds` in
   `src/data/survival_folds.py` builds the 5 × 5 folds. The folds are
   stratified by event status and follow-up time, and seeded so that every
   model sees exactly the same patients in each fold.
4. **Fit the cell.** `run_cell` in `src/pipelines/confirmatory/cells.py`
   does the work for one fold and one model:
   - `FoldFeaturePreprocessor` (`src/data/fold_preprocessing.py`) learns
     imputation values, category levels and scaling from the **training
     rows only**, then applies them to the validation rows. Nothing about the
     validation patients leaks into the model.
   - `tune_candidate` (`src/pipelines/confirmatory/fitting.py`) picks the RSF
     and DeepSurv hyperparameters by inner three-fold cross-validation inside
     the training fold. Cox and the Bayesian models have nothing to tune.
   - The final model is fitted. A Bayesian fit must pass the convergence
     gate; if it fails, it is refitted at most twice (see "Where each idea
     lives" below).
   - `evaluate_predictions` (`src/pipelines/confirmatory/evaluation.py`)
     scores the validation predictions: integrated Brier score, Uno and
     Harrell concordance, time-dependent AUC and calibration.
5. **Store the cell.** The cell is written as JSON with a content hash, so
   any later change to the file is detected.
6. **Pool the cells.** `aggregation.py` writes `fold_metrics.csv` and
   `out_of_fold_predictions.csv.gz`. `inference.py` compares models fold by
   fold and writes `inference.json`.
7. **Record provenance.** The manifest and completion record list every
   input and output hash. `src/utils/frozen_evidence.py` later checks the
   frozen evidence against the checkpoint commit (ADR-030).

## What reads the stored cells afterwards

| Stage | Entry script | Code | Refits models? |
|---|---|---|---|
| Robustness (RQ2, RQ4) | `scripts/run_robustness.py` | `src/pipelines/robustness/` | Yes, Bayesian models under prespecified perturbations |
| Explanation (RQ3) | `scripts/run_confirmatory_explainability.py` | `src/explainability/` | No; uses stored coefficients and posterior summaries |
| Horseshoe sampler sensitivity (ADR-032) | `scripts/run_horseshoe_sampler_sensitivity.py` | `src/pipelines/posthoc_sampler.py` | Yes; the 75 horseshoe cells, post-hoc |
| Tables and figures | `scripts/render_confirmatory.py` | `src/rendering/` | No; pure renderer that checks every source hash |

## Suggested reading order

1. `src/data/cohorts.py`, `survival_folds.py` and `fold_preprocessing.py`:
   what goes into a model.
2. `src/models/cox.py`, then `src/models/bayesian/model.py`, `piecewise.py`
   and `diagnostics.py`: the models and the Bayesian quality gate.
3. `src/evaluation/metrics.py` and `calibration.py`: how predictions are
   scored.
4. `src/pipelines/confirmatory/cells.py`, `fitting.py` and `evaluation.py`:
   one cell from start to finish.
5. `src/statistics/repeated_cv.py`, `hypothesis_tests.py` and
   `src/pipelines/confirmatory/inference.py`: how models are compared.
6. `src/rendering/`: how the results become thesis tables and figures.
7. `src/explainability/` and `src/pipelines/robustness/`: the RQ3 and RQ2/RQ4
   stages.

## Where each idea lives

| Idea | Where |
|---|---|
| Paired, stratified folds; the repeat seed is 260817 + 1009(r − 1) | `src/data/survival_folds.py` |
| Training-fold-only preprocessing | `src/data/fold_preprocessing.py` |
| Evaluation horizons (25th/50th/75th percentiles of training event times) and the 25-point IBS grid | `evaluation_horizons_and_grid` in `src/pipelines/confirmatory/evaluation.py`; `src/evaluation/metrics.py` |
| Censoring of validation follow-up after the last training horizon, for the IPCW metrics | `administratively_truncate_for_ipcw` in `src/pipelines/confirmatory/evaluation.py` |
| IBS, Uno and Harrell C, AUC | `src/evaluation/metrics.py`, `ranking.py` |
| Calibration (intercept, slope, calibration-in-the-large, curves) | `src/evaluation/calibration.py`, `calibration_model.py` |
| Bayesian likelihood (piecewise-exponential Poisson) and priors | `src/models/bayesian/model.py`, `piecewise.py` |
| Prior and posterior predictive checks | `src/models/bayesian/predictive_checks.py` |
| Convergence gate: zero divergences, R-hat < 1.01, bulk ESS > 400, BFMI ≥ 0.30, no tree-depth hits | `check_convergence` in `src/models/bayesian/diagnostics.py` |
| Refit ladder: target acceptance 0.99 with doubled tuning, then also a non-centred baseline | `src/pipelines/confirmatory/fitting.py` |
| Deterministic seeds for every random step | `deterministic_seed` in `src/pipelines/confirmatory/options.py` |
| Nadeau–Bengio corrected paired comparison | `src/statistics/repeated_cv.py` |
| Holm adjustment; post-hoc bound for the incomplete family (ADR-033) | `holm_adjust` in `src/statistics/hypothesis_tests.py`; `src/rendering/holm_bounds.py` |
| Event-stratified paired bootstrap | `src/statistics/bootstrap.py`, `resampling.py` |
| Content hashes, run manifests, checkpoint verification | `src/utils/reproducibility.py`, `frozen_evidence.py` |
| Exact linear SHAP and explanation stability | `src/explainability/shap_analysis.py`, `stability.py`, `uncertainty.py` |
| Robustness conditions (training fractions, censoring, priors, intervals, features) | `src/pipelines/robustness/conditions.py` |

## Names used throughout

- `times`, `events`: follow-up time in the cohort's own unit (days or
  months) and the event indicator (1 = event, 0 = censored), one entry per
  subject.
- `fold.repeat`, `fold.fold`: the outer repeat (1–5) and fold (1–5).
  `fold.train_indices` and `fold.validation_indices` index the rows of the
  cohort.
- `cell`: the dictionary for one cohort × fold × model result. Its keys
  `metrics`, `predictions` and `model_details` hold the scores, the
  validation predictions and model-specific extras.
- `predictions["risk"]`: a higher value means higher risk, but the scale
  differs by model. The model docstrings in `src/models/` state each one.

## Running things

All commands run in the locked environment described in the README.

```bash
make verify-env                 # confirm the exact locked environment
make test                       # schema checks and the full test suite
make lint                       # Ruff
python scripts/reproduce_confirmatory_cells.py --selection quick
                                # refit six stored cells, check they match
make render-confirmatory CONFIRMATORY_RUN=<run directory>
                                # tables and figures from a verified run
```

The confirmatory run is complete and closed. Rerunning it does not create
new evidence: `make confirmatory-resume` only verifies it. New analyses are
post-hoc and write to their own run directories.
