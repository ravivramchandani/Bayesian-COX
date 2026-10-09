# Submission evidence lock record

Updated 2026-10-07 under ADR-048. The owner directed completion of T-106,
T-108 and T-147 without reviewer decisions. This record preserves the wording
and evidence limits that were locked. No statistical-supervisor,
principal-supervisor or clinical-reviewer approval is claimed.

## Locked statistical wording

1. "The confirmatory run stored all 450 planned cells. Four hundred and thirty
   cells passed the prespecified diagnostic gate; 20 horseshoe cells failed."
   Source: the completion and run-manifest hashes in the submission evidence
   manifest.
2. "Five of the nine prespecified primary contrasts were estimable from all
   25 paired folds. The confirmatory Holm family is incomplete, so the
   analysis does not establish a full-family superiority or equivalence
   result."
3. "The separately labelled post-hoc Holm bound shows that none of the five
   estimable contrasts could be rejected for any values of the four missing
   p-values. It supplies neither missing estimates nor evidence of
   equivalence."
4. "The robustness grid contains 825 stored cells: 770 passed diagnostics and
   55 failed. Among 129 direct-effect rows, 121 estimates are available, 95
   with full paired coverage, 26 with partial coverage and 8 unavailable.
   All 45 difference-in-differences have estimates, 33 with full and 12 with
   partial coverage. No robustness p-values were calculated or stored."
5. "The separate 75-cell ADR-032 sampler sensitivity passed diagnostics. Its
   nine Holm-adjusted p-values are 1.0 and all corrected intervals include
   zero. This post-hoc sensitivity does not replace the original failures or
   establish equivalence."
6. "The explanation analysis did not pass its global stability gate: 102 of
   1,640 evaluable comparisons failed. No global explanation-stability claim
   is made."
7. "All 450 saved confirmatory refits matched on the recorded scientific
   fields in the reproduction check; timing and content-hash fields were
   excluded from that comparison."

## Locked cohort and clinical boundaries

1. "The study is a retrospective comparison of survival-prediction methods
   in three public cohorts. Each model is fitted within its cohort; no locked
   model is externally validated."
2. "For WHAS500, the primary predictor set is restricted to admission-time
   variables. Length of stay is excluded, and baseline availability of
   selected complications was not verified."
3. "For METABRIC, the endpoint is overall survival in months since initial
   diagnosis under the pinned cBioPortal metadata. Surgery and
   treatment-received variables are excluded from the primary feature set."
4. "For GBSG2, the endpoint is the source dataset's recurrence-free-survival
   event measured in days. The exact clinical time origin is not specified in
   pinned data documentation and is left unstated."
5. "The analysis does not estimate treatment effects or establish causal
   relationships, clinical utility or deployment readiness."
6. No feature is labelled clinical truth or a verified prognostic factor.
   No first-study or priority-of-discovery claim is made.

The cohort statements are limited to data/manifest.yaml, docs/study_protocol.md
and the cited dataset sources. The original failures, incomplete inferential
family, post-hoc status and failed explanation gate remain explicit.

## Owner override record

| Review gate | Disposition | Record |
| --- | --- | --- |
| Statistical wording | External review waived by owner; no statistical-supervisor approval claimed. | ADR-048 |
| Clinical/source wording | External domain review waived by owner; no clinical-reviewer approval claimed. Source-bounded claims remain mandatory. | ADR-048 and Q-006 |
| Thesis architecture and word budget | Owner-approved for project planning; principal-supervisor approval waived for T-108. | ADR-048 and docs/thesis_architecture.md |
| Owner instruction | Complete the evidence lock without reviewer decisions. | ADR-048, dated 2026-10-07 |
