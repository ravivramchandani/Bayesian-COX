"""Export the three benchmark cohorts to data/raw/ as CSV.

GBSG2 and WHAS500 come from scikit-survival. METABRIC is derived from the
clinical columns of data/external/METABRIC_RNA_Mutation.csv.

Every source is real. There is no synthetic fallback: if a source is missing,
the script fails.
"""

import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(ROOT, "data", "raw")
METABRIC_SOURCE = os.path.join(
    ROOT, "data", "external", "METABRIC_RNA_Mutation.csv"
)

METABRIC_FEATURES = [
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
]


def export_gbsg2() -> None:
    from sksurv.datasets import load_gbsg2

    X, y = load_gbsg2()
    df = pd.DataFrame(X)
    df["time"] = y["time"]
    df["cens"] = y["cens"].astype(int)

    target = os.path.join(RAW_DIR, "gbsg2.csv")
    df.to_csv(target, index=False)
    print(f"gbsg2: {len(df)} records, {int(df['cens'].sum())} events -> {target}")


def export_whas500() -> None:
    from sksurv.datasets import load_whas500

    X, y = load_whas500()
    df = pd.DataFrame(X)
    df["lenfol"] = y["lenfol"]
    df["fstat"] = y["fstat"].astype(int)

    target = os.path.join(RAW_DIR, "whas500.csv")
    df.to_csv(target, index=False)
    print(f"whas500: {len(df)} records, {int(df['fstat'].sum())} events -> {target}")


def export_metabric() -> None:
    """Build the METABRIC clinical cohort.

    `overall_survival` in the source encodes *alive* (1 = Living), so the
    event indicator is its complement.
    """
    if not os.path.exists(METABRIC_SOURCE):
        raise FileNotFoundError(
            f"METABRIC source not found at {METABRIC_SOURCE}. "
            "Download METABRIC_RNA_Mutation.csv into data/external/."
        )

    source = pd.read_csv(METABRIC_SOURCE, low_memory=False)

    missing = [c for c in METABRIC_FEATURES if c not in source.columns]
    if missing:
        raise ValueError(f"METABRIC source is missing columns: {missing}")

    df = source[METABRIC_FEATURES].copy()
    df["duration"] = pd.to_numeric(source["overall_survival_months"], errors="coerce")
    df["event"] = 1 - pd.to_numeric(source["overall_survival"], errors="coerce")

    before = len(df)
    df = df.dropna(subset=["duration", "event"])
    df = df[df["duration"] > 0].reset_index(drop=True)
    df["event"] = df["event"].astype(int)

    target = os.path.join(RAW_DIR, "metabric.csv")
    df.to_csv(target, index=False)
    print(
        f"metabric: {len(df)} records ({before - len(df)} dropped for missing or "
        f"non-positive follow-up), {int(df['event'].sum())} events -> {target}"
    )


def main() -> int:
    os.makedirs(RAW_DIR, exist_ok=True)
    export_gbsg2()
    export_whas500()
    export_metabric()
    return 0


if __name__ == "__main__":
    sys.exit(main())
