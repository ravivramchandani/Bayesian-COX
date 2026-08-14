# Claim–evidence register

This register controls the strength of thesis and paper claims. It is not a
results table. Status values are `VERIFIED`, `EXPLORATORY`, `PLANNED`,
`OWNER-PENDING` and `PROHIBITED`.

Before submission, each retained manuscript claim must also record its exact
wording, source/result key, code and data manifest, reviewer and verification
date. If evidence changes, the claim is weakened or removed; the analysis is
not changed to rescue it.

## Language rules

- “Superior” requires a prespecified paired contrast whose multiplicity-
  adjusted 95% interval excludes zero. The cohort, metric and effect size are
  stated in the same passage.
- An interval containing zero supports “no clear evidence of a difference,”
  not “equivalent.” Equivalence/non-inferiority requires a justified margin
  frozen before analysis.
- “Better calibrated” requires calibration slope/intercept or curve evidence.
  IBS alone is insufficient because it combines calibration and
  discrimination.
- “Prior effects diminish as information increases” requires the controlled
  RQ2 interaction/difference-in-differences, not a visual comparison of three
  cohorts.
- “Stable explanation” requires resampling uncertainty. Agreement between
  methods is model-conditional and is not feature truth.
- “External validation” requires a locked model evaluated without retuning in
  a compatible external cohort. Independently refitting on different cohorts
  is multi-cohort benchmarking.
- “Clinically useful/meaningful” requires a defined clinical use, decision
  threshold and utility analysis. Those are outside this study, so this
  wording is prohibited.
- No causal, treatment-benefit, fairness-effectiveness, deployment,
  universal-superiority or cross-domain generalisation claim is allowed.

## Register

| ID | Candidate claim | Current status | Present evidence | Required submission gate / allowed wording |
|---|---|---|---|---|
| C-001 | GBSG2 contains 686 patients and 299 recurrence events | VERIFIED | Official scikit-survival API and local count test | Preserve pinned source/hash and original-trial citation |
| C-002 | WHAS500 contains 500 patients and 215 deaths | VERIFIED | Official scikit-survival API and local count test | Preserve pinned source/hash and source citation |
| C-003 | Confirmatory METABRIC contains 1,980 positive-time records and 1,144 deaths | PLANNED | Pinned cBioPortal patient/sample snapshot and local proposal export agree; active pipeline has not yet been rebuilt | Claim only after source-manifest and exact-count tests pass |
| C-004 | The current 1,903-person METABRIC benchmark represents the full eligible clinical cohort | PROHIBITED | It omits 77 otherwise eligible positive-time records and 41 deaths | Describe it only as an exploratory 2020 Kaggle/cBioPortal-derived subset |
| C-005 | The current benchmark provides confirmatory model-comparison evidence | PROHIBITED | Holdout was inspected; CV preprocessing sees validation folds; test outcomes choose horizons; per-fold predictions are absent | Current numbers may be called exploratory/pilot only |
| C-006 | All 60 current automated tests pass and lint is clean | VERIFIED | `conda run -n bayes-cox make test` and `make lint`, 2026-08-14 | State with environment, date and commit if used in a reproducibility report |
| C-007 | A clean clone exactly reproduces the results | PLANNED | Seeds exist, but dependencies are open-ended and result/data manifests are incomplete | Claim only after dependency lock, clean-environment rerun and hash audit |
| C-008 | DeepSurv is a completed benchmark arm | PROHIBITED | A local class exists but is not in current result files; pycox/torch are not installed in the named environment | Claim only after reference validation, pinned dependencies and paired results |
| C-009 | IBS demonstrates calibration | PROHIBITED | IBS is a proper prediction-error score affected by calibration and discrimination; calibration code is unwired | Use “probabilistic prediction error” until calibration curves/slope/intercept exist |
| C-010 | Uno's C-index is the primary censoring-robust discrimination result | PLANNED | scikit-survival exposes the estimator; current reports use Harrell's C-index | Claim after fold-level IPCW implementation and tests pass |
| C-011 | All Bayesian fits converged | EXPLORATORY | Current summaries cover mainly `beta`; one divergence remains and baseline/prior parameters are not comprehensively gated | Limit to the inspected pilot variables; confirmatory claim requires all-parameter diagnostics and predictive checks |
| C-012 | The horseshoe improves smaller-cohort prediction | EXPLORATORY | Current point estimates are cohort-specific without paired inferential intervals | Present as a hypothesis-generating pilot pattern until RQ1/RQ2 pass |
| C-013 | Prior influence vanishes at large sample size or proves Bernstein–von Mises behaviour | PROHIBITED | One larger cohort with near-equal point estimates does not establish the theorem or mechanism | Use only a controlled information-regime result with qualified wording |
| C-014 | Continuous spike-and-slab output is a posterior inclusion probability | PROHIBITED | The implementation uses a continuous scale-mixing weight, not a discrete indicator | Call it a continuous inclusion weight/signal; define it mathematically |
| C-015 | Bayesian intrinsic importance and SHAP discover the true important features | PROHIBITED | They quantify different, model-conditional constructs; no ground truth exists in real cohorts | Report agreement/stability only, with within-model comparison and uncertainty |
| C-016 | Explanations are stable | PLANNED | Current analysis uses the first 40 test rows and one main sampling configuration | Claim only after fold/subject/seed stability intervals meet the frozen rule |
| C-017 | Selected features are clinically established prognostic factors | EXPLORATORY | A qualitative pilot observation exists without feature-level clinical citations | Verify each named factor with primary clinical evidence; make no causal claim |
| C-018 | WHAS500 is an admission-time prediction model using only available predictors | PLANNED | Current primary includes post-baseline length of stay; timing of complications needs audit | Claim only for the baseline-only specification after availability sign-off |
| C-019 | METABRIC is a diagnosis-time prediction model using only available predictors | PLANNED | Current predictors include surgery and treatment received; treatment dates are unavailable | Claim only for baseline/pathology primary predictors after timing audit |
| C-020 | Posterior uncertainty includes missing-covariate uncertainty | PROHIBITED | Current single imputation treats filled values as known | Claim only if fold-wise multiple-imputation uncertainty is propagated; otherwise state the limitation |
| C-021 | Results are robust to missingness, censoring, PH assumptions and feature choices | PLANNED | Required sensitivity analyses are not complete | Use only after the prespecified robustness gate, naming any dependencies |
| C-022 | Three cohorts provide external validation of one clinical model | PROHIBITED | Endpoints and predictor spaces differ and every model is refit | Call this multi-cohort benchmarking/replication settings |
| C-023 | The method generalises to non-healthcare domains | PROHIBITED | No non-healthcare data are evaluated | State only that the mathematics is applicable in principle, without empirical generalisation |
| C-024 | This is the first study to combine these methods | PROHIBITED | The novelty search is incomplete and related work is active | Replace with a precise contribution statement backed by a dated systematic search |
| C-025 | The work demonstrates clinical utility or supports deployment | PROHIBITED | No use case, threshold, impact study or external clinical validation exists | Frame as retrospective methodological evaluation only |
| C-026 | The study meets TRIPOD+AI and has low PROBAST+AI concern | PLANNED | Checklists/audit are not complete | Claim only after page-referenced checklists and independent review |
| C-027 | Dataset redistribution is permitted under the software MIT licence | PROHIBITED | Upstream data have separate terms, including METABRIC ODbL | Public archive must follow the approved data-release matrix |
| C-028 | The thesis will be accepted by a Q1 journal | PROHIBITED | Quartiles and editorial decisions are external and time-varying | Say “Q1-target” or “Q1-calibre”; re-verify journal/category at submission |

## Verification workflow

1. Draft the exact sentence and assign a claim ID before it enters a chapter.
2. Classify it as quantitative, methodological, factual/clinical or
   interpretive.
3. Link quantitative claims to an immutable result file and key; link factual
   claims to an authoritative source with DOI or another stable identifier.
4. Record dataset/config/code hashes for quantitative evidence.
5. Have statistical claims reviewed by the statistical supervisor and
   clinical claims reviewed by a domain-qualified reader.
6. Run a chapter-by-chapter audit at the evidence-freeze, full-draft and
   examiner-ready gates. Zero `PLANNED`, `OWNER-PENDING` or unsupported claims
   may remain in submitted text.
