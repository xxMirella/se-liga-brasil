"""Validate evidence and succession records; sources and dates are mandatory."""

from datetime import date

from service.party_orientation_model.contracts import (
    ALL_LAYERS,
    ATTRIBUTION_BASES,
    DIMENSION_OVERALL,
    EVIDENCE_SCHEMA,
    LAYER_DISCOURSE,
    LAYER_EXPERT,
    PROOF_LEVELS,
    SCORING_DIMENSIONS,
    SUCCESSION_SCHEMA,
    EvidenceItem,
    PartyModelContractError,
    PartySuccession,
    Rubric,
    require_finite,
)

MINIMUM_YEAR = 1800
MAXIMUM_YEAR = 2100


def parse_evidence_document(raw: dict, rubric: Rubric) -> tuple[EvidenceItem, ...]:
    """Accept `{schema_version, evidence: [...]}`; reject duplicates of evidence_id."""
    if raw.get("schema_version") != EVIDENCE_SCHEMA:
        raise PartyModelContractError("EVIDENCE_SCHEMA_NOT_SUPPORTED")
    items = tuple(parse_evidence_item(entry, rubric) for entry in raw.get("evidence") or ())
    identifiers = [item.evidence_id for item in items]
    if len(set(identifiers)) != len(identifiers):
        raise PartyModelContractError("EVIDENCE_ID_DUPLICATED")
    return items


def parse_evidence_item(entry: dict, rubric: Rubric) -> EvidenceItem:
    evidence_id = _text(entry, "evidence_id", "EVIDENCE_ID_REQUIRED", None)
    layer = _choice(entry, "layer", ALL_LAYERS, evidence_id)
    dimension = _parse_dimension(entry, layer, evidence_id)
    indicator_id = _text(entry, "indicator_id", "EVIDENCE_INDICATOR_REQUIRED", evidence_id)
    _check_indicator(rubric, indicator_id, dimension, evidence_id)
    start, end = _parse_years(entry, evidence_id)
    return EvidenceItem(
        evidence_id=evidence_id,
        political_party=_text(entry, "political_party", "EVIDENCE_PARTY_REQUIRED", evidence_id),
        layer=layer,
        dimension=dimension,
        indicator_id=indicator_id,
        stance=require_finite(
            entry.get("stance"), "EVIDENCE_STANCE_OUT_OF_RANGE", evidence_id, -1, 1
        ),
        source_id=_text(entry, "source_id", "EVIDENCE_SOURCE_REQUIRED", evidence_id),
        source_url=_text(entry, "source_url", "EVIDENCE_SOURCE_REQUIRED", evidence_id),
        source_date=parse_iso_date(
            entry.get("source_date"), "EVIDENCE_SOURCE_DATE_REQUIRED", evidence_id
        ),
        year_start=start,
        year_end=end,
        proof_level=_choice(entry, "proof_level", PROOF_LEVELS, evidence_id),
        attribution_basis=_choice(entry, "attribution_basis", ATTRIBUTION_BASES, evidence_id),
        extreme_markers=tuple(sorted(set(entry.get("extreme_markers") or ()))),
        human_reviewed=entry.get("human_reviewed") is True,
        policy_reference_id=entry.get("policy_reference_id"),
        description=str(entry.get("description") or ""),
    )


def parse_successions(raw: dict) -> tuple[PartySuccession, ...]:
    if raw.get("schema_version") != SUCCESSION_SCHEMA:
        raise PartyModelContractError("SUCCESSION_SCHEMA_NOT_SUPPORTED")
    return tuple(_parse_succession(entry) for entry in raw.get("successions") or ())


def _parse_succession(entry: dict) -> PartySuccession:
    label = f"{entry.get('predecessor')}>{entry.get('successor')}"
    succession = PartySuccession(
        predecessor=_text(entry, "predecessor", "SUCCESSION_PARTY_REQUIRED", label),
        successor=_text(entry, "successor", "SUCCESSION_PARTY_REQUIRED", label),
        effective_date=parse_iso_date(
            entry.get("effective_date"), "SUCCESSION_DATE_REQUIRED", label
        ),
        source_url=_text(entry, "source_url", "SUCCESSION_SOURCE_REQUIRED", label),
        source_date=parse_iso_date(
            entry.get("source_date"), "SUCCESSION_SOURCE_DATE_REQUIRED", label
        ),
    )
    if succession.predecessor.casefold() == succession.successor.casefold():
        raise PartyModelContractError("SUCCESSION_SAME_PARTY", label)
    return succession


def parse_iso_date(value, code: str, detail: str) -> date:
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as error:
        raise PartyModelContractError(code, detail) from error


def _text(entry: dict, key: str, code: str, detail: str | None) -> str:
    value = entry.get(key)
    if not isinstance(value, str) or not value.strip():
        raise PartyModelContractError(code, detail or key)
    return value.strip()


def _choice(entry: dict, key: str, allowed: tuple[str, ...], evidence_id: str) -> str:
    value = entry.get(key)
    if value not in allowed:
        raise PartyModelContractError(f"EVIDENCE_{key.upper()}_INVALID", evidence_id)
    return value


def _parse_dimension(entry: dict, layer: str, evidence_id: str) -> str:
    dimension = _choice(entry, "dimension", (*SCORING_DIMENSIONS, DIMENSION_OVERALL), evidence_id)
    reference_only = layer == LAYER_EXPERT
    if reference_only and dimension != DIMENSION_OVERALL:
        raise PartyModelContractError("EVIDENCE_EXPERT_MUST_BE_OVERALL", evidence_id)
    if dimension == DIMENSION_OVERALL and layer not in (LAYER_EXPERT, LAYER_DISCOURSE):
        raise PartyModelContractError("EVIDENCE_OVERALL_ONLY_FOR_REFERENCE", evidence_id)
    return dimension


def _check_indicator(rubric: Rubric, indicator_id: str, dimension: str, evidence_id: str) -> None:
    indicator = rubric.indicators.get(indicator_id)
    if indicator is None or indicator.dimension != dimension:
        raise PartyModelContractError("EVIDENCE_INDICATOR_NOT_IN_RUBRIC", evidence_id)


def _parse_years(entry: dict, evidence_id: str) -> tuple[int, int]:
    start, end = entry.get("year_start"), entry.get("year_end")
    valid = all(
        isinstance(year, int)
        and not isinstance(year, bool)
        and MINIMUM_YEAR <= year <= MAXIMUM_YEAR
        for year in (start, end)
    )
    if not valid or start > end:
        raise PartyModelContractError("EVIDENCE_VALIDITY_YEARS_INVALID", evidence_id)
    return start, end
