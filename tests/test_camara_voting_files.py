"""Anonymous official-contract fixtures; period files never write SQL voting facts."""

import json
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from crawlers.camara.acquisition import CamaraAcquisition
from crawlers.camara.configuration import API_BASE
from crawlers.camara.voting_acquisition import discover_votings
from crawlers.camara.voting_configuration import VotingConfiguration
from crawlers.camara.voting_normalization import normalize_individual_vote
from crawlers.camara.voting_pipeline import (
    collect_camara_source_files,
    normalize_camara_source_files,
)
from service.analytical_datasets.contracts import VOTE_COLUMNS, DatasetPartition
from service.analytical_datasets.public_voting_timeline import (
    MATTER_INPUT_COLUMNS,
    project_public_voting_timeline,
)
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from storage.files import hash_content, hash_file

DAY = date(2024, 5, 15)


def discovery_row(key="100-1"):
    return {
        "id": key,
        "uri": API_BASE + "votacoes/" + key,
        "data": str(DAY),
        "proposicaoObjeto": "PL 1/2024",
        "uriProposicaoObjeto": API_BASE + "proposicoes/100",
    }


def fixture_documents(*keys):
    documents = {
        "votacoes": {"dados": [discovery_row(key) for key in keys], "links": []},
        "proposicoes/100": {
            "dados": {
                "id": 100,
                "uri": API_BASE + "proposicoes/100",
                "siglaTipo": "PL",
                "numero": 1,
                "ano": 2024,
                "ementa": "Ementa oficial fictícia.",
            }
        },
        "deputados/1": {
            "dados": {
                "id": 1,
                "nomeCivil": "Pessoa Fictícia",
                "dataNascimento": "1980-01-01",
                "cpf": "12345678900",
            }
        },
    }
    for key in keys:
        documents["votacoes/" + key] = {
            "dados": discovery_row(key)
            | {"objetosPossiveis": [], "descUltimaAberturaVotacao": "Votação em primeiro turno"}
        }
        documents["votacoes/" + key + "/votos"] = {
            "dados": [
                {"deputado_": {"id": 1, "nome": "Nome parlamentar fictício"}, "tipoVoto": "Sim"}
            ],
            "links": [],
        }
    return documents


class FixtureAcquisition(CamaraAcquisition):
    def __init__(self, configuration, documents):
        super().__init__(configuration, None)
        self.documents, self.calls, self.artifacts = documents, [], []

    def json_document(self, path, kind):
        path = path.removeprefix(API_BASE)
        key = path.split("?")[0]
        self.calls.append(key)
        payload = self.documents[key]
        raw = json.dumps(payload, ensure_ascii=False).encode()
        directory = self.configuration.storage_directory
        directory.mkdir(exist_ok=True, parents=True)
        artifact_path = directory / (hash_content(payload) + ".json")
        artifact_path.write_bytes(raw)
        resource = Resource(
            "fixture-" + hash_content(path),
            kind,
            API_BASE + path,
            kind,
            2026,
            "fixture",
            file_suffix=".json",
        )
        artifact = DownloadedArtifact(
            resource, artifact_path, hash_file(artifact_path), "2026-10-17T12:00:00+00:00", len(raw)
        )
        self.artifacts.append(artifact)
        return payload, artifact


def identity_connection(person_ids=None):
    people = person_ids if person_ids is not None else [str(uuid4())]
    calls = []

    def execute(query, parameters):
        calls.append(query)
        assert "INSERT" not in query and "UPDATE" not in query and "DELETE" not in query
        return SimpleNamespace(
            fetchall=lambda: [
                {
                    "normalized_name": "pessoa ficticia",
                    "birth_date": "1980-01-01",
                    "person_ids": people,
                }
            ]
        )

    return SimpleNamespace(execute=execute), calls


def test_shared_discovery_two_events_one_profile_one_matter_and_one_identity_query(tmp_path):
    configuration = VotingConfiguration(tmp_path / "source", max_identity_profiles=1)
    acquisition = FixtureAcquisition(configuration, fixture_documents("100-1", "100-2"))
    connection, queries = identity_connection()
    result = normalize_camara_source_files(
        connection, acquisition, configuration, DAY, DAY, tmp_path / "daily.ndjson"
    )
    rows = [json.loads(line) for line in Path(result["input_path"]).read_text().splitlines()]
    assert len(rows) == 2 and len(queries) == 1
    assert acquisition.calls.count("votacoes") == 1
    assert acquisition.calls.count("deputados/1") == 1
    assert acquisition.calls.count("proposicoes/100") == 1
    assert {row["voting_id"] for row in rows} == {"camara:voting:100-1", "camara:voting:100-2"}
    assert all(
        set(row) == VOTE_COLUMNS | MATTER_INPUT_COLUMNS | {
            "source_observed_at", "matter_document_url", "matter_text_url"
        } for row in rows
    )
    projected = project_public_voting_timeline(
        {key: value for key, value in rows[0].items() if key != "source_observed_at"},
        DatasetPartition("camara", 2024),
    )
    assert projected["short_description"] == "Ementa oficial fictícia."
    assert result["sql_vote_writes"] == 0 and result["explicit_secret_votings"] == []
    text = Path(result["input_path"]).read_text()
    assert "12345678900" not in text and "nomeCivil" not in text and "deputado_" not in text
    assert all(hash_file(artifact.path) == artifact.sha256 for artifact in acquisition.artifacts)


def test_unresolved_or_ambiguous_people_are_not_assigned_by_parliamentary_name(tmp_path):
    configuration = VotingConfiguration(tmp_path / "source", max_identity_profiles=1)
    acquisition = FixtureAcquisition(configuration, fixture_documents("100-1"))
    connection, _ = identity_connection([str(uuid4()), str(uuid4())])
    result = normalize_camara_source_files(
        connection, acquisition, configuration, DAY, DAY, tmp_path / "daily.ndjson"
    )
    assert result["rows"] == 0 and result["identity_unresolved"] == 1
    assert Path(result["input_path"]).read_text() == ""


def test_zero_profile_budget_does_not_fetch_each_voter_or_invent_absence(tmp_path):
    configuration = VotingConfiguration(tmp_path / "source")
    acquisition = FixtureAcquisition(configuration, fixture_documents("100-1"))
    result = normalize_camara_source_files(
        None, acquisition, configuration, DAY, DAY, tmp_path / "daily.ndjson"
    )
    assert "deputados/1" not in acquisition.calls
    assert result["identity_unresolved"] == 1 and result["rows"] == 0


def test_symbolic_response_with_no_votes_is_not_a_secret_retirement(tmp_path):
    configuration = VotingConfiguration(tmp_path / "source")
    documents = fixture_documents("100-1")
    documents["votacoes/100-1/votos"]["dados"] = []
    acquisition = FixtureAcquisition(configuration, documents)
    result = normalize_camara_source_files(
        None, acquisition, configuration, DAY, DAY, tmp_path / "daily.ndjson"
    )
    assert result["rows"] == 0 and result["explicit_secret_votings"] == []
    assert not result["collection_complete"]


def test_event_budget_stops_before_extra_event_requests_and_reports_partial(tmp_path):
    configuration = VotingConfiguration(tmp_path / "source", max_votings=1)
    acquisition = FixtureAcquisition(configuration, fixture_documents("100-1", "100-2"))
    result = normalize_camara_source_files(
        None, acquisition, configuration, DAY, DAY, tmp_path / "daily.ndjson"
    )
    assert "votacoes/100-2" not in acquisition.calls
    assert result["discovery_complete"] is False and result["votings"] == 1


def test_discovery_deduplicates_and_rejects_conflicting_source_rows(tmp_path):
    configuration = VotingConfiguration(tmp_path)
    documents = fixture_documents("100-1", "100-1")
    acquisition = FixtureAcquisition(configuration, documents)
    rows, _, complete = discover_votings(acquisition, DAY, DAY, 10)
    assert len(rows) == 1 and complete
    documents["votacoes"]["dados"][1]["data"] = "2024-05-14"
    with pytest.raises(IngestionError, match="OUTSIDE_PARTITION"):
        discover_votings(acquisition, DAY, DAY, 10)


def test_unknown_vote_codes_do_not_become_no_and_art17_preserves_presiding():
    assert normalize_individual_vote({"tipoVoto": "Art. 17"}) == {
        "vote_choice": None,
        "participation_status": "presiding",
    }
    assert normalize_individual_vote({"tipoVoto": "Favorável com restrições"}) == {
        "vote_choice": None,
        "participation_status": "unknown",
    }
    assert normalize_individual_vote({"tipoVoto": "Não"})["vote_choice"] == "no"


def test_invalid_scope_fails_before_database_or_http(tmp_path):
    with pytest.raises(IngestionError, match="INTERVAL"):
        collect_camara_source_files(
            None, tmp_path, date(2024, 12, 31), date(2025, 1, 1), tmp_path / "daily.ndjson"
        )
    with pytest.raises(IngestionError, match="BUDGET"):
        collect_camara_source_files(
            None, tmp_path, DAY, DAY, tmp_path / "daily.ndjson", max_identity_profile_downloads=101
        )
