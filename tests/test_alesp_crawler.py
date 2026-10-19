"""Source contracts, adversarial formats and transactional payroll versions."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from crawlers.alesp.configuration import ALESP_PARSER_VERSION, ALESP_SOURCE, CrawlerConfiguration
from crawlers.alesp.discovery import parse_payroll_resources
from crawlers.alesp.normalization import normalize_payroll_row
from crawlers.alesp.projection import AlespProjectionWriter
from crawlers.alesp.validator import parse_payroll_document, validate_resource
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from storage.files import hash_file


def payroll_html(gross="1.000,00", taxes="100,00", net="900,00"):
    return (
        "<p>Mês de referência: MARÇO/2026</p>"
        "<p>Remuneração Bruta Tributos Remuneração Líquida</p>"
        "<table id='dados'><tr><td>Pessoa Fictícia</td>"
        f"<td>{gross}</td><td>{taxes}</td><td>{net}</td></tr></table>"
    )


def payroll_artifact(tmp_path, payload, timestamp):
    path = tmp_path / f"{uuid4().hex}.html"
    path.write_bytes(payload.encode("latin1"))
    resource = Resource(
        "alesp-deputy-payroll-2026-03",
        "Folha março",
        "https://www.al.sp.gov.br/repositorio/folha-de-pagamento/folha-deputados-2026-03.html",
        "deputy_payroll",
        2026,
        "alesp-deputy-payroll",
        "SP",
    )
    return DownloadedArtifact(
        resource, path, hash_file(path), timestamp.isoformat(), path.stat().st_size
    )


def test_discovery_only_accepts_published_official_resources():
    path = "/repositorio/folha-de-pagamento/folha-deputados-2026-03.html"
    resources = parse_payroll_resources(f'<a href="{path}">March</a>'.encode())
    assert [r.resource_id for r in resources] == ["alesp-deputy-payroll-2026-03"]
    with pytest.raises(IngestionError, match="UNTRUSTED_RESOURCE_URL"):
        parse_payroll_resources(f'<a href="https://evil.example{path}">March</a>'.encode())


def test_latin1_reference_and_negative_payments_are_preserved():
    rows = parse_payroll_document(payroll_html("-1", "0", "-1").encode("latin1"), "2026-03")
    normalized = normalize_payroll_row(rows[0], "2026-03")
    assert normalized["grossAmount"] == "-1.00"
    assert normalized["netAmount"] == "-1.00"
    with pytest.raises(IngestionError, match="PAYROLL_REFERENCE_MONTH_MISMATCH"):
        parse_payroll_document(payroll_html().encode(), "2026-04")
    with pytest.raises(IngestionError, match="PAYROLL_AMOUNT_RECONCILIATION_FAILED"):
        normalize_payroll_row(["Pessoa Teste", "1.000,00", "100,00", "901,00"], "2026-03")


def test_tampered_download_is_rejected(tmp_path):
    artifact = payroll_artifact(tmp_path, payroll_html(), datetime.now(UTC))
    artifact.path.write_text("changed")
    with pytest.raises(IngestionError, match="ARCHIVE_CHECKSUM_MISMATCH"):
        validate_resource(artifact, CrawlerConfiguration(tmp_path))


def ingest_payroll_version(repository, configuration, tmp_path, payload, timestamp):
    artifact = payroll_artifact(tmp_path, payload, timestamp)
    return repository.ingest_validated_artifact(validate_resource(artifact, configuration), 10)


def count_table(connection, table):
    return connection.execute("SELECT count(*) n FROM se_liga_brasil." + table).fetchone()["n"]


@pytest.mark.integration
def test_payroll_idempotence_corrections_stale_conflicts_and_identity(
    integration_database, tmp_path
):
    repository = IngestionRepository(
        integration_database,
        ALESP_SOURCE,
        AlespProjectionWriter(SqlBatchWriter(integration_database)),
        parser_version=ALESP_PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {})
    configuration = CrawlerConfiguration(tmp_path)
    timestamp = datetime.now(UTC)
    first = validate_resource(payroll_artifact(tmp_path, payroll_html(), timestamp), configuration)
    try:
        assert repository.ingest_validated_artifact(first, 10).new == 1
        assert repository.ingest_validated_artifact(first, 10).skipped_artifact
        row = integration_database.execute(
            "SELECT * FROM se_liga_brasil.person_payroll_payment"
        ).fetchone()
        assert row["person_id"] is None
        assert row["identity_status"] == "pending"
        changed = ingest_payroll_version(
            repository,
            configuration,
            tmp_path,
            payroll_html("-100,00", "0,00", "-100,00"),
            timestamp + timedelta(seconds=1),
        )
        assert changed.changed == 1
        row = integration_database.execute(
            "SELECT * FROM se_liga_brasil.person_payroll_payment"
        ).fetchone()
        assert row["net_amount"] == Decimal("-100.00")
        assert count_table(integration_database, "ingestion_entity_version") == 2
        stale = ingest_payroll_version(
            repository,
            configuration,
            tmp_path,
            payroll_html("2.000,00", "0,00", "2.000,00"),
            timestamp - timedelta(seconds=1),
        )
        assert stale.stale == 1
        conflict = ingest_payroll_version(
            repository,
            configuration,
            tmp_path,
            payroll_html("3.000,00", "0,00", "3.000,00"),
            timestamp + timedelta(seconds=1),
        )
        assert conflict.rejected == 1
        assert count_table(integration_database, "person_payroll_payment") == 1
    finally:
        repository.finish_run("completed", {})


def test_duplicate_recipient_blocks_ambiguous_publication(tmp_path):
    document = payroll_html().replace(
        "</table>",
        "<tr><td>Pessoa Fictícia</td><td>2.000,00</td><td>0,00</td><td>2.000,00</td></tr></table>",
    )
    artifact = payroll_artifact(tmp_path, document, datetime.now(UTC))
    with pytest.raises(IngestionError, match="DUPLICATE_PAYROLL_RECIPIENT"):
        validate_resource(artifact, CrawlerConfiguration(tmp_path))


def test_crawler_requires_session_pool_for_advisory_locks():
    from psycopg.conninfo import conninfo_to_dict

    from database.operations import session_connection_string

    session = session_connection_string(
        "postgresql://example_user@aws-1-us-east-2.pooler.supabase.com:6543/example_db"
    )
    assert conninfo_to_dict(session)["port"] == "5432"
    direct = "postgresql://example_user@localhost:6543/example_db"
    assert session_connection_string(direct) == direct


@pytest.mark.integration
def test_identity_bridge_links_existing_payroll_idempotently(integration_database, tmp_path):
    from database.person_identity import apply_payroll_identity_links

    repository = IngestionRepository(
        integration_database,
        ALESP_SOURCE,
        AlespProjectionWriter(SqlBatchWriter(integration_database)),
        parser_version=ALESP_PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {})
    configuration = CrawlerConfiguration(tmp_path)
    try:
        ingest_payroll_version(
            repository, configuration, tmp_path, payroll_html(), datetime.now(UTC)
        )
        payment = integration_database.execute(
            "SELECT * FROM se_liga_brasil.person_payroll_payment"
        ).fetchone()
        person_id = uuid4()
        integration_database.execute(
            "INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,primary_record_id) "
            "VALUES(%s,%s,'Pessoa Fictícia','Pessoa Teste',%s)",
            (person_id, str(person_id), payment["source_record_id"]),
        )
        link = {
            "external_id": payment["recipient_key"],
            "person_id": str(person_id),
            "evidence": {
                "method": "test_evidence",
                "official_subjects": [{"source_subject_id": "member-test"}],
                "birth_conflict_preserved": True,
            },
            "hash": "a" * 64,
        }
        first = apply_payroll_identity_links(
            integration_database, repository.source_id, [link], ALESP_SOURCE.official_url
        )
        assert first["linked_payments"] == 1
        second = apply_payroll_identity_links(
            integration_database, repository.source_id, [link], ALESP_SOURCE.official_url
        )
        assert second["linked_payments"] == 0
        assert count_table(integration_database, "person_identifier") == 1
        assert count_table(integration_database, "person_identity_review") == 1
        row = integration_database.execute(
            "SELECT person_id,identity_status FROM se_liga_brasil.person_payroll_payment"
        ).fetchone()
        assert row["person_id"] == person_id
        assert row["identity_status"] == "verified"
        conflicting = link | {"person_id": str(uuid4())}
        with pytest.raises(IngestionError, match="SOURCE_IDENTITY_BRIDGE_CONFLICT"):
            apply_payroll_identity_links(
                integration_database, repository.source_id, [conflicting], ALESP_SOURCE.official_url
            )
    finally:
        repository.finish_run("completed", {})
