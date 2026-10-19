"""CLI exits and dispatch must preserve failures and avoid unintended database access."""

from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from application import cli
from service.ingestion.contracts import IngestionError


def arguments(*values):
    return cli.create_argument_parser().parse_args(list(values))


@pytest.mark.parametrize("command,module,function", [
    ("collect-attendance", "application.attendance", "execute_attendance_command"),
    ("run-voting-pipeline", "application.voting", "execute_voting_command"),
    ("configure-voting-schedule", "application.voting", "execute_voting_command"),
    ("voting-worker", "application.voting", "execute_voting_command"),
    ("serve-public-api", "application.public_api", "execute_public_api_command"),
    ("collect-history", "application.legislative", "execute_historical_command"),
    ("collect-votes", "application.legislative", "execute_historical_command"),
    ("build-dataset", "application.analytical", "execute_analytical_command"),
    ("query-dataset", "application.analytical", "execute_analytical_command"),
    ("build-voting-timeline", "application.analytical", "execute_analytical_command"),
])
def test_service_commands_use_explicit_adapters(monkeypatch, command, module, function):
    from importlib import import_module

    delegated = Mock(return_value={"status": "delegated"})
    monkeypatch.setattr(import_module(module), function, delegated)
    request = arguments(command)
    assert cli.execute_command(request) == {"status": "delegated"}
    delegated.assert_called_once_with(request)


@pytest.mark.parametrize("result", [
    {"findings": ["issue"]}, {"failures": ["issue"]}, {"status": "partial"},
    {"rejected_files": 1},
])
def test_reported_errors_always_exit_nonzero(monkeypatch, result):
    monkeypatch.setattr(cli, "execute_command", lambda _: result)
    assert cli.execute_reported_command(arguments("review")) == 1


@pytest.mark.parametrize("error,code", [
    (ValueError("invalid input"), 1), (KeyboardInterrupt(), 130),
])
def test_failures_and_interrupts_have_distinct_exit_status(monkeypatch, error, code):
    def fail(_):
        raise error

    monkeypatch.setattr(cli, "execute_command", fail)
    assert cli.execute_reported_command(arguments("review")) == code


def test_reporter_rejections_cannot_be_reported_as_success(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "execute_command", lambda _: {})
    reporter = SimpleNamespace(rejected_files=["invalid"], log_path=tmp_path, events_path=tmp_path)
    assert cli.execute_reported_command(arguments("validate"), reporter) == 1


def test_reporter_without_rejections_finishes_successfully(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "execute_command", lambda _: {})
    reporter = SimpleNamespace(rejected_files=[], log_path=tmp_path, events_path=tmp_path)
    assert cli.execute_reported_command(arguments("validate"), reporter) == 0


@pytest.mark.parametrize("source", ["camara", "senado", "alerj", "tse_filiation"])
def test_wrong_crawler_scope_cannot_trigger_a_source(monkeypatch, source):
    monkeypatch.setattr(cli, "execute_crawler_command", Mock(side_effect=AssertionError))
    with pytest.raises(IngestionError, match="USE_ENRICHMENT_SERVICE_FOR_SOURCE"):
        cli.execute_command(arguments("--source", source, "download"))


@pytest.mark.parametrize("values", [("resolve-identities",), ("run", "--months", "2026-01")])
def test_tse_rejects_unrelated_scopes(values):
    with pytest.raises(IngestionError, match="INVALID_CRAWLER_SCOPE"):
        cli.execute_command(arguments(*values))


@pytest.mark.parametrize("command", ["db-verify", "db-migrate"])
def test_database_migration_is_explicit_and_closes_connection(monkeypatch, command):
    connection = object()
    monkeypatch.setattr(cli, "connect_database", lambda _: nullcontext(connection))
    migrate = Mock(return_value=True)
    monkeypatch.setattr(cli, "apply_ingestion_schema", migrate)
    monkeypatch.setattr(cli, "verify_schema", lambda _: {"tables": 46})
    result = cli.execute_command(arguments(command))
    assert result["tables"] == 46
    assert migrate.call_count == int(command == "db-migrate")


def test_review_dispatches_without_network(monkeypatch):
    monkeypatch.setattr(cli, "review_project", lambda _: [])
    assert cli.execute_command(arguments("review")) == {"findings": []}


@pytest.mark.parametrize("command", ["audit-completeness", "enrich", "dispatch", "purge-gaps"])
def test_enrichment_commands_do_not_use_tse_pipeline(monkeypatch, command):
    import application.enrichment as enrichment

    monkeypatch.setattr(enrichment, "execute_enrichment_command", lambda _: {"enrichment": True})
    assert cli.execute_command(arguments(command)) == {"enrichment": True}


def test_alesp_uses_own_source_adapter(monkeypatch):
    import application.alesp as alesp

    monkeypatch.setattr(alesp, "execute_alesp_command", lambda _: {"alesp": True})
    assert cli.execute_command(arguments("--source", "alesp", "run")) == {"alesp": True}


@pytest.mark.parametrize("command", ["discover", "ingest", "run"])
def test_tse_only_connects_database_for_ingestion(monkeypatch, command, tmp_path):
    configuration = SimpleNamespace(
        years=(2026,), ufs=("SP",), kinds=("candidate",), request_timeout_seconds=2,
        storage_directory=tmp_path,
    )
    monkeypatch.setattr(cli, "load_configuration", lambda *_: configuration)
    transport = object()
    monkeypatch.setattr(cli, "OfficialHttpClient", lambda *_: transport)
    monkeypatch.setattr(cli.httpx, "Client", lambda **_: nullcontext(object()))
    database = Mock(return_value=nullcontext(object()))
    monkeypatch.setattr(cli, "connect_database", database)
    monkeypatch.setattr(cli, "run_pipeline", lambda *args: {"phase": args[0]})
    monkeypatch.setattr(cli, "SqlBatchWriter", lambda _: object())
    monkeypatch.setattr(cli, "TseProjectionWriter", lambda _: object())
    monkeypatch.setattr(cli, "IngestionRepository", lambda *_, **__: object())
    monkeypatch.setattr(cli, "execute_ingestion_run", lambda *_, **__: {"phase": command})
    assert cli.execute_crawler_command(arguments(command)) == {"phase": command}
    assert database.call_count == int(command in {"run", "ingest"})


@pytest.mark.parametrize("command", ["review", "validate"])
def test_main_routes_reporter_for_crawler_commands(monkeypatch, command, tmp_path):
    monkeypatch.setattr("sys.argv", ["se-liga-brasil", command])
    reporter = object()
    monkeypatch.setattr(cli, "RunReporter", lambda _: nullcontext(reporter))
    monkeypatch.setattr(cli, "resolve_report_storage", lambda _: tmp_path)
    run = Mock(return_value=0)
    monkeypatch.setattr(cli, "execute_reported_command", run)
    assert cli.main() == 0
    assert len(run.call_args.args) == (2 if command == "validate" else 1)


def test_storage_selection_recovers_from_bad_configuration(monkeypatch, tmp_path):
    monkeypatch.setattr(cli, "load_configuration", Mock(side_effect=ValueError))
    request = arguments("run", "--storage-directory", str(tmp_path))
    assert cli.resolve_report_storage(request) == tmp_path
    assert cli.resolve_report_storage(arguments("run")).name == "tse"


@pytest.mark.parametrize("command", ["enrich", "dispatch"])
def test_enrichment_storage_uses_separate_namespace(command):
    assert cli.resolve_report_storage(arguments(command)).name == "enrichment"


def test_alesp_storage_uses_source_configuration(monkeypatch, tmp_path):
    import application.alesp as alesp

    monkeypatch.setattr(alesp, "load_alesp_configuration", lambda _: SimpleNamespace(
        storage_directory=tmp_path,
    ))
    assert cli.resolve_report_storage(arguments("--source", "alesp", "run")) == tmp_path


def test_scope_all_differs_from_unspecified_scope():
    scope = cli.parse_scope_overrides(arguments("discover", "--years", "all", "--ufs", "all"))
    assert scope["years"] == [] and scope["ufs"] == []
    scope = cli.parse_scope_overrides(arguments("discover"))
    assert scope["years"] is None and scope["ufs"] is None
    explicit = cli.parse_scope_overrides(arguments(
        "discover", "--years", "2020,2022", "--kinds", "candidate,asset", "--office-codes", "6,7",
    ))
    assert explicit["years"] == [2020, 2022]
    assert explicit["office_codes"] == ["6", "7"]


def test_static_build_does_not_receive_database_credentials(monkeypatch, tmp_path):
    from service.static_publication import build

    run = Mock(return_value={"files": 9})
    monkeypatch.setattr(build, "build_civic_site", run)
    assert cli.execute_command(arguments(
        "build-static-site", "--output-directory", str(tmp_path),
    )) == {"files": 9}
    run.assert_called_once_with(Path(tmp_path), backend_origin=None)
