import pytest
from test_database_integration import start_repository

from crawlers.tse.validator import validate_resource
from database.operations import refresh_person_profiles
from storage.validation_index import ValidationIndex

pytestmark = pytest.mark.integration


def test_same_document_reuses_person_and_party_changes_keep_dated_snapshots(
    integration_database, configuration, archive_factory, candidate_row
):
    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "identity.sqlite")
    try:
        row = candidate_row | {"NR_CPF_CANDIDATO": "52998224725"}
        first = validate_resource(archive_factory("candidate", [row]), configuration, index)
        repository.ingest_validated_artifact(first, 500)
        changed = row | {
            "SQ_CANDIDATO": "222",
            "DT_GERACAO": "06/10/2026",
            "NR_PARTIDO": "98",
            "NM_PARTIDO": "Novo Partido",
            "SG_PARTIDO": "NOVO",
        }
        second = validate_resource(archive_factory("candidate", [changed]), configuration, index)
        repository.ingest_validated_artifact(second, 500)
        old = row | {
            "ANO_ELEICAO": "2022",
            "DT_NASCIMENTO": "11/05/1980",
            "SQ_CANDIDATO": "333",
            "DT_GERACAO": "07/10/2026",
            "NR_PARTIDO": "97",
            "NM_PARTIDO": "Partido Antigo",
            "SG_PARTIDO": "ANTIGO",
        }
        historical = validate_resource(
            archive_factory("candidate", [old], dataset_year=2022), configuration, index
        )
        assert repository.ingest_validated_artifact(historical, 500).rejected == 0
        assert_birth_date_review(integration_database)
        assert repository.ingest_validated_artifact(second, 500).skipped_artifact
        refresh_person_profiles(integration_database)
        counts = integration_database.execute("""
            SELECT count(*) AS people FROM se_liga_brasil.person
        """).fetchone()
        assert counts["people"] == 1
        party = integration_database.execute("""
            SELECT party.code FROM se_liga_brasil.person_profile profile
            JOIN se_liga_brasil.political_party party
            ON party.id=profile.last_observed_political_party_id
        """).fetchone()
        assert party["code"] == "98"
        affiliations = integration_database.execute("""
            SELECT election_context_year,information_valid_until,valid_from
            FROM se_liga_brasil.political_party_affiliation
            ORDER BY election_context_year DESC,information_valid_from
        """).fetchall()
        assert len(affiliations) == 3
        assert affiliations[0]["information_valid_until"] is not None
        assert all(affiliation["valid_from"] is None for affiliation in affiliations)
        contexts = integration_database.execute("""
            SELECT count(*) AS contexts FROM se_liga_brasil.person_activity_context
            WHERE political_party_id IS NOT NULL
        """).fetchone()
        assert contexts["contexts"] == 3
    finally:
        index.close()
        repository.finish_run("completed", {})


def test_unique_personal_evidence_reuses_person_without_source_identifier(
    integration_database, configuration, archive_factory, candidate_row
):
    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "homonym.sqlite")
    try:
        first = validate_resource(
            archive_factory("candidate", [candidate_row]), configuration, index
        )
        repository.ingest_validated_artifact(first, 500)
        duplicate_name = candidate_row | {"SQ_CANDIDATO": "222"}
        second = validate_resource(
            archive_factory("candidate", [duplicate_name]), configuration, index
        )
        repository.ingest_validated_artifact(second, 500)
        people = integration_database.execute(
            "SELECT count(*) AS people FROM se_liga_brasil.person"
        ).fetchone()
        assert people["people"] == 1
        reviews = integration_database.execute("""
            SELECT count(*) AS reviews FROM se_liga_brasil.person_identity_review
            WHERE reason_code='NAME_PARTY_MATCH_REQUIRES_REVIEW'
        """).fetchone()
        assert reviews["reviews"] == 0
    finally:
        index.close()
        repository.finish_run("completed", {})


def test_history_uses_personal_evidence_and_blocks_ambiguous_homonyms(
    integration_database, configuration, archive_factory, candidate_row
):
    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "history-identities.sqlite")
    try:
        older = candidate_row | {"ANO_ELEICAO": "2022", "SQ_CANDIDATO": "222"}
        rows = validate_resource(
            archive_factory("candidate", [older], dataset_year=2022), configuration, index
        )
        repository.ingest_validated_artifact(rows, 500)
        current = candidate_row | {"NR_CPF_CANDIDATO": "52998224725"}
        rows = validate_resource(archive_factory("candidate", [current]), configuration, index)
        repository.ingest_validated_artifact(rows, 500)
        history_row = older | {
            "ANO_ELEICAO_ATUAL": "2026",
            "SQ_CANDIDATO_ATUAL": candidate_row["SQ_CANDIDATO"],
            "SG_UF_ATUAL": "PA",
        }
        history = validate_resource(archive_factory("history", [history_row]), configuration, index)
        assert repository.ingest_validated_artifact(history, 500).rejected == 0
        count = integration_database.execute("""
            SELECT count(DISTINCT person_id) AS people FROM se_liga_brasil.electoral_candidacy
        """).fetchone()
        assert count["people"] == 1
        other = candidate_row | {"SQ_CANDIDATO": "333", "NR_CPF_CANDIDATO": "11144477735"}
        rows = validate_resource(archive_factory("candidate", [other]), configuration, index)
        repository.ingest_validated_artifact(rows, 500)
        conflict = history_row | {"SQ_CANDIDATO_ATUAL": "333", "DT_GERACAO": "06/10/2026"}
        rows = validate_resource(archive_factory("history", [conflict]), configuration, index)
        assert repository.ingest_validated_artifact(rows, 500).rejected == 1
        reasons = list(repository.iter_resource_rejections(rows.artifact.resource.resource_id))
        assert reasons[0]["reason_code"] == "PERSON_IDENTITY_AMBIGUOUS"
    finally:
        index.close()
        repository.finish_run("completed", {})


def assert_birth_date_review(connection):
    assert (
        connection.execute(
            "SELECT count(*) AS total FROM se_liga_brasil.person_identity_review "
            "WHERE reason_code='BIRTH_DATE_DISAGREEMENT_SAME_DOCUMENT'"
        ).fetchone()["total"]
        == 1
    )
