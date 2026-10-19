"""National enrichment includes people without candidacies and bounded source partitions."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from crawlers.receita_federal import identity, pipeline
from crawlers.transferegov.acquisition import (
    TransferegovAcquisition,
    partition_query,
    validate_page,
)
from database.enrichment import fetch_enrichment_candidates
from service.ingestion.contracts import IngestionError


@pytest.mark.parametrize("filters", [{"id_proposta": None}, {"id_proposta": " "}])
def test_transfer_empty_filter_cannot_create_national_download(filters):
    with pytest.raises(IngestionError, match="TRANSFEREGOV_EMPTY_FILTER"):
        partition_query("parcerias", "proposta", filters)


@pytest.mark.parametrize(
    ("document", "error"),
    [
        ({"data": []}, "TRANSFEREGOV_INVALID_PAGINATION"),
        (
            {"data": [], "total_pages": True, "total_items": 0, "page_number": 1, "page_size": 10},
            "TRANSFEREGOV_INVALID_PAGINATION",
        ),
        (
            {"data": [], "total_pages": 1, "total_items": 2, "page_number": 1, "page_size": 10},
            "TRANSFEREGOV_INCOMPLETE_PAGE",
        ),
        (
            {
                "data": ["not-object"],
                "total_pages": 1,
                "total_items": 1,
                "page_number": 1,
                "page_size": 10,
            },
            "TRANSFEREGOV_SCHEMA_CHANGED",
        ),
    ],
)
def test_transfer_pagination_rejects_unproven_or_incomplete_pages(document, error):
    with pytest.raises(IngestionError, match=error):
        validate_page(document, 1, 10)


def test_transfer_invalid_json_is_quarantined_and_page_url_is_partitioned(monkeypatch, tmp_path):
    from crawlers.transferegov import acquisition

    path = tmp_path / "invalid.json"
    path.write_bytes(b"not json")
    artifact = SimpleNamespace(path=path)
    download = Mock(return_value=artifact)
    monkeypatch.setattr(acquisition, "download_resource", download)
    config = SimpleNamespace(page_size=10, max_pages=2)
    collector = TransferegovAcquisition(config, "client")
    with pytest.raises(IngestionError, match="TRANSFEREGOV_INVALID_JSON"):
        list(collector.pages("parcerias", "proposta", {"id_proposta": "123"}))
    resource = download.call_args.args[0]
    assert "id_proposta=123" in resource.url and "pagina=1" in resource.url
    assert download.call_args.args[-1] is collector.budget


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("person_id", "other", "CNPJ_INVALID_REVIEWED_RELATIONSHIP"),
        ("reviewed_by", " ", "CNPJ_INVALID_REVIEWED_RELATIONSHIP"),
        ("evidence_url", "http://official.example", "CNPJ_INVALID_REVIEW_EVIDENCE"),
        ("evidence_url", "https://user@official.example", "CNPJ_INVALID_REVIEW_EVIDENCE"),
        ("reviewed_at", "not-date", "CNPJ_INVALID_REVIEW_TIMESTAMP"),
        ("reviewed_at", "2024-01-01T10:00:00", "CNPJ_INVALID_REVIEW_TIMESTAMP"),
    ],
)
def test_corporate_review_requires_person_candidate_source_and_aware_timestamp(field, value, error):
    reviewed = identity.ReviewedRelationship(
        "one", "https://official.example", "Reviewer", "2024-01-01T10:00:00Z"
    )
    with pytest.raises(IngestionError, match=error):
        identity.validate_review(replace(reviewed, **{field: value}), {"one"})


def test_partner_scan_drops_personal_document_and_records_actual_source_observation(monkeypatch):
    artifact = SimpleNamespace(path="source", sha256="a" * 64, fetched_at="2024-01-05T00:00:00Z")
    monkeypatch.setattr(pipeline, "iter_partition_rows", Mock(return_value=[["raw"]]))
    monkeypatch.setattr(
        pipeline,
        "normalize_partner",
        Mock(
            return_value={
                "partner_document": "never-in-normalized-facts",
                "company_base": "12345678",
            }
        ),
    )
    monkeypatch.setattr(pipeline, "identify_partner", Mock(return_value={"observation_key": "key"}))
    facts = pipeline.scan_partners(
        [artifact], {}, {}, SimpleNamespace(max_matches=10), "2024-02-01"
    )
    assert "partner_document" not in facts["key"]
    assert facts["key"]["observed_on"] == "2024-01-05"
    assert facts["key"]["source_sha256"] == "a" * 64


def test_partner_kind_and_unknown_name_cannot_prove_company_ownership():
    assert identity.identify_partner({"partner_kind": "1"}, [], {}, {}, "hash") is None
    assert (
        identity.identify_partner(
            {"partner_kind": "2", "partner_name": "Unknown"}, [], {}, {}, "hash"
        )
        is None
    )


@pytest.mark.integration
def test_enrichment_default_includes_person_without_candidacy_and_current_office(
    integration_database,
):
    connection = integration_database
    source = connection.execute("""
        INSERT INTO se_liga_brasil.source(code,publisher,official_url,acquisition_method)
        VALUES('scope-test','Official','https://official.example','api') RETURNING id
    """).fetchone()["id"]
    record = connection.execute(
        """
        INSERT INTO se_liga_brasil.source_record(
          source_id,external_key,source_url,content_sha256,payload)
        VALUES(%s,'person','https://official.example',%s,'{}') RETURNING id
    """,
        (source, "a" * 64),
    ).fetchone()["id"]
    institution = connection.execute("""
        INSERT INTO se_liga_brasil.institution(code,name,level,uf,official_url)
        VALUES('camara','Câmara','federal','BR','https://official.example') RETURNING id
    """).fetchone()["id"]
    person_id = str(uuid4())
    connection.execute(
        """
        INSERT INTO se_liga_brasil.person(id,slug,civil_name,display_name,primary_record_id,
          has_current_public_office,current_public_office_kind,current_public_office_institution_id,
          public_office_status_source_record_id,public_office_status_as_of)
        VALUES(%s,'scope-person','Pessoa Fictícia','Pessoa Pública',%s,true,'federal_deputy',
          %s,%s,current_date)
    """,
        (person_id, record, institution, record),
    )
    rows = fetch_enrichment_candidates(connection)
    assert [row["person_id"] for row in rows] == [person_id]
    assert rows[0]["has_federal_candidacy"] is True
    assert (
        fetch_enrichment_candidates(connection, person_id, ufs=("SP",))[0]["person_id"] == person_id
    )
