`audit_support.py` uses Python 3.11 standard-library modules to validate and stage
exactly 55 pinned supporting artifacts into a fresh `audit/` tree. These are
**audit and preparation evidence, not production completion or visual QA**.

The copied inventory is 28 executed-reference artifacts, 9 implementation and
training preparation artifacts, and 18 METABRIC provenance artifacts. The
original capture totals 39,229,087 bytes. It includes original synthetic R
arithmetic fixtures as reference audit inputs; those are not production results.
It excludes the installed R environment and synthetic/preflight release verdicts.

The production argument is the **code root containing `coordination/`**, not the
live run/results directory. The parent release stager must authenticate that
production checkout and its freeze to the fitted run before calling this helper.
This helper checks the freeze's canonical hash, all eight frozen metadata files,
and the production environment lock. It does not inspect production cells or
read the measured expression matrix, clinical records, or matched parquet.

From the directory containing the helper:

```sh
python3 audit_support_selftest.py
python3 audit_support.py \
  --production /path/to/authenticated-production-code/project \
  --reference-root /Users/macuser/bayes-cox-runs/extension-reference-20260928 \
  --preparation /Users/macuser/bayes-cox-runs/extension-preparation-20260928 \
  --target /path/to/fresh-release-stage/audit
```

Integration from `stage_extensions.py` after its fitted-run/source gates:

```python
from audit_support import stage_audit_support

audit_record = stage_audit_support(
    production, args.reference_root, args.preparation_dir, stage / "audit"
)
stage_record["audit_support"] = audit_record
```

No project utility imports are needed; the parent can call this after inserting
the analysis code root into `sys.path`. The function preserves each artifact's
bytes under `catalytic/`, `preparation/`, or `metabric/`, validates the full set
before copying, checks stable source identities/timestamps during reads, then
rehashes every copied file. It publishes by an atomic no-replace directory rename
on macOS or Linux. Symlinks, parent traversal, source-root overlap (including
macOS case aliases), changed sources, altered pins/domain links, and existing
targets fail. Failed temporary trees are removed. Use canonical paths if a
trusted OS alias such as macOS `/var` would otherwise introduce a symlink.

`audit_support_manifest.json` contains `schema_version`, `classification`, the
explicit false `production_completion_or_visual_qa_evidence` flag, `file_count`,
`total_bytes`, `category_counts`, a sorted `files` list with `path`, `category`,
`bytes`, `sha256`, and `binding`, and frozen production/domain `bindings`.
`content_sha256` hashes canonical JSON excluding that field. The return value
contains the manifest filename, its actual byte SHA256, its canonical content
SHA256, file count, category counts, total payload bytes, and classification.
The 55-file count excludes the manifest itself.

The 24 reference artifacts are bound to the exact production reference registry;
the other 31 artifacts have fixed capture SHA256 pins. Environment/full-test logs
join the production implementation receipt and freeze; the final training profile
joins the frozen profile. METABRIC download/audit/pair/supplement/commit/tree/LFS
evidence joins the frozen source and matched preparation reports. Original host
paths inside those reports remain documentary; the staged relative paths and
hash inventory carry the evidence on another laptop.

The parent separately stages the measured raw files and LICENSE, source report,
matched parquet/manifest, production/reproduction results, and final visual QA.
Later `--validation-logs` evidence is a separate optional parent-stager inventory,
not a replacement for the original frozen implementation receipt and not part of
these 55 files. This helper has no scientific model fits, result selection,
completion verdict, or visual-QA claim.
