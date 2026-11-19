# Conservative natural-prose edit — 19 November 2026

## Scope and outcome

Applied the complete supervisor-supplied `natural_prose_style_edit_prompt_Claude.md`
conservatively to the current thesis at `b2b9aa9`. Both repositories were clean at
entry. The whole report, bibliography and active input material were read before
editing; every changed passage was then checked against its original and in context.

Only 37 local passages in the five main chapters changed: six Introduction,
five Literature Review, twelve Methodology, eleven Results and three Conclusion
passages. The edits clarify awkward wording, remove small repetitions and improve
referents and transitions. No section or paragraph was reordered. One Results
passage combines two sentences about observed follow-up. The citation-flow fix
shortens redundant wording and keeps the citation with the preceding word.

The structure, four research questions, eight objectives, scientific argument,
qualifications and technical content remain intact. Abstract, acknowledgements,
ten appendices, bibliography, Main configuration, figures and table inputs remain
byte-identical. No facts or citations were added; no experiment, model fit,
bootstrap sampling, simulation, code change, commit, push or Overleaf update was
performed. The revised sources and PDF are local and ready for author review.

## Guide checker counts

These are Section 9 prose-checker counts, not an institutional whole-thesis word
count. They cover the abstract, five chapters and ten appendix narratives. Fixed
numerical table bodies, bibliography and front matter are excluded by this count.

**22,357 → 22,216 checked prose words (0.63% shorter).**

| File | Before | After |
|---|---:|---:|
| abstract.tex | 313 | 313 |
| introduction.tex | 1,546 | 1,485 |
| literature_review.tex | 5,019 | 4,994 |
| methodology.tex | 7,362 | 7,352 |
| results.tex | 5,000 | 4,956 |
| conclusion.tex | 1,633 | 1,632 |
| appendix_a.tex | 28 | 28 |
| appendix_b.tex | 36 | 36 |
| appendix_c.tex | 161 | 161 |
| appendix_d.tex | 84 | 84 |
| appendix_e.tex | 71 | 71 |
| appendix_f.tex | 209 | 209 |
| appendix_g.tex | 110 | 110 |
| appendix_h.tex | 274 | 274 |
| appendix_i.tex | 373 | 373 |
| appendix_j.tex | 138 | 138 |

| Checker pattern | Before | After |
|---|---:|---:|
| em/en dash in prose | 0 | 0 |
| semicolon | 93 | 93 |
| stock words | 3 | 2 |
| generic openers | 0 | 0 |
| throat-clearing | 0 | 0 |
| opener This/These/It | 169 | 169 |
| participial tail | 1 | 1 |
| contrast template | 42 | 40 |
| caveat phrase | 7 | 7 |
| balanced pair (, while / , whereas) | 51 | 50 |
| without + -ing caveat | 12 | 12 |
| appositive summary tail | 0 | 0 |
| justification (since / so that) | 4 | 4 |
| copula avoidance | 1 | 1 |
| three-item list (rough; check by hand) | 292 | 293 |
| plain 'but' (keep) | 22 | 20 |
| self-reference (the study will...) | 0 | 0 |
| meta-discourse words | 231 | 229 |
| hypothetical modals (would/could/may/might) | 25 | 25 |
| summary/meta | 7 | 6 |
| substitute phrases | 0 | 0 |
| neither/nor | 3 | 3 |
| instead/whereas/likewise | 13 | 13 |
| assistant artefacts | 0 | 0 |
| placeholders/notes | 0 | 0 |
| process notes | 1 | 1 |
| tool names | 0 | 0 |

The two remaining stock-word matches are the LaTeX `landscape` environment name,
not running prose. The process-note match describes checking SHAP output against
its analytic expression, which is an implemented verification method. Real
technical inventories account for rough list matches. Semicolons, necessary
contrasts and accurate technical qualifications were retained where they read
clearly. The two removed “but” matches belonged to “not only … but also” formulas;
plain contrasts were not systematically suppressed. Numerical targets were used
as diagnostics and did not justify rewriting accurate prose.

## Meaning-sensitive passages checked

Locations use section names and paragraph openings; source line numbers are stable
because the edits replace individual source lines.

| Location | Meaning preserved |
|---|---|
| Introduction, Background, closing paragraph (line19) | Both whether and when clinical events occur remain linked to incomplete follow-up. |
| Introduction, Problem Statement, opening paragraph (line53) | The prior/likelihood/posterior relationship and qualified effect on estimation, uncertainty and prediction are retained. |
| Literature Review, Foundations, Perera and Dwivedi paragraph (line9) | Observation information and whether the analysis answers the question remain complementary considerations; no new agreement between papers is asserted. |
| Methodology, Survival and Hazard Functions (line172) | The formerly vague “they” explicitly refers to survival and hazard functions. |
| Methodology, Piecewise-Exponential Model (line240) | Baseline hazard varies across intervals; covariate effects retain proportional hazards. |
| Methodology, posterior-distribution explanation (line271) | Sentence splitting retains posterior means, 95% credible intervals, hazard-ratio distributions and directional probabilities. |
| Methodology, Prior-Sensitivity Methodology, opening paragraph (line527) | Only “to this assessment” was removed; the information-relative-to-likelihood rationale remains. A nonbreaking space prevents an isolated citation across the page break. |
| Results, GBSG2 subsection (line63) | Two sentences become one; observed median/quartiles remain distinct from the censoring-adjusted Kaplan–Meier median. |
| Results, Cross-Cohort Comparison (line120) | Sample size, events, censoring, covariate structure and clinical setting still qualify within-cohort interpretation. |
| Conclusion, External Validation (line131) | Independent healthcare cohorts remain the proposed validation setting; repeated wording about independent populations is simplified. |

Other changes are local grammar or word choice with no intended change in meaning.
All changed paragraphs were reread alongside the unchanged surrounding argument.

## Verification

- Citation-key occurrences and claim attachments, all labels/reference occurrences,
  heading titles, exact aim/objectives/questions, numeric-token occurrences,
  mathematical expressions, footnotes, technical identifiers and full protected
  table/figure/code/quotation blocks pass comparison with the baseline.
- All tracked files outside the five edited chapter sources and rebuilt PDF
  retain their baseline hashes. The bibliography has100 unique entries, all cited,
  with no duplicate publication URLs. Active labels are unique and all reference
  targets resolve. Tables, figure data, saved results and statistical settings
  are unchanged.
- Eleven existing focused reporting tests pass. Coordination schemas and Git
  whitespace checks pass. No new tests or model-suite result are claimed.
- A fresh extraction of the final 61-file active source ZIP builds using canonical
  `make thesis` from the project root. The final PDF has 128 pages, 46 tables and
  seven figures. The final log has zero LaTeX warnings, undefined citations or
  references, overfull/underfull boxes or oversized-float warnings. Existing
  nonfatal engine notices are not scientific or layout errors.
- Visual review covered the complete page overview and readable detail for
  revised passages, all seven figures, numerical tables and continuations,
  dense posterior tables, landscape tables, front matter and references.
  The citation-flow fix was rebuilt and its affected PDF pages 51–52 reinspected.
  Other page texts are unchanged by that final adjustment.
- The existing cleared PDF metadata policy is preserved: authoring fields remain
  blank, with no document ID, XMP or attachments. The cover remains unchanged.
- The previous 128-page PDF and all six older source archives are preserved and
  hash-checked. The final active ZIP includes the same 61 required source/figure
  files as the previous verified package, with only the five chapter sources
  changed. Its payloads match the delivered sources.

## Deliverables

- Updated thesis sources and `thesis-overleaf/Main.pdf`.
- `reports/thesis_final/Ravi_Thesis_Conservative_Prose_2026-11-19.pdf`.
- `reports/thesis_final/Ravi_Thesis_Overleaf_2026-11-19_conservative_prose.zip`.
- Preserved previous PDF: `reports/thesis_final/Ravi_Thesis_Before_Conservative_Prose_2026-11-19.pdf`.

## Flags and assumptions

No unresolved factual, attribution, placeholder or author-action flag was found
in this style pass. Interpretation-essential uncertainty and original/post-hoc
boundaries remain in their existing locations. A style edit does not provide a
new scientific or clinical validation.

Assumptions: preserve the current compiled scope, headings, British English and
impersonal academic voice; retain all author-owned text and the established
metadata exclusions; make only changes with a clear local benefit. The shared
Overleaf/GitHub publication remains at its prior revision until publication is
explicitly requested.

Final PDF SHA-256: `d35fdc4a1cd9682445708d810f9d0b88ac013491a8f17fa792c971af975f12b9`.
Final source ZIP SHA-256: `b064b7a9f27d155d657043e29bae465b75649c57b206a04d25587d4741ca71be`.
