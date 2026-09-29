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
