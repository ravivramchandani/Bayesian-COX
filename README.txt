Explainable Bayesian Survival Models
Ravi V. Ramchandani

Compile Main.tex with pdfLaTeX. The source includes the figures and tables used by the thesis.

Saved aggregate results are in generated/ and report_summaries/. The manuscript reads its presentation tables from tables/. Supplementary calibration and predictive tables can be regenerated with:

python3 scripts/render_supplementary_tables.py

The renderer verifies the saved aggregate checksums and does not fit models.
