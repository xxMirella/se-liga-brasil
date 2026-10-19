"""Reusable existence and change detection, independent of TSE or electoral data."""

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from itertools import batched
from typing import Protocol

from service.ingestion.contracts import IngestionError
from storage.files import hash_content


class RecordState(StrEnum):
    NEW = "new"
    UNCHANGED = "unchanged"
    CHANGED = "changed"
    STALE = "stale"
    CONFLICTING = "conflicting"


@dataclass(frozen=True)
class RecordIdentity:
    source_code: str
    data_type: str
    external_key: str

    def __post_init__(self):
        if not all(
            value.strip() for value in (self.source_code, self.data_type, self.external_key)
        ):
            raise IngestionError("INVALID_RECORD_IDENTITY")


@dataclass(frozen=True)
class RecordSnapshot:
    identity: RecordIdentity
    normalized_data: dict
    source_generated_at: datetime

    def __post_init__(self):
        if self.source_generated_at.tzinfo is None:
            raise IngestionError("TIMEZONE_REQUIRED")

    @property
    def content_sha256(self) -> str:
        return hash_content(self.normalized_data)


@dataclass(frozen=True)
class StoredRecord:
    content_sha256: str
    source_generated_at: datetime


class RecordLookup(Protocol):
    def fetch_existing_records(
        self, identities: list[RecordIdentity]
    ) -> dict[RecordIdentity, StoredRecord]:
        """Fetch a batch of identities using the source namespace and its unique key."""


def classify_snapshot(incoming: RecordSnapshot, existing: StoredRecord | None) -> RecordState:
    if existing is None:
        return RecordState.NEW
    if incoming.source_generated_at < existing.source_generated_at:
        return RecordState.STALE
    if incoming.content_sha256 == existing.content_sha256:
        return RecordState.UNCHANGED
    if incoming.source_generated_at == existing.source_generated_at:
        return RecordState.CONFLICTING
    return RecordState.CHANGED


class DataExistenceService:
    """One-record convenience and batch APIs share the same comparison policy."""

    def __init__(self, lookup: RecordLookup) -> None:
        self.lookup = lookup

    def exists(self, identity: RecordIdentity) -> bool:
        return identity in self.lookup.fetch_existing_records([identity])

    def inspect_record(self, record: RecordSnapshot) -> RecordState:
        return self.inspect_records([record])[record.identity]

    def inspect_records(self, records: list[RecordSnapshot]) -> dict[RecordIdentity, RecordState]:
        identities = [record.identity for record in records]
        existing = self.lookup.fetch_existing_records(identities)
        return {
            record.identity: classify_snapshot(record, existing.get(record.identity))
            for record in records
        }

    def iter_record_states(
        self, records: Iterable[RecordSnapshot], *, batch_size: int = 500
    ) -> Iterator[tuple[RecordIdentity, RecordState]]:
        if not 1 <= batch_size <= 5000:
            raise IngestionError("INVALID_BATCH_SIZE")
        for batch in batched(records, batch_size):
            yield from self.inspect_records(list(batch)).items()
