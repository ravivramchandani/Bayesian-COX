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

- Scope: `src/data/preprocessing.py`.
- Contract: For each dataset a covariate with known prognostic value retains
  univariate concordance away from 0.5 after preprocessing: `log_pnodes` on
  GBSG2 at least 0.60, `age` on WHAS500 at least 0.65,
  `nottingham_prognostic_index` on METABRIC at least 0.55.
- Verified-by: `pytest tests/test_data.py -k preserves_prognostic_signal`
- Rationale: If features and outcomes become misaligned, every model collapses
  to chance and the failure looks like weak models rather than broken data.

## INV-003 — Baselines reach their published range

- Scope: `src/models/cox.py`, `src/models/random_survival_forest.py`.
- Contract: Test-set concordance stays above 0.62 on GBSG2, 0.65 on WHAS500
  and 0.60 on METABRIC for both baselines.
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
- Contract: Every package under `src/` imports without error, and the
  bootstrap, cross-validation and ranking modules run against real data even
  while no script calls them.
- Verified-by: `pytest tests/test_pipeline.py`
- Rationale: Modules not yet wired into a script have no other check. Three of
  them were left broken by a metrics rename and nothing detected it.

## INV-007 — Reported numbers trace to a result file

- Scope: `reports/`.
- Contract: Every quantitative claim in a report corresponds to a value in
  `reports/tables/*.json` produced by a script in `scripts/`.
- Verified-by: Manual check at phase exit, recorded in
  `coordination/phase_reports/`.
- Rationale: The previous reports narrated numbers that no longer matched any
  artefact, and drew conclusions the data did not support.
