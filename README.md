# Bayesian Survival Models for Explainable Prediction of Diseases

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
available. Robustness production is running in the frozen worktree.
Confirmatory explanation production completed but failed its convergence
gate, so it permits no explanation-stability claim.

The modular refactors are integrated and passed their required output gates:
six model refits, the original explanation SHA-256, all three confirmatory
aggregate files, the six-cell quick selection and four additional confirmatory
cells, three robustness refits, and the exhaustive renderer comparison.
ADR-030 checkpoint verification is integrated throughout the active pipeline;
ADR-034 retired the pilot execution lane while preserving its historical
data, results and source history. The original WIP checkpoints remain on
three `wip/*-20260927` branches. The full 450-cell reproduction is running
from sealed commit `11f86ce`; the separate 75-cell sampler sensitivity is
queued after robustness. Final rendering, visual QA and
evidence packaging remain. Thesis edits are outside this code programme.

## Start here — continue from another machine

Restore the completed confirmatory evidence before downstream work. Its exact
552 MB evidence directory is preserved in the private GitHub Release
[`confirmatory-v1-44b6085`](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/confirmatory-v1-44b6085).
The repository contains a fail-closed restoration helper that downloads both
release assets, verifies SHA-256, rejects unexpected archive paths, validates
all run/cell/aggregate hashes and checks all 80 frozen input blobs against
the release checkpoint. Live protocol, raw data, manifest and lock files must
also remain unchanged.

From the root of a fresh clone:

```bash
# Confirm that GitHub CLI can access the private repository.
gh auth status

# Build the exact macOS arm64 environment.
conda-lock install -n bayes-cox-clean conda-lock.yml

# Download, verify and restore the released evidence.
conda run -n bayes-cox-clean python scripts/restore_confirmatory_release.py
```

A successful restoration ends with:

```text
cells=450 complete=430 failed_diagnostics=20
completion_content_sha256=03870efdae3134305794ea977fd9cbe7913c0d693f1b009337546319aa03bee1
frozen_inputs=80 checkpoint verified; live study inputs unchanged
```

The restored directory is
`reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651/`. The helper
never overwrites an existing directory; when the run is already present it
verifies it in place. After restoration, read `coordination/HANDOFF.md` and
`coordination/TODO.md` for the evidence boundary and next tasks.

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
conda run -n bayes-cox-clean python -m ruff check .
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
rejects changes to the live study inputs. Frozen robustness production remains
in its original unchanged worktree; refactored-code reproduction writes to
separate output directories.

Completed confirmatory resume is now read-only verification and accepts the
refactored code when historical evidence and live study inputs are intact.
New confirmatory execution remains closed. Production execution refuses
methodological overrides and hash mismatches.
Each cell is checkpointed with data, dependency, configuration, code, seed,
runtime, diagnostic and prediction lineage. Figures and tables are rendered
from frozen artefacts without refitting. The current instruction is to complete the code/results programme described
in `coordination/HANDOFF.md` and `coordination/TODO.md`; Overleaf edits are excluded.

## Refactor verification and separate sampler sensitivity

`scripts/complete_results_programme.py` coordinates the remaining work from
a clean detached checkout of the final committed code. It seals the code and
source hashes, verifies reusable checkpoints and writes outside the original
evidence directories. Two workers regenerate all 450 confirmatory cells while
the six original robustness workers continue. Supervisor PID 40646 performs
the frozen run's final unsharded resume and aggregation automatically. Once
robustness is complete and verified, the coordinator starts the separate
75-cell sampler sensitivity with six workers, then verifies and renders both
result bundles. Final visual QA and packaging follow those generated outputs.
One operating-system lock protects the programme output, including surviving
child stages after a coordinator crash. Resume the same sealed checkout and
output directory only after the previous stage processes have finished.

On the original machine, run from that sealed detached checkout:

```bash
python scripts/complete_results_programme.py \
  --source-dir ~/bayes-cox-runs/frozen/reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651 \
  --robustness-dir ~/bayes-cox-runs/frozen/reports/robustness/confirmatory_v1_robustness_robustness_702d93af33bf \
  --explanation ~/bayes-cox-runs/frozen/reports/explainability/confirmatory_v1_confirmatory_cdcdcee84651_explainability_v1.json \
  --output-dir ~/bayes-cox-runs/results-programme \
  --reproduction-workers 2 --sampler-workers 6 \
  --robustness-supervisor-pid 40646
```

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

After the generated bundles pass final visual QA, a `release_ready` seal
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
- Robustness production is running under the frozen code; final aggregation
  and verification remain outstanding. Confirmatory explanation production
  stored 1,845 comparisons, but 102 of 1,640 evaluable convergence comparisons
  failed, so no RQ3 claim is permitted. Primary claim review and thesis writing
  remain unfinished; Overleaf edits are excluded from the current programme.
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

The thesis source is in the adjacent `thesis-overleaf` repository. Compile it
with `make thesis` and audit internal project identifiers with `make jargon`.
