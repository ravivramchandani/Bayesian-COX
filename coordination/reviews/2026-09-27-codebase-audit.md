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
