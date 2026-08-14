"""Build the three confirmatory benchmark cohorts in ``data/raw``.

Every input is downloaded from an immutable upstream revision and checked
before it is parsed. There is deliberately no synthetic or unverified-data
fallback. The exploratory 1,904-row METABRIC export is retained separately
under ``data/external`` and is never used by this confirmatory exporter.
"""

from __future__ import annotations

import hashlib
import sys
from io import StringIO
from pathlib import Path
from urllib.request import Request, urlopen

import pandas as pd
from scipy.io import arff

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"

SKSURV_COMMIT = "3e887ed7307a60c08f3fafec8b00d57f7a2d4982"  # v0.24.1
CBIOPORTAL_COMMIT = "165bd77077b03038f9c2ee104959eb474770b2a9"

SOURCES = {
    "gbsg2": {
        "url": (
            "https://raw.githubusercontent.com/sebp/scikit-survival/"
            f"{SKSURV_COMMIT}/sksurv/datasets/data/GBSG2.arff"
        ),
        "sha256": "8c1ba1df4d80216b58695d6bbc9f51284664ab37124e101d56df089851645b04",
    },
    "whas500": {
        "url": (
            "https://raw.githubusercontent.com/sebp/scikit-survival/"
            f"{SKSURV_COMMIT}/sksurv/datasets/data/whas500.arff"
        ),
        "sha256": "f64040c91398875137822eca306a927208df6896808cd9764af7065722fa53d6",
    },
    "metabric_patient": {
        "url": (
            "https://media.githubusercontent.com/media/cBioPortal/datahub/"
            f"{CBIOPORTAL_COMMIT}/public/brca_metabric/data_clinical_patient.txt"
        ),
        "sha256": "2a6bbadc6e4b2b07c0505559d438da959fc5c9aba55c7194abc394e2d6454995",
    },
    "metabric_sample": {
        "url": (
            "https://media.githubusercontent.com/media/cBioPortal/datahub/"
            f"{CBIOPORTAL_COMMIT}/public/brca_metabric/data_clinical_sample.txt"
        ),
        "sha256": "9a2291e065e2a0a5337b4eaeb09836e70b1bc3e1ed17714a013b53515697e6dc",
    },
}

DERIVED_SHA256 = {
    "gbsg2": "2158b777d27ecfb69b187d3cbcad13fd1eb92d626935c528a4465fea6490ae5f",
    "whas500": "4bb01775c04eca11d7f06d6e5dfebd0a5cce75aa7e73fe4261732385be106fcc",
    "metabric": "731ea80ce0240cb6aa96ffb0f4a3bb379615202966c954512664bef02b29545c",
}

GBSG2_COLUMNS = [
    "age",
    "estrec",
    "horTh",
    "menostat",
    "pnodes",
    "progrec",
    "tgrade",
    "tsize",
    "time",
    "cens",
]

WHAS500_COLUMNS = [
    "afb",
    "age",
    "av3",
    "bmi",
    "chf",
    "cvd",
    "diasbp",
    "gender",
    "hr",
    "los",
    "miord",
    "mitype",
    "sho",
    "sysbp",
    "lenfol",
    "fstat",
]

METABRIC_COLUMNS = [
    "patient_id",
    "age_at_diagnosis",
    "type_of_breast_surgery",
    "cellularity",
    "chemotherapy",
    "hormone_therapy",
    "radio_therapy",
    "tumor_size",
    "tumor_stage",
    "lymph_nodes_examined_positive",
    "neoplasm_histologic_grade",
    "nottingham_prognostic_index",
    "er_status",
    "pr_status",
    "her2_status",
    "inferred_menopausal_state",
    "pam50_+_claudin-low_subtype",
    "duration",
    "event",
]


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _download_verified(source_name: str) -> bytes:
    spec = SOURCES[source_name]
    request = Request(spec["url"], headers={"User-Agent": "bayesian-cox-data-export/1"})
    with urlopen(request, timeout=60) as response:  # noqa: S310 - pinned HTTPS URL
        content = response.read()

    observed = _sha256(content)
    if observed != spec["sha256"]:
        raise ValueError(
            f"{source_name} source hash mismatch: expected {spec['sha256']}, "
            f"observed {observed}"
        )
    return content


def _decode_arff(content: bytes) -> pd.DataFrame:
    records, _ = arff.loadarff(StringIO(content.decode("utf-8")))
    frame = pd.DataFrame(records)
    for column in frame.select_dtypes(include=["object", "string"]).columns:
        non_missing = frame[column].dropna()
        if not non_missing.empty and isinstance(non_missing.iloc[0], bytes):
            frame[column] = frame[column].str.decode("utf-8")
    return frame


def _write_verified(frame: pd.DataFrame, dataset_name: str) -> Path:
    content = frame.to_csv(index=False).encode("utf-8")
    expected = DERIVED_SHA256[dataset_name]
    if expected and _sha256(content) != expected:
        raise ValueError(
            f"{dataset_name} derived hash mismatch: expected {expected}, "
            f"observed {_sha256(content)}"
        )

    target = RAW_DIR / f"{dataset_name}.csv"
    target.write_bytes(content)
    return target


def export_gbsg2() -> None:
    frame = _decode_arff(_download_verified("gbsg2"))[GBSG2_COLUMNS].copy()
    frame["cens"] = pd.to_numeric(frame["cens"], errors="raise").astype(int)

    if len(frame) != 686 or int(frame["cens"].sum()) != 299:
        raise ValueError("GBSG2 eligibility invariant failed; expected 686 rows/299 events")
    if frame.isna().any().any() or not frame["time"].gt(0).all():
        raise ValueError("GBSG2 contains missing values or non-positive follow-up")

    target = _write_verified(frame, "gbsg2")
    print(f"gbsg2: 686 records, 299 events -> {target}")


def export_whas500() -> None:
    frame = _decode_arff(_download_verified("whas500"))[WHAS500_COLUMNS].copy()
    frame["fstat"] = pd.to_numeric(frame["fstat"], errors="raise").astype(int)

    if len(frame) != 500 or int(frame["fstat"].sum()) != 215:
        raise ValueError("WHAS500 eligibility invariant failed; expected 500 rows/215 events")
    if frame.isna().any().any() or not frame["lenfol"].gt(0).all():
        raise ValueError("WHAS500 contains missing values or non-positive follow-up")

    target = _write_verified(frame, "whas500")
    print(f"whas500: 500 records, 215 events -> {target}")


def _read_cbioportal_table(content: bytes) -> pd.DataFrame:
    return pd.read_csv(StringIO(content.decode("utf-8")), sep="\t", comment="#")


def export_metabric() -> None:
    """Build the eligible OS cohort from the pinned cBioPortal study files."""
    patients = _read_cbioportal_table(_download_verified("metabric_patient"))
    samples = _read_cbioportal_table(_download_verified("metabric_sample"))

    if len(patients) != 2509 or len(samples) != 2509:
        raise ValueError("METABRIC source invariant failed; expected 2,509 patient/sample rows")
    if not patients["PATIENT_ID"].is_unique or not samples["PATIENT_ID"].is_unique:
        raise ValueError("METABRIC patient/sample identifiers must each be unique")

    patient_columns = {
        "PATIENT_ID": "patient_id",
        "AGE_AT_DIAGNOSIS": "age_at_diagnosis",
        "BREAST_SURGERY": "type_of_breast_surgery",
        "CELLULARITY": "cellularity",
        "CHEMOTHERAPY": "chemotherapy",
        "HORMONE_THERAPY": "hormone_therapy",
        "RADIO_THERAPY": "radio_therapy",
        "LYMPH_NODES_EXAMINED_POSITIVE": "lymph_nodes_examined_positive",
        "NPI": "nottingham_prognostic_index",
        "INFERRED_MENOPAUSAL_STATE": "inferred_menopausal_state",
        "CLAUDIN_SUBTYPE": "pam50_+_claudin-low_subtype",
        "OS_MONTHS": "duration",
        "OS_STATUS": "os_status",
    }
    sample_columns = {
        "PATIENT_ID": "patient_id",
        "TUMOR_SIZE": "tumor_size",
        "TUMOR_STAGE": "tumor_stage",
        "GRADE": "neoplasm_histologic_grade",
        "ER_STATUS": "er_status",
        "PR_STATUS": "pr_status",
        "HER2_STATUS": "her2_status",
    }

    patient_frame = patients[list(patient_columns)].rename(columns=patient_columns)
    sample_frame = samples[list(sample_columns)].rename(columns=sample_columns)
    frame = patient_frame.merge(
        sample_frame, on="patient_id", how="inner", sort=False, validate="one_to_one"
    )
    if len(frame) != 2509:
        raise ValueError("METABRIC patient/sample merge did not retain all 2,509 IDs")

    status_map = {"0:LIVING": 0, "1:DECEASED": 1}
    unknown_status = sorted(set(frame["os_status"].dropna()) - set(status_map))
    if unknown_status:
        raise ValueError(f"Unexpected METABRIC OS status values: {unknown_status}")

    frame["duration"] = pd.to_numeric(frame["duration"], errors="coerce")
    frame["event"] = frame["os_status"].map(status_map)
    complete_outcome = frame.dropna(subset=["duration", "event"])
    if len(complete_outcome) != 1981:
        raise ValueError(
            "METABRIC complete-OS invariant failed; expected 1,981 records before "
            "positive-time eligibility"
        )

    frame = complete_outcome.loc[complete_outcome["duration"] > 0].copy()
    frame["event"] = frame["event"].astype(int)
    frame = frame[METABRIC_COLUMNS].reset_index(drop=True)

    if len(frame) != 1980 or int(frame["event"].sum()) != 1144:
        raise ValueError(
            "METABRIC eligibility invariant failed; expected 1,980 rows/1,144 deaths"
        )
    if not frame["patient_id"].is_unique:
        raise ValueError("Eligible METABRIC patient identifiers must be unique")

    target = _write_verified(frame, "metabric")
    print(
        "metabric: 1,980 records (528 missing OS, 1 zero-time record excluded), "
        f"1,144 deaths -> {target}"
    )


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    export_gbsg2()
    export_whas500()
    export_metabric()
    return 0


if __name__ == "__main__":
    sys.exit(main())
