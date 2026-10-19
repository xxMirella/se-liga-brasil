"""Identity invariants independent of electoral identifiers; isolated database only."""

import pytest
from test_database_integration import start_repository

from crawlers.tse.validator import validate_resource
from storage.validation_index import ValidationIndex

pytestmark = pytest.mark.integration


def test_changed_source_identifier_keeps_same_person(
    integration_database, configuration, archive_factory, candidate_row
):
    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "identity.sqlite")
    try:
        for sequence in ("111", "222"):
            artifact = validate_resource(
                archive_factory("candidate", [candidate_row | {"SQ_CANDIDATO": sequence}]),
                configuration,
                index,
            )
            assert repository.ingest_validated_artifact(artifact, 500).rejected == 0
        counts = integration_database.execute("""
            SELECT (SELECT count(*) FROM se_liga_brasil.person) AS people,
             (SELECT count(*) FROM se_liga_brasil.person_identifier) AS source_identifiers,
             (SELECT count(DISTINCT person_id) FROM se_liga_brasil.electoral_candidacy) AS owners
        """).fetchone()
        assert counts == {"people": 1, "source_identifiers": 0, "owners": 1}
        person = integration_database.execute(
            "SELECT id,slug FROM se_liga_brasil.person"
        ).fetchone()
        assert person["slug"] == f"person-{person['id']}"
    finally:
        index.close()
        repository.finish_run("completed", {})


def test_missing_personal_evidence_creates_review_not_person(
    integration_database, configuration, archive_factory, candidate_row
):
    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "missing.sqlite")
    try:
        row = candidate_row | {"DT_NASCIMENTO": "#NULO", "NR_CPF_CANDIDATO": "#NULO"}
        artifact = validate_resource(archive_factory("candidate", [row]), configuration, index)
        assert repository.ingest_validated_artifact(artifact, 500).rejected == 1
        assert (
            integration_database.execute(
                "SELECT count(*) AS total FROM se_liga_brasil.person"
            ).fetchone()["total"]
            == 0
        )
        assert (
            integration_database.execute(
                "SELECT reason_code FROM se_liga_brasil.person_identity_review"
            ).fetchone()["reason_code"]
            == "PERSON_IDENTITY_INSUFFICIENT"
        )
    finally:
        index.close()
        repository.finish_run("partial", {})


def test_mixed_document_availability_in_same_batch_keeps_one_person(
    integration_database, configuration, archive_factory, candidate_row
):
    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "mixed.sqlite")
    try:
        rows = [
            candidate_row | {"SQ_CANDIDATO": "111", "NR_CPF_CANDIDATO": "52998224725"},
            candidate_row | {"SQ_CANDIDATO": "222", "NR_CPF_CANDIDATO": "#NULO"},
        ]
        artifact = validate_resource(archive_factory("candidate", rows), configuration, index)
        assert repository.ingest_validated_artifact(artifact, 500).rejected == 0
        assert (
            integration_database.execute(
                "SELECT count(*) AS people FROM se_liga_brasil.person"
            ).fetchone()["people"]
            == 1
        )
    finally:
        index.close()
        repository.finish_run("completed", {})


def test_conflicting_documents_preserve_homonyms_and_block_ambiguous_name(
    integration_database, configuration, archive_factory, candidate_row
):
    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "homonyms.sqlite")
    try:
        rows = [
            candidate_row | {"SQ_CANDIDATO": "111", "NR_CPF_CANDIDATO": "52998224725"},
            candidate_row | {"SQ_CANDIDATO": "222", "NR_CPF_CANDIDATO": "11144477735"},
            candidate_row | {"SQ_CANDIDATO": "333", "NR_CPF_CANDIDATO": "#NULO"},
        ]
        artifact = validate_resource(archive_factory("candidate", rows), configuration, index)
        assert repository.ingest_validated_artifact(artifact, 500).rejected == 1
        assert (
            integration_database.execute(
                "SELECT count(*) AS people FROM se_liga_brasil.person"
            ).fetchone()["people"]
            == 2
        )
        assert (
            integration_database.execute(
                "SELECT reason_code FROM se_liga_brasil.person_identity_review"
            ).fetchone()["reason_code"]
            == "PERSON_IDENTITY_AMBIGUOUS"
        )
    finally:
        index.close()
        repository.finish_run("partial", {})


def test_party_evidence_persistence_is_idempotent(
    integration_database, configuration, archive_factory, candidate_row
):
    from database.political_party_verification import persist_party_evidence

    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "party-evidence.sqlite")
    try:
        artifact = validate_resource(
            archive_factory("candidate", [candidate_row]), configuration, index
        )
        repository.ingest_validated_artifact(artifact, 500)
        person = integration_database.execute("SELECT id FROM se_liga_brasil.person").fetchone()
        report = {
            "person_id": str(person["id"]),
            "political_party_code": "13",
            "starts_on": "2020-01-01",
            "reported_end_date": None,
            "source_url": "https://www.al.sp.gov.br/official-test",
        }
        for _ in range(2):
            persist_party_evidence(
                integration_database,
                repository.source_id,
                "https://www.al.sp.gov.br/",
                [report],
                "political_party_affiliation_report",
            )
        assert (
            integration_database.execute(
                "SELECT count(*) AS total FROM se_liga_brasil.person_fact "
                "WHERE field_name='political_party_affiliation_report'"
            ).fetchone()["total"]
            == 1
        )
    finally:
        index.close()
        repository.finish_run("completed", {})


def test_migration_removes_source_identity_and_preserves_internal_links(
    integration_database, configuration, archive_factory, candidate_row
):
    from database.operations import apply_internal_identity_schema

    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "migration.sqlite")
    try:
        artifact = validate_resource(
            archive_factory("candidate", [candidate_row]), configuration, index
        )
        repository.ingest_validated_artifact(artifact, 500)
        person = integration_database.execute("SELECT * FROM se_liga_brasil.person").fetchone()
        integration_database.execute(
            "ALTER TABLE se_liga_brasil.person_identifier "
            "DROP CONSTRAINT person_identifier_no_electoral_identity"
        )
        integration_database.execute(
            "INSERT INTO se_liga_brasil.person_identifier "
            "VALUES(%s,'candidate:2026','source-id',%s,%s)",
            (repository.source_id, person["id"], person["primary_record_id"]),
        )
        integration_database.execute("UPDATE se_liga_brasil.person SET slug='tse-legacy'")
        assert apply_internal_identity_schema(integration_database)
        assert not apply_internal_identity_schema(integration_database)
        assert (
            integration_database.execute(
                "SELECT person_id FROM se_liga_brasil.electoral_candidacy"
            ).fetchone()["person_id"]
            == person["id"]
        )
        assert (
            integration_database.execute(
                "SELECT count(*) AS total FROM se_liga_brasil.person_identifier"
            ).fetchone()["total"]
            == 0
        )
    finally:
        index.close()
        repository.finish_run("completed", {})
