# Backward-elimination feature-selection addendum

Version 1.0. This is a separate, post-hoc analysis. It does not alter the
frozen confirmatory or robustness feature sets, saved cells, aggregates, or
claims. No result from this analysis may replace a frozen estimate.

## Analysis

Apply grouped backward elimination to the project's primary baseline clinical
feature set in each of the 75 existing outer-fold identities across GBSG2,
WHAS500, and METABRIC. This is a Cox PH feature-selection comparison, not a
selection step for the Bayesian models or the RSF surrogate study.

The selection unit is the source-feature group declared by the fold
preprocessor. All dummy columns for one categorical source feature are removed
together. Engineered terms follow the preprocessor's declared source grouping.
Columns with no variation in an inner-training fold are omitted for that fit.
At least one feature group remains in every candidate model.

Within each outer-training fold, construct one deterministic, event/time-
stratified three-fold inner partition. At each step, score the models formed by
removing each one remaining feature group. Refit imputation, encoding and
scaling on each inner-training split only. Fit the fixed Cox PH comparator
(`l2_reg=0.0001`) and score mean IPCW integrated Brier score using that split's
training-defined horizons, evaluation grid and censoring distribution. A
candidate is eligible only when it produces a valid score on every inner
fold. Retain every candidate score and failure.

Derive each inner-fold seed as
`deterministic_seed(260817, "backward_elimination", cohort, repeat, fold)`
from the existing outer-fold identity. Do not reuse one inner seed across all
outer cells.

Choose the eligible removal with the lowest mean inner-fold IBS at each step.
Resolve exact ties by the original preprocessor feature-group order. Continue
greedily until one group remains or no candidate removal passes all inner
folds. The resulting nested path is the candidate set; no search over subsets
outside this path is performed.

Select the smallest path model whose mean IBS is no greater than the minimum
path mean plus one fold standard error of the minimum-IBS model. The standard
error is the sample standard deviation of its three inner-fold scores divided
by the square root of three. This one-standard-error rule is only a model
selection heuristic; it is not an inferential interval. Ties among eligible
path models resolve first by fewer groups, then lower mean IBS, then earlier
path position.

After selection, fit the preprocessor and Cox model again on the complete
outer-training fold using only the selected groups. Evaluate once on the
unchanged outer-validation subjects and existing training-defined evaluation
rules. Outer-validation outcomes must not influence elimination, stopping,
selection, or preprocessing.

## Reporting and claims

Record the protocol hash, code hash, source data and fold identities, all
candidate scores/failures, selected groups, selected-feature counts, runtime,
and outer-fold metrics in a new run directory. Report performance beside the
unselected Cox comparator on identical folds. Summarise selection frequency
and overlap across repeats and cohorts. Treat uncertainty and feature
stability descriptively; do not use outer-fold results to revise the method,
claim a causal feature, or claim superiority, equivalence, clinical utility,
or confirmation of any original hypothesis. The selection analysis is
exploratory because it was added after the frozen confirmatory results.

Do not start production until this addendum and its implementation are bound
to a run manifest. Any later methodological change requires a new version and
must preserve this version's records.
