# Current evidence status — 2026-09-27

The protocol and `claim_evidence_register.md` are preserved study-definition
records. This dated status note records subsequent evidence without changing
their claim rules. It does not assert submission review or supervisor sign-off.

| Register item | Verified current evidence | Permitted interpretation |
| --- | --- | --- |
| C-006: runtime and checks | The exact 259-package lock is verified. Current integrated checks are recorded in the code-verification report. | Name the tested code checkpoint, date and checks. |
| C-007: exact regeneration | All 450 original cells and aggregates verify; limited refit gates reproduce exactly. Full 450-cell regeneration remains pending. | Do not claim full independent regeneration before its exhaustive report passes. |
| C-008: DeepSurv arm | All 75 original DeepSurv cells have status `complete`. | The frozen arm completed; its comparative findings still require the correct paired inference. |
| C-009/C-010: prediction and calibration | Frozen complete cells contain IPCW IBS, discrimination and explicit calibration outputs. | IBS is prediction error; calibration wording uses the separate slope/intercept/curve outputs. |
| C-011: Bayesian convergence | 205 of 225 original Bayesian cells passed; 20 horseshoe cells failed the frozen diagnostic gate. | An all-fit convergence claim is false. Preserve and report diagnostic attrition. |
| C-012: horseshoe advantage | Five primary prior contrasts are estimable; four horseshoe contrasts are unavailable. No available unadjusted p-value is below 0.49. | Do not infer superiority or equivalence. The confirmatory Holm family remains incomplete. |
| C-016: stable explanations | The original explanation artifact has 1,845 comparisons. Of 1,640 evaluable convergence comparisons, 102 fail the prespecified rule. Global claim permission is false. | Descriptive explanation results may be labelled as such; an explanation-stability claim is not permitted. |
| C-021: robustness | Original frozen-code production is active. Its 825-cell completion and inferential artifacts remain pending. | No general robustness conclusion is available from implementation or partial outputs. |

ADR-033 allows a separately labelled mathematical bound: none of the five
estimable primary contrasts can be rejected by Holm for any values of the
four missing p-values. This does not produce their estimates or establish
equivalence.

ADR-032 defines a separate 75-cell horseshoe sampler sensitivity. Changing
target acceptance to 0.999 on every original attempt is post-hoc. Its findings
cannot replace the 20 confirmatory failures, complete the original Holm
family or change the explanation artifact's failed gate.

The authoritative production evidence is
`confirmatory_v1_confirmatory_cdcdcee84651`, with completion content hash
`03870efdae3134305794ea977fd9cbe7913c0d693f1b009337546319aa03bee1`.
The original explanation artifact hash is
`120984c7edfac468f471b9f500470623689b2647e4bde56d271cc9623346ecd5`.
Current execution and code checks are in `coordination/HANDOFF.md` and
`coordination/reviews/2026-09-27-integrated-code-verification.md`.
