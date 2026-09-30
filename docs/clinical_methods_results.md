# Focused clinical methods results — ADR-045

This is a **separate, outcome-aware post-hoc clinical study**, released on
2026-10-01 NZ. The subset was selected after partial extension outcomes and
execution statuses existed. Its [scope and analysis rules](protocol_addendum_clinical_methods.md)
and [225-cell roster](../coordination/clinical_methods_roster.json) were
committed before this focused performance analysis, but that does not make
the selection result-blind or externally preregistered. The study does not
change the confirmatory record or finish the 1,625-fit extension.

The [private evidence release](https://github.com/ravivramchandani/Bayesian-COX/releases/tag/clinical-methods-posthoc-20261001-eaebcd7)
is pinned to analysis code `eaebcd7b422e63cc7b0792cc8ac481f83a0080ba`
and canonical package inventory SHA-256
`3497558581a4fefb67eabcf8a2b215cec6f48e3654fe681679a2572f54378953`.
The [release receipt](../coordination/recovery/2026-10-01-clinical-methods-release.json)
binds the source, figures, assets and fresh scientific replay. Ravi can use
the [execution and restore guide](clinical_methods_execution.md) on an
Apple Silicon Mac with private-repository access and the exact environment
lock. The receiving replay passed on a fresh clone and download on this Mac;
Ravi's physical laptop has not yet been tested.

| Fixed evidence | Verified result |
| --- | --- |
| Selected penalised-Cox cells | 225/225 independently rescored across GBSG2, WHAS500 and clinical METABRIC; ridge, lasso and elastic net, each with five repeats by five outer folds |
| Bayesian comparison references | 150 original normal and continuous spike-and-slab cells, plus 75 separately labelled ADR-032 horseshoe sensitivity cells |
| Fixed primary family | 27/27 penalised-minus-Bayesian integrated Brier score contrasts estimable with 25 aligned fold pairs each |
| Repeated-CV uncertainty and multiplicity | Every 95% interval crosses zero; zero Holm rejections; all 27 Holm-adjusted p-values are 1.0 |
| Saved first-fold penalised refits | Nine of nine agree with source cells on non-timing scientific content; zero of nine historical formal refit receipts exist |
| Original horseshoe context | 20/75 original cells failed diagnostics (18 GBSG2, two METABRIC); the separate ADR-032 sensitivity passed 75/75 |
| Transfer | Four figures and nine claim boundaries passed named review; fresh private-release download, archive restore and independent scientific replay passed |

The recorded visual and claim reviewer was Codex; this is not independent
clinical or journal peer review. Ravi should inspect the figures and any
manuscript wording before using them.

The contrast is **penalised IBS minus Bayesian IBS**, so a positive value
favours Bayesian prediction. Across the 27 contrasts, mean differences range
from −0.0010341 to +0.0002984. These small observed differences and their
intervals do not prove equivalence. There is no supported superiority claim,
global winner, pooled cross-cohort effect, or causal attribution to a prior
alone. The Bayesian piecewise-exponential and penalised Cox models also have
different likelihood and baseline-hazard implementations.

The released `rendered/paired_contrasts.csv` contains each fixed contrast,
interval and adjusted p-value. `rendered/cell_metrics.csv`,
`rendered/diagnostic_coverage.csv` and the four reviewed figures show
secondary discrimination, calibration, diagnostic coverage and observed
end-to-end cell times. Optimizer status and fit attempts are in
`verified/analysis/descriptive.json`. Accepted-only summaries must be read with
the planned and failed denominators; observed times come from separate runs
and are not hardware-normalized fit-only costs. Integrated Brier score alone
does not establish calibration.

These are three distinct internal-validation cohorts with different
endpoints, not external transport validation of one model. They are clinical,
low-dimensional settings, so these findings do not answer the METABRIC
gene-expression question. One known same-individual pair in clinical
METABRIC may cross historical folds, and exact pretreatment availability of
some predictors remains unresolved; the METABRIC survival time origin is
documented as initial diagnosis. The restored baseline releases omit raw
posterior arrays, so this study uses stored diagnostic records and the
earlier 450/450 exact-refit report for the original confirmatory references,
rather than newly recomputed trace diagnostics. The separately labelled
ADR-032 references are pinned by their own manifest, cell hashes and
lineage; that report did not refit them.

There is no treatment action or validated decision threshold here, and no
decision-curve or clinical-utility claim. A fresh replay on Ravi's laptop
would establish that machine's receipt, not change these scientific limits.

This complete subset is reusable methods evidence, but journal acceptance
or a Q1-level contribution is not established by this comparison alone.
The thesis remains on the ADR-044 submission-first route. The unfinished
full extension, catalytic correction and any later manuscript are separate
tasks; no Overleaf edit or paper submission is implied by this release.
