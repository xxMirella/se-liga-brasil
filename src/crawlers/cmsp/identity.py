"""Explicit reviewed evidence contracts for a source without civil identifiers."""

from dataclasses import dataclass
from uuid import UUID

from normalization.identity import normalize_person_name
from service.ingestion.contracts import IngestionError


@dataclass(frozen=True)
class ReviewedAuthorBinding:
    person_id: UUID
    official_author_name: str
    artifact_sha256: str
    evidence_reference: str
    method: str = "reviewed_personal_identity_evidence"


def index_reviewed_bindings(bindings):
    indexed = {}
    for binding in bindings:
        valid = (
            isinstance(binding.person_id, UUID)
            and binding.method == "reviewed_personal_identity_evidence"
            and bool(binding.evidence_reference.strip())
            and len(binding.artifact_sha256) == 64
        )
        if not valid:
            raise IngestionError("CMSP_UNVERIFIED_AUTHOR_BINDING")
        name = normalize_person_name(binding.official_author_name)
        if not name or name in indexed:
            raise IngestionError("CMSP_AMBIGUOUS_REVIEWED_AUTHOR")
        indexed[name] = binding
    return indexed
