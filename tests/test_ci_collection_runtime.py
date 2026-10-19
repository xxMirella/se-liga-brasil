"""Source locks, cooldowns and run failure transitions are observable contracts."""

from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from service.crawling.runs import execute_ingestion_run
from service.ingestion.contracts import IngestionError
from service.legislative_collection import runtime
from service.voting_pipeline import runner


@dataclass
class Configuration:
    storage_directory: Path
    request_timeout_seconds: int = 1


@pytest.mark.parametrize(
    "result,status",
    [
        ({}, "completed"),
        ({"failures": ["error"]}, "partial"),
        ({"artifacts": [{"rejected": 1}]}, "partial"),
        ({"identity_unresolved": 1}, "partial"),
    ],
)
def test_run_does_not_label_rejections_or_unknown_identities_complete(tmp_path, result, status):
    repository = SimpleNamespace(begin_run=Mock(), finish_run=Mock())
    output = execute_ingestion_run(
        "run", Configuration(tmp_path), None, repository, pipeline=lambda *_: dict(result)
    )
    assert output["status"] == status
    repository.finish_run.assert_called_once_with(status, result)
    assert repository.begin_run.call_args.args[1]["storage_directory"] == str(tmp_path)


@pytest.mark.parametrize("error", [ValueError("bad input"), KeyboardInterrupt()])
def test_run_failure_always_records_failed_lifecycle(tmp_path, error):
    repository = SimpleNamespace(begin_run=Mock(), finish_run=Mock())
    with pytest.raises(type(error)):
        execute_ingestion_run(
            "run", Configuration(tmp_path), None, repository, pipeline=Mock(side_effect=error)
        )
    repository.finish_run.assert_called_once_with("failed", {})


@pytest.mark.parametrize("source", ["senado", "camara"])
def test_vote_source_dispatch_caps_proposition_budget(monkeypatch, tmp_path, source):
    import crawlers.camara.voting_pipeline as camara
    import service.voting_pipeline.source_senado as senado

    collect = Mock(return_value={"rows": 0})
    target = camara if source == "camara" else senado
    name = "collect_camara_source_files" if source == "camara" else "collect_senate_source_files"
    monkeypatch.setattr(target, name, collect)
    assert runner.collect_source_input(
        None,
        tmp_path,
        source,
        date(2024, 1, 1),
        date(2024, 1, 2),
        tmp_path / "input",
        limit=200,
        proposition_ids=(1,),
    ) == {"rows": 0}
    options = collect.call_args.kwargs
    assert options.get("max_propositions", options.get("max_processes")) == 100
    if source == "camara":
        assert options["proposition_ids"] == (1,)


def test_unknown_voting_source_rejected_before_network(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        runner.collect_source_input(None, tmp_path, "invalid", None, None, tmp_path / "input")


@pytest.mark.parametrize(
    "source,start,end",
    [
        ("invalid", date(2024, 1, 1), date(2024, 1, 2)),
        ("camara", date(2024, 1, 2), date(2024, 1, 1)),
        ("camara", date(2024, 1, 1), date(2024, 4, 1)),
    ],
)
def test_refresh_rejects_unbounded_input_without_database(source, start, end, tmp_path):
    with pytest.raises(ValueError, match="bounded"):
        runner.run_source_refresh(None, tmp_path, tmp_path, source, start, end)


@pytest.mark.parametrize("fails", [False, True])
def test_refresh_unlocks_source_even_if_collection_fails(monkeypatch, tmp_path, fails):
    connection = SimpleNamespace(
        execute=Mock(
            return_value=SimpleNamespace(
                fetchone=lambda: {"acquired": True},
            )
        )
    )
    collect = Mock(side_effect=ValueError("failed")) if fails else Mock(return_value={"rows": 0})
    monkeypatch.setattr(runner, "collect_source_input", collect)
    monkeypatch.setattr(runner, "consolidate_acquisition", lambda *_: {"pipeline_triggered": False})
    args = (connection, tmp_path, tmp_path, "camara", date(2024, 1, 1), date(2024, 1, 2))
    if fails:
        with pytest.raises(ValueError, match="failed"):
            runner.run_source_refresh(*args, proposition_ids=(1,))
    else:
        result = runner.run_source_refresh(*args, proposition_ids=(1,))
        assert result["pipeline_triggered"] is False
        assert result["coverage"] == "requested_source_interval_not_full_career"
    assert "pg_advisory_unlock" in connection.execute.call_args.args[0]
    assert not list(tmp_path.glob("daily-voting-*"))


def test_refresh_cannot_steal_held_source_lock(tmp_path):
    connection = SimpleNamespace(
        execute=Mock(
            return_value=SimpleNamespace(
                fetchone=lambda: {"acquired": False},
            )
        )
    )
    with pytest.raises(ValueError, match="already running"):
        runner.run_source_refresh(
            connection, tmp_path, tmp_path, "camara", date(2024, 1, 1), date(2024, 1, 2)
        )
    assert connection.execute.call_count == 1


def test_durable_cooldown_prevents_source_attempts():
    connection = SimpleNamespace(
        execute=Mock(
            return_value=SimpleNamespace(
                fetchone=lambda: {"remaining": 25},
            )
        )
    )
    with pytest.raises(IngestionError, match="SOURCE_COOLDOWN_ACTIVE"):
        runtime.check_source_cooldown(connection, "camara")


@pytest.mark.parametrize("status", [None, 403, 429, 503])
def test_official_collection_uses_shared_runtime_and_persists_transient_cooldown(
    monkeypatch, tmp_path, status
):
    connection = SimpleNamespace(execute=Mock(return_value=SimpleNamespace(fetchone=lambda: None)))
    definition = runtime.CollectionDefinition(
        SimpleNamespace(code="camara"), "v1", frozenset(), lambda _: object(), lambda *_: object()
    )
    monkeypatch.setattr(runtime, "IngestionRepository", lambda *_, **__: object())
    monkeypatch.setattr(runtime, "SqlBatchWriter", lambda _: object())
    monkeypatch.setattr(runtime, "local_run_lock", lambda _: nullcontext())
    monkeypatch.setattr(runtime.httpx, "Client", lambda **_: nullcontext(object()))
    monkeypatch.setattr(runtime, "OfficialHttpClient", lambda *_: object())
    postpone = Mock()
    monkeypatch.setattr(runtime, "postpone_source", postpone)
    if status:
        monkeypatch.setattr(
            runtime, "execute_ingestion_run", Mock(side_effect=ValueError("source"))
        )
        monkeypatch.setattr(
            runtime, "describe_error", lambda _: {"code": "HTTP_ERROR", "status": status}
        )
        with pytest.raises(ValueError, match="source"):
            runtime.run_official_collection(
                connection, Configuration(tmp_path), definition, object()
            )
        assert postpone.call_args.args[2] == 3600
    else:
        monkeypatch.setattr(
            runtime, "execute_ingestion_run", lambda *_, **__: {"status": "completed"}
        )
        assert runtime.run_official_collection(
            connection, Configuration(tmp_path), definition, object()
        ) == {"status": "completed"}
        postpone.assert_not_called()
