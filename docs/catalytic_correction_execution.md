# Catalytic correction execution

ADR-040/T-190 specifies a separate post-hoc sensitivity. The original
extension run and its failure records remain immutable. The correction uses
the same models, optimizer and sampling gates, with bounded rejection only
after the exact original synthetic-rank guard.

Read [the addendum](protocol_addendum_catalytic_correction.md) and the current
[HANDOFF](../coordination/HANDOFF.md) before executing a stage. The preflight
does not fit models, select by held-out scores, approve reuse or create the
corrected numerical freeze.

## Training-input preflight

The runner accounts for all 825 catalytic outer contexts and all 825 WME
inner contexts. A WME inner proposal serves three tau candidates. It verifies
the original 118 input hashes, exact 259-package lock, manifest and reconstructed
job plan before loading training inputs. It fits the original preprocessing
within each current training set, after outer administrative censoring and
before any inner generation.

Use the committed runner and candidate from a clean pinned checkout. The
scientific source must be the separate clean production checkout at
`119476fef55b1eeb690527f234c1423440720d45`. Set these explicit paths:

| Variable | Required input |
| --- | --- |
| `CORRECTION_CODE` | Pinned correction-code checkout |
| `SOURCE119` | Clean original production checkout |
| `ORIGINAL_RUN` | Original extension run with its byte-pinned manifest |
| `MATCHED` | Matched parquet bound by that manifest |
| `RECIPES` | Verified extracted recipe inventory |
| `LOCK_PYTHON` | Exact locked environment interpreter |
| `PREFLIGHT_OUTPUT` | New external directory with sufficient free space |

The recipe archive is
`coordination/recovery/2026-09-29-generator-correction-inventory.tar.gz`.
Extract it into a new directory. The runner verifies its receipt and every
member before using `contexts.jsonl`. The original candidate archive is a
historical preparation record; the active candidate includes independently
reviewed optional processor-state restoration.

```bash
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1

nice -n 15 "$LOCK_PYTHON" -B \
  "$CORRECTION_CODE/scripts/catalytic_correction/run_preflight.py" \
  --source "$SOURCE119" --run "$ORIGINAL_RUN" --matched "$MATCHED" \
  --inventory "$RECIPES" \
  --candidate-module "$CORRECTION_CODE/src/pipelines/extensions/correction_generator.py" \
  --candidate-sha256 64963c33b067c3c67f5406037a3782820d99c1d687598a9536c72225e6939f11 \
  --correction-config "$CORRECTION_CODE/config/catalytic_correction.yaml" \
  --correction-addendum "$CORRECTION_CODE/docs/protocol_addendum_catalytic_correction.md" \
  --python "$LOCK_PYTHON" --cap 256 --restore-processor-state \
  --output "$PREFLIGHT_OUTPUT"
```

Use one low-priority worker. Processor restoration receives only selected
source columns after the controller independently fits the full original
training frame. It verifies the complete metadata and original feature order.
Every proposal still passes the original constructor, and the first seed and
draw order remain unchanged.

## Evidence and resume

The output manifest binds the source, raw inputs, inventory, runner, candidate,
addendum, configuration and environment. Each context records its training
membership, processor, real design and outcomes. Each proposal records its
seed, original constructor outcome, exact arrays, time scale and hazard,
rank/support measurements and separate legacy metadata. Failed original draws
remain present alongside accepted redraws.

Outputs use atomic no-replace publication and exclusive claims. A repeated
command verifies completed checkpoints and uses only verified attempt
archives. It refuses changed inputs, extra attempts, missing receipts and
partial files. `--recover-stale-claims` may archive only a proven dead claim
from the same host. Do not clear or edit claims from a live process.

`completion.json` means every scheduled context is accounted for. Read its
outcome counts and `all_contexts_feasible`; completion does not imply every
context accepted. A limited pass remains explicitly partial. Rank exhaustion
and nonrank failures are terminal recorded outcomes, never additional redraw
criteria. Measurement failure does not change the original constructor's
decision.

The stored-generator comparison is deliberately narrower than fit reuse.
Original inner arrays were not saved; independent original replay and complete
model/fit/evaluation witnesses remain required. Missing original cells wait
for their current workers. Neither this preflight nor the original release
receipts certifies corrected fitting, reporting or transfer.

## Independent original replay and exact reuse

`run_reuse.py` first requires a complete, byte-pinned preflight. It launches
one fresh original-import child per context, fits preprocessing on the full
raw training frame, calls the original generator once at the original seed,
and delegates its constructor guard. It independently compares all four
constructor inputs, complete processor metadata and the original returned
metadata or its absence. An accepted label or legacy JSON hash alone is
insufficient. No model, optimizer, prediction or metric is executed.

The same pass binds all 1,625 logical cells: ordered raw and encoded training
and validation inputs, censored outcomes, preprocessing, models, sampling,
seeds, evaluation rules and every WME inner dependency. Role receipts retain
both transparent canonical values. Saved successes and failures require exact
original cell and trace bytes. Missing or currently owned original outcomes
remain pending. Later finished-source snapshots are append-only; never edit
a frozen inventory or replace an original cell.

Use the clean pinned correction checkout and the same exact interpreter:

```bash
"$LOCK_PYTHON" -B \
  "$CORRECTION_CODE/scripts/catalytic_correction/run_reuse.py" --help
```

All source/helper/config/addendum/preflight hashes are explicit CLI inputs.
Use a new external output directory; the final stdout names the immutable
`inventories/<digest>/inventory.json` and its byte hash. The result also
contains `definition.json`, `arithmetic_selector.json` and
`replay/completion.json`. These files define arithmetic coverage and pilot
eligibility. The pilot scope includes changed accepted inputs with complete
role proofs even when an original worker still owns that cell. Its ownership
barrier remains in force before actual fitting.

## Changed-input arithmetic

The integrated `independent_arithmetic.py` independently evaluates the
catalytic kernel and analytic score, fixed/adaptive prior expressions and
weighted Breslow objective/score. Its reference loader compiles only the
byte-pinned original function definitions. It does not import a model,
construct prior data, generate proposals or compute rank.

`bound_arithmetic.py` requires a complete 1,650-context preflight and an
explicit, byte-pinned selector. The selector must be reconciled with the
independent reuse inventory before execution; a successful selected subset
does not establish complete changed-input coverage. Bayesian fixed and
adaptive outer inputs both require the original kappa initialization.

`run_arithmetic.py` is the complete accounting entry point. It requires all
1,650 actual preflight and independent replay receipts, the complete
1,625-cell inventory and an exact locked controller interpreter. Before
optimization it verifies selector labels and witnesses against their actual
receipts and performs independent base formula/gradient/unit checks. Changed
Bayesian outer inputs then use the untouched original kappa initializer once,
with its actual success/value/post-score predicate recorded. An original
guard failure remains a terminal optimizer outcome; adaptive optimum checks
remain pending for that outcome. A formula mismatch is unresolved and blocks
the corrected freeze.

The coordinator accounts for unchanged, changed and terminal contexts and
rechecks completed checkpoint semantics on resume without repeating a solver.
Its `accounting.json` and every bound artifact are required by the fit gates.
The lower-level `bound_arithmetic.py` remains available for explicit isolated
compute/validate calls. The complete coordinator exposes its required inputs:

```bash
"$LOCK_PYTHON" -B \
  "$CORRECTION_CODE/scripts/catalytic_correction/run_arithmetic.py" --help
```

An arithmetic or original optimizer failure retains partial records and a
failure receipt. It is not permission to select another proposal or change a
gate. Account for every affected context explicitly before a corrected freeze;
these helpers alone certify neither reuse nor production readiness.

## Assemble the reviewed freeze

`build_freeze.py` reads the complete preflight, independent replay, exact
reuse/refit inventory, transparent role proofs and actual arithmetic account.
It verifies the current inventory/definition/selector hashes and all 1,650
selector receipt bindings. The selector describes input requirements; it
does not itself approve or certify arithmetic. The builder's preparation
receipt is preserved in
`coordination/recovery/2026-09-29-generator-correction-freeze-builder-v2.tar.gz`.

The first operation emits an unapproved execution proposal. Finalization
requires five existing root reviews bound to its exact acyclic execution
digest; it cannot write those approvals. Both operations use a new exclusive
output directory and recheck every input. Consult the supplied schema and
explicit paths rather than inferring a freeze from a successful source test.

```bash
"$LOCK_PYTHON" -B \
  "$CORRECTION_CODE/scripts/catalytic_correction/build_freeze.py" --help
```

## Reviewed corrected fits

`fit_controller.py` retains its original `account`, `pilot` and `remaining`
implementation. Direct `account` remains unchanged. Pilot/remaining calls
must use
`scripts/catalytic_correction/guarded_dispatch/capture_guarded_dispatch.py`,
which delegates that unchanged controller only after actual selection/scope
and named adoption checks. The controller requires a separate reviewed
correction freeze and manifest, all original
input bytes, full preflight and arithmetic accounting, and five existing
byte-pinned reviews: method, arithmetic, input witness, implementation and
freeze. Each review binds the same acyclic execution definition and immutable
inventory. Preparation receipts cannot substitute for these reviews.

The prospective pilot uses the largest `n_train * p` matrix in each changed
input model/setting/gene-budget group, with lexicographic cell-ID ties. It
does not select by fit success or performance. Pending original ownership
means wait for the chosen cell. The child delegates unchanged original
scientific code with accepted byte-verified proposals, four chains, 2,000
tuning/draw iterations and every original diagnostic remedy and gate. A
changed WME inner input requires all nine tuning fits; outer-only changes
can reuse tuning only with complete identity evidence.

```bash
"$LOCK_PYTHON" -B \
  "$CORRECTION_CODE/scripts/catalytic_correction/fit_controller.py" \
  --freeze "$CORRECTED_FREEZE" --freeze-sha256 "$CORRECTED_FREEZE_SHA256" \
  --manifest "$CORRECTED_MANIFEST" --manifest-sha256 "$CORRECTED_MANIFEST_SHA256" \
  --python "$LOCK_PYTHON" --output "$CORRECTED_RUN" --phase account
```

An actual review of all retained pilot outcomes, resources and lineage is
required for `remaining`. Nonzero child execution preserves logs and blocks
automatic refitting of an existing attempt. Original optimizer/tuning and
diagnostic failures remain reportable failures. A controller accounting
receipt alone does not certify numerical verification, reporting or release.

## Pre-fit continuation

`continue_prefit.py` accepts an explicit byte-pinned request and a clean
execution checkout. It waits for the specified same-host preflight process
to exit, verifies its actual command identity, then requires all 1,650
context outcomes and removal of live controller/launcher claims. It executes
`run_reuse.py` and `run_arithmetic.py` serially with the same exact locked
interpreter and five numeric-thread variables set to one. Each actual
invocation, return code and raw log is retained. A nonzero or incomplete
stage stops advancement; it does not retry a failed numerical operation.

The continuation's final pre-fit receipt means actual replay/reuse and
arithmetic evidence is prepared. It creates no scientific review, corrected
freeze, pilot or fit. Only one continuation owns an output attempt. Inspect
the live launch/request/log bindings in HANDOFF before starting any process.

## Prospective corrected reproduction

ADR-041 fixes the selected scope before corrected scores: the sorted unique
union of the original plan's 92 repeat-one/fold-one cells and all
input-selected full-budget pilot cells. A separate supplied scope review
and immutable code/input/selection bindings precede execution.

`reproduction/run_reproduction.py` requires the separately reviewed actual
selection, correction freeze and fit manifest. Its sealed preparation,
88 injected guards and original validation attempts are preserved in
`coordination/recovery/2026-09-29-generator-correction-reproduction.tar.gz`;
a further fresh-process import check is integrated into the repository suite.
Run the controller from a clean pinned checkout with explicit paths:

```bash
"$LOCK_PYTHON" -I -B \
  "$CORRECTION_CODE/scripts/catalytic_correction/reproduction/run_reproduction.py" --help
```

The active original refit producer is the separately pinned external
`prestage_refits.py`, which delegates original119 scientific code. Its actual
new-refit log/owner/environment/input/return-code proof and the later actual
official cached comparison are separately required. Do not infer missing
historical producer evidence from a saved cell or comparison receipt.
Later source or numerical-evidence acquisition uses reviewed append-only
resolution records and never changes the frozen selection or prior proof.
The execution/resume controller is not a read-only receiving checker; a
separate path-mapped receiving adapter must preserve restored evidence.

ADR-042 permits separately reviewed per-entry I/O only after actual complete
reuse and producer checks identify genuinely missing inherited-original
proof. It preserves the frozen selection and requires fresh distinct
numerical/capture roots, actual execution and official comparison evidence.
The archived preparation and clean source review do not choose a subset,
approve execution or make release-v2 accept a new wrapper. Any adoption
requires separately pinned source and receiving release wiring.

The reviewed implementation is available in `per_entry_io/`. Before any
execution, an actual prospective location plan must bind every fresh numerical
and capture root. Capture, selected-controller ownership/comparison, producer
validation and receiving resolution must agree on that entry's declared
historical numerical root. The original sealed modules retain their original
pins; the wrappers have separate implementation pins. Installing or testing
these wrappers supplies neither a missing subset nor an approved location plan.

Changed accepted inputs require fresh full-budget refits with the identical
corrected freeze, seeds and gates. Unchanged reused outcomes require actual
original numerical-refit receipts and reviewed producer/source/environment/
input evidence; their actual scientific contents and posterior/sample-statistic
arrays are compared again. Missing evidence remains pending. Terminal input
outcomes receive independent replay of the applicable complete outer/inner
rank-only generator recipe and are labelled no-fit recipe reproduction.
These routes are separately accounted for. No byte audit becomes a numerical
refit, and the selected union does not claim an all-grid numerical rerun.

## Mixed verification and reporting

The separate read-only selected-reproduction receiving entry point is
`receiving/verify_restored_reproduction.py`. Supply a byte-pinned receiving
bindings file, the same locked interpreter and a new external output path.
Its [contract](../scripts/catalytic_correction/receiving/interface_contract.json)
requires trusted complete tree/file inventories and explicit historical-to-
receiving maps. Historical documents are unchanged. The receiving checker
loads the exact sealed reproduction preparation, including its original
test-source pin, from its transported evidence role; adapted repository tests
do not substitute for that preparation. All three existing evidence routes,
actual execution proofs and stored arrays are rechecked. It never launches
missing numerical work, resumes a claim or turns a pending proof into success.
Capture its actual process exit code separately from its output receipt.
No actual receiving check is certified by implementation tests.

`verification/verify_mixed_extensions.py` requires all 1,625 original and
resolved corrected outcomes and the actual reviewed freeze. It independently
reconstructs all input roles, checks generation-use/tuning/seed/child lineage,
recomputes stored posterior/prior diagnostics and rescores complete forecasts.
Referenced traces, failed partial traces and orphan files remain accounted
for. It delegates the unchanged four-family, RQ2 and decision-curve reducers
to the pinned original scientific source and preserves baseline findings.

The verifier has its own mixed-lineage certificate. It does not inherit the
original extension certificate. Actual release-v2 source verification must
use `release/capture_mixed_source.py`, binding the unchanged ten verifier
sources/preparation, the locked interpreter, actual return code zero, raw
logs and completed outputs before `render_verified_mix.py` can render.
The older generic capture API alone does not supply release-v2's genuine
producer proof. Injection is test-only and cannot certify actual science.
Rendering leaves actual visual QA, selected reproduction, the reporting
sidecar and fresh private restoration pending. The exact tested runtime and
source-only reviews are preserved in
`coordination/recovery/2026-09-29-generator-correction-verification-v2.tar.gz`.
Restored input locations use explicit path bindings; immutable historical
paths and recorded bytes are preserved.

The final reporting and reporting-replay adapters require the completed mixed
certificate, selected reproduction, frozen descriptive comparisons and actual named
visual review. Their [contract](../scripts/catalytic_correction/reporting/interface_contract.json)
preserves all failed denominators and complete-pair requirements. Partial
comparisons report observed means without confidence intervals. The fixed
roster has 1,625 dimension rows, 123 descriptive comparisons and links to the
27 existing formal contrasts. Only a comparison with all 25 paired folds may
receive its existing corrected interval.

Before that actual review, `reporting/corrected_pdf_qa.py prepare` renders all
32 PDF pages, four indexed contact sheets and a blank review record. It
separately binds the six table
inventories. Root must inspect
every actual page at full size and the contact sheets before supplying the
required attestation; an implementation test or generated image supplies
no review. Source and fresh receiving reporting replay compare all four
deterministic reporting artifacts. Actual review evidence and genuine source
and receiving process exits are retained separately.

The complete 100-file `release/` v2 preparation is retained unchanged, including
the original preparation, review findings and every earlier failed capture
attempt. Its
[contract](../scripts/catalytic_correction/release/interface_contract.json)
requires genuine source/fresh receiving captures, complete distinct evidence
trees and actual reporting/review/replay proof. Whole trees retain failures,
orphans and empty directories. Only the four explicitly specified capture
roles may be flat four-file groups. Actual stage, package, remote download and
fresh receiving verification remain separate completion gates.

For ADR-042 per-entry evidence, use the separately named complete 233-file
`release_v3/` carrier and its
[contract](../scripts/catalytic_correction/release_v3/interface_contract.json).
Its controller/read-only source capture binds genuine process exits, raw
logs and the actual written selected pass. The current location plan and
all prior plans, distinct numerical/capture trees and failed attempts remain
explicitly retained. Its receiving entrypoint invokes only the new read-only
selected verifier; the original mixed and reporting command gates remain
unchanged. Original v2, receiving and per-entry preparation pins retain
their distinct historical identities. Installing four runtime files alone
is insufficient. Tested integration does not supply an actual missing
subset, plan adoption, numerical producer, source capture or receiving check.

Final private retention must include every file in the preserved 1,339-file
forensic sparsebundle, including the interrupted first replay and partial
child. The curated incident preparation supplies a prospective 1,384-file
mapping, exact saved inventory and dated partial logs; it is not a current
image rehash or a staged payload. Actual staging must recheck all source
bytes, regular-file/no-link status and destination collisions. The exact
checkpoint count error and later correction remain unchanged. Unfiltered
global user/app stdout is excluded with original hashes and invocation
bindings preserved. No standalone raw filesystem-check capture is available.

## Subsequent stages

The V3 guarded-dispatch carrier is integrated and tested engineering source. Its
41 fictional tests and independent 41-test/nine-case review passed; the
portable adapter is sealed. Exact receipt prefixes are `65db400…`, `a97d6a2…`
and `cbe9759…`. V1/V2, their failed checks and actual counterexamples remain
preserved and unadopted. V3 changes only the no-fit decision consistency
checks; all old scientific pins and predicates remain unchanged. Its full
locked suite passed 1,040 tests and 293 subtests with zero skips
at 15:34:34 UTC; all 752 captured files were unchanged and repository-wide
Ruff passed. Actual captures and reviewed-source bindings are in the
[integration record](../coordination/recovery/2026-09-29-generator-correction-guarded-dispatch-integration-v3.json).

Before pilot/remaining dispatch, root must supply the five actual method,
arithmetic, input-witness, implementation and freeze reviews, the corrected
numerical freeze/manifest, ADR-041 selection and named scope review, and the
separately reviewed guard request/adoption. The implementation review binds
the guard source/preparation before freeze; selection and request then bind
the finalized freeze without a digest cycle. The launcher is
`scripts/catalytic_correction/guarded_dispatch/capture_guarded_dispatch.py`.
Its first introduction refuses every previous corrected attempt, including
empty/orphan directories; resume retains the original selection and complete
capture history. Remaining keeps the original actual pilot-review gate.

Use `scripts/catalytic_correction/guarded_dispatch/verify_guarded_dispatch_proof.py`
separately in source and fresh receiving modes with externally reviewed
locations. Capture the genuine process return, raw logs and emitted receipt;
source proof must bind the staged history, and fresh proof stays outside the
immutable restored payload. Existing release-v3 transports the history but
does not execute these semantic checks. Neither engineering source adoption
nor semantic proof certifies scientific correctness or numerical completion.
See the [v2 review record](../coordination/recovery/2026-09-29-generator-correction-guarded-dispatch-v2-review.json)
for rejected history and the [preservation record](../coordination/recovery/2026-09-29-generator-correction-checkout-preservation.json)
for the exact checkout backup.

1. Independently verify original first proposals and enumerate exact reuse,
   changed inputs and unresolved outcomes, including all WME inner dependencies.
2. Verify kernel, kappa and weighted-mixture arithmetic on changed accepted
   inputs; record original optimizer failures without selecting a new proposal.
3. Freeze the reviewed method, implementation, complete input manifest,
   reuse/refit inventory and prospective full-budget pilot selection.
4. Execute and review the pilot under unchanged original budgets and gates;
   schedule only necessary correction fits with an explicit resource budget.
5. Verify fits, traces, metrics and reproduction; refresh inference, RQ2,
   decision curves and reports; perform actual visual QA.
6. Package original and corrected lineages in the private repository's release
   assets and prove a fresh remote restore before completing Ravi's handoff.

These stages retain every original failure and every new terminal outcome.
The original numerical workers and their postfit coordinator continue under
their existing ownership. Overleaf and paper/submission/DOI work remain
outside this implementation programme.
