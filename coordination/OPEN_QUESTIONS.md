# OPEN QUESTIONS

Questions with no obvious defensible answer, where the choice would materially
change the work. Anything with an obvious answer is decided and recorded in
`DECISIONS.md` instead.

Q-001 through Q-008 are answered and retain their recorded answers; Q-001 has
the explicit ADR-038/ADR-039 post-hoc exception. Q-007 records the owner's
ADR-048 override for T-106, T-108 and T-147. Q-008 records the ADR-051 waiver
for T-193/T-194 execution without claiming independent review. Dated source,
journal-policy and ranking rechecks remain verification tasks.
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
- Update 2026-09-28: Reopened and superseded by ADR-038. The supervisor
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


## Q-007 - Who will provide the requested thesis claim and architecture approvals?

- Status: ANSWERED
- Track: OWNER
- Blocks: none. The owner waived reviewer decisions for T-106, T-108 and T-147 under ADR-048.
- Context: The owner requested completion of the evidence lock without waiting for statistical, principal-supervisor or clinical/domain reviewer decisions. No reviewer contacts were recorded, and Q-006 states that no clinical reviewer was named.
- Answer: On 2026-10-07 the owner explicitly directed that the prepared source-bounded claim wording and thesis architecture be locked without reviewer decisions. External reviewer approval is not claimed. ADR-048 records the scope and limits of the override.

## Q-008 — Who will independently accept the RSF surrogate protocol?

- Status: ANSWERED (owner waiver; independent review not obtained)
- Track: OWNER
- Blocks: None for T-193/T-194 execution under ADR-051. T-195 still requires
  independent scientific and claim review before its results can be adopted.
- Context: ADR-049 requires independent scientific acceptance of protocol
  v1.0 before any RSF replay or surrogate fit. No reviewer or acceptance
  receipt is recorded. Engineering, focused tests and no-result preflight
  continue while this item is open.
- Answer: On 2026-10-07, after being informed that independent acceptance was
  still pending, the owner instructed execution and waived that prerequisite
  for T-193/T-194 under ADR-051. No reviewer was identified and independent
  scientific acceptance is not claimed. The frozen protocol methods and
  prediction-replay tolerances remain unchanged; T-195 review remains open.
