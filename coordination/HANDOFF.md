# HANDOFF

State needed to resume work in a new session or on another machine.

Updated: 2026-10-01 (New Zealand; dated checkpoints below use UTC)

## Post-successor replay staging — waiting since 2026-10-01, 05:53 UTC

A third detached watcher (PID 962 at launch) waits for the successor's
genuine `complete.json` and released producer claim. Its
[launch](recovery/2026-10-01-post-successor-replay-stage-launch.json) and
[start](recovery/2026-10-01-post-successor-replay-stage-start.json) receipts
bind clean code commit `f2a5703`, the fixed recovery plan, successor launch,
preflight/replay anchors and destination. The locked suite passed 1,110 tests,
9 skips and 288 subtests before launch. The watcher has no completed source
to seal yet. After the successor finishes, it captures the final 1,625-cell
producer-lineage sealer, then verifies and copies the 1,650 complete V3
first-draw replay contexts to
`/Volumes/BayesCoxRecovery20261001/correction-replay-recovered-20261001`.
It stops before reuse inventory, arithmetic or a corrected fit. A failed
gate retains its claim and capture for review. Keep its pinned checkout
`/Volumes/BayesCoxRecovery20261001/ravi-post-successor-runtime-20261001`
at `f2a5703` untouched alongside the two earlier runtime checkouts and
keep SSD980 and its mounted APFS images attached.

## Correction replay transfer — prepared, source run still pending

The V3 independent first-draw replay has 1,650 completed contexts: 1,400
accepted original first draws and 250 rank-rejected first draws followed by
the frozen redraw rule. Its 1,536-cell input/reuse inventory is partial.
`scripts/catalytic_correction/stage_replay_for_recovered_run.py` now verifies
the recovered run's 1,625-cell producer lineage and deeply checks every
preflight, replay, child and numeric proposal before copying only the complete
replay evidence to a fresh output with a run-path-only execution-manifest
change. All 1,650 actual V3 contexts passed its read-only verifier; the
recovered source is not complete, so no full staging, new input/reuse
inventory, arithmetic or corrected fit has run. See
`docs/catalytic_correction_execution.md` for the source anchors and next gate.

The extension release bundle also carries the captured sequential supervisor
launch and its published attestation, with receiving-side command, plan,
source, process and archive bindings. This is preparatory release code; no
complete recovered run or new private extension release exists yet.

## Recovered-grid successor — waiting since 2026-10-01, 03:23 UTC

The final-lineage sealer and captured-proof release/restore gate are prepared in the
coordination checkout. After the successor's real completion, use the
[assembly guide](../docs/extension_recovery_assembly.md) to bind the 411
new producer files and six captured zero returns. This code has no result to
seal yet. The release stage now refuses an assembled recovered run without
its final supplement, recomputes the actual source proof from the controller,
and packages the refit/continuation captures and recovery source archive. It
can use independent Git metadata for the frozen production checkout. Deep
verification, renewed source-bound 92-cell reproduction checks, render/QA
and transfer are still required. A read-only audit found 89 unaffected
prestaged refits as candidates for exact rechecking and three affected
selected identities whose six declared refit traces are missing. The latter
require fresh captured fits; the former cannot receive new source-bound
receipts until the recovered run exists and exact cell, trace, scientific
content and sampled arrays are reverified. Do not describe the 89 as newly
fitted or infer ADR-041 producer return codes from their saved records.

A second detached watcher (PID 83450 at launch) waits for the 21-refit
supervisor's real complete receipt and six fixed-shard returns. Its
[launch checkpoint](recovery/2026-10-01-recovered-extension-continuation-launch.json)
pins clean analysis commit `442a35c`, source, plan, process and claim. No
assembly or continuation cell has begun. After the prior proof passes, it
captures separate assembly preflight and assembly, then runs only the 411
originally absent manifest positions through the sealed six-shard runner,
one worker at a time. Each return and new cell/trace hash is checked before
another shard begins. Its `complete.json` will mean a stored 1,625-cell grid
pending deep verification, 92 selected reproductions, final 411-producer
lineage, figures/PDF review and private release. A failure retains its claim
and capture for review; it never retries or changes the original run.

Keep the first two runtime checkouts untouched while their watchers are active:
`/Volumes/BayesCoxRecovery20261001/ravi-thesis-handoff-20261001` at `a673512`
and `/Volumes/BayesCoxRecovery20261001/ravi-continuation-runtime-20261001` at
`442a35c`. The separate coordination worktree can publish further code and
status without changing either pinned process. The preserved correction
evidence image at `/Volumes/BayesCoxExtensions20260928` was reattached
read-only after the SSD reconnect and passed APFS verification; correction
replay still requires the recovered full-grid source and is not running.

## Sequential recovery supervisor — waiting since 2026-10-01, 03:04 UTC

A detached supervisor (PID 38835 at launch) is waiting for the fourth
captured refit. It has not dispatched another cell. Its
[launch checkpoint](recovery/2026-10-01-sequential-recovery-supervisor-launch.json)
binds the fixed plan, live capture, clean analysis commit `a673512`, source
hash, start and exclusive supervisor claim. The locked suite passed 1,081
tests, 9 skips and 288 subtests before launch. The runner will verify the
fourth cell's actual return, trace bytes and official scientific comparison,
then handle the remaining fixed shards one cell at a time. Any mismatch,
interrupted attempt, code change, missing SSD mount or low-space gate stops it
with a retained claim for review. Three of 21 refits are verified now; the
fourth remains pending. The 411 absent cells and correction have not begun.

Keep `/Volumes/SSD980` and `/Volumes/BayesCoxRecovery20261001` mounted. Do
not edit or switch the pinned runtime checkout
`/Volumes/BayesCoxRecovery20261001/ravi-thesis-handoff-20261001` or start an
independent recovery worker while the supervisor runs. Coordination updates
can be made from the separate worktree without changing the pinned runtime
checkout. The APFS image briefly unmounted when SSD980 reconnected during
testing; it was reattached, passed a live filesystem verification and the
active fit continued. Check the local `captures/sequential-v1` start, per-cell
returns and `complete.json` or `failure.json` before advancing T-191. The
[supervisor guide](../docs/extension_recovery_supervision.md) gives the exact
paths and stop rules.

## Fourth monitored recovery fit — launched 2026-10-01, 02:03 UTC

Three of 21 affected refits remain verified; the fourth is active and has no
terminal scientific result yet. Worker 0 is fitting the fixed matched-METABRIC
expression spike-and-slab `r01f03` cell in a separate write-once attempt under
the unchanged v3 recovery plan. Its
[launch receipt](recovery/2026-10-01-fourth-extension-recovery-launch.json)
binds the process, claims, code and capture. The first preflight for this cell
stopped before a producer claim because the sealed checkout's shared iCloud
Git metadata stalled. The
[no-fit preflight record](recovery/2026-10-01-extension-recovery-git-metadata-preflight.json)
documents a process-scoped independent Git metadata clone at the same frozen
commit: the sealed source tree checked clean and its freshly built manifest
matched exactly. No scientific code, frozen input or original cell was changed.
Check the active capture, typed returns and official comparison before counting
this refit or launching another worker. Keep SSD980 and its APFS image mounted.

## Separate focused clinical methods study — ADR-045

The owner approved a smaller post-hoc methods study while Ravi finishes the
submission-first thesis. Its dated, hash-pinned scope is in
`docs/protocol_addendum_clinical_methods.md`,
`coordination/clinical_methods_roster.json` and
`coordination/clinical_methods_scope_freeze.json`. The fixed input is 225
original extension clinical penalised-Cox cells, 150 frozen normal/spike-slab
references and 75 ADR-032 horseshoe references across all three cohorts and
25 folds. The original 27-member Holm family remains complete-or-unavailable;
diagnostic attrition and the original horseshoe failures stay visible. The
new scope was selected after partial extension execution, so it is not
result-blind. Focused scores were not inspected during the scope decision.

T-192 is complete as a separate, privately released study. Clean code commit
`eaebcd7b422e63cc7b0792cc8ac481f83a0080ba` verified and independently
rescored 225/225 selected penalised cells and compared all nine saved
first-fold refits on non-timing scientific content. The nine historical
formal refit receipts remain absent and are reported as such. All 27 fixed
IBS contrasts have 25 paired folds; the Holm family is complete, with zero
rejections and every repeated-CV interval crossing zero. This establishes
neither superiority nor equivalence. The original horseshoe record retains
20 diagnostic failures; the separate ADR-032 sensitivity passed 75/75 cells.

The [private focused release](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/clinical-methods-posthoc-20261001-eaebcd7)
has canonical inventory SHA-256
`3497558581a4fefb67eabcf8a2b215cec6f48e3654fe681679a2572f54378953`.
Its four PDFs and nine claim boundaries passed named review. A fresh GitHub
download passed archive verification and independent scientific replay of
225 cells, nine refits, the analysis and preserved QA. The
[release receipt](recovery/2026-10-01-clinical-methods-release.json) binds
the code, scope, asset and replay hashes; the [results note](../docs/clinical_methods_results.md)
gives the permitted interpretation. The earlier candidate render was
rejected for ambiguous horseshoe and interval labels, corrected in `eaebcd7`,
and preserved outside the release; its statistical aggregates were unchanged.
This receiving check used a fresh clone and download on this Mac, not Ravi's
physical laptop.

The 1,625-fit extension, recovery and correction retain their original open
tasks and frozen gates. This focused release cannot be called the full
extension release. Ravi's thesis remains on the ADR-044 baseline path;
Overleaf and paper work are unchanged.

## Submission-first scope — 2026-10-01 New Zealand

ADR-044 supersedes ADR-036's requirement that the unfinished Q1-oriented
extension and catalytic correction be completed before thesis submission.
Ravi's thesis now proceeds from the verified, privately released baseline:
confirmatory, robustness, explanation, the separately labelled ADR-032 sampler
sensitivity and ADR-033 Holm bound, including the original diagnostic and
explanation failures. T-147 and T-150–T-161 are the submission critical path;
the results and conclusion chapters are still essentially empty. The frozen
extension addendum and every numerical/release gate remain intact. The owner
wants the experiment completed quickly, so its separate run may continue in
parallel, but partial extension cells cannot support completed-grid claims or
delay the baseline thesis. The worker-5 refit below has now been verified;
no numerical producer was active at the 20:34 UTC checkpoint. Recheck
controller state and host resources before a new launch. The two-day
experiment aim is not a verified ETA: 18 refits, 411 absent cells, selected
reproduction and correction
still remain. Paper drafting and DOI work stay after thesis submission.
Overleaf edits still await the owner's separate instruction.

## Third monitored recovery fit — completed 2026-09-30, 20:27 UTC

After the second refit passed independent review, worker 5 started one new
write-once cell under the unchanged pinned v3 controller:
`metabric_matched__expression__r01f01__pv_horseshoe__full`, with
`--max-new-cells 1`. Its detached wrapper, invocation, logs and typed returns
are under
`~/bayes-cox-runs/original-extension-recovery-20260930-v3/captures/worker05_ramp1/`
and its `refits/` attempt. The
[portable launch receipt](recovery/2026-09-30-third-extension-recovery-launch.json)
binds the plan and capture hashes. The worker and child acquired their expected
exclusive claims; no other numerical worker was active at launch. The wrapper
and fitting child returned zero, the cell and new trace passed hash and
identity checks, and an independent repeat of the official non-timing
scientific comparison matched the original. Original posterior-array equality
remains unavailable because the original trace bytes are missing. The
[third-refit receipt](recovery/2026-09-30-third-extension-recovery-refit.json)
binds the returns and comparison; it is not a completed grid or remote result
release. Three of 21 affected refits are verified; 18 remain. The
`--max-new-cells 1` ramp stopped with no active claim or worker. At launch the
Mac APFS control volume had about 42 GiB free (above the controller's 10 GiB
gate), memory pressure reported 64% free, and the SSD APFS image was mounted.
At the 20:34 UTC post-test check, the Mac had 36 GiB free, 12.7 GiB swap in
use and 35% reported memory free; Storage Management and FileProvider were
also consuming substantial CPU. No next fit was launched under that host
pressure. Recheck before any new producer. Keep SSD980 attached.

## Second monitored recovery fit — completed 2026-09-30, 14:03 UTC

After the open macOS Storage Settings window closed, observed swap-outs fell
to zero over ten seconds and free memory rose above 70%. A single new
write-once refit started under the same pinned v3 plan and controller: worker
4 with `--max-new-cells 1`, targeting
`metabric_matched__expression__r01f01__bayesian_horseshoe__full`.
Its wrapper and child are captured under
`~/bayes-cox-runs/original-extension-recovery-20260930-v3/captures/worker04_ramp1/`
and the corresponding `refits/` entry. The wrapper and child returned zero by
14:03 UTC, the cell and both new posterior traces passed hash and identity
checks, and the official non-timing scientific comparison matched the saved
original. The [second-refit receipt](recovery/2026-09-30-second-extension-recovery-refit.json)
binds those local records. The original posterior arrays remain missing, so
exact sampled-array equality cannot be claimed. This cell belongs to the fixed
92 selected reproduction identities; its old reproduction entry has no trace
or receipt, and a fresh recovered-source binding remains required. The
one-cell worker-4 ramp stopped cleanly. Two of 21 affected refits are now
verified, 19 remain, and no numerical worker or recovery claim was active at
the 19:50 UTC review.

The separate assembly adapter is documented in
`docs/extension_recovery_assembly.md`. Its read-only inspection reports two
completed comparisons out of 21; preflight and assembly remain gated on all
21 successful refit receipts and the six complete worker returns. The pinned
v3 numerical controller is unchanged. The adapter's proof and claim guards
passed against tests and the first real refit. The full locked-environment
suite passed 1,040 tests with 9 skipped and 288 subtests. No recovered run
has been assembled.

## Recovery status — 2026-09-30, 12:52 UTC

The first of 21 separate recovery refits finished at 12:31 UTC. Its captured
wrapper and fitting child both returned zero, the cell and new posterior trace
verify, and the official non-timing scientific comparison matches the saved
original. The original missing posterior arrays remain unavailable for exact
sample comparison. The `--max-new-cells 1` ramp stopped worker 3 cleanly;
there is no numerical worker or live recovery claim at this checkpoint. The
[portable first-refit receipt](recovery/2026-09-30-first-extension-recovery-refit.json)
binds the local return and comparison hashes. Twenty affected refits and all
411 initially absent extension cells remain; no complete grid is certified.

The host's unrelated Storage Management and File Provider processes are
currently consuming high CPU while swap use grows past 19 GiB. Keep numerical
dispatch at one monitored worker only after swap-out activity settles; do not
scale the six shards on this host yet. Review also found that the pinned v3
controller's `assemble` command imports an identity verifier that is absent
from sealed production commit `119476f`. Do not invoke that command. A
separate reviewed assembly adapter is required; the pinned refit controller
and completed attempt remain unchanged.

## Monitored recovery launch and SSD storage — 2026-09-30, 12:10 UTC

ADR-043's recovery controller is published at `1a92d5e`; its full locked test
suite passed 1,035 tests, 9 skips and 288 subtests, and focused lint passed.
The fresh no-launch plan at
`~/bayes-cox-runs/original-extension-recovery-20260930-v3/plan.json` strictly
checked 1,193 intact cells/traces, the 21-cell and 411-absent rosters, matched
data, locked environment, exclusive claims and an exact original manifest.
At 12:09 UTC a single monitored, full-budget recovery fit began: worker 3,
`--max-new-cells 1`, for
`metabric_matched__expression__r01f05__bayesian_horseshoe__full`.
Its captured wrapper, invocation, logs, claims and typed return are under
`~/bayes-cox-runs/original-extension-recovery-20260930-v3/captures/worker03_ramp1/`
and the corresponding `refits/` entry. The fit is not yet a verified result;
do not start another producer for this cell or remove the SSD while checking
the incident evidence. The controller stops the worker after this one new fit
for resource and scientific comparison review. An interrupted attempt remains
visible and requires a separately reviewed archived retry; no automatic
overwrite is permitted.

The owner asked to reduce Mac storage. The two 30 September internal backup
sparsebundles were rechecked file by file against their byte-identical SSD
originals (1,339 and 2,759 files), then detached. The SSD originals are now
mounted read-only at the same two `/Volumes/BayesCox*` paths; only the
redundant internal copies were removed. Local usage fell from about 80 GiB to
64 GiB, and Mac data-volume free space rose from about 95 GiB to 111 GiB.
The original extension run, sealed code, matched data, active recovery root
and 47 GiB V3 replay remain at their pinned APFS paths. The raw SSD980 volume
is ExFAT; do not move a live write-once root there. The verification and
removal receipt is
`~/bayes-cox-runs/interruption-recovery-20260930-v1/internal_image_copy_relocation_20260930.json`.
The portable [storage checkpoint](recovery/2026-09-30-storage-relief-checkpoint.json)
records the two source mounts and local receipt hashes.
A dedicated 300 GiB virtual, case-sensitive APFS sparsebundle was created on
SSD980 and mounted at `/Volumes/BayesCoxRecovery20261001`. Exclusive-create
and atomic-rename probes passed. It is reserved for future recovered and
corrected result roots; none of the pinned existing roots was moved into it.
Keep SSD980 attached and mount the image before any future job targeting it.

Current integration checkout:
`~/bayes-cox-runs/ravi-main-integration-20260929`. Current engineering validation
passed 1,040 tests and 293 subtests with zero skips at 15:34:34 UTC on
29 September. All 752 captured implementation files were unchanged;
repository-wide Ruff passed. The actual scientific reviews, numerical freeze
and corrected fits remain pending. Details are in the guarded-dispatch
integration-v3 record below.

macOS offloaded the original
repository's Git metadata and several documents to iCloud; scoped downloads
restored the metadata used by the frozen production worktree. The new clone
started from remote-verified `dc081c0`; its
pushed `f9f3d02` checkpoint matched all 349 implementation files in the actual
successful full-suite capture. The original repository and all original
numerical owners/evidence
remain preserved. The two original execution/code-guide variants have now
returned and were byte-preserved before reconciliation. Their useful root,
reporting and transfer details are retained in the resident guides alongside
the later incident safeguards. Recorded production-worktree Git checks returned
the expected `119476f` and a clean tree. All 141 files and four directories
in the original main checkout's eight edited files and 20 untracked entries
are now byte-preserved in a recovery archive. All untracked source/test/JSON
and compressed archive collisions match resident main exactly. Six older
document variants remain preserved. The source-only dependency audit found
that four live-route worktrees share original main's Git administration.
General Git synchronization was deferred while those owners were active;
no stash, fetch or merge occurred in that preservation step. At 14:55 UTC
on 29 September the
six disjoint documents were mirrored from remote-verified `a26d5a2`.
All six matched published bytes; 135 other scoped files, the 141-file backup,
six preceding published variants, 24 selected shared-Git administrative files
and 634 implementation files remained unchanged. Its actual zero-return
capture is retained in
`coordination/recovery/2026-09-29-generator-correction-document-mirror-v3.json`.

## Interruption recovery — 2026-09-30, updated 11:21 UTC

The six original extension workers and V3 pre-fit continuation are stopped;
their recorded PIDs are historical. The original run has 1,214 of 1,625 cell
JSONs (1,000 complete, 176 failed, 38 failed diagnostics), leaving 411
positions without a cell. A strict audit found 21 stored cells referencing 34
missing posterior traces. Those 21 records remain unchanged; 1,193 stored
cells passed their cell/trace hash checks. Six dead-owner claims and two
uncommitted trace files were copied, hash-verified and archived under
`~/bayes-cox-runs/interruption-recovery-20260930-v1/original_orphans/`
before the original claim paths were cleared. No original worker has restarted.

V3 sealed all 1,650 first-draw replay contexts and wrote its arithmetic
selector. Its input/reuse log stops at 1,536 of 1,625 cells; no completed
inventory or arithmetic result exists. Resuming it now would encounter the
missing original traces. Neither the old one-attempt owner nor its V3 child
has a recorded successful return. The five execution reviews, corrected
freeze, corrected fits, reporting and release remain pending.

The pinned expression source and regenerated matched parquet were restored
with their exact frozen SHA-256 hashes (`4470069455a4ed38ffed5d12513e468bbf5b9a57d66fa1162e7bd9a64889ab7a`
and `36ddcdc14d0bd76ee7c88d2c78fab2fab2039ed3819e5c70fd27b21c7b335971`).
Two missing numerical libraries were restored from their exact conda package
archives; the frozen environment verifier passed. SSD980 is mounted, while
both external sparsebundle originals remain detached and their byte-verified
internal copies are mounted read-only. Neither internal image contains the
missing traces. The local integrity list is
`~/bayes-cox-runs/environment-recovery-20260930-after-reboot-v1/missing_original_traces_audit.json`.
The portable [trace inventory](recovery/2026-09-30-host-interruption-trace-inventory.json)
records all 34 expected hashes without presenting them as repaired results.
The isolated frozen-code pilot under
`~/bayes-cox-runs/original-trace-reconstruction-pilot-20260930-v1/`
finished. Its fresh cell matches the saved non-timing scientific record under
the sealed reproduction comparator, but its posterior NetCDF SHA differs.
The wrapper returned 1 solely on this hash mismatch; its fitting child
produced a terminal complete cell. The original posterior arrays are missing,
so their equality to the new samples cannot be established. The pilot changed
no original file and is not one of the 21 accepted recovery refits. The
[pilot comparison](recovery/2026-09-30-original-trace-pilot-comparison.json)
records the hashes, comparison and limitation.

ADR-043/T-191 governs the next work. The exact 411 absent-cell identities are
frozen in the [absent roster](recovery/2026-09-30-original-extension-absent-roster.json);
verify that roster against the original run before new dispatch, then capture
all 21 affected fits in fresh write-once
roots under the sealed settings. Compare each official scientific record to
its saved original. A new recovered source run may inherit the 1,193 strictly
verified cells and those 21 fresh cells only after all comparisons pass; it
then fills the 411 frozen absent positions with one producer. Preserve every
terminal failed outcome. Rebind the fixed 92 selected reproduction checks and
V3's reuse/arithmetic inventory to that actual recovered source. V3's 1,650
sealed replay contexts remain distinct evidence, but its 1,536-cell partial
inventory cannot certify the new source. Do not relaunch the interrupted
one-attempt wrapper or treat saved cell JSONs alone as complete evidence.

## Next action — validate the catalytic generator correction

ADR-040/T-190 records corrective work after the observed synthetic-rank
failures. The original numerical programme is paused at the interruption
checkpoint above; no corrected numerical run has started. Preserve its frozen
inputs and saved cells. Training-only generator preflight is complete across
all 825 catalytic jobs and every WME inner split. Independent first-draw
replay is complete; the reuse/refit inventory and arithmetic are pending.
Original accepted and failed outcomes are retained only when complete
inputs/model/fit/evaluation identity is proved.

The preserved proposal is
`coordination/recovery/2026-09-29-generator-correction-proposal/PROPOSAL.md`.
Its four original files match the external preparation bytes and its five
source-document bindings match base commit `16fabf1`. It is a historical
pending proposal, not a corrected method freeze, preflight result or fit.
The candidate method is bounded rejection on synthetic rank only, preserving
the original first draw. Conditioning changes its sampling law; a separate
addendum and actual method/implementation review are required before fitting.
Existing source and private transfer checks do not certify corrected evidence.

The active candidate is `src/pipelines/extensions/correction_generator.py`;
the real preflight entry point is
`scripts/catalytic_correction/run_preflight.py`. The candidate's 17 focused
tests and the runner's 25 injected tests passed. Independent source reviews
found no material defect. Optional processor restoration matches original
clinical, singleton and selected-gene proposals exactly; complete training
provenance is independently bound by the controller. The prospective cap is
256 whole proposals, original seed first, with rank-only retry seeds specified
in `config/catalytic_correction.yaml` and
`docs/protocol_addendum_catalytic_correction.md`. The candidate, recipe,
preflight-runner, selective-fit-contract and independent-arithmetic preparation
receipts are preserved with their original bytes in five dated recovery
archives. Full locked-environment `make test` passed 391 tests and 21 subtests;
schemas and Ruff passed. The compact verification record is
`coordination/recovery/2026-09-29-generator-correction-integration.json`. These are
implementation/preparation evidence, not actual preflight results or a
corrected fit freeze. See
[execution instructions](../docs/catalytic_correction_execution.md).

The real preflight started at 2026-09-29 06:22 UTC from clean detached commit
`cc231a0daed2614a087e9889e5d93556351a7fc2`, which is pushed and remote-verified.
PID 81194 used one low-priority worker and one numerical thread and has exited. Its output is
`/Volumes/BayesCoxExtensions20260928/correction-20260929/preflight_v1`; the
separate launch receipt is `preflight_v1_launch.json` in its parent directory
and logs are in the sibling `worker_logs` directory. Completion accounts for
all 1,650 contexts: 1,400 accepted the original first draw and 250 accepted a
rank-conditioned redraw, with no terminal outcome. The largest accepted
attempt index was 87. Root's actual saved-record audit passed at 09:05 UTC:
12,446 artifact bindings (2,309,258,335 bytes), all receipt/seed histories and
118 original input bindings verified; there were no within-context retry-seed
collisions or omitted training categories in accepted proposals. These are
training-input feasibility results, not optimizer, MCMC or reuse certification.
Redraws touch 168 outer identities; this is not an actual refit count.
The complete-preflight verification JSON and 18-member metadata/audit archive
are in `coordination/recovery/2026-09-29-generator-correction-complete-preflight-*`.
The full proposal arrays remain on APFS and must be included in the final
private release. The retained first root audit attempt incorrectly fixed
synthetic M at 1,000; the passing audit follows the unchanged source formula
`max(1000, 4*p)`, including M=2,108 for p=527. No scientific evidence changed.
Do not duplicate the completed audit or edit its source checkout.

The independent arithmetic helpers are integrated at
`scripts/catalytic_correction/{independent_arithmetic,bound_arithmetic}.py`.
Their 29 synthetic tests pass using three pinned historical Git blobs rather
than machine-specific source paths. Actual changed-input arithmetic remains
pending the complete preflight and independently reviewed reuse inventory.
The full locked suite with these integrated helpers passed 420 tests and
21 subtests; schemas and Ruff passed. Its separate compact receipt is
`coordination/recovery/2026-09-29-generator-correction-arithmetic-integration.json`.

The complete first-draw/reuse inventory runner, changed-input arithmetic
coordinator and selective-fit controller are now integrated. Their focused
injected tests passed 61, 35 and 37 tests respectively. The reviewed replay
and fit runtime bytes are retained unchanged alongside their sealed recovery
archives; test paths are portable. The separate arithmetic source review
records the resolved interpreter, receipt-binding, coverage and checkpoint
findings. These are implementation checks. Actual replay, arithmetic, the
five bound execution reviews, corrected freeze and pilot remain pending.
Original pending ownership is a launch barrier, never a reason to select a
smaller pilot. The pilot uses the largest training matrix in each specified
model/setting/gene-budget group under the unchanged four-chain budget.
The full locked suite with these integrations passed 553 tests and 57
subtests; schemas, exact 259-package verification and Ruff passed. All 157
original source/build/lock bytes are unchanged. Both integration test
attempts are retained; the first exposed a test-isolation issue, fixed by
checking tool imports in a fresh process. The compact receipt is
`coordination/recovery/2026-09-29-generator-correction-execution-integration.json`.

The first detached pre-fit continuation was launched at 2026-09-29 07:48 UTC,
PID 97059. It verified PID 81194's exit and complete, byte-bound
preflight evidence with no remaining live claims. At 08:55 UTC it started the actual
independent first-draw/reuse pass and complete changed-input arithmetic,
serially, from clean detached pushed commit `d332013`. It stops before the
five execution reviews, corrected freeze or pilot. This attempt later exited
during the storage incident recorded below; it is preserved, not the current owner.
Its code is `scripts/catalytic_correction/continue_prefit.py`; the live
external helper is separately pinned and must not be edited. The APFS parent
contains `continuation_v1_request.json`, `continuation_v1_launch.json`,
`continuation_v1/` and sibling `worker_logs/continuation_v1.*` logs. Failure
or an incomplete upstream stage is retained and stops advancement.
Source-only peer review and 12 injected guards passed; neither constitutes
actual completed replay or arithmetic. At 09:07 UTC, 19 independent first-draw
contexts were recorded; whole replay and arithmetic completion remain pending.

ADR-041 prospectively fixes selected reproduction to the sorted union of
the original 92 repeat-one/fold-one identities and input-selected pilots.
Freeze the actual selection and its supplied scope review before any
corrected score. Original numerical receipts may wait for their existing
owner; byte agreement does not substitute for actual producer/refit proof.

The reviewed freeze builder, serial pre-fit continuation, mixed deep verifier
and selected reproduction controller are integrated with unchanged sealed
runtime bytes. Freeze and verification require the current inventory,
definition, selector and complete 1,650-context arithmetic binding. Selected
reproduction checks the actual external pre-stage numerical producer separately
from the later official cached comparison, retaining unavailable provenance as
pending. A terminal pending-source envelope may acquire a separately reviewed
finished-source snapshot without mutation or a second generator replay.
The full locked suite passed 727 tests and 57 subtests with no skips; exact
259-package environment, schemas and Ruff passed. All 157 original source/
build/lock bytes remain unchanged. Validation history retains the earlier
fixture-isolation failure and capture-path failures. Its compact record is
`coordination/recovery/2026-09-29-generator-correction-verification-reproduction-integration.json`.
These are implementation checks; actual correction evidence and completion
remain pending. Correction-aware reporting/QA and receiving transfer adapters
are being prepared separately before use.

The separate read-only selected-reproduction receiving verifier is integrated
at `scripts/catalytic_correction/receiving/verify_restored_reproduction.py`.
It preserves historical JSON paths with explicit trusted receiving mappings,
checks all three completed evidence routes, actual producer/child/environment
proofs and stored science/sample/terminal arrays, and writes only a fresh
external verification directory. It cannot dispatch, resume or repair work.
Original sealed runtime bytes and all 42 preparation files are preserved;
portable integration tests passed 65 checks and 13 subtests. The full locked
suite passed 792 tests and 70 subtests with no skips at 09:23 UTC; environment,
schemas and Ruff passed, and all 157 original source/build/lock files remain
unchanged. Compact record:
`coordination/recovery/2026-09-29-generator-correction-receiving-integration.json`.
This is tested implementation, not an actual fresh receiving check or release.

At about 09:44 UTC the backing SSD980 mount became unavailable and the
mounted correction image returned I/O errors. The original pre-fit
continuation and replay process exited; no exit code was recovered or
invented. Root preserved an unchanged, byte-verified copy of all 1,339 disk
image files (5,559,317,478 bytes), normally detached the stale image and
reattached it read-only. The APFS check passed with exit code zero. All
12,446 preflight artifact bytes, all 1,650 completion-bound context receipts
and 76 complete replay contexts were independently rehashed successfully.
One uncommitted next child and its claims remain in the old attempt.

The second pre-fit attempt launched continuation PID 29120 at 09:55 UTC on
29 September through owned capture PID 29118. Its witness root was
`/Volumes/BayesCoxTransfer20260929/correction-20260929/reuse_v2`.
At 22:20:35 UTC, its wrapper ended with actual return code 1: an I/O error
occurred while hashing `reuse.stdout.log` after the reuse subprocess returned.
No child return-code receipt was published, so the subprocess return code is
unknown. Neither replay completion nor arithmetic was published. Preserve
this attempt, its partial child, claims and logs under
`~/bayes-cox-runs/extensions-20260928/correction_storage_incident_20260929_v1/`
and the external transfer image; do not infer a scientific failure from the
wrapper error.

At the second storage incident, both external APFS image volumes were
unmounted while SSD980 remained mounted. Both original sparsebundles were
normally detached and left unchanged. Complete internal backup copies were
verified file by file against the detached originals: 1,339 files and
5,559,317,478 bytes for the original preflight/code image, and 2,759 files
and 11,516,716,006 bytes for the transfer image. Only the internal copies are
mounted read-only. The old copy is at its historical
`/Volumes/BayesCoxExtensions20260928` path for exact input-path bindings;
the transfer copy is at `/Volumes/BayesCoxTransferRecovery20260930`.
Recovery capture and clone-copy receipts are under
`~/bayes-cox-runs/correction-storage-recovery-20260930-v1/`.

The independent read-only audit in
`~/bayes-cox-runs/correction_transfer_clone_receipt_audit_20260930_v1/`
has sealed receipt SHA-256
`5240addb8523c92fcd9e4cbb795bd9a872bffe8e2c74d982fa6bfed7cf40eb76`.
It accepted all 1,592 complete top-level replay receipts, including their
bound child/input artifacts and recomputed first-draw assessment, with zero
recorded failures. Exactly 58 of 1,650 contexts still lack a top-level
receipt. One partial context has no completion receipt and is not reusable.
The separate V3 staging returned code zero and byte-verified 1,592 complete
contexts (6,370 files; 2,701,809,549 bytes) into
`~/bayes-cox-runs/correction-storage-recovery-20260930-v1/reuse_v3`.
Its `reuse_v3_staging.completed.json` records the audit binding and exclusion
of the partial context and old claims. V3 detached capture PID 27135 and
continuation helper PID 27137 launched at 03:00:40 UTC on 30 September from
`~/bayes-cox-runs/correction-continuation-v3-owner-20260930-v1/`.
The frozen request SHA-256 is
`ab38b3ecf6dbfe729e65ea11722945dbcb291b32fac05cdfd2ea96596dba7b9a`.
Its witness is the internal
`~/bayes-cox-runs/correction-storage-recovery-20260930-v1/reuse_v3` root;
new arithmetic and orchestration outputs are sibling `arithmetic_v3` and
`continuation_v3` directories under the same recovery root.
This was the V3 launch state. The replay later sealed all 1,650 contexts,
but the continuation stopped during input/reuse inventory as recorded in the
current interruption checkpoint. No arithmetic, scientific freeze or final
result is certified by recovery, staging or launch.

At 02:44 UTC on 30 September, all six original workers were alive and the
original run held 1,188 of 1,625 cells: 979 complete, 174 failed and 35
failed diagnostics. About 27 GiB of internal space remained at 02:51 UTC.
Check internal `df` every 10–15 minutes during further V3 or original writes.
Do not start corrected fitting at 15 GiB or less free, or any further
write-heavy stage at 10 GiB or less free. These are recovery-space guards,
not scientific gates. The remaining 437 original cells have a planning
estimate of about 19.8 GiB but no proven upper bound. Do not duplicate the
original workers; keep SSD980 attached for the eventual transfer, without
mounting or writing either original sparsebundle.

Correction-aware reporting/QA is integrated at
`scripts/catalytic_correction/reporting/`. Its reviewed runtime and copied
historical support bytes are unchanged, and 51 portable checks plus three
subtests passed. Actual reports, figure inspection and receiving replay still
require completed mixed evidence. Independent review found two transfer
preparation defects: unmarked injected mixed-verifier capture and unrestricted
filtered capture-group roles. The original preparation and finding record
are preserved. The separately reviewed v2 transfer implementation is now
integrated at `scripts/catalytic_correction/release/`; its full 100-file
preparation is retained and 68 portable checks plus 35 subtests passed.
Actual source mixed verification must use its `capture_mixed_source.py`.
Whole evidence trees retain failed/orphan files; only four specified capture
roles may be flat four-file groups. Independent follow-up review found no
remaining material defect within that implementation contract.

The expanded full locked suite passed 911 tests and 108 subtests with no
skips at 11:22 UTC. All 349 captured implementation files were unchanged
through the successful check, and all 157 original source/build/lock files
were reverified unchanged. Exact 259-package verification, schemas and Ruff
passed. The default-cache run retained the correct original-source path and
unchanged numerical, compiler and BLAS settings. Both earlier cancelled
test attempts and their genuine nonzero returns remain preserved; they are
not scientific fit failures or successful checks. The 208-member validation
archive retains the actual commands, source captures, logs and diagnostic
limits. Compact record:
`coordination/recovery/2026-09-29-generator-correction-reporting-release-integration.json`.
This validates implementation, not completed scientific results or a release.

At 11:28 UTC the new replay had 219 independently verified first-draw
receipts; original production still had the 1,095 outcomes recorded above.
The unchanged partial first replay remains retained in the forensic image.
The curated storage-incident preparation contains 1,384 prospective retained
files, including all 1,339 forensic-image files. Root checked the small-file
bytes and exact saved inventory mapping; a current image rehash and actual
staging remain required. Its 52-member archive preserves the checkpoint
error/correction and dated partial logs without unfiltered global user paths.

A separately reviewed read-only Darwin observer registered all nine existing
original processes at 11:16 UTC. Observer child PID 48621, captured by wrapper
PID 48620, records genuine future kernel exit statuses without controlling
the jobs. Its launch/request/identity/subscription evidence is retained in
the 23-member dated archive. No exit event or finished-observer receipt was
present at that snapshot. Earlier unavailable return codes remain unknown;
subscriptions and later exits do not supply numerical or comparison approval.

ADR-042 specifies separate per-entry I/O support if actual inherited
producer evidence is missing. The actual subset, location plan, adapter
adoption and any new original-law execution remain pending complete reuse
and producer evidence. Do not rerun all 92 cells automatically or copy a
new refit into an old historical root. Source and receiving release wiring
must bind any new adapter explicitly. Final private retention also includes
the unchanged 1,339-file forensic image with the stopped first replay attempt.
The separate 44-member per-entry I/O preparation and its ten-member
independent source review are archived; no material finding remains within
that contract. Its exact implementation is now installed at
`scripts/catalytic_correction/per_entry_io/`, with 54 passing portable checks
and 32 subtests. Full locked `make test` passed 965 tests and 140 subtests,
with no skips, at 12:35 UTC. Ruff passed. All 399 captured implementation
files, the prior 349-file checkpoint and all 157 original source/build/lock
files remain unchanged. The stalled original-fixture Git check completed
naturally after scoped metadata downloads; no test, numerical worker or
scientific setting was changed. Actual commands, raw diagnostics and root
archival lookup errors are retained in the separate validation archive.
This is implementation integration, not actual adapter adoption, a missing
subset or an approved location plan. Actual use must explicitly bind the
separate release wiring. The reviewed preparation
record is `coordination/recovery/2026-09-29-generator-correction-per-entry-io-reviewed-preparation.json`.
The integration record is
`coordination/recovery/2026-09-29-generator-correction-per-entry-io-integration.json`.

At 12:39 UTC the current replay had 323 independently verified contexts.
Original production had 1,103 stored outcomes: 908 complete, 169 failed and
26 failed diagnostics. This dated metadata checkpoint is not a completed
grid or corrected result. Internal storage showed about 83 GB free after
an earlier low reading; no further project files were relocated or deleted.
The free-space fluctuation's cause is unknown. The curated storage checkpoint
and both original/recovered guide variants are preserved in recovery archives.

The separately named `scripts/catalytic_correction/release_v3/` implementation
now retains its complete 233-file carrier, including all 196 predecessor
files. Its four runtime files have distinct pins; original v2, receiving and
per-entry source/preparation identities remain unchanged. Genuine source
controller/read-only captures bind the actual written selected pass, while
fresh receiving uses only the new read-only selected entrypoint and retains
the original mixed/reporting command gates. Whole distinct evidence trees,
all current/prior location plans and failed attempts remain mandatory.
Focused checks passed 33 tests and 17 subtests. Full locked make test passed
998 tests and 157 subtests without skips at 12:50 UTC; Ruff and schemas passed.
All 634 captured implementation files, the previous 399/349-file checkpoints
and all 157 original source/build/lock files are unchanged. Exact historical
logs and a source-delta patch retain their whitespace; other staged files
pass the diff check. Actual preparation, peer review, portable test review and
validation records are archived. Compact record:
`coordination/recovery/2026-09-29-generator-correction-release-v3-integration.json`.
This completes tested release wiring, not actual adapter/plan adoption,
source capture, staging, release or fresh receiving verification.

At 12:51 UTC the current replay had 342 independently verified contexts;
original production still had the 1,103 outcomes above. Before any corrected
pilot score, root must validate and freeze ADR-041's actual original-92/pilot
selection and supplied scope review. The five-review numerical freeze alone
does not enforce that additional selection gate. Current continuation stops
before fitting; no corrected score or selection-gate violation exists.
Predispatch engineering enforcement is integrated and tested; the actual numerical prerequisites remain pending.

At 13:22 UTC the current replay had 403 independently verified contexts.
Original production had 1,105 stored outcomes: 909 complete, 170 failed and
26 failed diagnostics. All nine original owners, the current continuation
and the exit observer remained present. This is a dated metadata checkpoint,
not a complete grid, numerical approval or release.

The guarded-dispatch design preserves the existing scientific pins and adds
ADR-041's actual selection and named scope review before pilot/remaining
fits. V1 remains preserved and unadopted after three counterexamples involving
input protection, numerical references in no-fit records and account-pass
bindings. V2 remains preserved and unadopted after independent probes accepted
contradictory original-reuse decisions.

V3 closes those gaps and is now integrated as reviewed engineering source at
`scripts/catalytic_correction/guarded_dispatch/`. Its full locked suite passed
1,040 tests and 293 subtests with zero skips at 15:34:34 UTC; all 752 captured
implementation files were unchanged. Repository-wide Ruff passed. All 634
preceding implementation files, 157 original source/build/lock files and
original scientific pins remain unchanged. The exact reviewed carrier and
portable fixtures, all prior failures, independent reviews and completed
validation captures are retained in
`coordination/recovery/2026-09-29-generator-correction-guarded-dispatch-integration-v3.json`.
The separately retained AST convention clarification leaves its metadata's
historical creation interpreter unknown; the actual tests use the locked
Python 3.11 environment.

Pilot/remaining fits must use `capture_guarded_dispatch.py`. The five actual
method, arithmetic, input-witness, implementation and freeze reviews,
corrected numerical freeze, ADR-041 selection/scope and named dispatch
adoption remain pending. First introduction refuses prior numerical attempts;
resume retains the original proof. Separately captured source and genuine
fresh receiving calls to `verify_guarded_dispatch_proof.py` remain required
before release completion. Existing release-v3 transports that history but
does not run those semantic checks. The prior design and exact checkout
backup remain linked from the checkout-preservation record.

At 14:43 UTC the read-only checkpoint found 582 independently verified input
receipts and 1,111 original outcomes: 914 complete, 170 failed and 27 failed
diagnostics. All 15 selected original/continuation/observer processes were
present. The 634 implementation files still equal the 998-test successful
capture, and all 20 original design source pins are unchanged. The compact
v2 review record retains actual captures and the non-adoption finding:
`coordination/recovery/2026-09-29-generator-correction-guarded-dispatch-v2-review.json`;
passing fictional tests do not certify actual dispatch or scientific results.

At 15:38:44 UTC on 29 September, the non-atomic metadata checkpoint had 707 of
1,650 independently verified first-draw receipts and 1,115 of 1,625 original
outcomes: 917 complete, 170 failed and 28 failed diagnostics. The actual
presence query returned zero with all 15 selected PIDs present. The 634
preceding implementation files and 20 original source pins were unchanged;
the parent capture also bound all 752 current implementation files.
This is a dated progress checkpoint, not a completed grid or numerical
approval. Its capture is retained with the document-validation checkpoint.

Use a specified full-budget pilot under that new freeze to measure compute
and execution before scheduling the necessary correction fits. Preserve its
failed outcomes too. Refresh dependent analyses/QA and verify a fresh remote
restore before declaring the corrected handoff complete. The original
clinical/robustness/sampler releases and unaffected comparators need no
restart. Do not promise a total completion time from the earlier short profile.

At 2026-09-29 09:07 UTC the original run had 1,092 stored cells. All six
production workers and the remaining pre-stage worker were active. Original
completion/final-analysis markers were absent. At 09:07 UTC, internal free
space was about 38 GiB and the mounted APFS image had about 195 GiB free.
These dated counts are checkpoints, not a live progress claim. Correction
evidence used that APFS image; see the current interruption checkpoint for
the present original-run and mount state.

At 08:50 UTC, 12 inactive duplicate compressed release/download cache files
were copied, independently rehashed and relocated to
`/Volumes/BayesCoxExtensions20260928/historical-archive-cache-20260929-v1/`.
They retain their original parent-directory basenames and total 2.690 GiB.
Global open-file and current helper-reference checks found no active use.
The source copies were removed only after both sets matched the historical
release hashes; external bytes were checked again afterward. Raw inputs,
results/traces, old restored evidence, historical manifests/checksums and
all numerical owners remain unchanged. The mapping and receipts are in
`coordination/recovery/2026-09-29-generator-correction-storage-verification.json`
and its 19-member recovery archive. Copy the explicitly mapped external
file back if an old compressed cache is needed; the remote baseline release
assets remain available. The conditional budget is not an exact future
allocation or certified selective-refit count. Refresh actual sizes before
final release/download/fresh-restore staging.

## Active post-hoc extension production — authorised 2026-09-28

The owner requested plan corrections and full verified code/results
implementation. ADR-039 refines ADR-038. Implementation, real author/CRAN R
fixture parity, pinned METABRIC preparation, 298 tests, coordination schemas
and Ruff have passed. The implementation is remotely pushed. Six disjoint
numerical workers began the 1,625-fit grid on this Mac from
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

Use the reviewed
`~/bayes-cox-runs/extensions-20260928/final_validation_bundle_preparation_v2`
for final bundle v3 assembly. It preserves every original v1 file and reuses
the pinned support gates/copier while adding the reporting preparation,
actual five-file tables, source replay and factual claim records. The source
capture records actual commands, zero exits and 111 current metadata/official
receipt hashes. The portable receiving driver keeps fresh replay receipts
outside immutable evidence and requires their pass before publication.
Its 43 synthetic metadata checks, 20 mocked capture/I/O checks, six syntax
checks and independent source reviews passed. The complete 22-file preparation
and root verification are preserved in the 27-member
`coordination/recovery/2026-09-28-extension-bundle-v2-preparation.tar.gz`.
Root verified all 359 historical files, six archived members, 20 new static
inputs and all 157 unchanged tested source files. No actual reporting/claim
invocation, completed support review or final bundle assembly has run.
The 2026-09-28 05:02:06 UTC checkpoint has 926 stored cells (774 complete,
140 execution failures and 12 diagnostic failures), with 276 clinical
METABRIC cells and no matched cells. There are still 66 candidate refits
and no official receipts. Numerical/coordinator ownership is unchanged.

T-180 is frozen: content hash
`50b5f30f697b633718078e18c0da54be297361f8b06aeaf95af32e12aa1c646f`.
No extension outer-validation result existed before the freeze. All
extension outputs are post-hoc and remain separate from the closed primary
record. The remaining gates are complete 1,625-cell accounting, deep
diagnostic/score verification, separate RQ2/four-family/DCA aggregates,
92 exact refits, rendering and actual PDF QA, verified reporting tables/source
replay, private release, fresh download/scientific restore/reporting replay,
and factual plan/handoff close-out. Original results remain
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

### Standing owner instructions (updated 2026-10-01)

- Submission-first scope (ADR-044) uses the verified baseline and completed
  separately labelled sensitivities. The post-hoc extension and correction
  remain active research with unchanged scientific gates, but no longer block
  the thesis. The paper is drafted later; no Q1 acceptance is guaranteed.
- Do not edit the Overleaf thesis until the owner instructs.
- Only one agent works on the repository at a time.
- Commit and push regularly at completed, verified milestones; confirm the
  remote branch contains the commit before reporting that it is pushed.
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

11. [ ] Non-blocking post-hoc extension experiments under ADR-044; T-180–T-186
    and T-189–T-191 in `TODO.md`. These analyses were not part of the completed
    baseline coordinator and do not gate thesis submission.
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

Owner-set planning target: the live thesis programme in `TODO.md` runs from
2026-08-17 to 2026-11-30. This 15-week schedule supersedes the earlier
26-week dates for project management without changing any frozen analytical
method or claim gate. Confirm the university submission deadline separately;
ADR-044 defers paper drafting and DOI work until after thesis submission.

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
