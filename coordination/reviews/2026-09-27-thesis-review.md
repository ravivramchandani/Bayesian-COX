# Thesis review against the implementation — 2026-09-27

Review of the Overleaf thesis (`../thesis-overleaf`, commit `a5f026a`) against
the code, configuration and frozen run at commit `2e55c0b`. The thesis is not
edited in the current programme; these items are carried in `TODO.md` under
T-152 to T-156.

## Status

| Chapter | Approx. words | State |
|---|---:|---|
| Front matter (`Main.tex`) | 400 | Abstract ends in a placeholder (`Main.tex:78-80`) |
| 1 Introduction | 1,880 | Substantive draft |
| 2 Literature review | 6,180 | Substantive |
| 3 Methodology | 5,240 | Substantive, written in pre-freeze future tense |
| 4 Results and discussion | 0 | Heading only |
| 5 Conclusion | 15 | Template sentence |
| Appendix A Reproducibility | 2,130 | Pre-freeze, with placeholders |
| Appendix B Diagnostics | 1,620 | Pre-freeze |

The thesis has 36 references, no figures and five tables.

The methodology matches the code and configuration on:
- cohort counts and predictors;
- fold design and seeds;
- preprocessing;
- comparator grids;
- likelihood, priors and sampler settings;
- the diagnostic gate and remedies;
- metrics, horizons and calibration;
- inference, robustness scope and explanation settings.

## Corrections

| # | Location | Correction |
|---|---|---|
| 1 | `methodology.tex:23-27` | The freeze exists (`config/protocol_freeze.json`) and the run is complete (430 complete, 20 failed diagnostics). Rewrite in past tense. |
| 2 | `methodology.tex:398, 407-414`; `appendix_reproducibility.tex:187-214` | The repeat count is still conditional. Five repeats were retained (ADR-029). |
| 3 | `appendix_reproducibility.tex:200, 229, 242, 251-254` | Replace the run-directory placeholders with `reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651` and `reports/confirmatory_rehearsal_final_20260815/confirmatory_v1_rehearsal_df0135acdf99`. |
| 4 | `appendix_reproducibility.tex:8-15`; `appendix_diagnostics.tex:14-18` | Still says only development and rehearsal outputs exist. |
| 5 | `appendix_reproducibility.tex:84` | Says 150 tests. The count is 170, and it will change after the refactor. |
| 6 | `appendix_diagnostics.tex:104-110` | The first remedy (target acceptance 0.99) was a no-op for the horseshoe, which already used 0.99. Its recorded attempts are 0.99/2000, 0.99/4000, then 0.99/4000 with a non-centred baseline. The second remedy changes the baseline parameterisation, not the horseshoe scales. |
| 7 | `methodology.tex:390-393, 522-529`; `appendix_diagnostics.tex:118-122` | State three consequences of a failed cell: it stores no predictions; one missing fold removes that contrast's primary and comparator estimates; Holm is computed only when all nine contrasts exist. |
| 8 | `methodology.tex:446-467` | Not mentioned: validation follow-up is censored after the last training horizon for IBS, Uno C and AUC. Harrell C and calibration use observed follow-up. |
| 9 | `methodology.tex:631-637` | The displayed contribution equation is termwise. The confirmatory quantity is grouped, E_s abs(sum over j in g of x_ij beta_j). |
| 10 | `methodology.tex:498-500` | Peak memory was never measured; say so. |
| 11 | `methodology.tex:422-423` | Says the prior hyperparameters were fixed by prior-predictive assessment, but no documented assessment justifies tau0 = 0.1, the slab (4, 2) or the spike and slab scales. Cite one or soften the sentence. |
| 12 | `methodology.tex:551-553, 610-621` | Robustness contrasts use the completed paired folds. Explanation claims need a complete cell inventory, which blocks horseshoe claims in GBSG2 and METABRIC. |
| 13 | `introduction.tex:146-147, 157-158`; `Main.tex:67-68` | "Posterior uncertainty" is named as an outcome but has no estimand. Define a descriptive measure or remove it. |
| 14 | `introduction.tex:191-193`; `Main.tex:71-73` | Proportional hazards is tested and reported, but no alternative specification is fitted, so contrast persistence under PH changes cannot be claimed. |
| 15 | `literature_review.tex:376-378` | Robustness cells store IBS only; no inclusion-stability result exists. |
| 16 | `literature_review.tex:769-770` | There is one nested subset per fold, not multiple subset seeds. |
| 17 | `methodology.tex:285-290` | The last cut point is the maximum scaled time plus one, and the last hazard is extrapolated beyond it. A missing ordinal value is coded -1 before scaling. |
| 18 | `methodology.tex:86-89`; `appendix_reproducibility.tex:68` | Explain that the data come from the scikit-survival 0.24.1 source while the runtime is 0.28.0. |
| 19 | `introduction.tex:196-201`; `methodology.tex:659-697` | The hypotheses are unlabelled in the introduction, but the methodology uses H3a and H3b. Label H1–H3b consistently with `docs/study_protocol.md`. |

## Claims the evidence does not support

- `Main.tex:61-69` and `introduction.tex:152-156, 171-175` imply every prior
  is compared on every cohort. The horseshoe is estimable only in WHAS500.
- The title and abstract promise explanation stability and "when prior choice
  changes" results. RQ2 and RQ3 have not run.
- H3b is likely to be near zero, because the posterior means are close to Cox.
  Discuss its power openly.

## Observed outcome to report

- Five of nine primary contrasts are estimable: all three in WHAS500, and
  normal versus spike-and-slab in GBSG2 and METABRIC. Each has |ΔIBS| ≤ 0.00034
  and p ≥ 0.49. No Holm-adjusted rejection is possible, whatever the four
  missing contrasts are.
- The 20 horseshoe failures come from 1 to 11 divergent transitions each, with
  R-hat near 1.00 and bulk ESS in the thousands. The seven surviving GBSG2
  horseshoe folds are a selected subset, so a complete-case horseshoe
  comparison is not valid.
- Descriptive comparator effects from `inference.json`:
  - Bayesian models versus Cox: |ΔIBS| of about 1e-4.
  - METABRIC Bayesian versus random survival forest: ΔIBS +0.008 (0.0045 to
    0.0114).
  - METABRIC Bayesian versus DeepSurv: ΔIBS +0.0029 (0.0007 to 0.0051).

## Proposal alignment

These proposal deviations are not yet in `docs/proposal_deviations.md` or the
thesis:
- the title change;
- the move from one train/test split to repeated nested cross-validation;
- fold-local imputation instead of dropping rows;
- no feature selection;
- the panel's request for a fair explainability evaluation across all models;
- the prior-information (catalytic prior) direction moving to future work;
- the panel's requested Bayesian Cox literature (Sinha and Dey 1997; Volinsky
  et al. 1997);
- the requested workflow figures.

## LaTeX notes

- `results.tex:2` has the label `chap:resul`.
- `Main.tex:48` uses `\today`.
- `\listoffigures` is empty.
- Chapters are referenced in plain text instead of with `\ref`.
- Notation clashes:
  - lambda is both the baseline hazard and the horseshoe local scale;
  - z_j is both a Bernoulli indicator and a standard normal;
  - tau0 has two meanings;
  - a is both the median event time and the cut points.
- British and American spelling is mixed.

## Compliance points for the owner

- The AI-assistance disclosure was removed in thesis commit `726c10f`. Check
  the institution's current generative-AI policy.
- The title differs from the approved proposal.
- The declaration and acknowledgement pages are missing.
