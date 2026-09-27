# Current evidence status — 2026-09-28

The protocol and `claim_evidence_register.md` are preserved study-definition
records. This dated status note records subsequent evidence without changing
their claim rules. It does not assert submission review or supervisor sign-off.

| Register item | Verified current evidence | Permitted interpretation |
| --- | --- | --- |
| C-006: runtime and checks | The exact 259-package lock is verified. Current integrated checks are recorded in the code-verification report. | Name the tested code checkpoint, date and checks. |
| C-007: exact regeneration | All 450 saved refits match the original cells outside the recorded timing/hash fields. Exhaustive independent inventory, report, source and sealed-code verification passed. | Exact regeneration is supported for sealed commit `11f86ced8735b32767debb58f3cbbefbb5a7b8e6` in the recorded lock environment. |
| C-008: DeepSurv arm | All 75 original DeepSurv cells have status `complete`. | The frozen arm completed; its comparative findings still require the correct paired inference. |
| C-009/C-010: prediction and calibration | Frozen complete cells contain IPCW IBS, discrimination and explicit calibration outputs. | IBS is prediction error; calibration wording uses the separate slope/intercept/curve outputs. |
| C-011: Bayesian convergence | 205 of 225 original Bayesian cells passed; 20 horseshoe cells failed the frozen diagnostic gate. | An all-fit convergence claim is false. Preserve and report diagnostic attrition. |
| C-012: horseshoe advantage | Five primary prior contrasts are estimable; four horseshoe contrasts are unavailable. No available unadjusted p-value is below 0.49. | Do not infer superiority or equivalence. The confirmatory Holm family remains incomplete. |
| C-016: stable explanations | The original explanation artifact has 1,845 comparisons. Of 1,640 evaluable convergence comparisons, 102 fail the prespecified rule. Global claim permission is false. | Descriptive explanation results may be labelled as such; an explanation-stability claim is not permitted. |
| C-021: robustness | Frozen-code production and aggregates completed. Strict verification accepted 825 cells: 770 pass diagnostics and 55 fail. Coverage and scientific claim review remain pending. | Report the completed grid and attrition; inferential claims require actual comparison coverage and intervals. Completion alone does not establish general robustness. |

ADR-033 allows a separately labelled mathematical bound: none of the five
estimable primary contrasts can be rejected by Holm for any values of the
four missing p-values. This does not produce their estimates or establish
equivalence.

ADR-032 defines a separate 75-cell horseshoe sampler sensitivity. Changing
target acceptance to 0.999 on every original attempt is post-hoc. Its findings
cannot replace the 20 confirmatory failures, complete the original Holm
family or change the explanation artifact's failed gate.

All 75 ADR-032 cells are saved, independently verified and have passing
diagnostic status. Their aggregate inference and completion records were
pending at the dated numerical checkpoint. The final programme record,
rendered lineages, actual visual QA, claim review and private supplementary
release remain outstanding. New results are still local; a pushed code
checkpoint is not a pushed evidence bundle. The dated evidence and report
hashes are in `coordination/recovery/2026-09-28-numerical-checkpoint.json`.

ADR-036/ADR-037 make the four new post-hoc analyses planned thesis evidence:
tuned penalised Cox, a precisely specified Piironen–Vehtari variant, survival
decision curves and matched METABRIC clinical/expression comparisons. They
have not produced results and are not queued by the current core coordinator.
T-180's actual addendum and hash freeze remain pending. It must precede their
own results and preserve the actual earlier ADR-032/ADR-033 chronology.
The new plan does not change any permitted primary or explanation claim.
ADR-038 additionally plans a post-hoc Cox catalytic-prior arm; it has not
started and also requires the new addendum before its own results.

The authoritative production evidence is
`confirmatory_v1_confirmatory_cdcdcee84651`, with completion content hash
`03870efdae3134305794ea977fd9cbe7913c0d693f1b009337546319aa03bee1`.
The original explanation artifact hash is
`120984c7edfac468f471b9f500470623689b2647e4bde56d271cc9623346ecd5`.
Current execution and code checks are in `coordination/HANDOFF.md` and
`coordination/reviews/2026-09-27-integrated-code-verification.md`.
