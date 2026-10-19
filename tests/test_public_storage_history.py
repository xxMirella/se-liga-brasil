"""History includes old published dates without probing empty calendar days."""

import json
from dataclasses import asdict
from datetime import date, timedelta
from urllib.parse import unquote
from uuid import uuid4

import httpx
import pytest
from test_public_storage_votes import Metadata, vote

from service.daily_voting_dataset import DailyVotingPartition, consolidate_daily_votes
from service.dataset_storage.catalog import published_partitions
from service.dataset_storage.read import DailyDatasetReader, DatasetReadError
from service.dataset_storage.supabase import StorageConfiguration, SupabaseDatasetStorage
from service.public_profile.contracts import PublicProfileError
from service.public_profile.storage_history import get_person_storage_history


@pytest.fixture
def history_environment(tmp_path):
    person_id = str(uuid4())
    objects, calls = {}, []
    for number, day in enumerate((date(2008, 2, 12), date(2026, 10, 14)), 1):
        partition = DailyVotingPartition("senado", day)
        incoming = tmp_path / f"{number}.ndjson"
        row = vote(person_id, f"senado:plenary:{number}") | {"occurred_on": str(day)}
        incoming.write_text(json.dumps(row) + "\n")
        manifest = consolidate_daily_votes(incoming, tmp_path / "derived", partition, "test-v1")
        directory = tmp_path / "derived" / partition.relative_path
        objects[partition.relative_path + "/manifest.json"] = json.dumps(asdict(manifest)).encode()
        objects[partition.relative_path + "/" + manifest.parquet_file] = (
            directory / manifest.parquet_file
        ).read_bytes()
        objects[partition.relative_path + "/private-checkpoint.parquet"] = b"never public"

    def respond(request):
        calls.append((request.method, str(request.url)))
        assert request.headers["apikey"] == "server-secret"
        if request.method == "POST":
            assert request.url.path == "/storage/v1/object/list-v2/voting-datasets"
            assert json.loads(request.content)["with_delimiter"] is False
            return httpx.Response(
                200,
                json={
                    "folders": [],
                    "hasNext": False,
                    "objects": [{"name": key} for key in objects],
                },
            )
        key = unquote(request.url.path.split("/voting-datasets/", 1)[1])
        return httpx.Response(200, content=objects[key]) if key in objects else httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    reader = DailyDatasetReader(
        SupabaseDatasetStorage(
            StorageConfiguration("https://example.supabase.co", "server-secret"), client
        ),
        tmp_path / "cache",
        clock=lambda: 1000,
    )
    return Metadata(person_id), reader, objects, calls


def history(metadata, reader, **kwargs):
    return get_person_storage_history(
        metadata, reader, metadata.person_id, as_of=date(2026, 10, 18), **kwargs
    )


def test_history_old_records_cursor_and_cache_without_empty_day_probes(history_environment):
    metadata, reader, objects, calls = history_environment
    first = history(metadata, reader, limit=1)
    assert first["items"][0]["occurred_on"] == "2026-10-14"
    assert first["period"]["starts_on"] == "2008-02-12"
    assert first["coverage"]["full_career_verified"] is False
    assert first["coverage"]["datasets"]["catalog_pinned"] is True
    assert first["coverage"]["datasets"]["scan_budget_reached"] is False
    assert first["next_cursor"]
    objects.clear()
    second = history(metadata, reader, limit=1, cursor=first["next_cursor"])
    assert second["items"][0]["occurred_on"] == "2008-02-12"
    assert second["next_cursor"] is None
    assert len(calls) == 5  # one catalog + exactly two published manifests/Parquets
    assert not any("private-checkpoint" in path for _, path in calls)
    assert "server-secret" not in json.dumps(first)
    assert "parquet_file" not in json.dumps(first)


def test_history_empty_catalog_is_explicit(history_environment):
    metadata, reader, objects, calls = history_environment
    objects.clear()
    result = history(metadata, reader)
    assert result["items"] == []
    assert result["period"]["starts_on"] is None
    assert result["coverage"]["datasets"]["state"] == "not_published"
    assert result["next_cursor"] is None
    assert len(calls) == 1


def test_history_cursor_cannot_cross_person_or_office_filters(history_environment):
    metadata, reader, _, calls = history_environment
    first = history(metadata, reader, limit=1)
    previous_calls = len(calls)
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        history(metadata, reader, cursor=first["next_cursor"], office_kind="senator")
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        get_person_storage_history(
            metadata, reader, str(uuid4()), cursor=first["next_cursor"], as_of=date(2026, 10, 18)
        )
    assert len(calls) == previous_calls


def test_history_parquet_hash_remains_verified(history_environment):
    metadata, reader, objects, _ = history_environment
    key = next(key for key in objects if key.endswith(".parquet") and "private" not in key)
    objects[key] = b"tampered"
    with pytest.raises(PublicProfileError, match="DATASET_OBJECT_INTEGRITY_FAILED"):
        history(metadata, reader)


def test_catalog_cursor_loops_are_rejected(history_environment):
    _, reader, _, _ = history_environment
    reader.storage.client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={"objects": [], "folders": [], "hasNext": True, "nextCursor": "same-token"},
            )
        )
    )
    with pytest.raises(DatasetReadError, match="DATASET_CATALOG_INVALID"):
        published_partitions(reader)


def test_catalog_uses_bounded_continuation_not_truncated_success(history_environment, monkeypatch):
    _, reader, _, _ = history_environment
    monkeypatch.setattr("service.dataset_storage.catalog.MAX_CATALOG_PAGES", 1)
    reader.storage.client = httpx.Client(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"objects": [], "folders": [], "hasNext": True, "nextCursor": "next"}
            )
        )
    )
    with pytest.raises(DatasetReadError, match="DATASET_CATALOG_BUDGET_EXCEEDED"):
        published_partitions(reader)


def test_scan_budget_keeps_continuation_even_when_no_person_vote(history_environment, monkeypatch):
    from service.public_profile import storage_history

    metadata, reader, _, _ = history_environment
    catalog = [
        {"source": "senado", "occurred_on": str(date(2026, 10, 18) - timedelta(days=i))}
        for i in range(20)
    ]
    monkeypatch.setattr(storage_history, "published_partitions", lambda reader: catalog)
    inspected = []
    monkeypatch.setattr(
        storage_history, "load_history_batch", lambda reader, batch: inspected.extend(batch) or []
    )
    monkeypatch.setattr(storage_history, "query_snapshot", lambda *args: [])
    first = history(metadata, reader)
    assert len(inspected) == 16
    assert first["items"] == []
    assert first["next_cursor"]
    assert first["coverage"]["datasets"]["scan_budget_reached"]
    second = history(metadata, reader, cursor=first["next_cursor"])
    assert len(inspected) == 20
    assert second["next_cursor"] is None
