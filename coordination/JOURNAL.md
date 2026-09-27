# JOURNAL

Append-only record of findings and results. Facts and numbers, not process
narration.

---

## 2026-08-14 — Committed results were produced from synthetic data

`scripts/download_datasets.py` fell back to a synthetic generator whenever
scikit-survival failed to import, and the fallback was silent. In that
generator `time` and `cens` are drawn independently of every covariate, so the
data carries no signal by construction.

Confirmed from the scaler parameters in `data/processed/gbsg2/metadata.json`,
which match the generator rather than the real cohort: age 51.29/17.07 against
a real 53.05/10.11, tumour size 63.78/32.41 against 29.33/14.29, and
progesterone receptor standard deviation equal to its mean, the signature of
an exponential draw, against a real 202 versus 110.

Univariate concordance for `pnodes` was 0.645 in the real raw file and 0.499
after preprocessing. Every model sat between 0.427 and 0.576 across all three
cohorts because there was nothing to find. The pipeline crashed on the real
data at `src/data/preprocessing.py:281`, taking the mean of the non-numeric
`tgrade` column, so the real cohorts were never processed.

All figures, result tables and reports produced before this date are void.

## 2026-08-14 — Convergence diagnostics were fixed values

`MCMCDiagnostics.compute_rhat` returned `{"rhat_max": 1.01}` and
`compute_ess` returned `{"ess_bulk_min": 1500.0}` regardless of the fit.
`MCMCSampler.sample` returned `{"status": "ready"}` without sampling. Both
modules were removed and diagnostics are now computed from the trace with
arviz.

## 2026-08-14 — Baselines restored to the published range

After the data path was rebuilt, test-set concordance:

| Cohort | Cox PH | RSF | Previously reported |
|---|---|---|---|
| GBSG2 | 0.702 | 0.689 | 0.482 |
| WHAS500 | 0.722 | 0.743 | 0.469 |
| METABRIC | 0.665 | 0.675 | 0.513 |

Published Cox baselines for these cohorts are near 0.67, 0.75 and 0.63.

## 2026-08-14 — Plain horseshoe funnels under NUTS

The direct non-centred horseshoe produced 208 divergent transitions on GBSG2
across 8000 draws. Replacing it with the regularised horseshoe, where a slab
term bounds the local scales, reduced this to one divergence with R-hat
1.0000 and bulk effective sample size 1155. Concordance was unchanged at
0.702.

## 2026-08-14 — Full benchmark completed on real data

Fifteen model-cohort fits. Test-set concordance:

| Model | GBSG2 | WHAS500 | METABRIC |
|---|---|---|---|
| Cox PH | 0.7021 | 0.7215 | 0.6649 |
| Random survival forest | 0.6865 | 0.7504 | 0.6747 |
| Bayesian Cox, Normal | 0.6995 | 0.7310 | 0.6663 |
| Bayesian Cox, horseshoe | 0.7018 | 0.7454 | 0.6639 |
| Bayesian Cox, spike-and-slab | 0.6943 | 0.7293 | 0.6662 |

Every Bayesian fit converged: R-hat 1.0000 throughout, minimum bulk effective
sample size 1155, and one divergent transition in 8000 draws across the whole
run.

Two observations worth carrying into the analysis. The horseshoe is the
strongest Bayesian arm on the two smaller cohorts and gives the best
calibration on WHAS500 (IBS 0.1313 against 0.1445 for Cox PH), which is what
a shrinkage prior should do when the sample is small relative to the number
of covariates. On METABRIC, the largest cohort, the three priors are
indistinguishable — the likelihood dominates and the prior stops mattering.
That is the Bernstein-von Mises behaviour the panel asked to see addressed,
and it is now something the results demonstrate rather than assert.

Cost scales sharply with the horseshoe: 424 seconds on METABRIC against 88
for the Normal prior, from the smaller step sizes its geometry requires.

## 2026-08-14 — Kernel SHAP sampling capped after checking stability

Kernel SHAP's default coalition count scales with the feature count, which on
METABRIC against a 300-tree forest made the explainability run take hours.
Capping it at 256 coalitions per explained row brings one cohort-model pair to
31 seconds.

The cap was checked rather than assumed: two runs at different seeds on the
METABRIC forest agree at Spearman 0.989 with an identical top-five set, the
fourth and fifth features merely swapping places. That is well inside what a
rank comparison needs, which is all the built-in-versus-post-hoc analysis
uses the SHAP values for.

## 2026-08-14 — Censoring weights require a bounded test horizon

Time-dependent AUC and the integrated Brier score estimate censoring weights
from the training follow-up, so every test event time must fall inside it.
METABRIC and WHAS500 both contain test observations past their training
horizon, which raised rather than returning a value. Test observations beyond
the horizon are now administratively censored at it before the weighted
metrics are computed; concordance still uses the untruncated data. GBSG2 and
WHAS500 results are unchanged by this, since it only affects the case that
previously failed.

## 2026-08-14 — Built-in explainability tracks the model family, not the data

Eighteen comparisons across three cohorts. Spearman correlation between the
posterior ranking and SHAP:

| Cohort | vs Cox PH | vs random survival forest |
|---|---|---|
| GBSG2 | +0.57 to +0.95 | -0.19 to +0.13 |
| WHAS500 | +0.46 to +0.68 | +0.17 to +0.40 |
| METABRIC | +0.90 to +0.92 | +0.39 to +0.52 |

The posterior signal agrees strongly with attribution computed on Cox PH and
much less with attribution computed on the forest. Both the Bayesian model
and Cox PH are linear in the log hazard, so what the agreement measures is
shared model structure rather than a shared reading of the data. Any claim
that a built-in signal and a post-hoc one "agree" therefore has to name which
model the post-hoc signal was computed on.

The horseshoe is the exception worth noting: it is the only prior whose
ranking moves toward the forest on every cohort, which fits a prior that lets
a few coefficients escape shrinkage rather than spreading weight evenly.

The features the sparsity priors retain are the clinically expected ones —
positive lymph nodes on GBSG2, cardiogenic shock and age on WHAS500, age and
nodal status on METABRIC — so the signal is recovering known prognostic
structure rather than arbitrary directions.

## 2026-08-14 — Current benchmark is exploratory, not confirmatory

The benchmark holdout has been inspected and used in model interpretation.
Cross-validation receives a matrix whose imputation, encoding and scaling were
fitted on the full development training split, so each validation fold
informed its preprocessing. Evaluation horizons are selected from test event
times, and the result JSON retains only fold mean/standard deviation rather
than paired fold predictions. `src/statistics/permutation.py` also returns the
constant value `0.05` for every input and is not valid evidence.

The 15 fits and 18 explanation comparisons remain useful pipeline and
hypothesis-generating evidence. They cannot support confirmatory superiority,
equivalence, calibration or multiplicity-controlled claims. ADR-014 defines a
fold-local repeated nested-CV replacement.

## 2026-08-14 — Active METABRIC source omits eligible survival records

The active source is the 1,904-row, 693-column Kaggle version-1 combined
clinical/omics export, SHA-256
`d4802594827667a71a75b5ae5c3cad1eb4346222052fcc792361c64abc7e43bc`.
It produces 1,903 positive-time records and 1,103 deaths. The single excluded
record has zero follow-up, not missing follow-up.

The 2,509-row clinical export stored with the proposal matches the pinned
cBioPortal DataHub patient/sample files on patient IDs, outcome status,
outcome missingness and clinical values. Requiring complete overall-survival
outcomes and positive time produces 1,980 records and 1,144 deaths. The active
pilot therefore omits 77 otherwise eligible records and 41 deaths. ADR-016
requires the pinned cBioPortal source for confirmatory METABRIC.

## 2026-08-14 — Thesis source fails a clean publication build

The Overleaf source fails `latexmk -halt-on-error` at the malformed
Kaplan–Meier equation in `literature_review.tex`. A nonstop diagnostic build
reported hundreds of LaTeX errors and 349 undefined-citation warnings. Static
bibliography inspection found 62 entries, 56 cited keys, missing key `ref8`,
seven unused entries, 38 entries without a stable identifier and malformed
BibTeX entry `ref23`.

The literature review is about 25,700 words, while the introduction,
methodology, results, conclusion, abstract and appendices are template or
effectively empty. Writing and bibliography repair therefore start in Week 1
in parallel with confirmatory engineering.

## 2026-08-15 — Confirmatory cohorts are pinned and rebuilt

The raw confirmatory inputs now reproduce from immutable upstream snapshots:

| Cohort | Records | Events | Derived SHA-256 |
|---|---:|---:|---|
| GBSG2 | 686 | 299 | `2158b777d27ecfb69b187d3cbcad13fd1eb92d626935c528a4465fea6490ae5f` |
| WHAS500 | 500 | 215 | `4bb01775c04eca11d7f06d6e5dfebd0a5cce75aa7e73fe4261732385be106fcc` |
| METABRIC | 1,980 | 1,144 | `731ea80ce0240cb6aa96ffb0f4a3bb379615202966c954512664bef02b29545c` |

GBSG2 and WHAS500 use the pinned scikit-survival v0.24.1 repository
snapshot. METABRIC uses cBioPortal DataHub commit
`165bd77077b03038f9c2ee104959eb474770b2a9`; its patient metadata defines
overall survival in months since initial diagnosis. The 1,904-row Kaggle file
is pilot input only.

## 2026-08-15 — Exact environment and implementation verification pass

The clean environment `bayes-cox-lock-verify-20260815-b` contains all 259
locked package records and matching HDF5 2.1.0 build/runtime libraries. The
lock SHA-256 is
`1921895d4a404fc99e848d69ccd4a3f6639a3d1610315c82ecd463ed4bcdfb57`.
The complete current suite passed 150 tests and Ruff reported no violations in
that environment.

The passing suite covers fold-local preprocessing, paired repeated folds,
reference survival metrics, explicit calibration, corrected paired inference,
DeepSurv, all-parameter Bayesian diagnostics and predictive checks,
content-addressed cell/checkpoint schemas, frozen-cell explanation,
robustness and pure result rendering. A passing implementation test is not a
confirmatory effect estimate.

## 2026-08-15 — Existing rehearsal is not the protocol-freeze rehearsal

The stored result-blind rehearsal contains 18 cells: 14 complete and four
failed. The failed cells are the WHAS500 and METABRIC random-forest and
DeepSurv arms under the earlier IPCW support implementation. Focused post-fix
smoke checks pass, but methodological inputs changed afterward. The stored run
therefore cannot set the repeat count or protocol freeze and supplies no
scientific result. A new exact 18-cell result-blind rehearsal remains required.

## 2026-08-15 — Pilot interpretations are withdrawn from the claim pool

The 2026-08-14 pilot point estimates remain useful engineering evidence, but
their earlier interpretations as Bernstein–von Mises behaviour, expected
small-sample shrinkage benefit or recovery of clinically established features
are not verified findings. The inspected holdout and leakage defects already
recorded above prevent those statements from entering the thesis or paper.
Only a frozen paired analysis and source-backed clinical facts may support
replacement wording.

## 2026-08-15 — Optional transport and simulation are permanently excluded

The retained three-cohort study contains 3,166 subjects and 1,658 events and
already requires 450 primary model-fold cells at five repeats. The lean
robustness plan adds 825 checkpoint cells and 885 Bayesian fits before any
diagnostic refits. Rotterdam transport and the ADEMP simulation were therefore
dropped before protocol freeze to protect the six-month thesis schedule.
Neither branch is needed for a retained claim; the study makes no external-
validation or simulated coefficient-recovery claim.

## 2026-08-15 — Thesis foundation and prospective methods package build cleanly

The prior 25,700-word literature review and broken bibliography were replaced
by a focused 6,281-word review, a 1,919-word introduction and 36 cited
references: 30 with DOI records and six authoritative web records. A
substantive prospective methodology chapter plus
reproducibility/governance and diagnostic appendices now describes the
implemented design without inserting results.

LaTeX/BibTeX produced a 70-page A4 PDF with embedded fonts and no undefined
citations/references, LaTeX warnings, or overfull/underfull boxes. The internal-
identifier audit passed and the methodology/appendix pages were visually
inspected. Results, conclusion and the numerical abstract remain deliberately
unwritten until frozen evidence exists.

## 2026-08-15 — Confirmatory interpretation boundaries are explicit

The primary WHAS500 prediction set contains nine admission-available
predictors and excludes length of stay and the four admission-course
complications `afb`, `sho`, `chf` and `av3`. The published-full representation
is a named sensitivity, not the primary analysis.

Every interpreted confirmatory Bayesian cell must record zero divergent
transitions in addition to passing the R-hat, bulk-ESS, BFMI and tree-depth
gates. The one-divergence regularised-horseshoe fit recorded in the pilot
history remains pilot evidence and does not satisfy this production gate.

Confirmatory RQ3 uses exact no-refit linear SHAP for the frozen Bayesian risk
score and, secondarily, frozen Cox. Forest SHAP and any DeepSurv explanation
are excluded; the earlier forest Kernel-SHAP comparisons remain exploratory.
No empirical result is generalised beyond the evaluated healthcare setting or
presented as cross-domain transport evidence.

## 2026-08-15 — Result-blind predecision rehearsal retains five repeats

The fresh exact-environment rehearsal completed all 18 planned cohort/model
cells. Inspection was restricted to console cell status and elapsed time plus
manifest controls and completion counts; no metric, prediction, calibration,
inference or explanation output was opened. Rounded cell runtimes summed to
196.1 seconds. Even their maximum rounding bound projected the planned five-
repeat workload below 22.81 serial hours, so the deterministic 72-hour rule
requires retaining five repeats. `confirmatory.yaml` now records
`frozen_after_rehearsal`; a fresh final-input rehearsal and the write-once
content freeze remain required before confirmatory evidence is generated.

## 2026-08-15 — Frozen confirmatory run checkpointed without effect inspection

The final-input rehearsal completed all 18 planned cohort/model cells. Only
completion, controls, hashes and runtime were inspected. The deterministic
resource rule retained five repeats. The write-once protocol freeze records 80
inputs, all of which independently rehash correctly, under freeze content
SHA-256
`3b5e1042d592ebb6fade0a4a76c1f0d31ce9c0c1cfc08357be46f163f037d2ca`.

The frozen production run is active. At this checkpoint all 150 GBSG2 cells
and all 150 WHAS500 cells were stored; METABRIC was still running. No completed
aggregate, inference table or final comparative claim exists at this point,
and no partial metric or effect was admitted as evidence. The owner requested
a local checkpoint commit now, followed by completion and verification of this
confirmatory run. Robustness, confirmatory explanation and post-confirmatory
thesis result writing are paused until a later owner instruction.

## 2026-08-15 — Owner compresses delivery programme to 30 November 2026

The owner set 2026-11-30 as the final thesis and paper-package deadline. The
live task register is therefore compressed from 26 weeks to 15 weeks beginning
2026-08-17. Dependencies, acceptance evidence and analytical scope are
unchanged; writing, review and publication preparation overlap more tightly.

The earlier dates inside the write-once frozen protocol and decision history
remain as the administrative schedule recorded at analysis freeze. They are
superseded for current project management by `coordination/TODO.md` and this
entry. Their bytes cannot be changed while the confirmatory run and its
downstream frozen analyses rely on the recorded 80-input hash set.

## 2026-08-15 — Frozen confirmatory execution closes with an incomplete primary family

The production run at
`reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651/` stored the
exact planned grid of 450 cells. The exhaustive frozen-run check accepted the
manifest, completion record, aggregate hashes, all stored-cell hashes, the
complete-cell metric and prediction lineages and the unchanged 80-input
protocol freeze. The completion record contains 430 complete cells and 20
`failed_diagnostics` cells.

All 20 failures are horseshoe fits that exhausted the three prespecified
attempts. Eighteen occur in GBSG2 and two in METABRIC; WHAS500 has no failed
cell. Every non-horseshoe model completed all 25 folds in every cohort. The
failed fits do not enter the aggregate metric table or inferential estimates.

This is a completed frozen execution, not a complete primary inferential
family. The generated `inference.json` reports `status: incomplete` and
`holm_family_complete: false`. Five of the nine primary prior contrasts have
all 25 paired folds. The two GBSG2 and two METABRIC contrasts involving the
horseshoe are recorded as `incomplete_no_confirmatory_inference`; no corrected
effect or test is supplied for them. Consequently, the partial primary family
cannot support a complete-family superiority, equivalence or multiplicity-
controlled claim.

No new sampler remedy, selective rerun or methodological override is permitted
inside this frozen analysis. Robustness, confirmatory explanation, claim
review and post-confirmatory thesis result writing remain paused at the
owner's checkpoint. The live delivery programme still ends on 2026-11-30.

## 2026-09-27 — Commit e824c1b reverted

Commit `e824c1b` (2026-08-31, "Refactor code structure for improved
readability and maintainability") changed 243 files:

- It re-added 124 files removed in `3321115` and returned 46 files to their
  pre-2026-08-14 versions.
- Among those, the three raw cohorts were replaced with the output of the
  former synthetic fallback. For example, GBSG2 row 1 changed from age 70,
  1,814 days to age 22, 98 days. The `pnode` column and missing `tgrade` are
  the fallback's signature.
- `scripts/mock_frozen_data.py` wrote randomly generated cells
  (C-index 0.6 ± 0.1) and predictions into the frozen run directory.
- 37 of the 80 frozen inputs changed, and `src/pipelines/confirmatory.py` no
  longer imported.

Revert `2e55c0b` restored the `4eeb1ac` tree. At the revert, the frozen run
verifies (450 cells, 80 inputs unchanged) and 170 tests pass in the lock
environment.

## 2026-09-27 — External notebook not adopted

A separately developed notebook (`Bayesian_Ravi Ramchandani.ipynb`,
2026-09-26) re-implements the study in 110 code cells.

- Its Phase 2 reads CSV files that are identical to the synthetic files
  above.
- Its Phase 3 acquires the real cohorts, but it evaluates only the first
  outer fold. Its final evaluation covers 7 of 18 model–cohort pairs, using
  metric values carried over from the notebook session. The cell that runs
  the confirmatory sampling was not executed in the saved copy.
- Its seven C-index values fall inside the frozen run's per-fold ranges.

The repository pipeline supersedes it; nothing from it enters the evidence.

## 2026-09-27 — No significant difference detected in five estimable primary contrasts

From `inference.json` of the frozen run (ΔIBS = model A minus model B):

| Cohort | Contrast | ΔIBS | 95% NB interval | p |
|---|---|---:|---|---:|
| GBSG2 | normal − spike-and-slab | +0.00002 | −0.00010, +0.00015 | 0.693 |
| WHAS500 | normal − horseshoe | +0.00034 | −0.00171, +0.00240 | 0.732 |
| WHAS500 | normal − spike-and-slab | +0.00006 | −0.00012, +0.00024 | 0.493 |
| WHAS500 | horseshoe − spike-and-slab | −0.00028 | −0.00217, +0.00161 | 0.760 |
| METABRIC | normal − spike-and-slab | −0.00001 | −0.00009, +0.00007 | 0.833 |

The smallest available p-value, 0.493, exceeds 0.05/5. In Holm's step-down
procedure, an estimable contrast is tested at best at 0.05/5, and only if
all four missing hypotheses were rejected first. So no estimable contrast can
be rejected at family-wise level 0.05, whatever the four missing p-values
are.

Interpretation corrected under ADR-037: these results do not establish
equivalence or absence of a prior effect. Four primary contrasts remain
unavailable; the numerical table and Holm bound above are unchanged.

## 2026-09-27 — Horseshoe failures are rare divergences under a zero-tolerance gate

All 83 failing horseshoe attempts failed on divergent transitions alone:

- GBSG2: 1–11 divergences per 8,000 draws.
- METABRIC: 1–2 per 8,000 draws.
- Every attempt: maximum R-hat 1.00, minimum bulk ESS 1,528, minimum BFMI
  0.72, and no tree-depth limit hits.

The per-attempt probability of zero divergences was 0.10 in GBSG2, 0.58 in
METABRIC and 0.83 in WHAS500. With three independent attempts, these
predict 18.0, 1.9 and 0.1 failed cells; observed: 18, 2 and 0.

The first prespecified remedy changed nothing for the horseshoe, which
already used target acceptance 0.99, and the second re-parameterises only
the baseline hazard.

On the frozen seeds, target acceptance 0.999 cleared 6 of 7 failed GBSG2
cells. Runtime rose 1.2–1.3 times, and posterior means moved by at most 0.07
posterior SD.

The implementation matches Piironen and Vehtari (2017,
doi:10.1214/17-EJS1337SI) Appendix C.1, with half-t(2) local scales and a
fixed τ0 = 0.1. ArviZ 0.23 rounds R-hat to two decimals even with
`round_to=None`, so the R-hat gate fires from a true value of about 1.005.
Evidence: `~/bayes-cox-runs/horseshoe-investigation-20260927/`.

## 2026-09-27 — Confirmatory explanation produced; convergence gate not met

`scripts/run_confirmatory_explainability.py`, run with the frozen code on the
frozen run, wrote
`reports/explainability/confirmatory_v1_confirmatory_cdcdcee84651_explainability_v1.json`
(SHA-256 `120984c7edfac468f471b9f500470623689b2647e4bde56d271cc9623346ecd5`).

- It made 1,845 comparisons from 205 Bayesian cells; the 20 failed
  horseshoe cells were excluded.
- 1,538 of 1,640 evaluable convergence comparisons pass, so the prespecified
  summary is `failed` and no RQ3 claim is permitted.
- Every failure is a Spearman ρ below 0.95; the top-five overlap condition
  never fails.
- Failures concentrate in GBSG2 normal and spike-and-slab: 33 of 150 budget
  comparisons each, median ρ 0.976, minimum 0.738.
- With eight feature groups, three adjacent rank swaps are enough to fall
  below 0.95.

## 2026-09-27 — Frozen robustness production started

Robustness production started with the frozen code at `2e55c0b`, from
`~/bayes-cox-runs/frozen`: 825 cells and 885 Bayesian fits, with a projected
69.6 serial hours against the 72-hour limit.

The cells are fitted by six worker processes that share the plan through
lock files (ADR-031). A sharded cell refitted in a fresh unsharded process
was identical in every field except timings.

## 2026-09-27 — Interrupted work preserved and continuation state audited

The five existing main commits through `6c037a8` were pushed. Thirteen
unfinished source files were committed and pushed on three WIP branches:
models `6b41431`, confirmatory `d6bd723`, and explanation `089efc1`. None is
integrated or has passed its frozen-output equivalence gate. The rendering
worktree contained no changes. The external harness, initial horseshoe
investigation and baseline reproduction report were archived with per-file
hashes under `coordination/recovery/`.

Main passed environment verification, 170 tests, Ruff and coordination
schemas. The model worktree passed 44 focused tests; all 13 unfinished files
passed syntax and lint checks. All 450 frozen cell hashes and three aggregate
hashes match their completion record. At 12:23:48 Auckland, robustness had
75/825 recorded cells and six live workers. Explanation production's failed
convergence gate was confirmed. The full 75-cell ADR-032 sensitivity and
checkpoint-bound verification remain unimplemented.

README, TODO and HANDOFF were reconciled with these facts. The separate
Overleaf repository is clean and matches its remote at `a5f026a`; no thesis
file was changed. Details and the remaining sequence are in
`coordination/reviews/2026-09-27-recovery-audit.md`.

## 2026-09-27 — Checkpoint restoration and separate sampler runner implemented

`src/utils/frozen_evidence.py` verifies the original Git blobs and unchanged
live protocol, raw data, manifest and lock files under ADR-030. The release
restorer accepted the existing 450-cell run from current main: all 80 input
blobs match the checkpoint and live study inputs are unchanged. The focused
verification/restoration tests passed 27 cases.

The ADR-032 runner changes only target acceptance to 0.999 on every horseshoe
attempt, preserves the original remedy ladder and seeds, and writes all
75 refits and their inference to a separate, explicitly post-hoc directory.
Six tests checked the acceptance-only change, remedy order and resume labels
and hashes. Production execution awaits integration of the refactored code.

The main test suite passed 190 tests. Rendering extraction and its full
old/new-output comparison remain in progress, as do the three parallel
refactor gates and frozen robustness production. The owner selected
completion of the code and results programme; Overleaf edits remain excluded.

## 2026-09-27 — Integrated models, explanation, aggregation and rendering gates

The model refactor reproduced all six reference cells exactly after excluding
only timing fields and their containing hash. The horseshoe cell retained
its three failed attempts and `failed_diagnostics` status. Frozen explanation
reproduction retained SHA-256 `120984c7edfac468f471b9f500470623689b2647e4bde56d271cc9623346ecd5`.
Rebuilding all 450 stored cells' three aggregate files reproduced every byte.
The confirmatory package's additional cell gates remain in progress.

Completed confirmatory resume verified the actual 450-cell run read-only
after extraction. The separate full-refit driver now records source identity,
supports verified checkpoint reuse, and rejects writes inside frozen evidence.
Ten focused tests cover closed resume and refit checkpoint integrity.

The original and extracted renderers produced 881 and 886 files respectively:
874 identical, seven documented intentional changes, five additions and no
missing output. The comparison inventory and report are committed under
`coordination/recovery/` and `coordination/reviews/`. Representative PDFs
passed Poppler visual inspection; fonts are embedded.

The separate sampler sensitivity now has exhaustive 75-cell lineage and
nine-contrast verification, read-only completed resume and a pure post-hoc
renderer. Fifteen sampler/evidence tests passed, including rehashed corruption
and interrupted aggregate finalisation. These checks validate implementation;
75-cell production has not yet started. Main passed 217 tests and Ruff.

ADR-034 records retirement of the pilot execution lane, preservation of its
historical data/results/source history and migration of tests to active
fold-local cohort inputs. Implementation and robustness gates remain open.

## 2026-09-27 — Modular engineering gates complete; final production programme prepared

The modular models, confirmatory, explanation, robustness and rendering
implementations are integrated. Their required equivalence gates passed:

- All six model reference refits matched every field except wall-clock
  timings and their containing hash; the horseshoe retained all three failed
  attempts and its original `failed_diagnostics` outcome.
- Explanation reproduced SHA-256
  `120984c7edfac468f471b9f500470623689b2647e4bde56d271cc9623346ecd5`.
  The 102 failed comparisons among 1,640 evaluable convergence comparisons
  remain; no RQ3 stability claim is permitted.
- Rebuilding aggregates from all 450 stored confirmatory cells reproduced
  all three files byte for byte. The six-cell quick selection and four
  specified additional confirmatory refits also matched exactly.
- Three stored robustness cells covering Normal, spike-and-slab and
  horseshoe priors reproduced every non-timing field. The robustness package
  passed 196 tests, Ruff and coordination schemas before integration.
- The rendering gate retained 874 identical files, seven intentional
  changes, five additions and no missing output. Representative PDFs passed
  visual inspection; final bundles incorporating completed robustness are
  still pending.

The integrated `make all` check passed 241 tests, exact environment
verification, Ruff and coordination schemas. Subsequent focused checks passed
three supplemental tests; the final release checkpoint still requires the
complete suite after packaging integration. Gate evidence and local artifact
locations are recorded in
`coordination/reviews/2026-09-27-integrated-code-verification.md`.

ADR-030 is integrated throughout the active evidence pipeline: historical
source inputs verify at checkpoint `44b6085`, and live protocol, raw data,
manifest and lock files retain their frozen content. New robustness manifests
capture all actual current code and scripts and separate code identities in
run directories. The completed-run verifier reconstructs the exact frozen
825-cell/885-fit plan, checks cell body identities and conditions, raw-data
hashes, permitted statuses, source inputs and every recorded file/content hash.
Rehashed wrong-cell tests reject corruption. Unfinished frozen production
continues only with its original unchanged code and runtime.

ADR-034 pilot retirement is implemented at `3d6da8a`: pilot entry points,
exclusive modules and unused shells are retired, historical data/results
remain in place, source remains in Git history, and active tests use real
raw cohorts with fold-local training preprocessing. The default workflow
verifies the environment, tests and lint.

`scripts/complete_results_programme.py` coordinates the remaining long runs
from a clean detached checkout of the final integrated commit and records
sealed source/code identity. It runs the full 450-cell reproduction with two
workers alongside the six original frozen robustness workers. Existing
supervisor PID 40646 automatically finishes the frozen robustness run and its
aggregates. Once the exact 825-cell completion verifies, the coordinator
queues all 75 ADR-032 post-hoc horseshoe refits with six workers, verifies the
separate inference and renders both final bundles.

At this engineering checkpoint the full 450-cell reproduction and the
75-cell sampler sensitivity have not launched or completed. Frozen robustness
is still running. The modular gates establish implementation equivalence,
not completion of those production tasks. Final rendering, visual QA, claim
review, evidence packaging and final commit/push remain. No Overleaf file
was changed; thesis corrections remain recorded for later chapter work.

The completed integrated checkpoint passed 244 tests in 70.61 seconds,
coordination schemas and Ruff. Release restoration again verified all 450
original cells and 80 frozen inputs unchanged. The current render-bundle
checker accepted all 885 base outputs and their explanation-source lineage.
Seven selected numerical gate reports/logs are preserved in the deterministic
`coordination/recovery/2026-09-27-refactor-gates.tar.gz` with per-file hashes.

## 2026-09-27 — Publication layouts and coordinator recovery

The complete PDF review rasterized and inspected all 426 baseline pages at
150 dpi. All 850 fonts were embedded; page boxes passed. The review found
396 clean pages and 30 layout failures. Its exact per-file hashes and findings
are preserved in `coordination/recovery/2026-09-27-baseline-pdf-qa.json`.
The earlier representative-only inspection is superseded for layout coverage.
Compact metric labels, aligned runtime labels, covariate-proportional PH
panels and higher trace headings correct those defects without changing
numerical results. Corrected overview and METABRIC coefficient-trace previews
passed visual inspection; full replacement rendering/review remain pending.

The programme coordinator now acquires its output lock before reading or
writing the identity manifest. Every long child stage inherits the same
locked descriptor, preventing a restarted coordinator from overlapping a
surviving stage. A real child-process regression verifies that ownership
survives parent-handle closure and releases when the child exits. Duplicate
launches are rejected before manifest access.

Private packaging/restoration is integrated. Packaging requires the actual
final visual-QA-backed release seal and all seven evidence inventories;
five deterministic archives preserve separate evidence scopes and leave the
original 450-cell release unchanged. No final package has been created while
production remains incomplete.

The final execution checkpoint passed all 270 tests in 59.11 seconds,
coordination schemas, Ruff and the exact 259-package runtime verification.
The full check log is preserved in
`coordination/recovery/2026-09-27-final-code-check.log`.

## 2026-09-27 — Sealed full reproduction launched

Coordinator PID 57940 launched the remaining programme from detached commit
`11f86ced8735b32767debb58f3cbbefbb5a7b8e6` in
`~/bayes-cox-runs/refactored-programme-20260927/`. The output manifest in
`~/bayes-cox-runs/continuation-20260927/` records all 90 source/script hashes,
original evidence locations and the exact explanation hash. The locked
runtime and frozen-source preflight passed before the reproduction stage.
Two workers are allocated to the full 450-cell check; the six original
robustness workers continue, with supervisor PID 40646 managing aggregation.
The separate 75-cell sensitivity remains queued after robustness. `caffeinate`
PID 57941 prevents idle sleep while the coordinator is alive. No completion
or release-readiness claim is made at launch.

The first five saved cells (GBSG2 repeat 1, fold 1: normal, spike-and-slab,
Cox, DeepSurv and forest) independently passed their own content hashes and
matched every original non-timing field. The partial check is preserved in
`coordination/recovery/2026-09-27-programme-launch-check.json`; it explicitly
does not certify the full 450-cell reproduction. Both reproduction workers,
all six original robustness workers and their finishing supervisor are alive.

The full replacement render passed source/code/output-lineage verification
for all 885 registered outputs. Its exhaustive old/new comparison retains
36 identical original files and documents 845 intended differences: the
seven initial extraction changes plus 838 presentation fixes. All numerical
tables remain byte-identical apart from the previously documented primary
contrast-table improvements; no original path is missing. The comparison is
preserved in `coordination/recovery/2026-09-27-final-layout-equivalence.json`.

Full replacement visual QA passed all 426 single-page PDFs. The 419 changed
pages were actually reviewed, and seven unchanged overview pages reused exact
passed hashes. All 30 baseline defects are resolved. All fonts are embedded
with Unicode maps, and page boxes pass; conservative font-metric warnings
remain separate from visual defects. The hashed per-file record is preserved
in `coordination/recovery/2026-09-27-final-pdf-qa.json`. This base render does
not include unfinished robustness or post-hoc sampler outputs; their final
bundle still requires actual verification and visual QA.

## 2026-09-27 — Interactive session wrapped; numerical jobs continue

The owner requested a session wrap-up and explicitly chose to leave detached
numerical jobs running. At 03:18 UTC (16:18 Auckland), robustness had 549/825
stored cells: all 255 GBSG2 cells, all 270 WHAS500 cells and 24/300 METABRIC
cells. The full reproduction had 149/450 saved GBSG2 refits with no reported
mismatch. The 75-cell sensitivity remained queued. These counts do not
certify completed production or scientific acceptance.

All eight fitting workers, the finishing supervisor, programme coordinator
and its idle-sleep inhibitor were active. The 90 sealed source/script hashes
still matched `11f86ced8735b32767debb58f3cbbefbb5a7b8e6`. The dated process,
code and progress snapshot is preserved in
`coordination/recovery/2026-09-27-wrapup-checkpoint.json`. Interactive monitoring
was stopped without signalling any numerical process. The final QA,
evidence-summary and progress helpers are preserved in the deterministic
resume-tools archive with per-file hashes. `HANDOFF.md` records the remaining
verification, actual visual review, packaging, restore and private-release
steps. No Overleaf file was changed.

The handoff changes passed all 270 tests in 250.54 seconds while background
fits continued. Coordination schemas and the four-file resume archive's
hashes and deterministic metadata also passed verification.

## 2026-09-27 — Programme resumed after reboot

After the owner requested completion of every remaining code/results task,
execution resumed locally at 07:51:46 UTC (20:51 Auckland). The reboot had
stopped all earlier numerical jobs. The exact Python 3.11.15 environment with
237 conda and 22 pip packages, unchanged frozen checkout and all 90 code hashes
at sealed commit `11f86ced8735b32767debb58f3cbbefbb5a7b8e6` were verified.

The restart preserved and hash-checked earlier logs, recorded and released
only six claims for missing cells, and retained the 551 completed robustness
claims. Six new workers continue the unchanged frozen robustness runner;
supervisor PID 3372 owns its final official resume and aggregation. Coordinator
PID 3374 passed its runtime/source preflight and resumed the existing
154-cell reproduction checkpoint with two workers. Its sensitivity stage
remains queued after robustness. No saved numerical cell or original failure
was changed. The progress-only restart receipt and recovery tools are preserved
under `coordination/recovery/`. Overleaf remains outside this scope.

The restart checkpoint passed all 270 tests in 72.06 seconds and separate
coordination schema validation. Independent verification accepted the
deterministic two-file restart archive and checkpoint hashes.

## 2026-09-27 — Thesis extension plan refined after scientific review

The owner requested updates to the plans and coordination files. ADR-037
refines ADR-036 without changing the four named new analyses: inner-CV
penalised Cox, a precisely specified Piironen–Vehtari variant, survival
decision curves and matched METABRIC clinical/expression comparisons. The
variant is explicitly included in both genomic comparison arms. T-180–T-186
now require matched patients/folds, training-only preprocessing and selection,
survival-scale calibration, censoring-aware decision curves, dependency-aware
uncertainty, multiplicity, diagnostic coverage and separate result lineage.

The addendum must freeze the four new analyses before their own results.
The already computed ADR-033 bound and seven ADR-032 probes retain their
actual chronology; the current 75-cell sampler stage is independent of the
new addendum. Unsupported runtime estimates and the promise that a later
paper needs no further analysis were removed. The original five estimable
contrasts do not establish equivalence, and the failed explanation gate
remains unchanged.

At 10:01 UTC, the existing coordinator and six robustness workers were live,
with 603/825 robustness cells, 205/450 reproduction cells, no reported
reproduction mismatch and 0/75 sampler cells. The four new analyses were
not launched. No frozen evidence, source code or Overleaf file was changed.
Paper drafting, submission and DOI minting remain deferred after the thesis;
the existing private code/evidence release remains part of core close-out.

The five-file planning update passed all 270 tests in 92.22 seconds, separate
coordination schema validation and `git diff --check` in the exact lock
environment while the numerical jobs continued.

## 2026-09-28 — Completed numerical cells verified; final bundle still local

Read-only independent verification accepted all 450 saved reproduced cells
as exact non-timing matches, the completed frozen 825-cell robustness run
and all 75 saved ADR-032 sensitivity cells. All 90 sealed source/script hashes
match `11f86ced8735b32767debb58f3cbbefbb5a7b8e6`. Robustness contains 770
passing cells and 55 diagnostic failures; all 75 sensitivity cells have
passing status. These findings do not alter the original failed cells,
incomplete primary inference family or failed explanation-convergence gate.

The compact, content-hashed checkpoint is
`coordination/recovery/2026-09-28-numerical-checkpoint.json`. It preserves
actual report paths, byte/content hashes, verification counts and the
unfinished sampler inference/completion, rendering, visual QA and release
gates. The main repository was clean and matched its remote before this
status refresh. The existing coordinator remains active; no worker was
restarted. New numerical files are still local, and no supplementary release
has been created. Overleaf remains unchanged.

The checkpoint refresh passed all 270 tests in 55.52 seconds, separate
coordination schema validation and `git diff --check` in the exact runtime.

## 2026-09-28 — Completed programme released and restored from GitHub

The coordinator completed from sealed commit
`11f86ced8735b32767debb58f3cbbefbb5a7b8e6`. Exact reproduction is 450/450;
the completed frozen robustness grid is 825 cells with 770 diagnostic passes
and 55 failures; the separate post-hoc sensitivity has 75/75 passes and all
nine estimable contrasts have Holm-adjusted p-values 1.0 and corrected
intervals including zero. The original failures, incomplete primary family
and failed explanation gate remain unchanged. Coverage and scientific review
retain partial/unavailable robustness estimates and the PH/imputation limits.
Both final lineages and all 428 PDFs/pages passed verification and actual or
exact-hash-reused visual review.

Private releases `results-programme-20260927-11f86ce` and
`results-programme-audit-20260928` contain the completed results/code and full
QA/log/probe support respectively. All ten programme assets, all three audit
assets and every declared member were independently verified after download.
A fresh GitHub clone restored the original source and supplementary programme
into new folders: 455 original source files and 2,498 supplementary archive
members, plus five metadata files. It required no original-host result copy
or new fit. Published asset inventories and both resolved tag commits match
the verified drafts. Repository privacy and the unchanged original release
were checked.

The first packaging attempt rejected the path of an identical explanation
copy before assets were created. A revised seal binds its unchanged original
single-file directory; both seals and the correction history are preserved.
Ravi's guide, README, HANDOFF, TODO, evidence status and dated remote receipts
record restoration and the next extension tasks. New extension fits and
Overleaf editing have not started; paper/DOI work remains deferred.

The final close-out passed all 270 tests in 48.44 seconds, separate
coordination schema validation, Ruff and `git diff --check`. The fresh clone
also passed exact environment verification and Ruff. Compact validation is
in `coordination/recovery/2026-09-28-closeout-validation.json`; the final
Overleaf worktree remained unchanged.

The 20-file close-out support archive under
`coordination/recovery/2026-09-28-closeout-support/` preserves both seal
versions, published-release receipts, environment verification, full final
test output and the close-out helper source, with verified member hashes.

## 2026-09-28 — Extension implementation authorised and reference preparation verified

The owner requested full implementation after reviewing the revised plan.
ADR-039 records methodological corrections, explicit scope and dependencies.
One repository integration owner is implementing separate extension modules.
Executed author and official CRAN R functions produced frozen numerical
fixtures; Python catalytic kernel/kappa/WME checks agree at numerical tolerance.
Pinned measured METABRIC inputs passed hashes and alignment; matched
preparation contains 1,979 patients, 1,143 events and 20,192 Entrez genes after
within-sample median aggregation. No extension outer-validation score has
been computed, and T-180's result-blind freeze remains pending.

The post-hoc addendum and settings were frozen before any new outer-validation
result, content hash `50b5f30f697b633718078e18c0da54be297361f8b06aeaf95af32e12aa1c646f`.
A bounded 512-gene setting uses training-only variance ranking. The 100/100
one-chain training-only compact probes took 22.57 s (P-V), 4.95 s (fixed
catalytic) and 8.51 s (adaptive catalytic), not whole-programme estimates.
The compact likelihood/gradient matches interval expansion. Source audit
identified one biological duplicate pair in the frozen full clinical
METABRIC CSV; the matched cohort contains no overlapping known pair.
External snapshot review found warning-category, lost-attempt and pairing
verification defects. Implementation corrected them before production and
added focused negative tests; the review did not certify revised code.

The implementation was committed and pushed as `93431e4`. Its first sealed
launch check rejected a missing output parent directory before a manifest or
any fit existed. A directory-initialization fix and focused regression test
follow; no frozen settings or scientific results changed. Production will
start from the corrected clean commit, retaining the initial checkout.
