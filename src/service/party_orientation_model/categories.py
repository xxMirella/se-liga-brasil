"""Final categories: seven bands; extremes need a confirmed, documented, reviewed gate."""

from dataclasses import dataclass

from service.party_orientation_model.applicability import meets_proof_level
from service.party_orientation_model.contracts import (
    BEHAVIOR_LAYERS,
    CATEGORY_CONTROVERSIAL,
    CATEGORY_EXTREME_LEFT,
    CATEGORY_EXTREME_RIGHT,
    CATEGORY_MIXED_PROFILE,
    ORDERED_BAND_CATEGORIES,
    Rubric,
    ScoredEvidence,
)

EXTREME_SIDES = ((CATEGORY_EXTREME_LEFT, -1), (CATEGORY_EXTREME_RIGHT, 1))


@dataclass(frozen=True)
class CategoryDecision:
    category: str
    base_category: str
    notes: tuple[str, ...]
    documented_extreme_markers: tuple[str, ...]


def band_index(score: float, limits: tuple[float, ...]) -> int:
    for index, limit in enumerate(limits):
        if score <= limit:
            return index
    return len(limits)


def band_category(score: float, limits: tuple[float, ...]) -> str:
    return ORDERED_BAND_CATEGORIES[band_index(score, limits)]


def extreme_candidate(dimension_scores: dict[str, float], rubric: Rubric) -> str | None:
    """Intensity condition: at least one dimension beyond the extreme score on that side."""
    for category, sign in EXTREME_SIDES:
        minimum = rubric.extreme_criteria[category].minimum_abs_score
        if any(sign * score >= minimum for score in dimension_scores.values()):
            return category
    return None


def qualifying_marker_evidence(
    items: list[ScoredEvidence], category: str, rubric: Rubric
) -> list[ScoredEvidence]:
    criterion = rubric.extreme_criteria[category]
    return [
        scored
        for scored in items
        if set(scored.item.extreme_markers) & set(criterion.marker_ids)
        and meets_proof_level(scored.item, criterion.minimum_proof_level)
        and (scored.item.human_reviewed or not criterion.require_human_review)
        and scored.carried_from is None
    ]


def documented_markers(
    items: list[ScoredEvidence], category: str, rubric: Rubric
) -> tuple[str, ...]:
    criterion = rubric.extreme_criteria[category]
    found = set()
    for scored in qualifying_marker_evidence(items, category, rubric):
        found |= set(scored.item.extreme_markers) & set(criterion.marker_ids)
    return tuple(sorted(found))


def gate_failures(items: list[ScoredEvidence], category: str, rubric: Rubric) -> list[str]:
    """Why the extreme gate is not confirmed; an empty list means confirmed."""
    criterion = rubric.extreme_criteria[category]
    qualifying = qualifying_marker_evidence(items, category, rubric)
    markers = documented_markers(items, category, rubric)
    checks = (
        ("marcadores documentados insuficientes", len(markers) < criterion.minimum_markers),
        (
            "fontes independentes insuficientes",
            len({s.item.source_id for s in qualifying}) < criterion.minimum_sources,
        ),
        (
            "falta marcador em evidência de comportamento",
            criterion.require_behavior_marker
            and not any(s.item.layer in BEHAVIOR_LAYERS for s in qualifying),
        ),
        (
            "falta evidência primária",
            not any(s.item.proof_level == "documented_primary" for s in qualifying),
        ),
    )
    return [text for text, failed in checks if failed]


def decide_category(
    score: float,
    interval: tuple[float, float],
    dimension_scores: dict[str, float],
    items: list[ScoredEvidence],
    rubric: Rubric,
) -> CategoryDecision:
    limits = rubric.band_limits
    base = band_category(score, limits)
    span = band_index(interval[1], limits) - band_index(interval[0], limits)
    if span >= rubric.controversy_span_steps:
        note = f"intervalo de confiança cobre {span + 1} faixas; evidência não sustenta categoria"
        return CategoryDecision(CATEGORY_CONTROVERSIAL, base, (note,), ())
    candidate = extreme_candidate(dimension_scores, rubric)
    if candidate is not None:
        decision = _decide_extreme(candidate, base, items, rubric)
        if decision.category == candidate:
            return decision
        return _mixed_or_base(dimension_scores, base, decision, rubric)
    return _mixed_or_base(dimension_scores, base, None, rubric)


def _mixed_or_base(
    dimension_scores: dict[str, float], base: str, extreme: CategoryDecision | None, rubric: Rubric
) -> CategoryDecision:
    notes = extreme.notes if extreme else ()
    markers = extreme.documented_extreme_markers if extreme else ()
    left_edge, right_edge = rubric.band_limits[2], rubric.band_limits[3]
    sides = {
        -1 if s <= left_edge else 1 if s >= right_edge else 0 for s in dimension_scores.values()
    }
    if {-1, 1} <= sides:
        note = "dimensões econômica e sociocultural em lados opostos; sem rótulo único"
        return CategoryDecision(CATEGORY_MIXED_PROFILE, base, (*notes, note), markers)
    return CategoryDecision(base, base, notes, markers)


def _decide_extreme(
    candidate: str, base: str, items: list[ScoredEvidence], rubric: Rubric
) -> CategoryDecision:
    markers = documented_markers(items, candidate, rubric)
    failures = gate_failures(items, candidate, rubric)
    if not failures:
        return CategoryDecision(candidate, base, ("gate extremista confirmado",), markers)
    note = (
        f"intensidade na faixa de {candidate} sem gate confirmado ({'; '.join(failures)}); "
        f"mantida '{base}'"
    )
    return CategoryDecision(base, base, (note,), markers)
