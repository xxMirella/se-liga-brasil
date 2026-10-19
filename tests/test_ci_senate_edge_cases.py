"""Senate partial evidence never invents voting dates, identities or final outcomes."""

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from types import SimpleNamespace

import pytest

from crawlers.senado import committee_voting as committee
from crawlers.senado import legislative, process_pipeline, voting_identity
from normalization.identity import normalize_person_name
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from storage.files import save_json


def committee_row(**updates):
    return {
        "CodigoVotacao": "1",
        "CodigoColegiado": "2",
        "SiglaCasaColegiado": "SF",
        "SiglaColegiado": "CCJ",
        "DataHoraInicioReuniao": "2026-05-01T10:00:00",
        "IdentificacaoMateria": "PL 10/2026",
    } | updates


def test_committee_meeting_is_not_assumed_to_be_exact_voting_day():
    row = committee.normalize_committee_voting(committee_row())
    assert row["meeting_date"] == "2026-05-01"
    assert row["occurred_on"] is None
    assert row["date_precision"] == "unknown"
    assert row["final_outcome"] is None
    assert row["nominal_availability"] == "unavailable"
    assert row["proposition_reference"] == {"kind": "PL", "number": "10", "year": 2026}


@pytest.mark.parametrize(
    "payload,code",
    [
        ([], "SCHEMA_CHANGED"),
        ({"VotacoesComissao": {}}, "VERSION_CHANGED"),
        ({"VotacoesComissao": {"Metadados": {"VersaoServico": "2"}}}, "VERSION_CHANGED"),
        (
            {"VotacoesComissao": {"Metadados": {"VersaoServico": 1}, "Votacoes": []}},
            "SCHEMA_CHANGED",
        ),
        (
            {
                "VotacoesComissao": {
                    "Metadados": {"VersaoServico": 1},
                    "Votacoes": {"Votacao": [None]},
                }
            },
            "SCHEMA_CHANGED",
        ),
    ],
)
def test_committee_schema_changes_fail_explicitly(payload, code):
    with pytest.raises(IngestionError, match=code):
        committee.committee_voting_rows(payload)


@pytest.mark.parametrize("rows", [None, {}, {"Votacao": []}])
def test_committee_empty_publication_is_not_verified_absence(rows):
    payload = {"VotacoesComissao": {"Metadados": {"VersaoServico": 1}, "Votacoes": rows}}
    assert committee.committee_voting_rows(payload) == ([], "not_published_in_response")


@pytest.mark.parametrize("container", [[], {"Voto": [None]}, {"Voto": "unexpected"}])
def test_committee_malformed_person_vote_is_not_ignored(container):
    with pytest.raises(IngestionError, match="PERSON_VOTE_SCHEMA_CHANGED"):
        committee.committee_vote_rows({"Votos": container})


@pytest.mark.parametrize("presiding", [[], "yes", 2])
def test_committee_presiding_flag_must_follow_source_contract(presiding):
    with pytest.raises(IngestionError, match="PRESIDING_FLAG_CHANGED"):
        committee.normalize_committee_individual_vote(
            {"NomeParlamentar": "Pessoa Teste", "QualidadeVoto": "S", "VotoPresidente": presiding}
        )


def test_committee_unknown_choice_does_not_become_no_vote():
    vote = committee.normalize_committee_individual_vote(
        {"NomeParlamentar": "Pessoa Teste", "QualidadeVoto": "UNPUBLISHED"}
    )
    assert vote["choice"] is None
    assert vote["participation_status"] == "unknown"
    assert vote["is_presiding"] is None


@pytest.mark.parametrize(
    "updates,code",
    [
        ({"legislative_body_code": "CAE"}, "BODY_MISMATCH"),
        ({"meeting_date": "2026-06-01"}, "OUTSIDE_PARTITION"),
    ],
)
def test_committee_scope_rejects_wrong_institution_or_period(updates, code):
    row = {
        "legislative_body_code": "CCJ",
        "meeting_date": "2026-05-01",
        "source_key": "one",
    } | updates
    with pytest.raises(IngestionError, match=code):
        committee.validate_committee_scope([row], "CCJ", date(2026, 5, 1), date(2026, 5, 2))


def test_duplicate_committee_events_are_not_counted_twice():
    row = {"legislative_body_code": "CCJ", "meeting_date": None, "source_key": "one"}
    with pytest.raises(IngestionError, match="DUPLICATE_SENATE_COMMITTEE_VOTING"):
        committee.validate_committee_scope([row, row], "CCJ", date(2026, 5, 1), date(2026, 5, 2))


@pytest.mark.parametrize("maximum", [True, 0, 1001, "1"])
def test_committee_invalid_budget_stops_before_network(maximum):
    with pytest.raises(IngestionError, match="BUDGET"):
        committee.collect_committee_votings(
            None, "CCJ", date(2026, 5, 1), date(2026, 5, 2), maximum=maximum
        )


@pytest.mark.parametrize("code", ["../internal", "ccj", None])
def test_committee_code_cannot_inject_request_path(code):
    with pytest.raises(IngestionError, match="SCOPE"):
        committee.collect_committee_votings(None, code, date(2026, 5, 1), date(2026, 5, 2))


def test_committee_collection_marks_dates_unverified(monkeypatch):
    acquisition = SimpleNamespace(
        json_document=lambda *args: (
            {
                "VotacoesComissao": {
                    "Metadados": {"VersaoServico": 1},
                    "Votacoes": {"Votacao": committee_row()},
                }
            },
            "artifact",
        )
    )
    rows, artifact, coverage = committee.collect_committee_votings(
        acquisition, "CCJ", date(2026, 5, 1), date(2026, 5, 2)
    )
    assert len(rows) == 1 and artifact == "artifact"
    assert coverage["exact_voting_dates"] == "not_published_in_contract"
    assert coverage["coverage"] == "not_verified"


def test_mixed_house_committee_only_resolves_senate_profile_identity():
    vote = {
        "CodigoParlamentar": "1",
        "SiglaCasaParlamentar": "SF",
        "NomeParlamentar": "Pessoa Teste",
        "QualidadeVoto": "N",
    }
    row = committee_row(
        Votos={
            "Voto": [vote, vote | {"SiglaCasaParlamentar": "CD"}, vote | {"CodigoParlamentar": "2"}]
        }
    )
    resolved, missing = committee.resolve_committee_individuals(
        [row], {"1": ("canonical", "a" * 64)}
    )
    assert missing == 2
    assert resolved[0]["person_id"] == "canonical"
    assert resolved[0]["choice"] == "no"
    row["Votos"]["Voto"] = [vote, vote]
    with pytest.raises(IngestionError, match="DUPLICATE_SENATE_COMMITTEE_VOTER"):
        committee.resolve_committee_individuals([row], {"1": ("canonical", "a" * 64)})


@pytest.mark.parametrize("value", ["invalid", 0, -1, None])
def test_process_keys_reject_invalid_input_before_io(value):
    with pytest.raises(IngestionError, match="INVALID_SENATE_PROCESS_SCOPE"):
        legislative.bounded_process_keys([value], 1)


def test_process_keys_are_deduplicated_and_bounded_before_http():
    assert legislative.bounded_process_keys(["2", 1, 2], 2) == [1, 2]
    with pytest.raises(IngestionError, match="BATCH_LIMIT_EXCEEDED"):
        legislative.bounded_process_keys([1, 2], 1)
    with pytest.raises(IngestionError, match="INVALID_SENATE_PROCESS_SCOPE"):
        legislative.bounded_process_keys([], 0)


def test_process_response_key_must_match_requested_document():
    acquisition = SimpleNamespace(
        json_document=lambda *args: ({"id": 2, "sigla": "PL"}, "artifact")
    )
    with pytest.raises(IngestionError, match="KEY_MISMATCH"):
        list(legislative.collect_process_details(acquisition, [1]))


def test_process_events_preserve_description_without_inventing_final_result():
    result = legislative.normalize_process(
        {
            "id": 1,
            "sigla": "PL",
            "autuacoes": [
                {
                    "informesLegislativos": [
                        {
                            "id": 4,
                            "data": "2026-05-01T12:00:00",
                            "enteAdministrativo": {"sigla": "SF"},
                        }
                    ]
                }
            ],
        }
    )
    assert result["events"][0]["body"] == "SF"
    assert result["events"][0]["final_outcome"] is None
    assert result["final_outcome"] is None
    with pytest.raises(IngestionError, match="PROCEEDING_SCHEMA_CHANGED"):
        list(legislative.process_events({"autuacoes": [{"informesLegislativos": [{}]}]}))


@pytest.mark.parametrize("payload", [None, {}, {"id": 1}])
def test_process_schema_does_not_accept_partial_identification(payload):
    with pytest.raises(IngestionError, match="PROCESS_SCHEMA_CHANGED"):
        legislative.normalize_process(payload)


def test_secret_voting_never_exports_individual_choices():
    row = {
        "codigoSessaoVotacao": 1,
        "dataSessao": "2026-05-01",
        "idProcesso": 2,
        "votacaoSecreta": "S",
        "votos": [{"choice": "yes"}],
    }
    assert legislative.normalize_voting(row)["nominal_vote_evidence"] == []
    with pytest.raises(IngestionError, match="SCHEMA_CHANGED"):
        legislative.normalize_voting(row | {"votacaoSecreta": "unknown"})


def test_unknown_legislative_domain_is_explicit_and_invalid_period_rejected():
    assert (
        legislative.legislative_capability("attendance", date(2026, 5, 1), date(2026, 5, 2))[
            "status"
        ]
        == "unsupported"
    )
    with pytest.raises(IngestionError, match="INVALID_LEGISLATIVE_INTERVAL"):
        legislative.validate_interval(date(2026, 5, 2), date(2026, 5, 1))


def identity_artifact(tmp_path, key="1", name="Pessoa Teste", url_key="1"):
    payload = {
        "DetalheParlamentar": {
            "Parlamentar": {
                "IdentificacaoParlamentar": {
                    "NomeCompletoParlamentar": name,
                    "CodigoParlamentar": key,
                },
                "DadosBasicosParlamentar": {"DataNascimento": "1980-01-01"},
            }
        }
    }
    path = tmp_path / f"profile-{key}-{url_key}.json"
    path.write_text(json.dumps(payload))
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    resource = Resource(
        "resource",
        "profile",
        f"https://legis.senado.leg.br/dadosabertos/senador/{url_key}.json",
        "profile",
        2026,
        "senado",
    )
    return DownloadedArtifact(resource, path, digest, "2026-05-01T12:00:00Z", path.stat().st_size)


def test_identity_artifact_hash_and_provider_subject_must_match(tmp_path):
    artifact = identity_artifact(tmp_path, url_key="2")
    with pytest.raises(IngestionError, match="PROFILE_KEY_MISMATCH"):
        voting_identity.profile_subject(artifact)
    artifact.path.write_text("{}")
    with pytest.raises(IngestionError, match="ARTIFACT_CHANGED"):
        voting_identity.profile_subject(artifact)


def test_identity_missing_name_does_not_issue_database_query(tmp_path):
    artifact = identity_artifact(tmp_path, name=None)
    assert voting_identity.resolve_profile_identities(None, [artifact]) == {}


@pytest.mark.parametrize("ambiguous", [True, False])
def test_identity_resolution_only_accepts_unique_name_and_birth(tmp_path, ambiguous):
    artifact = identity_artifact(tmp_path)
    rows = [
        {
            "person_id": "first",
            "normalized_name": normalize_person_name("Pessoa Teste"),
            "birth_date": date(1980, 1, 1),
        }
    ]
    if ambiguous:
        rows.append(rows[0] | {"person_id": "second"})
    connection = SimpleNamespace(execute=lambda *args: SimpleNamespace(fetchall=lambda: rows))
    result = voting_identity.resolve_profile_identities(connection, [artifact])
    assert result == ({} if ambiguous else {"1": ("first", artifact.sha256)})


def test_cached_profile_discovery_ignores_unrelated_urls_and_enforces_budget(tmp_path):
    directory = tmp_path / "manifests"
    directory.mkdir()
    save_json(
        directory / "unrelated.json",
        {"source_url": "https://attacker.invalid/dadosabertos/senador/1.json"},
    )
    save_json(
        directory / "valid.json",
        {
            "source_url": "https://legis.senado.leg.br/dadosabertos/senador/1.json",
            "fetched_at": "2026-05-01T00:00:00Z",
            "sha256": "a" * 64,
            "bytes": 20,
        },
    )
    artifacts = voting_identity.cached_identity_profiles(tmp_path)
    assert len(artifacts) == 1 and artifacts[0].acquisition_status == "cached"
    with pytest.raises(IngestionError, match="PROFILE_LIMIT_EXCEEDED"):
        voting_identity.cached_identity_profiles(tmp_path, maximum=0)


@pytest.mark.parametrize("maximum", [True, 0, 2])
def test_process_description_collection_only_allows_single_explicit_document(tmp_path, maximum):
    with pytest.raises(IngestionError, match="BUDGET_MUST_BE_ONE"):
        process_pipeline.collect_senate_process_details(None, tmp_path, [1], max_processes=maximum)


def test_process_description_requires_nonempty_registered_scope(tmp_path):
    with pytest.raises(IngestionError, match="SELECT_EXPLICIT_SENATE_PROCESS"):
        process_pipeline.collect_senate_process_details(None, tmp_path, [])
    connection = SimpleNamespace(execute=lambda *args: SimpleNamespace(fetchall=lambda: []))
    with pytest.raises(IngestionError, match="PROPOSITION_NOT_REGISTERED"):
        process_pipeline.known_processes(connection, [1])


def test_process_registration_must_match_observed_matter():
    process_pipeline.validate_registered_process(
        {"kind": "PL", "number": "1", "year": 2026}, {"kind": "PL", "number": 1, "year": None}
    )
    with pytest.raises(IngestionError, match="REGISTERED_PROPOSITION_MISMATCH"):
        process_pipeline.validate_registered_process({"kind": "PEC"}, {"kind": "PL"})


@dataclass
class Summary:
    new: int = 1


@pytest.mark.parametrize("description", [None, "Texto oficial resumido"])
def test_process_summary_missing_description_remains_visible_failure(monkeypatch, description):
    process = {"source_key": "1", "kind": "PL", "number": 1, "year": 2026}
    artifact = SimpleNamespace(sha256="a" * 64)
    monkeypatch.setattr(
        process_pipeline, "collect_process_details", lambda *args, **kwargs: [(process, artifact)]
    )
    monkeypatch.setattr(process_pipeline, "stage_process_summary", lambda *args: "staged")
    monkeypatch.setattr(
        process_pipeline, "process_summary_record", lambda _: {"summary": description}
    )
    repository = SimpleNamespace(ingest_validated_artifact=lambda *args: Summary())
    result = process_pipeline.ingest_process_summaries(
        None, SimpleNamespace(batch_size=10), None, repository, processes={"1": process}
    )
    assert result["artifacts"][0]["official_description_published"] is (description is not None)
    assert result["failures"] == (
        [] if description else [{"code": "SENATE_PROCESS_SUMMARY_NOT_PUBLISHED"}]
    )


def test_registered_process_collection_dispatches_only_known_explicit_scope(monkeypatch, tmp_path):
    row = {
        "official_key": process_pipeline.PROCESS_URL + "1",
        "kind": "PL",
        "number": 1,
        "year": 2026,
    }
    connection = SimpleNamespace(execute=lambda *args: SimpleNamespace(fetchall=lambda: [row]))
    monkeypatch.setattr(
        process_pipeline,
        "run_official_collection",
        lambda connection, config, definition, callback: {"scope": callback.keywords["processes"]},
    )
    assert process_pipeline.collect_senate_process_details(connection, tmp_path, [1])["scope"] == {
        "1": row
    }


def test_committee_invalid_timestamp_and_oversized_response_are_rejected():
    with pytest.raises(IngestionError, match="INVALID_COMMITTEE_MEETING_START"):
        committee.normalize_committee_voting(committee_row(DataHoraInicioReuniao="bad-date"))
    payload = {
        "VotacoesComissao": {
            "Metadados": {"VersaoServico": 1},
            "Votacoes": {"Votacao": [committee_row(), committee_row()]},
        }
    }
    acquisition = SimpleNamespace(json_document=lambda *args: (payload, None))
    with pytest.raises(IngestionError, match="RECORD_LIMIT_EXCEEDED"):
        committee.collect_committee_votings(
            acquisition, "CCJ", date(2026, 5, 1), date(2026, 5, 2), maximum=1
        )


def test_collect_process_details_deduplicates_http_and_yields_normalized_process():
    calls = []
    acquisition = SimpleNamespace(
        json_document=lambda path, kind: (
            calls.append(path) or ({"id": 1, "sigla": "PL"}, "artifact")
        )
    )
    result = list(legislative.collect_process_details(acquisition, [1, 1]))
    assert len(result) == 1
    assert result[0][0]["source_key"] == "1"
    assert calls == ["processo/1.json?v=1"]


def test_collect_votings_validates_payload_and_enforces_period_before_io():
    start, end = date(2026, 5, 1), date(2026, 5, 2)
    with pytest.raises(IngestionError, match="INTERVAL_LIMIT_EXCEEDED"):
        legislative.collect_votings(None, start, date(2026, 7, 1))
    acquisition = SimpleNamespace(json_document=lambda *args: ({}, None))
    with pytest.raises(IngestionError, match="SCHEMA_CHANGED"):
        legislative.collect_votings(acquisition, start, end)
    with pytest.raises(IngestionError, match="SCHEMA_CHANGED"):
        legislative.normalize_voting({})
    acquisition.json_document = lambda *args: (
        [
            {
                "codigoSessaoVotacao": 1,
                "dataSessao": "2026-05-01",
                "idProcesso": 2,
                "votacaoSecreta": "N",
                "votos": [],
            }
        ],
        "artifact",
    )
    rows, artifact = legislative.collect_votings(acquisition, start, end)
    assert artifact == "artifact"
    assert rows[0]["is_secret"] is False


def test_conflicting_profiles_cannot_assign_same_provider_key_to_different_people(tmp_path):
    first = identity_artifact(tmp_path, name="Pessoa Primeira")
    other_dir = tmp_path / "other"
    other_dir.mkdir()
    second = identity_artifact(other_dir, name="Pessoa Segunda")
    rows = [
        {
            "person_id": str(index),
            "normalized_name": normalize_person_name(name),
            "birth_date": date(1980, 1, 1),
        }
        for index, name in enumerate(["Pessoa Primeira", "Pessoa Segunda"])
    ]
    connection = SimpleNamespace(execute=lambda *args: SimpleNamespace(fetchall=lambda: rows))
    with pytest.raises(IngestionError, match="PROFILE_CONFLICT"):
        voting_identity.resolve_profile_identities(connection, [first, second])
