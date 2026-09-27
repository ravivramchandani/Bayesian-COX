"""Pinned measured-expression intake and deterministic matched-cohort assembly."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.utils.io import write_json_atomic
from src.utils.reproducibility import sha256_file


def verify_metabric_sources(source_dir: Path, report_path: Path) -> dict[str, str]:
    """Reject changed inputs before parsing their clinical or measured values."""
    report = json.loads(report_path.read_text())
    required = {"data_clinical_patient.txt", "data_clinical_sample.txt",
                "data_mrna_illumina_microarray.txt"}
    expected = {x["name"]: x["downloaded_sha256"] for x in report["data_files"]
                if x["name"] in required}
    if set(expected) != required:
        raise ValueError("source report does not pin every required METABRIC file")
    for name, digest in expected.items():
        if sha256_file(source_dir / name) != digest:
            raise ValueError(f"METABRIC source hash differs: {name}")
    return expected


def collapse_expression(raw: pd.DataFrame) -> pd.DataFrame:
    """Median-collapse alias/probe rows by Entrez ID within each sample.

    No transformation learns across patients here. Nonfinite intensities stay
    missing until the training-fold imputer handles them.
    """
    genes = pd.to_numeric(raw["Entrez_Gene_Id"], errors="raise")
    if not np.isfinite(genes).all() or np.any(genes <= 0) or np.any(genes % 1):
        raise ValueError("Entrez identifiers must be positive integers")
    values = raw.drop(columns=["Hugo_Symbol", "Entrez_Gene_Id"]).astype(float)
    values = values.replace([np.inf, -np.inf], np.nan)
    if values.columns.duplicated().any():
        raise ValueError("duplicate expression sample identifiers")
    values.index = genes.astype(int)
    result = values.groupby(level=0, sort=True).median().T
    result.columns = [f"gene:{c}" for c in result.columns]
    result.index.name = "sample_id"
    return result


def prepare_matched_metabric(
    source_dir: Path, report_path: Path, clinical_csv: Path,
    known_pairs_csv: Path, output_dir: Path,
) -> tuple[Path, dict[str, Any]]:
    """Match measured samples to positive clinical outcomes by explicit ID.

    Retain the existing diagnosis/pathology clinical features; the source
    patient OS outcome must agree with them. Known same-individual accessions
    cannot both enter this new matched cohort. Outputs are write-once.
    """
    hashes = verify_metabric_sources(source_dir, report_path)
    patient = pd.read_csv(source_dir / "data_clinical_patient.txt", sep="\t", comment="#")
    sample = pd.read_csv(source_dir / "data_clinical_sample.txt", sep="\t", comment="#")
    if patient.PATIENT_ID.duplicated().any() or sample.SAMPLE_ID.duplicated().any():
        raise ValueError("ambiguous source patient/sample identifiers")
    expression = collapse_expression(pd.read_csv(source_dir / "data_mrna_illumina_microarray.txt", sep="\t"))
    mapping = sample.set_index("SAMPLE_ID").loc[expression.index]
    if mapping.PATIENT_ID.duplicated().any() or not (mapping.SAMPLE_TYPE == "Primary").all():
        raise ValueError("expression does not map one primary sample per patient")
    expression.index = mapping.PATIENT_ID.to_numpy(str)
    clinical = pd.read_csv(clinical_csv).set_index("patient_id", verify_integrity=True)
    eligible = sorted(set(expression.index) & set(clinical.index))
    if not eligible:
        raise ValueError("no clinical/expression intersection")
    clinical = clinical.loc[eligible]
    clinical = clinical[np.isfinite(clinical.duration) & (clinical.duration > 0)]
    source_patient = patient.set_index("PATIENT_ID").loc[clinical.index]
    source_event = source_patient.OS_STATUS.str.split(":").str[0].astype(int)
    if not np.allclose(clinical.duration, source_patient.OS_MONTHS, rtol=1e-12, atol=1e-10):
        raise ValueError("matched clinical/source follow-up disagrees")
    if not np.array_equal(clinical.event, source_event):
        raise ValueError("matched clinical/source OS event disagrees")
    if not np.isin(clinical.event, [0, 1]).all():
        raise ValueError("nonbinary matched outcome")
    known_pairs = pd.read_csv(known_pairs_csv)
    ids = set(clinical.index)
    if any(a in ids and b in ids for a, b in zip(known_pairs.accession_a, known_pairs.accession_b, strict=True)):
        raise ValueError("known same-individual accessions coexist in matched cohort")
    matched = pd.concat([clinical, expression.loc[clinical.index]], axis=1).reset_index()
    matched = matched.rename(columns={matched.columns[0]: "patient_id"})
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "matched_metabric.parquet"
    if path.exists():
        raise FileExistsError(path)
    matched.to_parquet(path, index=False)
    metadata = {"source_sha256": hashes, "clinical_sha256": sha256_file(clinical_csv),
                "known_pairs_sha256": sha256_file(known_pairs_csv), "n_patients": len(matched),
                "n_genes": len(expression.columns), "events": int(matched.event.sum()),
                "aggregation": "within-sample median by Entrez ID",
                "processed_expression_limitation": "published cohort-normalized log2 assay; prospective normalization and exact pretreatment availability unresolved",
                "matched_sha256": sha256_file(path)}
    write_json_atomic(output_dir / "matched_metabric_manifest.json", metadata)
    return path, metadata
