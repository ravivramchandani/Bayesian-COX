# Cross-laptop continuation and reboot recovery

The read-only reboot audit found no surviving numerical processes, 551 of 825
robustness cells and 154 of 450 reproduction cells. Robustness comprised
GBSG2 255, WHAS500 270 and METABRIC 26 cells; reproduction comprised GBSG2
150 and METABRIC 4 cells. The 75-cell sampler sensitivity had not started.
These are checkpoint counts from the reboot audit, not a completion claim.

## Code and runtime

The exact lock supports Apple Silicon on macOS 14 or newer. Python 3.11.15,
the locked packages and matching native HDF5 2.1.0 must be verified on the
receiving laptop. Windows, Linux and Intel macOS require a separately built
and verified lock; they cannot silently substitute for this frozen runtime.
See `docs/environment_lock.md`.

Continue the unfinished historical robustness run only from frozen commit
`2e55c0b340f2acd8c52a11f2f76ba6d8cd67022b`, with its unchanged inputs and runtime.
The refactored robustness runner rejects reuse of that unfinished legacy run.
The remaining reproduction, sampler sensitivity and rendering pipeline uses
sealed commit `11f86ced8735b32767debb58f3cbbefbb5a7b8e6`. Preserve Git history,
including methodological checkpoint `44b608572a5e1006a05ed5e3c4985471b2ba594d`,
and the original protocol, raw data, manifests and lock bytes.

## Moving evidence

Copy completed source results and partial checkpoints without changing their
bytes. The reproduction checkpoint records relative inventories, code hashes,
source hashes and runtime versions; its 154 saved cells can be verified after
relocation. Retain the internal file layout and source run names. Historical
robustness execution expects its confirmatory source inside the frozen project
at the recorded relative location.

The outer `programme_manifest.json` pins absolute `source_dir` and
`robustness_dir` paths. Moving those paths requires a fresh outer programme
directory and identity, while preserving the copied original evidence and
checkpoint records. Do not rewrite the old manifest to conceal relocation.
Record any new host's continuation provenance separately. With no sensitivity
cells yet stored, start that separate analysis with a fresh actual-host
manifest from the sealed code.

## Restart ownership

Transferred PID files and claims do not establish live ownership on another
host. At the reboot audit, 551 claims matched saved cells and six claims
matched missing METABRIC cells. Release only those missing-cell claims after
confirming every actual frozen worker is absent; retain completed claims and
old logs. The existing launcher truncates worker logs and PID files, so use
fresh restart filenames or preserve the originals first.

For an all-local restart, start six frozen shard workers and confirm their
actual command lines and PIDs before starting the supervisor. Pass the new
supervisor PID to the sealed coordinator. Reproduction automatically resumes
its checkpoint, verifies saved cells and submits only missing cells. Sampler
sensitivity starts after robustness; the original methods remain unchanged.

The original 450-cell confirmatory evidence, its diagnostic failures,
incomplete Holm family and failed explanation convergence gate remain
immutable. Separate post-hoc results cannot replace those outcomes. Student
access and delivery arrangements are owner managed outside the code.
