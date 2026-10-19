from datetime import UTC, datetime, timedelta

import pytest

from service.data_validation.existence import (
    DataExistenceService,
    RecordIdentity,
    RecordSnapshot,
    RecordState,
    StoredRecord,
)
from storage.files import hash_content


class InMemoryRecordLookup:
    def __init__(self, records):
        self.records = records
        self.calls = 0

    def fetch_existing_records(self, identities):
        self.calls += 1
        return {
            identity: self.records[identity] for identity in identities if identity in self.records
        }


@pytest.mark.parametrize(
    ("data_type", "data"),
    [
        ("salary", {"gross": "1000.00"}),
        ("law", {"number": "1"}),
        ("candidate", {"name": "Fictício"}),
        ("budget_amendment", {"paid": "12.00"}),
    ],
)
def test_existence_is_independent_of_domain_data(data_type, data):
    identity = RecordIdentity("official-source", data_type, "key")
    timestamp = datetime.now(UTC)
    lookup = InMemoryRecordLookup({identity: StoredRecord(hash_content(data), timestamp)})
    service = DataExistenceService(lookup)
    assert service.exists(identity)
    assert (
        service.inspect_record(RecordSnapshot(identity, data, timestamp)) == RecordState.UNCHANGED
    )


def test_batch_lookup_happens_once_for_multiple_records():
    timestamp = datetime.now(UTC)
    records = [
        RecordSnapshot(RecordIdentity("source", "law", str(number)), {"number": number}, timestamp)
        for number in range(100)
    ]
    lookup = InMemoryRecordLookup({})
    assert set(DataExistenceService(lookup).inspect_records(records).values()) == {RecordState.NEW}
    assert lookup.calls == 1


def test_changed_stale_and_conflicting_are_distinct():
    identity = RecordIdentity("source", "salary", "person:month")
    timestamp = datetime.now(UTC)
    existing = StoredRecord(hash_content({"gross": "100.00"}), timestamp)
    service = DataExistenceService(InMemoryRecordLookup({identity: existing}))
    assert (
        service.inspect_record(RecordSnapshot(identity, {"gross": "200.00"}, timestamp))
        == RecordState.CONFLICTING
    )
    assert (
        service.inspect_record(
            RecordSnapshot(identity, {"gross": "200.00"}, timestamp + timedelta(days=1))
        )
        == RecordState.CHANGED
    )
    assert (
        service.inspect_record(
            RecordSnapshot(identity, {"gross": "200.00"}, timestamp - timedelta(days=1))
        )
        == RecordState.STALE
    )
