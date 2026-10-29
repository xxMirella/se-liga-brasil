"""Readable per-indicator explanation: which evidence pulled the score to which side."""

from collections import defaultdict

from service.party_orientation_model.assessment import DimensionAssessment
from service.party_orientation_model.contracts import Rubric, ScoredEvidence

NEUTRAL_BAND = 0.005
PUSH_TEXT = {"right": "direita", "left": "esquerda", "neutral": "sem inclinação"}


def push_side(value: float) -> str:
    if abs(value) < NEUTRAL_BAND:
        return "neutral"
    return "right" if value > 0 else "left"


def _item_entry(scored: ScoredEvidence, contribution: float) -> dict:
    return {
        "evidence_id": scored.item.evidence_id,
        "layer": scored.item.layer,
        "oriented_stance": scored.oriented_stance,
        "weight": scored.weight,
        "contribution": contribution,
        "pulls": push_side(contribution),
        "source_url": scored.item.source_url,
    }


def explain_dimension(
    assessment: DimensionAssessment, counted: list[ScoredEvidence], rubric: Rubric
) -> list[dict]:
    if assessment.score is None:
        return []
    by_indicator = defaultdict(list)
    for scored in counted:
        by_indicator[scored.item.indicator_id].append(scored)
    entries = []
    for indicator_id, members in by_indicator.items():
        contributions = assessment.score.contributions
        items = sorted(
            (_item_entry(s, contributions[s.item.evidence_id]) for s in members),
            key=lambda entry: (-abs(entry["contribution"]), entry["evidence_id"]),
        )
        net = sum(entry["contribution"] for entry in items)
        entries.append(
            {
                "dimension": assessment.dimension,
                "indicator_id": indicator_id,
                "label": rubric.indicators[indicator_id].label,
                "net_contribution": net,
                "pulls": push_side(net),
                "evidence": items,
            }
        )
    return sorted(
        entries, key=lambda entry: (-abs(entry["net_contribution"]), entry["indicator_id"])
    )


def summarize(explanations: list[dict], limit: int = 3) -> list[str]:
    lines = []
    for entry in explanations[:limit]:
        lead = entry["evidence"][0]
        lines.append(
            f"{entry['label']} ({entry['dimension']}): puxa para {PUSH_TEXT[entry['pulls']]} "
            f"({entry['net_contribution']:+.3f}); principal evidência {lead['evidence_id']} "
            f"na camada {lead['layer']}."
        )
    return lines
