# Benchmark cohorts

All three carry time-to-event outcomes with right censoring. Cohort sizes and
event counts are asserted in `tests/test_data.py`.

## GBSG2 — German Breast Cancer Study Group 2

- 686 patients, 299 events (43.6%)
- Outcome: recurrence-free survival, in days
- Source: `sksurv.datasets.load_gbsg2`
- Covariates: age, menopausal status, tumour size, tumour grade, positive
  lymph nodes, progesterone and oestrogen receptor concentrations, hormone
  therapy

Tumour grade is an ordered factor (I, II, III) and is encoded ordinally.
Receptor concentrations and node counts are right-skewed and enter the model
log-transformed alongside their raw values.

## WHAS500 — Worcester Heart Attack Study

- 500 patients, 215 events (43.0%)
- Outcome: all-cause mortality following acute myocardial infarction, in days
- Source: `sksurv.datasets.load_whas500`
- Covariates: age, sex, heart rate, systolic and diastolic blood pressure,
  BMI, cardiovascular history, atrial fibrillation, cardiogenic shock,
  congestive heart failure, complete heart block, MI order and type, length
  of hospital stay

This cohort replaces the heart-attack file named in the proposal, which
contains a binary classification label and no event time.

## METABRIC

- 1903 patients, 1103 events (58.0%)
- Outcome: overall survival, in months
- Source: clinical columns of `data/external/METABRIC_RNA_Mutation.csv`
- Covariates: age at diagnosis, surgery type, cellularity, chemotherapy,
  hormone therapy, radiotherapy, tumour size, tumour stage, positive lymph
  nodes, histologic grade, Nottingham prognostic index, ER/PR/HER2 status,
  menopausal state, PAM50 subtype

In the source, `overall_survival` encodes *alive*, so the event indicator is
its complement. One record with missing follow-up is dropped. Only clinical
covariates are used; the gene expression columns are out of scope.
