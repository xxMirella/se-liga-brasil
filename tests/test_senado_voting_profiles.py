"""Anonymous profile-acquisition budgets and evidence matching, with zero production writes."""

import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from application.cli import create_argument_parser
from crawlers.senado.voting_identity import resolve_profile_identities
from crawlers.senado.voting_profile_acquisition import (
    IdentityProfileAcquisition,
    requested_voter_profile_keys,
    validate_identity_profile_budget,
)
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from storage.files import hash_file


def profile_artifact(tmp_path, key, *, birth_date="1980-01-01", civil_name="Pessoa Fictícia"):
    path = tmp_path / f"profile-{key}.json"
    path.write_text(
        json.dumps(
            {
                "DetalheParlamentar": {
                    "Parlamentar": {
                        "IdentificacaoParlamentar": {
                            "CodigoParlamentar": key,
                            "NomeCompletoParlamentar": civil_name,
                        },
                        "DadosBasicosParlamentar": {"DataNascimento": birth_date},
                    }
                }
            }
        )
    )
    resource = Resource(
        f"profile-{key}",
        "profile",
        f"https://legis.senado.leg.br/dadosabertos/senador/{key}.json",
        "senado_profile",
        2026,
        "fixture",
        file_suffix=".json",
    )
    return DownloadedArtifact(
        resource, path, hash_file(path), "2026-10-17T12:00:00+00:00", path.stat().st_size
    )


def voting_rows(*keys):
    return [{"votacaoSecreta": "N", "votos": [{"codigoParlamentar": key} for key in keys]}]


def test_two_turns_and_partitions_reuse_one_profile_request(tmp_path, monkeypatch):
    artifact = profile_artifact(tmp_path, "123")
    requests, lookups = [], []

    def acquire(path, kind):
        requests.append((path, kind))
        return {}, artifact

    def resolve(connection, artifacts):
        lookups.append(artifacts)
        return {"123": (str(uuid4()), artifact.sha256)}

    monkeypatch.setattr(
        "crawlers.senado.voting_profile_acquisition.resolve_profile_identities", resolve
    )
    acquisition = IdentityProfileAcquisition(10)
    index = {}
    rows = voting_rows("123") * 2
    acquisition.extend_resolved_index(None, SimpleNamespace(json_document=acquire), rows, index)
    acquisition.extend_resolved_index(None, SimpleNamespace(json_document=acquire), rows, index)
    assert requests == [("senador/123.json", "senado_profile")]
    assert len(lookups[0]) == 1
    assert acquisition.summary()["profile_acquisition_attempts"] == 1
    assert set(index) == {"123"}


def test_zero_budget_and_secret_votes_make_no_requests():
    acquisition = IdentityProfileAcquisition()
    assert acquisition.acquire_missing_profiles(None, voting_rows("123"), {}) == []
    assert (
        requested_voter_profile_keys(
            [
                {"votacaoSecreta": "S", "votos": [{"codigoParlamentar": "123"}]},
            ]
        )
        == set()
    )
    assert requested_voter_profile_keys(voting_rows("../123", "-2", None, "", "١٢")) == set()


def test_profile_budget_is_shared_and_incomplete_profiles_not_retried(tmp_path):
    requests = []

    def acquire(path, kind):
        key = path.split("/")[-1].removesuffix(".json")
        requests.append(key)
        return {}, profile_artifact(tmp_path, key, birth_date=None)

    acquisition = IdentityProfileAcquisition(1)
    client = SimpleNamespace(json_document=acquire)
    assert acquisition.acquire_missing_profiles(client, voting_rows("2", "1"), {}) == []
    assert acquisition.acquire_missing_profiles(client, voting_rows("1", "3"), {}) == []
    assert requests == ["1"]
    assert acquisition.summary()["profiles_without_personal_evidence"] == 1


def test_cached_unmatched_identity_is_not_repeatedly_downloaded(tmp_path):
    artifact = profile_artifact(tmp_path, "123")
    acquisition = IdentityProfileAcquisition(10)
    acquisition.mark_cached_profiles([artifact])
    assert acquisition.acquire_missing_profiles(None, voting_rows("123"), {}) == []


@pytest.mark.parametrize("maximum", [-1, 101, True, None, "1"])
def test_invalid_profile_budgets_fail_before_network(maximum):
    with pytest.raises(IngestionError, match="INVALID_SENATE_IDENTITY_PROFILE_BUDGET"):
        validate_identity_profile_budget(maximum)


def test_cli_exposes_disabled_default_and_explicit_profile_budget():
    parser = create_argument_parser()
    assert parser.parse_args(["collect-votes", "--source", "senado"]).max_identity_profiles == 0
    assert (
        parser.parse_args(
            [
                "collect-votes",
                "--source",
                "senado",
                "--max-identity-profiles",
                "10",
            ]
        ).max_identity_profiles
        == 10
    )


def test_profile_http_failure_propagates_without_resolved_identity():
    def acquire(path, kind):
        raise IngestionError("HTTP_ERROR", {"status": 429})

    acquisition = IdentityProfileAcquisition(1)
    with pytest.raises(IngestionError, match="HTTP_ERROR"):
        acquisition.acquire_missing_profiles(
            SimpleNamespace(json_document=acquire), voting_rows("1"), {}
        )
    assert acquisition.acquired == 0


def test_all_profiles_resolve_in_one_database_call(tmp_path):
    calls = []
    person_id = str(uuid4())

    def execute(query, parameters):
        calls.append((query, parameters))
        return SimpleNamespace(
            fetchall=lambda: [
                {
                    "person_id": person_id,
                    "normalized_name": "pessoa ficticia",
                    "birth_date": date(1980, 1, 1),
                }
            ]
        )

    profiles = [profile_artifact(tmp_path, "1"), profile_artifact(tmp_path, "2")]
    resolved = resolve_profile_identities(SimpleNamespace(execute=execute), profiles)
    assert len(calls) == 1
    assert set(resolved) == {"1", "2"}


def test_identical_full_name_and_birth_date_remain_unresolved_when_ambiguous(tmp_path):
    rows = [
        {
            "person_id": str(uuid4()),
            "normalized_name": "pessoa ficticia",
            "birth_date": date(1980, 1, 1),
        }
        for _ in range(2)
    ]
    connection = SimpleNamespace(execute=lambda *args: SimpleNamespace(fetchall=lambda: rows))
    assert resolve_profile_identities(connection, [profile_artifact(tmp_path, "1")]) == {}


def test_download_cache_prevents_repeated_http_for_same_profile(tmp_path, monkeypatch):
    import httpx

    from crawlers.senado.acquisition import SenateAcquisition
    from crawlers.senado.configuration import OFFICIAL_HOSTS, SenateConfiguration
    from service.acquisition.http_client import OfficialHttpClient

    artifact = profile_artifact(tmp_path, "1")
    requests = []

    def respond(request):
        requests.append(request.url.path)
        return httpx.Response(200, content=artifact.path.read_bytes())

    monkeypatch.setattr("service.acquisition.http_client.pace_official_request", lambda *args: None)
    configuration = SenateConfiguration(tmp_path / "cache")
    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        transport = OfficialHttpClient(configuration, client, OFFICIAL_HOSTS)
        for _ in range(2):
            acquisition = SenateAcquisition(configuration, transport)
            budget = IdentityProfileAcquisition(1)
            assert len(budget.acquire_missing_profiles(acquisition, voting_rows("1"), {})) == 1
    assert requests == ["/dadosabertos/senador/1.json"]


@pytest.mark.integration
def test_sql_personal_evidence_requires_unique_name_birth_and_uses_one_lookup(
    integration_database, tmp_path
):
    connection = integration_database
    connection.execute("""
        INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method)
        VALUES('profile-fixture','Fixture','https://example.invalid','api')
    """)
    connection.execute("""
        INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,
          content_sha256,payload)
        SELECT id,'profile-fixture','https://example.invalid',repeat('c',64),'{}'
        FROM se_liga_brasil.source WHERE code='profile-fixture'
    """)
    for name in ("pessoa ficticia", "pessoa ficticia", "pessoa unica"):
        connection.execute(
            """
            INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,
              normalized_name,birth_date,primary_record_id)
            SELECT %s,%s,%s,%s,%s,'1980-01-01',id FROM se_liga_brasil.source_record
            WHERE external_key='profile-fixture'
        """,
            (str(uuid4()), str(uuid4()), name, name, name),
        )
    lookups = []

    def execute(query, parameters):
        lookups.append(query)
        return connection.execute(query, parameters)

    profiles = [
        profile_artifact(tmp_path, "1"),
        profile_artifact(tmp_path, "2", civil_name="Pessoa Única"),
    ]
    resolved = resolve_profile_identities(SimpleNamespace(execute=execute), profiles)
    assert len(lookups) == 1
    assert set(resolved) == {"2"}


def test_expired_unmatched_profile_can_be_rechecked_but_recent_manifest_is_reused(tmp_path):
    from dataclasses import replace
    from datetime import UTC, datetime, timedelta

    from crawlers.senado.configuration import SenateConfiguration
    from storage.files import save_json

    now = datetime.now(UTC)
    artifact = replace(
        profile_artifact(tmp_path, "123"), fetched_at=(now - timedelta(days=2)).isoformat()
    )
    configuration = SenateConfiguration(tmp_path)
    acquisition = IdentityProfileAcquisition(1)
    acquisition.mark_cached_profiles([artifact], configuration)
    assert acquisition.attempted_keys == set()
    save_json(
        tmp_path / "manifests" / (artifact.resource.resource_id + ".json"),
        {
            "last_full_check_at": artifact.fetched_at,
            "checked_at": now.isoformat(),
        },
    )
    acquisition.mark_cached_profiles([artifact], configuration)
    assert acquisition.attempted_keys == {"123"}
