"""Score one dimension: weighted mean per layer; behavior always outweighs discourse."""

from dataclasses import dataclass
from math import sqrt

from service.party_orientation_model.contracts import (
    BEHAVIOR_LAYERS,
    LAYER_DISCOURSE,
    Rubric,
    ScoredEvidence,
)

Z_95 = 1.96


@dataclass(frozen=True)
class LayerScore:
    layer: str
    mean: float
    total_weight: float
    effective_share: float
    standard_error: float
    item_count: int
    effective_sample_size: float


@dataclass(frozen=True)
class DimensionScore:
    score: float
    standard_error: float
    layer_scores: tuple[LayerScore, ...]
    contributions: dict[str, float]

    @property
    def interval(self) -> tuple[float, float]:
        margin = Z_95 * self.standard_error
        return max(-1.0, self.score - margin), min(1.0, self.score + margin)


def group_by_layer(items: list[ScoredEvidence], rubric: Rubric) -> dict[str, list[ScoredEvidence]]:
    """Only layers with a positive rubric weight score; others stay reference material."""
    grouped: dict[str, list[ScoredEvidence]] = {}
    for scored in items:
        if rubric.layer_weights.get(scored.item.layer, 0) > 0 and scored.weight > 0:
            grouped.setdefault(scored.item.layer, []).append(scored)
    return grouped


def weighted_mean(items: list[ScoredEvidence]) -> tuple[float, float]:
    total = sum(scored.weight for scored in items)
    return sum(scored.weight * scored.oriented_stance for scored in items) / total, total


def effective_sample_size(items: list[ScoredEvidence]) -> float:
    total = sum(scored.weight for scored in items)
    return total * total / sum(scored.weight**2 for scored in items)


def layer_standard_error(items: list[ScoredEvidence], mean: float, prior_deviation: float) -> float:
    """Shrunk variance (prior pulls a thin sample toward doubt) over the effective sample."""
    total = sum(scored.weight for scored in items)
    sample_size = effective_sample_size(items)
    variance = sum(s.weight * (s.oriented_stance - mean) ** 2 for s in items) / total
    shrunk = (sample_size * variance + prior_deviation**2) / (sample_size + 1)
    return sqrt(shrunk / sample_size)


def effective_layer_weights(layers: list[str], rubric: Rubric) -> dict[str, float]:
    """Discourse is capped below the behavior weight actually present: behavior always outweighs."""
    weights = {layer: rubric.layer_weights[layer] for layer in layers}
    behavior_total = sum(weight for layer, weight in weights.items() if layer in BEHAVIOR_LAYERS)
    if LAYER_DISCOURSE in weights and behavior_total > 0:
        weights[LAYER_DISCOURSE] = min(
            weights[LAYER_DISCOURSE], rubric.discourse_cap_ratio * behavior_total
        )
    return weights


def build_layer_scores(
    grouped: dict[str, list[ScoredEvidence]], rubric: Rubric
) -> tuple[LayerScore, ...]:
    weights = effective_layer_weights(sorted(grouped), rubric)
    total_weight = sum(weights.values())
    scores = []
    for layer in sorted(grouped):
        mean, layer_total = weighted_mean(grouped[layer])
        scores.append(
            LayerScore(
                layer=layer,
                mean=mean,
                total_weight=layer_total,
                effective_share=weights[layer] / total_weight,
                standard_error=layer_standard_error(
                    grouped[layer], mean, rubric.prior_standard_deviation
                ),
                item_count=len(grouped[layer]),
                effective_sample_size=effective_sample_size(grouped[layer]),
            )
        )
    return tuple(scores)


def item_contributions(
    grouped: dict[str, list[ScoredEvidence]], layer_scores: tuple[LayerScore, ...]
) -> dict[str, float]:
    contributions = {}
    for layer_score in layer_scores:
        for scored in grouped[layer_score.layer]:
            fraction = scored.weight / layer_score.total_weight
            contributions[scored.item.evidence_id] = (
                layer_score.effective_share * fraction * scored.oriented_stance
            )
    return contributions


def score_dimension(items: list[ScoredEvidence], rubric: Rubric) -> DimensionScore | None:
    grouped = group_by_layer(items, rubric)
    if not grouped:
        return None
    layer_scores = build_layer_scores(grouped, rubric)
    score = sum(layer.effective_share * layer.mean for layer in layer_scores)
    error = sqrt(sum((layer.effective_share * layer.standard_error) ** 2 for layer in layer_scores))
    return DimensionScore(
        score=max(-1.0, min(1.0, score)),
        standard_error=error,
        layer_scores=layer_scores,
        contributions=item_contributions(grouped, layer_scores),
    )
