# Extension PDF visual QA helper

`extension_pdf_qa.py` is an analysis-only helper. It does not change
the production run, reproduction run, PDFs or lineage. Use it only
after finalization has written the deeply verified 1,625-cell `completion.json`
and the final renderer has written all 32 PDF/PNG pairs.

Use the exact locked Python that has Pillow installed, plus Poppler's
`pdfinfo`, `pdffonts` and `pdftoppm` on `PATH`:

```bash
"$extension_python" scripts/extension_release/extension_pdf_qa.py prepare \
  --run "$extension_home/run" \
  --rendered "$extension_home/rendered_v1" \
  --renderer "$analysis_code/scripts/render_extensions.py" \
  --qa-dir "$extension_home/pdf_qa_v1"
```

Preparation checks the complete deep-verification marker, exact 32-figure
inventory and order, six exact CSV tables and their hashes/source lineage,
all 1,625 cell hashes, one-page PDF boxes and embedded fonts. It renders
every page with Poppler at 130 DPI, checks raster
readability and PDF/PNG aspect ratios, and writes four numbered contact sheets.
The `qa_inventory.json` and `review_template.json` files are write-once.
Preparation explicitly leaves visual QA pending.

Open every `page_renders/*.png` at full size and inspect the four
`contact_sheets/*.png` files. Check labels, title and legend readability,
clipping, overlap, missing symbols, empty panels, and unexpected axes or
linework. Copy `review_template.json` to `review.json`; fill the reviewer name,
timezone-aware review time, exact attestation sentence shown below, and one
`pass` or `fail` verdict for every figure. A failed figure needs an issue.
The template's `inventory_sha256` and figure order must stay unchanged.

`I examined every rendered PDF page at full size and the indexed contact sheets.`

Then issue the receipt:

```bash
"$extension_python" scripts/extension_release/extension_pdf_qa.py receipt \
  --qa-dir "$extension_home/pdf_qa_v1" \
  --review "$extension_home/pdf_qa_v1/review.json"
```

The command rechecks every bound file and writes
`visual_qa_receipt.json` exactly once. A failed review is recorded as failed;
make a corrected final render in a new directory and run fresh QA rather than
overwriting the old evidence. The receipt preserves the review form's hash,
the inventory hash, the run completion hash, six CSV hashes and every figure
verdict. The reviewer may be the integration agent recording a truthful
tool-assisted visual inspection; no visual pass is inferred by the helper.

The helper's absolute paths identify the reviewed checkout on this computer.
Remote packaging should include the script, inventory, page renders, contact
sheets, review form and receipt, and independently check their archive hashes
after restore. The generated synthetic fixture is explicitly `test_only` and
its receipt can never be a final evidence receipt.
