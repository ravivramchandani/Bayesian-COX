# Reboot continuation audit

Read-only audit: 2026-09-27 07:54:42 UTC. Execution restarted once at
2026-09-27 07:51:46 UTC. This records successful continuation, not completed
results or passed scientific gates.

## Observed execution

Six detached robustness workers, PIDs 3362–3367, use the exact locked Python
and the unchanged frozen shard worker with worker IDs 0–5. Their observed
CPU usage was approximately 92–105%, and all six fresh logs showed sampling.
Supervisor 3372 was waiting on those same workers. Coordinator 3374 uses
sealed code, two reproduction workers, six later sampler workers and
`--robustness-supervisor-pid 3372`. Caffeinate 3376 follows coordinator 3374.

Reproduction driver 3693 is a child of coordinator 3374 and explicitly uses
`--selection all --workers 2 --resume`. Its fresh log recorded METABRIC
random survival forest repeat 1/fold 1 as `identical=True`, completing in
84.7 seconds. The checkpoint held 154 cells before restart. At report
creation, 155 reproduction cells and 551 robustness cells were stored;
the required reproduction and robustness completion records were still
absent. No traceback or runtime/value error was found in the fresh launch
logs at the audit snapshot.

## Preservation evidence

The restart receipt records exactly six released claims for missing
METABRIC cells. Their former worker/PID contents are preserved in
`/Users/macuser/bayes-cox-runs/logs/resume_20260927T075146Z/released_claims.json`.
The 551 completed-cell claims were retained at restart. Old PID numbers are
historical evidence, not current ownership.

All 20 preserved log/PID snapshots matched their recorded SHA256 hashes.
Their original files retained the preserved bytes exactly; append-only logs
were checked by their preserved prefix. Fresh worker logs have separate
filenames under `logs/resume_20260927T075146Z`.

The outer programme manifest byte hash remains
`a26bcb3c6e8da343b8576085c0d8a05f60c7b54d59d959fe159acd15310c2582`.
The frozen checkout remains at
`2e55c0b340f2acd8c52a11f2f76ba6d8cd67022b`, with only untracked explanation
and robustness result directories. Sealed checkout
`11f86ced8735b32767debb58f3cbbefbb5a7b8e6` remains clean. The launch receipt
records verification of 90 sealed code files. Source/environment preflight
was completed before launch; this independent audit did not rerun fitting
or change those sources.

## Scope

The original 450-cell evidence and its diagnostic, Holm and explanation
limitations remain unchanged. Sensitivity, final rendering, actual visual
QA and supplementary release gates are still downstream tasks. The
cross-laptop continuation review remains accurate: its counts explicitly
refer to the reboot checkpoint, while execution now proceeds locally under
the user's instruction to continue all tasks.

Primary receipt:
`/Users/macuser/bayes-cox-runs/logs/current_resume.json`.
Fresh coordinator log:
`/Users/macuser/bayes-cox-runs/logs/resume_20260927T075146Z/programme.log`.
This audit created only this review file and did not launch, stop or alter
any numerical job, evidence file or sealed source.
