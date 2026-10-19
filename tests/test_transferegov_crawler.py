"""Official-shape anonymous fixtures; no production writes or network calls."""

import json
from dataclasses import replace
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest

from crawlers.transferegov.acquisition import TransferegovAcquisition, partition_query
from crawlers.transferegov.configuration import OFFICIAL_HOSTS, CrawlerConfiguration
from crawlers.transferegov.identity import (
    ReviewedParticipation,
    attach_reviewed_participation,
    index_reviewed_participations,
)
from crawlers.transferegov.normalization import normalize_payment_order, normalize_proposal
from crawlers.transferegov.pipeline import collect_records
from service.acquisition.http_client import OfficialHttpClient
from service.ingestion.contracts import IngestionError


def acquisition_fixture(tmp_path, responder, **limits):
    configuration = replace(
        CrawlerConfiguration(tmp_path, request_min_interval_seconds=0), **limits
    )
    client = httpx.Client(transport=httpx.MockTransport(responder))
    transport = OfficialHttpClient(configuration, client, OFFICIAL_HOSTS)
    return TransferegovAcquisition(configuration, transport)


def envelope(rows, page=1, pages=1, size=100):
    return {
        "data": rows,
        "page_number": page,
        "total_pages": pages,
        "total_items": len(rows),
        "page_size": size,
    }


def test_shared_cache_avoids_repeat_http_and_preserves_original(tmp_path):
    requests = []

    def responder(request):
        requests.append(request)
        return httpx.Response(200, json=envelope([{"id_parceria": 1, "id_proposta": 2}]))

    acquisition = acquisition_fixture(tmp_path, responder)
    first = list(acquisition.pages("parcerias", "parceria", {"id_parceria": 1}))
    second = list(acquisition.pages("parcerias", "parceria", {"id_parceria": 1}))
    assert len(requests) == 1
    assert first[0][1].sha256 == second[0][1].sha256
    assert second[0][1].acquisition_status == "cached"
    assert first[0][1].path.read_bytes() == second[0][1].path.read_bytes()


def test_deduplication_across_people_partitions_and_records(tmp_path):
    requests = []

    def responder(request):
        requests.append(request)
        return httpx.Response(200, json=envelope([{"id_parceria": 1, "id_proposta": 2}]))

    acquisition = acquisition_fixture(tmp_path, responder)
    partitions = [{"id_proposta": 2}, {"id_proposta": 2}, {"id_parceria": 1}]
    records = list(collect_records(acquisition, "parcerias", "parceria", partitions))
    assert len(requests) == 2
    assert len(records) == 1
    assert records[0]["signed_on"] is None


def test_page_limit_signals_incomplete_coverage(tmp_path):
    acquisition = acquisition_fixture(
        tmp_path,
        lambda request: httpx.Response(200, json=envelope([{"id_parceria": 1}], pages=2)),
        max_pages=1,
    )
    with pytest.raises(IngestionError, match="PAGE_LIMIT_EXCEEDED"):
        list(acquisition.pages("parcerias", "parceria", {"id_parceria": 1}))


def test_repeated_page_cursor_is_rejected(tmp_path):
    acquisition = acquisition_fixture(
        tmp_path, lambda request: httpx.Response(200, json=envelope([{"id_parceria": 1}], pages=2))
    )
    with pytest.raises(IngestionError, match="PAGINATION_DRIFT"):
        list(acquisition.pages("parcerias", "parceria", {"id_parceria": 1}))


@pytest.mark.parametrize("filters", [{}, {"nome_parlamentar": "Exemplo"}, {"id_proposta": None}])
def test_invalid_filters_fail_without_requests(filters):
    with pytest.raises(IngestionError):
        partition_query("parcerias", "parceria", filters)


def test_numeric_decimal_does_not_pass_through_float(tmp_path):
    content = (
        '{"data":[{"id_op":1,"id_documento_habil":2,"vl_ordem_pagamento":100.10}],'
        '"page_number":1,"total_pages":1,"total_items":1,"page_size":100}'
    )
    acquisition = acquisition_fixture(
        tmp_path, lambda request: httpx.Response(200, content=content)
    )
    rows, _ = next(acquisition.pages("parcerias", "ordem-pagamento", {"id_op": 1}))
    payment = normalize_payment_order(rows[0])
    assert payment["ordered_amount"] == "100.10"
    assert payment["executed_amount"] is None


def test_budget_rejects_oversize_artifact(tmp_path):
    acquisition = acquisition_fixture(
        tmp_path,
        lambda request: httpx.Response(200, content=json.dumps(envelope([])).encode()),
        max_download_bytes=5,
    )
    with pytest.raises(IngestionError, match="DOWNLOAD_LIMIT_EXCEEDED"):
        list(acquisition.pages("parcerias", "parceria", {"id_parceria": 1}))
    assert not list(tmp_path.rglob("*.part"))


def test_order_is_not_executed_and_snapshot_has_no_fabricated_validity():
    proposal = normalize_proposal({"id_proposta": 1, "nr_vlr_total": "100.00"})
    assert proposal["valid_from"] is None and proposal["valid_until"] is None
    assert proposal["organizations"] == []


def test_reviewed_identity_is_bound_to_artifact_and_never_executor():
    participation = ReviewedParticipation(
        UUID(int=1), "1", "a" * 64, "amendment_author", "review:1"
    )
    indexed = index_reviewed_participations([participation])
    record = {"record_key": "1", "source_sha256": "a" * 64}
    assert attach_reviewed_participation(record, indexed)["person_id"] == str(UUID(int=1))
    assert (
        attach_reviewed_participation(record | {"source_sha256": "b" * 64}, indexed)["person_id"]
        is None
    )
    with pytest.raises(IngestionError, match="UNPROVEN_PERSONAL_ROLE"):
        index_reviewed_participations([replace(participation, role="executor")])


def test_record_and_partition_limits_are_explicit(tmp_path):
    acquisition = SimpleNamespace(configuration=CrawlerConfiguration(tmp_path, max_records=0))
    acquisition.pages = lambda *args: iter([([{"id_parceria": 1, "id_proposta": 2}], None)])
    with pytest.raises(IngestionError, match="RECORD_LIMIT_EXCEEDED"):
        list(collect_records(acquisition, "parcerias", "parceria", [{"id_parceria": 1}]))
    acquisition.configuration = replace(acquisition.configuration, max_partitions=0)
    with pytest.raises(IngestionError, match="PARTITION_LIMIT_EXCEEDED"):
        list(collect_records(acquisition, "parcerias", "parceria", [{"id_parceria": 1}]))


def test_shared_transport_retries_server_error(tmp_path, monkeypatch):
    monkeypatch.setattr("service.acquisition.http_client.time.sleep", lambda delay: None)
    requests = []

    def responder(request):
        requests.append(request)
        if len(requests) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json=envelope([], pages=0))

    acquisition = acquisition_fixture(tmp_path, responder)
    assert list(acquisition.pages("parcerias", "parceria", {"id_parceria": 1}))[0][0] == []
    assert len(requests) == 2


def test_conflicting_snapshot_requires_recollection(tmp_path):
    artifact = SimpleNamespace(
        resource=SimpleNamespace(url="https://example.invalid"),
        sha256="a" * 64,
        fetched_at="2026-10-17T00:00:00Z",
    )
    acquisition = SimpleNamespace(configuration=CrawlerConfiguration(tmp_path))
    acquisition.pages = lambda *args: iter(
        [
            ([{"id_parceria": 1, "id_proposta": 2}], artifact),
            ([{"id_parceria": 1, "id_proposta": 3}], artifact),
        ]
    )
    with pytest.raises(IngestionError, match="SNAPSHOT_CONFLICT"):
        list(collect_records(acquisition, "parcerias", "parceria", [{"id_parceria": 1}]))
