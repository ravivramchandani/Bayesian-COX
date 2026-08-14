# Claim–evidence register

This register controls the strength of thesis and paper claims. It is not a
results table. Status values are `VERIFIED`, `EXPLORATORY`, `PLANNED`,
`OWNER-PENDING` and `PROHIBITED`.

Before submission, each retained manuscript claim must also record its exact
wording, source/result key, code and data manifest, reviewer and verification
date. If evidence changes, the claim is weakened or removed; the analysis is
not changed to rescue it.

## Language rules

- “Superior” requires a prespecified paired contrast whose Holm-adjusted
  p-value is at most 0.05 and whose nominal 95% Nadeau–Bengio interval excludes
  zero. The interval is not multiplicity-adjusted; the cohort, metric and
  effect size are stated in the same passage.
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
| C-003 | Confirmatory METABRIC contains 1,980 positive-time records and 1,144 deaths | VERIFIED | Pinned cBioPortal snapshot, `data/manifest.yaml`, derived SHA-256 and exact-count/schema tests agree | Preserve the pinned commit, eligibility rule and derived hash with the claim |
| C-004 | The current 1,903-person METABRIC benchmark represents the full eligible clinical cohort | PROHIBITED | It omits 77 otherwise eligible positive-time records and 41 deaths | Describe it only as an exploratory 2020 Kaggle/cBioPortal-derived subset |
| C-005 | The current benchmark provides confirmatory model-comparison evidence | PROHIBITED | Holdout was inspected; CV preprocessing sees validation folds; test outcomes choose horizons; per-fold predictions are absent | Current numbers may be called exploratory/pilot only |
| C-006 | The verified locked environment passes the automated suite and lint | VERIFIED | Fresh locked environment, exact lock hash and environment-verifier report exist; 150 tests passed without warnings and Ruff was clean on 2026-08-15 | State the exact test/lint status, lock hash, date and code/input freeze if used in a reproducibility report |
| C-007 | A clean clone exactly reproduces the confirmatory results | PLANNED | Exact dependency/data locks, deterministic seeds, content hashes and refusal-on-mismatch logic are implemented; no frozen production result exists to rerun | Claim only after protocol freeze, completed production run and independent checksum-equivalent rerun |
| C-008 | DeepSurv is a completed confirmatory benchmark arm | PLANNED | Reference pycox CoxPH wrapper, pinned torch/pycox/torchtuples and deterministic signal/prediction/support tests pass; the old rehearsal's WHAS500/METABRIC cells failed before the support fix and no final paired run exists | Claim completion only after every frozen paired cell and result manifest passes |
| C-009 | IBS demonstrates calibration | PROHIBITED | IBS combines calibration and discrimination. Explicit curve, calibration-in-the-large/intercept and slope code is now implemented and tested, but confirmatory estimates are absent | Call IBS probabilistic prediction error; make calibration wording only from the explicit frozen calibration outputs |
| C-010 | Uno's C-index is the primary censoring-robust discrimination result | PLANNED | Fold-level implementation matches scikit-survival in reference tests and rejects unsupported horizons; confirmatory estimates are absent | Claim as a result only after frozen paired cells pass; methodology wording is verified |
| C-011 | All Bayesian fits converged | PLANNED | All-parameter R-hat, bulk/tail ESS, MCSE, divergence, BFMI and tree-depth gates plus prior/posterior predictive summaries are implemented and tested; confirmatory fits are absent | Make a fit-level claim only for cells whose frozen diagnostics pass; retain failed cells explicitly |
| C-012 | The horseshoe improves smaller-cohort prediction | EXPLORATORY | Current point estimates are cohort-specific without paired inferential intervals | Present as a hypothesis-generating pilot pattern until RQ1/RQ2 pass |
| C-013 | Prior influence vanishes at large sample size or proves Bernstein–von Mises behaviour | PROHIBITED | One larger cohort with near-equal point estimates does not establish the theorem or mechanism | Use only a controlled information-regime result with qualified wording |
| C-014 | Continuous spike-and-slab output is a posterior inclusion probability | PROHIBITED | The implementation uses a continuous scale-mixing weight, not a discrete indicator | Call it a continuous inclusion weight/signal; define it mathematically |
| C-015 | Bayesian intrinsic importance and SHAP discover the true important features | PROHIBITED | They quantify different, model-conditional constructs; no ground truth exists in real cohorts | Report agreement/stability only, with within-model comparison and uncertainty |
| C-016 | Explanations are stable | PLANNED | Frozen-cell exact linear-SHAP analysis, random paired subject/background samples, three nested budgets, three seeds and three-stage bootstrap uncertainty are implemented and tested; no production explanation artefact exists | Claim only after the frozen fold/subject/seed stability intervals meet the prespecified rule |
| C-017 | Selected features are clinically established prognostic factors | EXPLORATORY | A qualitative pilot observation exists without feature-level clinical citations | Verify each named factor with primary clinical evidence; make no causal claim |
| C-018 | The primary WHAS500 specification is restricted to documented admission/baseline predictors | VERIFIED | Frozen primary feature config and tests exclude length of stay and complications whose onset timing is not established | Do not imply excluded complications are post-admission; state that their baseline availability was unverified |
| C-019 | The primary METABRIC specification excludes surgery and treatment-received variables | VERIFIED | Frozen baseline/pathology config and tests; pinned cBioPortal metadata defines OS in months since initial diagnosis | The endpoint may be described as OS since initial diagnosis; do not infer treatment timing or clinical utility beyond the verified variables |
| C-020 | Posterior uncertainty includes missing-covariate uncertainty | PROHIBITED | A five-imputation, fold-local METABRIC sensitivity is implemented: risk scores and survival probabilities are averaged before pooled metrics are recomputed, while per-imputation metrics and diagnostics are archived separately. It does not form one posterior integrating covariate uncertainty | Report the sensitivity and this limitation; never describe it as full Bayesian propagation of imputation uncertainty |
| C-021 | Results are robust to missingness, censoring, PH assumptions and feature choices | PLANNED | A prespecified, checkpointed robustness runner and inference schema are implemented and tested; no production robustness estimates exist | Use only after the prespecified robustness run and uncertainty gate, naming every dependence or reversal |
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
5. Have statistical claims reviewed by the statistical supervisor. No named
   clinical reviewer is available; therefore every clinical factual statement
   requires an authoritative source, and unsupported interpretation is
   removed rather than represented as externally reviewed.
6. Run a chapter-by-chapter audit at the evidence-freeze, full-draft and
   examiner-ready gates. Zero `PLANNED`, `OWNER-PENDING` or unsupported claims
   may remain in submitted text.
