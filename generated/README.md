# Regenerated thesis evidence

These aggregate tables and vector figures are rendered from the locked submission baseline. No model is fitted. Patient-level records and posterior arrays are not copied into this directory.

Run from the thesis repository, with a restored source archive and Python 3.10 or newer containing matplotlib (and its NumPy dependency):

```sh
python scripts/regenerate_thesis_results.py --source-root /path/to/bayes-cox-runs --project-root ../project --output-dir generated
```

The source archive layout must include `frozen/reports/confirmatory`, `frozen/data/raw`, and `student-programme-results-20260928`. The small `provenance.json` records all source file hashes, renderer identity, actual rendering runtime, exact aggregation rules and output hashes. The rendering runtime is separate from the frozen scientific fitting environment, which remains Python 3.11.15 under its original lock. The renderer rejects changed source files.

The full 174-row robustness table is intended for an appendix. Partial horseshoe coverage, all diagnostic failures, unavailable primary contrasts and the failed explanation stability gate are retained. Sampler sensitivity and Holm bounds are post hoc and never replace primary evidence.

Required LaTeX packages: `booktabs`, `longtable`, `adjustbox`, `graphicx`, `array`, `setspace`. Each `table_*.tex` is a complete labelled table; figures are included separately. `results_macros.tex` defines scalar commands.
