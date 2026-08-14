# Benchmark cohorts

The confirmatory benchmark uses three genuine right-censored clinical
cohorts. Immutable URLs, upstream and derived SHA-256 hashes, eligibility,
event coding, licences, citations and missingness are frozen in the
[machine-readable data manifest](../data/manifest.yaml). Rebuild the raw
analysis files with:

```bash
python scripts/download_datasets.py
```

The exporter verifies every downloaded byte and the deterministic derived
CSV. A missing input or hash mismatch raises; there is no synthetic fallback.

## GBSG2 — German Breast Cancer Study Group 2

- Analysis population: 686 patients and 299 recurrence-free-survival events
  (43.6%).
- Follow-up unit: days.
- Immutable source: scikit-survival v0.24.1 commit
  [`3e887ed...`](https://github.com/sebp/scikit-survival/tree/3e887ed7307a60c08f3fafec8b00d57f7a2d4982/sksurv/datasets/data).
- Original trial report:
  [Schumacher et al.](https://doi.org/10.1200/JCO.1994.12.10.2086).
- Missingness: none in the distributed cohort.

The primary set contains the eight supplied clinical predictors: age, tumour
size, positive nodes, progesterone and oestrogen receptor concentrations,
hormone therapy, menopausal status and ordered tumour grade. It contains no
automatically generated duplicate predictors. The former log copies of node
and receptor measures and the age-by-hormone-therapy interaction are retained
only as the named `engineered_augmented` sensitivity.

The pinned ARFF/README do not state the clinical anchor of the trial-defined
recurrence-free-survival clock precisely enough to label it more narrowly.
The thesis should retain that limitation unless the primary report supplies
the missing definition.

## WHAS500 — Worcester Heart Attack Study

- Analysis population: 500 acute-myocardial-infarction admissions and 215
  all-cause deaths (43.0%).
- Time origin and unit: hospital admission, followed in days.
- Immutable source: scikit-survival v0.24.1 commit
  [`3e887ed...`](https://github.com/sebp/scikit-survival/tree/3e887ed7307a60c08f3fafec8b00d57f7a2d4982/sksurv/datasets/data).
- Source book: [Hosmer, Lemeshow and May](https://doi.org/10.1002/9780470258019).
- Missingness: none in the distributed cohort.

The primary admission-time set is age, sex, heart rate, systolic and
diastolic blood pressure, BMI, cardiovascular-disease history, MI order and
MI type. Length of stay (`los`) is definitely post-baseline and is excluded.
The source metadata defines atrial fibrillation (`afb`), cardiogenic shock
(`sho`), congestive heart failure (`chf`) and complete heart block (`av3`),
but does not establish that their onset preceded or occurred at admission;
they are therefore excluded from the primary set rather than assumed safe.

The named `published_full` sensitivity contains all 14 supplied predictors,
including those five excluded fields. A separate `engineered_augmented`
sensitivity adds the legacy low-BMI threshold to the parsimonious primary
set. Neither sensitivity supports an admission-time availability claim.

This cohort replaces the proposal's heart-attack classification file, which
has no event-time outcome.

## METABRIC

### Confirmatory source

The active analysis file is rebuilt from the official cBioPortal DataHub
study `brca_metabric`, pinned at commit
[`165bd770...`](https://github.com/cBioPortal/datahub/tree/165bd77077b03038f9c2ee104959eb474770b2a9/public/brca_metabric).
The patient and sample tables each contain 2,509 unique patient IDs. After
requiring both overall-survival fields and positive follow-up, the exact
analysis population is 1,980 patients with 1,144 deaths. The eligibility flow
is 528 exclusions for missing OS and one living patient excluded for zero
follow-up.

The pinned patient metadata defines `OS_MONTHS` as overall survival in months
since initial diagnosis. `0:LIVING` maps to `event=0`; `1:DECEASED` maps to
`event=1`. The derived file retains `patient_id`, and all 1,980 IDs are unique.

The primary diagnosis/pathology set contains age at diagnosis, Nottingham
prognostic index (NPI), cellularity, ER status, PR status, HER2 status,
inferred menopausal state and PAM50/claudin-low subtype. It excludes:

- NPI components (tumour size, positive nodes and histologic grade), so a
  composite and all of its components cannot compete as duplicate evidence;
- tumour stage, which is missing in 514/1,980 records (26.0%);
- surgery type, chemotherapy, hormone therapy and radiotherapy received,
  which are unavailable at the primary diagnosis/pathology prediction time.

The prespecified sensitivity sets are `npi_components` (replace NPI with its
three components), `npi_plus_stage` (add stage with fold-local missing-data
handling), and `treatment_augmented` (add observed surgery/treatment fields).
No primary or sensitivity set silently adds log-node or stage-interaction
duplicates.

Missingness in the eligible confirmatory cohort is:

| Variable | Missing, n (%) |
|---|---:|
| Age at diagnosis | 0 (0.0) |
| NPI | 1 (0.1) |
| Cellularity | 64 (3.2) |
| ER status | 0 (0.0) |
| PR status | 1 (0.1) |
| HER2 status | 1 (0.1) |
| Menopausal state | 1 (0.1) |
| PAM50/claudin-low subtype | 1 (0.1) |
| Surgery type | 25 (1.3) |
| Chemotherapy / hormone therapy / radiotherapy | 1 each (0.1 each) |
| Tumour size | 25 (1.3) |
| Tumour stage | 514 (26.0) |
| Positive nodes | 76 (3.8) |
| Histologic grade | 87 (4.4) |

The study-specific
[Open Database License](https://raw.githubusercontent.com/cBioPortal/datahub/165bd77077b03038f9c2ee104959eb474770b2a9/public/brca_metabric/LICENSE)
requires attribution and share-alike handling of adapted databases.

### Exploratory pilot source

`data/external/METABRIC_RNA_Mutation.csv` is the 1,904-row, 693-column Kaggle
version-1 export published on 2020-05-26. Its SHA-256 is
`d4802594827667a71a75b5ae5c3cad1eb4346222052fcc792361c64abc7e43bc`.
Its historical eligible pilot population is 1,903 records and 1,103 deaths;
one record has zero follow-up. In that file `overall_survival=1` means living,
so the historical event was its complement.

This file is preserved only to reproduce exploratory pilot work. It must be
called the “2020 Kaggle/cBioPortal-derived 1,904-patient subset” and must never
supply a confirmatory METABRIC result. Pilot and confirmatory provenance are
separate entries in the manifest.

## Data governance and release

The repository MIT licence governs project software only. The pinned
scikit-survival repository distributes its content under GPL-3.0-or-later and calls
the bundled datasets freely available, but no separate original-data licence
was identified in its data directory. METABRIC carries its study-specific
ODbL terms. The conservative public-release default is therefore scripts,
metadata, hashes and citations rather than newly redistributing patient-level
source or derived files without the applicable attribution/licence package.

## New-dataset decision

No fourth independently refitted core cohort is needed for this six-month
master's thesis. The repaired core contains 3,166 patients and 1,658 events
across three clinical settings. Calibration, paired confirmatory inference,
robustness, explanation stability and writing have higher priority than
adding another heterogeneous benchmark.

The optional Rotterdam-to-GBSG2 transport branch was permanently dropped
before protocol freeze, together with the optional simulation. The core study
therefore makes no external-validation or coefficient-recovery claim. Both
remain possible future extensions after the master's thesis rather than
unresolved data requirements.
