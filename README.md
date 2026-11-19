# Bayesian Survival Models for Explainable Prediction of Diseases


## Final thesis report

The standalone 130-page report, **Explainable Bayesian Survival Models**, contains the complete study, its results and 100 scholarly references. The full matched-fold posterior comparisons cover 32 encoded coefficients under three priors. Methods explain the evaluation window and report exact training events per coefficient. All original results and references are preserved.

- [Read the current PDF](https://github.com/ravivramchandani/Bayesian-COX/blob/thesis/final-report-20261117/Main.pdf).
- [Download the current Overleaf source ZIP](reports/thesis_final/Ravi_Thesis_Overleaf_2026-11-19_review_amendments.zip).
- [Ravi's thesis instructions](docs/ravi_thesis_next_steps.md).
- [Verification record](coordination/reviews/2026-11-19-examiner-v3-amendments.json).

The source and saved PDF are published in the [shared Overleaf project](https://www.overleaf.com/project/6af91395a2e68e546f56fbc0) and on the [GitHub thesis branch](https://github.com/ravivramchandani/Bayesian-COX/tree/thesis/final-report-20261117), revision `462e8c6`. The report has 46 tables and seven figures. Its 61-file source ZIP contains only the LaTeX files and figures required to compile the report; an independent build produces an identical PDF. Operational material and authoring metadata remain excluded from the report. Full evidence records remain preserved separately in the repositories.

Code and reproducibility materials for a Master of Applied Technologies
thesis at the School of Computing, Unitec.

The approved study is a three-cohort comparison of coefficient priors in a
Bayesian piecewise-exponential proportional-hazards model. It evaluates
prediction error, discrimination, explicit survival calibration, posterior
quality, design robustness and model-conditional explanation stability. The
frozen confirmatory execution is complete: all 450 planned cells are stored,
430 passed the diagnostic gate and 20 horseshoe cells retain prespecified
`failed_diagnostics` records. Five of nine primary contrasts are estimable,
so the Holm family is incomplete and no complete-family superiority claim is
available. Explanation production completed but failed its convergence
gate, so it permits no explanation-stability claim.

The refactors and complete code/results programme are verified. All 450
reproduction cells match outside recorded timing/hash fields. Robustness
retains 770 diagnostic passes and 55 failures across all 825 cells. The
separate post-hoc sampler sensitivity has 75 diagnostic passes; all nine
contrasts have Holm-adjusted p-values of 1.0 and corrected intervals including
zero. Both final rendered lineages and all 428 PDFs passed verification and
review. Original failed cells and incomplete primary inference are unchanged.

The completed baseline results, exact code, tables, figures and audit records
are in private GitHub Releases and have been downloaded and restored
independently.
ADR-044 makes this verified baseline the submission-scope thesis evidence.
The separate post-hoc extension was interrupted and is being recovered in a
new lineage; its 1,625-fit grid, catalytic correction, rendering, visual
review and remote restoration remain incomplete. This research may continue
in parallel but does not block the baseline thesis or support full-grid
claims yet. Follow [extension execution](docs/extensions_execution.md) and
the current HANDOFF before running anything. The thesis report is complete under ADR-053; paper drafting remains deferred until after thesis submission.

## Start here — Ravi's handoff

Start with [Ravi's thesis next steps](docs/ravi_thesis_next_steps.md) on any laptop.
It explains private access, the thesis evidence limits, and how to get the
reviewed figures and tables without installing the numerical environment.
The [technical handoff](docs/ravi_handoff.md) keeps the optional locked
Apple Silicon verification and the separate unfinished experiment state.

- [Original 450-cell evidence](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/confirmatory-v1-44b6085)
- [Verified code/results programme](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/results-programme-20260927-11f86ce)
- [Full audit evidence and logs](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/results-programme-audit-20260928)
- [Separate focused post-hoc clinical methods evidence](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/clinical-methods-posthoc-20261001-eaebcd7)

A Git clone contains current code, data manifests, plans and guides. Large
results are release assets in the same private repository. Reading the
released reports needs no model fit or specific operating system. Optional
exact restoration verifies hashes and preserves immutable evidence; it does
not fit models. No files from the original laptop are required.

## Models

| Family | Implementation |
| :--- | :--- |
| Cox proportional hazards | lifelines |
| Random survival forest | scikit-survival |
| DeepSurv | pinned pycox `CoxPH` with PyTorch/torchtuples |
| Bayesian PH, weakly informative Normal prior | project PyMC implementation, NUTS |
| Bayesian PH, regularised horseshoe prior | project PyMC implementation, NUTS |
| Bayesian PH, continuous spike-and-slab prior | project PyMC implementation, NUTS |

The Bayesian model uses a piecewise-exponential full likelihood, not the Cox
partial likelihood. Its confirmatory diagnostics cover every sampled
parameter and include prior- and posterior-predictive checks. The continuous
spike-and-slab weight is an inclusion signal, not a discrete posterior
inclusion probability.

The post-hoc extension adds ridge, lasso and elastic-net Cox, a survival-
calibrated horseshoe specification, fixed/adaptive catalytic coefficient
priors and a catalytic weighted-mixture point estimator. The Bayesian
variants retain the PWE likelihood and full diagnostic gate; the weighted
mixture uses weighted Breslow partial likelihood and optimizer checks.
Both matched METABRIC feature settings include all thirteen models. The
settings, gene budget, comparison families and decision-curve rules are in
the [frozen extension addendum](docs/protocol_addendum_extensions.md).

## Cohorts

| Cohort | Subjects | Events | Pinned source |
| :--- | ---: | ---: | :--- |
| GBSG2 | 686 | 299 | scikit-survival v0.24.1 source snapshot |
| WHAS500 | 500 | 215 | scikit-survival v0.24.1 source snapshot |
| METABRIC | 1,980 | 1,144 | cBioPortal DataHub commit `165bd77077b03038f9c2ee104959eb474770b2a9` |

All three contain right-censored time-to-event outcomes. METABRIC is rebuilt
from the pinned patient and sample files; `DECEASED` is the event and the
pinned metadata defines overall survival in months since initial diagnosis.
The earlier 1,904-row Kaggle/cBioPortal-derived file is retained only for
historical pilot provenance. Exact source, eligibility, endpoint, licence and hash
records are in `data/manifest.yaml`.

No fourth real cohort is required. The optional Rotterdam transport analysis
and optional ADEMP simulation were permanently dropped before protocol freeze
to preserve the six-month master's-thesis scope.

## Exact environment

The official runtime is the content-addressed macOS arm64 conda lock, not an
arbitrary environment with the same name. The lock SHA-256 is:

```text
1921895d4a404fc99e848d69ccd4a3f6639a3d1610315c82ecd463ed4bcdfb57
```

Install and verify it with conda-lock:

```bash
conda-lock install -n bayes-cox-clean conda-lock.yml
conda run -n bayes-cox-clean python scripts/verify_environment.py
conda run -n bayes-cox-clean python -m pytest -q
conda run -n bayes-cox-clean python -m ruff check --no-cache .
```

The independently verified local environment is
`bayes-cox-lock-verify-20260815-b`. The older `bayes-cox` environment is not
lock-equivalent because its PyTorch provenance differs. See
`docs/environment_lock.md` for the clean-build procedure and platform limits.

## Confirmatory workflow

The completed analysis was deliberately gated. Rehearsal output is labelled
`rehearsal_only` and is not scientific evidence. The write-once freeze records
five repeats and 80 content-addressed inputs. The current production evidence
must be restored from the Release above. The authorised reproduction writes
verification-only refits to a separate directory and preserves that evidence.

```bash
# Correct continuation path for this checkpoint:
conda run -n bayes-cox-clean python scripts/restore_confirmatory_release.py
```

The restore helper verifies historical code against checkpoint `44b6085`
under ADR-030, so refactoring does not invalidate preserved evidence. It still
rejects changes to the live study inputs. Frozen robustness production
completed in its unchanged worktree; refactored-code reproduction completed
in a separate output directory.

Completed confirmatory resume is now read-only verification and accepts the
refactored code when historical evidence and live study inputs are intact.
New confirmatory execution remains closed. Production execution refuses
methodological overrides and hash mismatches.
Each cell is checkpointed with data, dependency, configuration, code, seed,
runtime, diagnostic and prediction lineage. Figures and tables are rendered
from frozen artefacts without refitting. Current manuscript instructions are in ADR-053 and `docs/ravi_thesis_next_steps.md`.

## Refactor verification and separate sampler sensitivity

`scripts/complete_results_programme.py` completed the sealed programme from
commit `11f86ced8735b32767debb58f3cbbefbb5a7b8e6`: 450 reproduction cells,
frozen 825-cell robustness verification, the separate 75-cell sampler
sensitivity and both rendered bundles. All numerical stages and the
coordinator exited successfully. No restart is needed. Restore the released
evidence through Ravi's guide instead of using historical host PIDs.

The full regeneration is verification-only. The sampler sensitivity refits
all 75 horseshoe cells under ADR-032, changing only target acceptance to
0.999 on every original attempt. Its labels, folds, seeds, diagnostic gate
and separate nine-contrast inference are verified independently. It cannot
replace the 20 confirmatory failures or complete the confirmatory Holm family.

`render_horseshoe_sensitivity.py` requires `--run-dir`, `--source-dir` and a
new `--output-dir`; it creates a separately labelled post-hoc bundle. The
confirmatory renderer retains all nine primary contrasts and shows unavailable
estimates explicitly. Its ADR-033 bound is a labelled mathematical consequence
of the observed five p-values, without supplying the four missing tests.

## Private evidence packaging and restoration

The generated bundles passed final visual QA. A `release_ready` seal
records the verified analysis report, actual QA report, sealed code commit
and exact inventories of the seven evidence directories. Analysis verification
alone cannot satisfy this gate.

```bash
python scripts/package_programme_release.py \
  --seal ~/bayes-cox-runs/results-programme/programme_release_ready.json \
  --project-root ~/bayes-cox-runs/refactored-programme \
  --output-dir ~/bayes-cox-runs/programme-release
python scripts/restore_programme_release.py \
  --release-dir ~/bayes-cox-runs/programme-release \
  --original-run ~/bayes-cox-runs/frozen/reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651
```

Packaging creates five deterministic archives: committed code, full
reproduction, robustness, confirmatory reports with the explanation artifact,
and separate post-hoc sampler evidence. The original 450-cell release remains
unchanged and is referenced by its hashes. Metadata and `SHA256SUMS` accompany
the archives. Existing destinations are verified rather than overwritten.
These archives are private evidence; the public redistribution rules remain
those recorded in `OPEN_QUESTIONS.md`.

Restoration verifies every archive, inventory and reference by default.
Add `--output-dir <new-directory>` to restore into a fresh directory; the
original run must already be restored at `--original-run`. Extraction rejects
links, unsafe paths, duplicate entries and colliding destinations, and never
overwrites existing files.

## Current evidence boundary

- Data rebuilding, feature specifications, fold-local preprocessing,
  repeated folds, metrics, calibration, paired inference, DeepSurv, Bayesian
  checks, exact explanation analysis, robustness runners and immutable result
  schemas are implemented and tested.
- The final result-blind rehearsal completed 18 of 18 cells. The deterministic
  runtime gate retained five repeats, and the write-once protocol freeze has
  SHA-256
  `3b5e1042d592ebb6fade0a4a76c1f0d31ce9c0c1cfc08357be46f163f037d2ca`.
- The frozen production run stored all 450 planned cells: 430 complete and 20
  rejected by the prespecified diagnostic gate. Every rejected cell is a
  horseshoe fit and remains excluded from metrics and inference.
- `inference.json` is explicitly incomplete. Five of nine primary contrasts
  have all 25 paired folds; the four GBSG2/METABRIC horseshoe contrasts have
  no confirmatory inference. The Holm family is therefore incomplete.
- Robustness production, aggregation and review completed: 825 cells, 770
  diagnostic passes and 55 failures. Direct effects have 121/129 estimates
  and 95/129 fully paired rows; difference-in-differences has 45 estimates
  and 33 fully paired rows. Partial and unavailable estimates stay explicit.
  Confirmatory explanation production stored 1,845 comparisons, but 102 of 1,640 evaluable convergence comparisons
  failed, so no RQ3 claim is permitted. Code/results claim review is complete;
  the completed thesis wording is recorded under ADR-053.
  No complete-family superiority or equivalence claim is accepted. ADR-033
  permits a separately labelled post-hoc bound on the incomplete Holm family.

The observed findings and permitted interpretations are recorded in
[current_evidence_status.md](docs/current_evidence_status.md). The frozen
claim rules remain in `docs/claim_evidence_register.md`; the live execution
state is in `coordination/TODO.md` and `coordination/HANDOFF.md`. Completed
engineering gates are recorded in
[the integrated verification report](coordination/reviews/2026-09-27-integrated-code-verification.md).

## Layout

```text
config/         approved design, dataset and model specifications
coordination/   decisions, invariants, protocol, tasks and handoff state
data/           pinned-source manifests plus local raw/processed data
docs/           study protocol, resource ledger and evidence rules
scripts/        rehearsal, freeze, confirmatory, robustness and render entry points
src/            data, models, evaluation, explainability and statistics
tests/          reference, leakage, lineage, schema and reproducibility tests
reports/        exploratory artefacts and content-addressed run directories
```

New to the code? Start with [docs/code_guide.md](docs/code_guide.md), a guided tour
from raw data to stored results.

The thesis source is in the adjacent `thesis-overleaf` repository. Compile it
with `make thesis` and audit internal project identifiers with `make jargon`.
