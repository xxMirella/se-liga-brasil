"""Pipelines and the daily job must trigger the serving rebuild; none of this touches a network."""

import importlib.util
import json
import sys
from contextlib import nullcontext
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from application import cli, enrichment, senado_history

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_cli(*arguments):
    return cli.create_argument_parser().parse_args(arguments)


def test_collection_commands_rebuild_after_orchestration(monkeypatch):
    calls = []
    connection = object()
    monkeypatch.setattr(enrichment, "connect_database", lambda _: nullcontext(connection))
    monkeypatch.setattr(
        enrichment, "orchestrate_collection", lambda *_, **__: calls.append("collect") or {}
    )
    monkeypatch.setattr(
        enrichment, "rebuild_serving_datasets", lambda *args: calls.append(("rebuild", *args))
    )
    enrichment.execute_enrichment_command(parse_cli("enrich"))
    assert calls[0] == "collect"
    assert calls[1][:2] == ("rebuild", connection)
    assert calls[1][2] == datetime.now(UTC).date()


@pytest.mark.parametrize("command", ["purge-gaps", "audit-completeness"])
def test_diagnostic_commands_do_not_rebuild(monkeypatch, command):
    rebuild = Mock()
    monkeypatch.setattr(enrichment, "connect_database", lambda _: nullcontext(object()))
    monkeypatch.setattr(enrichment, "purge_processed_gaps", lambda _: {})
    monkeypatch.setattr(enrichment, "assess_completeness", lambda *_: {})
    monkeypatch.setattr(enrichment, "rebuild_serving_datasets", rebuild)
    enrichment.execute_enrichment_command(parse_cli(command))
    rebuild.assert_not_called()


def stub_tse_command(monkeypatch, tmp_path, rebuild, ingestion):
    configuration = SimpleNamespace(
        years=(2026,), ufs=("SP",), kinds=("candidate",), request_timeout_seconds=2,
        storage_directory=tmp_path,
    )
    monkeypatch.setattr(cli, "load_configuration", lambda *_: configuration)
    monkeypatch.setattr(cli, "OfficialHttpClient", lambda *_: object())
    monkeypatch.setattr(cli.httpx, "Client", lambda **_: nullcontext(object()))
    monkeypatch.setattr(cli, "connect_database", lambda _: nullcontext(object()))
    monkeypatch.setattr(cli, "run_pipeline", lambda *args: {"phase": args[0]})
    monkeypatch.setattr(cli, "SqlBatchWriter", lambda _: object())
    monkeypatch.setattr(cli, "TseProjectionWriter", lambda _: object())
    monkeypatch.setattr(cli, "IngestionRepository", lambda *_, **__: object())
    monkeypatch.setattr(cli, "execute_ingestion_run", ingestion)
    monkeypatch.setattr(cli, "rebuild_serving_datasets", rebuild)


@pytest.mark.parametrize(("command", "rebuilds"), [("ingest", 1), ("run", 1), ("discover", 0)])
def test_tse_pipeline_rebuilds_only_after_ingestion(monkeypatch, tmp_path, command, rebuilds):
    rebuild = Mock()
    stub_tse_command(monkeypatch, tmp_path, rebuild, lambda *_, **__: {"phase": command})
    assert cli.execute_crawler_command(parse_cli(command)) == {"phase": command}
    assert rebuild.call_count == rebuilds


def test_tse_pipeline_failure_does_not_rebuild(monkeypatch, tmp_path):
    rebuild = Mock()
    stub_tse_command(monkeypatch, tmp_path, rebuild, Mock(side_effect=RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        cli.execute_crawler_command(parse_cli("run"))
    rebuild.assert_not_called()


@pytest.mark.parametrize(("committed", "rebuilds"), [(True, 1), (False, 0)])
def test_senado_history_rebuilds_only_when_the_load_committed(
    monkeypatch, tmp_path, committed, rebuilds
):
    rebuild = Mock()
    monkeypatch.setattr(senado_history, "SenateArchive", lambda *_: object())
    monkeypatch.setattr(senado_history, "build_load_plan", lambda *_: object())
    monkeypatch.setattr(senado_history, "load_inventory_senator_ids", lambda *_: set())
    monkeypatch.setattr(senado_history, "HistoricalSenateWriter", lambda *_: object())
    monkeypatch.setattr(senado_history, "connect_database", lambda _: nullcontext(object()))
    monkeypatch.setattr(
        senado_history,
        "run_historical_load",
        lambda *_: SimpleNamespace(committed=committed, idempotent=True),
    )
    monkeypatch.setattr(
        senado_history,
        "build_report",
        lambda *_: {"inserted": 0, "would_insert": 0, "second_pass_inserted": 0, "pending": {}},
    )
    monkeypatch.setattr(senado_history, "rebuild_serving_datasets", rebuild)
    arguments = SimpleNamespace(
        apply=committed,
        source_directory=None,
        env_file=None,
        reviewed_identities=None,
        report_file=tmp_path / "report.json",
    )
    senado_history.execute_senado_history_command(arguments)
    assert rebuild.call_count == rebuilds


def load_rebuild_script():
    path = PROJECT_ROOT / "scripts" / "rebuild_serving_datasets.py"
    spec = importlib.util.spec_from_file_location("rebuild_serving_datasets_script", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("outcomes", "expected_exit"),
    [({"person_directory": "abc"}, None), ({"a": "abc", "b": "failed:RuntimeError"}, 1)],
)
def test_daily_job_reports_outcomes_and_fails_loudly(
    monkeypatch, capsys, outcomes, expected_exit
):
    script = load_rebuild_script()
    monkeypatch.setattr(script, "connect_database", lambda _: nullcontext(object()))
    monkeypatch.setattr(script, "rebuild_serving_datasets", lambda *_: outcomes)
    monkeypatch.setattr(sys, "argv", ["rebuild", "--as-of", "2026-11-05"])
    if expected_exit is None:
        script.main()
    else:
        with pytest.raises(SystemExit) as raised:
            script.main()
        assert raised.value.code == expected_exit
    report = json.loads(capsys.readouterr().out)
    assert report == {"as_of": date(2026, 11, 5).isoformat(), "datasets": outcomes}


def test_daily_schedule_units_point_to_the_rebuild_script():
    service = (PROJECT_ROOT / "deploy/se-liga-brasil-serving-rebuild.service").read_text()
    timer = (PROJECT_ROOT / "deploy/se-liga-brasil-serving-rebuild.timer").read_text()
    assert "scripts/rebuild_serving_datasets.py" in service
    assert "Type=oneshot" in service
    assert "OnCalendar=*-*-*" in timer
    assert "Persistent=true" in timer
