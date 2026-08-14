# OPEN QUESTIONS

Questions with no obvious defensible answer, where the choice would materially
change the work. Anything with an obvious answer is decided and recorded in
`DECISIONS.md` instead.

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

## Q-002 — What institutional ethics/privacy determination applies?

- Status: OPEN
- Track: OWNER
- Blocks: the final ethics statement and thesis submission declaration only.
- Context: The work is secondary analysis of public, de-identified clinical
  cohorts, but no Unitec exemption, low-risk determination or other written
  institutional decision is present. Engineering and drafting continue under
  ADR-002 while the owner obtains the required determination.
- Answer: Pending the institutional data/ethics owner; T-102.

## Q-003 — Which upstream data may be redistributed in the public archive?

- Status: OPEN
- Track: OWNER
- Blocks: public release of patient-level source/derived data only.
- Context: The project MIT licence covers software, while scikit-survival data
  notices and the METABRIC study-specific ODbL impose separate attribution and
  redistribution conditions. The current private repository tracks raw and
  processed patient-level files. Code, manifests and access scripts can be
  prepared without waiting.
- Answer: Pending a dataset-by-dataset release matrix approved by the data
  owner; T-103.

## Q-004 — Do the supervisors approve the confirmatory protocol?

- Status: OPEN
- Track: OWNER
- Blocks: the protocol-freeze tag and confirmatory run only.
- Context: Prediction times, primary predictors, estimands, multiplicity,
  repeated nested CV and claim rules materially define what the thesis can
  conclude. The draft in `docs/study_protocol.md` requires principal and
  statistical-supervisor approval before headline results are generated.
- Answer: Pending the Week 2 scope/statistical-analysis review; T-101/T-104.

## Q-005 — Which journal format and ranking source control the paper?

- Status: OPEN
- Track: OWNER
- Blocks: final journal-specific manuscript formatting only.
- Context: BMC Medical Research Methodology is the primary scope candidate and
  Computer Methods and Programs in Biomedicine the main alternative. Quartile
  depends on database, category and year and can change. The supervisors must
  select the target and the institution's accepted ranking source; writing to
  a neutral IMRaD structure continues.
- Answer: Pending Week 2 and pre-submission verification; T-105/T-172.

## Q-006 — Who will review clinical predictor timing and interpretation?

- Status: OPEN
- Track: OWNER
- Blocks: final clinical-interpretation claims only.
- Context: Admission/diagnosis-time availability and claims that selected
  variables are established prognostic factors require domain-qualified
  review. Statistical work can use the conservative baseline-only
  specifications while the reviewer is identified.
- Answer: Pending a named clinical/domain reviewer; T-112/T-106.
