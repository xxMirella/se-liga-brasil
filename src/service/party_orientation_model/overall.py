"""Combine dimension scores into one left-right score using the rubric's dimension weights."""

from dataclasses import dataclass
from math import sqrt

from service.party_orientation_model.assessment import DimensionAssessment
from service.party_orientation_model.contracts import Rubric
from service.party_orientation_model.scoring import Z_95


@dataclass(frozen=True)
class OverallScore:
    score: float
    standard_error: float
    confidence: float
    dimensions_used: tuple[str, ...]

    @property
    def interval(self) -> tuple[float, float]:
        margin = Z_95 * self.standard_error
        return max(-1.0, self.score - margin), min(1.0, self.score + margin)


def combine_dimensions(
    assessments: dict[str, DimensionAssessment], rubric: Rubric
) -> tuple[OverallScore | None, tuple[str, ...]]:
    """None plus reasons unless every dimension required by the rubric is sufficient."""
    missing = tuple(
        f"required_dimension_insufficient:{name}"
        for name in rubric.sufficiency.required_dimensions
        if not assessments[name].is_sufficient
    )
    if missing:
        return None, missing
    usable = {name: a for name, a in assessments.items() if a.is_sufficient}
    total = sum(rubric.dimension_weights[name] for name in usable)
    if total <= 0:
        return None, ("dimension_weights_zero_for_available_dimensions",)
    shares = {name: rubric.dimension_weights[name] / total for name in usable}
    score = sum(shares[name] * usable[name].score.score for name in usable)
    error = sqrt(sum((shares[name] * usable[name].score.standard_error) ** 2 for name in usable))
    confidence = min(assessment.confidence for assessment in usable.values())
    return OverallScore(score, error, confidence, tuple(sorted(usable))), ()


def combine_behavior_scores(dimension_scores: dict[str, float], rubric: Rubric) -> float | None:
    total = sum(rubric.dimension_weights[name] for name in dimension_scores)
    if not dimension_scores or total <= 0:
        return None
    return (
        sum(rubric.dimension_weights[name] * score for name, score in dimension_scores.items())
        / total
    )
