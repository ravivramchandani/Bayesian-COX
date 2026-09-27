# Brief: documentation pass for readability

## Role

Implementer. One package per implementer, each in its own git worktree
branch.

## Goal

Every module, class and function explains clearly and accurately what it
does, why, and how it fits into the pipeline, so a master's student with a
statistics and machine-learning background can read the code without help.
No executable code changes.

## Hard rule: documentation only

Change only comments, docstrings and line wrapping. The gate below must pass:
after docstrings are removed, every edited file's syntax tree must be
identical to the base revision.

```bash
PY=/Users/macuser/miniconda3/envs/bayes-cox-lock-verify-20260815-b/bin/python
$PY /Users/macuser/bayes-cox-runs/harness/ast_equivalence.py . <base commit>
$PY -m pytest -q
$PY -m ruff check .
```

The gate must report every changed file as documentation-only. The tests must
pass and Ruff must be clean.

If you find a bug or a misleading name, do not fix it. Describe it in your
report.

## What to write

**Module docstring**
- What the module is for, and where it sits in the pipeline (which stage
  calls it, and what it produces).
- Its main entry points.

**Public function or class**
- A one-line summary.
- A short plain-language explanation of the method when it is not obvious,
  for example what IPCW weighting corrects for, or why the Nadeau–Bengio
  variance is inflated.
- `Args:`, `Returns:` and, where relevant, `Raises:` sections, in Google
  style. State units, scales, array shapes and allowed values. Examples:
  - times are in the cohort's own unit (days or months);
  - risk scores differ by model;
  - arrays are indexed by subject.

**Private helper**
- A one-line docstring, plus `Args:` if the parameters are not obvious.

**Test function**
- A one-line docstring saying what behaviour or rule the test protects. Name
  the invariant (INV-00N) or decision record (ADR-0NN) where one applies.

**Inline comments**
- Explain *why*, at the steps a reader would otherwise stop at:
  - statistical formulas;
  - edge cases;
  - orderings kept for reproducibility, such as the order of random-number
    use;
  - defensive checks.
- In long functions, a short comment above a group of lines may name the
  step the group performs.
- Never restate a line of code.

**Abbreviations**
- Define each at first use in a module: IBS, IPCW, OOF, NB (Nadeau–Bengio),
  PH, NUTS, ESS, R-hat, BFMI, SHAP, RQ1–RQ4, and so on.

## Accuracy

- Every sentence must be true of the code as written. Read the function
  body, and any function it calls where that matters, before writing.
- Do not describe intended behaviour, planned features or results.
- When an existing docstring is wrong or incomplete, correct it and list the
  correction in your report.
- If you are unsure what something does, trace it or leave it undocumented;
  never guess.

## Style

- British spelling (normalise, artefact), matching the repository.
- Plain, professional language. No banners, decorative rules or process
  narration, and no references to refactors, agents or AI.
- Keep docstrings proportionate: a two-line helper does not need a page.

## Report

Keep the report under 400 words. Include:
- the files changed;
- the gate output;
- every existing docstring corrected, and why;
- any suspected bug or misleading name you left unchanged.

Commit on your branch with a plain descriptive message and no co-author
trailer.
