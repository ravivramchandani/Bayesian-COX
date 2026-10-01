# Ravi: thesis next steps

You can read the verified results and prepare the thesis on Windows, Linux or
macOS. You do **not** need an Apple Silicon Mac, conda, a Git clone or the
supervisor's SSD for these steps. The Mac-specific software lock is only for
optional verification of the saved evidence; that verification has already
passed on the original Mac.

1. **Check access.** Sign in and open the
   [private GitHub repository](https://github.com/ravivramchandani/Bayesian-COX).
   Open the thesis project from your Overleaf dashboard. If either project is
   missing or GitHub shows a 404 page, ask Ali for access before proceeding.
2. **Read the claim limits before writing.** Use the dated
   [current evidence status](current_evidence_status.md) for what is ready.
   The older [claim register](claim_evidence_register.md) keeps the study's
   claim rules, but its historical result statuses are not current. The thesis
   uses the released confirmatory, robustness and explanation evidence, plus the
   separately labelled ADR-032 sampler sensitivity and ADR-033 Holm bound.
   Report the original 20 diagnostic failures, incomplete primary comparison
   family and failed explanation-stability gate. The unfinished 1,625-cell
   extension is outside the current thesis-submission scope; it may continue
   separately and needs its own release gates before any result claim.
3. **Get the reviewed thesis figures and tables if you need local copies.**
   Open the [supplementary results release](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/results-programme-20260927-11f86ce),
   expand **Assets**, and download `programme-confirmatory-reports.tar.gz`
   (about 588 MB).
   Extract it with your computer's archive app. If the first extraction gives
   you a `.tar` file, extract that too. Open `rendered_confirmatory/figures/`
   for PDF/PNG figures and `rendered_confirmatory/tables/` for CSV/LaTeX
   tables. Start with `tables/primary_contrasts_thesis.tex`,
   `tables/fold_metric_summary.csv` and the top-level
   `figures/paired_ibs_effects.pdf`; the many files under `figures/traces/`
   are detailed audit plots, not the first drafting step. Read
   `rendered_confirmatory/EXPLANATION_GATE_NOTICE.txt` before using
   explanation material.
4. **Keep the sampler sensitivity separate.** From the same release, download
   and extract `programme-posthoc-sensitivity.tar.gz` if you need the ADR-032
   figure or table. They are in `rendered_posthoc/`; read its
   `POSTHOC_EVIDENCE_NOTICE.txt`. Do not present these post-hoc results as a
   repair of the original failed cells.
5. **Work from the shared thesis draft.** Check the Results, Discussion,
   Conclusion and abstract against the released tables and the claim limits.
   Coordinate edits to the shared Overleaf project with Ali; ADR-044 reserves
   Overleaf editing for a separate owner instruction. Send draft claims and
   figures for supervisor review before treating the thesis as finished.

The two archives in steps 3–4 contain the figures and tables needed for the
submission-first thesis. Downloading the original 450-cell archive and all
ten supplementary assets is **not required** just to read or write the thesis.
The released results were already restored and scientifically checked on a
fresh local clone. Downloading and extracting an archive lets you inspect
its contents; it is not a new scientific replay on your laptop.

| Download | Expected SHA-256 |
| --- | --- |
| `programme-confirmatory-reports.tar.gz` | `008f31e2b6d5c33930a79156a850a31afc574f53909d8a1d67c4f1d93662ce15` |
| `programme-posthoc-sensitivity.tar.gz` | `7445abe7fb28c85a559566ad54cb4e5cf70e663250dd3b4f25a4d4ff55ce69ee` |

To check a download, run the command for your laptop in the folder containing
the archive and compare its output with the matching value above. Replace the
file name when checking the second archive:

```text
Windows PowerShell: Get-FileHash .\programme-confirmatory-reports.tar.gz -Algorithm SHA256
macOS Terminal:     shasum -a 256 programme-confirmatory-reports.tar.gz
Linux terminal:     sha256sum programme-confirmatory-reports.tar.gz
```

The [focused clinical methods results](clinical_methods_results.md) are a
separate post-hoc study, not a thesis-submission prerequisite. Its summary is
readable on GitHub without downloading anything. If you want its underlying
figures and CSVs, download `part-000001.tar.gz` from the
[focused private release](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/clinical-methods-posthoc-20261001-eaebcd7)
and extract its `rendered/` folder. The archive SHA-256 is
`072fcdef51dc84299499cf2c66a2f843f5989fa1067b4c69bcf276dbe83d0678`.

Only if you are asked to **re-verify the saved evidence in the exact locked
environment**, use the
[technical restore handoff](ravi_handoff.md#optional-locked-environment-verification-and-restore-on-a-fresh-apple-silicon-mac)
and [environment lock guide](environment_lock.md). The committed lock covers
macOS arm64. That restore checks saved results and does not fit new models.
Equivalent verification on Windows, Linux or Intel Mac would require a
separately built and verified environment; it is not needed for the
thesis-writing steps above.
