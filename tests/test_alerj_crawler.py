"""Fictitious ALERJ layout and identity tests; no production writes."""

from dataclasses import replace
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from test_database_integration import start_repository

from crawlers.alerj.configuration import PARSER_VERSION, SOURCE, CrawlerConfiguration
from crawlers.alerj.parsing import latest_payroll_document, parse_profile, parse_roster
from crawlers.alerj.payroll import normalize_deputy_row, parse_amount, parse_deputy_payroll
from crawlers.alerj.pipeline import (
    collect_alerj_enrichment,
    match_roster_targets,
    select_person_payroll,
)
from crawlers.alerj.projection import AlerjProjectionWriter
from crawlers.alerj.staging import stage_records
from crawlers.tse.validator import validate_resource
from service.ingestion.contracts import DownloadedArtifact, IngestionError, Resource
from service.ingestion.repository import IngestionRepository
from service.ingestion.sql_batches import SqlBatchWriter
from storage.files import hash_file
from storage.validation_index import ValidationIndex


def profile_html():
    return """<div class="partido"><span>PSOL</span>PSOL</div>
    <h1>DEPUTADA Maria Exemplo</h1><h2>NASCIMENTO</h2><p>5 de maio de 1980</p>
    <h1>13º Legislatura (2023 – 2027) - Atual</h1>
    <p>Posse na ALERJ: PSOL - Data 01/02/2023</p>
    <h1>Legislaturas Anteriores</h1>
    <p>Troca de partido: Ingresso no PT - Data 20/03/2018</p>""".encode()


def payroll_line():
    amounts = [
        "10.000,00",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "-",
        "100,00",
        "900,00",
        "500,00",
        "9.000,00",
    ]
    return "  ".join(["MARIA EXEMPLO", "DEPUTADO ESTADUAL", *amounts])


def test_profile_keeps_explicit_history_without_claiming_exercise():
    profile = parse_profile(profile_html(), "Maria Exemplo")
    assert profile["birthDate"] == "1980-05-05"
    assert profile["politicalPartyAbbreviation"] == "PSOL"
    assert profile["affiliationEvents"][1]["startsOn"] == "2018-03-20"
    assert "inExercise" not in profile


def test_profile_rejects_wrong_subject_and_missing_birth():
    with pytest.raises(IngestionError, match="NAME_MISMATCH"):
        parse_profile(profile_html(), "Outra Pessoa")
    with pytest.raises(IngestionError, match="LAYOUT_CHANGED"):
        parse_profile(profile_html().replace(b"NASCIMENTO", b"CONTATO"), "Maria Exemplo")


def test_payroll_reconciles_and_separates_indemnity():
    row = normalize_deputy_row(payroll_line(), "2026-09-01")
    assert row["grossAmount"] == "10000.00"
    assert row["taxAmount"] == "1000.00"
    assert row["netAmount"] == "9000.00"
    assert row["components"]["indemnity"] == "500.00"
    assert row["indemnityIncludedInNet"] is False
    assert parse_amount("-") == Decimal("0.00")


def test_payroll_rejects_changed_columns_arithmetic_and_duplicates():
    with pytest.raises(IngestionError, match="COLUMN_MISMATCH"):
        normalize_deputy_row(payroll_line() + "  -", "2026-09-01")
    with pytest.raises(IngestionError, match="RECONCILIATION_FAILED"):
        normalize_deputy_row(payroll_line().replace("9.000,00", "9.001,00"), "2026-09-01")
    text = "Folha de Pagamento de setembro de 2026\n" + payroll_line() + "\n" + payroll_line()
    with pytest.raises(IngestionError, match="DUPLICATE_PAYROLL_RECIPIENT"):
        parse_deputy_payroll(text)


def test_catalog_uses_dates_instead_of_document_ids():
    html = b"""<div id="heading-2025">DEZEMBRO
    <a href="/download-spic?file=https%3A%2F%2Fwww2.alerj.rj.gov.br%2Fold">pdf</a></div>
    <div id="heading-2026">SETEMBRO
    <a href="/download-spic?file=https%3A%2F%2Fwww2.alerj.rj.gov.br%2Fnew">pdf</a></div>"""
    assert latest_payroll_document(html) == ("2026-09-01", "https://www2.alerj.rj.gov.br/new")


def test_alias_candidates_remain_ambiguous_and_payroll_requires_civil_name():
    people = [
        {"person_id": "a", "civil_name": "Maria Completa", "display_name": "Maria"},
        {"person_id": "b", "civil_name": "Maria Outra", "display_name": "Maria"},
    ]
    assert match_roster_targets([{"display_name": "Maria", "url": "official"}], people) == []
    with pytest.raises(IngestionError, match="IDENTITY_REVIEW_REQUIRED"):
        select_person_payroll(people[0], {"MARIA": {"recipientName": "Maria"}})


def test_roster_deduplicates_image_and_name_links():
    html = b"""<a href="/Deputados/PerfilDeputado/1"><img alt="Maria"></a>
    <a href="/Deputados/PerfilDeputado/1">Maria Exemplo</a>"""
    assert len(parse_roster(html)) == 1


@pytest.mark.integration
def test_alerj_projection_links_person_and_preserves_unknown_exercise(
    integration_database, configuration, archive_factory, candidate_row, tmp_path
):
    tse = start_repository(integration_database)
    artifact = archive_factory("candidate", [candidate_row])
    index = ValidationIndex(tmp_path / "candidates.sqlite")
    tse.ingest_validated_artifact(validate_resource(artifact, configuration, index), 500)
    person_id = str(
        integration_database.execute("SELECT id FROM se_liga_brasil.person").fetchone()["id"]
    )
    repository = IngestionRepository(
        integration_database,
        SOURCE,
        AlerjProjectionWriter(SqlBatchWriter(integration_database)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {})
    try:
        payroll = normalize_deputy_row(payroll_line(), "2026-09-01")
        payroll.update({"personId": person_id, "recipientKey": person_id, "representedUf": "RJ"})
        path = tmp_path / "original.pdf"
        path.write_bytes(b"immutable fictitious source")
        resource = Resource(
            "test-collection",
            "salary",
            "https://www2.alerj.rj.gov.br/test",
            "alerj_payroll",
            2026,
            "test-payroll",
            "RJ",
            ".pdf",
        )
        document = DownloadedArtifact(
            resource, path, hash_file(path), datetime.now(UTC).isoformat(), path.stat().st_size
        )
        staged = stage_records(document, CrawlerConfiguration(tmp_path), [payroll])
        assert repository.ingest_validated_artifact(staged, 500).new == 1
        assert repository.ingest_validated_artifact(staged, 500).skipped_artifact
        ingest_profile_fixture(repository, document, tmp_path, person_id)
        row = integration_database.execute(
            "SELECT person_id::text,net_amount FROM se_liga_brasil.person_payroll_payment"
        ).fetchone()
        assert row["person_id"] == person_id and row["net_amount"] == Decimal("9000.00")
        assert (
            integration_database.execute(
                "SELECT has_current_public_office FROM se_liga_brasil.person"
            ).fetchone()["has_current_public_office"]
            is None
        )
    finally:
        repository.finish_run("completed", {})
        tse.finish_run("completed", {})


def ingest_profile_fixture(repository, document, storage, person_id):
    profile = {
        "personId": person_id,
        "birthDate": "1980-05-10",
        "inExercise": None,
        "politicalPartyAbbreviation": "TESTE",
        "institutionCode": "alerj",
    }
    artifact = replace(
        document,
        resource=replace(document.resource, resource_id="fictitious-profile", kind="alerj_profile"),
    )
    staged = stage_records(artifact, CrawlerConfiguration(storage), [profile])
    assert repository.ingest_validated_artifact(staged, 500).new == 1
    assert (
        repository.connection.execute(
            "SELECT count(*) AS total FROM se_liga_brasil.political_party_affiliation "
            "WHERE information_scope='institution:alerj'"
        ).fetchone()["total"]
        == 1
    )


def test_unsupported_fields_do_not_open_network_or_database(tmp_path):
    result = collect_alerj_enrichment(
        None, tmp_path, [{"person_id": "example"}], {"current_public_office", "political_activity"}
    )
    assert result["status"] == "blocked"
    assert result["people"] == []


def test_unmatched_roster_does_not_download_payroll(tmp_path):
    from types import SimpleNamespace

    from crawlers.alerj.configuration import ROSTER_URL
    from crawlers.alerj.pipeline import collect_shared_evidence

    path = tmp_path / "roster.html"
    path.write_bytes(b'<a href="/Deputados/PerfilDeputado/1">Maria Exemplo</a>')
    calls = []

    def acquire(url, kind):
        calls.append((url, kind))
        return SimpleNamespace(path=path)

    acquisition = SimpleNamespace(acquire=acquire)
    _, targets, payroll, document, _ = collect_shared_evidence(
        acquisition, [{"person_id": "unmatched", "civil_name": "Pessoa Diferente"}]
    )
    assert targets == [] and payroll == {} and document is None
    assert calls == [(ROSTER_URL, "alerj_roster")]
