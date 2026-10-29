"""Detect where what a party says differs from what it does, plus the expert calibration gap."""

from collections import defaultdict

from service.party_orientation_model.contracts import (
    BEHAVIOR_LAYERS,
    DIMENSION_OVERALL,
    LAYER_DISCOURSE,
    LAYER_EXPERT,
    SCORING_DIMENSIONS,
    Rubric,
    ScoredEvidence,
)
from service.party_orientation_model.scoring import score_dimension, weighted_mean

DIRECTION_TEXT = {
    1: "comporta-se mais à direita do que declara",
    -1: "comporta-se mais à esquerda do que declara",
}


def _severity(gap: float, threshold: float) -> str:
    return "strong" if abs(gap) >= 2 * threshold else "moderate"


def _record(kind: str, subject: str, discourse: float, behavior: float, threshold: float) -> dict:
    gap = behavior - discourse
    return {
        "kind": kind,
        "subject": subject,
        "discourse_score": discourse,
        "behavior_score": behavior,
        "gap": gap,
        "severity": _severity(gap, threshold),
        "explanation": f"No eixo '{subject}', o partido {DIRECTION_TEXT[1 if gap > 0 else -1]} "
        f"(discurso {discourse:+.2f}, comportamento {behavior:+.2f}; -1 esquerda a +1 direita).",
    }


def layer_split(items: list[ScoredEvidence]) -> tuple[list[ScoredEvidence], list[ScoredEvidence]]:
    behavior = [s for s in items if s.item.layer in BEHAVIOR_LAYERS and s.weight > 0]
    discourse = [s for s in items if s.item.layer == LAYER_DISCOURSE and s.weight > 0]
    return behavior, discourse


def behavior_dimension_scores(items: list[ScoredEvidence], rubric: Rubric) -> dict[str, float]:
    behavior, _ = layer_split(items)
    scores = {}
    for dimension in SCORING_DIMENSIONS:
        scored = score_dimension([s for s in behavior if s.item.dimension == dimension], rubric)
        if scored is not None:
            scores[dimension] = scored.score
    return scores


def dimension_divergences(items: list[ScoredEvidence], rubric: Rubric) -> list[dict]:
    behavior, discourse = layer_split(items)
    records = []
    for dimension in SCORING_DIMENSIONS:
        behavior_items = [s for s in behavior if s.item.dimension == dimension]
        discourse_items = [s for s in discourse if s.item.dimension == dimension]
        if not behavior_items or not discourse_items:
            continue
        behavior_score = score_dimension(behavior_items, rubric).score
        discourse_score = score_dimension(discourse_items, rubric).score
        if abs(behavior_score - discourse_score) >= rubric.divergence_dimension_threshold:
            record = _record(
                "dimension",
                dimension,
                discourse_score,
                behavior_score,
                rubric.divergence_dimension_threshold,
            )
            records.append(record | _evidence_ids(behavior_items, discourse_items))
    return records


def indicator_divergences(items: list[ScoredEvidence], rubric: Rubric) -> list[dict]:
    behavior, discourse = layer_split(items)
    behavior_by_indicator, discourse_by_indicator = (
        _by_indicator(behavior),
        _by_indicator(discourse),
    )
    records = []
    for indicator_id in sorted(set(behavior_by_indicator) & set(discourse_by_indicator)):
        behavior_mean, _ = weighted_mean(behavior_by_indicator[indicator_id])
        discourse_mean, _ = weighted_mean(discourse_by_indicator[indicator_id])
        if abs(behavior_mean - discourse_mean) >= rubric.divergence_indicator_threshold:
            record = _record(
                "indicator",
                indicator_id,
                discourse_mean,
                behavior_mean,
                rubric.divergence_indicator_threshold,
            )
            records.append(
                record
                | _evidence_ids(
                    behavior_by_indicator[indicator_id], discourse_by_indicator[indicator_id]
                )
            )
    return records


def self_declaration_divergence(
    items: list[ScoredEvidence], behavior_overall: float | None, rubric: Rubric
) -> list[dict]:
    declared = [
        s
        for s in items
        if s.item.layer == LAYER_DISCOURSE
        and s.item.dimension == DIMENSION_OVERALL
        and s.weight > 0
    ]
    if not declared or behavior_overall is None:
        return []
    declared_mean, _ = weighted_mean(declared)
    if abs(behavior_overall - declared_mean) < rubric.divergence_dimension_threshold:
        return []
    record = _record(
        "self_declaration",
        "overall",
        declared_mean,
        behavior_overall,
        rubric.divergence_dimension_threshold,
    )
    return [
        record
        | {
            "discourse_evidence_ids": sorted(s.item.evidence_id for s in declared),
            "behavior_evidence_ids": [],
        }
    ]


def expert_calibration(
    items: list[ScoredEvidence], model_overall: float | None, rubric: Rubric
) -> dict | None:
    """Expert surveys are a reference for calibration, never an input of the score."""
    experts = [s for s in items if s.item.layer == LAYER_EXPERT and s.weight > 0]
    if not experts:
        return None
    mean, _ = weighted_mean(experts)
    gap = None if model_overall is None else model_overall - mean
    return {
        "expert_reference_score": mean,
        "model_overall_score": model_overall,
        "gap": gap,
        "exceeds_threshold": gap is not None and abs(gap) >= rubric.calibration_gap_threshold,
        "evidence_ids": sorted(s.item.evidence_id for s in experts),
        "note": "Pesquisa de especialistas é referência de calibração; não entra na pontuação.",
    }


def _by_indicator(items: list[ScoredEvidence]) -> dict[str, list[ScoredEvidence]]:
    grouped = defaultdict(list)
    for scored in items:
        grouped[scored.item.indicator_id].append(scored)
    return grouped


def _evidence_ids(behavior: list[ScoredEvidence], discourse: list[ScoredEvidence]) -> dict:
    return {
        "behavior_evidence_ids": sorted(s.item.evidence_id for s in behavior),
        "discourse_evidence_ids": sorted(s.item.evidence_id for s in discourse),
    }
