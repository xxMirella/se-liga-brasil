"""Official descriptions, immutable source evidence and rollback-only projection tests."""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from crawlers.senado.configuration import SOURCE, SenateConfiguration
from crawlers.senado.process_pipeline import (
    collect_senate_process_details,
    known_processes,
    validate_registered_process,
)
from crawlers.senado.process_staging import (
    PARSER_VERSION,
    SenateProcessSummaryProjection,
    process_summary_record,
    stage_process_summary,
)
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from storage.files import hash_file


def summary_process(description="Ementa oficial fictícia."):
    return {
        "source_key": "123",
        "kind": "PL",
        "number": "1",
        "year": 2026,
        "description": description,
        "authorship_evidence": [{"codigoParlamentar": "999"}],
        "generated_norm_evidence": {"codigo": "456"},
    }


def process_artifact(tmp_path, process, observed_at):
    path = tmp_path / (uuid4().hex + ".json")
    path.write_text(json.dumps(process))
    resource = Resource(
        "senado-process123",
        "process",
        "https://legis.senado.leg.br/dadosabertos/processo/123.json?v=1",
        "process",
        2026,
        "fixture",
        file_suffix=".json",
    )
    return DownloadedArtifact(resource, path, hash_file(path), observed_at, path.stat().st_size)


def test_staging_whitelists_description_and_preserves_original(tmp_path):
    process = summary_process()
    artifact = process_artifact(tmp_path, process, "2026-10-17T12:00:00+00:00")
    before = hash_file(artifact.path)
    staged = stage_process_summary(artifact, SenateConfiguration(tmp_path), process)
    row = json.loads(staged.records_path.read_text())["normalizedData"]
    assert row["summary"] == "Ementa oficial fictícia."
    assert row["official_url"].endswith("/processo/123")
    assert "authorship_evidence" not in row and "codigoParlamentar" not in json.dumps(row)
    assert hash_file(artifact.path) == before
    newer = process_artifact(tmp_path, process, "2026-10-18T12:00:00+00:00")
    newer_staging = stage_process_summary(newer, SenateConfiguration(tmp_path), process)
    assert json.loads(newer_staging.records_path.read_text())["normalizedData"] == row
    assert row == process_summary_record(process)


def test_budget_and_registration_fail_before_http(tmp_path):
    with pytest.raises(IngestionError, match="BUDGET_MUST_BE_ONE"):
        collect_senate_process_details(None, tmp_path, [1], max_processes=2)
    with pytest.raises(IngestionError, match="BATCH_LIMIT"):
        collect_senate_process_details(None, tmp_path, [1, 2])
    connection = SimpleNamespace(execute=lambda *args: SimpleNamespace(fetchall=lambda: []))
    with pytest.raises(IngestionError, match="NOT_REGISTERED"):
        known_processes(connection, [1])
    with pytest.raises(IngestionError, match="PROPOSITION_MISMATCH"):
        validate_registered_process(summary_process(), {"kind": "PEC"})


def seed_known_process(connection):
    connection.execute("""
        INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method)
        VALUES('summary-fixture','Fixture','https://example.invalid','api')
    """)
    record_id = connection.execute("""
        INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,
          content_sha256,payload)
        SELECT id,'summary-fixture','https://example.invalid',repeat('d',64),'{}'
        FROM se_liga_brasil.source WHERE code='summary-fixture' RETURNING id
    """).fetchone()["id"]
    institution_id = connection.execute("""
        INSERT INTO se_liga_brasil.institution(code,name,level,uf,official_url)
        VALUES('senado','Senado Federal','federal','BR','https://www.senado.leg.br')
        RETURNING id
    """).fetchone()["id"]
    connection.execute(
        """
        INSERT INTO se_liga_brasil.proposition(institution_id,official_key,kind,number,year,
          title,current_status,status_as_of,source_record_id)
        VALUES(%s,'https://legis.senado.leg.br/dadosabertos/processo/123','PL','1',2026,
          'PL 1/2026','unknown',now(),%s)
    """,
        (institution_id, record_id),
    )


def ingest_description(repository, tmp_path, description, observed_at):
    process = summary_process(description)
    artifact = process_artifact(tmp_path, process, observed_at)
    return repository.ingest_validated_artifact(
        stage_process_summary(artifact, SenateConfiguration(tmp_path), process), 500
    )


@pytest.mark.integration
def test_sql_summary_replay_correction_stale_and_missing_text(integration_database, tmp_path):
    connection = integration_database
    seed_known_process(connection)
    assert set(known_processes(connection, [123])) == {"123"}
    repository = IngestionRepository(
        connection,
        SOURCE,
        SenateProcessSummaryProjection(SqlBatchWriter(connection)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"test": True})
    try:
        first = ingest_description(
            repository, tmp_path, "Texto oficial.", "2026-10-17T12:00:00+00:00"
        )
        assert first.new == 1
        replay = ingest_description(
            repository, tmp_path, "Texto oficial.", "2026-10-18T12:00:00+00:00"
        )
        assert replay.skipped_artifact
        ingest_description(repository, tmp_path, "Texto retificado.", "2026-10-19T12:00:00+00:00")
        stale = ingest_description(
            repository, tmp_path, "Texto antigo.", "2026-10-18T13:00:00+00:00"
        )
        assert stale.stale == 1
        ingest_description(repository, tmp_path, None, "2026-10-20T12:00:00+00:00")
        row = connection.execute("""
            SELECT p.summary,r.payload->>'summary' AS source_summary,p.current_status
            FROM se_liga_brasil.proposition p JOIN se_liga_brasil.source_record r
            ON r.id=p.source_record_id WHERE p.official_key LIKE '%%/processo/123'
        """).fetchone()
        assert row == {
            "summary": "Texto retificado.",
            "source_summary": "Texto retificado.",
            "current_status": "unknown",
        }
        versions = connection.execute("""
            SELECT count(*) AS n FROM se_liga_brasil.ingestion_entity_version version
            JOIN se_liga_brasil.ingestion_entity entity ON entity.id=version.entity_id
            WHERE entity.entity_kind='senado_process_summary'
        """).fetchone()["n"]
        assert versions == 4
    finally:
        repository.finish_run("completed", {})
