"""Publication and queue boundaries without credentials, production DB or networking."""

import hashlib
import json
from contextlib import nullcontext
from types import SimpleNamespace

import httpx
import pytest

from database import voting_refresh
from service.attendance import dataset
from service.dataset_storage import supabase
from service.ingestion.contracts import IngestionError
from service.voting_pipeline import source_senado
from storage.files import load_json, save_json


@pytest.mark.parametrize("installed", [True, False])
def test_queue_schema_migration_runs_only_when_missing(monkeypatch, installed):
    calls = []
    monkeypatch.setattr(voting_refresh, "read_sql_file", lambda path: "BEGIN; SELECT 1; COMMIT;")
    monkeypatch.setattr(voting_refresh, "strip_transaction_wrapper", lambda sql: "SELECT 1")
    connection = SimpleNamespace(
        transaction=lambda: nullcontext(),
        execute=lambda sql, *args: (
            calls.append(sql) or SimpleNamespace(fetchone=lambda: {"installed": installed})
        ),
    )
    assert voting_refresh.apply_voting_refresh_schema(connection) is not installed
    assert len(calls) == (1 if installed else 2)


@pytest.mark.parametrize("timezone", ["UTC", "GMT", None, "America/Belem"])
def test_cron_configuration_validates_timezone_before_scheduling(monkeypatch, timezone):
    monkeypatch.setattr(voting_refresh, "apply_voting_refresh_schema", lambda _: None)
    calls = []

    def execute(sql, parameters=None):
        calls.append((sql, parameters))
        return SimpleNamespace(fetchone=lambda: {"timezone": timezone, "job_id": 7})

    connection = SimpleNamespace(transaction=lambda: nullcontext(), execute=execute)
    if timezone == "America/Belem":
        with pytest.raises(ValueError, match="Cron timezone"):
            voting_refresh.configure_voting_schedule(connection)
        assert not any(parameters for sql, parameters in calls)
    else:
        result = voting_refresh.configure_voting_schedule(connection)
        assert result == {"job_id": 7, "days": [1, 15], "local_time": "08:00 America/Belem"}
        assert calls[2][1][1] == "0 11 1,15 * *"
        assert calls[3][1][1] == "0 12 * * *"


@pytest.mark.parametrize("owned", [True, False])
def test_queue_completion_requires_owned_lease_and_preserves_summary(owned):
    calls = []
    connection = SimpleNamespace(
        execute=lambda sql, params: (
            calls.append(params)
            or SimpleNamespace(fetchone=lambda: {"id": "job"} if owned else None)
        )
    )
    if owned:
        voting_refresh.finish_voting_refresh(connection, "job", "worker", {"rows": 4})
        assert calls[0][0].obj == {"rows": 4}
        assert calls[0][1:] == ("job", "worker")
    else:
        with pytest.raises(ValueError, match="lease is no longer owned"):
            voting_refresh.finish_voting_refresh(connection, "job", "worker", {})


@pytest.mark.parametrize("delay,expected", [(-1, 60), (120, 120), (1000000, 86400)])
def test_queue_failures_bound_retry_delay_and_error_payload(delay, expected):
    calls = []
    connection = SimpleNamespace(execute=lambda sql, params: calls.append(params))
    voting_refresh.fail_voting_refresh(connection, "job", "worker", "X" * 200, delay)
    assert calls == [("X" * 100, expected, "job", "worker")]


def test_queue_claim_passes_worker_ownership_and_returns_empty_result():
    calls = []
    connection = SimpleNamespace(
        execute=lambda sql, params: (
            calls.append((sql, params)) or SimpleNamespace(fetchone=lambda: None)
        )
    )
    assert voting_refresh.claim_voting_refresh(connection, "worker") is None
    assert calls[0][1] == ("worker",)
    assert "SKIP LOCKED" in calls[0][0]


@pytest.mark.parametrize("missing_status", [400, 404])
def test_missing_bucket_is_created_private_with_fixed_size_budget(missing_status):
    calls = []

    def respond(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(missing_status, json={"code": "NoSuchBucket"})
        return httpx.Response(200)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        storage = supabase.SupabaseDatasetStorage(
            supabase.StorageConfiguration("https://example.supabase.co", "offline-token"), client
        )
        storage.ensure_private_bucket()
    payload = json.loads(calls[1].content)
    assert payload["public"] is False
    assert payload["file_size_limit"] == supabase.MAX_OBJECT_BYTES


def test_storage_configuration_fallback_project_and_secret_never_in_repr(monkeypatch):
    monkeypatch.setattr(
        supabase,
        "dotenv_values",
        lambda path: {
            "SUPABASE_PROJECT_ID": "a" * 20,
            "SUPABASE_SERVICE_ROLE_KEY": "offline-secret",
        },
    )
    monkeypatch.setattr(supabase.os, "environ", {})
    config = supabase.load_storage_configuration("unused-offline.env")
    assert config.url == "https://" + "a" * 20 + ".supabase.co"
    assert "offline-secret" not in repr(config)


def test_storage_configuration_without_credentials_fails_locally(monkeypatch):
    monkeypatch.setattr(supabase, "dotenv_values", lambda path: {})
    monkeypatch.setattr(supabase.os, "environ", {})
    with pytest.raises(ValueError, match="CREDENTIALS_REQUIRED"):
        supabase.load_storage_configuration()


def test_remote_verification_closes_response_when_size_budget_is_exceeded(monkeypatch):
    monkeypatch.setattr(supabase, "MAX_OBJECT_BYTES", 2)
    with httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"oversized"))
    ) as client:
        storage = supabase.SupabaseDatasetStorage(
            supabase.StorageConfiguration("https://example.supabase.co", "offline-token"), client
        )
        with pytest.raises(ValueError, match="verification budget"):
            storage.verify_remote_object("object/path", "a" * 64)


def test_attendance_snapshot_groups_months_and_requires_private_bucket(monkeypatch, tmp_path):
    calls = []
    rows = [
        {"normalized_value": {"period": period, "personId": person}}
        for period, person in [("2026-02", "one"), ("2026-01", "one"), ("2026-02", "two")]
    ]
    connection = SimpleNamespace(execute=lambda sql: SimpleNamespace(fetchall=lambda: rows))
    storage = SimpleNamespace(ensure_private_bucket=lambda: calls.append("private"))
    monkeypatch.setattr(
        dataset,
        "publish_attendance_month",
        lambda directory, storage, period, records: calls.append((period, len(records))),
    )
    result = dataset.publish_attendance_dataset(connection, tmp_path, storage)
    assert calls == ["private", ("2026-01", 1), ("2026-02", 2)]
    assert result == {"partitions": 2, "rows": 3, "published": True}


@pytest.mark.parametrize("fail_manifest", [False, True])
def test_attendance_manifest_is_activated_only_after_verified_file_upload(tmp_path, fail_manifest):
    calls = []

    def upload(key, path, digest):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest
        calls.append("parquet")

    def request(*args, **kwargs):
        calls.append("manifest")
        return httpx.Response(
            500 if fail_manifest else 200, request=httpx.Request("POST", "https://example.invalid")
        )

    storage = SimpleNamespace(upload_immutable=upload, request=request, object_path=lambda key: key)
    records = [{"period": "2026-01", "personId": "canonical", "presentDays": 3}]
    manifest_path = tmp_path / "attendance/camara/year=2026/month=01/manifest.json"
    if fail_manifest:
        with pytest.raises(httpx.HTTPStatusError):
            dataset.publish_attendance_month(tmp_path, storage, "2026-01", records)
        assert not manifest_path.exists()
    else:
        first = dataset.publish_attendance_month(tmp_path, storage, "2026-01", records)
        second = dataset.publish_attendance_month(tmp_path, storage, "2026-01", records)
        assert first == second == load_json(manifest_path)
        assert first["coverage"] == "collected_people_only"
    assert calls == ["parquet", "manifest"]


@pytest.mark.parametrize("value", [None, "2026", 2026, "", "oops", 1700, 2201])
def test_source_matter_year_is_optional_but_never_silently_invalid(value):
    if value is None:
        assert source_senado.optional_year(value) is None
    elif str(value) == "2026":
        assert source_senado.optional_year(value) == 2026
    else:
        with pytest.raises(IngestionError, match="INVALID_SENATE_MATTER_YEAR"):
            source_senado.optional_year(value)


def test_source_identity_observation_only_uses_manifest_with_matching_hash(tmp_path):
    from storage.files import hash_content

    url = "https://legis.senado.leg.br/dadosabertos/senador/1.json"
    path = tmp_path / "manifests" / ("senado-" + hash_content(url) + ".json")
    acquisition = SimpleNamespace(configuration=SimpleNamespace(storage_directory=tmp_path))
    save_json(path, {"sha256": "different", "fetched_at": "2026-05-01T00:00:00Z"})
    observations = {}
    source_senado.update_identity_observations(
        acquisition, {"1": ("person", "expected")}, observations
    )
    assert observations == {}
    save_json(path, {"sha256": "expected", "fetched_at": "2026-05-01T00:00:00Z"})
    source_senado.update_identity_observations(
        acquisition, {"1": ("person", "expected")}, observations
    )
    assert observations == {"expected": "2026-05-01T00:00:00Z"}
    source_senado.update_identity_observations(
        acquisition, {"1": ("person", "expected")}, observations
    )
    assert observations == {"expected": "2026-05-01T00:00:00Z"}


def test_senate_source_collection_reuses_cached_identity_observations(monkeypatch, tmp_path):
    from datetime import date

    profiles = [SimpleNamespace(sha256="a" * 64, fetched_at="2026-05-01T00:00:00Z")]
    monkeypatch.setattr(source_senado, "cached_identity_profiles", lambda directory: profiles)
    monkeypatch.setattr(
        source_senado,
        "resolve_profile_identities",
        lambda connection, profiles: {"1": ("canonical", "a" * 64)},
    )
    monkeypatch.setattr(
        source_senado.IdentityProfileAcquisition, "mark_cached_profiles", lambda *args: None
    )
    monkeypatch.setattr(
        source_senado, "official_source_acquisition", lambda *args: nullcontext("acquisition")
    )
    calls = []
    monkeypatch.setattr(
        source_senado,
        "normalize_senate_source_files",
        lambda *args, **kwargs: calls.append((args, kwargs)) or {"rows": 0},
    )
    result = source_senado.collect_senate_source_files(
        None, tmp_path, date(2026, 5, 1), date(2026, 5, 2), tmp_path / "out.ndjson"
    )
    assert result == {"rows": 0}
    assert calls[0][0][1] == "acquisition"
    assert calls[0][1]["identity_observations"] == {"a" * 64: "2026-05-01T00:00:00Z"}


def test_source_requires_timezone_in_every_dependent_observation():
    with pytest.raises(IngestionError, match="OBSERVATION_TIMEZONE_REQUIRED"):
        source_senado.latest_observation("2026-05-01T12:00:00Z", "2026-05-01T10:00:00")


def test_source_explicit_secret_vote_is_documented_without_individual_choices():
    raw = {
        "codigoSessaoVotacao": 1,
        "dataSessao": "2026-05-01",
        "idProcesso": 2,
        "votacaoSecreta": "S",
    }
    artifact = SimpleNamespace(fetched_at="2026-05-02T00:00:00Z")
    assert source_senado.secret_voting_observations([raw], artifact) == [
        {
            "voting_id": "senado:plenary:1",
            "occurred_on": "2026-05-01",
            "source_observed_at": "2026-05-02T00:00:00Z",
        }
    ]


def test_oversized_local_object_is_rejected_before_open_or_upload(monkeypatch, tmp_path):
    path = tmp_path / "large"
    path.write_bytes(b"123")
    monkeypatch.setattr(supabase, "MAX_OBJECT_BYTES", 2)
    storage = supabase.SupabaseDatasetStorage(None, None)
    with pytest.raises(ValueError, match="exceeds budget"):
        storage.upload_immutable("object", path, hashlib.sha256(b"123").hexdigest())
