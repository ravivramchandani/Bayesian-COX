# Benchmark cohorts

All three core cohorts contain genuine time-to-event outcomes with right
censoring. Counts are asserted in tests. The current benchmark is a pilot;
the confirmatory source and feature rules are in `docs/study_protocol.md`.

## GBSG2 — German Breast Cancer Study Group 2

- 686 patients, 299 recurrence-free-survival events (43.6%).
- Time unit: days.
- Source interface:
  [`sksurv.datasets.load_gbsg2`](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.datasets.load_gbsg2.html).
- Original trial DOI: <https://doi.org/10.1200/JCO.1994.12.10.2086>.
- Covariates: age, menopausal status, tumour size, tumour grade, positive
  lymph nodes, progesterone and oestrogen receptor concentrations, and
  hormone therapy.

The local raw CSV matches the official scikit-survival data values. The
confirmatory manifest will pin the exact package release, upstream ARFF hash,
retrieval date, data notice and derived-file hash.

Tumour grade is ordered. Receptor concentrations and node counts are
right-skewed. The primary feature rule and any raw/log transformation are
fitted within each outer-training fold and frozen before confirmatory runs.

## WHAS500 — Worcester Heart Attack Study

- 500 patients, 215 all-cause deaths (43.0%).
- Time origin: acute-myocardial-infarction admission; follow-up in days.
- Source interface:
  [`sksurv.datasets.load_whas500`](https://scikit-survival.readthedocs.io/en/stable/api/generated/sksurv.datasets.load_whas500.html).
- Source-book DOI: <https://doi.org/10.1002/9780470258019>.
- Supplied covariates include age, sex, heart rate, blood pressure, BMI,
  cardiovascular history/complications, MI order/type and length of stay.

The local raw CSV matches the official scikit-survival data values. The
confirmatory manifest will pin the release, upstream ARFF hash, data notice
and derived hash.

For admission-time prediction, length of stay is post-baseline and is excluded
from the primary model. The timing of atrial fibrillation, cardiogenic shock,
heart failure and heart block must also be verified. The full published
feature set is a comparability sensitivity, not the primary prospective-
availability specification.

This cohort replaces the proposal's heart-attack classification file, which
has no event-time outcome.

## METABRIC

Two distinct source versions must not be conflated.

### Exploratory pilot source

- Source: `data/external/METABRIC_RNA_Mutation.csv`.
- Provenance: Kaggle dataset version 1, published 2020-05-26; a
  cBioPortal-derived combined clinical/omics file.
- Source shape: 1,904 rows by 693 columns.
- SHA-256:
  `d4802594827667a71a75b5ae5c3cad1eb4346222052fcc792361c64abc7e43bc`.
- Pilot analysis population: 1,903 positive-time records and 1,103 deaths.

`overall_survival = 1` means living, so the event indicator is its complement.
One record is excluded because follow-up time is zero, not because follow-up
is missing. Only clinical columns are used.

This version is retained to reproduce pilot files only. It must be described
as the “2020 Kaggle/cBioPortal-derived 1,904-patient subset,” not the complete
METABRIC clinical cohort.

### Confirmatory source

- Authoritative source: cBioPortal DataHub study `brca_metabric`, pinned at
  commit
  [`165bd77077b03038f9c2ee104959eb474770b2a9`](https://github.com/cBioPortal/datahub/tree/165bd77077b03038f9c2ee104959eb474770b2a9/public/brca_metabric).
- Patient-file SHA-256:
  `2a6bbadc6e4b2b07c0505559d438da959fc5c9aba55c7194abc394e2d6454995`.
- Sample-file SHA-256:
  `9a2291e065e2a0a5337b4eaeb09836e70b1bc3e1ed17714a013b53515697e6dc`.
- Study licence:
  [Open Database License (ODbL)](https://github.com/cBioPortal/datahub/blob/master/public/brca_metabric/LICENSE).
- A matching 2,509-row clinical export is already local at
  `../proposal/Proposal/1Breast Cancer METABRIC.csv`.
- Expected confirmatory population after requiring complete OS outcome and
  positive follow-up: 1,980 patients and 1,144 deaths.

All 2,509 patient IDs and survival-status/missingness fields in the local
export match the pinned cBioPortal clinical files; OS-time differences are
decimal rounding. The active pilot therefore omits 77 otherwise eligible
positive-time records and 41 deaths. Exact schema/count/hash tests must pass
before confirmatory use.

The exact METABRIC overall-survival time origin must be verified from the
source documentation before the thesis calls it diagnosis-time prediction.
Under that intended target, the primary model excludes surgery type,
chemotherapy, hormone therapy and radiotherapy received unless predictor
timing is defensible; no treatment dates are available for a clean
post-treatment landmark. The primary specification also avoids using
Nottingham prognostic index together with all of its tumour-size, grade and
node components.

Tumour stage is missing in about 26% of the proposed confirmatory cohort.
Stage is excluded from the primary core set or receives a frozen missingness
representation; fold-wise multiple imputation is a sensitivity analysis.

## Data governance and release

The repository MIT licence governs project software. It does not overwrite
upstream dataset terms. Before public release, the owner-approved data matrix
must specify which source/derived files can be redistributed, the required
attribution/share-alike text and whether only download scripts/manifests may
be published.

Each result manifest records the immutable source, hashes, eligibility flow,
endpoint and event coding. A missing source or hash mismatch raises; no
synthetic fallback is permitted for real-cohort analysis.

## New-dataset decision

No fourth independently refitted core cohort is required. After the METABRIC
upgrade the core contains 3,166 patients and 1,658 events across three
clinical settings. Completing calibration, confirmatory inference,
robustness, explainability stability and writing has higher value than adding
another heterogeneous benchmark.

A Rotterdam-to-GBSG2 locked transport evaluation is publication-enhancing
only and is governed by T-115. If that Week 4 gate fails, it is dropped. No
claim of external validation is made merely because a model family is
refitted separately in several cohorts.
