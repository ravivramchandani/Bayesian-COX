# Ravi: thesis files and research handoff

Start with [the final thesis files and upload steps](ravi_thesis_next_steps.md). The finished 100-page report and source are on GitHub branch `thesis/final-report-20261117` at `feae8e2`. The active Overleaf project is [6af91395a2e68e546f56fbc0](https://www.overleaf.com/project/6af91395a2e68e546f56fbc0); its direct Git push was rejected, so the prepared source awaits an editor's upload. Reading or editing the thesis requires only a browser on any operating system.

The technical release and experiment details below are retained for their separate uses.

The baseline code and results programme is complete and remotely verified.
The separate 1,625-cell post-hoc extension and catalytic correction remain
unfinished. Their final results are not yet available as a verified remote release.

ADR-044 sets a submission-first thesis scope: use the verified baseline,
robustness and explanation evidence, plus the separately labelled ADR-032
sampler sensitivity and ADR-033 Holm bound. Report the original diagnostic
failures, incomplete primary contrast family and failed explanation gate.
The unfinished extension may continue as separate post-hoc research but is
not a thesis-submission prerequisite. Do not infer full-grid findings from
its partial results. The owner authorised full Overleaf replacement on 2026-10-21. All chapters
and appendices are now a complete LaTeX draft with regenerated results. Ravi
should review that draft and resolve supervisor feedback; no new model run is
required. The dated conversion receipt is in
`coordination/reviews/2026-10-21-thesis-conversion.json `.

A separate [post-hoc clinical methods study](clinical_methods_results.md)
is now complete and privately released. Its fixed 225 penalised-Cox cells
were independently rescored; all 27 comparisons have 25 matched fold pairs,
but none passes Holm adjustment and none establishes equivalence. The
original horseshoe run retains 20 failed-diagnostic cells, while the separate
ADR-032 sensitivity passed 75/75. Nine saved penalised refits matched their
source records on non-timing scientific content, although all nine earlier
formal receipts remain absent. This focused study does not finish the
1,625-fit extension or alter the submission-first thesis scope.

Historical recovery notes follow. On 2026-10-21 the SSD contained five verified
recovery refits, no completed extension release, and no active controller on
this Mac. Statements below that controllers are active describe their dated
October 1 launch state and are not current. Read
[HANDOFF](../coordination/HANDOFF.md) and [TODO](../coordination/TODO.md)
before any separately authorised extension work. The original workers stopped
after a host interruption; four of 21 missing-trace refits have verified
non-timing scientific comparisons. Three separately captured V2 controllers
are active on the owner's Mac to finish the remaining refits, assemble the
recovered grid and stage correction replay. Do not start a competing worker
or treat the partial local run as a verified release. Their launch evidence
and current limits are in HANDOFF; the final extension results are still pending.
A portable V2 release verifier is now in the repository, but it can only
validate and package the extension after the recovered grid and its final
producer lineage exist. The current run files themselves have not been
published as a complete remote release.
A clone supplies code and plans. Completed results are restored from the
private releases below.

The correction's full training-input preflight is complete: 1,400 of 1,650
contexts accepted the original draw and 250 accepted a rank-conditioned
redraw, with no terminal outcome. The
[completed-preflight record](../coordination/recovery/2026-09-29-generator-correction-complete-preflight-verification.json)
binds all 12,446 artifacts and seed histories. The pre-interruption
original-draw replay is preserved; recovered-source staging waits for the
full extension grid. The input/reuse inventory and arithmetic must complete
before the five actual execution reviews, freeze and full-budget corrected
pilot. No corrected fit has started.

The corrected launch safeguard is integrated as reviewed engineering source.
Earlier V1/V2 versions and their review failures remain preserved. The five
actual scientific reviews, corrected numerical freeze, ADR-041 selection/named
scope review and dispatch adoption are still pending.

Corrected pilot/remaining fits use the
[guarded launcher](../scripts/catalytic_correction/guarded_dispatch/capture_guarded_dispatch.py).
The separate `verify_guarded_dispatch_proof.py` checks retained dispatch
history. Its actual source and fresh receiving captures remain required
before release completion. Scientific budgets and acceptance gates are unchanged.

The current implementation includes the reviewed freeze builder, selective-fitting,
mixed deep verification, selected reproduction, reporting and release-v3
components. The full locked suite passed 1,040 tests and 293 subtests with
zero skips at 15:34:34 UTC on 29 September; all 752 captured files remained
unchanged. Repository-wide lint passed. These are implementation checks;
the numerical programme remains in progress.
Exact validation history is linked from the
[v3 integration record](../coordination/recovery/2026-09-29-generator-correction-guarded-dispatch-integration-v3.json).
The final extension transfer still requires completed numerical evidence,
selected reproduction, actual figure review and a fresh remote restore.
Guard history additionally requires separately captured source and fresh
receiving semantic verification; existing release-v3 only transports those
records.

At the 30 September interruption checkpoint, the original run has 1,214 of
1,625 cell records (1,000 complete, 176 failed, 38 failed diagnostics).
Twenty-one of those records reference 34 missing posterior traces, so the
stored count does not certify a verified grid. Six interrupted claims and two
partial traces were archived with verified hashes. The
[trace inventory](../coordination/recovery/2026-09-30-host-interruption-trace-inventory.json)
records each missing file and expected hash. The frozen raw expression,
matched cohort and locked environment have been restored and verified. An
isolated frozen-code pilot completed. Its new cell matches the saved official
non-timing scientific record, but the new NetCDF hash differs; the missing
original posterior arrays cannot be compared. Its
[comparison receipt](../coordination/recovery/2026-09-30-original-trace-pilot-comparison.json)
is method evidence, not a restored original trace or a released result. The
original six workers remain stopped. ADR-043/T-191 requires all 21 affected
cells to be refitted in fresh captured roots, then a separate recovered run
to finish the 411 identities fixed in the
[absent roster](../coordination/recovery/2026-09-30-original-extension-absent-roster.json).
Preserve the old run and every
terminal failure; do not resume its workers or copy pilot traces into it.

The V3 correction has sealed all 1,650 first-draw replay contexts and written
its selector. Its input/reuse inventory stopped at 1,536 of 1,625 cells; no
complete inventory, arithmetic, corrected fit or corrected result is certified.
The completed replay is preserved, while source-dependent reuse and arithmetic
must be checked against the recovered run before corrected fitting.
The two original sparsebundles on SSD980 were freshly byte-verified against
their redundant internal copies, then mounted read-only at the same paths;
only the internal duplicates were removed, freeing about 16 GiB. The active
run and V3 replay stay at their pinned Mac APFS paths. SSD980's raw filesystem
is ExFAT, so live numerical roots must not be moved onto it as plain folders.
A [portable storage checkpoint](../coordination/recovery/2026-09-30-storage-relief-checkpoint.json)
records the verification.
A dedicated 300 GiB virtual APFS image on SSD980 is mounted at
`/Volumes/BayesCoxRecovery20261001` for future results; it has passed
exclusive-create and atomic-rename probes. Existing result roots were not
moved into it, and it must be mounted before any future job using it.
At the 20:34 UTC 30 September checkpoint, the first three monitored refits
had zero wrapper/child returns and matching official non-timing scientific
records. The [first receipt](../coordination/recovery/2026-09-30-first-extension-recovery-refit.json),
[second receipt](../coordination/recovery/2026-09-30-second-extension-recovery-refit.json)
and [third receipt](../coordination/recovery/2026-09-30-third-extension-recovery-refit.json)
bind that historical evidence. A fourth refit was later verified through a
separate no-fit comparison, and the V2 controller is now working through the
remaining 17; see the latest [HANDOFF](../coordination/HANDOFF.md). The 411
initially absent cells still await continuation. Original missing posterior
arrays cannot be compared. The earlier controller's assembly command is
retired; the separate adapter must bind the full recovered source before
continuation. No partial extension or correction evidence has yet been
published as a remote results release.
The [assembly guide](extension_recovery_assembly.md) identifies the separate
adapter and its full-refit gate; assembly has not yet run.

Owner-side integration uses the resident checkout. The earlier six-document
mirror into the original IDE checkout was narrowly scoped while live worktrees
depend on its shared Git metadata. The
[14:55 document mirror](../coordination/recovery/2026-09-29-generator-correction-document-mirror-v3.json)
records that narrow update from published `a26d5a2`.

Use [the clinical methods execution guide](clinical_methods_execution.md)
and [release receipt](../coordination/recovery/2026-10-01-clinical-methods-release.json)
for an optional exact replay of the focused subset. Its fresh download and
scientific replay passed on the original Mac. Ravi needs to check his own
private GitHub and Overleaf access, but he does not need a Mac or a replay to
read the release and work on the thesis. Clinical METABRIC's known
same-individual pair may cross historical folds, and exact pretreatment
availability of some predictors remains unresolved. The baseline releases lack raw posterior
arrays, so no new trace-level diagnostic recalculation is claimed.

Use [the code guide](code_guide.md),
[correction execution](catalytic_correction_execution.md) and
[extension execution](extensions_execution.md) for component and run details.
The [evidence status](current_evidence_status.md) defines permitted scientific
claims. The full numerical restore procedure below targets an Apple Silicon
Mac because the exact lock is macOS arm64. It is optional for thesis writing.
Completed baseline releases were checked through a fresh clone and restore
on the original Mac; a second physical laptop was not tested.

## What is on GitHub

The private repository is
[ravivramchandani/Bayesian-COX](https://github.com/ravivramchandani/Bayesian-COX).
Use an account with access to this repository. There are four evidence releases:

- [Original confirmatory evidence](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/confirmatory-v1-44b6085):
  all 450 original cells, predictions, metrics, inference and source manifests.
- [Supplementary code/results programme](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/results-programme-20260927-11f86ce):
  the exact 450-cell reproduction, 825-cell robustness run, 75-cell post-hoc
  sampler sensitivity, original explanation, final reports and figures,
  verified code snapshot, QA and hash inventories. All ten assets were
  downloaded and restored successfully.
- [Supporting audit evidence](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/results-programme-audit-20260928):
  full native PDF review evidence, completed logs, earlier probes and external
  helpers; all three assets and 899 archive members verified after download.
- [Focused post-hoc clinical methods evidence](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/clinical-methods-posthoc-20261001-eaebcd7):
  225 selected penalised cells, nine saved refits, fixed 27-contrast analysis,
  descriptive tables, four reviewed PDF figures, frozen scope and code
  snapshots. Its canonical package inventory SHA-256 is
  `3497558581a4fefb67eabcf8a2b215cec6f48e3654fe681679a2572f54378953`;
  a fresh download and scientific replay passed. It depends on the first two
  releases for Bayesian reference evidence and does not include raw posterior
  arrays or the unfinished full extension.

Large results are release assets in the same private repository. A Git clone
contains the current code, plans and guides; the commands below retrieve the
result files and verify them. None of these releases requires files from the
supervisor's laptop.

If you contribute code or documentation from your own laptop, use your GitHub
account to clone the private repository. If you already have a clone, skip the
first command and enter that directory. Update `main`, use a new branch for
each change, and add only the intended source or documentation files:

```bash
gh repo clone ravivramchandani/Bayesian-COX bayesian-cox
cd bayesian-cox
git switch main
git pull --ff-only origin main
git switch -c ravi/my-change
git add path/to/changed-file
git commit -m "Describe the change"
git push -u origin HEAD
```

Replace the example branch, file path and message with your actual change.
Open a pull request into `main` for review. Do not commit raw datasets, local
run directories or partial extension results; the published evidence is in
the four releases above. Thesis writing in Overleaf does not require these
Git commands.

## Thesis source and PDF

The completed thesis source and PDF are backed up in this GitHub repository's [thesis branch](https://github.com/ravivramchandani/Bayesian-COX/tree/thesis/final-report-20261117). The code and original experiment evidence remain on `main`.

For Overleaf upload or browser editing, use [the final thesis instructions](ravi_thesis_next_steps.md). The active project is [6af91395a2e68e546f56fbc0](https://www.overleaf.com/project/6af91395a2e68e546f56fbc0). The earlier 6a750f3e project is a historical checkpoint. The report is complete; it does not need numerical replay.

## Optional locked-environment verification and restore on a fresh Apple Silicon Mac

This verifies the released evidence again on a receiving machine. Ravi does
not need to do it to read the results or prepare the thesis. For those tasks,
follow [Ravi's thesis next steps](ravi_thesis_next_steps.md) on any operating system.

Prerequisites for this optional verification: Apple Silicon, macOS 14 or newer,
Git, authenticated GitHub CLI (`gh`), and an arm64 conda installation. Use the
exact environment described in [environment_lock.md](environment_lock.md).
Install the lock tool in its own environment; do not regenerate the scientific lock.

The pending extension/correction receiving checks also require equality with
the complete frozen environment report. That report records arm64,
macOS 26.6 and Python 3.11.15, with all 259 locked packages. The baseline
installation minimum above does not certify extension replay on another OS
version. Verify the actual report before running the final extension checks;
keep any mismatch explicit and preserve the frozen environment requirements.

Run these commands in Terminal, using fresh destination directories:

```bash
gh auth status
gh repo clone ravivramchandani/Bayesian-COX bayesian-cox
cd bayesian-cox

conda create -n bayes-cox-conda-lock-4-0-2 \
  --override-channels -c conda-forge conda-lock=4.0.2
conda run -n bayes-cox-conda-lock-4-0-2 \
  conda-lock install -n bayes-cox-clean conda-lock.yml
conda run -n bayes-cox-clean python scripts/verify_environment.py

conda run -n bayes-cox-clean python scripts/restore_confirmatory_release.py

RAVI_REPO="$PWD"
RAVI_ORIGINAL="$RAVI_REPO/reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651"
RAVI_ASSETS="$RAVI_REPO/../ravi-programme-assets-20260927"
RAVI_RESULTS="$RAVI_REPO/../ravi-programme-results-20260927"

gh release download results-programme-20260927-11f86ce \
  --repo ravivramchandani/Bayesian-COX --dir "$RAVI_ASSETS"
conda run -n bayes-cox-clean python scripts/restore_programme_release.py \
  --release-dir "$RAVI_ASSETS" --original-run "$RAVI_ORIGINAL" \
  --output-dir "$RAVI_RESULTS"

conda run -n bayes-cox-clean make test PYTHON=python
conda run -n bayes-cox-clean python -m ruff check --no-cache .
```

The original restoration reports `cells=450 complete=430 failed_diagnostics=20`
and completion content hash
`03870efdae3134305794ea977fd9cbe7913c0d693f1b009337546319aa03bee1`.
The supplementary helper verifies every asset, archive member and metadata
hash, checks the original evidence, and restores into a fresh directory.
If the result directory already exists, it verifies its exact contents rather
than replacing them. No model is fitted by either restoration command.

The exact locked environment has 259 packages, Python 3.11.15 and matching
HDF5 2.1.0 build/runtime libraries. A differently configured Python environment
does not satisfy the numerical reproduction claim.

## Where to find the restored files

Paths below are relative to `$RAVI_RESULTS`, except the original source:

| Location | Contents |
| --- | --- |
| `$RAVI_ORIGINAL` | Immutable original 450-cell study |
| `code/` | Complete committed code snapshot `11f86ced8735b32767debb58f3cbbefbb5a7b8e6` used for the verified programme |
| `reproduction/` | All 450 refits, checkpoint and exact-comparison report |
| `robustness/` | All 825 cells, completion record and robustness/PH aggregates |
| `sampler_run/` | All 75 separate higher-acceptance horseshoe cells and their inference |
| `explanation/` | Unchanged original explanation result |
| `rendered_confirmatory/` | Generated primary, robustness and explanation tables, figures and LaTeX |
| `rendered_posthoc/` | Separately labelled sampler-sensitivity tables and figure |
| `release_metadata/` | Analysis verification, visual QA, release seal, manifest and checksums |

Read current plans and teaching documentation from the latest Git clone.
`code/` preserves the exact earlier revision used for the numerical claim.
Some preserved provenance records contain the original host's absolute
paths. Keep those bytes unchanged; use the restored paths above. A new
experiment records its actual host paths in a new manifest and output folder.

## Optional audit archive

The supporting archive is separate from the ten-asset result bundle. Restore
it when inspecting the native visual review, historical probes or logs:

```bash
RAVI_AUDIT_ASSETS="$RAVI_REPO/../ravi-audit-assets-20260928"
RAVI_AUDIT="$RAVI_REPO/../ravi-audit-evidence-20260928"
gh release download results-programme-audit-20260928 \
  --repo ravivramchandani/Bayesian-COX --dir "$RAVI_AUDIT_ASSETS"
(cd "$RAVI_AUDIT_ASSETS" && shasum -a 256 -c SHA256SUMS)
mkdir "$RAVI_AUDIT"
tar -xzf "$RAVI_AUDIT_ASSETS/programme-audit-evidence.tar.gz" -C "$RAVI_AUDIT"
```

`programme-audit-manifest.json ` records every member hash and size. Historical
logs and PID files describe earlier states; use the current HANDOFF for what
to run next. The final QA status is passed; earlier pending or format-rejected
records are retained for provenance.

## Continue from the existing evidence

The existing numerical programme is complete and remotely verified. Its fits
do not need to be rerun on the receiving laptop. All 428 final PDFs passed
review; all nine separate sampler contrasts are estimable, have Holm-adjusted
p-values of 1.0 and corrected intervals containing zero. Read the
[numerical summary](../coordination/recovery/2026-09-28-numerical-evidence-summary.json)
and [close-out review](../coordination/reviews/2026-09-28-programme-closeout.md).
A new result always goes in a separate directory.

T-180 is now frozen, and the separate 1,625-fit post-hoc extension grid was
launched from sealed commit `119476f`. It covers penalised Cox (T-182), the
precisely specified Piironen–Vehtari variant (T-183), survival decision
curves (T-184), matched METABRIC clinical/expression comparisons (T-185), and
the catalytic-prior variants/reference-parity checks (T-189). The original
host run stopped at the interruption checkpoint above; the separately captured
V2 recovery is active on the owner's Mac. Do not start duplicate workers on a
receiving laptop or merge partial outputs into the frozen run.
The extension transfer is pending its complete-grid, deep verification,
92-refit, final PDF-QA and fresh remote-restoration gates. Follow
[extension execution](extensions_execution.md) and the current HANDOFF;
T-186 is checked only after its separate evidence bundle passes. Under
ADR-044 these are non-blocking extension gates, not conditions for the
baseline thesis evidence freeze.

The original 20 horseshoe failures, incomplete original primary contrast
family and failed explanation-convergence gate remain part of the evidence.
The 75 new sampler fits are post-hoc sensitivity results and cannot replace
them. Preserve the actual earlier Holm-bound and sampler-probe chronology.

Thesis editing is authorised under ADR-053. Paper drafting,
submission and DOI minting are deferred until after thesis submission.

## Post-hoc extension evidence

The unfinished 1,625-cell extension programme remains separate from the released
baseline above. Its final release is pending numerical, visual and remote-transfer
verification. The [extension restoration guide](extensions_restore.md) gives the
receiving-Mac procedure and baseline dependencies; replace its remaining tag and
digest placeholders only after the verified release receipt is committed.
