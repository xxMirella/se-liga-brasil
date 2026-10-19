"""Source entry points require explicit scopes and isolate configuration from effects."""

from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from application import alesp, attendance, enrichment
from application.cli import create_argument_parser
from service.ingestion.contracts import IngestionError


def parse(*values):
    return create_argument_parser().parse_args(list(values))


@pytest.mark.parametrize("option", ["--ufs", "--office-codes"])
def test_alesp_rejects_tse_only_options(option):
    with pytest.raises(IngestionError, match="INVALID_CRAWLER_SCOPE"):
        alesp.load_alesp_configuration(parse("run", option, "SP"))


@pytest.mark.parametrize("years,expected", [(None, None), ("all", []), ("2020,2022", [2020, 2022])])
def test_alesp_optional_scope_preserves_all_vs_default(monkeypatch, years, expected, tmp_path):
    load = Mock(return_value="configuration")
    monkeypatch.setattr(alesp, "load_configuration", load)
    values = [
        "run",
        "--months",
        "2022-01,2022-02",
        "--kinds",
        "payroll",
        "--storage-directory",
        str(tmp_path),
    ]
    if years:
        values.extend(["--years", years])
    assert alesp.load_alesp_configuration(parse(*values)) == "configuration"
    scope = load.call_args.args[1]
    assert scope["years"] == expected
    assert scope["months"] == ["2022-01", "2022-02"]
    assert scope["storage_directory"] == str(tmp_path)


@pytest.mark.parametrize("command", ["discover", "run", "ingest", "resolve-identities"])
def test_alesp_database_access_is_only_for_write_phases(monkeypatch, command, tmp_path):
    configuration = SimpleNamespace(years=[], kinds=["payroll"], request_timeout_seconds=1)
    monkeypatch.setattr(alesp, "load_alesp_configuration", lambda _: configuration)
    monkeypatch.setattr(alesp.httpx, "Client", lambda **_: nullcontext(object()))
    monkeypatch.setattr(alesp, "OfficialHttpClient", lambda *_: object())
    database = Mock(return_value=nullcontext(object()))
    monkeypatch.setattr(alesp, "connect_database", database)
    monkeypatch.setattr(alesp, "SqlBatchWriter", lambda _: object())
    monkeypatch.setattr(alesp, "AlespProjectionWriter", lambda _: object())
    monkeypatch.setattr(alesp, "IngestionRepository", lambda *_, **__: object())
    monkeypatch.setattr(alesp, "run_alesp_pipeline", lambda *args: {"phase": args[0]})
    monkeypatch.setattr(alesp, "execute_ingestion_run", lambda *args, **_: {"phase": args[0]})
    assert alesp.execute_alesp_command(parse(command)) == {"phase": command}
    assert database.call_count == int(command != "discover")


@pytest.mark.parametrize("command", ["purge-gaps", "audit-completeness", "dispatch", "enrich"])
def test_enrichment_routes_queue_maintenance_without_collection(monkeypatch, command, tmp_path):
    connection = object()
    monkeypatch.setattr(enrichment, "connect_database", lambda _: nullcontext(connection))
    purge, assess, orchestrate = [Mock(return_value={"ok": True}) for _ in range(3)]
    monkeypatch.setattr(enrichment, "purge_processed_gaps", purge)
    monkeypatch.setattr(enrichment, "assess_completeness", assess)
    monkeypatch.setattr(enrichment, "orchestrate_collection", orchestrate)
    monkeypatch.setattr(enrichment, "career_collectors", lambda *_: {"career": True})
    result = enrichment.execute_enrichment_command(
        parse(
            command,
            "--storage-directory",
            str(tmp_path),
            "--fields",
            "salary,education",
            "--include-career",
        )
    )
    assert result == {"ok": True}
    assert purge.call_count == int(command == "purge-gaps")
    assert assess.call_count == int(command == "audit-completeness")
    if command in {"dispatch", "enrich"}:
        options = orchestrate.call_args.kwargs
        assert options["refresh_assessment"] == (command != "dispatch")
        assert options["field_names"] == ["salary", "education"]
        assert options["career_collectors"] == {"career": True}


def test_enrichment_without_optional_backfill_keeps_it_disabled(monkeypatch):
    monkeypatch.setattr(enrichment, "connect_database", lambda _: nullcontext(object()))
    run = Mock(return_value={})
    monkeypatch.setattr(enrichment, "orchestrate_collection", run)
    enrichment.execute_enrichment_command(parse("dispatch"))
    assert run.call_args.kwargs["career_collectors"] is None
    assert run.call_args.kwargs["field_names"] is None


def test_attendance_cli_reuses_official_collection_and_publishes_after_it(monkeypatch, tmp_path):
    connection, configuration, definition, storage = (object() for _ in range(4))
    calls = []
    monkeypatch.setattr(attendance, "connect_database", lambda _: nullcontext(connection))
    monkeypatch.setattr(attendance, "CrawlerConfiguration", lambda _: configuration)
    monkeypatch.setattr(attendance, "CollectionDefinition", lambda *_: definition)
    monkeypatch.setattr(
        attendance, "run_official_collection", lambda *_: calls.append("collect") or {}
    )
    monkeypatch.setattr(attendance.httpx, "Client", lambda **_: nullcontext(object()))
    monkeypatch.setattr(attendance, "load_storage_configuration", lambda _: object())
    monkeypatch.setattr(attendance, "SupabaseDatasetStorage", lambda *_: storage)
    monkeypatch.setattr(
        attendance, "publish_attendance_dataset", lambda *_: calls.append("publish") or {"rows": 5}
    )
    result = attendance.execute_attendance_command(
        parse(
            "collect-attendance",
            "--storage-directory",
            str(tmp_path),
        )
    )
    assert calls == ["collect", "publish"]
    assert result == {"dataset": {"rows": 5}, "status": "partial"}


def test_attendance_pipeline_forwards_person_scope_without_crawling_other_people(monkeypatch):
    collect = Mock(return_value={"people": 1})
    monkeypatch.setattr(attendance, "collect_attendance_batch", collect)
    assert attendance.attendance_pipeline(
        None, None, "source", "repository", limit=1, person_id="person"
    ) == {"people": 1}
    collect.assert_called_once_with("repository", "source", limit=1, person_id="person")
