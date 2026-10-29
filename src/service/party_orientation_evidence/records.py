"""Builders for `party_orientation_evidence.v1` records; pure: no files, network or database."""

from datetime import date

from service.party_orientation_model.contracts import EVIDENCE_SCHEMA, Rubric

PROOF_PRIMARY = "documented_primary"
PROOF_SECONDARY = "documented_secondary"
PROOF_REPORTED = "reported"


def dimension_of(rubric: Rubric, indicator_id: str) -> str:
    return rubric.indicators[indicator_id].dimension


def evidence_record(
    *,
    evidence_id: str,
    political_party: str,
    layer: str,
    dimension: str,
    indicator_id: str,
    stance: float,
    source_id: str,
    source_url: str,
    source_date: date,
    year_start: int,
    year_end: int,
    proof_level: str,
    attribution_basis: str,
    description: str,
    policy_reference_id: str | None = None,
) -> dict:
    """One evidence entry. Never human reviewed here: reviews are recorded by people, not code."""
    record = {
        "evidence_id": evidence_id,
        "political_party": political_party,
        "layer": layer,
        "dimension": dimension,
        "indicator_id": indicator_id,
        "stance": round(stance, 6),
        "source_id": source_id,
        "source_url": source_url,
        "source_date": source_date.isoformat(),
        "year_start": year_start,
        "year_end": year_end,
        "proof_level": proof_level,
        "attribution_basis": attribution_basis,
        "human_reviewed": False,
        "description": description,
    }
    if policy_reference_id:
        record["policy_reference_id"] = policy_reference_id
    return record


def evidence_document(layer_name: str, records: list[dict], notes: list[str], generated_on: date):
    """Stable order, so identical inputs give identical bytes."""
    return {
        "schema_version": EVIDENCE_SCHEMA,
        "layer_name": layer_name,
        "generated_on": generated_on.isoformat(),
        "conversion_notes": notes,
        "evidence": sorted(records, key=lambda record: record["evidence_id"]),
    }
