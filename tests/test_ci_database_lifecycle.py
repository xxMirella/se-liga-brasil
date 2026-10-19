"""Offline database boundary tests: no credentials, sockets or production writes."""

from contextlib import contextmanager
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from psycopg.conninfo import conninfo_to_dict

from database import operations
from service.ingestion import repository
from service.ingestion.contracts import (
    DownloadedArtifact,
    IngestionError,
    IngestionSummary,
    Resource,
    SourceDescriptor,
    ValidatedArtifact,
)
from storage.files import hash_content, hash_file


class RecordingConnection:
    def __init__(self, rows=()):
        self.rows = iter(rows)
        self.calls = []
        self.events = []

    def execute(self, sql, parameters=None):
        self.calls.append((sql, parameters))
        return self

    def fetchone(self):
        return next(self.rows)

    def fetchall(self):
        return next(self.rows)

    @contextmanager
    def transaction(self):
        self.events.append("begin")
        try:
            yield
        except Exception:
            self.events.append("rollback")
            raise
        else:
            self.events.append("commit")


@pytest.fixture
def staged(tmp_path):
    archive, records, rejected = [tmp_path / name for name in ("raw", "records", "rejected")]
    archive.write_bytes(b"immutable original")
    records.write_text("", encoding="utf-8")
    rejected.write_text("", encoding="utf-8")
    resource = Resource("r", "test", "https://official.example/data", "candidate", 2024, "d")
    downloaded = DownloadedArtifact(resource, archive, hash_file(archive), "2024-01-01", 18)
    return ValidatedArtifact(
        downloaded,
        records,
        rejected,
        hash_file(records),
        hash_file(rejected),
        "scope",
        {"valid": 2},
    )


def ingestion(connection):
    source = SourceDescriptor("test", "Official Publisher", "https://official.example")
    return repository.IngestionRepository(connection, source, Mock())


@pytest.mark.parametrize("value", ["", "https://project.supabase.co", "sqlite:///local"])
def test_connection_rejects_non_postgres_configuration_without_connecting(monkeypatch, value):
    monkeypatch.setenv("DATABASE_URL", value)
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    connect = Mock()
    monkeypatch.setattr(operations.psycopg, "connect", connect)
    with pytest.raises(IngestionError, match="POSTGRES_CONNECTION_REQUIRED"):
        operations.connect_database()
    connect.assert_not_called()


def test_connection_uses_session_pooler_for_advisory_locks(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://ci:dummy@x.pooler.supabase.com:6543/db")
    monkeypatch.setattr(operations, "load_dotenv", Mock())
    connect = Mock(return_value="connection")
    monkeypatch.setattr(operations.psycopg, "connect", connect)
    assert operations.connect_database(tmp_path / "test.env") == "connection"
    args, kwargs = connect.call_args
    assert conninfo_to_dict(args[0])["port"] == "5432"
    assert kwargs["prepare_threshold"] is None
    assert kwargs["autocommit"] is True
    operations.load_dotenv.assert_called_once_with(tmp_path / "test.env", override=False)


@pytest.mark.parametrize(
    "url", ["postgresql://ci@localhost:6543/db", "postgresql://ci@x.pooler.supabase.com:5432/db"]
)
def test_non_transaction_pooler_connections_remain_unchanged(url):
    assert operations.session_connection_string(url) == url


@pytest.mark.parametrize(
    ("tables", "rls", "exposed", "error"),
    [
        (46, 45, 0, "SCHEMA_VERIFICATION_FAILED"),
        (999, 999, 0, "SCHEMA_VERIFICATION_FAILED"),
        (46, 46, 1, "SCHEMA_UNEXPECTEDLY_PUBLIC"),
    ],
)
def test_schema_verification_fails_closed(tables, rls, exposed, error):
    connection = RecordingConnection(
        [{"tables": tables, "rls_tables": rls}, {"exposed_roles": exposed}]
    )
    with pytest.raises(IngestionError, match=error):
        operations.verify_schema(connection)


def test_schema_verification_accepts_private_rls_schema():
    connection = RecordingConnection([{"tables": 46, "rls_tables": 46}, {"exposed_roles": 0}])
    assert operations.verify_schema(connection)["exposed_roles"] == 0


MIGRATION_APPLIERS = [
    "apply_internal_identity_schema",
    "apply_parliamentary_enrichment_schema",
    "apply_data_gap_schema",
    "apply_source_policy_schema",
    "apply_gap_cleanup_schema",
    "apply_person_public_office_schema",
    "apply_collection_routes_schema",
    "apply_optional_proposition_number_schema",
    "apply_business_relationship_schema",
    "apply_legislative_voting_schema",
    "apply_career_receipt_schema",
    "apply_voting_refresh_queue_schema",
    "apply_office_legal_scope_schema",
]


@pytest.mark.parametrize("name", MIGRATION_APPLIERS)
@pytest.mark.parametrize("installed", [True, False])
def test_migrations_are_idempotent_and_strip_nested_transactions(monkeypatch, name, installed):
    connection = RecordingConnection([{"installed": installed, "nullable": installed}])
    read = Mock(return_value="-- migration\nBEGIN;\nCREATE TABLE example(id int);\nCOMMIT;\n")
    monkeypatch.setattr(operations, "read_sql_file", read)
    assert getattr(operations, name)(connection) is (not installed)
    if installed:
        read.assert_not_called()
        assert len(connection.calls) == 1
    else:
        read.assert_called_once()
        assert "BEGIN;" not in connection.calls[-1][0]
        assert "COMMIT;" not in connection.calls[-1][0]


def test_extension_migrations_do_not_short_circuit_after_first_change(monkeypatch):
    names = ["apply_payroll_schema", *MIGRATION_APPLIERS]
    calls = []
    for name in names:
        monkeypatch.setattr(
            operations, name, lambda connection, name=name: calls.append(name) or True
        )
    assert operations.apply_ingestion_extensions(object()) is True
    assert calls == names


def test_migration_failure_rolls_back_and_holds_lock_before_schema_check(monkeypatch):
    connection = RecordingConnection([{"installed": False}])
    monkeypatch.setattr(operations, "read_sql_file", Mock(side_effect=RuntimeError("migration")))
    with pytest.raises(RuntimeError, match="migration"):
        operations.apply_ingestion_schema(connection)
    assert "pg_advisory_xact_lock" in connection.calls[0][0]
    assert connection.events == ["begin", "rollback"]


def test_profile_refresh_has_transaction_scoped_timeouts():
    connection = RecordingConnection()
    operations.refresh_person_profiles(connection)
    assert connection.events == ["begin", "commit"]
    assert "statement_timeout" in connection.calls[0][0]
    assert "lock_timeout" in connection.calls[1][0]
    assert "REFRESH MATERIALIZED VIEW" in connection.calls[2][0]


def test_changed_staging_file_is_rejected_before_any_database_write(staged):
    connection = RecordingConnection()
    staged.records_path.write_text("tampered", encoding="utf-8")
    with pytest.raises(IngestionError, match="VALIDATION_CHECKSUM_MISMATCH"):
        ingestion(connection).ingest_validated_artifact(staged, 100)
    assert connection.calls == []


def test_wrong_parser_is_rejected_before_any_database_write(staged):
    connection = RecordingConnection()
    with pytest.raises(IngestionError, match="PARSER_VERSION_MISMATCH"):
        ingestion(connection).ingest_validated_artifact(replace(staged, parser_version="old"), 100)
    assert connection.calls == []


def test_completed_artifact_replay_does_not_project_again(staged):
    connection = RecordingConnection([{"id": 8, "status": "completed"}])
    repo = ingestion(connection)
    summary = repo.ingest_validated_artifact(staged, 100)
    assert summary.skipped_artifact and summary.unchanged == 2
    repo.projector.project_batch.assert_not_called()
    assert connection.events == []


def test_projection_failure_rolls_back_without_marking_artifact_completed(staged, monkeypatch):
    connection = RecordingConnection([None, {"id": 8}])
    repo = ingestion(connection)
    monkeypatch.setattr(repo, "ingest_staged_batches", Mock(side_effect=RuntimeError("projection")))
    with pytest.raises(RuntimeError, match="projection"):
        repo.ingest_validated_artifact(staged, 100)
    assert connection.events == ["begin", "rollback"]
    assert not any("SET status=%s,ingested_at" in sql for sql, _ in connection.calls)


def test_artifact_with_rejections_remains_partial_and_successfully_commits(staged, monkeypatch):
    connection = RecordingConnection([None, {"id": 8}, {"count": 2}])
    repo = ingestion(connection)
    monkeypatch.setattr(repo, "ingest_staged_batches", Mock(return_value=IngestionSummary(new=2)))
    summary = repo.ingest_validated_artifact(staged, 100)
    assert summary.rejected == 2
    status_calls = [
        params for sql, params in connection.calls if "SET status=%s,ingested_at" in sql
    ]
    assert status_calls[0][0] == "partial"
    assert connection.events == ["begin", "commit"]
    assert "DROP TABLE" in connection.calls[-1][0]


def test_run_lock_contention_cannot_interrupt_another_run():
    connection = RecordingConnection([{"acquired": False}])
    repo = ingestion(connection)
    with pytest.raises(IngestionError, match="CRAWLER_ALREADY_RUNNING_IN_DATABASE"):
        repo.begin_run("run", {})
    assert len(connection.calls) == 1
    assert repo.run_id is None


def test_run_lifecycle_tags_source_and_releases_session_lock():
    connection = RecordingConnection([{"acquired": True}, {"id": 17}])
    repo = ingestion(connection)
    repo.begin_run("run", {"source_code": "untrusted"})
    assert repo.source_id == 17 and repo.run_id == "run"
    configuration = connection.calls[2][1][1].obj
    assert configuration["source_code"] == "test"
    repo.finish_run("completed", {"new": 1})
    assert "pg_advisory_unlock" in connection.calls[-1][0]


def test_record_hash_excludes_location_but_still_validates_document_bytes(tmp_path):
    document = tmp_path / "original.pdf"
    document.write_bytes(b"official content")
    data = {"documentSha256": hash_file(document), "storageReference": str(document)}
    record = {
        "normalizedData": data,
        "contentSha256": hash_content({"documentSha256": data["documentSha256"]}),
    }
    repository.verify_staged_record(record)
    document.write_bytes(b"changed bytes")
    with pytest.raises(IngestionError, match="DOCUMENT_CHECKSUM_MISMATCH"):
        repository.verify_staged_record(record)
    with pytest.raises(IngestionError, match="STAGED_RECORD_HASH_MISMATCH"):
        repository.verify_staged_record(record | {"contentSha256": "bad"})


def test_rejections_use_keyset_pagination_and_preserve_resource_scope():
    rows = [[{"id": 3}, {"id": 10}], [{"id": 12}], []]
    connection = RecordingConnection(rows)
    repo = ingestion(connection)
    repo.run_id = "run"
    assert [row["id"] for row in repo.iter_resource_rejections("resource")] == [3, 10, 12]
    assert [params for _, params in connection.calls] == [
        ("run", "resource", 0),
        ("run", "resource", 10),
        ("run", "resource", 12),
    ]


def test_stale_classification_survives_projection_reclassification(monkeypatch):
    connection = RecordingConnection()
    repo = ingestion(connection)
    record = {
        "normalizedData": {"name": "Example"},
        "contentSha256": hash_content({"name": "Example"}),
    }
    monkeypatch.setattr(repository, "read_json_lines", lambda path: iter([record, record]))
    repo.batch_writer = Mock()
    repo.batch_writer.summarize_batch.side_effect = [
        {"stale": 1, "new": 1},
        {"unchanged": 1, "new": 1},
    ]
    repo.progress = Mock()
    validated = SimpleNamespace(
        records_path="unused",
        summary={"valid": 2},
        artifact=SimpleNamespace(resource=SimpleNamespace(kind="candidate")),
    )
    summary = repo.ingest_staged_batches(validated, {}, 10)
    assert summary.stale == 1 and summary.new == 1 and summary.unchanged == 1
    repo.progress.assert_called_once_with("ingest_progress", processed_records=2, total_records=2)


@pytest.mark.parametrize("installed", [True, False])
def test_base_schema_checks_all_migrations_under_one_transaction(monkeypatch, installed):
    connection = RecordingConnection(
        [{"installed": installed}, {"installed": installed}, {"installed": not installed}]
    )
    reader = Mock(return_value="BEGIN; SELECT 'migration'; COMMIT;")
    monkeypatch.setattr(operations, "read_sql_file", reader)
    extensions = Mock(return_value=False)
    monkeypatch.setattr(operations, "apply_ingestion_extensions", extensions)
    assert operations.apply_ingestion_schema(connection) is (not installed)
    extensions.assert_called_once_with(connection)
    assert reader.call_count == (0 if installed else 3)
    assert connection.events == ["begin", "commit"]


@pytest.mark.parametrize(("payroll", "quality"), [(True, True), (False, True), (True, False)])
def test_payroll_and_signed_asset_migrations_are_independent(monkeypatch, payroll, quality):
    connection = RecordingConnection([{"installed": payroll}, {"installed": quality}])
    reader = Mock(return_value="BEGIN; SELECT 1; COMMIT;")
    monkeypatch.setattr(operations, "read_sql_file", reader)
    assert operations.apply_payroll_schema(connection) is (not (payroll and quality))
    assert reader.call_count == int(not payroll) + int(not quality)


def test_rejection_batches_are_bounded_and_keep_run_and_artifact_provenance(monkeypatch):
    connection = RecordingConnection()
    repo = ingestion(connection)
    records = [{"reasonCode": "INVALID_DATE", "rowNumber": index} for index in range(3)]
    monkeypatch.setattr(repository, "read_json_lines", lambda path: iter(records))
    repo.save_validation_rejections(
        SimpleNamespace(rejected_path="unused"), {"run_id": "run", "artifact_id": 42}, 2
    )
    payloads = [params for _, params in connection.calls]
    assert [len(params["rejections"].obj) for params in payloads] == [2, 1]
    assert all(params["run_id"] == "run" and params["artifact_id"] == 42 for params in payloads)
    repo.run_id = "run"
    repo.reject_resource("resource", IngestionError("INVALID_DATE", {"column": "date"}))
    rejected = connection.calls[-1][1]
    assert rejected["artifact_id"] is None
    assert rejected["rejections"].obj == [
        {"resourceId": "resource", "reasonCode": "INVALID_DATE", "details": {"column": "date"}}
    ]
