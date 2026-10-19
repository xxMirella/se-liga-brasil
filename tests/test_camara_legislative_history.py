"""Anonymous contracts for optional source-backed legislative enrichment."""

from types import SimpleNamespace

import pytest

from crawlers.camara.configuration import API_BASE
from crawlers.camara.legislative_history import (
    collect_legislative_history,
    normalize_history_page,
    proposition_identifier,
)
from crawlers.camara.legislative_normalization import (
    normalize_author,
    normalize_collective_decision,
    normalize_proceeding,
)
from crawlers.camara.projection import CamaraProjectionWriter
from crawlers.camara.staging import record_key
from service.ingestion.contracts import IngestionError

PROPOSITION = API_BASE + "proposicoes/123"


def test_stage_approval_is_not_project_approval_or_rejection():
    row = {"uri": API_BASE + "votacoes/123-1", "data": "2026-01-02", "aprovacao": 0}
    result = normalize_collective_decision(row, PROPOSITION)
    assert result["result"] == "unknown"
    assert result["approvalIndicator"] == 0
    assert "not_final" in result["scope"]
    assert (
        normalize_collective_decision(row | {"aprovacao": 1}, PROPOSITION)["result"] == "approved"
    )
    assert "personId" not in result


def test_author_roles_require_verified_person_and_explicit_source_role():
    row = {"uri": API_BASE + "deputados/1", "proponente": 0, "ordemAssinatura": 2}
    assert normalize_author(row, PROPOSITION, lambda _: None) is None
    result = normalize_author(row, PROPOSITION, lambda _: "internal-person")
    assert result["role"] == "coauthor"
    assert "uri" not in result
    assert normalize_author(row | {"proponente": 1}, PROPOSITION, lambda _: "p")["role"] == "author"
    with pytest.raises(IngestionError, match="AUTHOR_ROLE_UNVERIFIED"):
        normalize_author(row | {"proponente": None}, PROPOSITION, lambda _: "p")


def test_proceedings_deduplicate_by_sequence_without_inventing_final_status():
    row = {"sequencia": 1, "dataHora": "2026-01-02T12:30", "despacho": "Aprovado em comissão"}
    facts = normalize_history_page([row, row], "tramitacoes", PROPOSITION, None)
    assert len(facts) == 1
    assert facts[0]["status"] == "unknown"
    assert facts[0]["timeZone"] == "America/Sao_Paulo"
    changed = normalize_proceeding(row | {"despacho": "Descrição corrigida"}, PROPOSITION)
    assert changed["recordKey"] == facts[0]["recordKey"]
    assert record_key("camara_legislative_tramitacoes", changed) == changed["recordKey"]


@pytest.mark.parametrize(
    "key", ["https://example.org/proposicoes/123", PROPOSITION + "?x=1", "123"]
)
def test_document_keys_cannot_redirect_acquisition(key):
    with pytest.raises(IngestionError, match="INVALID_PROPOSITION_KEY"):
        proposition_identifier(key)


def test_collection_deduplicates_shared_documents_and_enforces_bound(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "crawlers.camara.legislative_history.collect_proposition_history",
        lambda _a, _r, identifier, _p: calls.append(identifier),
    )
    collect_legislative_history(None, None, [PROPOSITION, PROPOSITION], max_propositions=1)
    assert calls == ["123"]
    with pytest.raises(IngestionError, match="BUDGET_EXCEEDED"):
        collect_legislative_history(
            None, None, [PROPOSITION, PROPOSITION + "4"], max_propositions=1
        )


def test_pagination_failure_does_not_report_complete(monkeypatch):
    monkeypatch.setattr("crawlers.camara.legislative_history.ingest_collected", lambda *args: {})
    detail = {"uri": PROPOSITION, "siglaTipo": "PL", "numero": 1, "ano": 2026}

    def interrupted_pages(path, kind):
        yield [{"sequencia": 1, "dataHora": "2026-01-02T12:30"}], None
        raise IngestionError("CAMARA_PAGE_LIMIT_EXCEEDED")

    acquisition = SimpleNamespace(
        json_document=lambda *args: ({"dados": detail}, None), pages=interrupted_pages
    )
    with pytest.raises(IngestionError, match="PAGE_LIMIT_EXCEEDED"):
        collect_legislative_history(acquisition, None, [PROPOSITION])


def test_legislative_projection_does_not_require_person_or_write_current_office():
    statements = []
    writer = SimpleNamespace(execute_statements=lambda name, params: statements.append(name))
    CamaraProjectionWriter(writer).project_batch({}, "camara_legislative_tramitacoes")
    assert statements == ["camara_legislative_history"]


@pytest.mark.integration
def test_events_are_projected_idempotently_in_isolated_schema(
    integration_database, configuration, archive_factory, candidate_row, tmp_path
):
    from uuid import uuid4

    from test_camara_crawler import ingest_rows
    from test_database_integration import start_repository

    from crawlers.camara.configuration import PARSER_VERSION, SOURCE, CrawlerConfiguration
    from crawlers.camara.normalization import normalize_proposition
    from crawlers.tse.validator import validate_resource
    from service.ingestion.repository import IngestionRepository
    from service.ingestion.sql_batches import SqlBatchWriter
    from storage.validation_index import ValidationIndex

    tse = start_repository(integration_database)
    index = ValidationIndex(tmp_path / "history.sqlite")
    repository = IngestionRepository(
        integration_database,
        SOURCE,
        CamaraProjectionWriter(SqlBatchWriter(integration_database)),
        parser_version=PARSER_VERSION,
    )
    repository.begin_run(str(uuid4()), {"test": True})
    try:
        tse.ingest_validated_artifact(
            validate_resource(archive_factory("candidate", [candidate_row]), configuration, index),
            500,
        )
        person_id = str(
            integration_database.execute("SELECT id FROM se_liga_brasil.person").fetchone()["id"]
        )
        config = CrawlerConfiguration(tmp_path)
        detail = {"uri": PROPOSITION, "siglaTipo": "PL", "numero": 1, "ano": 2026}
        ingest_rows(
            repository, config, "camara_propositions", [normalize_proposition(detail, person_id)]
        )
        row = {"sequencia": 1, "dataHora": "2026-01-02T12:30", "despacho": "Aprovado em comissão"}
        fact = normalize_proceeding(row, PROPOSITION)
        ingest_rows(repository, config, "camara_legislative_tramitacoes", [fact])
        result = integration_database.execute(
            "SELECT count(*) AS total FROM se_liga_brasil.proposition_event"
        ).fetchone()
        assert result["total"] == 1
        status = integration_database.execute(
            "SELECT current_status FROM se_liga_brasil.proposition"
        ).fetchone()
        assert status["current_status"] == "unknown"
    finally:
        index.close()
        repository.finish_run("completed", {})
        tse.finish_run("completed", {})


def test_author_staging_can_retry_after_identity_becomes_verified():
    from crawlers.camara.staging import staging_scope

    kind = "camara_legislative_autores"
    assert staging_scope(kind, []) != staging_scope(
        kind, [{"recordKey": "verified-internal-person"}]
    )
    assert staging_scope(kind, [{"recordKey": "one"}]) == staging_scope(
        kind, [{"recordKey": "one"}]
    )
