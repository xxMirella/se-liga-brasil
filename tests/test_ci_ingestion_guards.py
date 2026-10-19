"""Transport, staging and audit failures stay bounded and provenance-aware."""

from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock

import httpx
import pytest

from crawlers.tse import validator
from service.acquisition import http_client
from service.completeness import assessment
from service.crawling import ingestion
from service.ingestion import sql_batches
from service.ingestion.contracts import IngestionError, IngestionSummary, Resource


class BatchConnection:
    def __init__(self):
        self.events = []
        self.execute = Mock(return_value=self)

    @contextmanager
    def pipeline(self):
        self.events.append("pipeline")
        yield

    def fetchall(self):
        return [{"classification": "new", "count": 2}, {"classification": "stale", "count": 1}]


def test_sql_batches_cache_statements_and_keep_bind_parameters(monkeypatch):
    reader = Mock(return_value="-- header\nSELECT %(value)s;\n-- comment\nSELECT 2; ;")
    monkeypatch.setattr(sql_batches, "read_sql_file", reader)
    connection = BatchConnection()
    writer = sql_batches.SqlBatchWriter(connection)
    writer.execute_statements("reconcile", {"value": "safe-bound-value"})
    writer.execute_statements("reconcile", {"value": "second-value"})
    reader.assert_called_once_with("ingestion/reconcile.sql")
    assert connection.execute.call_count == 4
    assert connection.execute.call_args_list[0].args == (
        "SELECT %(value)s",
        {"value": "safe-bound-value"},
    )
    assert connection.events == ["pipeline", "pipeline"]
    assert writer.summarize_batch() == {"new": 2, "stale": 1}


def resource():
    return Resource(
        "official-id",
        "Official Dataset",
        "https://official.example/data",
        "candidate",
        2024,
        "dataset",
    )


def test_validation_rejections_keep_structured_context_without_raw_payload(monkeypatch):
    report = Mock()
    monkeypatch.setattr(ingestion, "report_rejection", report)
    monkeypatch.setattr(
        ingestion,
        "read_json_lines",
        lambda path: iter(
            [
                {
                    "reasonCode": "INVALID_DATE",
                    "entryName": "data.csv",
                    "rowNumber": 8,
                    "details": {"column": "date"},
                    "raw_payload": "must never be logged",
                }
            ]
        ),
    )
    ingestion.report_validation_rejections(
        SimpleNamespace(rejected_path="unused", artifact=SimpleNamespace(resource=resource()))
    )
    assert report.call_args.args[1:] == (
        "validate",
        "INVALID_DATE",
        "data.csv",
        8,
        {"column": "date"},
    )


def test_ingestion_failure_is_reported_and_later_resources_continue(monkeypatch):
    first, second = (
        resource(),
        Resource("second", "Second", "https://official.example/second", "asset", 2024, "dataset"),
    )
    plans = [
        SimpleNamespace(artifact=SimpleNamespace(resource=r), summary={"valid": 1})
        for r in (first, second)
    ]
    repo = Mock()
    repo.ingest_validated_artifact.side_effect = [
        IngestionError("INVALID_DATE"),
        IngestionSummary(new=1, rejected=1),
    ]
    repo.iter_resource_rejections.return_value = [
        {
            "reason_code": "IDENTITY_CONFLICT",
            "entry_name": "data.csv",
            "row_number": 4,
            "details": {"field": "birth_date"},
        }
    ]
    emit = Mock()
    monkeypatch.setattr(ingestion, "emit_event", emit)
    failures = []
    results = ingestion.ingest_validation_plan(
        SimpleNamespace(batch_size=10), repo, plans, failures
    )
    assert len(results) == 1 and results[0]["resource_id"] == "second"
    assert failures[0]["code"] == "INVALID_DATE"
    repo.reject_resource.assert_called_once()
    rejection = next(call for call in emit.call_args_list if call.args == ("rejected",))
    assert rejection.kwargs["stage"] == "ingest" and rejection.kwargs["uf"] == "BR"
    assert rejection.kwargs["context"] == {"field": "birth_date"}


def test_completeness_persists_full_report_but_returns_no_person_details(monkeypatch, tmp_path):
    report = {"people": [{"person_id": "one"}], "total_people": 1, "complete_people": 0}
    refresh = Mock()
    monkeypatch.setattr(assessment, "refresh_current_public_offices", refresh)
    monkeypatch.setattr(assessment, "fetch_completeness_rows", Mock(return_value=[]))
    monkeypatch.setattr(assessment, "build_completeness_report", Mock(return_value=report))
    monkeypatch.setattr(assessment, "overlay_career_batches", Mock(return_value=report))
    persist = Mock(return_value={"queued": 1})
    monkeypatch.setattr(assessment, "persist_data_gaps", persist)
    monkeypatch.setattr(assessment, "purge_processed_gaps", Mock(return_value={"purged": 0}))
    save = Mock()
    monkeypatch.setattr(assessment, "save_json", save)
    result = assessment.assess_completeness("db", tmp_path, "one")
    assert "people" not in result and result["queued"] == 1
    persist.assert_called_once_with("db", report)
    save.assert_called_once_with(tmp_path / "people/one/completeness.json", report)
    refresh.assert_called_once_with("db")


def test_career_assessment_batches_people_without_losing_any_results(monkeypatch):
    people = [{"person_id": str(index)} for index in range(1001)]

    def assess(connection, ids, today):
        return {"assessments": {person_id: "assessed" for person_id in ids}}

    collect = Mock(side_effect=assess)
    monkeypatch.setattr(assessment, "assess_career_coverage", collect)
    overlay = Mock(return_value="report")
    monkeypatch.setattr(assessment, "overlay_political_activity_coverage", overlay)
    assert assessment.overlay_career_batches("db", {"people": people}, date(2024, 1, 1)) == "report"
    assert [len(call.args[1]) for call in collect.call_args_list] == [1000, 1]
    assert len(overlay.call_args.args[1]) == 1001


@pytest.mark.parametrize(
    ("error", "attempt", "attempts", "delay", "postponed"),
    [
        (httpx.ConnectError("offline"), 0, 3, 0.5, False),
        (httpx.ConnectError("offline"), 2, 3, None, False),
        (
            IngestionError("HTTP_ERROR", {"retryable": True, "retry_after_seconds": 3}),
            0,
            3,
            3,
            False,
        ),
        (
            IngestionError("HTTP_ERROR", {"retryable": True, "retry_after_seconds": 90}),
            0,
            3,
            None,
            True,
        ),
        (IngestionError("HTTP_ERROR", {"status": 503, "retryable": True}), 2, 3, None, True),
        (IngestionError("UNTRUSTED_RESOURCE_URL"), 0, 3, None, False),
    ],
)
def test_http_backoff_obeys_retry_budget_and_defers_long_waits(
    monkeypatch, error, attempt, attempts, delay, postponed
):
    postpone = Mock()
    monkeypatch.setattr(http_client, "postpone_official_host", postpone)
    assert http_client.retry_delay(error, attempt, attempts, "https://official.example") == delay
    assert postpone.called is postponed


def test_http_transport_retries_then_closes_response_even_if_consumer_fails(monkeypatch):
    client = http_client.OfficialHttpClient(SimpleNamespace(max_attempts=2), Mock(), frozenset())
    response = Mock()
    monkeypatch.setattr(
        client,
        "_follow_official_redirects",
        Mock(side_effect=[httpx.ConnectError("offline"), response]),
    )
    sleep = Mock()
    monkeypatch.setattr(http_client.time, "sleep", sleep)
    with pytest.raises(RuntimeError, match="consumer"), client.stream_response("url"):
        raise RuntimeError("consumer")
    sleep.assert_called_once_with(0.5)
    response.close.assert_called_once()


def test_http_byte_limit_closes_response_on_oversized_body(monkeypatch):
    response = Mock()
    response.iter_bytes.return_value = iter([b"123", b"456"])
    client = http_client.OfficialHttpClient(SimpleNamespace(max_attempts=1), Mock(), frozenset())
    monkeypatch.setattr(client, "_open_response", Mock(return_value=response))
    with pytest.raises(IngestionError, match="RESOURCE_DOWNLOAD_LIMIT_EXCEEDED"):
        client.fetch_bytes("url", max_bytes=5)
    response.close.assert_called_once()


@pytest.mark.parametrize(
    ("kind", "row", "expected"),
    [
        ("candidate", {"CD_CARGO": "7", "SG_UF": "SP"}, False),
        ("candidate", {"CD_CARGO": "6", "SG_UF": "RJ"}, False),
        ("candidate", {"CD_CARGO": "6", "SG_UF": "SP"}, True),
        (
            "history",
            {
                "ANO_ELEICAO_ATUAL": "2024",
                "SQ_CANDIDATO_ATUAL": "x",
                "SG_UF_ATUAL": "SP",
                "SG_UF": "RJ",
            },
            False,
        ),
        ("complement", {"ANO_ELEICAO": "2024", "SQ_CANDIDATO": "x"}, True),
        ("asset", {"ANO_ELEICAO": "2024", "SQ_CANDIDATO": "x"}, True),
    ],
)
def test_validation_scope_uses_candidate_index_for_dependent_resources(kind, row, expected):
    index = Mock()
    index.has_candidate.return_value = True
    session = SimpleNamespace(
        artifact=SimpleNamespace(resource=SimpleNamespace(kind=kind)),
        configuration=SimpleNamespace(ufs=("SP",), office_codes=("6",)),
        index=index,
    )
    assert validator.is_row_selected(row, session) is expected


def test_validator_identity_scope_can_skip_valid_but_unrequested_person(monkeypatch):
    session = SimpleNamespace(
        configuration=SimpleNamespace(allows_identity=lambda record: False),
        artifact=SimpleNamespace(resource=SimpleNamespace(kind="candidate")),
        index=Mock(),
        identity_builder=None,
        summary={"skipped": 0},
        accept_record=Mock(),
    )
    monkeypatch.setattr(validator, "is_row_selected", Mock(return_value=True))
    monkeypatch.setattr(validator, "normalize_row", Mock(return_value={"normalizedData": {}}))
    monkeypatch.setattr(validator, "build_record_context", Mock(return_value={}))
    validator.validate_csv_row({}, "data.csv", 2, session)
    assert session.summary["skipped"] == 1
    session.accept_record.assert_not_called()


def test_document_validation_quarantines_incomplete_documents(
    monkeypatch,
):
    archive = Mock()
    archive.open.return_value.__enter__ = Mock(return_value="stream")
    archive.open.return_value.__exit__ = Mock(return_value=False)
    entry = SimpleNamespace(filename="proposal.pdf")
    session = SimpleNamespace(
        artifact="artifact",
        configuration="configuration",
        reject_record=Mock(),
        accept_record=Mock(),
    )
    error = IngestionError("DOCUMENT_TOO_LARGE")
    monkeypatch.setattr(validator, "stage_document", Mock(side_effect=error))
    validator.validate_document_entry(archive, entry, session)
    session.reject_record.assert_called_once_with(
        error, "proposal.pdf", None, {"entry_name": "proposal.pdf"}
    )
    session.accept_record.assert_not_called()


def test_csv_validation_emits_bounded_progress_and_delegates_all_rows(monkeypatch):
    archive = Mock()
    archive.open.return_value.__enter__ = Mock(return_value="stream")
    archive.open.return_value.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(validator, "read_csv_rows", Mock(return_value=[(9999, {}), (10000, {})]))
    emit = Mock()
    monkeypatch.setattr(validator, "emit_event", emit)
    validate = Mock()
    monkeypatch.setattr(validator, "validate_csv_row", validate)
    session = SimpleNamespace(artifact=SimpleNamespace(resource=SimpleNamespace(kind="candidate")))
    validator.validate_csv_entry(archive, SimpleNamespace(filename="data.csv"), session)
    assert validate.call_count == 2
    emit.assert_called_once_with("validate_progress", entry_name="data.csv", rows_scanned=10000)


def test_validation_rolls_back_scope_savepoint_when_archive_validation_fails(monkeypatch, tmp_path):
    archive = tmp_path / "source.zip"
    archive.write_bytes(b"raw")
    from storage.files import hash_file

    artifact = SimpleNamespace(
        path=archive, sha256=hash_file(archive), resource=SimpleNamespace(resource_id="source")
    )
    config = SimpleNamespace(scope_key="scope", storage_directory=tmp_path)
    index = Mock()
    monkeypatch.setattr(
        validator, "write_validation_files", Mock(side_effect=IngestionError("BAD_ZIP"))
    )
    with pytest.raises(IngestionError, match="BAD_ZIP"):
        validator.validate_resource(artifact, config, index)
    assert [call.args[0] for call in index.connection.execute.call_args_list] == [
        "SAVEPOINT validate_resource",
        "ROLLBACK TO SAVEPOINT validate_resource",
        "RELEASE SAVEPOINT validate_resource",
    ]
