# Running the post-hoc extension programme

The primary programme is closed and remotely restored as documented in
[Ravi's handoff](ravi_handoff.md). The new extension specification is
[the frozen addendum](protocol_addendum_extensions.md), with a write-once
hash record in `coordination/extension_protocol_freeze.json`. It has 1,625
distinct planned fits, 90 reused full RQ2 anchors and 92 selected exact refits.
Its new results are not complete until all verification, reproduction,
rendering, actual visual QA and remote-restoration gates pass.

Use the exact Apple Silicon conda lock and verify it before fitting. Keep
one repository integration owner. Run production from a clean detached
checkout of the implementation commit, with outputs outside the checkout.
Do not run from a mutable development branch, change sampler settings,
combine manifests, overwrite failed cells or edit the primary outputs.
Set BLAS/OpenMP/Accelerate to one thread per worker. Start with six disjoint
workers on this host; resource settings affect scheduling, not the grid.
On a smaller receiving Mac choose fewer workers and monitor memory/disk.

The commands below use shell variables `extension_python`, `extension_code`,
and `extension_home` chosen for the receiving machine. Do not copy absolute
paths from another computer. Point `extension_python` to its verified lock
interpreter, `extension_code` to the sealed checkout and `extension_home`
to a new external directory. Run preparation and fitting inside the sealed
checkout.

```bash
"$extension_python" scripts/prepare_extensions.py \
  --source-cache "$extension_home/source" --output "$extension_home/prepared"

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  "$extension_python" scripts/run_extensions.py \
  --matched "$extension_home/prepared/matched_metabric.parquet" \
  --output "$extension_home/run" --workers 6 --worker 0
```

Run the same worker command for indices 1 through 5 concurrently, using
identical `--workers`, interpreter, code and inputs. Workers verify the same
manifest and write exclusive claimed cells. Re-running a worker strictly
verifies existing cell/trace hashes and continues only missing cells.
An interrupted claim or trace is preserved; check that its named process
is dead before archiving the claim/unfinished trace directory and retrying
the same cell. Never delete a completed failed outcome to obtain another fit.

For this long grid, `scripts/prestage_extension_refits.py` can use spare
cores while production continues. It imports the sealed checkout, verifies
the manifest and source hashes, and refits selected cells only after their
source checkpoints exist. It writes no final reproduction receipts. Use a
separate external reproduction directory and disjoint worker indices. The
official `reproduce_extensions.py` command below still runs after all 1,625
source cells exist; it rechecks scientific content and actual trace arrays
before issuing the 92 receipts. Avoid running the two drivers concurrently
against the same selected cell.

After all workers finish, use separately restored original, ADR-032 sampler
and robustness directories from Ravi's baseline handoff. The production
manifest pins every fitted source and input file. Finalization can use a
later clean analysis checkout with an independently corrected verifier,
provided `--production-code` identifies the original sealed checkout.
The verifier checks every production hash and allows only its own file,
the finalization script and the renderer to differ in the analysis checkout; it records
their hashes with the original production commit. Run finalization and
rendering from that analysis checkout. Run selected numerical refits from
the original production checkout so their fitting code matches exactly:

```bash
"$extension_python" scripts/finalize_extensions.py \
  --matched "$extension_home/prepared/matched_metabric.parquet" \
  --run "$extension_home/run" \
  --production-code "$extension_code" \
  --primary "$primary_run" --sampler "$sampler_run" --robustness "$robustness_run"

# Change to the sealed production checkout before this command.
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 \
  "$extension_python" scripts/reproduce_extensions.py \
  --matched "$extension_home/prepared/matched_metabric.parquet" \
  --source "$extension_home/run" --output "$extension_home/reproduction" \
  --workers 6 --worker 0

# Change back to the verified analysis checkout before this command.
"$extension_python" scripts/render_extensions.py \
  --run "$extension_home/run" --output "$extension_home/rendered_v1"
```

Repeat reproduction worker indices 1 through 5. Require all 92 receipts,
actual trace-array comparison, independent all-cell rescoring/diagnostics,
and complete grid accounting. The numerical completion file explicitly
leaves reproduction and rendering pending; separate receipts close those
gates. Rendering creates PDF/PNG pairs and lineaged tables, including the
conditional decision-curve pointwise intervals and support/exclusion rows,
but does not constitute
visual QA. Inspect each final rendered PDF page and preserve the QA evidence.
Reports must state diagnostic exclusions, incomplete families, conditional
decision-curve uncertainty, inherited clinical METABRIC duplicate-pair
exposure and upstream expression normalization. The original negative and
missing primary findings remain visible.

Package code, inputs/source metadata, all attempted cells/traces, aggregates,
92 reproduction receipts/traces, plots/tables and actual QA in a new private
GitHub release. The standard-library packer in
`scripts/extension_release/` creates bounded tar.gz shards and an exact
member/hash inventory from a stable, symlink-free staging tree; its verifier
requires the independently recorded canonical inventory digest. Include
checksums and an exact member inventory, then download and restore into a
fresh clone/directory before claiming Ravi has the full
extension evidence remotely. Public publication, paper drafting, DOI and
Overleaf changes remain deferred.
