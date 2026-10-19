from datetime import date
from types import SimpleNamespace

import pytest

from crawlers.alerj.legislative import legislative_capability as alerj_capability
from crawlers.alesp.legislative import collect_proceedings, normalize_proceeding
from crawlers.alesp.legislative import legislative_capability as alesp_capability
from crawlers.senado.legislative import (
    collect_process_details,
    collect_votings,
    normalize_process,
    normalize_voting,
)
from service.ingestion.contracts import IngestionError

START = date(2024, 1, 1)
END = date(2024, 1, 31)


def test_unsupported_domains_and_empty_selection_require_no_transport():
    assert alerj_capability("votings", START, END)["status"] == "unsupported"
    assert alesp_capability("laws", START, END)["status"] == "unsupported"
    records, artifact = collect_proceedings(None, None, [], START, END)
    assert list(records) == [] and artifact is None


def test_process_collection_deduplicates_before_io_and_preserves_stages():
    calls = []

    def fetch(path, kind):
        calls.append(path)
        return {"id": 10, "sigla": "REQ", "situacaoAtual": "Aprovado"}, None

    result = list(collect_process_details(SimpleNamespace(json_document=fetch), [10, 10]))
    assert len(calls) == 1
    assert result[0][0]["kind"] == "REQ"
    assert result[0][0]["final_outcome"] is None


def test_process_batch_limit_fails_before_transport():
    with pytest.raises(IngestionError, match="BATCH_LIMIT"):
        list(collect_process_details(None, range(1, 102)))


def test_process_limit_stops_reading_oversized_input():
    consumed = []

    def identifiers():
        for key in range(1, 10000):
            consumed.append(key)
            yield key

    with pytest.raises(IngestionError, match="BATCH_LIMIT"):
        list(collect_process_details(None, identifiers(), max_processes=2))
    assert consumed == [1, 2, 3]


def test_process_schema_failure_is_not_empty_coverage():
    with pytest.raises(IngestionError, match="SCHEMA_CHANGED"):
        normalize_process({"error": "unavailable"})


def test_process_events_keep_body_and_unclassified_outcome():
    payload = {
        "id": 1,
        "sigla": "PL",
        "autuacoes": [
            {
                "informesLegislativos": [
                    {
                        "id": 2,
                        "data": "2024-01-03 00:00:00",
                        "descricao": "Aprovado requerimento",
                        "colegiado": {"sigla": "CCJ"},
                    }
                ]
            }
        ],
    }
    event = normalize_process(payload)["events"][0]
    assert event["occurred_on"] == "2024-01-03"
    assert event["body"] == "CCJ" and event["final_outcome"] is None


def test_secret_voting_never_produces_individual_votes():
    row = {
        "codigoSessaoVotacao": 1,
        "idProcesso": 2,
        "dataSessao": "2024-01-03",
        "votacaoSecreta": "S",
        "votos": [{"siglaVotoParlamentar": "Sim"}],
        "resultadoVotacao": "A",
        "totalVotosSim": 60,
    }
    normalized = normalize_voting(row)
    assert normalized["nominal_vote_evidence"] == []
    assert normalized["collective_result_code"] == "A"
    assert normalized["final_outcome"] is None


def test_voting_partition_bounds_fail_before_transport():
    with pytest.raises(IngestionError, match="INTERVAL_LIMIT"):
        collect_votings(None, START, date(2025, 1, 1))


def test_voting_transport_failure_propagates_without_complete_marker():
    def fetch(path, kind):
        raise IngestionError("SOURCE_RATE_LIMITED")

    with pytest.raises(IngestionError, match="SOURCE_RATE_LIMITED"):
        collect_votings(SimpleNamespace(json_document=fetch), START, END)


def test_alesp_document_events_are_stable_and_do_not_infer_approval():
    row = {
        "IdDocumento": "10",
        "Data": "03/01/2024",
        "NrOrdem": "1",
        "IdEtapa": "2",
        "Descricao": "Aprovado requerimento",
        "NmEtapa": "Comissão",
    }
    assert normalize_proceeding(row) == normalize_proceeding(row)
    assert normalize_proceeding(row)["final_outcome"] is None


def test_alesp_stream_filters_documents_and_dates(tmp_path):
    from crawlers.alesp.legislative import selected_proceedings

    path = tmp_path / "proceedings.xml"
    row = (
        "<DocumentoAndamento><IdDocumento>{}</IdDocumento><Data>{}</Data>"
        "<NrOrdem>1</NrOrdem><IdEtapa>2</IdEtapa><Descricao>Texto</Descricao>"
        "</DocumentoAndamento>"
    )
    path.write_text(
        "<root>"
        + row.format("10", "03/01/2024")
        + row.format("20", "04/01/2024")
        + row.format("10", "01/02/2024")
        + "</root>"
    )
    events = list(selected_proceedings(path, {"10"}, START, END))
    assert len(events) == 1 and events[0]["proposition_source_key"] == "10"
