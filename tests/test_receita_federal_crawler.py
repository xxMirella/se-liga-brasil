"""Bounded CNPJ snapshots use fictional fixtures and never access a database."""

import csv
from dataclasses import replace
from io import StringIO
from uuid import uuid4
from zipfile import ZipFile

import pytest

from crawlers.receita_federal import CrawlerConfiguration, plan_resources, scan_snapshot
from crawlers.receita_federal.identity import ReviewedRelationship, partner_evidence_key
from crawlers.receita_federal.parsing import iter_partition_rows
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from storage.files import hash_file


@pytest.fixture
def configuration(tmp_path):
    return CrawlerConfiguration(tmp_path, max_resources=4)


def archive(tmp_path, kind, rows):
    text = StringIO(newline="")
    csv.writer(text, delimiter=";", lineterminator="\n").writerows(rows)
    path = tmp_path / (kind + ".zip")
    with ZipFile(path, "w") as zipped:
        zipped.writestr(kind + ".csv", text.getvalue().encode("cp1252"))
    resource = Resource(
        kind, kind, "https://arquivos.receitafederal.gov.br/fixture.zip", kind, 2026, "2026-09"
    )
    return DownloadedArtifact(resource, path, hash_file(path), "2026-10-17", path.stat().st_size)


def partner_row(name="PESSOA FICTÍCIA", document="***123456**"):
    return ["12345678", "2", name, document, "49", "20200105", "", "", "", "", "4"]


def test_selective_plan_deduplicates_and_blocks_untrusted_urls(configuration):
    url = "https://arquivos.receitafederal.gov.br/dados/cnpj/2026-09/Socios0.zip"
    assert len(plan_resources("2026-09", [url, url], configuration)) == 1
    with pytest.raises(IngestionError, match="UNTRUSTED"):
        plan_resources(
            "2026-09", [url.replace("arquivos.receitafederal.gov.br", "example.com")], configuration
        )
    with pytest.raises(IngestionError, match="SNAPSHOT_URL_MISMATCH"):
        plan_resources("2026-08", [url], configuration)


def test_masked_document_and_homonyms_never_confirm_identity(tmp_path, configuration):
    artifact = archive(tmp_path, "partners", [partner_row(), partner_row()])
    people = [{"person_id": str(uuid4()), "full_name": "Pessoa Fictícia"} for _ in range(2)]
    result = scan_snapshot([artifact], people, configuration, observed_on="2026-10-17")
    assert len(result.relationships) == 1
    relationship = result.relationships[0]
    assert relationship["person_id"] is None
    assert relationship["identity_status"] == "unverified"
    assert len(relationship["candidate_person_ids"]) == 2
    assert "partner_document" not in relationship
    assert relationship["entered_on"] == "2020-01-05"
    assert relationship["observed_on"] == "2026-10-17"
    assert relationship["exited_on"] is None


def test_reviewed_relationship_and_replay_are_deterministic(tmp_path, configuration):
    row = partner_row()
    artifact = archive(tmp_path, "partners", [row])
    person = {"person_id": str(uuid4()), "full_name": "Pessoa Fictícia"}
    observation_key = artifact.sha256 + ":" + partner_evidence_key(row)
    review = ReviewedRelationship(
        person["person_id"],
        "https://www.gov.br/evidencia",
        "test-reviewer",
        "2026-10-17T00:00:00+00:00",
    )
    arguments = {"observed_on": "2026-10-17", "reviewed_relationships": {observation_key: review}}
    first = scan_snapshot([artifact, artifact], [person], configuration, **arguments)
    assert first == scan_snapshot([artifact], [person], configuration, **arguments)
    assert first.relationships[0]["person_id"] == person["person_id"]
    assert first.relationships[0]["identity_status"] == "reviewed"


def test_business_files_are_read_once_for_person_batch(tmp_path, configuration, monkeypatch):
    from crawlers.receita_federal import pipeline

    partner = archive(tmp_path, "partners", [partner_row()])
    company = archive(
        tmp_path, "companies", [["12345678", "EMPRESA FICTÍCIA", "2062", "49", "1,00", "01", ""]]
    )
    establishment_row = [""] * 30
    establishment_row[:7] = ["12345678", "0001", "00", "1", "", "02", "20200105"]
    establishment_row[10] = "20200105"
    establishment_row[19:21] = ["SP", "7107"]
    establishment = archive(tmp_path, "establishments", [establishment_row])
    calls = []
    original = pipeline.iter_partition_rows

    def counted_rows(path, kind, configuration):
        calls.append(kind)
        return original(path, kind, configuration)

    monkeypatch.setattr(pipeline, "iter_partition_rows", counted_rows)
    people = [{"person_id": str(uuid4()), "full_name": "Pessoa Fictícia"} for _ in range(10)]
    result = scan_snapshot(
        [partner, company, establishment], people, configuration, observed_on="2026-10-17"
    )
    assert calls == ["partners", "companies", "establishments"]
    assert len(result.companies) == len(result.establishments) == 1
    assert result.companies[0]["share_capital"] == "1.00"


@pytest.mark.parametrize(
    "limit,code",
    [
        ({"max_records_per_resource": 0}, "RECORD_LIMIT"),
        ({"max_uncompressed_bytes": 1}, "UNCOMPRESSED_LIMIT"),
        ({"max_members_per_resource": 0}, "ZIP_MEMBER_LIMIT"),
    ],
)
def test_streaming_limits_fail_without_returning_complete_result(
    tmp_path, configuration, limit, code
):
    artifact = archive(tmp_path, "partners", [partner_row()])
    with pytest.raises(IngestionError, match=code):
        list(iter_partition_rows(artifact.path, "partners", replace(configuration, **limit)))


def test_matching_memory_is_bounded(tmp_path, configuration):
    artifact = archive(tmp_path, "partners", [partner_row()])
    people = [{"person_id": str(uuid4()), "full_name": "Pessoa Fictícia"}]
    with pytest.raises(IngestionError, match="MATCH_LIMIT"):
        scan_snapshot(
            [artifact], people, replace(configuration, max_matches=0), observed_on="2026-10-17"
        )


def test_layout_change_is_not_silently_accepted(tmp_path, configuration):
    artifact = archive(tmp_path, "partners", [["incorrect"]])
    with pytest.raises(IngestionError, match="LAYOUT_CHANGED"):
        list(iter_partition_rows(artifact.path, "partners", configuration))


def test_unreviewed_relationships_are_not_staged_for_database(tmp_path, configuration):
    from crawlers.receita_federal.staging import stage_snapshot_facts

    artifact = archive(tmp_path, "partners", [partner_row()])
    person = {"person_id": str(uuid4()), "full_name": "Pessoa Fictícia"}
    facts = scan_snapshot([artifact], [person], configuration, observed_on="2026-10-17")
    validated = stage_snapshot_facts(artifact, facts, configuration)
    assert validated.summary["valid"] == 0
    assert validated.records_path.read_text() == ""
    assert artifact.sha256 == hash_file(artifact.path)


def test_review_requires_timestamp_and_evidence(tmp_path, configuration):
    row = partner_row()
    artifact = archive(tmp_path, "partners", [row])
    person = {"person_id": str(uuid4()), "full_name": "Pessoa Fictícia"}
    review = ReviewedRelationship(
        person["person_id"], "https://www.gov.br/evidencia", "test-reviewer", "2026-10-17"
    )
    key = artifact.sha256 + ":" + partner_evidence_key(row)
    with pytest.raises(IngestionError, match="REVIEW_TIMESTAMP"):
        scan_snapshot(
            [artifact],
            [person],
            configuration,
            observed_on="2026-10-17",
            reviewed_relationships={key: review},
        )


def test_reviewed_link_is_staged_without_masked_document(tmp_path, configuration):
    import json

    from crawlers.receita_federal.staging import stage_snapshot_facts

    row = partner_row()
    artifact = archive(tmp_path, "partners", [row])
    person = {"person_id": str(uuid4()), "full_name": "Pessoa Fictícia"}
    review = ReviewedRelationship(
        person["person_id"],
        "https://www.gov.br/evidencia",
        "test-reviewer",
        "2026-10-17T00:00:00+00:00",
    )
    key = artifact.sha256 + ":" + partner_evidence_key(row)
    facts = scan_snapshot(
        [artifact],
        [person],
        configuration,
        observed_on="2026-10-17",
        reviewed_relationships={key: review},
    )
    validated = stage_snapshot_facts(artifact, facts, configuration)
    record = json.loads(validated.records_path.read_text())
    assert record["normalizedData"]["person_id"] == person["person_id"]
    assert record["normalizedData"]["exited_on"] is None
    assert "***123456**" not in validated.records_path.read_text()


def test_review_change_changes_artifact_scope_to_avoid_skipped_replay(tmp_path, configuration):
    from crawlers.receita_federal.staging import stage_snapshot_facts

    row = partner_row()
    artifact = archive(tmp_path, "partners", [row])
    person = {"person_id": str(uuid4()), "full_name": "Pessoa Fictícia"}
    initial = scan_snapshot([artifact], [person], configuration, observed_on="2026-10-17")
    review = ReviewedRelationship(
        person["person_id"],
        "https://www.gov.br/evidencia",
        "test-reviewer",
        "2026-10-17T00:00:00+00:00",
    )
    key = artifact.sha256 + ":" + partner_evidence_key(row)
    reviewed = scan_snapshot(
        [artifact],
        [person],
        configuration,
        observed_on="2026-10-17",
        reviewed_relationships={key: review},
    )
    assert (
        stage_snapshot_facts(artifact, initial, configuration).scope_key
        != stage_snapshot_facts(artifact, reviewed, configuration).scope_key
    )


@pytest.fixture
def business_database(integration_database):
    from database.operations import read_sql_file, strip_transaction_wrapper

    integration_database.execute(
        strip_transaction_wrapper(read_sql_file("migrations/0016_business_relationships.sql"))
    )
    return integration_database


@pytest.fixture
def business_repository(business_database):
    from crawlers.receita_federal.projection import BusinessProjectionWriter
    from crawlers.receita_federal.staging import PARSER_VERSION
    from service.ingestion.contracts import SourceDescriptor
    from service.ingestion.repository import IngestionRepository
    from service.ingestion.sql_batches import SqlBatchWriter

    source = SourceDescriptor(
        "receita_federal", "Receita Federal", "https://www.gov.br/receitafederal"
    )
    repository = IngestionRepository(
        business_database,
        source,
        BusinessProjectionWriter(SqlBatchWriter(business_database)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {})
    yield repository
    repository.finish_run("completed", {})


def seed_business_person(connection, source_id):
    record_id = connection.execute(
        """
        INSERT INTO se_liga_brasil.source_record(source_id,external_key,source_url,
         content_sha256,payload)
        VALUES(%s,'fixture-person','https://www.gov.br/fixture',%s,'{}') RETURNING id
    """,
        (source_id, "a" * 64),
    ).fetchone()["id"]
    person_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,primary_record_id)
        VALUES(%s,%s,'Pessoa Fictícia','Pessoa Fictícia',%s)
    """,
        (person_id, person_id, record_id),
    )
    return {"person_id": person_id, "full_name": "Pessoa Fictícia"}


def business_fixture_artifacts(tmp_path):
    row = partner_row()
    partner = archive(tmp_path, "partners", [row])
    company = archive(
        tmp_path, "companies", [["12345678", "EMPRESA FICTÍCIA", "2062", "49", "1,00", "01", ""]]
    )
    establishment_row = [""] * 30
    establishment_row[:7] = ["12345678", "0001", "00", "1", "", "02", "20200105"]
    establishment_row[10] = "20200105"
    establishment_row[19:21] = ["SP", "7107"]
    establishment = archive(tmp_path, "establishments", [establishment_row])
    return (company, establishment, partner), row


def assert_business_entities_without_person_link(connection):
    assert (
        connection.execute("SELECT count(*) AS n FROM se_liga_brasil.business").fetchone()["n"] == 1
    )
    assert (
        connection.execute(
            "SELECT count(*) AS n FROM se_liga_brasil.business_establishment"
        ).fetchone()["n"]
        == 1
    )
    assert (
        connection.execute(
            "SELECT count(*) AS n FROM se_liga_brasil.person_business_relationship_observation"
        ).fetchone()["n"]
        == 0
    )


@pytest.mark.integration
def test_sql_business_projection_and_reviewed_relationship_replay(
    business_database,
    business_repository,
    tmp_path,
    configuration,
):
    from crawlers.receita_federal.pipeline import ingest_snapshot_facts

    person = seed_business_person(business_database, business_repository.source_id)
    artifacts, row = business_fixture_artifacts(tmp_path)
    facts = scan_snapshot(artifacts, [person], configuration, observed_on="2026-10-17")
    ingest_snapshot_facts(artifacts, facts, configuration, business_repository)
    assert_business_entities_without_person_link(business_database)
    review = ReviewedRelationship(
        person["person_id"],
        "https://www.gov.br/evidencia",
        "test-reviewer",
        "2026-10-17T00:00:00+00:00",
    )
    key = artifacts[2].sha256 + ":" + partner_evidence_key(row)
    facts = scan_snapshot(
        artifacts,
        [person],
        configuration,
        observed_on="2026-10-17",
        reviewed_relationships={key: review},
    )
    ingest_snapshot_facts(artifacts, facts, configuration, business_repository)
    repeated = ingest_snapshot_facts(artifacts, facts, configuration, business_repository)
    assert all(summary.skipped_artifact for summary in repeated)
    relation = business_database.execute(
        "SELECT * FROM se_liga_brasil.person_business_relationship_observation"
    ).fetchall()
    assert len(relation) == 1
    assert str(relation[0]["person_id"]) == person["person_id"]
    assert relation[0]["exited_on"] is None
    assert relation[0]["entered_on"].isoformat() == "2020-01-05"
    assert relation[0]["snapshot_month"].isoformat() == "2026-09-01"
    assert (
        business_database.execute(
            "SELECT count(*) AS n FROM se_liga_brasil.ingestion_rejection"
        ).fetchone()["n"]
        == 0
    )


def test_reanalysis_date_does_not_change_source_observation(tmp_path, configuration):
    artifact = archive(tmp_path, "partners", [partner_row()])
    person = {"person_id": str(uuid4()), "full_name": "Pessoa Fictícia"}
    first = scan_snapshot([artifact], [person], configuration, observed_on="2026-10-17")
    later = scan_snapshot([artifact], [person], configuration, observed_on="2026-10-18")
    assert first.relationships == later.relationships


@pytest.mark.integration
def test_sql_reanalysis_and_review_versions_are_distinct(
    business_database,
    business_repository,
    tmp_path,
    configuration,
):
    from crawlers.receita_federal.pipeline import ingest_snapshot_facts

    person = seed_business_person(business_database, business_repository.source_id)
    artifacts, row = business_fixture_artifacts(tmp_path)
    key = artifacts[2].sha256 + ":" + partner_evidence_key(row)
    review = ReviewedRelationship(
        person["person_id"],
        "https://www.gov.br/evidencia",
        "test-reviewer",
        "2026-10-17T00:00:00+00:00",
    )
    first = scan_snapshot(
        artifacts,
        [person],
        configuration,
        observed_on="2026-10-17",
        reviewed_relationships={key: review},
    )
    ingest_snapshot_facts(artifacts, first, configuration, business_repository)
    later = scan_snapshot(
        artifacts,
        [person],
        configuration,
        observed_on="2026-10-18",
        reviewed_relationships={key: review},
    )
    assert all(
        summary.skipped_artifact
        for summary in ingest_snapshot_facts(artifacts, later, configuration, business_repository)
    )
    revised = replace(review, reviewed_at="2026-10-18T00:00:00+00:00")
    facts = scan_snapshot(
        artifacts,
        [person],
        configuration,
        observed_on="2026-10-18",
        reviewed_relationships={key: revised},
    )
    ingest_snapshot_facts(artifacts, facts, configuration, business_repository)
    observations = business_database.execute("""
        SELECT person_id,observed_on,reviewed_at FROM
        se_liga_brasil.person_business_relationship_observation ORDER BY reviewed_at
    """).fetchall()
    assert len(observations) == 2
    assert observations[0]["observed_on"] == observations[1]["observed_on"]
    assert observations[0]["reviewed_at"] != observations[1]["reviewed_at"]
    assert (
        business_database.execute(
            "SELECT count(*) AS n FROM se_liga_brasil.ingestion_rejection"
        ).fetchone()["n"]
        == 0
    )
