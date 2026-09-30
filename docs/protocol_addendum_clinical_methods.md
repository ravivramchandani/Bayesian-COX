# Focused post-hoc clinical methods study

Scope decision: 2026-10-01, after partial extension outcomes and execution
statuses existed. This study is an outcome-aware narrowing of the separate
post-hoc extension, not a new result-blind or externally preregistered
experiment. The 27-member penalised-Cox comparison family itself was fixed
in the 2026-09-28 extension addendum before its outer-validation results.
Neither this scope decision nor its outputs modify that addendum, the
1,625-fit grid, the primary confirmatory record, or their release gates.

## Question and fixed population

Across three distinct clinical survival cohorts, how do tuned ridge, lasso
and elastic-net Cox models compare with the project's Bayesian
piecewise-exponential models under normal, continuous spike-and-slab and
separately labelled ADR-032 regularised-horseshoe priors, considering
out-of-fold prediction, calibration, diagnostic coverage and observed
computational burden? A difference cannot be attributed to the coefficient
prior alone because the Bayesian and penalised models also use different
survival likelihood and baseline-hazard implementations. The cohorts have
different endpoints and are separate internal-validation settings, not
external validations of one transported model.

The fixed roster is `coordination/clinical_methods_roster.json`: all three
original clinical cohorts, all three penalised methods and all five repeats
by five outer folds, or 225 source cells. All outcomes, including failures,
stay in the denominator. References are the same 25 folds per cohort for
the original normal and continuous spike-and-slab models (150 cells) and
the 75-cell ADR-032 post-hoc horseshoe sampler sensitivity. The original
horseshoe record, including 20 diagnostic failures, is reported separately
as reliability context and never replaced in confirmatory inference.
Existing within-Bayesian reduced-information robustness is contextual only:
there are no matched penalised-Cox fits for those conditions. Matched
METABRIC expression, catalytic priors, Piironen–Vehtari variant and decision
curves remain in the original extension programme, outside this study.

## Estimands and claims

The primary estimand for each cohort, penalised method and Bayesian
reference is the mean of 25 patient/fold-paired differences in integrated
Brier score (penalised minus Bayesian); positive favours the Bayesian model.
Use the frozen training-defined evaluation grid and IPCW rules. Require
identical training and validation patient IDs, observed time/event and IBS
grid in every pair. A contrast with fewer than 25 accepted pairs is
unavailable for formal inference; show its coverage and reason. Use the
existing Nadeau–Bengio repeated-CV 95% interval and p-value with 5 repeats,
5 folds and test/train ratio 1/4. The exact 27 contrasts form one Holm family.
Apply Holm only if all 27 contrasts are estimable. A positive comparison
claim additionally requires the corrected interval to exclude zero in the
same direction. No equivalence, global winner, pooled-across-cohort effect
or causal prior-effect claim follows from a non-significant result.

Report per-cell and by-cohort diagnostic/optimizer status, accepted pair
coverage, discrimination, survival calibration at the three stored
training-defined horizons, and observed fit/tuning time as secondary
descriptive evidence. Preserve the models' distinct failure mechanisms;
do not compare accepted-only performance without the attrition denominator.
An integrated Brier score is not, by itself, proof of calibration. Any
unavailable metric, failed diagnostic or unsupported horizon stays explicit.
Do not select a threshold, cohort, model or horizon after seeing held-out
performance. No treatment action or validated risk threshold is specified,
so this focused study makes no decision-curve or clinical-utility claim.

## Source, verification and release

Read only saved cells from the extension run whose `manifest.json` has
SHA-256 `83b9049fb6aaaadab576b34de0741e4f510344dcefba9f96198d15b5ab4f49b9`
and fit commit `119476fef55b1eeb690527f234c1423440720d45`.
The primary and ADR-032 manifests/completions must match the pinned hashes
in `coordination/extension_sources/baseline_sources.json`. Independently
verify all 225 selected cell identities, content hashes, matched raw-data
and fold lineage, predictions and recomputed metrics. Verify original
Bayesian traces/diagnostics with the existing frozen evidence helpers.
Compare all nine saved first-fold penalised refits to their source cells,
including complete non-timing scientific content, and record any missing
receipt as pending rather than silently certifying reproduction. No new
numerical fit is part of this first evidence extraction.

Generate a separate write-once verification report, 27-row comparison
table, coverage/diagnostic and computational summaries, source-hash ledger,
rendered figures/tables and actual layout QA. Preserve source and failed
records unchanged. A private release must include the exact scope, code,
selected cells/reproduction evidence and analysis lineage; a fresh download
and scientific replay on restored evidence is required before calling this
study complete. Transport checks alone do not establish scientific validity.
The thesis uses its already released baseline under ADR-044; this study does
not block thesis submission, authorize Overleaf edits, or start paper
drafting, DOI minting or journal submission.
