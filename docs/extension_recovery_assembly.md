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
  --assembly-plan /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3/assembly_adapter_plan_v1.json
python scripts/assemble_recovered_extension.py assemble \
  --control /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3 \
  --assembly-plan /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3/assembly_adapter_plan_v1.json
```

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
