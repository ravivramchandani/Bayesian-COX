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

## Reviewed corrected fits

`fit_controller.py` accepts `account`, `pilot` and `remaining` phases. It
requires a separate reviewed correction freeze and manifest, all original
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

## Subsequent stages

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
