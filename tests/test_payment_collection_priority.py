"""Payment batches keep queue priority all the way to each remote collector."""

from contextlib import nullcontext
from unittest.mock import Mock

import pytest

from application.cli import create_argument_parser
from database.data_gaps import claim_data_gaps
from service.ingestion.contracts import IngestionError
from service.orchestration import data_collection


@pytest.mark.parametrize("source", ["camara", "senado", "alerj"])
def test_collector_receives_queue_priority_instead_of_uuid_order(monkeypatch, tmp_path, source):
    people = {"z-current": {"current_salary"}, "a-other": {"current_salary"}}
    candidates = [{"person_id": key} for key in ["a-other", "unclaimed", "z-current"]]
    collector = Mock(return_value={})
    if source == "senado":
        from crawlers.senado import pipeline

        monkeypatch.setattr(pipeline, "collect_senado_enrichment", collector)
    else:
        name = "run_camara_collection" if source == "camara" else "collect_alerj_enrichment"
        monkeypatch.setattr(data_collection, name, collector)
    data_collection.collect_requested_source(None, tmp_path, source, people, [], candidates)
    assert [row["person_id"] for row in collector.call_args.args[2]] == list(people)


@pytest.mark.parametrize("limit", [0, -1, 1001, True, 1.5])
def test_invalid_task_budget_never_touches_database(limit):
    connection = Mock()
    with pytest.raises(IngestionError, match="INVALID_DATA_GAP_LIMIT"):
        claim_data_gaps(connection, "worker", limit=limit)
    connection.transaction.assert_not_called()


def test_cli_passes_explicit_small_payment_budget(monkeypatch, tmp_path):
    from application import enrichment

    run = Mock(return_value={})
    monkeypatch.setattr(enrichment, "connect_database", lambda _: nullcontext(None))
    monkeypatch.setattr(enrichment, "orchestrate_collection", run)
    arguments = create_argument_parser().parse_args(
        [
            "dispatch",
            "--fields",
            "current_salary",
            "--sources",
            "camara",
            "--task-limit",
            "10",
            "--storage-directory",
            str(tmp_path),
        ]
    )
    enrichment.execute_enrichment_command(arguments)
    assert run.call_args.kwargs["task_limit"] == 10
    assert run.call_args.kwargs["field_names"] == ["current_salary"]


@pytest.mark.parametrize("value", ["0", "1001", "invalid"])
def test_cli_rejects_invalid_budget_before_connecting(value):
    with pytest.raises(SystemExit):
        create_argument_parser().parse_args(["dispatch", "--task-limit", value])
