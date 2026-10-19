"""Fictitious Senate profile projection, isolated schema and rollback only."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from test_database_integration import start_repository

from crawlers.senado.configuration import PARSER_VERSION, SOURCE, SenateConfiguration
from crawlers.senado.projection import SenateProjectionWriter
from crawlers.senado.staging import stage_records
from crawlers.tse.validator import validate_resource
from service.ingestion.contracts import DownloadedArtifact, Resource
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from storage.files import hash_file
from storage.validation_index import ValidationIndex

pytestmark = pytest.mark.integration


def create_test_person(
    integration_database, tmp_path, configuration, archive_factory, candidate_row
):
    connection = integration_database
    tse = start_repository(connection)
    index = ValidationIndex(tmp_path / "identity.sqlite")
    try:
        validated = validate_resource(
            archive_factory("candidate", [candidate_row]), configuration, index
        )
        tse.ingest_validated_artifact(validated, 500)
    finally:
        index.close()
        tse.finish_run("completed", {})
    return str(connection.execute("SELECT id FROM se_liga_brasil.person").fetchone()["id"])


def create_profile_artifact(tmp_path, person_id):
    path = tmp_path / "profile.json"
    path.write_text("{}")
    resource = Resource(
        "fictional-profile",
        "senado_profile",
        "https://legis.senado.leg.br/dadosabertos/senador/example.json",
        "senado-profile",
        2026,
        "senado-test",
        file_suffix=".json",
    )
    artifact = DownloadedArtifact(
        resource, path, hash_file(path), datetime.now(UTC).isoformat(), path.stat().st_size
    )
    data = {
        "personId": person_id,
        "politicalPartyAbbreviation": "TESTE",
        "representedUf": "SP",
        "legislatureKey": "57-58",
        "termStart": "2023-02-01",
        "termEndExclusive": "2031-02-01",
        "exerciseStartsOn": "2023-02-01",
        "exerciseEndExclusive": "2026-10-31",
        "capacity": "holder",
        "inExercise": True,
        "observedOn": datetime.now(UTC).date().isoformat(),
        "officeKind": "senator",
        "institutionCode": "senado",
    }
    return artifact, data


def test_senate_profile_updates_canonical_office_and_is_idempotent(
    integration_database, tmp_path, configuration, archive_factory, candidate_row
):
    connection = integration_database
    person_id = create_test_person(
        connection, tmp_path, configuration, archive_factory, candidate_row
    )
    artifact, data = create_profile_artifact(tmp_path, person_id)
    repository = IngestionRepository(
        connection,
        SOURCE,
        SenateProjectionWriter(SqlBatchWriter(connection)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"test": True})
    try:
        validated = stage_records(artifact, SenateConfiguration(tmp_path), [data])
        assert repository.ingest_validated_artifact(validated, 500).rejected == 0
        assert repository.ingest_validated_artifact(validated, 500).skipped_artifact
        row = connection.execute(
            """SELECT has_current_public_office,current_public_office_kind
            FROM se_liga_brasil.person WHERE id=%s""",
            (person_id,),
        ).fetchone()
        assert (
            str(
                connection.execute(
                    "SELECT ends_before FROM se_liga_brasil.office_exercise"
                ).fetchone()["ends_before"]
            )
            == "2026-10-31"
        )
        assert row == {"has_current_public_office": True, "current_public_office_kind": "senator"}
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM se_liga_brasil.office_exercise"
            ).fetchone()["n"]
            == 1
        )
        assert (
            connection.execute(
                "SELECT count(*) AS n FROM se_liga_brasil.political_party_affiliation "
                "WHERE information_scope='institution:senado'"
            ).fetchone()["n"]
            == 1
        )
    finally:
        repository.finish_run("completed", {})
