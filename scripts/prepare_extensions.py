"""Download hash-pinned sources and prepare the matched expression cohort."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from urllib.request import urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipelines.extensions.genomics import prepare_matched_metabric
from src.utils.reproducibility import sha256_file


def main() -> None:
    """Restore required measured sources without substituting missing observations."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    report = root / "coordination/extension_sources/metabric_source_report.json"
    args.source_cache.mkdir(parents=True, exist_ok=True)
    files = json.loads(report.read_text())["data_files"]
    required = {"LICENSE", "data_clinical_patient.txt", "data_clinical_sample.txt",
                "data_mrna_illumina_microarray.txt", "meta_mrna_illumina_microarray.txt"}
    for entry in files:
        if entry["name"] not in required:
            continue
        path = args.source_cache / entry["name"]
        if path.exists():
            if sha256_file(path) != entry["downloaded_sha256"]:
                raise ValueError(f"cached source changed: {entry['name']}")
            continue
        partial = path.with_suffix(path.suffix + ".part")
        if partial.exists():
            raise FileExistsError(f"preserve/review interrupted download before retrying: {partial}")
        with urlopen(entry["payload_url"], timeout=120) as response, partial.open("xb") as target:
            while block := response.read(1024 * 1024):
                target.write(block)
        if sha256_file(partial) != entry["downloaded_sha256"]:
            raise ValueError(f"downloaded source hash differs: {entry['name']}")
        partial.rename(path)
        print(entry["name"], "downloaded and verified", flush=True)
    path, metadata = prepare_matched_metabric(args.source_cache, report, root / "data/raw/metabric.csv",
        root / "tests/fixtures/extensions/metabric_known_accession_pairs.csv", args.output)
    print(path, metadata["matched_sha256"])


if __name__ == "__main__":
    main()
