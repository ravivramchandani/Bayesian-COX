# TODO

Live task list, grouped by phase. Completed tasks are pruned; history lives in
git.

---

## Phase 0 — Repair and verification (done)

Complete. The data path, metrics, baselines, Bayesian inference, diagnostics
and explainability were rebuilt and put under test.

## Phase 1 — Benchmark

- T-010 — Run the full benchmark across all three cohorts and commit
  `reports/tables/benchmark.json`.
- T-011 — Run the explainability comparison and commit
  `reports/tables/explainability.json`.
- T-012 — Generate figures: posterior forest plots, survival curves with
  credible bands, calibration curves, SHAP summaries.

## Phase 2 — Statistical comparison

- T-020 — Paired comparison of models across CV folds with multiplicity
  control.
- T-021 — Bootstrap confidence intervals for the headline concordance
  differences.
- T-022 — Prior sensitivity sweep over the horseshoe global scale and the
  spike-and-slab spike and slab widths.

## Phase 3 — Robustness

- T-030 — Censoring-rate sensitivity by administrative truncation.
- T-031 — Small-sample behaviour by subsampling the training split, which is
  where the sparsity priors should show their advantage.
- T-032 — WHAS500 sensitivity run without `los` (Q-005).

## Phase 4 — Thesis writing

- T-040 — Methodology chapter: cohorts and selection rationale, baselines,
  Bayesian formulation, prior specifications with hyperparameters, sampler
  configuration, diagnostics protocol, explainability comparison protocol,
  evaluation framework.
- T-041 — Operationalise the research questions with measurable success
  criteria.
- T-042 — Results chapter from `reports/tables/`.
- T-043 — Discussion, limitations, future work.
- T-044 — Abstract, written last.

## Phase 5 — Submission

- T-050 — Reproducibility appendix: dependency versions, hardware, seeds,
  dataset provenance, runtime per stage.
- T-051 — Citation audit; every entry carries a DOI or arXiv identifier.
- T-052 — Figure audit; every figure traces to a script and a result file.
- T-053 — Final compile with zero undefined references.
