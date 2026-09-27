# OPEN QUESTIONS

Questions with no obvious defensible answer, where the choice would materially
change the work. Anything with an obvious answer is decided and recorded in
`DECISIONS.md` instead.

There are currently no open questions. Q-001 through Q-006 are answered and
must not be reopened within this study. Dated source, journal-policy and
ranking rechecks are verification tasks, not requests for a new owner
decision.

Format:

```markdown
## Q-NNN — <one-line question>
- Status: OPEN | ANSWERED | OBSOLETE
- Track: OWNER | ENGINEERING
- Blocks: <the single deliverable that cannot be finished without it, or none>
- Context: <what raised it>
- Answer: <when answered>
```

---

## Q-001 — Is the catalytic prior worth a fourth arm?

- Status: ANSWERED
- Track: ENGINEERING
- Blocks: nothing. The three-prior comparison is complete without it.
- Context: A catalytic prior stabilises the partial-likelihood estimator when
  the sample is small relative to the number of covariates. That is a
  different regime from the sparsity-as-explainability question this project
  answers, so it extends the prior sweep rather than belonging in the primary
  comparison. It becomes worth adding only if the small-sample robustness run
  in Phase 3 shows the existing priors degrading, which would give it
  something to be measured against.
- Answer: No within the six-month confirmatory programme. The three existing
  priors answer the frozen questions; adding another arm after results risks
  scope and outcome-driven model selection. A catalytic prior is future work
  under ADR-019.
- Update 2026-09-28: Reopened and superseded by ADR-037. The supervisor
  approved adding the Cox catalytic prior as a labelled post-hoc extension
  arm before any RQ2 robustness result was inspected.

## Q-002 — What institutional ethics/privacy determination applies?

- Status: ANSWERED
- Track: OWNER
- Blocks: none.
- Context: The work is secondary analysis of public, de-identified clinical
  cohorts, but no Unitec exemption, low-risk determination or other written
  institutional decision is present. Engineering and drafting continue under
  ADR-002 while the owner obtains the required determination.
- Answer: On 2026-08-15 the owner confirmed that the ethics, privacy and data-
  use decisions are approved and instructed that they not be reopened. No
  institutional reference number or letter was supplied, so none may be
  invented or reported. The thesis states only the verifiable facts: secondary
  analysis of public de-identified data and owner-confirmed approval.

## Q-003 — Which upstream data may be redistributed in the public archive?

- Status: ANSWERED
- Track: OWNER
- Blocks: none. The conservative no-patient-level-redistribution default is
  binding unless an upstream term is independently verified more precisely.
- Context: The project MIT licence covers software, while scikit-survival data
  notices and the METABRIC study-specific ODbL impose separate attribution and
  redistribution conditions. The current private repository tracks raw and
  processed patient-level files. Code, manifests and access scripts can be
  prepared without waiting.
- Answer: On 2026-08-15 the owner approved the licensing decisions and
  instructed that they not be reopened. Public release must still obey each
  verified upstream term: software remains MIT-licensed; METABRIC database
  material carries ODbL attribution/share-alike; and ambiguous patient-level
  redistribution is handled conservatively through manifests and retrieval
  scripts rather than an invented permission.

## Q-004 — Do the supervisors approve the confirmatory protocol?

- Status: ANSWERED
- Track: OWNER
- Blocks: none. The result-blind rehearsal and content-addressed freeze remain
  engineering gates, not approval questions.
- Context: Prediction times, primary predictors, estimands, multiplicity,
  repeated nested CV and claim rules materially define what the thesis can
  conclude. The draft in `docs/study_protocol.md` requires principal and
  statistical-supervisor approval before headline results are generated.
- Answer: Approved by the owner on 2026-08-15, including the frozen RQs,
  estimands, nested-validation design, primary contrasts, claim rules and
  scope controls. The owner instructed that supervisor-controlled decisions
  not be reopened.

## Q-005 — Which journal format and ranking source control the paper?

- Status: ANSWERED
- Track: OWNER
- Blocks: none. Current instructions and ranking facts are rechecked as part
  of manuscript production.
- Context: BMC Medical Research Methodology is the primary scope candidate and
  Computer Methods and Programs in Biomedicine the main alternative. Quartile
  depends on database, category and year and can change. The supervisors must
  select the target and the institution's accepted ranking source; writing to
  a neutral IMRaD structure continues.
- Answer: Owner-approved on 2026-08-15: BMC Medical Research Methodology is
  the primary scope target and Computer Methods and Programs in Biomedicine is
  the alternative. Current quartile/category and author instructions are
  independently reverified at manuscript freeze and submission; this is a
  factual check, not a new owner decision.

## Q-006 — Who will review clinical predictor timing and interpretation?

- Status: ANSWERED
- Track: OWNER
- Blocks: none. Unsupported clinical interpretation is excluded.
- Context: Admission/diagnosis-time availability and claims that selected
  variables are established prognostic factors require domain-qualified
  review. Statistical work can use the conservative baseline-only
  specifications while the reviewer is identified.
- Answer: No named clinical reviewer was supplied, and the owner instructed
  that approvals not be requested again on 2026-08-15. Predictor timing is
  therefore verified from authoritative dataset/trial documentation, and the
  manuscript excludes clinical-utility, treatment-effect and causal claims.
  Any interpretation that cannot be supported that way is removed rather than
  presented as externally reviewed.
