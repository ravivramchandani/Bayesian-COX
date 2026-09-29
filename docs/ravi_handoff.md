# Ravi: restore the results and continue the work

The baseline code and results programme is complete and remotely verified.
The separate 1,625-cell post-hoc extension and catalytic correction are still
active. Their final results are not yet available as a verified remote release.

Read [HANDOFF](../coordination/HANDOFF.md) and [TODO](../coordination/TODO.md)
before launching extension work on another Mac. The owner's existing jobs
still own the original run and input replay; do not start overlapping workers.
A clone supplies code and plans. Completed results are restored from the
private releases below.

The correction's full training-input preflight is complete: 1,400 of 1,650
contexts accepted the original draw and 250 accepted a rank-conditioned
redraw, with no terminal outcome. The
[completed-preflight record](../coordination/recovery/2026-09-29-generator-correction-complete-preflight-verification.json)
binds all 12,446 artifacts and seed histories. Independent original-draw/input
replay and arithmetic must complete before the five actual execution reviews,
freeze and full-budget pilot. The detached continuation stops before fitting.

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

At 15:38:44 UTC on 29 September, a non-atomic metadata check showed 707 of
1,650 independent input receipts and 1,115 of 1,625 original outcomes:
917 complete, 170 failed and 28 failed diagnostics. All 15 monitored jobs
were present. These are dated progress counts.
Original successes/failures and interrupted storage/replay evidence remain
preserved. Keep SSD980 and its two mounted images available while jobs run.
Owner-side integration uses the resident checkout; only the six published
guide/coordination documents are mirrored into the original IDE checkout
while live worktrees depend on its shared Git metadata. The
[14:55 document mirror](../coordination/recovery/2026-09-29-generator-correction-document-mirror-v3.json)
records that narrow update from published `a26d5a2`.

Use [the code guide](code_guide.md),
[correction execution](catalytic_correction_execution.md) and
[extension execution](extensions_execution.md) for component and run details.
The [evidence status](current_evidence_status.md) defines permitted scientific
claims. This guide targets an Apple Silicon Mac: completed baseline releases
were checked through a fresh clone and restore on this Mac, while Ravi must
verify the frozen environment on his own laptop. A second physical laptop was
not tested.

## What is on GitHub

The private repository is
[ravivramchandani/Bayesian-COX](https://github.com/ravivramchandani/Bayesian-COX).
Use an account with access to this repository. There are three evidence releases:

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

Large results are release assets in the same private repository. A Git clone
contains the current code, plans and guides; the commands below retrieve the
result files and verify them. None of these releases requires files from the
supervisor's laptop.

## Install and restore on a fresh Mac

Prerequisites: Apple Silicon, macOS 14 or newer, Git, authenticated GitHub CLI
(`gh`), and an arm64 conda installation. Use the exact environment described
in [environment_lock.md](environment_lock.md). Install the lock tool in its
own environment; do not regenerate the scientific lock.

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
conda run -n bayes-cox-clean python -m ruff check .
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

`programme-audit-manifest.json` records every member hash and size. Historical
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

T-180 is now frozen, and the separate 1,625-fit post-hoc extension grid is
running from sealed commit `119476f`. It covers penalised Cox (T-182), the
precisely specified Piironen–Vehtari variant (T-183), survival decision
curves (T-184), matched METABRIC clinical/expression comparisons (T-185), and
the catalytic-prior variants/reference-parity checks (T-189). Do not start
duplicate workers on a receiving laptop while the active host owns this run.
The extension transfer is pending its complete-grid, deep verification,
92-refit, final PDF-QA and fresh remote-restoration gates. Follow
[extension execution](extensions_execution.md) and the current HANDOFF;
T-186 is checked only after its separate evidence bundle passes.

The original 20 horseshoe failures, incomplete original primary contrast
family and failed explanation-convergence gate remain part of the evidence.
The 75 new sampler fits are post-hoc sensitivity results and cannot replace
them. Preserve the actual earlier Holm-bound and sampler-probe chronology.

Overleaf editing still requires the owner's instruction. Paper drafting,
submission and DOI minting are deferred until after thesis submission.

## Post-hoc extension evidence

The active 1,625-cell extension programme remains separate from the released
baseline above. Its final release is pending numerical, visual and remote-transfer
verification. The [extension restoration guide](extensions_restore.md) gives the
receiving-Mac procedure and baseline dependencies; replace its remaining tag and
digest placeholders only after the verified release receipt is committed.
