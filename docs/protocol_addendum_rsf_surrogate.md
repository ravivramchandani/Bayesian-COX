# RSF surrogate-tree protocol addendum

Version 1.0 was frozen on 2026-10-07 under ADR-049, before inspecting any
stored RSF prediction values. This is a separate post-hoc study under ADR-047
and does not change the confirmatory record.

## Question and analysis population

For each eligible outer-validation fold, how closely can a shallow regression
tree reproduce the fold-specific random survival forest (RSF) risk scores,
and how does the distilled tree perform against observed survival outcomes?
The analysis uses the existing GBSG2, WHAS500 and METABRIC cohorts and all 25
planned five-repeat, five-fold outer cells per cohort. The planned denominator
is retained. A missing or failed source RSF cell, an unverifiable source, or
a failed replay is recorded with its reason and is not replaced or omitted
from accounting. No cell is selected based on its observed score.

## Teacher, replay and student

The teacher target is the RSF risk score returned by
`RandomSurvivalForestModel.predict_risk`, the sum of the forest's cumulative
hazard estimates at its training event times. Higher values denote higher
risk. Survival-probability curves are not a target in this version.

Replay each source RSF with its recorded fold, preprocessing state, selected
hyperparameters and seed. Verify cohort and row identities, input and source
hashes, feature order and preprocessing-state hash. Before fitting a student,
compare replayed validation risk scores to the immutable source prediction
array using `numpy.allclose(rtol=1e-10, atol=1e-12)` and exact subject order.
A failed comparison blocks use of that cell as a teacher; record the mismatch
and continue accounting for other cells.

The student is `sklearn.tree.DecisionTreeRegressor` with squared-error
criterion, no feature subsampling, and no sample weights. It uses the same
fold-local, encoded feature matrix as the RSF. Fit targets are the replayed
RSF's predictions on the outer-training subjects. Select complexity using
three-fold shuffled `KFold` cross-validation on those outer-training rows
only. The candidate grid is `max_depth` in `{1, 2, 3, 4}` and
`min_samples_leaf` in `{0.05, 0.10, 0.20}` (fractions of each inner-training
fold). Select the lowest mean validation MSE against teacher scores, then
apply the one-standard-error rule: among candidates within one standard error
of the minimum (the sample standard deviation across the three fold MSEs,
divided by `sqrt(3)` for the minimum-MSE candidate), choose the shallower
depth, then the larger minimum-leaf fraction. Refit that setting on all
outer-training rows. Outer-validation features and outcomes are not used for
fitting or selection.

The student uses the RSF's encoded features. Every encoded column is mapped
to its original feature group using the saved fold-preprocessor metadata.
One-hot columns retain their source feature group; engineered columns retain
the source groups declared by the feature specification. Report encoded split
rules with their feature-group mapping and training-fitted scale metadata.

## Measures

Report these measures separately for each eligible outer-validation cell:

- Fidelity: Spearman rank correlation and root mean squared error divided by
  the standard deviation of the teacher risk scores on that validation fold.
- Survival-outcome performance: Harrell's concordance index for the teacher
  and student risk scores on the same validation subjects, plus the paired
  student-minus-teacher difference. Larger risk denotes shorter survival.
- Complexity: selected depth, node count, leaf count, and number of distinct
  original feature groups used in splits.
- Rule and feature stability: per-feature-group proportion of the 25 planned
  trees using that group, split-use counts, and the per-fold text rules.
  These summaries are descriptive; repeated folds are not treated as
  independent replicates for hypothesis tests.

For cohort summaries, within each outer-validation fold convert teacher and
student scores separately to midrank percentiles, then average each subject's
five held-out percentiles across the five repeats. Calculate fidelity and
concordance once per subject from these repeated-fold average percentiles.
Report a 95% percentile interval from 2,000 event-stratified subject bootstrap
resamples of these subject-level averages, using the fixed cohort-specific
seed in the implementation. These intervals describe subject resampling
conditional on the fitted repeated-fold models; they do not quantify
model-refitting or external-population uncertainty. Also report fold-level
distributions and the complete status denominator. Undefined metrics
(including zero-variance scores or no comparable outcome pairs) are retained
with an explicit reason.

## Seeds, failures and claims

Use each source cell's recorded seed for RSF replay. For each cohort in the
fixed order GBSG2, WHAS500, METABRIC, use inner-CV/tree seed
`47047 + 100000 * cohort_index + 1009 * (repeat - 1) + (fold - 1)`. Use
bootstrap seed `147047 + cohort_index`. Record all seeds in each cell.
No stochastic operation may rely on a library default.

Preserve source failures, absent cells, replay mismatches, fit errors and
undefined metrics as distinct statuses. Never fill a missing prediction,
replace a failed source, or make a partial cohort denominator look complete.
Write all protocol, source, code, cell and aggregate artefacts to a new
post-hoc run directory; do not overwrite baseline or prior evidence.

The tree is an approximation of the RSF prediction function. Fidelity is not
survival accuracy, and survival accuracy is not fidelity. The study supports
no causal, biological, clinical-utility, deployment, superiority, equivalence,
independent-validation, or original explanation-stability claim. It does not
revive confirmatory RSF SHAP and does not repair the frozen explanation gate.
Any thesis inclusion remains subject to the thesis claim process.

## Production gate

An independent scientific reviewer must review and accept this frozen
protocol before any RSF replay or surrogate result is generated. Until that
acceptance is recorded, implementation, focused tests and non-result
preflight may proceed; production fitting is held. After acceptance, time one
representative fold per cohort before deciding whether the full 75-cell run
fits the compute allowance. A separate scientific and claim review is
required before T-195 can close.
