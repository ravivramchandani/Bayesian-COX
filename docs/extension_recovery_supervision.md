# Extension trace-recovery supervision

The original v3 plan fixes 21 trace-incomplete cell identities and six worker
shards. `scripts/supervise_extension_recovery.py` waits for the active fourth
captured refit, then dispatches the remaining cells one at a time through the
unchanged, plan-pinned `recover_extension_run.py`. Each dispatch gets a new
capture directory with its real process return. The supervisor verifies the
saved cell, trace bytes, first-attempt child return and official non-timing
scientific comparison before moving to the next cell. It also records the six
terminal fixed-shard worker receipts. The analysis commit, verifier hashes and
supervisor bytes are pinned for the whole sequence. A final receipt call uses
the same one-cell cap after rechecking every attempt in its shard, then checks
that those attempts did not change. A mismatch, an active claim, a changed
code/input binding, insufficient space or an unmounted SSD stops the sequence;
there is no automatic retry or overwrite.

The supervisor uses the independent Git metadata directory only for Git checks
on the frozen production worktree. It does not modify the production checkout
or original extension result. Start it only from a clean, committed analysis
checkout, with the locked interpreter and the SSD mounted. The capture root
must be a new directory directly under the fixed controller's `captures`:

```bash
/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/python -B \
  scripts/supervise_extension_recovery.py \
  --control /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3 \
  --capture-root /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3/captures/sequential-v1 \
  --production-git-dir /Volumes/BayesCoxRecovery20261001/frozen-git-metadata-119476f/.git \
  --wait-capture /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3/captures/worker00_ramp2 \
  --execute
```

`start.json`, the per-cell `launch.json`/`return.json` and verification files,
and `complete.json` or `failure.json` are write-once local evidence. An error
leaves `sequential_supervisor.claim` in place for audit. Do not remove it or
restart a failed cell without reviewing the capture, active process and fixed
plan. Do not launch another recovery worker while this supervisor owns the
sequence. After `complete.json`, use the separate
[assembly adapter](extension_recovery_assembly.md) to preflight and assemble
the 1,214 stored cells. This is not the 1,625-cell extension release.
