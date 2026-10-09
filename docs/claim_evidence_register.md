# Claim–evidence register

This register controls the strength of thesis and paper claims. It is not a
results table. Status values are `VERIFIED`, `EXPLORATORY`, `PLANNED`,
`OWNER-PENDING` and `PROHIBITED`. The active baseline table below
records evidence status and human approval separately.

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
5. Statistical-supervisor review is the default. ADR-048 records the owner's
   one-time waiver for this evidence-lock milestone; waived review is not
   reported as external approval. Clinical factual statements still require
   authoritative sources, and unsupported interpretation is excluded.
6. Run a chapter-by-chapter audit at the evidence-freeze, full-draft and
   examiner-ready gates. Zero `PLANNED`, `OWNER-PENDING` or unsupported claims
   may remain in submitted text.

## Submission-baseline claim dispositions - 2026-10-07

These rows are the active evidence-backed wording candidates for the ADR-044
submission baseline. Codex root checked the source traces and boundaries on
2026-10-07. Under ADR-048, the owner waived external reviewer decisions for
this evidence-lock milestone and authorized these conservative claims. This is
not represented as supervisor or clinical-reviewer approval. These dated
rows supersede historical result statuses in C-007, C-008, C-011, C-016 and
C-021; the original rows remain as claim-development history. Only the
active baseline dispositions below are cleared for the locked submission
scope. Other historical candidates retain their prior statuses; PLANNED or
EXPLORATORY candidates are excluded unless their own evidence gates are later
completed. PROHIBITED claims remain out of scope.

| ID | Proposed submission wording | Evidence and trace | Evidence status | Allowed boundary | Reviewer, date and status |
| --- | --- | --- | --- | --- | --- |
| S-001 | The confirmatory run stored 450 planned cells; 430 passed the frozen diagnostic gate and 20 horseshoe cells failed. | Confirmatory completion SHA-256 44d5d6e2c3cf4d0350c3bc8cb27291436c9934b219c4c895cb139525e6fa25f6; run-manifest SHA-256 2a1817365675aa179174b5edf5b3da67bbcb2be1b2eb4143347e4b295052ce02; private release confirmatory-v1-44b6085. | Evidence reviewed | Preserve the failed cells and the all-horseshoe failure pattern. | Codex root, 2026-10-07; SS review waived by owner under ADR-048 |
| S-002 | Five of nine prespecified primary contrasts were estimable from all 25 paired folds. The Holm family is incomplete; no complete-family superiority or equivalence conclusion is made. | Numerical summary coordination/recovery/2026-09-28-numerical-evidence-summary.json, SHA-256 9477ad52020ef7951e7cbe24ac6d6b2096a4369f9d1843d5cdf33cf2a42ddc5c; confirmatory release archive SHA-256 0dbb745b82e5998b5aabc4bb3f05b28f87e00ba2851101a8accb83d447ddf34b. | Evidence reviewed | Do not imply all nine tests or the full multiplicity adjustment are available. | Codex root, 2026-10-07; SS review waived by owner under ADR-048 |
| S-003 | None of the five estimable contrasts could be Holm-rejected for any values of the four missing p-values. This bound supplies neither missing estimates nor evidence of equivalence. | Render-equivalence record coordination/recovery/2026-09-27-render-equivalence.json; CSV SHA-256 df7b77c20ef63b3ed26e013b97308693b9329a0c3d484f80338cefc229f41c14; TeX SHA-256 a43c53e453d45ecb750c355b0fa95ab10b0b5f7ddd5e7f8f9b4d2e0796a3e082. | Evidence reviewed; post hoc | Label separately as the ADR-033 mathematical bound. | Codex root, 2026-10-07; SS review waived by owner under ADR-048 |
| S-004 | The robustness grid contains 825 stored cells: 770 passed diagnostics and 55 failed. Of 129 direct-effect rows, 121 estimates are available, 95 with full paired coverage, 26 partial and 8 unavailable. All 45 difference-in-differences have estimates, 33 with full and 12 with partial coverage. No robustness p-values were calculated or stored. | Robustness completion SHA-256 8f136a6b2f9cf0a18308db71d63a69b1b145b0c767548cc7465d4af73e781152; run-manifest SHA-256 0fc556b803da4f37daa9a63dbddc5ce5ffd350aa2b2831b0a6546b634c36139f; supplementary archive SHA-256 05918c159acf84367cdcbb8d9fdd5cf8a6ceeb1bf6d72fb56d9a4ab09f7ea7e4. | Evidence reviewed | Descriptive estimates and intervals only; retain pairing coverage and failures. | Codex root, 2026-10-07; SS review waived by owner under ADR-048 |
| S-005 | The separate 75-cell ADR-032 sampler sensitivity passed diagnostics. Its nine Holm-adjusted p-values are 1.0 and every corrected interval includes zero. It does not replace original failures or establish equivalence. | Completion SHA-256 0684ca1e61ef8492f27c79f486ea8e57cc75e139808f9a15535f426e82d4833a; manifest SHA-256 76acf071cf41f5456538799625979775ad00a5ab699b55b88987fee7ed6c5d00; sensitivity archive SHA-256 7445abe7fb28c85a559566ad54cb4e5cf70e663250dd3b4f25a4d4ff55ce69ee. | Evidence reviewed; post hoc | Keep separate from and subordinate to original confirmatory outcomes. | Codex root, 2026-10-07; SS review waived by owner under ADR-048 |
| S-006 | The explanation analysis did not pass its global stability gate: 102 of 1,640 evaluable comparisons failed. No global explanation-stability claim is made. | Frozen explanation JSON SHA-256 120984c7edfac468f471b9f500470623689b2647e4bde56d271cc9623346ecd5; original explanation release and programme confirmatory reports archive. | Evidence reviewed | Agreement is model-conditional, not feature truth; do not generalise to RSF SHAP. | Codex root, 2026-10-07; SS review waived by owner under ADR-048 |
| S-007 | All 450 saved confirmatory refits matched on recorded scientific fields in the reproduction check; timing and content-hash fields were excluded. | Reproduction verification SHA-256 5ee67afad696efe1848f3b697c45ed995127ec5cefbefac21291b4753af1ec28; reproduction archive SHA-256 4f5b684dad73ebe1c6fbc612ce95a51648ab11d05524c7ca970e47392ec96826. | Evidence reviewed | Say only matched on the compared scientific fields; do not claim byte-identical traces or that every timing/hash field matched. | Codex root, 2026-10-07; SS review waived by owner under ADR-048 |
| C-029 | The study is a retrospective comparison of survival-prediction methods in three public cohorts. Each model is fitted within its cohort; no locked model is externally validated. | data/manifest.yaml and docs/study_protocol.md; source commits, endpoint definitions and cohort counts are recorded in the pinned data manifest. | Source-bounded wording reviewed 2026-10-07 | Call this multi-cohort benchmarking, not external validation, transport or clinical deployment. | Codex root, 2026-10-07; domain review waived by owner under ADR-048 |
| C-030 | WHAS500 primary predictors are restricted to admission-time variables. Length of stay is excluded; baseline availability of selected complications was not verified. | data/manifest.yaml, WHAS500 primary_admission feature rule and docs/study_protocol.md. | Source-bounded wording reviewed 2026-10-07 | Do not state that excluded complications occurred after admission. | Codex root, 2026-10-07; domain review waived by owner under ADR-048 |
| C-031 | METABRIC overall survival is measured in months since initial diagnosis under the pinned cBioPortal metadata. Surgery and treatment-received variables are excluded from the primary feature set. | Pinned cBioPortal commit 165bd77077b03038f9c2ee104959eb474770b2a9, data/manifest.yaml, and docs/study_protocol.md. | Source-bounded wording reviewed 2026-10-07 | Do not infer treatment timing, treatment effect or clinical utility. | Codex root, 2026-10-07; domain review waived by owner under ADR-048 |
| C-032 | GBSG2 uses the source dataset's recurrence-free-survival event measured in days; the exact clinical time origin is not stated in pinned data documentation. | Pinned scikit-survival commit 3e887ed7307a60c08f3fafec8b00d57f7a2d4982 and data/manifest.yaml. | Source-bounded wording reviewed 2026-10-07 | Do not supply a more specific clinical anchor without primary-source confirmation. | Codex root, 2026-10-07; domain review waived by owner under ADR-048 |
| C-033 | The study does not estimate treatment effects or establish causal relationships, clinical utility or deployment readiness. | Frozen scope and exclusions in docs/study_protocol.md; ADR-044 submission scope; no decision-utility or locked external-validation design. | Evidence boundary reviewed 2026-10-07 | Prohibited claims remain prohibited; this is a scope statement. | Codex root, 2026-10-07; PS review waived by owner under ADR-048 |
| C-034 | No first-study or other priority-of-discovery claim is made. | Existing C-024 remains prohibited; no complete novelty search is claimed. | Evidence boundary reviewed 2026-10-07 | Use a specific contribution statement only after a dated literature review supports it. | Codex root, 2026-10-07; PS review waived by owner under ADR-048 |
| C-035 | GBSG2 contributes 686 records and 299 observed recurrence events. | Pinned scikit-survival data source and data/manifest.yaml; derived-data SHA-256 2158b777d27ecfb69b187d3cbcad13fd1eb92d626935c528a4465fea6490ae5f. | Evidence reviewed 2026-10-07 | State dataset counts without adding unsupported clinical interpretation. | Codex root, 2026-10-07; PS review waived by owner under ADR-048 |
| C-036 | WHAS500 contributes 500 records and 215 observed deaths. | Pinned scikit-survival data source and data/manifest.yaml; derived-data SHA-256 4bb01775c04eca11d7f06d6e5dfebd0a5cce75aa7e73fe4261732385be106fcc. | Evidence reviewed 2026-10-07 | State dataset counts without adding unsupported clinical interpretation. | Codex root, 2026-10-07; PS review waived by owner under ADR-048 |
| C-037 | METABRIC contributes 1,980 eligible positive-time records and 1,144 observed deaths. | Pinned cBioPortal DataHub commit 165bd77077b03038f9c2ee104959eb474770b2a9 and data/manifest.yaml; derived-data SHA-256 731ea80ce0240cb6aa96ffb0f4a3bb379615202966c954512664bef02b29545c. | Evidence reviewed 2026-10-07 | Use this eligible analysis cohort count, not the exploratory subset. | Codex root, 2026-10-07; PS review waived by owner under ADR-048 |

These dispositions lock the evidence sources and conservative wording for
the submission baseline under ADR-048. No external reviewer approval is
claimed. T-106 and T-147 are complete by owner override; unsupported claims
remain excluded, and no additional result wording is authorized without a
corresponding frozen artifact and source trace.
