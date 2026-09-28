"""Load real cohorts, construct survival folds and fit training-only preprocessing.

The pipelines use ``cohorts`` for outcomes and feature declarations,
``survival_folds`` for paired validation indices, and ``fold_preprocessing``
for transformations whose learned state comes only from training rows.
"""
