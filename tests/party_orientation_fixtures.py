"""Small, clearly fictitious fixtures for the party orientation model. Never copied to data/."""

import copy

from service.party_orientation_model.contracts import EVIDENCE_SCHEMA, RUBRIC_SCHEMA, Period
from service.party_orientation_model.evidence import parse_evidence_item
from service.party_orientation_model.rubric import parse_rubric

PERIOD_2019_2022 = Period("2019-2022", 2019, 2022)
PERIOD_2023_2026 = Period("2023-2026", 2023, 2026)
FICTIONAL_SOURCE = "https://example.invalid/fictional-source"

INDICATOR_DIMENSION = {
    "economic_privatization": "economic",
    "economic_social_spending": "economic",
    "economic_labor_regulation": "economic",
    "sociocultural_civil_rights": "sociocultural",
    "sociocultural_traditional_values": "sociocultural",
    "sociocultural_law_and_order": "sociocultural",
    "self_declared_position": "overall",
    "expert_position": "overall",
}

RUBRIC_DOCUMENT = {
    "schema_version": RUBRIC_SCHEMA,
    "rubric_version": "fixture-rubric.1",
    "layer_weights": {
        "votes": 0.30,
        "implemented_policies": 0.25,
        "supported_policies": 0.10,
        "bills": 0.10,
        "thematic_focus": 0.05,
        "discourse": 0.20,
        "expert_survey": 0.0,
    },
    "discourse_cap_ratio": 0.4,
    "proof_multipliers": {"reported": 0.4, "documented_secondary": 0.7, "documented_primary": 1.0},
    "succession_multiplier": 0.7,
    "dimension_weights": {"economic": 0.5, "sociocultural": 0.5},
    "indicators": [
        {
            "indicator_id": "economic_privatization",
            "dimension": "economic",
            "direction": 1,
            "weight": 1.0,
            "label": "Privatizações",
        },
        {
            "indicator_id": "economic_social_spending",
            "dimension": "economic",
            "direction": -1,
            "weight": 1.0,
            "label": "Gasto social",
        },
        {
            "indicator_id": "economic_labor_regulation",
            "dimension": "economic",
            "direction": -1,
            "weight": 0.8,
            "label": "Regulação do trabalho",
        },
        {
            "indicator_id": "sociocultural_civil_rights",
            "dimension": "sociocultural",
            "direction": -1,
            "weight": 1.0,
            "label": "Direitos civis",
        },
        {
            "indicator_id": "sociocultural_traditional_values",
            "dimension": "sociocultural",
            "direction": 1,
            "weight": 1.0,
            "label": "Valores tradicionais",
        },
        {
            "indicator_id": "sociocultural_law_and_order",
            "dimension": "sociocultural",
            "direction": 1,
            "weight": 0.6,
            "label": "Ordem pública",
        },
        {
            "indicator_id": "self_declared_position",
            "dimension": "overall",
            "direction": 1,
            "weight": 1.0,
            "label": "Autodeclaração",
        },
        {
            "indicator_id": "expert_position",
            "dimension": "overall",
            "direction": 1,
            "weight": 1.0,
            "label": "Pesquisa de especialistas",
        },
    ],
    "band_limits": [-0.8, -0.5, -0.15, 0.15, 0.5, 0.8],
    "extreme_criteria": {
        "extreme_left": {
            "minimum_abs_score": 0.8,
            "minimum_markers": 2,
            "minimum_proof_level": "documented_secondary",
            "minimum_sources": 2,
            "require_human_review": True,
            "marker_ids": ["marker_left_a", "marker_left_b", "marker_left_c"],
            "require_behavior_marker": True,
        },
        "extreme_right": {
            "minimum_abs_score": 0.8,
            "minimum_markers": 2,
            "minimum_proof_level": "documented_secondary",
            "minimum_sources": 2,
            "require_human_review": True,
            "marker_ids": ["marker_right_a", "marker_right_b", "marker_right_c"],
            "require_behavior_marker": True,
        },
    },
    "sufficiency": {
        "minimum_items": 4,
        "minimum_behavior_items": 2,
        "minimum_indicators": {"economic": 2, "sociocultural": 2},
        "minimum_sources": 2,
        "minimum_confidence": 0.3,
        "required_dimensions": ["economic", "sociocultural"],
    },
    "divergence": {
        "dimension_threshold": 0.35,
        "indicator_threshold": 0.5,
        "calibration_gap_threshold": 0.3,
    },
    "prior_standard_deviation": 0.5,
    "confidence": {
        "weights": {"count": 0.25, "layers": 0.25, "agreement": 0.25, "precision": 0.25},
        "target_items": 8,
        "precision_scale": 1.0,
        "label_limits": [0.4, 0.7],
    },
    "controversy_span_steps": 3,
    "periods": [
        {"period_id": "2019-2022", "year_start": 2019, "year_end": 2022},
        {"period_id": "2023-2026", "year_start": 2023, "year_end": 2026},
    ],
}


def rubric_document(**overrides) -> dict:
    document = copy.deepcopy(RUBRIC_DOCUMENT)
    document.update(overrides)
    return document


def make_rubric(**overrides):
    return parse_rubric(rubric_document(**overrides))


def evidence_entry(
    identifier,
    party,
    layer,
    indicator,
    stance,
    *,
    years=(2020, 2020),
    source=None,
    proof="documented_primary",
    markers=(),
    reviewed=False,
) -> dict:
    return {
        "evidence_id": identifier,
        "political_party": party,
        "layer": layer,
        "dimension": INDICATOR_DIMENSION[indicator],
        "indicator_id": indicator,
        "stance": stance,
        "source_id": source or f"fictional-source-{identifier}",
        "source_url": f"{FICTIONAL_SOURCE}/{identifier}",
        "source_date": "2021-03-01",
        "year_start": years[0],
        "year_end": years[1],
        "proof_level": proof,
        "attribution_basis": "member_votes_by_affiliation_at_vote_date",
        "extreme_markers": list(markers),
        "human_reviewed": reviewed,
    }


def evidence(rubric, identifier, party, layer, indicator, stance, **options):
    return parse_evidence_item(
        evidence_entry(identifier, party, layer, indicator, stance, **options), rubric
    )


def evidence_document(entries) -> dict:
    return {"schema_version": EVIDENCE_SCHEMA, "evidence": list(entries)}


def balanced_party_evidence(rubric, party, stance, prefix="e"):
    """Four behavior items across two indicators and one discourse item per dimension."""
    layers = ("votes", "implemented_policies", "bills", "supported_policies")
    economic = "economic_privatization"
    social = "sociocultural_traditional_values"
    items = []
    for index, layer in enumerate(layers):
        economic_indicator = economic if index % 2 == 0 else "economic_social_spending"
        economic_stance = stance * rubric.indicators[economic_indicator].direction
        items.append(
            evidence(
                rubric, f"{prefix}-eco-{index}", party, layer, economic_indicator, economic_stance
            )
        )
        social_indicator = social if index % 2 == 0 else "sociocultural_civil_rights"
        social_stance = stance * rubric.indicators[social_indicator].direction
        items.append(
            evidence(rubric, f"{prefix}-soc-{index}", party, layer, social_indicator, social_stance)
        )
    items.append(evidence(rubric, f"{prefix}-eco-d", party, "discourse", economic, stance))
    items.append(evidence(rubric, f"{prefix}-soc-d", party, "discourse", social, stance))
    return tuple(items)
