# Thesis architecture and word budget

Current draft: the owner authorised preserving Ravi's complete report in LaTeX
and replacing the Overleaf version on 2026-10-21. All chapters and appendices
now exist with regenerated results and the full clarity/coherence revision.
The current PDF has 147 pages; see
`coordination/reviews/2026-10-21-thesis-conversion.json`. The current structure
retains source appendices A–J and adds reproducibility appendix K. The table
below preserves the earlier planning budget, not a claim about current length.

Earlier planning status: owner-approved under ADR-048 on 2026-10-07.
Principal-supervisor approval was waived for T-108; no supervisor approval is
claimed. This target does not establish an institutional word limit. Overleaf is a separate repository; it was replaced under the later explicit
owner instruction.

## Scope

The thesis reports the ADR-044 submission baseline: the original confirmatory
analysis, frozen robustness and explanation results, with ADR-032 and ADR-033
clearly labelled as post-hoc additions. The unfinished extension, catalytic
correction and ADR-045/T-192 clinical methods study are outside this evidence
freeze. The original diagnostic failures, incomplete primary family and failed
explanation gate stay visible.

## Owner-approved planning structure

| Part | Purpose | Evidence inputs | Proposed target |
| --- | --- | --- | ---: |
| Abstract | State the question, design, strongest supported findings and limits. Avoid a winner claim. | Locked claim ledger and final results chapter. | 250–300 words, separately counted |
| Chapter 1: Introduction | Define the prediction problem, gap, questions, contribution and scope. State that this is retrospective multi-cohort benchmarking, not clinical deployment or external validation. | Frozen protocol; source-bounded cohort descriptions; locked claim ledger. | 2,000 (1,800–2,200) |
| Chapter 2: Literature review | Cover survival prediction, Bayesian coefficient priors, comparator models, calibration and explanation measures; position the contribution without a “first study” claim. | Verified bibliography; protocol and permitted novelty wording. | 6,000 (5,000–7,000) |
| Chapter 3: Methodology | Specify cohorts, eligibility, predictor timing, fold-local preprocessing, models, validation, metrics, diagnostics, inference, robustness, explanation analysis and reproducibility. | Frozen protocol/configuration, data manifest, exact lock, implementation and run manifests. | 5,000 (4,500–5,500) |
| Chapter 4: Results and discussion | Present the frozen results with failures and uncertainty, then answer each research question only at its supported strength. Keep primary, robustness and post-hoc evidence visibly distinct. | Rendered frozen result tables/figures, evidence manifest, claim ledger and review receipts. | 7,000 (6,000–8,000), approximately 4,000 results and 3,000 discussion |
| Chapter 5: Conclusion | Summarise the supported methodological findings, limitations and next research steps without extending to clinical utility or deployment. | Chapter 4 and locked claim ledger. | 1,000 (800–1,200) |
| Appendix A: Reproducibility | Record code, environment, data access, seeds, immutable manifests and reproduction commands. | Frozen environment and release manifests. | Separate from main-text budget |
| Appendix B: Diagnostics | Preserve fit-level and explanation-gate diagnostics and attrition. | Confirmatory, robustness and explanation diagnostic artifacts. | Separate from main-text budget |

The owner-approved main-text planning target is 21,000 words, with a planning range of
18,100–23,900. The abstract and appendices are tracked separately. At the 7 October checkpoint, review estimates were approximately 1,880 words
for the introduction, 6,180 for the literature review and 5,240 for methodology;
results and conclusion were unfinished. Those counts and writing states are
historical. The 21 October revision retains the source topics while consolidating repeated
prose. Its 147-page total includes front matter, tables, figures, appendices and
references; page count is not a main-text word count. Author/supervisor review
should reconcile final length with the institution's actual requirements.

## Owner-adopted planning convention

The planning total counts chapter headings and main-body prose. It excludes
the abstract, front matter, references, tables, figure captions and appendices.
The owner adopts this convention for the project plan under ADR-048. The
repository does not record a programme word limit. Verify any formal handbook
requirement before final submission; this is a later factual check, not part
of the T-108 planning approval.

## Decision record

- Owner: accepted for project planning on 2026-10-07 under ADR-048.
- Principal supervisor: review waived by the owner for T-108; no supervisor
  approval is represented.
- Approved institutional word limit: not recorded; verify before submission.
- Record: coordination/DECISIONS.md, ADR-048.
