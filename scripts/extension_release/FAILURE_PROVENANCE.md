# Supplemental synthetic-rank failure provenance

The original failed cells are immutable. Their generator raised before it
returned synthetic metadata. `audit_rank_failures.py` reconstructs that
missing provenance in a fresh process using the exact fitted code and lock.
It captures the original generator's source frame and constructor arrays,
then invokes the unchanged original rank validator. It performs no model
fit, optimization, sampling or outcome scoring.

Use the latest clone's helper with the original production checkout:

```bash
"$extension_python" "$extension_tools/scripts/extension_release/audit_rank_failures.py" \
  --production-code "$extension_code" \
  --run "$extension_home/run" \
  --matched "$extension_home/prepared/matched_metabric.parquet" \
  --output "$extension_home/failure_provenance_v2"
```

`extension_tools` is the current Git clone; `extension_code` is the sealed
fitting checkout. The output must be outside production code/results.
The helper's exact bytes are part of each case binding. If those bytes change,
including a documentation-only edit, use a new output version and preserve the
earlier audit. The active host retains its partial `failure_provenance_v1` with
the original helper; the finished-grid audit uses the reviewed current helper
in a fresh `failure_provenance_v2`. Neither version changes the frozen generator.
The helper verifies fitted source hashes, memberships, seeds, outer
preprocessing and Python/NumPy/pandas identity. Restored code archives without
Git metadata are supported. Run it separately from a process that has already
imported another checkout's `src` modules.

Each case records its original cell hashes, reached inner/outer draw seeds,
training-state hashes, M/p, time scale/rate, categorical prevalence, numerical
rank and zero columns. Exact synthetic arrays use relative paths and NPY
without pickle. WME stops at its first failed inner draw; later unreached
draws are not written. If its outer draw failed, preceding reached inner
draws are retained. This reconstructs generation only; it does not rerun
the original inner optimizer fits.

Existing case files are reconstructed and compared byte for byte. Different
content fails rather than overwriting evidence. Content-addressed snapshots
retain partial checkpoints as failures arrive. Their classification is
`post_hoc_failure_provenance`, with `programme_completion=not_assessed`.
The complete-grid snapshot is selected only after all 1,625 source cells
exist. It is supplemental provenance, not original fit metadata or a remedy.

Supply the directory to the stager through `--failure-audit`. The shared
`failure_transfer.py` requires exact failed-cell coverage, source/helper
bindings and every retained array hash before and after copying. This is
separate from the 55 pinned preparation artifacts. The portable science
verifier replays the original generator into fresh temporary storage and
requires the same complete snapshot/array bindings without changing the
restored evidence.

Focused integrity and retained-array checks are available through
`selftest_rank_failures.py --sidecars <audit-directory>`. Cross-runtime or
cross-platform bit identity is not asserted; the fresh restore uses the
recorded Apple Silicon lock.
