# HANDOFF

State needed to resume work in a new session or on another machine.

Updated: 2026-09-28

## Active post-hoc extension production — authorised 2026-09-28

The owner requested plan corrections and full verified code/results
implementation. ADR-039 refines ADR-038. Implementation, real author/CRAN R
fixture parity, pinned METABRIC preparation, 298 tests, coordination schemas
and Ruff have passed. The implementation is remotely pushed. Six disjoint
numerical workers are actively filling the 1,625-fit grid on this Mac from
clean detached production commit `119476f`, with outputs outside Git at
`~/bayes-cox-runs/extensions-20260928/run`. First completed cell scores and
one saved posterior/prior diagnostic pair were independently checked. Do not
start duplicate workers or alter that sealed checkout. Inspect live PIDs,
claims, logs and cell hashes before resuming a stopped process. The manifest
pins every production input; its status is incomplete until all 1,625 cells
exist and downstream gates pass.

The verifier-only correction began at `ce8d6f5`; the separately pinned
analysis/renderer checkout is now `8551d32`. Finalization
uses that analysis checkout with `--production-code` pointing at the original
`119476f` checkout, and confirms all production hashes. Selected 92 numerical
refits must use the original production checkout. See
[execution instructions](../docs/extensions_execution.md). Both code
versions and the actual result directories must be included in the final
private evidence release and fresh restoration check.

At 2026-09-27 22:55 UTC (2026-09-28 11:55 Auckland), 226 of 1,625 production
cells and 22 selected candidate refits had been written; all observed source
cells were complete. Six production PIDs 62025–62030 and two sealed-code
pre-stage refit PIDs 64406/64435 were active. At 23:22 UTC the monitoring
coordinator alone was replaced to use the strengthened verifier; no fit or
refit process was interrupted. Current coordinator PID 71385 runs
`~/bayes-cox-runs/extensions-20260928/coordinate_after_fits_v2.py` and logs to
`~/bayes-cox-runs/extensions-20260928/worker_logs/coordinator_v2.log`.
The earlier coordinator source/log are retained; current counts at replacement
were 353 production cells and 35 selected refits.
After all workers exit it requires the complete grid and 92 candidate
refits, runs deep finalization from clean analysis commit `8551d32`, executes
the official 92-cell exact comparison from production commit `119476f`,
renders 32 figures/six tables, and prepares full-size PDF contact sheets.
It stops on any failed gate and writes `coordinator_failure.json`; successful
preparation writes `analysis_prepared.json`. Neither file constitutes final
visual approval or remote release. Inspect actual commands/PIDs and the
current cell/receipt files before any restart; the dated counts above are a
checkpoint, not a live progress claim.
`caffeinate -dimsu -w 71385` is active as PID 71386, bound to the
coordinator lifetime so idle sleep does not interrupt this Mac's computation.

The later transfer-only update passes 310 repository tests, 16 audit-support
integrity tests, the exact environment, schemas and Ruff. Its compact receipt
is `coordination/recovery/2026-09-28-extension-transfer-verification.json`;
complete logs/source hashes are in
`~/bayes-cox-runs/extensions-20260928/transfer_validation_v1` and must be
staged through `--validation-logs`. The latest clone's stager additionally
requires `--reference-root` and `--preparation-dir` for 55 pinned supporting
artifacts. Use `--clone-staging` on this APFS volume, then measure actual
inventory size/free space before one fresh remote restoration. The portable
`verify_restored_science.py` rechecks frozen sources/all-cell science and
directly repeats all 92 stored trace comparisons without fitting.
Production/analysis commits and running worker ownership remain as above.

The first clinical METABRIC cells contain execution failures before outer sampling:
rare training categories were absent from a frozen synthetic draw, producing
zero encoded columns and rank rejection. Independent reconstruction confirms
the cause; the encoder preserves valid whole categories. The addendum has no
redraw remedy. Keep these failed cells and all candidate refits unchanged.
Supplemental matrix reconstruction is being recorded separately because the
original generator raised before returning its synthetic metadata. Final
verification must report execution and diagnostic failures separately, with
unavailable contrasts/curves retained. These findings do not restart workers
or alter the frozen fitting implementation.

The later failure-provenance/visual-transfer update passes 349 repository
tests in 83.84 s, 16 support-integrity tests, 12 rank-audit tests, exact
environment verification, schemas and Ruff. Its compact receipt is
`coordination/recovery/2026-09-28-extension-failure-qa-verification.json`;
full logs and 157 unchanged source hashes are in
`~/bayes-cox-runs/extensions-20260928/transfer_validation_v2`. Preserve both
validation versions in the final transfer. The latest stager now also
requires `--failure-audit`: run its current `audit_rank_failures.py` against
the original production code and the finished source grid. Preserve the
partial `~/bayes-cox-runs/extensions-20260928/failure_provenance_v1` and its
original helper bytes. The later documentation pass changed the helper's byte
identity, so the finished-grid audit must use the reviewed current helper in
a fresh `failure_provenance_v2`; case bindings cannot mix helper versions.
Partial snapshots are supplemental provenance, not completion.
Staging/restoration bind every reviewed PDF/PNG/table, retained review form,
inventory, 32 page renders and four contact sheets to the original passed
receipt. Fresh restoration additionally repeats the rank reconstruction.
No numerical worker, sampling rule or analysis checkout changed.

The subsequent portable-path correction resolves the Mac's temporary replay
directory before applying the strict symlink gate. All 349 repository tests,
schemas, Ruff and an actual 42-case generator replay passed; the latter
checks 104 retained array paths/bytes on the current partial grid. It does
not claim complete scientific restoration. The compact receipt is
`coordination/recovery/2026-09-28-extension-native-path-verification.json`;
full logs are in `~/bayes-cox-runs/extensions-20260928/transfer_validation_v3`.
Preserve all three validation versions through the final transfer.

The baseline documentation pass is complete and integrated: 115 Python files,
858 module/class/function docstrings, and 230 successful stripped-AST
comparisons against both `f0cce64` and integration base `0ba4c3d`. All 349
repository tests pass in 85.44 s; normal repository Ruff, schemas and diff
checks pass. Original 103 worktree drafts remain unchanged and are preserved
with review ledgers, source hashes, helpers and complete gate logs in
`coordination/recovery/2026-09-28-documentation-gates.tar.gz` (269 members).
The compact receipt is
`coordination/recovery/2026-09-28-documentation-pass-verification.json` and
the review is `coordination/reviews/2026-09-28-documentation-pass.md`.
Full current-integration logs are additionally retained in
`~/bayes-cox-runs/extensions-20260928/transfer_validation_v4_documentation`.
Preserve this fourth validation version in the final transfer. No executable
statement, import, running worker or sealed scientific source changed.

The receiving-Mac procedure is now in `docs/extensions_restore.md`, cross-linked
from Ravi's baseline handoff. It explicitly restores the three baseline runs
separately, downloads only inventory/numeric shards, checks canonical identity
and a measured disk budget, extracts both commit-identified code archives, and
uses the latest clone's scientific verifier. Shell/Python syntax and both sealed
commits are checked; all 157 tested source hashes remain unchanged. Receipt:
`coordination/recovery/2026-09-28-extension-receiving-guide-verification.json`.
The tag/digest placeholders remain pending actual publication; syntax checking
does not constitute a downloaded complete-package restoration.

The extension documentation follow-up has now been independently reviewed and
corrected. All 25 changed Python files match the stripped executable AST at
`b4300fc`; all 140 changed Python files match `0ba4c3d`. All 153 Python modules
and 1,051 class/function definitions are documented. All 349 repository tests
pass in 88.60 s; normal Ruff, schemas and diff checks pass. All 157 tested
source/build/lock hashes stayed unchanged during these gates, and both sealed
scientific checkouts remain clean. Full logs are retained in
`~/bayes-cox-runs/extensions-20260928/transfer_validation_v5_extension_documentation`.
Preserve this fifth validation version with the earlier four. The review and
compact source-bound receipt are
`coordination/reviews/2026-09-28-extension-documentation-pass.md` and
`coordination/recovery/2026-09-28-extension-documentation-verification.json`.
The original analysis checkout's renderer/QA helper still owns final rendering
and the actual review receipt; current clone documentation cannot substitute
its different helper bytes for that binding.

The owner attached `/Volumes/SSD980`. Its ExFAT filesystem failed the actual
atomic no-replace preflight. A task-owned 200 GiB APFS sparse image now mounts
at `/Volumes/BayesCoxExtensions20260928`; actual atomic commit and existing-
destination preservation passed. No drive was reformatted or unrelated file
changed. Keep this image mounted: clone staging remains on the source internal
APFS volume, while package creation, the fresh remote download and one full
restore use the external APFS image. Measure both actual package requirements
and available space before transfer. The exact historical probe helper hash,
paths and capacity are recorded in
`coordination/recovery/2026-09-28-extension-external-storage-verification.json`;
it is a filesystem preflight, not completed science restoration. The receiving
guide's APFS prose and unchanged template are bound by
`2026-09-28-extension-receiving-guide-apfs-verification.json`.

Transfer tools are now pinned in a clean detached `2b701a8` checkout at
`~/bayes-cox-runs/extensions-transfer-code-20260928-2b701a8`. All 157 source
bytes match the fifth validation receipt. Its rank helper has SHA-256
`98cc7563c466e01d5bc72b8ba72a5beda771dceee16aeb3224a9639e1c1030fe`.
The partial second reconstruction records 73 rank failures on a dated
795-cell snapshot. All 184 retained synthetic-array hashes verify; all 86
arrays across the 34 earlier cases remain identical. Both versions and
the original helper are retained. This is supplemental provenance, not a
finished-grid audit or a new fitting remedy.

At 2026-09-28 02:51 UTC, reviewed post-fit companion
`~/bayes-cox-runs/extensions-20260928/complete_postfit_support_v1.py` started
as PID 98854, with `caffeinate` PID 98855 bound to its lifetime. It waits
for the original six fitting workers, requires all 1,625 source cells,
finishes rank reconstruction in `failure_provenance_v2`, and audits all
referenced full-grid traces using the pinned diagnostic-boundary driver.
Only exact byte-bound earlier trace inspections may be reused. Findings
remain reviewable separately from frozen acceptance rules; orphan trace
bytes are inventoried without inventing new diagnostic comparisons.
The original primary traces are still limited to their retained thinned
draws; this audit cannot recover missing full primary energies or latents.
The companion writes `postfit_support_prepared_v1.json` or
`postfit_support_failure_v1.json`. A prepared marker requires root review
and does not approve science, visual QA or transfer. Numerical coordinator
71385 alone still owns finalization, official refit comparison and rendering.
Do not duplicate either process. Inspect current commands and markers before
resuming after a stopped session.

The corrected transfer commands are prepared in
`~/bayes-cox-runs/extensions-20260928/final_transfer_runbook_v2`.
The earlier runbook and its two review findings remain unchanged. The new
version refreshes the package-plus-restore space budget after the fresh
clone and immediately before download, retaining the earlier budget receipt.
Its private draft guard and dependent commands share an exit-on-failure
subshell. Archive and scientific verification execute from the byte-matched
fresh clone. No stage, package, extension release, download or complete
restore has run. The reviewed source, launch ownership, partial provenance
and corrected preparation are retained in
`coordination/recovery/2026-09-28-extension-postfit-preparation.tar.gz`
and its compact verification receipt. Final validation bundle v3 must retain
all five validation versions, original and current support histories,
both runbooks/reviews, complete support audit results and storage receipts.
Seal it only after the finished audits are reviewed; preserve earlier
bundles unchanged.

The dated 2026-09-28 03:14:35 UTC checkpoint contains 837 of 1,625 source
cells: 730 complete, 99 execution failures and eight diagnostic failures.
GBSG2 and WHAS500 each contain all 325 cells; clinical METABRIC contains 187.
Matched clinical/expression production has not written cells at this
checkpoint. There are 66 candidate refits and no official comparison
receipts yet. All six fitting workers, both pre-stagers and both coordinators
are active, with no failure marker. These are dated counts, not completion.
The corrected runbook passed independent review with no unresolved findings;
its actual publication target/tag and asset bytes still require execution
checks. The 50-member recovery archive verifies all retained bytes, and all
157 previously tested source files remain unchanged. Compact receipt:
`coordination/recovery/2026-09-28-extension-postfit-preparation-verification.json`.

Final factual claim review is prepared in
`~/bayes-cox-runs/extensions-20260928/final_claim_review_preparation_v1`.
Its read-only helper requires the complete, deeply verified 1,625-cell grid,
92 official comparison receipts and actual passed figure QA before producing
source-bound counts. It retains incomplete comparison families, descriptive
RQ2 coverage and the original failed explanation claim. It cannot certify
publication or restoration. Its 21 pure schema checks and independent review
passed; it has not been invoked on actual extension results.

The supporting bundle assembler is prepared in
`~/bayes-cox-runs/extensions-20260928/final_validation_bundle_preparation_v1`.
It pins 359 historical files and six archive members, verifies the finished
support companion's actual rank/trace outputs and stable logs, and requires
`completed_support_review_v1.json` with eight fields and 16 actual byte
bindings. Root must inspect the findings after companion exit before writing
that review. Complete audits with findings remain reviewable; this review
approves preservation only. The assembler passed 43 pure guards and independent
review. No final bundle has been assembled. Both prepared tools, reviews and
contracts are preserved in the 39-member
`coordination/recovery/2026-09-28-extension-final-closeout-preparation.tar.gz`.
Its receipt verifies the historical inputs and all 157 unchanged tested
source files. The dated 2026-09-28 03:47:56 UTC checkpoint has 852 source
cells (736 complete, 106 execution failures, ten diagnostic failures),
66 candidate refits and no official receipts. These remain partial counts.

The final coverage audit identified two reporting omissions under the
already frozen addendum: explicit p/n and events/p in generated tables,
and descriptive paired catalytic-versus-comparator effects outside the four
formal families. Separate read-only sidecars are prepared; do not
alter the sealed fits, existing aggregates or specified families. Include
the sidecar source, verified tables and replay instructions in final transfer.
Complete paired effects retain the specified Nadeau–Bengio 95% intervals
without new significance claims; partial coverage stays explicit.

The reporting helper is prepared in
`~/bayes-cox-runs/extensions-20260928/final_reporting_sidecar_preparation_v1`.
It passed 21 synthetic checks, scoped lint/syntax checks and independent
review. It emits 1,625 ratio rows and 123 descriptive comparator rows, linking
27 existing formal contrasts without duplication. Its five-file output and
portable read-only replay preserve partial coverage and the original baseline
identities. Actual generation and source/fresh-restored replays remain pending.
All 15 preparation files, root review and dated observation are preserved in
the 19-member
`coordination/recovery/2026-09-28-extension-reporting-preparation.tar.gz`.
The archive verifies every retained byte; all 157 previously tested source
files and 18 earlier claim-preparation files remain unchanged. At
2026-09-28 04:33:35 UTC, 900 source cells are stored: 762 complete, 127 execution
failures and 11 diagnostic failures. Clinical METABRIC has 250 cells;
matched production has no stored cells. The 66 candidate refits have no
official comparison receipts yet. These are partial dated counts.

T-180 is frozen: content hash
`50b5f30f697b633718078e18c0da54be297361f8b06aeaf95af32e12aa1c646f`.
No extension outer-validation result existed before the freeze. All
extension outputs are post-hoc and remain separate from the closed primary
record. The remaining gates are complete 1,625-cell accounting, deep
diagnostic/score verification, separate RQ2/four-family/DCA aggregates,
92 exact refits, rendering and actual PDF QA, private release, fresh download
and restore, and factual plan/handoff close-out. Original results remain
available below. Overleaf and paper/DOI work are deferred.

## Completed baseline programme — Ravi can restore it

The completed programme is remotely available and independently restored.
Follow [Ravi's handoff](../docs/ravi_handoff.md), rather than historical PID
or reboot instructions below. No numerical process needs restart.

- Exact reproduction: 450/450 matches from sealed commit
  `11f86ced8735b32767debb58f3cbbefbb5a7b8e6`; all 90 code hashes match.
- Frozen robustness: 825 verified cells, 770 diagnostic passes and 55
  failures. Direct effects have 121/129 estimates and 95/129 fully paired
  rows; difference-in-differences has 45/45 estimates, 33 fully paired.
- Separate post-hoc sampler sensitivity: 75/75 diagnostic passes, nine
  estimable contrasts, all Holm-adjusted p-values 1.0 and all corrected
  intervals including zero.
- Both rendered lineages and all 428 PDFs/pages passed. The passed V3 review
  supports 426 exact PDF hashes; two new PDFs were actually inspected.
- The unchanged original source is in release `confirmatory-v1-44b6085`.
  New results and sealed code: [results-programme-20260927-11f86ce](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/results-programme-20260927-11f86ce),
  exactly ten downloaded/verified assets, restored through a fresh clone.
- Native QA evidence, probes, complete logs and external helpers:
  [results-programme-audit-20260928](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/results-programme-audit-20260928),
  three downloaded assets and all 899 archive members verified.

Compact evidence is in `coordination/recovery/2026-09-28-programme-closeout.json`
and `2026-09-28-numerical-evidence-summary.json`; the factual review is
`coordination/reviews/2026-09-28-programme-closeout.md`. Restoration was tested
on this Apple Silicon Mac with the existing verified lock, not on a second
physical laptop. The receiving Mac must verify its environment.

Original 20 horseshoe failures, incomplete primary inference and the failed
explanation gate remain findings. The frozen extension production above is
active under ADR-039. The separate documentation-only pass is tracked in
step 12.
Overleaf edits and paper/DOI work remain excluded.

## Earlier numerical checkpoint — before final close-out

The dated checkpoint is
`coordination/recovery/2026-09-28-numerical-checkpoint.json`. Independent
read-only verification accepted all 450 reproduced cells as exact matches
outside recorded timing/hash fields, the completed frozen 825-cell robustness
run and all 75 saved ADR-032 sampler cells. All 90 sealed source/script
hashes still match `11f86ced8735b32767debb58f3cbbefbb5a7b8e6`.

- Reproduction: 450/450 checked and identical; the report is
  `~/bayes-cox-runs/continuation-20260927/reproduction/verification.json`.
- Robustness: all 825 cells and completed aggregates verify. There are 770
  cells with passing diagnostic status and 55 recorded diagnostic failures.
  The six workers and finishing supervisor have exited.
- Sampler sensitivity: all 75 saved cells verify and have passing diagnostic
  status. Its inference/completion records were still pending at checkpoint.
- Coordinator PID 3374 remains responsible for sampler inference, strict
  final verification and both rendered bundles. No duplicate run is needed.
- New results remain local under `~/bayes-cox-runs/continuation-20260927/`
  and the original robustness directory below. They have not yet been
  packaged into the private supplementary release.

Final inference, completed render lineages, actual visual QA, claim review,
packaging, isolated restore and private-release verification remain required.
Stored cell counts do not complete these gates. The original failed cells,
incomplete primary family and failed explanation gate remain unchanged.
The new ADR-035 and ADR-038 extension experiments have not started. Overleaf
remains outside this programme.

## Earlier checkpoint — resumed after reboot

The owner requested completion of all remaining code/results tasks. At
07:51:46 UTC (20:51 Auckland) on 2026-09-27, execution resumed on this Mac
after its reboot had stopped every earlier numerical process. The exact
259-package runtime, unchanged frozen checkout and all 90 sealed code hashes
were verified before restarting. No completed cell was rerun or removed.

- Robustness resumed from 551/825 stored cells: GBSG2 255, WHAS500 270,
  METABRIC 26. Six missing-cell claims were recorded and released; the 551
  claims for saved cells were retained.
- Full reproduction resumed from 154/450 saved cells: GBSG2 150 and
  METABRIC 4. The checkpoint verifies these refits before submitting only
  the remaining 296 cells. No mismatch had been reported at restart.
- Sampler sensitivity remains queued after robustness, with 0/75 cells.
- Six frozen workers are PIDs 3362–3367; supervisor PID 3372 owns the final
  official robustness resume. Coordinator PID 3374 runs the sealed programme;
  `caffeinate` PID 3376 prevents idle sleep during its lifetime.
- Fresh launcher logs are in
  `~/bayes-cox-runs/logs/resume_20260927T075146Z/`. Earlier logs and PID records
  were copied there and hash-checked before restart. Internal programme logs
  append to their existing files.

The restart receipt is preserved in
`coordination/recovery/2026-09-27-restart-checkpoint.json`; external recovery
tools are in the matching restart-tools archive and hash manifest. The current
monitor reads `~/bayes-cox-runs/logs/current_resume.json`, rather than historical
PIDs. Inspect actual command lines before any further restart. The cross-laptop
instructions remain available in
`coordination/reviews/2026-09-27-cross-laptop-continuation.md`; no evidence was
transferred and no second laptop run was launched.

Numerical completion, final rendering, actual final visual QA, claim review,
packaging, isolated restore and private release remain required. The older
checkpoint below records historical state, not current process ownership.

## Earlier session checkpoint — numerical jobs left running

The owner wrapped up the interactive session on 2026-09-27 and explicitly
requested that the detached numerical jobs keep running. This pauses
interactive work; it does not stop or restart any fit. The checkpoint at
03:18 UTC (16:18 Auckland) is preserved in
`coordination/recovery/2026-09-27-wrapup-checkpoint.json`.

- Robustness: 549/825 stored cells. GBSG2 has 255/255, WHAS500 has 270/270,
  and METABRIC has 24/300. These are file counts, not diagnostic pass counts;
  final aggregation and strict completion verification remain pending.
- Full reproduction: 149/450 saved refits, all currently in GBSG2. No
  mismatch is reported; the complete 450-cell equality report is pending.
- Post-hoc sensitivity: 0/75; queued after completed robustness verifies.
- All six robustness workers, both reproduction workers, supervisor PID
  40646, coordinator PID 57940 and its `caffeinate` PID 57941 were active.
  All 90 sealed source/script hashes still matched commit `11f86ce`.
- Integrated code, 270-test validation and the passed 426-PDF base review
  are complete. Final numerical evidence, rendering, visual QA, claim review,
  packaging, restore verification and private release remain unfinished.

Resume by reading this checkpoint and inspecting the actual live state:

```bash
/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/python -B \
  /Users/macuser/bayes-cox-runs/harness/monitor_programme_once.py
```

Do not launch another coordinator or manually finish robustness while the
existing processes remain active. The coordinator proceeds automatically
through the numerical stages and final rendering. Its final
`~/bayes-cox-runs/continuation-20260927/programme_analysis_verified.json`
means analysis/rendering verification is complete and actual final visual QA
is still required. If `programme_failure.json` exists instead, inspect its
stage log before deciding how to resume; retain all existing evidence.

The next interactive steps are:

1. Strictly verify completed 450/825/75 evidence using the coordinator gates
   and external `~/bayes-cox-runs/harness/summarize_programme_evidence.py`.
   The helper refuses incomplete evidence and preserves scientific failures.
2. Follow `~/bayes-cox-runs/final-pdf-qa-preparation-20260927/README.md`.
   `final_pdf_qa.py` compares both final bundles with the passed V3 inventory,
   checks their actual PDF hashes, boxes and fonts, and rasterizes every new
   or changed page. Reuse only exact passed PDF hashes; actually inspect all
   remaining pages before producing a passed record.
3. Create the actual visual-QA-backed release seal for all seven evidence
   roots, package it with `scripts/package_programme_release.py`, verify an
   isolated restore, and upload a new private supplementary release. Leave
   the original confirmatory release unchanged; download and hash-check the
   new assets before closing the programme.
4. Update the final factual claims and task status, run the required checks,
   and commit/push the close-out. Overleaf edits remain outside this scope.

The four external resume helpers are preserved in
`coordination/recovery/2026-09-27-resume-tools.tar.gz` with per-file hashes in
the matching manifest. If a helper is missing, extract it to an external
directory. Preserve the frozen checkout, sealed programme checkout, original
results, V3 render and full V3 QA records; they are required source evidence.

## Recovery checkpoint

The interrupted work was inspected and preserved on 2026-09-27. The five
existing main commits through `6c037a8` were pushed, and the unfinished model,
confirmatory and explanation changes were committed to three remote WIP
branches. Their completed modular implementations are now integrated; the
original checkpoints remain preserved. The initial branches, validation and
runtime snapshot are in
`coordination/reviews/2026-09-27-recovery-audit.md`.

An archive and per-file hashes under `coordination/recovery/` preserve the
external runtime harness, initial horseshoe investigation and six-cell
baseline reproduction report. Running production outputs remain in the
frozen worktree. The Overleaf repository is clean and matches its remote.

## Active programme — refactor, completion and reproduction

Owner instruction of 2026-09-27, which supersedes the "stop and wait" step
in the 2026-08-16 sequence below:

- make this repository the single script-based pipeline; the external
  notebook is not ported;
- simplify and document the code so a new reader can follow it, without
  losing any function;
- correct errors and inconsistencies, run the paused downstream stages, and
  update the coordination files;
- do not edit the Overleaf thesis in this programme; record thesis
  corrections in `TODO.md` for later;
- commit and push at the end, with no AI co-author trailer.

### Standing owner instructions (2026-09-27)

- The thesis must contain every experiment a Q1 journal paper needs
  (ADR-036), with the scientific design refined by ADR-037. The paper is
  drafted later; the thesis is its planned evidence base, not a guarantee
  of acceptance or of no further reviewer-requested analysis.
- Do not edit the Overleaf thesis until the owner instructs.
- Only one agent works on the repository at a time.
- **Current state: baseline programme remotely verified; extensions active.**
  - The latest owner instruction requests everything Ravi needs on GitHub.
    Baseline evidence, full QA/log audit and its restore guide are released.
    Extension evidence still requires the full completion gates listed above.
  - The baseline coordinator and numerical stages exited successfully.
    Do not restart that completed programme or duplicate the active extension
    workers, selected refits or coordinator.
  - ADR-035–ADR-039 extensions run from sealed production `119476f` with
    separately sealed analysis `8551d32`. T-180 was frozen before their own
    outer-validation results; its frozen record remains unchanged.
  - The documentation-only pass is tracked in step 12; its worktree edits
    are separate from the sealed numerical code identity.

At 10:01 UTC on 2026-09-27, the read-only monitor reported 603/825 robustness
cells and 205/450 reproduction cells, no reported reproduction mismatch,
0/75 sampler cells and a live coordinator. These counts are a dated progress
snapshot, not completion or diagnostic acceptance. Read the current monitor
for live state; do not use this snapshot to decide whether to restart.

Findings behind each step are in
`coordination/reviews/2026-09-27-codebase-audit.md`.
Completed integration gates and their evidence locations are in
`coordination/reviews/2026-09-27-integrated-code-verification.md`.

### Established facts

- Commit `e824c1b` (2026-08-31) replaced the raw cohorts with output of the
  former synthetic fallback, restored pre-2026-08-14 files and wrote random
  cells into the frozen run directory. Revert `2e55c0b` restored the
  `4eeb1ac` tree. The frozen run verifies there and 170 tests pass in the
  lock environment.
- All 80 frozen inputs are stored byte-for-byte in commits `95af081`,
  `44b6085`, `4eeb1ac` and `2e55c0b`. This lets the frozen evidence be
  verified against a checkpoint commit instead of the working tree.
- ADR-030 is integrated in release restoration, completed confirmatory
  resume, robustness provenance and evidence verification. Original code is
  verified against checkpoint `44b6085`; live protocol, raw data, manifest and
  lock files retain their frozen bytes. New runs record every current source
  and script file. Frozen robustness completed in its unchanged original
  checkout and runtime; current code never mixed into its cells. Its complete
  verified evidence is in the baseline releases listed above.
- Primary results: the five estimable contrasts have maximum |ΔIBS| approximately 0.00034 and
  p ≥ 0.49. The smallest available p exceeds 0.05/5. Under Holm's
  step-down procedure, no estimable contrast can therefore be rejected,
  whatever the four missing p-values are.
- The external notebook (2026-09-26) builds Phase 2 on the synthetic CSVs.
  Phase 3 uses the real cohorts, but it evaluates one outer fold and 7 of 18
  model–cohort pairs, using metric values carried over in the session. The
  repository pipeline supersedes it.

### Plan and status

1. [x] Run robustness (T-140–T-143) and explanation (T-144) production with
   the frozen code, from a detached worktree of `2e55c0b` outside iCloud
   (`~/bayes-cox-runs/frozen`), in the lock environment.
   - Explanation: done 2026-09-27. Output:
     `~/bayes-cox-runs/frozen/reports/explainability/confirmatory_v1_confirmatory_cdcdcee84651_explainability_v1.json`
     (SHA-256 `120984c7…6ecd5`). It made 1,845 comparisons; the convergence
     summary is `failed`, so no claim is permitted.
   - Robustness: completed and independently verified 2026-09-28 in
     `~/bayes-cox-runs/frozen/reports/robustness/confirmatory_v1_robustness_robustness_702d93af33bf/`.
     The six workers used the unmodified frozen runner. Supervisor PID 3372
     finished the official unsharded resume and aggregation; workers and
     supervisor have now exited. All 825 cells verify, including 55 recorded
     diagnostic failures. Logs remain in `~/bayes-cox-runs/logs/`.
   - Production and coverage/interpretation review are complete; T-140–T-144
     record actual partial coverage and negative claim gates.
     Do not relaunch workers or the robustness finisher.
2. [x] Build a reproduction harness that reruns one cell and compares it
   with the frozen record: `scripts/reproduce_confirmatory_cells.py`. The
   baseline on unchanged code reproduced the quick selection exactly.
   Robustness equivalent: `~/bayes-cox-runs/harness/check_robustness_cell.py`.
   A sharded production cell matched a fresh unsharded refit exactly.
3. [x] Integrate checkpoint-bound frozen-evidence verification (ADR-030).
   Release restoration and completed confirmatory resume verify the actual
   450-cell run read-only. Robustness has current-code manifests, safe resume
   separation and `verify_completed_robustness_run`, which checks the exact
   frozen 825-cell/885-fit blueprint, source inputs, cell identities and all
   recorded hashes without refitting.
4. [x] Refactor for readability, module by module. Tests and required
   equivalence gates passed. The rules and gates are in
   `coordination/briefs/2026-09-27-readability-refactor.md`.
   - Models: all six reference refits matched every non-timing field,
     including the horseshoe's three failed diagnostic attempts.
   - Explanation: the original SHA-256 `120984c7…6ecd5` reproduced exactly;
     its negative convergence finding remains unchanged.
   - Confirmatory: all 450 stored cells reproduced the three aggregate files
     byte for byte; the six quick-selection cells and four specified
     additional refits matched exactly.
   - Robustness: three stored production cells covering all three priors
     matched exactly. Rehashed wrong-cell identity, condition, raw-data hash
     and status checks reject corruption.
   - Rendering retains all nine primary contrasts, explicitly unavailable
     tests and the separate ADR-033 bound, and produces thesis-ready LaTeX.
5. [x] Retire the legacy pilot execution lane under ADR-034. Historical data
   and results remain in place, retired source remains in Git history, and
   active tests use real raw cohorts with fold-local preprocessing.
6. [x] Regenerate the 450-cell run with the refactored code and compare it
   with the frozen artefacts (the ADR-026 reproduction claim). All 450 refits
   matched every non-timing field from sealed commit
   `11f86ced8735b32767debb58f3cbbefbb5a7b8e6`. Independent verification of
   the complete saved-refit inventory, report, source and code checkpoint
   passed on 2026-09-28; see the numerical checkpoint above.
7. [x] Render the frozen results tables and figures, including the Holm
   family-completion bound. The full old/new comparison retained 874 identical
   files, seven intended changes and five additions, with no missing output.
   See `coordination/reviews/2026-09-27-rendering-refactor-verification.md`.
   The subsequent full 426-page review found 30 legacy layout defects.
   The complete replacement bundle passed all 426 PDF pages, recorded in
   `coordination/reviews/2026-09-27-full-pdf-review.md`.
   The final completed-robustness and post-hoc bundles passed all 428 PDFs;
   see the 2026-09-28 close-out review.
8. [x] Complete the labelled post-hoc horseshoe sensitivity under ADR-032.
   All 75 cells and attempts verify and pass diagnostics. All nine contrasts
   are estimable, all adjusted p-values are 1.0 and all corrected intervals
   include zero. Separate rendering passed lineage verification and PDF review.
9. [x] Finalise documentation and evidence packaging. Strict numerical summary,
   coverage/claim review, actual visual QA and the seven-root seal are complete.
   Local and fresh remote restorations verified every archive member hash;
   two new private releases preserve results and full audit support.
10. [x] Commit and push verified evidence and Ravi's handoff. The final
    close-out is recorded in the dated review and compact receipt.

11. [ ] Thesis extension experiments under ADR-036–ADR-038; T-180–T-186 and
    T-189 in `TODO.md`. The new analyses were not part of the completed coordinator.
    Dependencies:
    - freeze the actual new-analysis addendum (T-180) before their own results;
      reference existing ADR-032/ADR-033 evidence with its actual chronology;
    - T-181 is the completed sensitivity in step 8, independent of T-180;
      do not run it twice;
    - after T-180, run fair inner-CV penalised-Cox comparators (T-182) and
      censoring-aware decision curves from stored predictions (T-184);
    - after T-180/T-181, run the precisely specified Piironen–Vehtari clinical
      variant (T-183), with comparable sampler settings and unchanged gates;
    - after T-180/T-182/T-183, run matched METABRIC clinical-only and clinical-
      plus-expression arms (T-185), explicitly including the new variant;
    - after T-180, validate the Cox catalytic prior against the authors'
      implementation and run it wherever the other priors run, including
      RQ2 conditions and both matched METABRIC settings (T-189, ADR-038);
    - render and actually review the separate extension bundle (T-186).

    Paper drafting and submission are deferred until after the thesis.

12. [x] Documentation pass (owner instruction 2026-09-28). Brief:
    `coordination/briefs/2026-09-28-documentation-pass.md`. Preserved the four
    original worktree drafts, reviewed independent candidate packages, and
    integrated all 115 baseline files: pipelines; models, evaluation,
    statistics, data and utils; explanation and rendering; scripts and tests.
    - Gate: 230 stripped-AST matches against `f0cce64` and `0ba4c3d`;
      all 349 repository tests, normal Ruff, schemas and diff checks pass.
    - Every module/class/function in the declared baseline scope is documented;
      the reading guide `docs/code_guide.md` maps the active extension separately.
    - Review, exact source hashes, unchanged original drafts and full gate logs:
      `coordination/reviews/2026-09-28-documentation-pass.md` and
      `coordination/recovery/2026-09-28-documentation-pass-verification.json`.
    - Extension follow-up (commits `c3175dc` to `9acef2e`): the post-baseline
      extension files are now documented too. They cover the catalytic and
      calibrated-horseshoe priors, penalised Cox, decision curves, the
      release, transfer and audit scripts, and their tests. Every module and
      all 1,051 class/function definitions and 153 modules have docstrings.
      The independent correction review and source-bound fifth validation
      version above supersede the initial wording. All 25 extension files
      pass the stripped-AST gate; 349 tests pass and Ruff is clean.

Tick each box when its step is complete, and record where its outputs are.

`scripts/complete_results_programme.py` completed from immutable checkout
`~/bayes-cox-runs/refactored-programme-20260927/`, with output in
`~/bayes-cox-runs/continuation-20260927/`. All 90 code hashes and original
explanation bytes remain sealed. Coordinator PID 3374, supervisor 3372,
workers and caffeinate exited. Its verified-analysis record was followed by
actual visual QA, claim review and private release verification. Historical
logs and host paths are in the audit release. The student restore guide
requires neither these host paths nor another run of the completed fits.

Administrative deadline: the live programme in `TODO.md` runs from 2026-08-17
to 2026-11-30. This 15-week schedule supersedes the earlier 26-week dates for
project management without changing any frozen analytical method or claim
gate.

## Exact runtime

On the original machine, use the verified locked environment directly. The
absolute path below is machine-specific; on another machine, install
`conda-lock.yml` as `bayes-cox-clean` using the README instructions. The older
environment named `bayes-cox` is not lock-equivalent because its PyTorch
package route differs.

```bash
EXACT_PY=/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/python
$EXACT_PY scripts/verify_environment.py
$EXACT_PY -m pytest -q
$EXACT_PY -m ruff check .
```

Verified 2026-08-16: 170 tests pass and Ruff is clean. The exact macOS arm64
lock contains 259 packages and has SHA-256
`1921895d4a404fc99e848d69ccd4a3f6639a3d1610315c82ecd463ed4bcdfb57`.
Python is 3.11.15; h5py 3.16.0 uses matching HDF5 2.1.0 build/runtime
libraries. PyMC chains run sequentially (`cores=1`) on this machine.

## Authoritative status

The design, statistical analysis plan, ethics/data-use position, licensing
position, journal targets and supervisor-decision track are owner-approved.
Q-001 through Q-006 are answered and must not be asked again. No institutional
ethics reference or named clinical reviewer was supplied, so neither may be
invented. Clinical interpretation without an authoritative source is omitted.

The confirmatory engineering foundation is implemented and reference-tested:
fold-local preprocessing, paired repeated outer folds, compact inner tuning,
training-only horizons, IPCW metrics, explicit calibration, corrected paired
inference, immutable cell/prediction schemas, DeepSurv, full Bayesian quality
gates, frozen-cell explanation, lean robustness and pure rendering.

Implementation is not scientific evidence. The final-input result-blind
rehearsal completed all 18 cells using only status/timing inspection, and the
deterministic resource rule retained five repeats. The write-once protocol
freeze exists unchanged at `config/protocol_freeze.json`; all 80 recorded
inputs verify against the original checkpoint, while live methodological
inputs retain their frozen bytes. The freeze content SHA-256 is
`3b5e1042d592ebb6fade0a4a76c1f0d31ce9c0c1cfc08357be46f163f037d2ca`.

The frozen confirmatory execution is complete at
`reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651/`. The frozen-
run verifier accepted the exact 450-cell grid, content hashes, aggregate
hashes, complete-cell metric and prediction lineages and unchanged protocol
freeze. Of the 450 cells, 430 completed and 20 exhausted the prespecified
diagnostic remedies.
All failures are horseshoe fits: 18 in GBSG2 and two in METABRIC. WHAS500 and
every non-horseshoe arm completed all 25 folds.

The inferential evidence is deliberately incomplete. `inference.json` records
`status: incomplete` and `holm_family_complete: false`: five of nine primary
contrasts have all 25 paired folds, while the two GBSG2 and two METABRIC
horseshoe contrasts have no confirmatory inference. No complete-family
superiority, equivalence or multiplicity-controlled claim is accepted.
Frozen robustness is complete and independently verified: 825 cells, with
770 diagnostic passes and 55 failures, released separately from the primary
record. The active extension production is the separate run listed above.
Confirmatory explanation production completed, but its convergence gate
failed and it permits no RQ3 claim. See the recovery checkpoint above.

## Data state

The three confirmatory raw files and their exact counts/hashes are complete:

| Cohort | Records/events | Derived SHA-256 |
|---|---:|---|
| GBSG2 | 686 / 299 | `2158b777d27ecfb69b187d3cbcad13fd1eb92d626935c528a4465fea6490ae5f` |
| WHAS500 | 500 / 215 | `4bb01775c04eca11d7f06d6e5dfebd0a5cce75aa7e73fe4261732385be106fcc` |
| METABRIC | 1,980 / 1,144 | `731ea80ce0240cb6aa96ffb0f4a3bb379615202966c954512664bef02b29545c` |

The manifest pins upstream files, hashes, citations, endpoint coding and
licence limits. Public release defaults to metadata, hashes and retrieval
scripts; the project MIT licence does not relicense patient data. METABRIC
database material is ODbL. The earlier 1,904-row METABRIC file remains pilot
input only.

Primary features are the eight raw GBSG2 predictors, nine documented
admission-time WHAS500 predictors and the baseline/pathology METABRIC set with
age, NPI and six categorical variables. Published-full, engineered,
NPI-component/stage and treatment-augmented representations are sensitivities.

## Evidence boundary and frozen-run state

The 15 legacy model/cohort fits and 18 legacy explanation comparisons are
exploratory pilot evidence only. They cannot support confirmatory superiority,
equivalence, calibration, prior-asymptotic or clinical-feature claims.

The legacy rehearsal stored all 18 planned cohort/model cells but only 14
completed and remains unusable. The fresh predecision rehearsal at
`reports/confirmatory_rehearsal_predecision_20260815/` completed 18/18 under
the exact reduced workload. Only console completion and runtime were inspected;
the rounded timing bound mandates five repeats. Its input hashes precede the
resulting status/decision update, so it cannot itself create the final freeze.
The subsequent final-input rehearsal at
`reports/confirmatory_rehearsal_final_20260815/confirmatory_v1_rehearsal_df0135acdf99/`
also completed 18/18 and is the timing evidence named by the write-once freeze.
No comparative rehearsal effect was inspected or admitted. Do not inspect or
report any rehearsal performance effect.

The production completion record has content SHA-256
`03870efdae3134305794ea977fd9cbe7913c0d693f1b009337546319aa03bee1`;
the manifest content SHA-256 is
`9ec040841b4751ee3064c93d21d5069ed27bf3bfd6641f0dfffff76557bbf9f7`.
The aggregate artefacts and all 450 cell files are covered by the completion
inventory. The 20 failed-diagnostic cells each contain all three frozen fit
attempts and are excluded from `fold_metrics.csv` and inference. Preserve this
failure outcome; do not add a remedy or selectively rerun a cell within the
current freeze.

The complete 552 MB evidence directory is available to authorised repository
collaborators as the private GitHub Release `confirmatory-v1-44b6085`:
<https://github.com/ravivramchandani/Bayesian-COX/releases/tag/confirmatory-v1-44b6085>.
Its archive SHA-256 is
`0dbb745b82e5998b5aabc4bb3f05b28f87e00ba2851101a8accb83d447ddf34b`.
From the root of a clone with the exact environment installed, run:

```bash
conda run -n bayes-cox-clean python scripts/restore_confirmatory_release.py
```

The helper downloads both assets, checks the supplied SHA-256, rejects unsafe
archive paths, verifies every frozen artefact and confirms all 80 checkpoint
input blobs plus unchanged live study inputs before installing the run beneath
`reports/confirmatory/`. It never overwrites an existing run and instead
verifies it in place.

The available complete contrasts and descriptive aggregates are frozen
production evidence, but the primary family is not complete. They may be used
only with wording that makes the diagnostic attrition and incomplete family
explicit. They must not be presented as though all nine primary contrasts or
their Holm adjustment were available.

The robustness runner is intentionally large even after scope control: at
five repeats it plans 825 checkpoint cells and 885 Bayesian fits, with RQ2 on
outer folds 1–2 and design/feature sensitivities on fold 1. It performs no
calibration bootstrap in IBS-only sensitivity cells and refuses production if
a timing-only projection from completed confirmatory cells exceeds 72 hours.

Rotterdam transport and the ADEMP simulation are permanently dropped under
ADR-025. They are not delayed tasks and cannot be reintroduced after results.
The evidence supports no external-validation or cross-domain generalisation
claim.

## Thesis state

The adjacent Overleaf repository now has a focused introduction and
literature review plus a substantial pre-freeze methodology and reproducibility/
diagnostic appendices. Its bibliography has 36 retained, cited entries: 30
with DOI records and six authoritative web records. The results, conclusion
and abstract remain intentionally unwritten. Frozen production evidence now
exists, but the primary inferential family is incomplete and the owner has
paused post-confirmatory thesis writing. Do not populate these chapters from
pilot or rehearsal effects, or start the production-results rewrite without a
new instruction.

After the methods package was added, a LaTeX/BibTeX build produced a 70-page
A4 PDF with no undefined citations/references, LaTeX warnings, or overfull/
underfull boxes; fonts are embedded and `make jargon` passes. Methodology and
appendix pages were visually inspected. Later results, conclusion and final
abstract writing must use renderer outputs and frozen result keys, not manually
transcribed values.

## Historical close-out sequence — superseded by the active programme

1. On a new machine, use the README restoration command and require the
   reported 450-cell, completion-hash and 80-input checks to pass. The source
   checkpoint and private evidence Release are already published; do not rerun
   or selectively reconstruct the confirmatory analysis.
2. The prospective `docs/study_protocol.md` is an immutable pre-execution
   record. Read it as the frozen analysis plan together with this close-out,
   which records the observed diagnostic attrition and inferential boundary.
3. The former downstream pause is superseded for code/results work by the
   2026-09-27 instruction above. Continue robustness, reproduction, sensitivity
   and evidence rendering. Overleaf chapter writing remains excluded.
4. On resumption, retain the prespecified failed-fit outcome and incomplete
   primary-family status in every downstream table and claim. A methodological
   change requires a new result-blind rehearsal and freeze; it cannot be folded
   into this run.

Do not edit live frozen methodological inputs. ADR-030 permits code and
ordinary-documentation changes while their original checkpoint blobs remain
verifiable. A methodological change cannot enter the completed confirmatory
analysis; the acceptance-only sensitivity is separate under ADR-032.
