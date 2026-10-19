"""Offline orchestration and destructive-reset safety contracts."""

from contextlib import contextmanager
from unittest.mock import Mock

import pytest

from database.data_reset import ProjectDataResetRepository
from service.ingestion.contracts import IngestionError
from service.orchestration import data_collection as orchestration


class ResetConnection:
    def __init__(self, tables=(), acquired=True, running=0, blocks=(b"id\n1\n",)):
        self.tables = tables
        self.acquired = acquired
        self.running = running
        self.blocks = blocks
        self.calls = []
        self.events = []
        self.last_sql = ""

    def execute(self, statement, parameters=None):
        self.last_sql = statement if isinstance(statement, str) else statement.as_string()
        self.calls.append((self.last_sql, parameters))
        return self

    def fetchall(self):
        return [{"tablename": name} for name in self.tables]

    def fetchone(self):
        if "advisory" in self.last_sql:
            return {"acquired": self.acquired}
        return {"total": self.running if "ingestion_run WHERE" in self.last_sql else 1}

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

    @contextmanager
    def cursor(self):
        yield self

    @contextmanager
    def copy(self, statement):
        self.calls.append((statement.as_string(), None))
        yield self.blocks


@pytest.fixture
def routed(monkeypatch):
    names = [
        "purge_processed_gaps",
        "route_data_gaps",
        "release_data_gaps",
        "defer_unmatched_institutional_people",
        "refresh_person_profiles",
        "save_json",
    ]
    mocks = {}
    for name in names:
        mocks[name] = Mock()
        monkeypatch.setattr(orchestration, name, mocks[name])
    monkeypatch.setattr(orchestration, "fetch_completeness_rows", Mock(return_value=[]))
    monkeypatch.setattr(orchestration, "fetch_enrichment_candidates", Mock(return_value=[]))
    monkeypatch.setattr(
        orchestration,
        "assess_completeness",
        Mock(return_value={"complete_people": 1, "total_people": 1, "missing_by_field": {}}),
    )
    return mocks


def test_group_requests_deduplicates_fields_and_preserves_source_boundaries():
    tasks = [{"assigned_source": "camara", "person_id": "p", "field_name": "salary"}] * 2
    tasks += [
        {"assigned_source": "camara", "person_id": "p", "field_name": "education"},
        {"assigned_source": "tse", "person_id": "p", "field_name": "education"},
    ]
    assert orchestration.group_source_requests(tasks) == {
        "camara": {"p": {"salary", "education"}},
        "tse": {"p": {"education"}},
    }


@pytest.mark.parametrize("source", ["tse", "alesp", "camara", "alerj", "senado", "tse_filiation"])
def test_source_delegation_is_batched_and_scoped_to_requested_people(monkeypatch, source):
    execute = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(orchestration, "execute_source_collection", execute)
    people = {"one": {"salary", "education"}}
    rows = [
        {"person_id": "one", "latest_election": 2024},
        {"person_id": "two", "latest_election": 2024},
    ]
    result = orchestration.collect_requested_source("db", "storage", source, people, rows, rows)
    assert result["status"] == "completed"
    execute.assert_called_once()
    arguments = execute.call_args.args
    assert all("two" not in repr(value) for value in arguments[2:])
    if source == "camara":
        assert arguments[-1][0]["requested_fields"] == ["education", "salary"]
    if source == "tse":
        assert arguments[-1] == [
            {"person_id": "one", "election_year": 2024, "fields": ["education", "salary"]}
        ]


def test_unknown_collector_is_explicitly_blocked():
    result = orchestration.collect_requested_source(None, None, "unknown", {}, [], [])
    assert result == {"status": "blocked", "failures": [{"code": "SOURCE_COLLECTOR_NOT_AVAILABLE"}]}


@pytest.mark.parametrize(
    ("result", "delay"),
    [
        ({"failures": []}, None),
        ({"status": "blocked", "failures": [{"code": "X"}]}, None),
        (
            {
                "failures": [
                    {"code": "RATE", "retry_after_seconds": 7200, "status": 429},
                    {"retry_after_seconds": 9000},
                ]
            },
            9000,
        ),
        ({"failures": [{}]}, 3600),
    ],
)
def test_source_cooldown_respects_maximum_retry_and_skips_permanent_blocks(
    monkeypatch, result, delay
):
    postpone = Mock()
    monkeypatch.setattr(orchestration, "postpone_source", postpone)
    orchestration.apply_source_cooldown("db", "camara", result)
    if delay is None:
        postpone.assert_not_called()
    else:
        assert postpone.call_args.args[:3] == ("db", "camara", delay)


def test_deferred_people_are_released_only_after_successful_source():
    connection = Mock()
    orchestration.release_deferred_people(
        connection,
        {
            "camara": {"deferred_person_ids": ["one"]},
            "tse": {"deferred_person_ids": ["two"], "failures": [{"code": "network"}]},
            "alesp": {},
        },
    )
    connection.execute.assert_called_once()
    assert connection.execute.call_args.args[1] == ("camara", ["one"])


@pytest.mark.parametrize(
    ("result", "fields", "error"),
    [
        ({"unsupported_fields": ["salary"]}, {"salary"}, "SOURCE_FIELD_NOT_SUPPORTED"),
        (
            {"status": "blocked", "failures": [{"code": "MISSING"}]},
            {"salary", "education"},
            "MISSING",
        ),
        ({"status": "blocked"}, {"salary", "education"}, "SOURCE_COLLECTOR_NOT_AVAILABLE"),
    ],
)
def test_unavailable_fields_are_blocked_without_losing_source_error(
    monkeypatch, result, fields, error
):
    block = Mock()
    monkeypatch.setattr(orchestration, "block_data_gaps", block)
    orchestration.block_unavailable_fields(
        "db", "worker", "camara", {"p": {"salary", "education"}}, result
    )
    assert set(block.call_args.args[3]) == fields
    assert block.call_args.args[4] == error


def test_no_due_tasks_preserves_cooldown_warning_and_avoids_collectors(
    monkeypatch, routed, tmp_path
):
    monkeypatch.setattr(orchestration, "claim_data_gaps", Mock(return_value=[]))
    collect = Mock()
    monkeypatch.setattr(orchestration, "collect_requested_source", collect)
    result = orchestration.orchestrate_collection("db", tmp_path, refresh_assessment=False)
    assert result["claimed_tasks"] == 0 and "cooldowns" in result["coverage_message"]
    collect.assert_not_called()
    routed["release_data_gaps"].assert_not_called()


def test_many_gaps_trigger_one_collection_per_source(monkeypatch, routed, tmp_path):
    tasks = [
        {"assigned_source": "camara", "person_id": "one", "field_name": field}
        for field in ("salary", "education")
    ]
    monkeypatch.setattr(orchestration, "claim_data_gaps", Mock(return_value=tasks))
    collect = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(orchestration, "collect_requested_source", collect)
    result = orchestration.orchestrate_collection("db", tmp_path, refresh_assessment=False)
    collect.assert_called_once()
    assert result["source_requests"] == {"camara": 1}
    assert result["status"] == "completed"
    routed["release_data_gaps"].assert_called_once()


@pytest.mark.parametrize(
    "failing_stage",
    [
        "collect_requested_source",
        "fetch_completeness_rows",
        "fetch_enrichment_candidates",
        "refresh_person_profiles",
        "assess_completeness",
    ],
)
def test_claimed_leases_are_released_on_every_post_claim_failure(
    monkeypatch, routed, tmp_path, failing_stage
):
    tasks = [{"assigned_source": "camara", "person_id": "one", "field_name": "salary"}]
    monkeypatch.setattr(orchestration, "claim_data_gaps", Mock(return_value=tasks))
    monkeypatch.setattr(orchestration, "collect_requested_source", Mock(return_value={}))
    monkeypatch.setattr(orchestration, failing_stage, Mock(side_effect=RuntimeError("failure")))
    with pytest.raises(RuntimeError, match="failure"):
        orchestration.orchestrate_collection("db", tmp_path, refresh_assessment=False)
    routed["release_data_gaps"].assert_called_once()


@pytest.mark.parametrize(
    "results",
    [
        {"x": {"status": "partial"}},
        {"x": {"deferred": 1}},
        {"x": {"unsupported": 1}},
        {"x": {"failures": [{}]}},
    ],
)
def test_collection_never_reports_complete_with_unresolved_source_outcomes(results):
    assert orchestration.collection_status({"complete_people": 1, "total_people": 1}, results) == (
        "partial"
    )


def test_missing_fields_override_inconsistent_complete_people_count():
    assert (
        orchestration.collection_status(
            {"complete_people": 1, "total_people": 1, "missing_by_field": {"salary": 1}}, {}
        )
        == "partial"
    )


def test_career_dispatch_is_optional_and_uses_collection_wrapper(monkeypatch):
    execute = Mock(return_value={"status": "partial"})
    monkeypatch.setattr(orchestration, "execute_source_collection", execute)
    results = {}
    orchestration.collect_career_resources("db", [], results, None)
    execute.assert_not_called()
    orchestration.collect_career_resources("db", [], results, {"camara": "collector"})
    assert results == {"career": {"status": "partial"}}


def test_reset_refuses_missing_schema_before_transaction(tmp_path):
    connection = ResetConnection()
    with pytest.raises(IngestionError, match="PROJECT_SCHEMA_NOT_FOUND"):
        ProjectDataResetRepository(connection, tmp_path).reset_project_data()
    assert connection.events == []


@pytest.mark.parametrize(
    ("acquired", "running", "error"),
    [
        (False, 0, "CRAWLER_ALREADY_RUNNING_IN_DATABASE"),
        (True, 1, "RUNNING_INGESTION_PREVENTS_RESET"),
    ],
)
def test_reset_refuses_active_ingestion_and_rolls_back(tmp_path, acquired, running, error):
    connection = ResetConnection(["person"], acquired, running)
    with pytest.raises(IngestionError, match=error):
        ProjectDataResetRepository(connection, tmp_path).reset_project_data()
    assert connection.events == ["begin", "rollback"]
    assert not any("TRUNCATE" in sql for sql, _ in connection.calls)


def test_reset_streams_private_backup_and_manifest_before_truncate(tmp_path):
    connection = ResetConnection(["person"])
    progress = Mock()
    result = ProjectDataResetRepository(connection, tmp_path, progress).reset_project_data()
    directory = next(tmp_path.iterdir())
    assert (directory / "person.csv").read_bytes() == b"id\n1\n"
    assert (directory / "person.csv").stat().st_mode & 0o777 == 0o600
    assert (directory / "manifest.json").exists()
    sqls = [sql for sql, _ in connection.calls]
    assert next(i for i, sql in enumerate(sqls) if "COPY" in sql) < next(
        i for i, sql in enumerate(sqls) if "TRUNCATE" in sql
    )
    assert '"se_liga_brasil"."person"' in next(sql for sql in sqls if "TRUNCATE" in sql)
    assert result["cleared_tables"] == 1
    assert connection.events == ["begin", "commit"]
    progress.assert_called_once_with("backup", table="person", rows=1)


@pytest.mark.parametrize("failure", ["backup", "manifest"])
def test_reset_aborts_before_truncate_if_backup_or_manifest_cannot_be_saved(
    monkeypatch, tmp_path, failure
):
    connection = ResetConnection(["person"])
    reset = ProjectDataResetRepository(connection, tmp_path)
    if failure == "backup":
        monkeypatch.setattr(reset, "backup_table", Mock(side_effect=OSError("disk full")))
    else:
        monkeypatch.setattr("database.data_reset.save_json", Mock(side_effect=OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        reset.reset_project_data()
    assert connection.events == ["begin", "rollback"]
    assert not any("TRUNCATE" in sql for sql, _ in connection.calls)
