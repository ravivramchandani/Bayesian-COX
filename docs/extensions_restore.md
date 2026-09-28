# Restore the post-hoc extension evidence

The original and supplementary baseline evidence is already released. The new
post-hoc extension evidence is a separate release and remains pending its final
verification and transfer gates. Restore the baseline first using `docs/ravi_handoff.md`.
Then, on your Apple Silicon Mac with the exact verified lock, obtain the extension
tag, canonical inventory digest and full production/analysis commits from the
committed extension release receipt. Publication is still pending; the template
below cannot yet download extension results. Download only its package inventory and
numeric shards, check available space, restore to a fresh folder and extract both
code archives outside that evidence folder. Use the latest clone's scientific
verifier with the original, ADR-032 sampler and robustness paths. It rechecks saved
results and all 92 refits without fitting; the retained visual receipt describes
the original review. Preserve failed outcomes and frozen files. Do not start
duplicate numerical workers while the active host owns the extension run.

The following is a **template for use only after publication**. Replace every
angle-bracket placeholder with the value from the committed release receipt.
Run inside the latest clone after the baseline handoff has restored its evidence.
The baseline paths below match that guide; change them if you chose other paths.

```bash
set -euo pipefail
gh auth status

RAVI_REPO="$PWD"
RAVI_ORIGINAL="$RAVI_REPO/reports/confirmatory/confirmatory_v1_confirmatory_cdcdcee84651"
RAVI_RESULTS="$RAVI_REPO/../ravi-programme-results-20260927"
RAVI_EXTENSION_TAG='<published-extension-release-tag>'
RAVI_INVENTORY_DIGEST='<canonical-inventory-sha256-from-committed-receipt>'
RAVI_PRODUCTION_COMMIT='119476fef55b1eeb690527f234c1423440720d45'
RAVI_ANALYSIS_COMMIT='8551d326b02bfe88915cfd9eb50c6ca8e5690e3a'

RAVI_PYTHON="$(conda run -n bayes-cox-clean python -c 'import sys; print(sys.executable)')"
"$RAVI_PYTHON" "$RAVI_REPO/scripts/verify_environment.py"

# Each destination must be fresh. Keep receipt/checksum assets out of assets/.
RAVI_EXTENSION_HOME="$RAVI_REPO/../ravi-extension-transfer"
RAVI_EXTENSION_ASSETS="$RAVI_EXTENSION_HOME/assets"
RAVI_EXTENSION_RESTORED="$RAVI_EXTENSION_HOME/restored"
RAVI_PRODUCTION_CODE="$RAVI_EXTENSION_HOME/production-code"
RAVI_ANALYSIS_CODE="$RAVI_EXTENSION_HOME/analysis-code"
mkdir "$RAVI_EXTENSION_HOME"
mkdir "$RAVI_EXTENSION_ASSETS"

gh release download "$RAVI_EXTENSION_TAG" \
  --repo ravivramchandani/Bayesian-COX --dir "$RAVI_EXTENSION_ASSETS" \
  --pattern inventory.json \
  --pattern 'part-[0-9][0-9][0-9][0-9][0-9][0-9].tar.gz'

# Manual receiving-workflow gate; verify.py itself has no disk-budget gate.
# Allowance: max(1 GiB, 5% of inventory file bytes), plus a 5 GiB reserve.
# Downloaded shards are already occupying disk when available space is measured.
PYTHONDONTWRITEBYTECODE=1 "$RAVI_PYTHON" - \
  "$RAVI_EXTENSION_ASSETS" "$RAVI_EXTENSION_HOME" "$RAVI_INVENTORY_DIGEST" \
  "$RAVI_REPO/scripts/extension_release" <<'PY'
import json
import shutil
import sys
from pathlib import Path

assets, home = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, sys.argv[4])
from verify import load_inventory

inventory = load_inventory(assets)
if inventory["canonical_sha256"] != sys.argv[3]:
    raise SystemExit("Trusted canonical inventory digest mismatch")
file_bytes = sum(m["size"] for m in inventory["members"] if m["type"] == "file")
largest_shard = max((s["bytes"] for s in inventory["shards"]), default=0)
overhead = max(1024**3, (file_bytes + 19) // 20)
reserve = 5 * 1024**3
required = file_bytes + largest_shard + overhead + reserve
free = shutil.disk_usage(home).free
record = {
    "status": "passed" if free >= required else "insufficient_space",
    "canonical_inventory_sha256": inventory["canonical_sha256"],
    "restore_parent": str(home.resolve()),
    "inventory_file_bytes": file_bytes,
    "largest_compressed_shard_bytes": largest_shard,
    "filesystem_overhead_allowance_bytes": overhead,
    "operating_reserve_bytes": reserve,
    "required_free_bytes": required,
    "measured_free_bytes": free,
}
with (home / "space-preflight.json").open("x") as handle:
    json.dump(record, handle, indent=2, sort_keys=True)
    handle.write("\n")
print(json.dumps(record, indent=2, sort_keys=True))
if free < required:
    raise SystemExit("Insufficient free space for this receiving-workflow budget")
PY

PYTHONDONTWRITEBYTECODE=1 "$RAVI_PYTHON" \
  "$RAVI_REPO/scripts/extension_release/verify.py" \
  "$RAVI_EXTENSION_ASSETS" "$RAVI_EXTENSION_RESTORED" \
  --expected-sha256 "$RAVI_INVENTORY_DIGEST"

# Git archive records its source commit in the global PAX comment header.
PYTHONDONTWRITEBYTECODE=1 "$RAVI_PYTHON" - \
  "$RAVI_EXTENSION_RESTORED/code/production.tar.gz" "$RAVI_PRODUCTION_COMMIT" \
  "$RAVI_EXTENSION_RESTORED/code/analysis.tar.gz" "$RAVI_ANALYSIS_COMMIT" <<'PYCODE'
import sys
import tarfile

for path, expected in zip(sys.argv[1::2], sys.argv[2::2], strict=True):
    with tarfile.open(path, "r:gz") as archive:
        observed = archive.pax_headers.get("comment")
    if observed != expected:
        raise SystemExit(f"Code archive source commit differs: {path}")
    print(f"Verified code archive commit: {observed}")
PYCODE
mkdir "$RAVI_PRODUCTION_CODE"
mkdir "$RAVI_ANALYSIS_CODE"
tar -xzf "$RAVI_EXTENSION_RESTORED/code/production.tar.gz" -C "$RAVI_PRODUCTION_CODE"
tar -xzf "$RAVI_EXTENSION_RESTORED/code/analysis.tar.gz" -C "$RAVI_ANALYSIS_CODE"

PYTHONDONTWRITEBYTECODE=1 "$RAVI_PYTHON" \
  "$RAVI_REPO/scripts/extension_release/verify_restored_science.py" \
  --production-code "$RAVI_PRODUCTION_CODE" \
  --analysis-code "$RAVI_ANALYSIS_CODE" \
  --restored "$RAVI_EXTENSION_RESTORED" \
  --primary "$RAVI_ORIGINAL" \
  --sampler "$RAVI_RESULTS/sampler_run" \
  --robustness "$RAVI_RESULTS/robustness" \
  --report "$RAVI_EXTENSION_HOME/restored-science-verified.json"
```

Keep the `space-preflight.json` and new scientific verification report outside the
strict asset/evidence directories. The space allowance is a stated workflow
budget, not an assertion about exact physical filesystem allocation. Allow
additional room for code extraction and temporary reconstruction if needed; the
published release receipt should report its actual measured package sizes.
