"""Real daily Parquets plus authenticated mocked Storage; no production writes."""

import json
from contextlib import nullcontext
from dataclasses import asdict
from datetime import date
from urllib.parse import unquote
from uuid import uuid4

import httpx
import pytest

pytest.importorskip("duckdb")
from service.daily_voting_dataset import DailyVotingPartition, consolidate_daily_votes
from service.dataset_storage.read import DailyDatasetReader
from service.dataset_storage.supabase import StorageConfiguration, SupabaseDatasetStorage
from service.public_profile.contracts import PublicProfileError, VoteQuery
from service.public_profile.storage_votes import get_person_storage_votes


class Metadata:
    def __init__(self, person_id):
        self.person_id, self.exercises = person_id, []

    def read_snapshot(self):
        return nullcontext()

    def fetch_person(self, person_id):
        return {"person_id": person_id, "display_name": "Pessoa demonstrativa"}

    def fetch_exercises(self, query):
        return self.exercises

    def fetch_vote_coverage(self, query):
        return []


def vote(person_id, voting_id):
    return {
        "person_id": person_id,
        "voting_id": voting_id,
        "institution_code": "senado",
        "occurred_on": "2026-10-14",
        "date_precision": "day",
        "vote_choice": "yes",
        "participation_status": "voted",
        "evidence_sha256": "a" * 64,
        "validation_status": "verified",
        "matter_kind": "PEC",
        "matter_number": "1",
        "matter_year": 2026,
        "matter_name": "PEC demonstrativa",
        "description": "Ementa oficial",
        "description_origin": "official_text",
        "official_url": "https://www.senado.leg.br/",
        "voting_subject": "Texto principal",
        "round_number": 1,
        "source_observed_at": "2026-10-15T12:00:00Z",
    }


@pytest.fixture
def environment(tmp_path):
    person_id = str(uuid4())
    partition = DailyVotingPartition("senado", date(2026, 10, 14))
    rows = [vote(person_id, f"senado:plenary:{number}") for number in (7106, 7107)]
    incoming = tmp_path / "input.ndjson"
    incoming.write_text("".join(json.dumps(row) + "\n" for row in rows))
    manifest = consolidate_daily_votes(incoming, tmp_path / "derived", partition, "test-v1")
    directory = tmp_path / "derived" / partition.relative_path
    objects = {
        partition.relative_path + "/manifest.json": json.dumps(asdict(manifest)).encode(),
        partition.relative_path + "/" + manifest.parquet_file: (
            directory / manifest.parquet_file
        ).read_bytes(),
    }
    requests = []

    def respond(request):
        assert request.method == "GET"
        assert request.headers["apikey"] == "server-secret"
        path = unquote(request.url.path.split("/voting-datasets/", 1)[1])
        requests.append(path)
        return (
            httpx.Response(200, content=objects[path]) if path in objects else httpx.Response(404)
        )

    client = httpx.Client(transport=httpx.MockTransport(respond))
    storage = SupabaseDatasetStorage(
        StorageConfiguration("https://example.supabase.co", "server-secret"), client
    )
    reader = DailyDatasetReader(storage, tmp_path / "cache", clock=lambda: 1000)
    query = VoteQuery(person_id, date(2026, 10, 14), date(2026, 10, 14), limit=1)
    return Metadata(person_id), reader, query, objects, requests


def test_storage_pages_cache_and_pinned_snapshot(environment):
    metadata, reader, query, objects, requests = environment
    first = get_person_storage_votes(metadata, reader, query)
    assert first["items"][0]["voting_id"] == "senado:plenary:7107"
    assert first["items"][0]["collective_result"] == "unknown"
    assert first["items"][0]["short_description"] == "Ementa oficial"
    assert first["coverage"]["absence_of_records_is_inactivity"] is False
    assert len(requests) == 3
    objects.clear()
    second = get_person_storage_votes(
        metadata,
        reader,
        VoteQuery(
            query.person_id, query.start_on, query.end_on, cursor=first["next_cursor"], limit=1
        ),
    )
    assert second["items"][0]["voting_id"] == "senado:plenary:7106"
    assert second["next_cursor"] is None
    assert len(requests) == 3
    get_person_storage_votes(metadata, reader, query)
    assert len(requests) == 3
    assert not any("private" in path for path in requests)
    serialized = json.dumps(first)
    assert "server-secret" not in serialized
    assert "evidence_sha256" not in serialized
    assert "parquet_file" not in serialized


def test_storage_integrity_failure_is_explicit(environment):
    metadata, reader, query, objects, _ = environment
    key = next(key for key in objects if key.endswith(".parquet"))
    objects[key] = b"broken parquet"
    with pytest.raises(PublicProfileError, match="DATASET_OBJECT_INTEGRITY_FAILED"):
        get_person_storage_votes(metadata, reader, query)


def test_storage_period_and_cursor_bounds(environment):
    metadata, reader, query, _, requests = environment
    with pytest.raises(PublicProfileError, match="DATASET_PERIOD_TOO_LARGE"):
        get_person_storage_votes(
            metadata, reader, VoteQuery(query.person_id, date(2026, 1, 1), date(2026, 12, 31))
        )
    assert not requests
    first = get_person_storage_votes(metadata, reader, query)
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        get_person_storage_votes(
            metadata,
            reader,
            VoteQuery(str(uuid4()), query.start_on, query.end_on, cursor=first["next_cursor"]),
        )
    reader.clock = lambda: 5000
    with pytest.raises(PublicProfileError, match="DATASET_SNAPSHOT_EXPIRED"):
        get_person_storage_votes(
            metadata,
            reader,
            VoteQuery(query.person_id, query.start_on, query.end_on, cursor=first["next_cursor"]),
        )


def test_unknown_exercise_does_not_fabricate_votes(environment):
    metadata, reader, query, _, _ = environment
    result = get_person_storage_votes(
        metadata,
        reader,
        VoteQuery(query.person_id, query.start_on, query.end_on, office_kind="senator"),
    )
    assert result["items"] == []
    assert result["exercise_link_state"] == "unconfirmed"


def test_missing_partitions_are_unknown_and_negatively_cached(environment):
    metadata, reader, query, objects, requests = environment
    objects.clear()
    result = get_person_storage_votes(metadata, reader, query)
    assert result["items"] == []
    assert result["coverage"]["datasets"]["state"] == "not_published"
    assert len(requests) == 2
    get_person_storage_votes(metadata, reader, query)
    assert len(requests) == 2


def test_office_interval_end_is_exclusive(environment):
    metadata, reader, query, _, _ = environment
    metadata.exercises = [
        {
            "exercise_id": 1,
            "term_id": 1,
            "office_kind": "senator",
            "institution_code": "senado",
            "institution_name": "Senado Federal",
            "starts_on": date(2026, 10, 1),
            "ends_before": date(2026, 10, 14),
            "capacity": "holder",
        }
    ]
    filtered = VoteQuery(query.person_id, query.start_on, query.end_on, office_kind="senator")
    result = get_person_storage_votes(metadata, reader, filtered)
    assert result["items"] == []
    metadata.exercises[0]["ends_before"] = date(2026, 10, 15)
    assert len(get_person_storage_votes(metadata, reader, filtered)["items"]) == 2


def test_office_context_is_pinned_between_pages(environment):
    metadata, reader, query, _, _ = environment
    metadata.exercises = [
        {
            "exercise_id": 1,
            "term_id": 1,
            "office_kind": "senator",
            "institution_code": "senado",
            "institution_name": "Senado Federal",
            "starts_on": date(2026, 10, 1),
            "ends_before": None,
            "capacity": "holder",
        }
    ]
    filtered = VoteQuery(
        query.person_id, query.start_on, query.end_on, office_kind="senator", limit=1
    )
    first = get_person_storage_votes(metadata, reader, filtered)
    metadata.exercises[0]["ends_before"] = date(2026, 10, 14)
    second = get_person_storage_votes(
        metadata,
        reader,
        VoteQuery(
            query.person_id,
            query.start_on,
            query.end_on,
            office_kind="senator",
            limit=1,
            cursor=first["next_cursor"],
        ),
    )
    assert second["items"][0]["voting_id"] == "senado:plenary:7106"


def test_manifest_wrong_partition_rejected(environment):
    metadata, reader, query, objects, _ = environment
    key = next(key for key in objects if key.endswith("manifest.json"))
    manifest = json.loads(objects[key])
    manifest["occurred_on"] = "2026-10-15"
    objects[key] = json.dumps(manifest).encode()
    with pytest.raises(PublicProfileError, match="DATASET_MANIFEST_INVALID"):
        get_person_storage_votes(metadata, reader, query)


def test_cache_budget_never_returns_unverified_page(environment):
    metadata, reader, query, _, _ = environment
    reader.max_cache_bytes = 100
    with pytest.raises(PublicProfileError, match="DATASET_CACHE_BUDGET_EXCEEDED"):
        get_person_storage_votes(metadata, reader, query)
    assert not list(reader.directory.glob("*.snapshot.json"))


def test_changed_remote_manifest_does_not_change_second_page(environment):
    metadata, reader, query, objects, requests = environment
    first = get_person_storage_votes(metadata, reader, query)
    reader.clock = lambda: 1400
    objects.clear()
    second = get_person_storage_votes(
        metadata,
        reader,
        VoteQuery(
            query.person_id, query.start_on, query.end_on, cursor=first["next_cursor"], limit=1
        ),
    )
    assert second["items"][0]["voting_id"] == "senado:plenary:7106"
    assert len(requests) == 3
    fresh = get_person_storage_votes(metadata, reader, query)
    assert fresh["items"] == []
    assert len(requests) == 5
    # A new first-page does not evict generations needed by a still-valid old cursor.
    assert get_person_storage_votes(
        metadata,
        reader,
        VoteQuery(
            query.person_id, query.start_on, query.end_on, cursor=first["next_cursor"], limit=1
        ),
    )["items"]


def test_private_projection_rejected_even_with_valid_hash(environment, tmp_path):
    import hashlib

    import duckdb

    metadata, reader, query, objects, _ = environment
    key = next(key for key in objects if key.endswith(".parquet"))
    original = tmp_path / "original.parquet"
    original.write_bytes(objects[key])
    malicious = tmp_path / "private.parquet"
    with duckdb.connect() as engine:
        engine.from_parquet(str(original)).create_view("original")
        engine.execute(
            "COPY (SELECT *, 'private' AS evidence_sha256 FROM original) TO ? (FORMAT PARQUET)",
            [str(malicious)],
        )
    content = malicious.read_bytes()
    digest = hashlib.sha256(content).hexdigest()
    manifest_key = next(key for key in objects if key.endswith("manifest.json"))
    manifest = json.loads(objects[manifest_key])
    manifest.update(parquet_sha256=digest, parquet_file=digest + ".parquet")
    objects[manifest_key] = json.dumps(manifest).encode()
    objects[key.rsplit("/", 1)[0] + "/" + digest + ".parquet"] = content
    with pytest.raises(PublicProfileError, match="DATASET_PUBLIC_SCHEMA_INVALID"):
        get_person_storage_votes(metadata, reader, query)
