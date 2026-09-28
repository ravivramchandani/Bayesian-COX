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

The final reporting tables must also show p, p/n and events/p for every
planned cell, preserving unavailable predictor counts. Generate the separate
123-row descriptive catalytic-versus-comparator table from verified stored
predictions, retaining missing pairs and linking the 27 existing formal
clinical contrasts. Complete 25-pair rows use the frozen corrected 95%
interval; partial rows report their observed mean without that interval.
These descriptive rows add no test or multiplicity family.

The prepared reporting helper, fixed roster and instructions are retained in
`coordination/recovery/2026-09-28-extension-reporting-preparation.tar.gz`.
Actual invocation requires finished numerical, reproduction and figure-QA
evidence. Its five-file output and a successful source replay belong in the
final supporting bundle with their source and invocation records. After the
remote restore, run a second read-only replay using the restored extension
evidence and the separately restored original baseline. Keep that new receipt
outside the immutable restored payload and require it to pass before release
publication. The final receiving guide supplies the pinned invocation paths.
The reviewed bundle/capture source and filled receiving addendum are retained
in `coordination/recovery/2026-09-28-extension-bundle-v2-preparation.tar.gz`.

Distinguish execution failures before sampling from failed MCMC diagnostics.
In clinical METABRIC, a training category can occur only once and be absent
from the single frozen empirical-marginal synthetic draw. Its encoded column
is then zero and the full-column-rank check rejects that draw. The addendum
specifies no regeneration remedy. Preserve the cell, seed, error and missing
predictions; do not redraw until rank passes or count the cell as a diagnostic
failure. A later reconstruction of the rejected matrix is supplemental
failure provenance, not metadata saved by the original fit. Report its source
cell hashes and exclude unavailable pairs/curves under the existing rules.
Use [the supplemental failure procedure](../scripts/extension_release/FAILURE_PROVENANCE.md)
with the latest clone's helper and the original sealed production checkout.
Supply the resulting directory through `--failure-audit` when staging. Its
complete snapshot covers every frozen rank failure and remains separate from
the 55 preparation artifacts. The transfer gate checks its source/case/array
hashes; fresh scientific restoration independently replays the original
generator without fitting or changing failed cells.

Use [the visual-QA procedure](../scripts/extension_release/PDF_QA.md) on the
final 32 PDF pages and six lineaged CSVs. Its automated checks prepare full-
size page images and contact sheets but leave the verdict pending. A named
reviewer must inspect every PDF page and record each pass/fail finding before
the write-once visual-QA receipt can pass.
Staging and restoration also require the retained `review.json`, its exact
receipt/inventory bindings, all 32 passed verdicts, all page renders and four
contact sheets. The portable gate uses supplied paths and preserves the
original review claim.

Package code, inputs/source metadata, all attempted cells/traces, aggregates,
92 reproduction receipts/traces, plots/tables and actual QA in a new private
GitHub release. `scripts/extension_release/stage_extensions.py` checks the
complete cell, receipt, figure, table, source-license and visual-QA inventories
before assembling the transfer tree. It includes both exact Git code archives,
the measured cBioPortal source and its license, matched Parquet, all run and
refit traces, logs, rendered outputs and QA record. The source report and
preparation manifest must match their original freeze hashes, and the
matched Parquet must match both preparation and production. Every file
referenced by the freeze is checked in both code checkouts. Supply the full
ten-file measured-source directory to `--raw-source`; the fitting preparation
command downloads only the five files it needs. The release also preserves
the executed reference scripts, source/alignment audits and preparation logs
as 55 separately labelled audit files. Supply their original reference root
and preparation directory through `--reference-root` and `--preparation-dir`;
Supply all retained integration-validation versions through the separate
`--validation-logs` directory for this programme's final transfer. The support
helper rechecks their pinned hashes and domain links
before copying, then rehashes every copy and records its inventory digest.
The standard-library packer in
`scripts/extension_release/` creates bounded tar.gz shards and an exact
member/hash inventory from a stable, symlink-free staging tree; its verifier
requires the independently recorded canonical inventory digest. Include
checksums and an exact member inventory, then download and restore into a
fresh clone/directory before claiming Ravi has the full
extension evidence remotely. Public publication, paper drafting, DOI and
Overleaf changes remain deferred.

On this APFS Mac, use `--clone-staging` for an independent copy-on-write
transfer tree. It requires native `clonefile`, refuses existing files and
fails if the volume cannot clone; it never silently makes a full duplicate.
Copied bytes still pass the same hashes. Before packaging and restoration,
measure actual sizes/free space, including retained failed attempts. Perform
one fresh remote restore. The receiving-workflow free-space check includes all inventory file
bytes, the largest compressed shard, filesystem overhead and a 5 GiB
operating reserve. Once a complete fresh download matches the independently
recorded hashes, the task-created upload package is a recoverable duplicate
if space needs reclaiming; preserve the scientific source, staged evidence,
receipts and fresh download.

Download only `inventory.json` and `part-*.tar.gz` into the directory passed
to the generic verifier; it rejects extra release metadata in that directory.
Use the canonical inventory digest from the committed release receipt.
Extract the two trusted code archives into fresh directories outside the
restored evidence tree. They contain the original raw clinical data and
freeze inputs, so independent rescoring needs no original-host source path.
They contain no `.git` directory; archived code can verify evidence, while
new fitting still requires a clean detached Git checkout.

After transfer verification and code extraction, use the latest clone's
`scripts/extension_release/verify_restored_science.py` with `--production-code`,
`--analysis-code`, `--restored`, `--primary`, `--sampler` and `--robustness`.
It verifies the exact environment, frozen sources and all cells, recalculates
the three stored aggregates, and directly re-compares the scientific content
and actual trace arrays of all 92 saved refits. It launches no fits, repeats
the supplemental rank-failure reconstruction, checks every retained visual-
review artifact and preserves identical finalized files. Its optional new
`--report` must be
outside the restored evidence tree. The copied visual-QA receipt attests to
the original inspection; preserved host paths are provenance and do not
claim a second visual review on the receiving laptop. The actual extension
release tag and digest remain pending until all production gates pass.

Use [the receiving-Mac guide](extensions_restore.md) for the baseline dependencies,
filtered download, explicit disk preflight, source-archive extraction and latest
scientific verifier. The generic archive verifier does not enforce a disk budget;
the guide runs that check before extraction. Final tag/digest values remain
unavailable until the completed extension release is verified and published.
