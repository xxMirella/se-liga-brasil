"""Reviewed record-to-person evidence; source personal identifiers are not retained."""

from dataclasses import dataclass
from uuid import UUID

from service.ingestion.contracts import IngestionError


@dataclass(frozen=True)
class ReviewedParticipation:
    person_id: UUID
    record_key: str
    artifact_sha256: str
    role: str
    review_reference: str


def index_reviewed_participations(participations):
    indexed = {}
    for participation in participations:
        if participation.role not in {"amendment_author", "formal_signatory"}:
            raise IngestionError("TRANSFEREGOV_UNPROVEN_PERSONAL_ROLE")
        if not isinstance(participation.person_id, UUID) or not participation.review_reference:
            raise IngestionError("TRANSFEREGOV_INVALID_REVIEW")
        key = (participation.artifact_sha256, participation.record_key)
        if key in indexed:
            raise IngestionError("TRANSFEREGOV_AMBIGUOUS_PERSONAL_LINK")
        indexed[key] = participation
    return indexed


def attach_reviewed_participation(record, participations):
    participation = participations.get((record["source_sha256"], record["record_key"]))
    if participation is None:
        return record | {"person_id": None, "person_link_status": "requires_reviewed_identity"}
    return record | {
        "person_id": str(participation.person_id),
        "personal_role": participation.role,
        "person_link_status": "reviewed",
        "review_reference": participation.review_reference,
    }
