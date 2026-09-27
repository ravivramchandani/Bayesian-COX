# INVARIANTS

Contracts the codebase must maintain. Each has one automated verification.
Weakening an invariant requires a superseding record in `DECISIONS.md`.

Format:

```markdown
## INV-NNN — <short title>
- Scope: <file, module, or "project-wide">
- Contract: <what must always be true>
- Verified-by: <command>
- Rationale: <what breaks if violated>
```

---

## INV-001 — No fabricated observations

- Scope: `scripts/download_datasets.py`, `data/`.
- Contract: Every row in `data/raw/` originates from scikit-survival or the
  METABRIC clinical export. No code path generates observations. A missing
  source raises rather than substituting data.
- Verified-by: `pytest tests/test_data.py -k "published_counts or tumour_grade"`
- Rationale: A silent synthetic fallback produced an entire set of results,
  figures and reports from data whose outcomes were independent of its
  covariates. Nothing downstream could detect it.

## INV-002 — Preprocessing preserves prognostic signal

- Scope: `src/data/cohorts.py`, `src/data/fold_preprocessing.py`.
- Contract: Within analysis-training subjects of the first paired outer fold,
  a declared primary covariate retains its raw univariate concordance after training-fitted
  preprocessing: `pnodes` on GBSG2 at least 0.60, `age` on WHAS500 at least 0.65,
  `nottingham_prognostic_index` on METABRIC at least 0.55.
- Verified-by: `pytest tests/test_data.py -k preserves_prognostic_signal`
- Rationale: If features and outcomes become misaligned, every model collapses
  to chance and the failure looks like weak models rather than broken data.

## INV-003 — Baselines reach their published range

- Scope: `src/models/cox.py`, `src/models/random_survival_forest.py`.
- Contract: On real raw cohorts and the deterministic first paired outer fold,
  concordance stays above 0.62 on GBSG2, 0.65 on WHAS500 and 0.60 on METABRIC
  for both baselines. Preprocessing is fitted only on analysis-training subjects.
- Verified-by: `pytest tests/test_models.py -k published_range`
- Rationale: These cohorts have published Cox baselines near 0.67, 0.75 and
  0.63. A baseline at chance indicates a pipeline defect, and this check
  catches it before any result is interpreted.

## INV-004 — Metrics match the reference implementation

- Scope: `src/evaluation/metrics.py`.
- Contract: The concordance index agrees exactly with
  `sksurv.metrics.concordance_index_censored`, including tie handling.
- Verified-by: `pytest tests/test_metrics.py -k matches_scikit_survival`
- Rationale: Every reported number depends on the metric. A metric that is
  only approximately right makes all comparisons unreliable.

## INV-005 — Convergence diagnostics are computed, never asserted

- Scope: `src/models/bayesian/diagnostics.py`, `src/models/bayesian/model.py`.
- Contract: R-hat, effective sample size and divergent transitions are derived
  from the posterior trace via arviz. No function returns a fixed diagnostic
  value.
- Verified-by: `pytest tests/test_models.py -k report_diagnostics`
- Rationale: The previous diagnostics returned a hardcoded R-hat of 1.01 and
  an effective sample size of 1500 regardless of the fit, so every model
  appeared to converge.

## INV-006 — Every package imports and every analysis module runs

- Scope: `src/`.
- Contract: Every remaining package under `src/` imports without error.
  Event-stratified bootstrap, single-time AUC and full outer-fold evaluation
  run on real data using training-fitted preprocessing and training censoring.
  Every eligible subject appears exactly once in validation within a repeat.
- Verified-by: `pytest tests/test_pipeline.py`
- Rationale: Functional analysis utilities and the active pipeline must remain
  usable after retirement of unused pilot loaders and placeholder packages.

## INV-007 — Reported numbers trace to a result file

- Scope: `reports/`.
- Contract: Every current quantitative report corresponds to a hash-verified
  cell or aggregate in its declared run. Rendered files record exact source
  keys, source hashes and renderer code hashes. Missing estimates and failed
  gates remain explicit; post-hoc sensitivity never replaces confirmatory data.
- Verified-by: `pytest tests/test_confirmatory_rendering.py tests/test_holm_bounds.py tests/test_posthoc_evidence.py tests/test_results_programme.py`
- Rationale: The previous reports narrated numbers that no longer matched any
  artefact, and drew conclusions the data did not support.

## INV-008 — Frozen evidence and current refits keep separate identities

- Scope: `src/utils/frozen_evidence.py`, confirmatory/robustness resume,
  `scripts/reproduce_confirmatory_cells.py`.
- Contract: Historical inputs match all 80 pinned Git blobs; live protocol,
  raw data/manifest and lock inputs retain their frozen content. Completed
  confirmatory resume is read-only. Refit checkpoints verify actual source
  identity and saved-cell hashes before reuse; only timing fields are excluded
  from reproduction comparisons.
- Verified-by: `pytest tests/test_frozen_evidence.py tests/test_closed_confirmatory_resume.py tests/test_reproduction_checkpoint.py`
- Rationale: A readability change must not invalidate historical evidence or
  silently mix cells computed by different implementations.

## INV-009 — Sampler sensitivity is complete, separate and acceptance-only

- Scope: `src/pipelines/posthoc_sampler.py`, `src/utils/posthoc_evidence.py`.
- Contract: Refit all 75 original horseshoe folds, change only target acceptance
  to 0.999 on every original attempt, preserve seeds/folds/remedies and the
  diagnostic gate, and retain all nine contrasts against unchanged comparators.
  Every cell and aggregate is labelled post-hoc; remaining failures are reported.
- Verified-by: `pytest tests/test_posthoc_sampler.py tests/test_posthoc_evidence.py`
- Rationale: Selecting only failures or relabelling a sensitivity as confirmatory
  would change the accepted evidence and conceal diagnostic attrition.
