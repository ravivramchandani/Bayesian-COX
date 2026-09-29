# Catalytic synthetic-design correction

Status: specified implementation candidate under ADR-040/T-190. Training-only
preflight is authorised. Corrected fitting requires the reviewed complete
input inventory, arithmetic checks and a distinct numerical freeze. No
corrected validation scores, fit-reuse certification or numerical completion
are asserted here.

This is a post-hoc methodological sensitivity proposed after original
synthetic-rank failures were observed. The original specification, sealed
production code, cells, failures and results retain their own lineage. The
original programme continues independently. Overleaf and paper/DOI work
remain outside the current implementation scope.

## Proposed generation rule

The three affected variants are fixed catalytic, adaptive catalytic and the
weighted mixture estimator. Use the original training-only source-variable
generator from production commit `119476f`, including its source order,
whole categorical levels, numeric marginals, derived features, training-fitted
encoder/gene selection, M = max(1000, 4p), scaled reference hazard and joint
covariate/time draw order. Keep every original constructor guard.

Attempt zero uses the original generation seed. After its exact constructor
rank rejection, attempt j uses
`deterministic_seed(original_seed, "rank_conditioned_retry", j)` for
j = 1, ..., 255. Each retry draws the complete original proposal. The cap
is 256 proposals including the first. Accept the first proposal passing the
original constructor. Cap exhaustion is an explicit execution failure.
Neither finite-input, hazard, preprocessing, optimizer nor sampling failures
permit another proposal. No held-out score or sampling outcome selects a
proposal. These settings are recorded before the real preflight and may not
be silently changed within this candidate version.

Keep successful legacy generator metadata unchanged and separate from the
attempt history. A rejected original generator returned no metadata; capture
its actual constructor inputs with explicit instrumentation provenance.
Record proposal seeds, dtype/shape/value hashes, accepted index, source
support, processor state, rank decision and terminal error. Report any actual
retry-seed collisions; do not silently change the seed rule to remove them.

## Scope and input verification

Construct every one of the 825 planned catalytic outer contexts and the 825
WME inner contexts, including ones not reached after original failures.
Each WME inner proposal is shared across the three frozen tau candidates;
there are 2,475 candidate uses, not additional generation contexts. Apply
administrative censoring to outer training outcomes before reconstructing
inner folds. Refit inner preprocessing and gene selection using inner
training alone. Fold planning follows the original source; no later generator
or processor consumes validation rows.

The controller fits the complete original training frame once per context.
An isolated proposal child may restore its complete hash-verified processor
state and receive only the original selected source columns. Restoration must
reproduce the original feature order, processor metadata and proposal arrays
exactly. This reduces transfer of unselected gene columns; it does not change
gene selection, the generator or its constructor guards. State integrity
alone does not prove training provenance; the context witness provides that
binding.

The preflight verifies all original source/data/config/lock and manifest
bindings, reconstructed memberships, real encoded inputs, p/M, times/rate,
processor state and proposal hashes. Compare attempt zero independently
against the original generation recipe and stored evidence where available.
Every scheduled context has an accepted, exhausted or explicit nonrank-input
outcome. An unresolved comparison is not an equivalence witness.

Accepted finite full-rank designs imply the norm-recoverability condition in
Li and Huang's properness results. Fixed positive tau and the original
positive adaptive hyperparameters retain finite-design properness when the
kernel and kappa are correctly evaluated. Conditioning on rank changes the
generator law and couples rows; the original iid stability and asymptotic
claims do not transfer. These are our implications for the proposed finite
designs, rather than a theorem about this retry implementation.
[Li and Huang (2026), Section 5.1, Theorems 1–2](https://academic.oup.com/biometrics/article/82/1/ujag004/8455879).

The ideal independent-proposal calculation gives a rank-conditioned law on
success and exhaustion probability (1-a)^K. It is not a numerical guarantee
for this deterministic finite-seed implementation. Structural dependencies
can make acceptance impossible, and full rank does not guarantee good
conditioning or optimizer/MCMC acceptance. Actual preflight outcomes and
singular-value summaries determine the observed feasibility.

## Reuse and corrected fitting

Reuse an existing success or failure only after independently binding exact
ordered real/synthetic/model/fit/evaluation inputs and unchanged seeds and
configuration. WME additionally requires every inner proposal, candidate
input, tuning rule and selected parameter context. Preserve the original
result and attach a separate reuse witness; do not relabel it as a new fit.
Missing original outcomes wait for their current owner before reuse is
decided. Changed or unproved inputs require a separate corrected fit.

Recheck prior/kernel/kappa and WME arithmetic on changed accepted designs.
Freeze the addendum/config, reviewed implementation, complete input manifest,
reuse/refit inventory and pilot selection before any corrected validation
score. Preserve original model, fit-attempt and evaluation seed derivations.
The original optimizer, prediction and Bayesian diagnostic gates remain in
force. Record new and original failure causes separately.

Choose one changed, fit-ready outer context for each affected
(model, setting, gene-budget) combination as the full-budget pilot. Select
the largest training-design size n_train times p, breaking ties by stable
cell-ID order. This training-input rule profiles both clinical and expression
work where correction is necessary; it never selects by a validation score.
If a combination has no changed fit-ready context, document that fact rather
than inventing a pilot fit.
Use the original four-chain 2,000-tune/2,000-draw sampling budget and all
prescribed remedies for Bayesian pilot fits; WME uses its original complete
inner tuning. Keep every pilot outcome under the frozen specification.

Before the remaining fits launch, review actual pilot timings/resources,
complete input/model/seed lineage, retained attempts and verifier results.
A diagnostic or optimizer failure triggers an explicit review of the
recorded cause and unchanged terminal classification. It is not discarded,
treated as a new tuning criterion or repaired by weakening a gate. Schedule
only the reviewed necessary fits with an explicit resource budget; do not
duplicate original jobs or infer total runtime from the former short profile.

## Reporting and transfer

Refresh affected inference, paired effects, RQ2 anchors, decision curves,
tables and figures with explicit original/corrected/reused lineage. Report
coverage and failures alongside predictive estimates, preserve the negative
original explanation finding and unavailable original contrasts, and make
no retrospective equivalence claim from incomplete evidence.

Require actual visual QA, independent input/metric/diagnostic verification,
corrected reproduction checks, private release and fresh restore/replay.
Existing frozen-version receipts certify their own original scope only.
Ravi's final guide must identify exact versions, reusable evidence, correction
outcomes and any remaining work. No completion flag is set before its actual
supporting evidence exists.
