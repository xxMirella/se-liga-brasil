"""Offline failure boundaries for publication, bounded reads and catalog discovery."""

import hashlib
import json
from datetime import date, datetime

import httpx
import pytest

from service.analytical_datasets.contracts import event_bounds
from service.analytical_datasets.storage import enforce_disk_budget
from service.daily_voting_dataset.contracts import DailyVotingPartition
from service.daily_voting_dataset.retirements import normalize_retirements
from service.dataset_storage.catalog import parse_published_partition, published_partitions
from service.dataset_storage.read import DailyDatasetReader, DatasetReadError
from service.dataset_storage.supabase import StorageConfiguration, SupabaseDatasetStorage


@pytest.fixture
def storage_reader(tmp_path):
    clients = []

    def create(respond, **options):
        client = httpx.Client(transport=httpx.MockTransport(respond))
        clients.append(client)
        storage = SupabaseDatasetStorage(
            StorageConfiguration("https://example.supabase.co", "offline-test-token"), client
        )
        return DailyDatasetReader(storage, tmp_path / "cache", **options)

    yield create
    for client in clients:
        client.close()


@pytest.mark.parametrize("key", ["/absolute", "../parent", "a/../b", "a//b", "a/./b"])
def test_object_keys_cannot_escape_or_alias_storage_location(storage_reader, key):
    reader = storage_reader(lambda _: pytest.fail("Invalid paths must not issue requests"))
    with pytest.raises(ValueError, match="Invalid dataset object key"):
        reader.storage.object_path(key)


@pytest.mark.parametrize(
    "status,body,missing",
    [(404, b"", True), (400, b'{"code":"NoSuchKey"}', True)],
)
def test_missing_object_is_optional_only_when_explicitly_allowed(
    storage_reader, status, body, missing
):
    reader = storage_reader(lambda _: httpx.Response(status, content=body))
    assert reader.download("manifest.json", 100, allow_missing=missing) is None
    with pytest.raises(DatasetReadError, match="DATASET_STORAGE_UNAVAILABLE"):
        reader.download("manifest.json", 100)


@pytest.mark.parametrize("body", [b"invalid json", b"[]", b'{"code":"Unauthorized"}'])
def test_other_storage_400_errors_are_not_treated_as_absent(storage_reader, body):
    reader = storage_reader(lambda _: httpx.Response(400, content=body))
    with pytest.raises(DatasetReadError, match="DATASET_STORAGE_UNAVAILABLE"):
        reader.download("manifest.json", 100, allow_missing=True)


def test_oversized_download_never_enters_local_cache(storage_reader):
    reader = storage_reader(lambda _: httpx.Response(200, content=b"12345"))
    with pytest.raises(DatasetReadError, match="DATASET_OBJECT_TOO_LARGE"):
        reader.download("manifest.json", 4)
    assert list(reader.directory.iterdir()) == []


def test_cache_replacement_counts_replaced_bytes_and_preserves_on_overflow(storage_reader):
    reader = storage_reader(
        lambda _: pytest.fail("Cache writes must remain local"), max_cache_bytes=4
    )
    path = reader.directory / "entry"
    reader.save_bytes(path, b"1234")
    reader.save_bytes(path, b"abcd")
    with pytest.raises(DatasetReadError, match="DATASET_CACHE_BUDGET_EXCEEDED"):
        reader.save_bytes(path, b"abcde")
    assert path.read_bytes() == b"abcd"
    assert list(reader.directory.iterdir()) == [path]


def test_parquet_corruption_is_rejected_before_cache_write(storage_reader):
    reader = storage_reader(lambda _: httpx.Response(200, content=b"corrupted"))
    partition = DailyVotingPartition("camara", date(2026, 5, 27))
    manifest = {"parquet_sha256": "a" * 64, "parquet_file": "a" * 64 + ".parquet"}
    with pytest.raises(DatasetReadError, match="DATASET_OBJECT_INTEGRITY_FAILED"):
        reader.parquet_path(partition, manifest)
    assert list(reader.directory.iterdir()) == []


def test_cached_parquet_tampering_is_not_replaced_silently(storage_reader):
    reader = storage_reader(lambda _: pytest.fail("Corruption must fail before network I/O"))
    digest = hashlib.sha256(b"original").hexdigest()
    (reader.directory / (digest + ".parquet")).write_bytes(b"tampered")
    with pytest.raises(DatasetReadError, match="DATASET_CACHE_INTEGRITY_FAILED"):
        reader.parquet_path(None, {"parquet_sha256": digest})


def test_snapshot_filter_and_expiry_are_checked_before_reuse(storage_reader):
    now = [1000]
    reader = storage_reader(
        lambda _: pytest.fail("Empty snapshots are local"), clock=lambda: now[0]
    )
    token, payload = reader.create_snapshot([], "person-a")
    assert reader.load_snapshot(token, "person-a") == payload
    with pytest.raises(DatasetReadError, match="INVALID_CURSOR"):
        reader.load_snapshot(token, "person-b")
    now[0] += 3600
    with pytest.raises(DatasetReadError, match="DATASET_SNAPSHOT_EXPIRED"):
        reader.load_snapshot(token, "person-a")
    reader.prune_expired_cache()
    assert not (reader.directory / (token + ".snapshot.json")).exists()


def test_snapshot_modified_after_creation_fails_integrity(storage_reader):
    reader = storage_reader(lambda _: pytest.fail("Snapshot reads are local"))
    token, _ = reader.create_snapshot([], "filters")
    (reader.directory / (token + ".snapshot.json")).write_text("{}")
    with pytest.raises(DatasetReadError, match="DATASET_SNAPSHOT_INTEGRITY_FAILED"):
        reader.load_snapshot(token, "filters")


def test_repeated_catalog_cursor_aborts_instead_of_looping(storage_reader):
    calls = []

    def respond(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={"objects": [], "hasNext": True, "nextCursor": "same"})

    reader = storage_reader(respond)
    with pytest.raises(DatasetReadError, match="DATASET_CATALOG_INVALID"):
        published_partitions(reader)
    assert len(calls) == 2
    assert not (reader.directory / "published-history.catalog.json").exists()


@pytest.mark.parametrize(
    "path",
    [
        "private/checkpoint.parquet",
        "legislative/camara/person_voting_timeline/year=2026/manifest.json",
    ],
)
def test_catalog_ignores_non_daily_and_private_objects(path):
    assert parse_published_partition(path) is None


def test_catalog_rejects_impossible_published_day():
    with pytest.raises(DatasetReadError, match="DATASET_CATALOG_INVALID"):
        parse_published_partition(
            "legislative/camara/person_voting_timeline/year=2026/month=02/day=30/manifest.json"
        )


def test_month_bounds_account_for_leap_year_without_inventing_day_precision():
    assert event_bounds("2000-02", "month") == ("2000-02-01", "2000-02-29")
    assert event_bounds("2100-02", "month") == ("2100-02-01", "2100-02-28")


@pytest.mark.parametrize("day", [datetime(2026, 5, 27), "2026-05-27", None])
def test_daily_partition_requires_exact_date_not_datetime_or_text(day):
    with pytest.raises(ValueError, match="precise voting day"):
        DailyVotingPartition("camara", day)


def test_disk_budget_counts_nested_files_and_accepts_exact_boundary(tmp_path):
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "data").write_bytes(b"123")
    enforce_disk_budget(tmp_path, 2, 5)
    with pytest.raises(ValueError, match="disk budget exceeded"):
        enforce_disk_budget(tmp_path, 3, 5)


@pytest.mark.parametrize("observation", [None, "2026-05-27T12:00:00"])
def test_retirement_requires_explicit_timezone_aware_source_timestamp(observation):
    with pytest.raises(ValueError, match="timestamp|timezone"):
        normalize_retirements(["camara:voting:123-1"], observation)


def test_retirements_deduplicate_and_normalize_observation_to_utc():
    identifiers, observation = normalize_retirements(
        ["camara:voting:123-2", "camara:voting:123-1", "camara:voting:123-2"],
        "2026-05-27T09:00:00-03:00",
    )
    assert identifiers == ("camara:voting:123-1", "camara:voting:123-2")
    assert observation == "2026-05-27T12:00:00.000000+00:00"


def test_empty_retirement_does_not_accept_unexplained_observation():
    assert normalize_retirements([], None) == ((), None)
    with pytest.raises(ValueError, match="without retired events"):
        normalize_retirements([], "2026-05-27T12:00:00Z")


@pytest.mark.parametrize(
    "url",
    [
        "http://example.supabase.co",
        "https://example.supabase.co.attacker.invalid",
        "https://user:password@example.supabase.co",
        "https://example.supabase.co:444",
        "https://example.supabase.co/other",
    ],
)
def test_storage_credentials_cannot_be_sent_to_untrusted_endpoint(url):
    with pytest.raises(ValueError, match="endpoint"):
        StorageConfiguration(url, "offline-test-token")


@pytest.mark.parametrize("bucket", ["a", "Uppercase", "a/b", "a" * 64])
def test_storage_bucket_contract_rejects_ambiguous_names(bucket):
    with pytest.raises(ValueError, match="valid bucket"):
        StorageConfiguration("https://example.supabase.co", "offline-test-token", bucket)


def test_failed_immutable_upload_cannot_overwrite_different_remote_content(
    storage_reader, tmp_path
):
    local = tmp_path / "public.parquet"
    local.write_bytes(b"expected-content")
    calls = []

    def respond(request):
        calls.append(request.method)
        if request.method == "POST":
            assert request.headers["x-upsert"] == "false"
            return httpx.Response(409)
        return httpx.Response(200, content=b"different-content")

    storage = storage_reader(respond).storage
    with pytest.raises(ValueError, match="Remote content-addressed object differs"):
        storage.upload_immutable(
            "public.parquet", local, hashlib.sha256(local.read_bytes()).hexdigest()
        )
    assert calls == ["POST", "GET"]


def test_duplicate_immutable_upload_succeeds_only_after_remote_hash_verification(
    storage_reader, tmp_path
):
    local = tmp_path / "public.parquet"
    content = b"same-content"
    local.write_bytes(content)
    calls = []

    def respond(request):
        calls.append(request.method)
        return (
            httpx.Response(409)
            if request.method == "POST"
            else httpx.Response(200, content=content)
        )

    storage_reader(respond).storage.upload_immutable(
        "public.parquet", local, hashlib.sha256(content).hexdigest()
    )
    assert calls == ["POST", "GET"]


def test_manifest_hash_mismatch_fails_before_upload(storage_reader, tmp_path):
    local = tmp_path / "public.parquet"
    local.write_bytes(b"changed")
    storage = storage_reader(
        lambda _: pytest.fail("Mismatched local data must not be uploaded")
    ).storage
    with pytest.raises(ValueError, match="differs from manifest"):
        storage.upload_immutable("public.parquet", local, "a" * 64)


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"objects": [], "hasNext": 1},
        {"objects": {}, "hasNext": False},
        {"objects": [None], "hasNext": False},
        {"objects": [{"name": 12}], "hasNext": False},
        {"objects": [], "hasNext": True},
        {"objects": [], "hasNext": True, "nextCursor": ""},
    ],
)
def test_malformed_catalog_cannot_activate_history_cache(storage_reader, payload):
    reader = storage_reader(lambda _: httpx.Response(200, json=payload))
    with pytest.raises(DatasetReadError, match="DATASET_CATALOG_INVALID"):
        published_partitions(reader)
    assert not (reader.directory / "published-history.catalog.json").exists()


def test_catalog_network_failure_does_not_become_empty_history(storage_reader):
    reader = storage_reader(lambda _: httpx.Response(503))
    with pytest.raises(DatasetReadError, match="DATASET_CATALOG_UNAVAILABLE"):
        published_partitions(reader)


def test_corrupted_catalog_cache_is_reported_without_network_retry(storage_reader):
    reader = storage_reader(lambda _: pytest.fail("Corrupt local state must fail closed"))
    (reader.directory / "published-history.catalog.json").write_text("incomplete-json")
    with pytest.raises(DatasetReadError, match="DATASET_CACHE_INTEGRITY_FAILED"):
        published_partitions(reader)


def test_remote_manifest_malformed_json_never_activates_cache(storage_reader):
    reader = storage_reader(lambda _: httpx.Response(200, content=b"not-json"))
    with pytest.raises(DatasetReadError, match="DATASET_MANIFEST_INVALID"):
        reader.current_manifest(DailyVotingPartition("camara", date(2026, 5, 27)))
    assert list(reader.directory.iterdir()) == []
