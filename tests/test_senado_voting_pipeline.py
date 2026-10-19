"""Anonymous contracts and rollback-only SQL for nominal voting history."""

import json
from datetime import date
from uuid import uuid4

import pytest

from crawlers.senado.configuration import SOURCE, SenateConfiguration
from crawlers.senado.legislative_voting import normalize_voting_record, resolve_voting_individuals
from crawlers.senado.voting_pipeline import monthly_partitions, select_unique_votings
from crawlers.senado.voting_staging import (
    PARSER_VERSION,
    SenateVotingProjection,
    stage_voting_records,
)
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from storage.files import hash_file


def voting_row(key=1, **changes):
    return {
        "codigoSessaoVotacao": key,
        "dataSessao": "2026-10-14",
        "idProcesso": 2,
        "votacaoSecreta": "N",
        "descricaoVotacao": "Votação em primeiro turno",
        "sigla": "PEC",
        "numero": "1",
        "ano": 2026,
        "votos": [
            {
                "codigoParlamentar": "123",
                "nomeParlamentar": "Pessoa Teste",
                "siglaVotoParlamentar": "Sim",
            }
        ],
    } | changes


def test_nominal_choice_is_distinct_from_absence_and_presiding():
    rows = [voting_row(), voting_row(2, descricaoVotacao="Votação em segundo turno")]
    assert [normalize_voting_record(row)["round_number"] for row in rows] == [1, 2]
    resolved, missing = resolve_voting_individuals(rows, {"123": (str(uuid4()), "a" * 64)})
    assert len(resolved) == 2 and missing == 0
    assert all("codigoParlamentar" not in json.dumps(row) for row in resolved)
    assert normalize_voting_record(voting_row(votacaoSecreta="S"))["nominal_votes"] == []


def test_partition_budget_and_snapshot_conflict_fail_before_extra_requests():
    with pytest.raises(IngestionError, match="PARTITION_LIMIT"):
        monthly_partitions(date(2026, 1, 1), date(2026, 3, 1), maximum=1)
    seen = {}
    bounds = date(2026, 10, 1), date(2026, 10, 31)
    assert len(select_unique_votings([voting_row(), voting_row()], seen, *bounds, 1)) == 1
    with pytest.raises(IngestionError, match="SNAPSHOT_CONFLICT"):
        select_unique_votings([voting_row(descricaoVotacao="Retificado")], seen, *bounds, 1)


def ingest_votes(repository, tmp_path, rows, identity, timestamp):
    path = tmp_path / (uuid4().hex + ".json")
    path.write_text(json.dumps(rows))
    resource = Resource(
        "voting-partition",
        "votes",
        "https://legis.senado.leg.br/dadosabertos/votacao.json",
        "senado_votings",
        2026,
        "test",
        file_suffix=".json",
    )
    artifact = DownloadedArtifact(resource, path, hash_file(path), timestamp, path.stat().st_size)
    records = [normalize_voting_record(row) for row in rows]
    votes, _ = resolve_voting_individuals(rows, identity)
    staged = stage_voting_records(artifact, SenateConfiguration(tmp_path), records, votes)
    return repository.ingest_validated_artifact(staged, 500), staged


@pytest.mark.integration
def test_sql_two_turns_replay_revision_and_secret_correction(integration_database, tmp_path):
    connection, person = integration_database, str(uuid4())
    seed_voting_person(connection, person)

    repository = IngestionRepository(
        connection,
        SOURCE,
        SenateVotingProjection(SqlBatchWriter(connection)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"test": True})
    identity = {"123": (person, "a" * 64)}
    try:
        rows = [voting_row(), voting_row(2, descricaoVotacao="Votação em segundo turno")]
        _, staged = ingest_votes(repository, tmp_path, rows, identity, "2026-10-17T12:00:00+00:00")
        assert repository.ingest_validated_artifact(staged, 500).skipped_artifact
        assert (
            connection.execute("SELECT count(*) AS n FROM se_liga_brasil.voting").fetchone()["n"]
            == 2
        )
        assert (
            connection.execute("SELECT count(*) AS n FROM se_liga_brasil.person_vote").fetchone()[
                "n"
            ]
            == 2
        )
        changed = voting_row(votos=[{"codigoParlamentar": "123", "siglaVotoParlamentar": "Não"}])
        ingest_votes(repository, tmp_path, [changed], identity, "2026-10-18T12:00:00+00:00")
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM se_liga_brasil.person_vote_revision"
            ).fetchone()["n"]
            == 3
        )
        ingest_votes(
            repository,
            tmp_path,
            [voting_row(votacaoSecreta="S")],
            identity,
            "2026-10-19T12:00:00+00:00",
        )
        assert (
            connection.execute("SELECT count(*) AS n FROM se_liga_brasil.person_vote").fetchone()[
                "n"
            ]
            == 1
        )
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM se_liga_brasil.voting "
                "WHERE held_at IS NULL AND held_on IS NOT NULL"
            ).fetchone()["n"]
            == 2
        )
    finally:
        repository.finish_run("completed", {})


def seed_voting_person(connection, person):
    connection.execute(
        "INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method) "
        "VALUES('fixture','Fixture','https://example.invalid','api')"
    )
    connection.execute(
        "INSERT INTO se_liga_brasil.source_record"
        "(source_id,external_key,source_url,content_sha256,payload) "
        "SELECT id,'fixture','https://example.invalid',repeat('a',64),'{}' "
        "FROM se_liga_brasil.source WHERE code='fixture'"
    )
    connection.execute(
        "INSERT INTO se_liga_brasil.person"
        "(id,slug,civil_name,display_name,primary_record_id) "
        "SELECT %s,%s,'Pessoa Teste','Teste',id "
        "FROM se_liga_brasil.source_record WHERE external_key='fixture'",
        (person, str(person)),
    )
