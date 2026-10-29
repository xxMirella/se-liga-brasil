"""Validate the rubric document (rubric.json contract) into an immutable Rubric."""

from service.party_orientation_model.contracts import (
    ALL_LAYERS,
    BEHAVIOR_LAYERS,
    CATEGORY_EXTREME_LEFT,
    CATEGORY_EXTREME_RIGHT,
    DIMENSION_OVERALL,
    LAYER_DISCOURSE,
    LAYER_EXPERT,
    PROOF_LEVELS,
    RUBRIC_SCHEMA,
    SCORING_DIMENSIONS,
    SCORING_LAYERS,
    ExtremeCriterion,
    Indicator,
    PartyModelContractError,
    Period,
    Rubric,
    Sufficiency,
    require_finite,
)

BAND_LIMIT_COUNT = 6
CONFIDENCE_TERMS = ("count", "layers", "agreement", "precision")


def parse_rubric(raw: dict) -> Rubric:
    if raw.get("schema_version") != RUBRIC_SCHEMA:
        raise PartyModelContractError("RUBRIC_SCHEMA_NOT_SUPPORTED")
    layer_weights = _parse_layer_weights(raw.get("layer_weights"))
    cap_ratio = require_finite(
        raw.get("discourse_cap_ratio"), "RUBRIC_DISCOURSE_CAP", "ratio", 0, 0.99
    )
    divergence = raw.get("divergence") or {}
    confidence = raw.get("confidence") or {}
    return Rubric(
        rubric_version=_require_text(raw, "rubric_version"),
        layer_weights=layer_weights,
        discourse_cap_ratio=cap_ratio,
        proof_multipliers=_parse_proof_multipliers(raw.get("proof_multipliers")),
        succession_multiplier=require_finite(
            raw.get("succession_multiplier"), "RUBRIC_SUCCESSION_MULTIPLIER", "range", 0, 1
        ),
        dimension_weights=_parse_dimension_weights(raw.get("dimension_weights")),
        indicators=_parse_indicators(raw.get("indicators")),
        band_limits=_parse_band_limits(raw.get("band_limits")),
        extreme_criteria=_parse_extreme_criteria(raw.get("extreme_criteria")),
        sufficiency=_parse_sufficiency(raw.get("sufficiency") or {}),
        divergence_dimension_threshold=_unit(divergence, "dimension_threshold"),
        divergence_indicator_threshold=_unit(divergence, "indicator_threshold"),
        calibration_gap_threshold=_unit(divergence, "calibration_gap_threshold"),
        prior_standard_deviation=_unit(raw, "prior_standard_deviation"),
        confidence_weights=_parse_confidence_weights(confidence.get("weights")),
        confidence_target_items=_positive_int(confidence, "target_items"),
        confidence_precision_scale=require_finite(
            confidence.get("precision_scale"), "RUBRIC_CONFIDENCE", "precision_scale", 0.1, 2
        ),
        confidence_labels=_parse_confidence_labels(confidence.get("label_limits")),
        controversy_span_steps=_positive_int(raw, "controversy_span_steps"),
        periods=_parse_periods(raw.get("periods")),
    )


def _require_text(raw: dict, key: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PartyModelContractError("RUBRIC_FIELD_REQUIRED", key)
    return value.strip()


def _unit(raw: dict, key: str) -> float:
    return require_finite(raw.get(key), "RUBRIC_UNIT_VALUE", key, 0, 2)


def _positive_int(raw: dict, key: str) -> int:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise PartyModelContractError("RUBRIC_POSITIVE_INTEGER", key)
    return value


def _parse_layer_weights(raw) -> dict[str, float]:
    if not isinstance(raw, dict) or set(raw) - set(ALL_LAYERS) or LAYER_DISCOURSE not in raw:
        raise PartyModelContractError("RUBRIC_LAYER_WEIGHTS_INVALID")
    weights = {
        key: require_finite(value, "RUBRIC_LAYER_WEIGHT", key, 0, 1) for key, value in raw.items()
    }
    if weights.get(LAYER_EXPERT, 0) != 0:
        raise PartyModelContractError("RUBRIC_EXPERT_LAYER_MUST_NOT_SCORE")
    behavior = sum(weights.get(layer, 0) for layer in BEHAVIOR_LAYERS)
    if behavior <= 0 or behavior <= weights[LAYER_DISCOURSE]:
        raise PartyModelContractError("RUBRIC_BEHAVIOR_MUST_OUTWEIGH_DISCOURSE")
    return {layer: weights.get(layer, 0.0) for layer in SCORING_LAYERS}


def _parse_proof_multipliers(raw) -> dict[str, float]:
    if not isinstance(raw, dict) or set(raw) != set(PROOF_LEVELS):
        raise PartyModelContractError("RUBRIC_PROOF_MULTIPLIERS_INVALID")
    values = {key: require_finite(raw[key], "RUBRIC_PROOF_MULTIPLIER", key, 0.01, 1) for key in raw}
    ordered = [values[level] for level in PROOF_LEVELS]
    if ordered != sorted(ordered):
        raise PartyModelContractError("RUBRIC_PROOF_MULTIPLIERS_NOT_MONOTONIC")
    return values


def _parse_dimension_weights(raw) -> dict[str, float]:
    if not isinstance(raw, dict) or set(raw) != set(SCORING_DIMENSIONS):
        raise PartyModelContractError("RUBRIC_DIMENSION_WEIGHTS_INVALID")
    weights = {
        key: require_finite(value, "RUBRIC_DIMENSION_WEIGHT", key, 0, 1)
        for key, value in raw.items()
    }
    if abs(sum(weights.values()) - 1) > 1e-9:
        raise PartyModelContractError("RUBRIC_DIMENSION_WEIGHTS_MUST_SUM_TO_ONE")
    return weights


def _parse_indicators(raw) -> dict[str, Indicator]:
    if not isinstance(raw, list) or not raw:
        raise PartyModelContractError("RUBRIC_INDICATORS_REQUIRED")
    indicators = {}
    for entry in raw:
        indicator = _parse_indicator(entry)
        if indicator.indicator_id in indicators:
            raise PartyModelContractError("RUBRIC_INDICATOR_DUPLICATED", indicator.indicator_id)
        indicators[indicator.indicator_id] = indicator
    return indicators


def _parse_indicator(entry: dict) -> Indicator:
    dimension = entry.get("dimension")
    if dimension not in (*SCORING_DIMENSIONS, DIMENSION_OVERALL):
        raise PartyModelContractError("RUBRIC_INDICATOR_DIMENSION", str(entry.get("indicator_id")))
    if isinstance(entry.get("direction"), bool) or entry.get("direction") not in (-1, 1):
        raise PartyModelContractError("RUBRIC_INDICATOR_DIRECTION", str(entry.get("indicator_id")))
    return Indicator(
        indicator_id=_require_text(entry, "indicator_id"),
        dimension=dimension,
        direction=entry["direction"],
        weight=require_finite(entry.get("weight"), "RUBRIC_INDICATOR_WEIGHT", "weight", 0, 10),
        label=_require_text(entry, "label"),
    )


def _parse_band_limits(raw) -> tuple[float, ...]:
    if not isinstance(raw, list) or len(raw) != BAND_LIMIT_COUNT:
        raise PartyModelContractError("RUBRIC_BAND_LIMITS_INVALID")
    limits = tuple(require_finite(value, "RUBRIC_BAND_LIMIT", "limit", -1, 1) for value in raw)
    if list(limits) != sorted(set(limits)):
        raise PartyModelContractError("RUBRIC_BAND_LIMITS_NOT_INCREASING")
    return limits


def _parse_extreme_criteria(raw) -> dict[str, ExtremeCriterion]:
    if not isinstance(raw, dict) or set(raw) != {CATEGORY_EXTREME_LEFT, CATEGORY_EXTREME_RIGHT}:
        raise PartyModelContractError("RUBRIC_EXTREME_CRITERIA_INVALID")
    criteria = {}
    for category, entry in raw.items():
        proof = entry.get("minimum_proof_level")
        markers = entry.get("marker_ids")
        if (
            proof not in PROOF_LEVELS
            or not markers
            or not isinstance(entry.get("minimum_markers"), int)
        ):
            raise PartyModelContractError("RUBRIC_EXTREME_CRITERION_INVALID", category)
        criteria[category] = ExtremeCriterion(
            category=category,
            minimum_abs_score=require_finite(
                entry.get("minimum_abs_score"), "RUBRIC_EXTREME_SCORE", category, 0.3, 1
            ),
            minimum_markers=max(1, entry["minimum_markers"]),
            minimum_sources=max(1, int(entry.get("minimum_sources", 1))),
            require_human_review=bool(entry.get("require_human_review", False)),
            minimum_proof_level=proof,
            marker_ids=tuple(sorted(set(markers))),
            require_behavior_marker=bool(entry.get("require_behavior_marker", True)),
        )
    return criteria


def _parse_sufficiency(raw: dict) -> Sufficiency:
    required = tuple(raw.get("required_dimensions") or ())
    if not required or set(required) - set(SCORING_DIMENSIONS):
        raise PartyModelContractError("RUBRIC_REQUIRED_DIMENSIONS_INVALID")
    return Sufficiency(
        minimum_items=_positive_int(raw, "minimum_items"),
        minimum_behavior_items=_positive_int(raw, "minimum_behavior_items"),
        minimum_indicators=_indicators_by_dimension(raw.get("minimum_indicators")),
        minimum_sources=_positive_int(raw, "minimum_sources"),
        minimum_confidence=require_finite(
            raw.get("minimum_confidence"), "RUBRIC_CONFIDENCE_RANGE", "minimum_confidence", 0, 1
        ),
        required_dimensions=required,
    )


def _indicators_by_dimension(raw) -> dict[str, int]:
    valid = isinstance(raw, dict) and set(raw) == set(SCORING_DIMENSIONS)
    if not valid or any(
        isinstance(v, bool) or not isinstance(v, int) or v < 1 for v in raw.values()
    ):
        raise PartyModelContractError("RUBRIC_MINIMUM_INDICATORS_INVALID")
    return dict(raw)


def _parse_confidence_weights(raw) -> dict[str, float]:
    if not isinstance(raw, dict) or set(raw) != set(CONFIDENCE_TERMS):
        raise PartyModelContractError("RUBRIC_CONFIDENCE_WEIGHTS_INVALID")
    weights = {key: require_finite(raw[key], "RUBRIC_CONFIDENCE_WEIGHT", key, 0, 1) for key in raw}
    if abs(sum(weights.values()) - 1) > 1e-9:
        raise PartyModelContractError("RUBRIC_CONFIDENCE_WEIGHTS_MUST_SUM_TO_ONE")
    return weights


def _parse_confidence_labels(raw) -> tuple[float, float]:
    if not isinstance(raw, list) or len(raw) != 2 or not 0 < raw[0] < raw[1] < 1:
        raise PartyModelContractError("RUBRIC_CONFIDENCE_LABELS_INVALID")
    return float(raw[0]), float(raw[1])


def _parse_periods(raw) -> tuple[Period, ...]:
    periods = []
    for entry in raw or ():
        start, end = entry.get("year_start"), entry.get("year_end")
        if not isinstance(start, int) or not isinstance(end, int) or start > end:
            raise PartyModelContractError("RUBRIC_PERIOD_INVALID", str(entry.get("period_id")))
        periods.append(Period(_require_text(entry, "period_id"), start, end))
    if len({period.period_id for period in periods}) != len(periods):
        raise PartyModelContractError("RUBRIC_PERIOD_DUPLICATED")
    return tuple(periods)
