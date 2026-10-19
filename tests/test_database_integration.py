from uuid import uuid4

import pytest

from crawlers.tse.configuration import TSE_SOURCE
from crawlers.tse.projection import TseProjectionWriter
from crawlers.tse.validator import validate_resource
from database.operations import read_sql_file, refresh_person_profiles, strip_transaction_wrapper
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from storage.validation_index import ValidationIndex

pytestmark = pytest.mark.integration


def start_repository(database):
    repository = IngestionRepository(
        database, TSE_SOURCE, TseProjectionWriter(SqlBatchWriter(database))
    )
    repository.begin_run(str(uuid4()), {"test": True})
    return repository


def test_batch_progress_and_profiles_are_updated_before_whole_run_finishes(
    integration_database, configuration, archive_factory, candidate_row
):
    repository = start_repository(integration_database)
    events = []
    repository.progress = lambda phase, **details: events.append((phase, details))
    index = ValidationIndex(configuration.storage_directory.parent / "index.sqlite")
    try:
        rows = [
            candidate_row | {"SQ_CANDIDATO": str(number), "NM_CANDIDATO": f"Pessoa {number}"}
            for number in range(3)
        ]
        validated = validate_resource(archive_factory("candidate", rows), configuration, index)
        repository.ingest_validated_artifact(validated, 2)
        assert [details["processed_records"] for phase, details in events] == [2, 3]
        refresh_person_profiles(integration_database)
        profiles = integration_database.execute(
            "SELECT count(*) AS total FROM se_liga_brasil.person_profile"
        ).fetchone()["total"]
        assert profiles == 3
    finally:
        index.close()
        repository.finish_run("completed", {})


def test_database_rejection_report_preserves_code_file_and_line(
    integration_database, configuration, archive_factory, candidate_row
):
    index = ValidationIndex(configuration.storage_directory.parent / "index.sqlite")
    repository = start_repository(integration_database)
    try:
        artifact = archive_factory("candidate", [candidate_row | {"DT_NASCIMENTO": "31/02/2000"}])
        validated = validate_resource(artifact, configuration, index)
        summary = repository.ingest_validated_artifact(validated, 500)
        rejections = list(repository.iter_resource_rejections(artifact.resource.resource_id))
        assert summary.rejected == 1
        assert len(rejections) == 1
        assert rejections[0]["reason_code"] == "INVALID_DATE"
        assert rejections[0]["row_number"] == 2
        assert rejections[0]["entry_name"].endswith(".csv")
    finally:
        index.close()
        repository.finish_run("partial", {})


def test_reingestion_is_idempotent_and_changes_preserve_versions(
    integration_database, configuration, archive_factory, candidate_row
):
    index = ValidationIndex(configuration.storage_directory.parent / "index.sqlite")
    repository = start_repository(integration_database)
    try:
        validated = validate_resource(
            archive_factory("candidate", [candidate_row]), configuration, index
        )
        assert repository.ingest_validated_artifact(validated, 500).new == 1
        assert repository.ingest_validated_artifact(validated, 500).skipped_artifact
        changed = candidate_row | {
            "DT_GERACAO": "06/10/2026",
            "NM_URNA_CANDIDATO": "Pessoa Atualizada",
        }
        changed_artifact = validate_resource(
            archive_factory("candidate", [changed]), configuration, index
        )
        assert repository.ingest_validated_artifact(changed_artifact, 500).changed == 1
        counts = integration_database.execute("""
            SELECT (SELECT count(*) FROM se_liga_brasil.person) AS people,
              (SELECT count(*) FROM se_liga_brasil.ingestion_entity_version) AS versions
        """).fetchone()
        assert counts == {"people": 1, "versions": 2}
        name = integration_database.execute(
            "SELECT display_name FROM se_liga_brasil.person"
        ).fetchone()
        assert name["display_name"] == "Pessoa Atualizada"
        repository.finish_run("completed", {})
    finally:
        index.close()


def test_stale_snapshot_cannot_overwrite_current_profile(
    integration_database, configuration, archive_factory, candidate_row
):
    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "index.sqlite")
    try:
        current = candidate_row | {"DT_GERACAO": "06/10/2026"}
        validated = validate_resource(archive_factory("candidate", [current]), configuration, index)
        repository.ingest_validated_artifact(validated, 500)
        stale = candidate_row | {"NM_URNA_CANDIDATO": "Nome Antigo"}
        validated = validate_resource(archive_factory("candidate", [stale]), configuration, index)
        assert repository.ingest_validated_artifact(validated, 500).stale == 1
        assert (
            integration_database.execute(
                "SELECT display_name FROM se_liga_brasil.person"
            ).fetchone()["display_name"]
            == "Pessoa Teste"
        )
        repository.finish_run("completed", {})
    finally:
        index.close()


def test_initial_schema_behavior_checks_still_pass(integration_database):
    from database.operations import apply_ingestion_schema, verify_schema

    sql = read_sql_file("tests.sql")
    sql = sql.removesuffix("\n").removesuffix("ROLLBACK;")
    sql = strip_transaction_wrapper(sql)
    # The original suite asserts 23 RLS tables; extensions in this test schema total 46.
    sql = sql.replace("<> 23", "<> 46")
    integration_database.execute(sql)
    assert apply_ingestion_schema(integration_database) is False
    assert verify_schema(integration_database)["tables"] == 46


def test_assets_and_generic_existence_keep_source_provenance(
    integration_database, configuration, archive_factory, candidate_row
):
    from decimal import Decimal

    from database.record_lookup import PostgresRecordLookup
    from service.data_validation import DataExistenceService, RecordIdentity

    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "index.sqlite")
    try:
        candidate = validate_resource(
            archive_factory("candidate", [candidate_row]), configuration, index
        )
        repository.ingest_validated_artifact(candidate, 500)
        asset_row = candidate_row | {
            "NR_ORDEM_BEM_CANDIDATO": "1",
            "CD_TIPO_BEM_CANDIDATO": "1",
            "DS_BEM_CANDIDATO": "Bem fictício",
            "VR_BEM_CANDIDATO": "1.234,56",
        }
        assets = validate_resource(archive_factory("asset", [asset_row]), configuration, index)
        assert repository.ingest_validated_artifact(assets, 500).rejected == 0
        stored = integration_database.execute("""
            SELECT asset.declared_value,record.source_url,record.fetched_at,asset.ingested_at
            FROM se_liga_brasil.candidate_asset_declaration asset
            JOIN se_liga_brasil.source_record record ON record.id=asset.source_record_id
        """).fetchone()
        assert stored["declared_value"] == Decimal("1234.56")
        assert stored["source_url"].startswith("https://cdn.tse.jus.br")
        assert stored["fetched_at"] and stored["ingested_at"]
        checker = DataExistenceService(PostgresRecordLookup(integration_database))
        assert checker.exists(RecordIdentity("tse", "asset", "2026:1:10000000001:1"))
        assert not checker.exists(RecordIdentity("tse", "law", "2026:1:10000000001:1"))
        repository.finish_run("completed", {})
    finally:
        index.close()


def test_history_links_years_using_personal_evidence(
    integration_database, configuration, archive_factory, candidate_row
):
    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "index.sqlite")
    try:
        current = validate_resource(
            archive_factory("candidate", [candidate_row]), configuration, index
        )
        repository.ingest_validated_artifact(current, 500)
        history_row = candidate_row | {
            "ANO_ELEICAO_ATUAL": "2026",
            "SQ_CANDIDATO_ATUAL": candidate_row["SQ_CANDIDATO"],
            "SG_UF_ATUAL": "PA",
            "ANO_ELEICAO": "2022",
            "SQ_CANDIDATO": "222222",
            "NM_CANDIDATO": candidate_row["NM_CANDIDATO"],
        }
        history = validate_resource(archive_factory("history", [history_row]), configuration, index)
        assert repository.ingest_validated_artifact(history, 500).rejected == 0
        counts = integration_database.execute("""
            SELECT count(*)::int AS candidacies,count(DISTINCT person_id)::int AS people
            FROM se_liga_brasil.electoral_candidacy
        """).fetchone()
        assert counts == {"candidacies": 2, "people": 1}
        repository.finish_run("completed", {})
    finally:
        index.close()


def test_missing_candidate_logs_name_key_and_both_source_lines(
    integration_database, configuration, archive_factory, candidate_row
):
    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "diagnostic.sqlite")
    try:
        validate_resource(archive_factory("candidate", [candidate_row]), configuration, index)
        row = candidate_row | {
            "NR_ORDEM_BEM_CANDIDATO": "1",
            "CD_TIPO_BEM_CANDIDATO": "1",
            "DS_BEM_CANDIDATO": "Bem fictício",
            "VR_BEM_CANDIDATO": "123,45",
        }
        row.pop("NM_CANDIDATO")
        artifact = validate_resource(archive_factory("asset", [row]), configuration, index)
        summary = repository.ingest_validated_artifact(artifact, 500)
        assert summary.new == 0
        assert summary.rejected == 1
        rejection = next(
            repository.iter_resource_rejections(artifact.artifact.resource.resource_id)
        )
        assert rejection["row_number"] == 2
        assert rejection["reason_code"] == "CANDIDATE_IDENTITY_NOT_FOUND"
        context = rejection["details"]
        assert context["candidate_name"] == candidate_row["NM_CANDIDATO"]
        assert context["lookup_external_id"] == candidate_row["SQ_CANDIDATO"]
        assert context["candidate_source"]["row_number"] == 2
        assert context["candidate_source"]["entry_name"] != rejection["entry_name"]
        assert "NR_CPF_CANDIDATO" not in str(context)
    finally:
        index.close()
        repository.finish_run("completed", {})


def test_negative_official_asset_is_preserved_for_review(
    integration_database, configuration, archive_factory, candidate_row
):
    from decimal import Decimal

    repository = start_repository(integration_database)
    index = ValidationIndex(configuration.storage_directory.parent / "negative-asset.sqlite")
    try:
        candidate = validate_resource(
            archive_factory("candidate", [candidate_row]), configuration, index
        )
        repository.ingest_validated_artifact(candidate, 500)
        asset_row = candidate_row | {
            "NR_ORDEM_BEM_CANDIDATO": "1",
            "CD_TIPO_BEM_CANDIDATO": "61",
            "DS_BEM_CANDIDATO": "Declaração fictícia com sinal preservado",
            "VR_BEM_CANDIDATO": "-491,27",
        }
        asset = validate_resource(archive_factory("asset", [asset_row]), configuration, index)
        assert asset.summary["rejected"] == 0
        assert repository.ingest_validated_artifact(asset, 500).new == 1
        row = integration_database.execute(
            "SELECT declared_value,value_quality_status "
            "FROM se_liga_brasil.candidate_asset_declaration"
        ).fetchone()
        assert row["declared_value"] == Decimal("-491.27")
        assert row["value_quality_status"] == "negative_requires_review"
        assert repository.ingest_validated_artifact(asset, 500).skipped_artifact
    finally:
        index.close()
        repository.finish_run("completed", {})
