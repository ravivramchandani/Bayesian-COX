# Extension trace-recovery supervision

The V2-aware successor launched from separate clean Mac-local commit
`0c3f48a` on 2026-10-01. Its actual process and start are pinned in
`coordination/recovery/2026-10-01-recovered-extension-continuation-v2-launch.json`.
It waits for the V2 supervisor's 21 verified refits and six terminal worker
returns. While waiting, the recovered run and assembly plan do not exist and
no 411-cell continuation fit has started. The command below is its **existing
launch record**, not an instruction to start another copy while its V2 claim
or process remains active:

```bash
/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/python -I -B \
  /Users/macuser/bayes-cox-runs/ravi-extension-continuation-runtime-20261001/scripts/continue_recovered_extension.py \
  --supervisor-version v2 \
  --control /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3 \
  --recovered-run /Volumes/BayesCoxRecovery20261001/recovered-extension-run \
  --assembly-plan /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3/assembly_adapter_plan_v2.json \
  --capture-root /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3/continuation_captures/sequential-v2 \
  --production-git-dir /Users/macuser/bayes-cox-runs/frozen-git-metadata-119476f-v2/.git \
  --poll-seconds 60 --execute
```

The reviewed V2 supervisor was launched from a clean Mac-local checkout at
`7f8a2b2` on 2026-10-01. Its captured process and first two dispatches are
bound in `coordination/recovery/2026-10-01-sequential-recovery-v2-launch.json`.
It requires the separate fourth-refit salvage proof, preserves every V1
failure/claim, and runs the unchanged fixed controller from `/private/tmp`
with independently verified local Git metadata. Worker 0 has a zero terminal
return; worker 1's first missing fit was pending at the launch checkpoint.
The command below records the V2 invocation; do not start another copy while
`sequential_supervisor_v2.claim` or its process remains active:

```bash
/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/python -I -B \
  /Users/macuser/bayes-cox-runs/ravi-extension-recovery-runtime-20261001/scripts/supervise_extension_recovery_v2.py \
  --control /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3 \
  --capture-root /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3/captures/sequential-v2 \
  --production-git-dir /Users/macuser/bayes-cox-runs/frozen-git-metadata-119476f-v2/.git \
  --execute
```

The stopped V1 supervisor and successor below are historical instructions.
They cannot complete or certify this V2 sequence.

The original `sequential-v1` supervisor failed after the fourth numerical
child returned zero: its parent wrapper lost a usable current directory while
importing the official comparison library. The v1 successor and replay watcher
also stopped. Their retained claims and failure receipts are historical
evidence; the command below is the **original launch record and must not be
rerun**. The fourth fit has since received a separate captured no-fit official
comparison and a verified proof. See
`coordination/recovery/2026-10-01-fourth-refit-postfit-salvage.json` and the
latest `coordination/HANDOFF.md`. A fresh v2 supervisor is required for the
remaining 17 refits; it must retain the v1 failure and use a stable Mac cwd.

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
sequence.

The separate `scripts/continue_recovered_extension.py` can wait for that
supervisor's `complete.json`, then invoke the
[assembly adapter](extension_recovery_assembly.md) and the frozen production
runner. It writes a new recovered run, captures six worker exits, and checks
each fixed absent shard (45, 84, 40, 93, 62 and 87 cells). It never changes
the original run. Launch it only from a second clean, committed checkout; the
first supervisor's analysis checkout remains pinned until it finishes:

```bash
/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/python -B \
  scripts/continue_recovered_extension.py \
  --control /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3 \
  --recovered-run /Volumes/BayesCoxRecovery20261001/recovered-extension-run \
  --assembly-plan /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3/assembly_adapter_plan_v1.json \
  --capture-root /Users/macuser/bayes-cox-runs/original-extension-recovery-20260930-v3/continuation_captures/sequential-v1 \
  --production-git-dir /Volumes/BayesCoxRecovery20261001/frozen-git-metadata-119476f/.git \
  --execute
```

The successor requires 25 GiB free on its SSD run volume and 20 GiB on the Mac
before each worker. Its `complete.json` means 1,625 cells are stored and their
file, trace, seed and membership gates passed. It does not certify deep
diagnostics, complete-grid statistics, the 92 selected reproductions, final
producer-lineage supplement, rendered PDFs, or a private release. Those
remain separate gates. A nonzero return leaves the current capture and
`continuation_supervisor.claim` for audit; it never retries automatically.
