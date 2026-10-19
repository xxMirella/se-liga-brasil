"""Attach activities to evidenced affiliations without guessing historical membership."""

from dataclasses import dataclass
from datetime import datetime

from service.ingestion.contracts import IngestionError


@dataclass(frozen=True)
class ActivityContext:
    source_id: int
    activity_kind: str
    external_key: str
    person_id: str
    source_record_id: int
    observed_at: datetime
    political_party_affiliation_id: int | None = None
    office_term_id: int | None = None
    occurred_at: datetime | None = None
    role: str = "subject"


class ActivityContextService:
    def __init__(self, repository) -> None:
        self.repository = repository

    def link_activity(self, context: ActivityContext) -> int:
        if not context.activity_kind.strip() or not context.external_key.strip():
            raise IngestionError("INVALID_ACTIVITY_CONTEXT")
        if context.observed_at.tzinfo is None:
            raise IngestionError("INVALID_ACTIVITY_TIMESTAMP")
        if context.occurred_at and context.occurred_at.tzinfo is None:
            raise IngestionError("INVALID_ACTIVITY_TIMESTAMP")
        return self.repository.link_context(context)
