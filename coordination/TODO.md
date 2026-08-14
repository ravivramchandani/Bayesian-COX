# TODO

Live task register for the 26-week thesis and paper programme, 2026-08-17 to
2027-02-14. Completed tasks are checked and later pruned; durable findings
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
  indication, limits, fees, open-science and AI-disclosure policies recorded;
  Q-005 answers the owner decision. The applicable institution-accepted
  ranking source and official author facts remain subject to T-172 factual
  re-verification, not a new owner decision.
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
- [x] T-109 (T, W1–5, owners R/IR; depends T-106) — Rebuild the bibliography
  from publisher/Crossref/authoritative records. Acceptance: every retained
  source has complete metadata and the best stable identifier for its source
  type; no missing, malformed or unused keys. Evidence: 36 retained entries,
  all cited; 30 DOI records and six authoritative web records verified.

## Weeks 2–4 — Data and predictor integrity

- [x] T-110 (T, W2–3, owner R; depends T-103) — Add a machine-readable source
  manifest. Acceptance: immutable URL/release/commit, retrieval date, DOI,
  licence, upstream/derived SHA-256, eligibility rule and endpoint coding for
  all three cohorts.
- [x] T-111 (T, W2–3, owner R; depends T-110) — Rebuild METABRIC from the
  pinned cBioPortal DataHub patient/sample snapshot. Acceptance: exact tests
  establish 1,980 positive-time records and 1,144 deaths, schema/value checks
  pass, and all METABRIC pilot results remain clearly separated.
- [x] T-112 (T, W2–3, owners R/SS/IR; depends T-101) — Audit prediction-time
  availability for every predictor. Acceptance: source-variable table and
  owner-approved conservative rule;
  primary WHAS500 excludes `los`; primary METABRIC excludes post-diagnosis
  treatment/surgery variables unless timing is defensible. No clinical-reviewer
  signature is invented; authoritative source evidence and conservative
  exclusions implement the owner-approved response in Q-006.
- [x] T-113 (T, W3–4, owner R; depends T-112) — Freeze primary and sensitivity
  feature sets. Acceptance: NPI/component redundancy, raw/log duplicates,
  interactions, categorical groups and feature degrees of freedom are
  prespecified and unit-tested.
- [x] T-114 (T, W3–4, owners R/SS; depends T-111/T-113) — Produce missingness
  and inclusion-flow specifications. Acceptance: fold-local primary handling
  plus multiple-imputation/core-feature sensitivity is prespecified; no claim of
  propagated imputation uncertainty unless implemented.
- [x] T-115 (P, decision W4, owners R/PS/SS/DO; depends T-101–T-114) — Decide
  the optional Rotterdam-to-GBSG2 locked transport evaluation. Acceptance:
  permanently dropped before freeze under ADR-025; no acquisition or
  harmonisation is authorised within this study.
- [x] T-116 (T, W2–4, owner R; no dependency) — Remove or repair duplicate
  cohort-loader schemas that disagree with the active pipeline. Acceptance:
  one authoritative loader/schema path per cohort and full data tests pass.

## Weeks 3–6 — Confirmatory infrastructure

- [x] T-120 (T, W3–5, owner R; depends T-113/T-114) — Build fold-local nested
  preprocessing. Acceptance: imputation, encoding, scaling, transformations,
  feature selection and horizon choice fit within each outer-training fold;
  leakage tests fail if validation data change a transformer.
- [x] T-121 (T, W3–5, owner R; depends T-104/T-120) — Implement the repeated
  five-by-five outer-CV and three-fold inner-CV design. Acceptance: event/time
  stratification, seeds and subject/fold IDs are deterministic and identical
  across paired models.
- [x] T-122 (T, W3–5, owner R; depends T-104/T-120) — Correct the evaluation
  layer. Acceptance: training-only horizons, IPCW IBS, Uno C, Harrell C and
  cumulative/dynamic AUC match reference implementations; unsupported
  horizons fail explicitly.
- [x] T-123 (T, W3–5, owners R/SS; depends T-122) — Wire survival calibration.
  Acceptance: calibration curves, intercept/calibration-in-the-large and slope
  with uncertainty at frozen horizons are generated and tested; IBS is no
  longer labelled calibration.
- [x] T-124 (T, W4–6, owners R/SS; depends T-104/T-121) — Implement valid
  paired inference. Acceptance: per-fold effects, Nadeau–Bengio corrected
  intervals/tests, Holm adjustment and event-stratified paired-bootstrap
  sensitivity pass simulation/reference tests; the constant-0.05 stub is
  removed.
- [x] T-125 (T, W3–5, owner R; depends T-121) — Expand the immutable result
  schema. Acceptance: predictions and metrics include subject, repeat/fold,
  dataset/config/code/dependency hashes, hyperparameters, seeds, runtime,
  hardware, commands and diagnostics.
- [x] T-126 (T, W4–6, owner R; depends T-125) — Make figures and reports pure
  renderers. Acceptance: they read frozen artefacts and never refit a model;
  lineage tests map every figure/table to a script and result key. The legacy
  pilot renderer remains explicitly separated from confirmatory targets.
- [x] T-127 (T, W4–6, owner R; depends T-101) — Validate the DeepSurv arm.
  Acceptance: pinned reference/parity implementation, real optimiser/dropout/
  normalisation/early-stopping configuration, compact inner grid, gradient
  and tiny-dataset overfit tests; otherwise a supervisor-approved ADR drops
  the comparator before protocol freeze.
- [x] T-128 (T, W4–6, owner R; depends T-101) — Complete Bayesian validation.
  Acceptance: time-scale/baseline-prior rule, prior predictive checks,
  posterior predictive checks and R-hat/ESS/MCSE/divergence/BFMI/tree-depth
  diagnostics for all parameters are tested and recorded.
- [x] T-129 (T, W3–6, owner R; no dependency) — Create an exact environment
  lock and clean-build workflow. Acceptance: a fresh environment installs
  pinned dependencies, all tests/lint pass, and the lock hash enters results.
  Evidence: 259 packages verified, 150 tests passed, Ruff clean; lock SHA-256
  `1921895d4a404fc99e848d69ccd4a3f6639a3d1610315c82ecd463ed4bcdfb57`.

## Weeks 7–12 — Protocol freeze and confirmatory evidence

- [x] T-130 (T, W7–8, owners R/SS; depends T-120–T-129) — Rehearse one outer
  fold per cohort/model without inspecting comparative effects. Acceptance:
  resource estimate, schema, diagnostics, calibration and failure handling
  pass; repeat count is fixed by the result-blind 72-hour compute rule.
  Evidence: the final-input rehearsal completed 18/18 cells and retained five
  repeats without comparative-effect inspection.
- [x] T-131 (T, end W8, owners R/PS/SS; depends T-130) — Freeze and tag the
  protocol, environment, data manifest, feature specifications, grids, seeds
  and analysis code. Acceptance: no methodological tuning after the tag.
  Evidence: write-once `config/protocol_freeze.json`; its content hash is the
  immutable analysis tag (no Git tag is claimed), with 80 verified input hashes
  and freeze content SHA-256
  `3b5e1042d592ebb6fade0a4a76c1f0d31ce9c0c1cfc08357be46f163f037d2ca`.
- [ ] T-132 (T, W9–11, owner R; depends T-131) — Run confirmatory GBSG2,
  WHAS500 and METABRIC repeated nested CV. Acceptance: all planned cells and
  out-of-fold predictions exist or a prespecified failed-cell record explains
  the failure; rerun checksums match. Checkpoint 2026-08-15: the frozen run is
  active; all GBSG2 and WHAS500 cells are stored and METABRIC is in progress.
  The full 450-cell completion and aggregate inference gates are not yet met.
- [ ] T-133 (T, W9–11, owner R; depends T-132 progressively) — Triage MCMC and
  neural failures using only frozen remedies. Acceptance: no interpreted fit
  breaches the diagnostic gate and all interventions are logged.
- [ ] T-134 (T, W11–12, owners R/SS; depends T-132) — Produce the RQ1 primary
  and secondary estimates. Acceptance: paired effects, corrected 95%
  intervals, adjusted primary tests, calibration and compute costs trace to
  immutable results; all null/negative findings are retained.
- [ ] T-135 (T, W11–12, owners R/PS/SS; depends T-134) — Complete the primary
  claim review. Acceptance: RQ1 wording is approved, unsupported superiority,
  equivalence and calibration claims are absent, and the results chapter
  skeleton is populated from generated tables.

## Weeks 11–16 — Robustness and explanation

Owner checkpoint 2026-08-15: T-140 through T-144 are deliberately paused
until T-132 is complete, verified and committed. Do not start these production
stages without a new owner instruction.

- [ ] T-140 (T, W11–13, owners R/SS; depends T-131) — Run the frozen prior
  hyperparameter and baseline-interval sensitivity. Acceptance: performance,
  uncertainty and diagnostics are compared without selecting a favourable
  configuration post hoc. Runner/schema/tests are complete; production
  artefacts are absent.
- [ ] T-141 (T, W12–14, owners R/SS; depends T-132) — Run RQ2 sample-size and
  administrative-censoring analyses. Acceptance: identical subsamples across
  priors, difference-in-differences estimates and uncertainty answer H2.
  Runner/schema/tests are complete; production artefacts are absent.
- [ ] T-142 (T, W12–14, owners R/SS; depends T-132) — Run feature-timing and
  missing-data sensitivities. Acceptance: WHAS500 with/without `los`,
  METABRIC baseline/treatment-augmented, NPI/components and missingness
  analyses all trace to frozen specifications. The five-imputation fold-local
  sensitivity is implemented; no robustness result exists yet.
- [ ] T-143 (T, W12–14, owners R/SS; depends T-132) — Check proportional-
  hazards assumptions and the frozen response. Acceptance: global/covariate
  tests and within-fit multiplicity control are reported; supported violations
  become limitations. No time interaction or time-varying coefficient is
  fitted or introduced in response to the assessment, and no silent model
  change is permitted.
  Aggregation and Holm logic are implemented; production assessment is absent.
- [ ] T-144 (T, W13–15, owners R/SS; depends T-132/T-113) — Run the revised
  RQ3 explanation protocol. Acceptance: random paired subjects, training-fold
  backgrounds, same-Bayesian-model SHAP, three-seed convergence, grouped
  features and fold/resample uncertainty are stored. The pure frozen-cell
  analysis is implemented and tested; the production artefact is absent.
- [x] T-145 (P, decision W12; owners R/SS) — Permanently drop the lean ADEMP
  simulation before freeze. Acceptance: ADR-025 records that no simulated
  result enters this study and coefficient-recovery simulation is future work.
- [x] T-146 (P, decision W4; owner R; depends T-115) — Permanently drop the
  Rotterdam-to-GBSG2 transport branch before acquisition or harmonisation.
  Acceptance: ADR-025 records the irreversible six-month scope decision.
- [ ] T-147 (T, W15–16, owners R/PS/SS; depends T-140–T-145) — Freeze all
  thesis evidence. Acceptance: clean rerun manifest, statistical/clinical
  claim approval, immutable result tag and zero unresolved thesis-critical
  row in the claim ledger.

## Weeks 1–22 — Thesis writing and audit

- [ ] T-150 (T, W1–6, owners R/PS; depends T-101/T-109) — Replace the
  oversized literature review with a 5,000–7,000-word critical healthcare
  synthesis. Acceptance: exact gap/RQs follow from reviewed evidence; no
  duplicated textbook, cybersecurity, business or unsupported material. A
  6,281-word focused draft is complete; supervisor text review remains.
- [ ] T-151 (T, W2–4, owners R/PS; depends T-101) — Draft the introduction.
  Acceptance: context, gap, contribution, operational RQs, scope and chapter
  map are substantive and supervisor-approved. A 1,919-word substantive draft
  is complete; supervisor text review remains.
- [ ] T-152 (T, W3–9, owners R/SS; depends progressively T-101–T-131) — Draft
  methodology to match the frozen implementation. Acceptance: cohorts,
  eligibility, missingness, predictors, validation, equations, priors,
  diagnostics, metrics, explainability, ethics and deviations are complete.
  The substantive pre-freeze chapter and diagnostic appendix are complete;
  final frozen repeat/hash details remain dependent on T-131.
- [ ] T-153 (T, W11–16, owners R/SS; depends progressively T-134–T-147) —
  Draft results from generated artefacts. Acceptance: exploratory and
  confirmatory evidence are separated; diagnostics, calibration, negative
  results and sensitivities are included without manual number transcription.
- [ ] T-154 (T, W14–17, owners R/PS/SS; depends T-147) — Draft discussion and
  conclusion. Acceptance: each RQ is answered at its supported strength;
  limitations cover internal evaluation, endpoint heterogeneity, predictor
  timing, missingness, PH, explanation and absence of clinical deployment.
- [ ] T-155 (T, W14–17, owners R/DO; depends T-102/T-103/T-129) — Complete
  reproducibility, ethics and data appendices. Acceptance: exact commands,
  environment/hardware, seeds, manifests, access/licensing, diagnostic
  supplements, data-availability wording and governance statements are present.
  A substantive prospective appendix is complete; production run identifiers
  and evidence remain pending.
- [ ] T-156 (T, W17–18, owners R/PS; depends T-150–T-155) — Write abstract,
  keywords and front matter last. Acceptance: structured abstract agrees
  exactly with frozen results; no template text remains.
- [ ] T-157 (T, end W18, owners PS/SS; depends T-150–T-156) — Full-draft
  gate. Acceptance: every chapter is substantive, all RQs are answered and no
  thesis-critical claim lacks evidence.
- [ ] T-158 (T, W19–20, owners R/PS/SS; depends T-157) — Complete two
  supervisor review cycles. Acceptance: consolidated comments are resolved or
  dispositioned with rationale; holiday weeks are protected from new scope.
- [ ] T-159 (T, W20–22, owners R/IR; depends T-158) — Run independent
  statistical, citation, equation, figure, accessibility, TRIPOD+AI,
  PROBAST+AI and reproducibility audits. Acceptance: checklists are page-
  referenced; clean LaTeX has zero undefined items or material overflow.
- [ ] T-160 (T, end W22, owners R/PS/SS; depends T-159) — Produce the
  examiner-ready thesis. Acceptance: content, statistics, ethics, citations,
  formatting and archive receive final sign-off.
- [ ] T-161 (T, W23, owners R/PS; depends T-160) — Submit the university-
  format thesis/source/evidence archive, leaving Weeks 24–26 as contingency.

## Weeks 14–26 — Paper and release

- [ ] T-170 (P, W14–18, owners R/PS; depends T-135 progressively) — Create
  the target-journal article and supplement architecture from frozen thesis
  evidence. Acceptance: contribution, reporting checklist and figure/table
  budget fit the selected journal with no new primary analysis.
- [ ] T-171 (P, W18–22, owners R/PS/SS; depends T-147/T-170) — Draft the
  manuscript and supplement. Acceptance: every statement uses the frozen
  claim ledger and result artefacts; title/abstract do not overclaim.
- [ ] T-172 (P, W22–24, owners R/PS/SS/IR; depends T-171) — Complete methods,
  domain and language review. Acceptance: a response matrix resolves every
  actionable comment and journal/category quartile is re-verified.
- [ ] T-173 (P, W22–25, owners R/DO; depends T-103/T-129/T-147) — Build the
  permissible publication archive. Acceptance: software, lock, manifests,
  derived outputs and data-access instructions have an archival DOI; upstream
  patient data are included only as allowed by the licence matrix.
- [ ] T-174 (P, W24–26, owners R/PS/SS; depends T-172/T-173) — Complete the
  journal submission package. Acceptance: manuscript, supplement, reporting
  checklist, cover letter, CRediT/COI/funding/AI disclosures and repository
  link are submission-ready.
- [ ] T-175 (T/P, W24–26, owners R/PS; no new scope) — Protected contingency
  for failed reruns, licence decisions, supervisor revisions, university
  corrections or journal formatting only.

## Hard scope controls

- No unprespecified model family, prior, real dataset or analysis after
  protocol freeze at the end of Week 8.
- Rotterdam transport and ADEMP simulation are already dropped and cannot be
  reactivated within this study.
- If more than one week behind, drop non-primary SHAP case studies and then
  non-primary sensitivity grid points.
- Never drop provenance, fold-local preprocessing, calibration, full Bayesian
  diagnostics, predictor-timing audit, primary robustness, claim verification
  or clean thesis build.
