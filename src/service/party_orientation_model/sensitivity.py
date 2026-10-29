"""Re-weigh the evidence classes to see whether categories depend on the approved 70/20/10."""

from dataclasses import replace

from service.party_orientation_model.contracts import (
    BEHAVIOR_LAYERS,
    CATEGORY_INSUFFICIENT,
    LAYER_DISCOURSE,
    Rubric,
)

SCENARIOS = (("85/10/5", 0.85, 0.10), ("50/40/10", 0.50, 0.40))  # behavior, statements


def with_class_weights(rubric: Rubric, behavior_share: float, statements_share: float) -> Rubric:
    """Behavior layers keep their proportions; external estimates stay at their own weight."""
    current = sum(rubric.layer_weights[layer] for layer in BEHAVIOR_LAYERS)
    weights = {
        layer: weight * behavior_share / current if layer in BEHAVIOR_LAYERS else weight
        for layer, weight in rubric.layer_weights.items()
    }
    weights[LAYER_DISCOURSE] = statements_share
    return replace(rubric, layer_weights=weights)


def category_changes(base: list[dict], scenario: list[dict]) -> dict:
    by_key = {(d["political_party_id"], d["period"]["period_id"]): d["category"] for d in base}
    changed = sum(
        1
        for d in scenario
        if by_key[(d["political_party_id"], d["period"]["period_id"])] != d["category"]
    )
    return {
        "combinations": len(scenario),
        "changed": changed,
        "classified_in_base": sum(1 for c in by_key.values() if c != CATEGORY_INSUFFICIENT),
    }
