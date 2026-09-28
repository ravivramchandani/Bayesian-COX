"""Seeded, paired subject and background selection for frozen-cell explanations.

Each fold uses seeded permutations shared by every prior and its Cox partner;
larger budgets extend the same permutations without drawing another sample.

Two properties follow. Selections are *paired*: the seeds depend on the
dataset, repeat, fold and explanation seed but not on the model, so every
Bayesian prior and the Cox model of a fold explain the same subjects against
the same background. Selections are *nested*: a budget takes the first ``n``
positions of a fixed permutation, so each smaller selection is contained in
the next larger one and the convergence gate measures the effect of adding
subjects rather than of drawing a new sample.

:func:`paired_selections` is called once per Bayesian cell by
:mod:`src.explainability.frozen_cells`."""

from __future__ import annotations

from typing import Any

import numpy as np

from src.explainability.protocol import ExplanationProtocol, _stable_seed
from src.utils.reproducibility import canonical_json_hash

# Row positions are used to slice arrays but are not part of a selection's
# identity, so the registry stores selections without them.
POSITION_KEYS = frozenset({"validation_positions", "background_positions"})


def paired_selections(
    train_ids: list[str],
    validation_ids: list[str],
    *,
    dataset: str,
    repeat: int,
    fold: int,
    protocol: ExplanationProtocol,
) -> list[dict[str, Any]]:
    """Choose the explained subjects and background for every seed and budget of a fold.

    A budget larger than the fold is capped at the fold size, so the
    requested and effective sizes are both recorded. Each selection is
    identified by ``selection_sha256``, a hash of the dataset, fold, seeds,
    requested budget and chosen subject identifiers.

    Args:
        train_ids: Outer-training subject identifiers, in cell order.
        validation_ids: Outer-validation subject identifiers, in cell order.
        dataset: Dataset key.
        repeat: Outer repeat number.
        fold: Outer fold number.
        protocol: Seeds and budgets to use.

    Returns:
        One record per ``(seed, budget)``, seed-major. ``validation_positions``
        and ``background_positions`` index into ``validation_ids`` and
        ``train_ids``.
    """
    selections: list[dict[str, Any]] = []
    for seed in protocol.seeds:
        # Subjects and background use separate derived seeds, and neither
        # includes the model key, which is what pairs the selections across
        # priors and Cox.
        subject_seed = _stable_seed(seed, dataset, repeat, fold, "subjects")
        background_seed = _stable_seed(seed, dataset, repeat, fold, "background")
        subject_order = np.random.default_rng(subject_seed).permutation(len(validation_ids))
        background_order = np.random.default_rng(background_seed).permutation(len(train_ids))
        for budget_index, budget in enumerate(protocol.budgets, start=1):
            n_subjects = min(budget.validation_subjects, len(validation_ids))
            n_background = min(budget.training_background, len(train_ids))
            subject_positions = subject_order[:n_subjects]
            background_positions = background_order[:n_background]
            selected_ids = [validation_ids[index] for index in subject_positions]
            background_ids = [train_ids[index] for index in background_positions]
            selection_state = {
                "dataset": dataset,
                "repeat": repeat,
                "fold": fold,
                "seed": seed,
                "derived_subject_seed": subject_seed,
                "derived_background_seed": background_seed,
                "budget_index": budget_index,
                "requested_validation_subjects": budget.validation_subjects,
                "requested_training_background": budget.training_background,
                "validation_subject_ids": selected_ids,
                "training_background_subject_ids": background_ids,
            }
            selections.append(
                {
                    **selection_state,
                    "effective_validation_subjects": n_subjects,
                    "effective_training_background": n_background,
                    "validation_positions": subject_positions.tolist(),
                    "background_positions": background_positions.tolist(),
                    "selection_sha256": canonical_json_hash(selection_state),
                }
            )
    return selections


def register_selection(registry: dict[str, dict[str, Any]], selection: dict[str, Any]) -> None:
    """Record a selection under its hash, failing if another selection has that hash.

    Every prior of a fold registers the same selections, so a repeated hash
    is expected; only a repeated hash with different content is an error.

    Args:
        registry: Selections seen so far, keyed by ``selection_sha256``;
            updated in place. Stored records omit the position lists.
        selection: One record from :func:`paired_selections`.

    Raises:
        RuntimeError: If the hash is already registered with other content.
    """
    registry_record = {key: value for key, value in selection.items() if key not in POSITION_KEYS}
    prior_selection = registry.setdefault(selection["selection_sha256"], registry_record)
    if prior_selection != registry_record:
        raise RuntimeError("selection hash collision detected")
