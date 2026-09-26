# Codebase audit — 2026-09-27

Findings that drive the refactor, completion and reproduction programme in
`coordination/HANDOFF.md`. File references are to commit `2e55c0b`.

## Frozen scope

`config/protocol_freeze.json` records SHA-256 hashes for 80 inputs.
`relevant_input_files` (`src/pipelines/confirmatory.py:1262`) builds the list
from fixed paths plus every `src/**/*.py`. The list includes the `Makefile`,
`coordination/DECISIONS.md`, `docs/study_protocol.md`,
`docs/claim_evidence_register.md` and `data/manifest.yaml`.

`verify_run_inputs_unchanged` (line 1336) fails when a listed file changes or
is missing, or when a new file appears under `src/`. It is called by:

- `scripts/run_robustness.py --mode robustness`, through
  `robustness_input_files` (`src/pipelines/robustness.py:1824`);
- `scripts/run_confirmatory.py --resume`;
- `scripts/restore_confirmatory_release.py` (lines 177–191).

Not frozen: the pilot scripts, `tests/`, `reports/tables`, `reports/figures`,
`reports/*.md`, `data/processed`, `data/external`,
`config/{base,model,training,logging}.yaml`, `INVARIANTS.md`, `README.md`,
`AGENTS.md`, `docs/architecture.md`, and the other coordination files.

## Module classification

| Class | Modules and scripts |
|---|---|
| Confirmatory | `scripts/{run_confirmatory,run_robustness,run_confirmatory_explainability,render_confirmatory,freeze_protocol,verify_environment,restore_confirmatory_release,download_datasets}.py`; `src/pipelines/{confirmatory,robustness}.py`; `src/explainability/{frozen_cells,posterior_analysis,shap_analysis}.py`; `src/data/{fold_preprocessing,survival_folds}.py`; `src/evaluation/{metrics,calibration}.py`; `src/models/{base,cox,random_survival_forest,deepsurv}.py`; `src/models/bayesian/{model,diagnostics}.py`; `src/statistics/{hypothesis_tests,repeated_cv}.py`; `src/utils/reproducibility.py` |
| Pilot only | `scripts/{prepare_dataset,run_eda,run_benchmark,run_explainability,make_figures,make_reports}.py`; `src/data/{preprocessing,feature_engineering,loader,split,validators,eda}.py`; `src/visualization/` |
| Tests only | `src/datasets/`; `src/evaluation/{cross_validation,ranking}.py`; `src/losses/` (stubs) |
| Imported by a package `__init__` but never called | `src/pipelines/{evaluation,inference,preprocessing,training}_pipeline.py` (stubs returning `None`); `src/statistics/{bootstrap,permutation,confidence_intervals}.py`; `src/models/bayesian/likelihood.py` |
| Unused | `src/utils/{config,constants,helpers,logger,seed}.py`; `config/{base,training,logging}.yaml`; `config/model.yaml` (pilot only) |

Some functions in confirmatory modules are used only by pilot code:
`evaluate_model`, `evaluation_times` and `evaluate_survival_model` in
`src/evaluation/metrics.py`, and `posterior_importance`, `compare_rankings`
and `shap_importance` in `src/explainability/`.

## Tests that depend on pilot code

- `tests/test_data.py`: 25 of its 43 tests use pilot modules or
  `data/processed`. Its module-level pilot imports mean the whole file fails
  if pilot code is removed.
- `tests/test_models.py`: 16 of 17 tests read the pilot `data/processed`
  splits. These tests carry INV-003 and INV-005.
- `tests/test_pipeline.py`: carries INV-006 and exercises pilot and test-only
  modules.
- INV-002 is pilot-only, and its text names `log_pnodes` while the test
  checks `pnodes` (`tests/test_data.py:39`). INV-007 refers to the pilot
  `reports/tables/*.json`.

## Pilot references outside the code

The thesis quotes no pilot numbers apart from the historical METABRIC pilot
counts (`methodology.tex:166-169`: 1,903 records, 1,103 deaths). That
statement is backed by `data/external/METABRIC_RNA_Mutation.csv` and
`test_pilot_metabric_provenance`. `appendix_reproducibility.tex:172` lists
`scripts/prepare_dataset.py` as a verification step, which is needed only
because the tests read `data/processed`.

Frozen documents cite pilot artefacts as history: `study_protocol.md:9-11`,
claims C-004, C-005, C-012 and C-017 in `claim_evidence_register.md`, and
ADR-014 and ADR-016.

## Documentation mismatches

- `AGENTS.md:37` says `make all` runs explainability and figures. It runs
  data, eda, benchmark and reports.
- `make benchmark`, `make reports` and `make all` overwrite tracked pilot
  artefacts, and `make_reports` stamps the current date.
- seaborn is pinned but not imported. `src/statistics/bootstrap.py` is in the
  freeze list but not called by any pipeline.

## External notebook

`local_codes/Bayesian/Bayesian_Ravi Ramchandani.ipynb`, dated 2026-09-26: 110
code cells, about 59,000 source lines, no text cells.

- Cells 3–33 read `gbsg2.csv`, `whas500.csv` and `metabric.csv`, which are
  identical to the synthetic files from `e824c1b`.
- Cells 34–108 acquire the real cohorts (cBioPortal METABRIC; scikit-survival
  GBSG2 and WHAS500).
- Evaluation scope is `held_out_first_outer_fold` only.
- Cell 91 stops with a registry-integrity failure. The later cells then
  report `protocol_compliance: True` over 7 of 18 pairs, using metric values
  labelled `*_existing`.
- The cell that runs the confirmatory NUTS sampling was never executed.
- Its seven C-index values fall inside the frozen run's per-fold ranges.

## Confirmatory pipeline map

- Entry point: `scripts/run_confirmatory.py` calls `execute_confirmatory_run`
  (`src/pipelines/confirmatory.py:1361`). For each dataset, fold and model,
  it runs `run_cell` (line 681), writes the cell JSON, then aggregates
  (`_aggregate_tables`), runs inference (`_repeated_cv_inference`) and writes
  the completion record.
- Every top-level symbol in `confirmatory.py` is used; there is no dead code
  there. `robustness.py:37-49` imports 12 names from it, including the
  private `_fit_with_diagnostic_rule`, `_ibs_times` and `_feature_spec`.
  These must keep working after a split.
- A test monkeypatches `confirmatory._model_from_parameters` and
  `_posterior_trace_snapshot` on the module object.
- Untested: `run_cell`, `execute_confirmatory_run`, `tune_candidate`,
  `_evaluate_predictions`, `_model_details`, `_aggregate_tables`,
  `_load_cells`, `load_analysis_dataset`, `_feature_spec`, `_ibs_times`,
  `deterministic_seed`, `_json_safe` and `_atomic_json`.
- Determinism: rerunning seven stored cells in memory reproduced every field
  except `total_seconds`, `fit_seconds` and `cell_content_sha256`. The cells
  were Cox, RSF, DeepSurv, normal and spike-and-slab on GBSG2 r1f1, a
  WHAS500 horseshoe cell, and a failed GBSG2 horseshoe cell. The cell hash
  covers the timings, so cell files can never match byte-for-byte. Compare
  them with the timing fields and the hash removed.
- Largest functions:
  - `_repeated_cv_inference`: 238 lines, nesting depth 6;
  - `execute_confirmatory_run`: 155 lines;
  - `BayesianCoxModel.fit`: 201 lines;
  - `run_cell`: 128 lines;
  - `freeze_protocol.main`: 204 lines.
- Duplicated helpers:
  - the event-stratified resampler, three times (proved RNG-equivalent);
  - `_json_safe` and `_atomic_json`, in robustness and frozen_cells;
  - live-hash maps, built three ways.
- Dead code:
  - `KaplanMeierSurvivalEstimator`;
  - `BayesianCoxModel.get_mcmc_diagnostics`;
  - `CoxPartialLikelihood`;
  - the four stub pipelines (`EvaluationPipeline.run` returns a fixed
    `c_index` of 0.75).
- Inaccurate names and docstrings:
  - `CoxPHModel.predict_risk` says "linear predictor" but returns exp(xβ).
  - `predictions.risk` uses a different scale per model: Cox exp(lp), RSF
    cumulative hazard, DeepSurv log-risk, Bayesian lp.
  - `BayesianCoxModel` is a piecewise-exponential Poisson model.
- Config keys that are never read: `inference.{primary_metric,
  key_secondary_metrics, primary_models, multiplicity, repeated_cv_interval,
  sensitivity_interval}` and `failed_fit_rule.second_refit`. The
  non-centred remedy is hardcoded as `attempt >= 2`.
- `run_confirmatory.py` records package versions but does not verify the
  environment.

## Horseshoe failures

Evidence files: `~/bayes-cox-runs/horseshoe-investigation-20260927/`
(`attempts.csv`, `cells.csv`, `repro.py`, `results/`).

- Every horseshoe attempt used 4 sequential chains, 2,000 draws and
  `jitter+adapt_diag`. The attempts ran at 0.99/2,000 tune, then 0.99/4,000,
  then 0.99/4,000 with a non-centred baseline. The first remedy therefore
  changed nothing for the horseshoe, which already used target acceptance
  0.99. The second remedy re-parameterises only the baseline hazard.
- All 83 failing attempts failed on divergences alone: 1–11 per 8,000 draws
  in GBSG2 and 1–2 in METABRIC. R-hat (1.00), bulk ESS (≥1,528), BFMI (≥0.72)
  and tree depth (no limit hits) passed with wide margins.

  | Cohort | Failed cells | Zero-divergence rate per attempt | Mean divergences per attempt |
  |---|---:|---:|---:|
  | GBSG2 | 18/25 | 0.10 | 2.53 |
  | METABRIC | 2/25 | 0.58 | 0.52 |
  | WHAS500 | 0/25 | 0.83 | 0.17 |

- There is no implementation error. The prior matches Piironen and Vehtari
  (2017, doi:10.1214/17-EJS1337SI) Appendix C.1, apart from two documented
  choices:
  - half-t(2) local scales, which that paper calls hierarchical shrinkage;
  - a fixed τ0 = 0.1, instead of the Eq. 3.12 rule (about 0.04 for GBSG2).
- GBSG2 differs from the other cohorts in the heavy right skew of its
  standardised covariates (progrec up to 10.4 SD, pnodes 8.0), not in its
  events per coefficient.
- Reproduction check: the frozen specification reproduces the archived
  divergence count exactly. On the frozen seeds, target acceptance 0.999
  cleared 6 of 7 failed GBSG2 cells (the remaining one: 11 to 2 divergences).
  Runtime rose 1.2–1.3 times. Posterior means moved by at most 0.07
  posterior SD.
- `diagnostics.py:18-23` passes `round_to=None`, which in ArviZ 0.23 still
  rounds R-hat to two decimals. The gate `r_hat >= 1.01` therefore fires
  from a true R-hat of about 1.005, which is stricter than documented. Keep
  this behaviour for the frozen protocol and document it.
