"""Nominal matches are review candidates, never proof of business ownership."""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from normalization.identity import normalize_person_name
from service.ingestion.contracts import IngestionError
from storage.files import hash_content


@dataclass(frozen=True)
class ReviewedRelationship:
    person_id: str
    evidence_url: str
    reviewed_by: str
    reviewed_at: str


def index_people(people):
    index = defaultdict(set)
    for person in people:
        person_id = str(UUID(str(person["person_id"])))
        index[normalize_person_name(person["full_name"])].add(person_id)
    return dict(index)


def partner_evidence_key(row):
    # Full row plus source partition hash in the caller identifies a source observation.
    return hash_content("\x1f".join(row))


def validate_review(reviewed, candidates):
    if reviewed.person_id not in candidates or not reviewed.reviewed_by.strip():
        raise IngestionError("CNPJ_INVALID_REVIEWED_RELATIONSHIP")
    parsed = urlsplit(reviewed.evidence_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise IngestionError("CNPJ_INVALID_REVIEW_EVIDENCE")
    try:
        reviewed_at = datetime.fromisoformat(reviewed.reviewed_at)
    except ValueError as error:
        raise IngestionError("CNPJ_INVALID_REVIEW_TIMESTAMP") from error
    if reviewed_at.tzinfo is None:
        raise IngestionError("CNPJ_INVALID_REVIEW_TIMESTAMP")


def identify_partner(partner, row, people_index, reviewed_relationships, artifact_hash):
    if partner["partner_kind"] != "2":
        return None
    candidates = people_index.get(normalize_person_name(partner["partner_name"]), set())
    if not candidates:
        return None
    observation_key = artifact_hash + ":" + partner_evidence_key(row)
    reviewed = reviewed_relationships.get(observation_key)
    if reviewed:
        validate_review(reviewed, candidates)
    return {
        "observation_key": observation_key,
        "candidate_person_ids": tuple(sorted(candidates)),
        "person_id": reviewed.person_id if reviewed else None,
        "identity_status": "reviewed" if reviewed else "unverified",
        "identity_evidence": reviewed.evidence_url if reviewed else None,
        "reviewed_by": reviewed.reviewed_by if reviewed else None,
        "reviewed_at": reviewed.reviewed_at if reviewed else None,
    }
