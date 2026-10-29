"""Sufficiency rules and explicit confidence per dimension; no guessing from thin evidence."""

from dataclasses import dataclass
from math import sqrt

from service.party_orientation_model.contracts import BEHAVIOR_LAYERS, Rubric, ScoredEvidence
from service.party_orientation_model.scoring import DimensionScore, group_by_layer, score_dimension

STATUS_SUFFICIENT = "sufficient"
STATUS_INSUFFICIENT = "insufficient_evidence"
CONFIDENCE_LABELS = ("low", "medium", "high")


@dataclass(frozen=True)
class DimensionAssessment:
    dimension: str
    status: str
    insufficiency_reasons: tuple[str, ...]
    score: DimensionScore | None
    item_count: int
    behavior_item_count: int
    indicator_count: int
    source_count: int
    confidence: float
    confidence_terms: dict[str, float]
    layers_agree: bool | None

    @property
    def is_sufficient(self) -> bool:
        return self.status == STATUS_SUFFICIENT


def counted_items(items: list[ScoredEvidence], rubric: Rubric) -> list[ScoredEvidence]:
    grouped = group_by_layer(items, rubric)
    return [scored for layer in sorted(grouped) for scored in grouped[layer]]


def insufficiency_reasons(
    dimension: str, counted: list[ScoredEvidence], rubric: Rubric
) -> tuple[str, ...]:
    if not counted:
        return ("no_scoring_evidence",)
    rules = rubric.sufficiency
    behavior = [s for s in counted if s.item.layer in BEHAVIOR_LAYERS]
    checks = (
        ("too_few_evidence_items", len(counted) < rules.minimum_items),
        ("too_few_behavior_items", len(behavior) < rules.minimum_behavior_items),
        (
            "too_few_distinct_indicators",
            len({s.item.indicator_id for s in counted}) < rules.minimum_indicators[dimension],
        ),
        (
            "too_few_distinct_sources",
            len({s.item.source_id for s in counted}) < rules.minimum_sources,
        ),
    )
    return tuple(reason for reason, failed in checks if failed)


def layer_coverage(score: DimensionScore, rubric: Rubric) -> float:
    present = sum(rubric.layer_weights[layer.layer] for layer in score.layer_scores)
    return present / sum(rubric.layer_weights.values())


def agreement_among_items(counted: list[ScoredEvidence], score: DimensionScore) -> float:
    total = sum(s.weight for s in counted)
    variance = sum(s.weight * (s.oriented_stance - score.score) ** 2 for s in counted) / total
    return 1 - min(1.0, sqrt(variance))


def layers_agree(score: DimensionScore, tolerance: float = 0.1) -> bool | None:
    """True when layer means point to the same side (or are near zero); None for a single layer."""
    if len(score.layer_scores) < 2:
        return None
    signs = {
        0 if abs(layer.mean) < tolerance else (1 if layer.mean > 0 else -1)
        for layer in score.layer_scores
    }
    return len(signs - {0}) <= 1


def confidence_terms(
    counted: list[ScoredEvidence], score: DimensionScore, rubric: Rubric
) -> dict[str, float]:
    low, high = score.interval
    return {
        "count": min(1.0, len(counted) / rubric.confidence_target_items),
        "layers": layer_coverage(score, rubric),
        "agreement": agreement_among_items(counted, score),
        "precision": max(0.0, 1 - (high - low) / rubric.confidence_precision_scale),
    }


def confidence_value(terms: dict[str, float], rubric: Rubric) -> float:
    return sum(rubric.confidence_weights[name] * value for name, value in terms.items())


def confidence_label(confidence: float, rubric: Rubric) -> str:
    low_limit, high_limit = rubric.confidence_labels
    if confidence < low_limit:
        return CONFIDENCE_LABELS[0]
    return CONFIDENCE_LABELS[1] if confidence < high_limit else CONFIDENCE_LABELS[2]


def assess_dimension(
    dimension: str, items: list[ScoredEvidence], rubric: Rubric
) -> DimensionAssessment:
    counted = counted_items(items, rubric)
    score = score_dimension(counted, rubric)
    reasons = list(insufficiency_reasons(dimension, counted, rubric))
    terms, confidence = {}, 0.0
    if score is not None:
        terms = confidence_terms(counted, score, rubric)
        confidence = confidence_value(terms, rubric)
    if score is not None and confidence < rubric.sufficiency.minimum_confidence:
        reasons.append("confidence_below_minimum")
    return DimensionAssessment(
        dimension=dimension,
        status=STATUS_INSUFFICIENT if reasons or score is None else STATUS_SUFFICIENT,
        insufficiency_reasons=tuple(reasons or (() if score else ("no_scoring_evidence",))),
        score=score,
        item_count=len(counted),
        behavior_item_count=sum(1 for s in counted if s.item.layer in BEHAVIOR_LAYERS),
        indicator_count=len({s.item.indicator_id for s in counted}),
        source_count=len({s.item.source_id for s in counted}),
        confidence=confidence,
        confidence_terms=terms,
        layers_agree=layers_agree(score) if score else None,
    )
