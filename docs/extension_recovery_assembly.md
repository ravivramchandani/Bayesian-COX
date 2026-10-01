# Extension recovery assembly

The `assemble` command in `scripts/recover_extension_run.py` is retired. It
imports `verify_cell_identity` from the frozen production checkout at
`119476f`, where that function does not exist. Keep the numerical controller
byte-pinned to the active v3 plan and use `scripts/assemble_recovered_extension.py`
for assembly.

After all 21 refits have a matching scientific comparison and all six workers
have complete return receipts, run the adapter from a committed, clean checkout
in the exact locked environment:

```bash
python scripts/assemble_recovered_extension.py inspect \
  --control /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3
python scripts/assemble_recovered_extension.py preflight \
  --control /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3 \
  --recovered-run /Volumes/BayesCoxRecovery20261001/recovered-extension-run \
  --assembly-plan /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3/assembly_adapter_plan_v1.json \
  --production-git-dir /Volumes/BayesCoxRecovery20261001/frozen-git-metadata-119476f/.git
python scripts/assemble_recovered_extension.py assemble \
  --control /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3 \
  --assembly-plan /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3/assembly_adapter_plan_v1.json \
  --production-git-dir /Volumes/BayesCoxRecovery20261001/frozen-git-metadata-119476f/.git
```

The current sealed checkout still has the exact frozen files, but its linked
Git metadata is on an iCloud-offloaded directory. The independent Git clone
at the same commit lets the adapter check that unchanged worktree without
modifying its `.git` pointer. The adapter scopes this metadata only to the
production-tree check; it verifies its own published analysis checkout with
its normal Git metadata. On a machine where the sealed checkout's Git works,
omit `--production-git-dir`. Each refit invocation may come from a different
integration checkout only when its actual controller file matches the same
plan-pinned SHA-256; the assembly proof retains every source path and hash.

Preflight verifies the sealed production inputs, original 1,193 intact
cells and traces, 21 new refit cells and traces, child returns and official
scientific comparisons. It rebuilds all 1,625 identities against the original
manifest using the current verifier and records exact code, source, receipt
and producer hashes in a write-once assembly plan. Assembly rechecks that
plan, copies the 1,214 saved cells into a separate APFS run, and writes its
lineage and return receipt. The 411 originally absent cells remain pending
until the sealed six-shard runner completes them. Full-grid verification,
selected-cell reproduction and release checks follow separately.
The pre-continuation lineage is not a final 1,625-cell release lineage: the
sealed continuation must add a final supplement binding each of the 411 new
cells to its producer before any full-grid result is released.

After the continuation watcher has written `complete.json` and released its
claim, seal the final producer map from the actual six captured returns:

```bash
python scripts/seal_recovered_extension_lineage.py \
  --control /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3 \
  --run /Volumes/BayesCoxRecovery20261001/recovered-extension-run
```

The command refuses an incomplete capture, failed return, changed saved cell
or trace, or any active producer claim. It writes
`recovery_continuation.json` once beside the unchanged frozen manifest and
pre-continuation lineage. The portable verifier in
`scripts/extension_release/recovery_lineage.py` rechecks all 1,625 cell and
trace hashes and the exact 1,193/21/411 producer partition without opening
historical host paths. Extension staging and fresh scientific restoration
require this check for a recovered run. Staging also requires
`--recovery-control /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3`.
It recomputes the source proof, copies the 21 original/refit comparisons and
captured returns plus six continuation captures into `recovery/`, and verifies
their exact producer source files in a third `code/recovery.tar.gz` archive.
The receiving verifier repeats those checks against the transferred records
without opening the original Mac paths. The staging command may receive
`--production-git-dir /Volumes/BayesCoxRecovery20261001/frozen-git-metadata-119476f/.git`
to archive the sealed source using its independently verified Git metadata.
This lineage gate precedes deep finalization, 92 renewed source-bound selected
comparisons, rendering, actual PDF review and private release; it does not
replace them. Previously fitted unaffected selected cells may be reused only
after exact recovered-source cell, trace, scientific-content and sampled-array
checks. The three selected identities affected by missing refit traces need
fresh captured refits. Label prior and new numerical producers separately;
saved prestage markers alone do not prove ADR-041 worker return codes.
