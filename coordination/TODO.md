# TODO

Live task register for the 15-week thesis and paper programme, 2026-08-17 to
2026-11-30. Completed tasks are checked and later pruned; durable findings
belong in `JOURNAL.md`. The design and claim rules are in
`docs/study_protocol.md` and `docs/claim_evidence_register.md`.

Owners: **R** Ravi; **PS** principal supervisor; **SS** statistical/
associate supervisor; **DO** institutional data/ethics owner; **IR**
independent clinical, methods or library reviewer. Tier **T** is
thesis-essential; tier **P** is publication-enhancing and subject to the
drop rules in the protocol.

A checked task has met its current acceptance evidence. Implementation alone
is not a scientific result; production tasks are checked only when their frozen
artefacts satisfy the stated gate.

## Current programme — 2026-09-28

The September programme in `HANDOFF.md` supersedes the earlier downstream
pause. All modular refactors are integrated and passed their required gates:
six exact model refits; the original explanation SHA-256; three byte-identical
confirmatory aggregate files rebuilt from all 450 cells; the six quick-selection
and four specified additional confirmatory refits; and three exact robustness
refits. Rendering retains all original output paths with documented
presentation changes and five additions. Its complete 426-PDF review passed.
ADR-030 checkpoint verification is integrated, and
ADR-034 pilot retirement is complete. Historical data, results and retired
source history remain preserved. The recovery audit records the original
interruption state, which the completed engineering checkpoints supersede.
Current gate evidence is in
`coordination/reviews/2026-09-27-integrated-code-verification.md`.

The complete 426-page PDF review subsequently identified 30 presentation
defects in the legacy layouts. Full replacement rendering and review passed
all 426 PDFs, resolving every observed defect. See
`coordination/reviews/2026-09-27-full-pdf-review.md`.

Frozen robustness production and final aggregation have finished without
changing the original code or saved cells. Independent strict verification
accepted all 825 cells: 770 pass diagnostics and 55 fail. The six workers
and supervisor have exited; no manual finish or restart is needed.

Full reproduction from sealed commit
`11f86ced8735b32767debb58f3cbbefbb5a7b8e6` passed exhaustive independent
verification: 450/450 saved refits match every non-timing field. All 90 sealed
code hashes still match. ADR-032 completed 75 sensitivity cells and its
nine-contrast inference, with all diagnostics passing, all adjusted p-values
1.0 and all corrected intervals including zero. Both final rendered lineages,
all 428 PDFs, coverage/claim review, packaging and local/fresh remote restore
passed. Completed results and full QA/log audit are in two new private
releases. Ravi's commands are in `docs/ravi_handoff.md`; completed fits need
no rerun. Final receipt: `coordination/recovery/2026-09-28-programme-closeout.json`.
Original explanation production retains its failed convergence gate and
permits no RQ3 stability claim. Overleaf edits remain excluded; the 19 recorded
thesis corrections belong to T-152 through T-156 when thesis work resumes.

The earlier wrap-up checkpoint is preserved unchanged. After the Mac rebooted,
the owner's instruction to complete all remaining tasks resumed the full
programme locally at 07:51:46 UTC on 2026-09-27: robustness 551/825,
reproduction 154/450 and sensitivity 0/75. The restart receipt and resumption
steps are in `HANDOFF.md` and
`coordination/recovery/2026-09-27-restart-checkpoint.json`. Production tasks
are complete where actual evidence satisfies their acceptance criteria.
Historical restart counts are superseded by final close-out above.

## Completed foundation

- [x] T-000 (T) — Phase 0 repair and verification. Evidence:
  `coordination/phase_reports/phase-0.md`.
- [x] T-001 (T) — Exploratory core benchmark: 15 model-cohort fits and 18
  explanation comparisons. Evidence: `reports/tables/benchmark.json` and
  `reports/tables/explainability.json`. These artefacts are pilot evidence,
  not the confirmatory analysis.

## Weeks 1–2 — Integrity, scope and governance

- [x] T-100 (T, W1, owner R; depends T-001) — Reconcile coordination state
  and write the exploratory Phase 1 report. Acceptance: TODO, HANDOFF,
  JOURNAL, DECISIONS and OPEN_QUESTIONS agree; the report traces every pilot
  value and labels all limitations. Evidence:
  `coordination/phase_reports/phase-1-confirmatory-foundation.md`.
- [x] T-101 (T, W1–2, owners R/PS/SS; depends T-100) — Freeze contribution,
  prediction times, RQs, hypotheses, estimands, primary contrasts, analysis
  populations and scope exclusions. Acceptance: versioned protocol signed off
  before confirmatory results are inspected. Evidence: owner approval, the
  result-blind compute decision and the content-addressed freeze recorded under
  T-130/T-131.
- [x] T-102 (T, W1–2, owners R/DO; no engineering dependency) — Record the
  owner-approved secondary-data ethics/privacy determination and approve the
  data-availability wording. Acceptance: Q-002 records the dated owner approval
  and the absence of an institutional reference; no identifier is invented.
- [x] T-103 (T, W1–2, owners R/DO; no engineering dependency) — Complete the
  dataset licence and redistribution matrix. Acceptance: each source has
  licence, attribution, public-release rule and owner decision; Q-003
  answered before a public archive is released.
- [x] T-104 (T, W1–2, owners R/PS/SS; depends T-101) — Specify and approve the
  statistical analysis plan. Acceptance: primary/secondary metrics, corrected
  repeated-CV inference, multiplicity family, missing-data rules, sensitivity
  rules and failed-fit handling are fully specified in the approved protocol/
  config.
- [x] T-105 (P, W1–2, owners R/PS; no dependency) — Select two journal
  candidates and one fallback. Acceptance: dated scope, public ranking
  indication, limits, fees, open-science and authorship/declaration policies
  recorded; Q-005 answers the owner decision. The applicable institution-
  accepted ranking source and official author facts remain subject to T-172
  factual re-verification, not a new owner decision.
- [ ] T-106 (T, W1–2, owners R/PS/SS/IR; begins immediately) — Establish and
  review the claim–evidence ledger. Acceptance: every submitted quantitative,
  clinical and novelty claim has an artefact/source, permitted wording,
  reviewer and verification date.
- [x] T-107 (T, W1–2, owner R; no dependency) — Repair the LaTeX/BibTeX
  foundation. Acceptance: `latexmk -halt-on-error` and BibTeX succeed; zero
  undefined citations/references, duplicate labels, replacement characters
  or legacy instructional placeholders. Evidence: clean 70-page A4 build,
  embedded fonts, clean log/box audit and `make jargon` pass. Deliberate
  result-gated stubs remain under T-153/T-154/T-156.
- [ ] T-108 (T, W1–2, owners R/PS; depends T-101) — Replace the template with
  the approved thesis architecture and word budget. Acceptance: every chapter
  has a purpose, evidence inputs and supervisor-approved target length.
- [x] T-109 (T, W1–3, owners R/IR; depends T-106) — Rebuild the bibliography
  from publisher/Crossref/authoritative records. Acceptance: every retained
  source has complete metadata and the best stable identifier for its source
  type; no missing, malformed or unused keys. Evidence: 36 retained entries,
  all cited; 30 DOI records and six authoritative web records verified.

## Weeks 1–3 — Data and predictor integrity

- [x] T-110 (T, W1–2, owner R; depends T-103) — Add a machine-readable source
  manifest. Acceptance: immutable URL/release/commit, retrieval date, DOI,
  licence, upstream/derived SHA-256, eligibility rule and endpoint coding for
  all three cohorts.
- [x] T-111 (T, W1–2, owner R; depends T-110) — Rebuild METABRIC from the
  pinned cBioPortal DataHub patient/sample snapshot. Acceptance: exact tests
  establish 1,980 positive-time records and 1,144 deaths, schema/value checks
  pass, and all METABRIC pilot results remain clearly separated.
- [x] T-112 (T, W1–2, owners R/SS/IR; depends T-101) — Audit prediction-time
  availability for every predictor. Acceptance: source-variable table and
  owner-approved conservative rule;
  primary WHAS500 excludes `los`; primary METABRIC excludes post-diagnosis
  treatment/surgery variables unless timing is defensible. No clinical-reviewer
  signature is invented; authoritative source evidence and conservative
  exclusions implement the owner-approved response in Q-006.
- [x] T-113 (T, W2–3, owner R; depends T-112) — Freeze primary and sensitivity
  feature sets. Acceptance: NPI/component redundancy, raw/log duplicates,
  interactions, categorical groups and feature degrees of freedom are
  prespecified and unit-tested.
- [x] T-114 (T, W2–3, owners R/SS; depends T-111/T-113) — Produce missingness
  and inclusion-flow specifications. Acceptance: fold-local primary handling
  plus multiple-imputation/core-feature sensitivity is prespecified; no claim of
  propagated imputation uncertainty unless implemented.
- [x] T-115 (P, decision W3, owners R/PS/SS/DO; depends T-101–T-114) — Decide
  the optional Rotterdam-to-GBSG2 locked transport evaluation. Acceptance:
  permanently dropped before freeze under ADR-025; no acquisition or
  harmonisation is authorised within this study.
- [x] T-116 (T, W1–3, owner R; no dependency) — Remove or repair duplicate
  cohort-loader schemas that disagree with the active pipeline. Acceptance:
  one authoritative loader/schema path per cohort and full data tests pass.

## Weeks 2–4 — Confirmatory infrastructure

- [x] T-120 (T, W2–3, owner R; depends T-113/T-114) — Build fold-local nested
  preprocessing. Acceptance: imputation, encoding, scaling, transformations,
  feature selection and horizon choice fit within each outer-training fold;
  leakage tests fail if validation data change a transformer.
- [x] T-121 (T, W2–3, owner R; depends T-104/T-120) — Implement the repeated
  five-by-five outer-CV and three-fold inner-CV design. Acceptance: event/time
  stratification, seeds and subject/fold IDs are deterministic and identical
  across paired models.
- [x] T-122 (T, W2–3, owner R; depends T-104/T-120) — Correct the evaluation
  layer. Acceptance: training-only horizons, IPCW IBS, Uno C, Harrell C and
  cumulative/dynamic AUC match reference implementations; unsupported
  horizons fail explicitly.
- [x] T-123 (T, W2–3, owners R/SS; depends T-122) — Wire survival calibration.
  Acceptance: calibration curves, intercept/calibration-in-the-large and slope
  with uncertainty at frozen horizons are generated and tested; IBS is no
  longer labelled calibration.
- [x] T-124 (T, W3–4, owners R/SS; depends T-104/T-121) — Implement valid
  paired inference. Acceptance: per-fold effects, Nadeau–Bengio corrected
  intervals/tests, Holm adjustment and event-stratified paired-bootstrap
  sensitivity pass simulation/reference tests; the constant-0.05 stub is
  removed.
- [x] T-125 (T, W2–3, owner R; depends T-121) — Expand the immutable result
  schema. Acceptance: predictions and metrics include subject, repeat/fold,
  dataset/config/code/dependency hashes, hyperparameters, seeds, runtime,
  hardware, commands and diagnostics.
- [x] T-126 (T, W3–4, owner R; depends T-125) — Make figures and reports pure
  renderers. Acceptance: they read frozen artefacts and never refit a model;
  lineage tests map every figure/table to a script and result key. The legacy
  pilot renderer remains explicitly separated from confirmatory targets.
- [x] T-127 (T, W3–4, owner R; depends T-101) — Validate the DeepSurv arm.
  Acceptance: pinned reference/parity implementation, real optimiser/dropout/
  normalisation/early-stopping configuration, compact inner grid, gradient
  and tiny-dataset overfit tests; otherwise a supervisor-approved ADR drops
  the comparator before protocol freeze.
- [x] T-128 (T, W3–4, owner R; depends T-101) — Complete Bayesian validation.
  Acceptance: time-scale/baseline-prior rule, prior predictive checks,
  posterior predictive checks and R-hat/ESS/MCSE/divergence/BFMI/tree-depth
  diagnostics for all parameters are tested and recorded.
- [x] T-129 (T, W2–4, owner R; no dependency) — Create an exact environment
  lock and clean-build workflow. Acceptance: a fresh environment installs
  pinned dependencies, all tests/lint pass, and the lock hash enters results.
  Evidence: 259 packages verified, 150 tests passed, Ruff clean; lock SHA-256
  `1921895d4a404fc99e848d69ccd4a3f6639a3d1610315c82ecd463ed4bcdfb57`.

## Weeks 4–8 — Protocol freeze and confirmatory evidence

- [x] T-130 (T, W4–5, owners R/SS; depends T-120–T-129) — Rehearse one outer
  fold per cohort/model without inspecting comparative effects. Acceptance:
  resource estimate, schema, diagnostics, calibration and failure handling
  pass; repeat count is fixed by the result-blind 72-hour compute rule.
  Evidence: the final-input rehearsal completed 18/18 cells and retained five
  repeats without comparative-effect inspection.
- [x] T-131 (T, end W5, owners R/PS/SS; depends T-130) — Freeze and tag the
  protocol, environment, data manifest, feature specifications, grids, seeds
  and analysis code. Acceptance: no methodological tuning after the tag.
  Evidence: write-once `config/protocol_freeze.json`; its content hash is the
  immutable analysis tag (no Git tag is claimed), with 80 verified input hashes
  and freeze content SHA-256
  `3b5e1042d592ebb6fade0a4a76c1f0d31ce9c0c1cfc08357be46f163f037d2ca`.
- [x] T-132 (T, W5–7, owner R; depends T-131) — Run confirmatory GBSG2,
  WHAS500 and METABRIC repeated nested CV. Acceptance: all planned cells and
  out-of-fold predictions exist or a prespecified failed-cell record explains
  the failure; rerun checksums match. Evidence: the verified frozen run at
  `reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651/` stores the
  exact 450-cell grid; 430 cells completed and 20 have prespecified
  `failed_diagnostics` records. Manifest, completion, aggregate and cell
  hashes, the complete-cell metric and prediction lineages and the unchanged
  80-input freeze passed the frozen-run checks.
- [x] T-133 (T, W5–7, owner R; depends T-132 progressively) — Triage MCMC and
  neural failures using only frozen remedies. Acceptance: no interpreted fit
  breaches the diagnostic gate and all interventions are logged. Evidence:
  all 20 failed cells are horseshoe fits and each records all three permitted
  attempts; the failed cells are excluded from aggregate metrics and
  inference. GBSG2 has 18 failed horseshoe folds, METABRIC has two and
  WHAS500 has none. No neural or other model cell failed.
- [ ] T-134 (T, W7–8, owners R/SS; depends T-132) — Produce the RQ1 primary
  and secondary estimates. Acceptance: paired effects, corrected 95%
  intervals, adjusted primary tests, calibration and compute costs trace to
  immutable results; all null/negative findings are retained. The aggregate
  artefacts exist, but this gate remains open: `inference.json` is explicitly
  `incomplete`, only five of nine primary contrasts have all 25 paired folds,
  and the nine-contrast Holm family is not complete. The two GBSG2 and two
  METABRIC contrasts involving the horseshoe have no confirmatory inference.
  Partial-family results must not be promoted as a complete primary analysis.
- [ ] T-135 (T, W7–8, owners R/PS/SS; depends T-134) — Complete the primary
  claim review. Acceptance: RQ1 wording is approved, unsupported superiority,
  equivalence and calibration claims are absent, and the results chapter
  skeleton is populated from generated tables. The September programme
  permits evidence review and rendering, while Overleaf edits remain outside
  that programme.

## Weeks 7–10 — Robustness and explanation

T-132 is complete and verified. T-140–T-144 production and evidence review
are complete. The summary and rendered tables retain diagnostic exclusions,
incomplete pairing, unavailable estimates and the failed explanation gate.
Completing these tasks does not establish general robustness, H2 support
or explanation stability.

- [x] T-140 (T, W7–8, owners R/SS; depends T-131) — Run the frozen prior
  hyperparameter and baseline-interval sensitivity. Acceptance: performance,
  uncertainty and diagnostics are compared without selecting a favourable
  configuration post hoc. The completed 825-cell run and aggregate hashes
  verify. Design effects: 39/45 estimates, 31/45 fully paired. Report
  intervals and attrition; no favourable configuration selected.
- [x] T-141 (T, W7–9, owners R/SS; depends T-132) — Run RQ2 sample-size and
  administrative-censoring analyses. Acceptance: identical subsamples across
  priors, difference-in-differences estimates and uncertainty answer H2.
  The frozen run verifies. All 54 RQ2 direct rows have estimates, 42 fully
  paired; all 45 difference-in-differences rows have estimates, 33 fully
  paired. Intervals include both signs; no uniform H2 support or invented
  robustness p-value is claimed.
- [x] T-142 (T, W7–9, owners R/SS; depends T-132) — Run feature-timing and
  missing-data sensitivities. Acceptance: WHAS500 with/without `los`,
  METABRIC baseline/treatment-augmented, NPI/components and missingness
  analyses all trace to frozen specifications. The five-imputation fold-local
  sensitivity is complete in the verified final robustness aggregates;
  feature effects have 28/30 estimates and 22/30 fully paired rows.
  Imputation averages predictions rather than forming a single posterior
  propagating covariate-imputation uncertainty; partial rows remain explicit.
- [x] T-143 (T, W7–9, owners R/SS; depends T-132) — Check proportional-
  hazards assumptions and the frozen response. Acceptance: global/covariate
  tests and within-fit multiplicity control are reported; supported violations
  become limitations. No time interaction or time-varying coefficient is
  fitted or introduced in response to the assessment, and no silent model
  change is permitted.
  The assessment verifies. METABRIC age and NPI reject within-fit Holm
  in all 25 outer fits; other findings are in the summary. Dependent-fit
  frequencies are descriptive and limit PH interpretation; no replacement
  model was fitted.
- [x] T-144 (T, W8–9, owners R/SS; depends T-132/T-113) — Run the revised
  RQ3 explanation protocol. Acceptance: random paired subjects, training-fold
  backgrounds, same-Bayesian-model SHAP, three-seed convergence, grouped
  features and fold/resample uncertainty are stored. The pure frozen-cell
  analysis produced 1,845 comparisons from 205 accepted Bayesian cells at
  `~/bayes-cox-runs/frozen/reports/explainability/confirmatory_v1_confirmatory_cdcdcee84651_explainability_v1.json`.
  Of 1,640 evaluable convergence comparisons, 102 failed. The prespecified
  summary is `failed`; no RQ3 claim is permitted. Preserve and report this
  outcome without changing the frozen gate.
- [x] T-145 (P, decision W7; owners R/SS) — Permanently drop the lean ADEMP
  simulation before freeze. Acceptance: ADR-025 records that no simulated
  result enters this study and coefficient-recovery simulation is future work.
- [x] T-146 (P, decision W3; owner R; depends T-115) — Permanently drop the
  Rotterdam-to-GBSG2 transport branch before acquisition or harmonisation.
  Acceptance: ADR-025 records the irreversible scope decision.
- [ ] T-147 (T, W9–10, owners R/PS/SS; depends T-140–T-145) — Freeze all
  thesis evidence. Acceptance: clean rerun manifest, statistical/clinical
  claim approval, immutable result tag and zero unresolved thesis-critical
  row in the claim ledger.

## Weeks 1–14 — Thesis writing and audit

- [ ] T-150 (T, W1–4, owners R/PS; depends T-101/T-109) — Replace the
  oversized literature review with a 5,000–7,000-word critical healthcare
  synthesis. Acceptance: exact gap/RQs follow from reviewed evidence; no
  duplicated textbook, cybersecurity, business or unsupported material. A
  6,281-word focused draft is complete; supervisor text review remains.
- [ ] T-151 (T, W1–3, owners R/PS; depends T-101) — Draft the introduction.
  Acceptance: context, gap, contribution, operational RQs, scope and chapter
  map are substantive and supervisor-approved. A 1,919-word substantive draft
  is complete; supervisor text review remains.
- [ ] T-152 (T, W2–6, owners R/SS; depends progressively T-101–T-131) — Draft
  methodology to match the frozen implementation. Acceptance: cohorts,
  eligibility, missingness, predictors, validation, equations, priors,
  diagnostics, metrics, explainability, ethics and deviations are complete.
  The substantive pre-freeze chapter and diagnostic appendix are complete;
  final frozen repeat/hash details and the corrections in
  `coordination/reviews/2026-09-27-thesis-review.md` remain to be applied.
- [ ] T-153 (T, W7–10, owners R/SS; depends progressively T-134–T-147) —
  Draft results from generated artefacts. Acceptance: exploratory and
  confirmatory evidence are separated; diagnostics, calibration, negative
  results and sensitivities are included without manual number transcription.
  The 2026-09-27 code programme prepares generated artefacts and recorded
  corrections; editing the Overleaf results chapter remains outside its scope.
  Scope includes the ADR-036/ADR-037 thesis experiments (T-180–T-186), with
  effects, uncertainty, paired coverage and diagnostic attrition. The original
  incomplete primary family and failed explanation gate remain explicit;
  Overleaf editing starts only on owner instruction.
- [ ] T-154 (T, W9–10, owners R/PS/SS; depends T-147) — Draft discussion and
  conclusion. Acceptance: each RQ is answered at its supported strength;
  limitations cover internal evaluation, endpoint heterogeneity, predictor
  timing, missingness, PH, explanation and absence of clinical deployment.
- [ ] T-155 (T, W9–10, owners R/DO; depends T-102/T-103/T-129) — Complete
  reproducibility, ethics and data appendices. Acceptance: exact commands,
  environment/hardware, seeds, manifests, access/licensing, diagnostic
  supplements, data-availability wording and governance statements are present.
  A substantive prospective appendix is complete; production run identifiers
  and evidence remain pending.
- [ ] T-156 (T, W10–11, owners R/PS; depends T-150–T-155) — Write abstract,
  keywords and front matter last. Acceptance: structured abstract agrees
  exactly with frozen results; no template text remains.
- [ ] T-157 (T, end W11, owners PS/SS; depends T-150–T-156) — Full-draft
  gate. Acceptance: every chapter is substantive, all RQs are answered and no
  thesis-critical claim lacks evidence.
- [ ] T-158 (T, W11–12, owners R/PS/SS; depends T-157) — Complete two
  supervisor review cycles. Acceptance: consolidated comments are resolved or
  dispositioned with rationale; holiday weeks are protected from new scope.
- [ ] T-159 (T, W12–13, owners R/IR; depends T-158) — Run independent
  statistical, citation, equation, figure, accessibility, TRIPOD+AI,
  PROBAST+AI and reproducibility audits. Acceptance: checklists are page-
  referenced; clean LaTeX has zero undefined items or material overflow.
- [ ] T-160 (T, end W13, owners R/PS/SS; depends T-159) — Produce the
  examiner-ready thesis. Acceptance: content, statistics, ethics, citations,
  formatting and archive receive final sign-off.
- [ ] T-161 (T, W14, owners R/PS; depends T-160) — Submit the university-
  format thesis/source/evidence archive, leaving Week 15 as contingency before
  the 2026-11-30 deadline.

## Paper and release — deferred until after thesis submission (ADR-036)

The thesis supplies the planned evidence base for the paper; future journal
review may require separately documented analyses. T-170 to T-174, T-187 and
T-188 start only after the thesis is submitted. This deferral does not stop
the existing programme's private code/evidence release and restore checks.

- [ ] T-170 (P, W9–11, owners R/PS; depends T-135 progressively) — Create
  the target-journal article and supplement architecture from frozen thesis
  evidence. Acceptance: contribution, reporting checklist and figure/table
  budget fit the selected journal with no new primary analysis.
- [ ] T-171 (P, W11–13, owners R/PS/SS; depends T-147/T-170) — Draft the
  manuscript and supplement. Acceptance: every statement uses the frozen
  claim ledger and result artefacts; title/abstract do not overclaim.
- [ ] T-172 (P, W13–14, owners R/PS/SS/IR; depends T-171) — Complete methods,
  domain and language review. Acceptance: a response matrix resolves every
  actionable comment and journal/category quartile is re-verified.
- [ ] T-173 (P, W13–15, owners R/DO; depends T-103/T-129/T-147) — Build the
  permissible publication archive. Acceptance: software, lock, manifests,
  derived outputs and data-access instructions have an archival DOI; upstream
  patient data are included only as allowed by the licence matrix.
- [ ] T-174 (P, W14–15, owners R/PS/SS; depends T-172/T-173) — Complete the
  journal submission package. Acceptance: manuscript, supplement, reporting
  checklist, cover letter, CRediT/COI/funding declarations and repository link
  are submission-ready.
- [ ] T-187 (P, deferred; depends T-186) — Draft the paper around when Bayesian
  shrinkage improves prediction or decision value beyond tuned penalised Cox,
  across dimensionality, prior specification and sampling reliability. Acceptance:
  TRIPOD+AI checklist complete; the target journal's quartile re-verified
  from JCR or SJR on the submission date.
- [ ] T-188 (P, deferred, owner action) — Mint an archival DOI for code and evidence
  (Zenodo), then submit. Owner steps: repository-to-Zenodo link, author
  declarations, journal submission.
- [ ] T-175 (T/P, W14–15, owners R/PS; no new scope) — Protected contingency
  for failed reruns, licence decisions, supervisor revisions, university
  corrections or journal formatting only.

## Thesis extension experiments — post-hoc under ADR-036–ADR-039

Owner instruction 2026-09-27: the thesis contains every experiment needed
for a Q1 journal paper, and the paper is drafted later. This is a quality
target, not an acceptance guarantee. Every result below is post-hoc and
labelled as such; the frozen confirmatory record stays primary. ADR-033's
Holm bound is already computed and rendered; ADR-032 has seven existing
probes and a separately specified 75-cell production stage. The extension
implementation and result-blind addendum are frozen; the 1,625-fit numerical
grid is active from sealed commit `119476f`. Its early cells are post-hoc
results, not a complete programme or grounds to check T-182–T-189 yet.
The strengthened analysis-only verifier is separately sealed at `8551d32` and cannot alter fitted
cells. Unmeasured two-hour and ten-hour runtime estimates are withdrawn;
estimate compute from actual monitored fits and resource use.

Programme close-out also requires reviewed finished-grid rank reconstruction
and inspection of all referenced retained traces, all 92 official exact
refit comparisons, actual visual QA, the private extension evidence release
and a fresh remote download/scientific restoration. Supplemental audits do
not alter the frozen generator, acceptance rules or original failed findings.
Current post-fit and numerical ownership are recorded in `HANDOFF.md`;
prepared transfer commands do not close these gates.
The prepared factual claim helper and supporting-bundle assembler require
actual finished-grid receipts, findings review and visual QA as appropriate.
Their passed pure checks and remote recovery archive preserve preparation;
they do not close numerical, scientific or transfer tasks.

- [x] T-180 (T; no dependency) — Write and freeze
  `docs/protocol_addendum_extensions.md` before results of the four new
  analyses exist. Acceptance: grids and inner-CV objectives, precise variant
  priors and survival-scale calibration, decision-curve action/thresholds/
  horizons/censoring/support, genomic eligibility and matched clinical
  controls, gene rule and feature budget are fixed. Specify hypotheses,
  metrics, comparison families, multiplicity, dependency-aware uncertainty,
  diagnostic/exclusion rules, seeds and reproduction checks. Reference the
  actual earlier ADR-032/ADR-033 decisions, probes and known results; do not
  label them result-blind. Record the addendum hash in a write-once file.
  Frozen under content hash
  `50b5f30f697b633718078e18c0da54be297361f8b06aeaf95af32e12aa1c646f`;
  write-once record: `coordination/extension_protocol_freeze.json`.
  No extension outer-validation result existed at this freeze.
  Also fixes the ADR-038 catalytic-prior settings: τ rules, synthetic-data
  generation, M and the reference-parity test case.
- [x] T-181 (T; depends frozen robustness completion) — Run the ADR-032
  horseshoe sampler sensitivity: all 75 cells at target acceptance 0.999.
  Acceptance: all 75 cells and their attempts are accounted for, with pass
  rate, paired coverage and the separate nine-contrast Holm family, including explicitly
  unavailable contrasts, rendered next to the frozen five-of-nine result.
  All 75 cells are stored, independently verified and pass diagnostics.
  Inference/completion and separate rendering now verify. All nine contrasts
  are estimable; all adjusted p-values are 1.0 and corrected intervals include
  zero. Final PDF QA passed. Independent of T-180; no duplicate run needed.
- [ ] T-182 (T; depends T-180) — Fit ridge, lasso and elastic-net Cox on the
  frozen outer folds of all three cohorts. Acceptance: same patients and
  evaluation rules as the Bayesian comparison; penalties selected by inner
  CV with preprocessing inside each training split; complete cell accounting,
  specified paired effects/uncertainty/multiplicity and reproduction checks.
- [ ] T-183 (T; depends T-180, T-181) — Run the Piironen–Vehtari horseshoe
  variant on all 75 clinical cells. Acceptance: fixed local/global/slab priors,
  expected relevant predictor count and justified survival-scale calibration;
  comparable ADR-032 sampler settings and unchanged gates; diagnostics, pass
  rate and paired contrasts labelled as joint prior-specification sensitivity.
- [ ] T-184 (T; depends T-180) — Run decision curve analysis from the stored
  out-of-fold predictions at the three training-defined horizons.
  Acceptance: survival net benefit against treat-all and treat-none, fixed
  clinical action/thresholds/censoring/support rules, and uncertainty that
  accounts for repeated patients across folds/repeats. Report every specified
  available curve and exclusions; identify fold-specific horizons honestly.
  No refitting or clinical deployment/impact claim.
- [ ] T-185 (T; preparation depends T-180 source rules; fitting depends T-180, T-182, T-183, T-189 implementation) — Build the matched METABRIC
  clinical-only and clinical-plus-expression comparison from the pinned
  cBioPortal archive. Acceptance: source hashes, audited patient/sample
  alignment and timing, same eligible patients/25 outer folds/endpoints/
  evaluation times in both arms. Fit gene selection, imputation and scaling
  inside the relevant training split, including inner CV; use the frozen
  feature budget. Include all six original model arms, the penalised Cox
  models, the Piironen–Vehtari variant and all three catalytic variants in both arms.
  Data preparation and its alignment/hash manifest precede all matched fits;
  it does not depend on completed comparator fits.
  Report predictor/event counts, diagnostics, matched effects, uncertainty,
  multiplicity and reproduction checks. Preserve the original full-cohort
  primary analysis separately.
- [ ] T-189 (T; depends T-180 and T-185 prepared data, not completed matched fits) — Implement and run the Cox catalytic prior
  arm (ADR-038). Acceptance:
  - the prior log-density and weighted mixture estimate match the authors'
    reference implementation on a fixed test case;
  - fixed-τ = p and adaptive-τ Bayesian cells, plus weighted-mixture cells,
    exist for the 25 outer folds of each cohort, the RQ2 conditions and the
    T-185 clinical-only and expression settings; Bayesian cells use the unchanged
    diagnostic gate, point-estimate cells use optimizer and prediction checks;
  - rank-rejected synthetic draws remain execution failures before sampling,
    with explicit failure counts and independently reconstructed provenance;
    the frozen generator has no redraw remedy and failed cells are immutable;
  - paired contrasts against the other priors and comparators are recorded.
- [ ] T-186 (T; depends T-181–T-185, T-189) — Render the extension bundle with the
  same verified renderer and lineage rules. Acceptance: every thesis number
  traces to generated evidence, with actual visual QA and separate primary/
  post-hoc lineage. Preserve the negative original explanation finding and
  unavailable original contrasts; no retrospective equivalence claim.

## Hard scope controls

- No unprespecified model family, prior, real dataset or analysis after
  protocol freeze at the end of Week 5, except the post-hoc thesis
  analyses named in ADR-035/ADR-036 and refined by ADR-037–ADR-039, specified in the
  frozen addendum before their own results. Existing ADR-032/ADR-033 evidence
  retains its earlier specification and actual chronology.
- Rotterdam transport and ADEMP simulation are already dropped and cannot be
  reactivated within this study.
- If more than one week behind, drop non-primary SHAP case studies and then
  non-primary sensitivity grid points.
- Never drop provenance, fold-local preprocessing, calibration, full Bayesian
  diagnostics, predictor-timing audit, primary robustness, claim verification
  or clean thesis build.
