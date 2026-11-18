# Independent scientific check of supervisor corrections

Reviewed the private supervisor email against the current source and the saved original results. This check made no thesis-source changes, ran no fitted models and performed no compilation.

## Verified corrections

- Hazard equation3.4 already contained division by Delta t in the pre-correction source; the correct expression is preserved. The signed IBS endpoint is now explicitly typeset in mathematics. The remaining wording uses intervals including zero, rather than claiming they are centred on zero.
- The WHAS500 result now identifies retention of25% of outer-training observations and the change in Normal-minus-Horseshoe IBS relative to full training. It does not turn the0.006323 difference-in-differences into an absolute advantage of that size.
- TableD.1 usesq_k for Horseshoe local scales and lambda_j for baseline interval rates, matching the methods.
- The825 model-condition-fold outcomes and885 underlying fits are distinguished; the five imputation-specific fits must all pass before one ensemble outcome is accepted. The prediction ensemble is not represented as a pooled posterior.
- The descriptive comparison uses the same7/25/23 Horseshoe-accepted fold sets for all six models. Its conditional selection and separation from unavailable complete-fold primary inference are explicit.
- The METABRIC age/NPI PH rejection frequencies are linked to interpretation of the Bayesian constant-effect hazard ratios. Baseline flexibility is correctly separated from time-varying coefficient effects.
- SHAP agreement concerns related summaries of the same linear log-risk model. The uncentred contribution's dependence on category reference coding and the separate102/1640 sampling-check failures are stated.
- AUC horizons, model risk scores, survival-weighted time summary, fold averaging and the explicit Uno tau plus administrative-recensoring rule agree with the implementation.
- Training predictive checks, example calibration bootstrap intervals and grouped calibration curves are now reported. The manuscript distinguishes fitted-survival checking from replicated counts, within-fold parameter bootstrap intervals from between-fold standard deviations, and bin-specific Kaplan-Meier intervals from calibration-parameter intervals.
- The paired-bootstrap interval in WHAS500 Normal-minus-Spike-and-Slab is positive while its corrected primary interval includes zero. The report retains both results and the primary inference/multiplicity rules.
- The requested abstract, sampler-setting, IBS/comparator, irrelevant-student, zero-interval and estimated-reduction wording corrections are present.

## Independent numerical checks

1. Recomputed all18 matched-fold rows directly from the immutable original430-row fold-metric CSV, selecting Horseshoe-complete repeat/fold identities independently. Every mean, sample standard deviation and fold count matches the new CSV. Both IBS/AUC LaTeX columns match the independent computations at their displayed precision.
2. Compared all5 new corrected/bootstrap records directly with the saved original inference.json. Point effects, both interval sets, pair counts, attempted/successful bootstrap counts and resampling descriptions match. The LaTeX table's10^-4 scale, signs and rounding are correct.
3. Read the original Bayesian cell JSONs, selected205 complete outcomes and recalculated interval containment from numerical bounds rather than trusting stored coverage flags. All205 total-count,1230 interval-count and615 fitted-survival comparisons are within their respective stored intervals. All9 cohort/prior aggregate means and maxima agree with the new summary. The mean absolute survival differences range from0.00244518504521201 to0.010726094525086098.
4. Compared all9 first-Normal-fit calibration parameter/interval records and all15 corresponding grouped-curve points directly with original cell JSONs, including bootstrap success counts and bin sample sizes. No mismatch was found. The first-fold middle-horizon slopes round toGBSG2:1.191[0.607,2.338], METABRIC:0.831[0.558,1.110], WHAS500:0.487[0.164,0.923].

## Concrete residual consistency items

The first pass found an active robustness-table footer still calling825 outcomes “conditions”; the root created an annotated presentation copy, preserving the original file. It also found “posterior-finiteness checks” in the conclusion's model-reliability objective row. The final recheck confirms that both this wording and the result-table finiteness wording now describe diagnostic aggregates, matching the method and actual gate. No substantive correction remains outstanding in this review.

Final compilation, visual review and publication remain with the root agent.
