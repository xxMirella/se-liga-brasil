"""Translate the conceptual proposal in rubric.json into the rubric contract of this model.

Everything the proposal states (indicators, layer classes and weights, band limits, gate
identifiers, minimum indicators) is read from it. Choices the proposal does not make are named in
MODEL_PARAMETERS so they are visible, auditable and pending approval together with the proposal.
"""

import re

from service.party_orientation_model.contracts import RUBRIC_SCHEMA, PartyModelContractError

PROPOSAL_SCHEMA = "1.0"
BAND_CATEGORIES_IN_PROPOSAL = (
    "esquerda_radical",
    "esquerda",
    "centro_esquerda",
    "centro",
    "centro_direita",
    "direita",
)
MODEL_PARAMETERS = {
    "discourse_cap_ratio": 0.5,
    "proof_multipliers": {"reported": 0.4, "documented_secondary": 0.7, "documented_primary": 1.0},
    "succession_multiplier": 0.7,
    "dimension_weights": {"economic": 0.5, "sociocultural": 0.5},
    "minimum_items": 6,
    "minimum_behavior_items": 1,
    "minimum_sources": 2,
    "minimum_confidence": 0.3,
    "divergence": {
        "dimension_threshold": 0.35,
        "indicator_threshold": 0.5,
        "calibration_gap_threshold": 0.3,
    },
    "prior_standard_deviation": 0.5,
    "confidence": {
        "weights": {"count": 0.25, "layers": 0.25, "agreement": 0.25, "precision": 0.25},
        "target_items": 10,
        "precision_scale": 1.0,
        "label_limits": [0.4, 0.7],
    },
    "controversy_span_steps": 3,
    "extreme_minimum_sources": 2,
}
REFERENCE_INDICATORS = (
    ("self_declared_position", "Autodeclaração do partido"),
    ("expert_position", "Pesquisa de especialistas"),
)


def is_proposal_document(raw: dict) -> bool:
    return raw.get("schema_version") == PROPOSAL_SCHEMA and "evidence_classes_and_weights" in raw


def adapt_proposal_to_rubric_document(raw: dict, periods: list[dict] | None = None) -> dict:
    classes = raw["evidence_classes_and_weights"]["weights_within_each_dimension"]
    limits = _band_limits(raw["category_thresholds"]["bands"])
    parameters = MODEL_PARAMETERS
    return {
        "schema_version": RUBRIC_SCHEMA,
        "rubric_version": f"rubric.json@{raw.get('generated_on')}:{raw.get('status')}",
        "layer_weights": _layer_weights(classes),
        "discourse_cap_ratio": parameters["discourse_cap_ratio"],
        "proof_multipliers": parameters["proof_multipliers"],
        "succession_multiplier": parameters["succession_multiplier"],
        "dimension_weights": parameters["dimension_weights"],
        "indicators": _indicators(raw["indicators"], _contested_weight(raw)),
        "band_limits": limits,
        "extreme_criteria": _extreme_criteria(raw["indicators"]["democratic_gate"], limits),
        "sufficiency": _sufficiency(raw["aggregation"]["dimension_score"]),
        "divergence": parameters["divergence"],
        "prior_standard_deviation": parameters["prior_standard_deviation"],
        "confidence": parameters["confidence"],
        "controversy_span_steps": parameters["controversy_span_steps"],
        "periods": periods or default_periods(),
    }


def default_periods() -> list[dict]:
    """Federal legislatures since the 1987 Constituent Assembly (calendar, not an opinion)."""
    starts = range(1987, 2027, 4)
    return [
        {"period_id": f"{start}-{start + 3}", "year_start": start, "year_end": start + 3}
        for start in starts
    ]


def _layer_weights(classes: dict) -> dict[str, float]:
    behavior = classes["behavior"]
    agenda_share = round(behavior["legislative_initiative_and_agenda"]["weight"] / 3, 6)
    return {
        "votes": behavior["roll_call_votes"]["weight"],
        "implemented_policies": behavior["implemented_policy_governing"]["weight"],
        # proposal groups bills, supported policies and focus in one class: split evenly
        "bills": agenda_share,
        "supported_policies": agenda_share,
        "thematic_focus": agenda_share,
        "discourse": classes["statements_total"],
        "expert_survey": 0.0,
    }


def _contested_weight(raw: dict) -> float | None:
    """Approved weight of indicators whose direction is contested; None keeps the proposal's."""
    return (
        (raw.get("approval") or {})
        .get("parameters", {})
        .get("contested_direction_indicator_weight")
    )


def _indicator_weight(entry: dict, contested_weight: float | None) -> float:
    if contested_weight is not None and entry.get("contested_direction"):
        return contested_weight
    return entry["weight_modifier"]


def _indicators(groups: dict, contested_weight: float | None = None) -> list[dict]:
    rows = [
        {
            "indicator_id": entry["id"],
            "dimension": dimension,
            "direction": 1,  # proposal poles are already on the axis: +1 is the positive pole
            "weight": _indicator_weight(entry, contested_weight),
            "label": entry["label"],
        }
        for dimension in ("economic", "sociocultural")
        for entry in groups[dimension]
    ]
    rows.extend(
        {
            "indicator_id": name,
            "dimension": "overall",
            "direction": 1,
            "weight": 1.0,
            "label": label,
        }
        for name, label in REFERENCE_INDICATORS
    )
    return rows


def _band_limits(bands: list[dict]) -> list[float]:
    by_category = {band["category"]: band["range"] for band in bands}
    limits = []
    for category in BAND_CATEGORIES_IN_PROPOSAL:
        numbers = re.findall(r"[+-]?\d+(?:\.\d+)?", by_category.get(category, ""))
        if not numbers:
            raise PartyModelContractError("RUBRIC_PROPOSAL_BAND_MISSING", category)
        limits.append(float(numbers[-1]))
    return limits


def _extreme_criteria(gate: list[dict], limits: list[float]) -> dict:
    markers = sorted(entry["id"] for entry in gate)
    criterion = {
        "minimum_abs_score": abs(limits[0]),
        "minimum_markers": 1,
        "minimum_proof_level": "documented_secondary",
        "minimum_sources": MODEL_PARAMETERS["extreme_minimum_sources"],
        "require_human_review": True,
        "require_behavior_marker": False,
        "marker_ids": markers,
    }
    return {"extreme_left": dict(criterion), "extreme_right": dict(criterion)}


def _sufficiency(aggregation_rule: str) -> dict:
    """The proposal requires '4 indicadores economicos e 3 culturais' in prose; read the numbers."""
    match = re.search(r"ao menos (\d+) indicadores economicos e (\d+) culturais", aggregation_rule)
    if match is None:
        raise PartyModelContractError("RUBRIC_PROPOSAL_MINIMUM_INDICATORS_MISSING")
    parameters = MODEL_PARAMETERS
    return {
        "minimum_items": parameters["minimum_items"],
        "minimum_behavior_items": parameters["minimum_behavior_items"],
        "minimum_indicators": {
            "economic": int(match.group(1)),
            "sociocultural": int(match.group(2)),
        },
        "minimum_sources": parameters["minimum_sources"],
        "minimum_confidence": parameters["minimum_confidence"],
        "required_dimensions": ["economic", "sociocultural"],
    }
