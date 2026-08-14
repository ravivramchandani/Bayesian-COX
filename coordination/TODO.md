# TODO

Live task list, grouped by phase. Completed tasks are pruned; history lives in
git.

---

## Phase 0 — Repair and verification (done)

Complete. The data path, metrics, baselines, Bayesian inference, diagnostics
and explainability were rebuilt and put under test.

## Phase 1 — Benchmark (done)

Complete. Fifteen model-cohort fits and eighteen explainability comparisons
in `reports/tables/`, 21 figures in `reports/figures/`, reports generated
from those files.

- T-013 — Add calibration curves to the benchmark output. The estimator
  exists in `src/evaluation/calibration.py` but nothing calls it.
- T-014 — Add DeepSurv to the benchmark as the deep-learning arm (ADR-009).

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
- T-032 — WHAS500 sensitivity run without `los`, settling whether it leaks
  outcome information (ADR-012).
- T-033 — If T-031 shows the existing priors degrading on small samples, add
  a catalytic prior as a fourth arm and measure it against them (Q-001).

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
