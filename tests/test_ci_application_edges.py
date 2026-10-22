"""CLI and resumable-worker contracts with all external effects replaced offline."""

from contextlib import nullcontext
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from application import analytical, voting
from service.attendance import collection
from service.ingestion.contracts import IngestionError


def arguments(**changes):
    return SimpleNamespace(
        **{
            "command": "run-voting-pipeline",
            "env_file": None,
            "local_only": True,
            "start_date": "2026-05-01",
            "end_date": "2026-05-27",
            "source": "camara",
            "storage_directory": None,
            "dataset_directory": None,
            "limit": 20,
            "max_identity_profiles": 0,
            "proposition_ids": "123,,456",
            "max_jobs": 2,
            "poll_seconds": 5,
            "daemon": False,
            "years": "2026",
            "person_id": "person",
            "input_file": None,
        }
        | changes
    )


def test_explicit_voting_refresh_forwards_document_ids_and_io_budgets(monkeypatch):
    calls = []
    monkeypatch.setattr(
        voting, "run_source_refresh", lambda *args, **kwargs: calls.append((args, kwargs))
    )
    voting.run_requested_refresh(
        "connection", arguments(), None, "camara", date(2026, 5, 1), date(2026, 5, 27)
    )
    positional, options = calls[0]
    assert positional[3:] == ("camara", date(2026, 5, 1), date(2026, 5, 27))
    assert options == {
        "publisher": None,
        "limit": 20,
        "max_identity_profiles": 0,
        "proposition_ids": ("123", "456"),
    }


def test_local_refresh_never_requests_storage_credentials(monkeypatch):
    monkeypatch.setattr(voting, "connect_database", lambda _: nullcontext("connection"))
    monkeypatch.setattr(
        voting,
        "load_storage_configuration",
        lambda _: pytest.fail("Local mode requires no storage secret"),
    )
    monkeypatch.setattr(
        voting, "run_requested_refresh", lambda *args: {"source": args[3], "publisher": args[2]}
    )
    assert voting.execute_voting_command(arguments()) == {"source": "camara", "publisher": None}


def test_schedule_setup_does_not_instantiate_http_or_worker(monkeypatch):
    monkeypatch.setattr(voting, "connect_database", lambda _: nullcontext("connection"))
    monkeypatch.setattr(
        voting, "configure_voting_schedule", lambda connection: {"connection": connection}
    )
    assert voting.execute_voting_command(arguments(command="configure-voting-schedule")) == {
        "connection": "connection"
    }


@pytest.mark.parametrize("start,end", [(None, "2026-05-27"), ("2026-05-01", None)])
def test_manual_voting_requires_both_explicit_dates(monkeypatch, start, end):
    monkeypatch.setattr(voting, "connect_database", lambda _: nullcontext(None))
    with pytest.raises(ValueError, match="Explicit voting dates"):
        voting.execute_voting_command(arguments(start_date=start, end_date=end))


@pytest.mark.parametrize("jobs,poll", [(0, 5), (101, 5), (1, 4), (1, 61)])
def test_worker_invalid_limits_fail_before_claiming_jobs(jobs, poll):
    with pytest.raises(ValueError, match="worker budget"):
        voting.run_voting_worker(None, arguments(max_jobs=jobs, poll_seconds=poll), None)


def test_durable_worker_cannot_consume_jobs_without_storage_publication():
    with pytest.raises(ValueError, match="publication to Storage"):
        voting.run_voting_worker(None, arguments(), None)


def test_non_daemon_worker_returns_results_without_sleep(monkeypatch):
    monkeypatch.setattr(voting, "process_voting_jobs", lambda *args: [{"status": "done"}])
    monkeypatch.setattr(voting.time, "sleep", lambda _: pytest.fail("Non-daemon must not sleep"))
    assert voting.run_voting_worker(None, arguments(local_only=False), "publisher") == {
        "processed": 1,
        "jobs": [{"status": "done"}],
    }


def test_empty_queue_stops_without_refreshing_or_finishing(monkeypatch):
    claims = []
    monkeypatch.setattr(voting, "claim_voting_refresh", lambda *args: claims.append(args))
    monkeypatch.setattr(
        voting, "run_requested_refresh", lambda *args: pytest.fail("No claimed job")
    )
    assert voting.process_voting_jobs("connection", arguments(), None, "worker") == []
    assert len(claims) == 1


def test_incomplete_discovery_is_failed_and_next_job_can_succeed(monkeypatch):
    jobs = iter(
        [
            {
                "id": 1,
                "source": "camara",
                "starts_on": date(2026, 5, 1),
                "ends_on": date(2026, 5, 27),
            },
            {
                "id": 2,
                "source": "senado",
                "starts_on": date(2026, 5, 1),
                "ends_on": date(2026, 5, 27),
            },
        ]
    )
    failed, finished = [], []
    monkeypatch.setattr(voting, "claim_voting_refresh", lambda *args: next(jobs))
    monkeypatch.setattr(
        voting, "run_requested_refresh", lambda *args: {"discovery_complete": args[3] == "senado"}
    )
    monkeypatch.setattr(
        voting, "describe_error", lambda error: {"code": str(error), "retry_after_seconds": 75}
    )
    monkeypatch.setattr(voting, "fail_voting_refresh", lambda *args: failed.append(args))
    monkeypatch.setattr(voting, "finish_voting_refresh", lambda *args: finished.append(args))
    results = voting.process_voting_jobs("connection", arguments(), "publisher", "worker")
    assert results[0]["code"] == "VOTING_DISCOVERY_BUDGET_EXCEEDED"
    assert failed[0][1:] == (1, "worker", "VOTING_DISCOVERY_BUDGET_EXCEEDED", 75)
    assert finished[0][1] == 2
    assert results[1] == {"discovery_complete": True}


@pytest.mark.parametrize("year", [None, "all", "2025,2026"])
def test_analytical_cli_requires_one_year_before_opening_database(year):
    with pytest.raises(IngestionError, match="SELECT_ONE_DATASET_YEAR"):
        analytical.execute_analytical_command(arguments(years=year))


def test_analytical_cli_rejects_non_legislative_source():
    with pytest.raises(IngestionError, match="SELECT_LEGISLATIVE_INSTITUTION"):
        analytical.execute_analytical_command(arguments(source="tse"))


def test_query_cli_requires_person_before_reading_partition(tmp_path):
    with pytest.raises(IngestionError, match="PERSON_ID_REQUIRED"):
        analytical.query_analytical_votes(
            arguments(person_id=None), tmp_path, SimpleNamespace(year=2026)
        )


@pytest.mark.parametrize("explicit", [True, False])
def test_analytical_query_default_year_and_explicit_dates_are_forwarded(
    monkeypatch, tmp_path, explicit
):
    calls = []
    monkeypatch.setattr(
        analytical,
        "query_person_votes",
        lambda *args, **kwargs: calls.append((args, kwargs)) or [{"vote": "yes"}],
    )
    options = arguments(
        start_date="2026-05-01" if explicit else None, end_date="2026-05-27" if explicit else None
    )
    result = analytical.execute_analytical_command(
        options.__class__(
            **vars(options) | {"command": "query-dataset", "dataset_directory": tmp_path}
        )
    )
    assert calls[0][0][3:] == (
        (date(2026, 5, 1), date(2026, 5, 27))
        if explicit
        else (date(2026, 1, 1), date(2026, 12, 31))
    )
    assert calls[0][1] == {"limit": 20}
    assert result["count"] == 1
    assert result["coverage"] == "selected_local_partition_only"


@dataclass
class FakeManifest:
    row_count: int


@pytest.mark.parametrize("from_file", [True, False])
def test_dataset_build_uses_input_file_or_temporary_export(monkeypatch, tmp_path, from_file):
    calls = []
    source = tmp_path / "input.ndjson"
    source.write_text("{}\n")

    def export(connection, path, institution, year):
        assert (connection, institution, year) == ("connection", "camara", 2026)
        path.write_text("{}\n")
        calls.append("export")

    def publish(path, directory, partition, parser):
        assert path.read_text() == "{}\n"
        assert directory == tmp_path
        assert parser == "offline-parser"
        calls.append("publish")
        return FakeManifest(1)

    monkeypatch.setattr(
        analytical, "dataset_build_strategy", lambda _: (publish, export, "offline-parser")
    )
    monkeypatch.setattr(analytical, "connect_database", lambda _: nullcontext("connection"))
    result = analytical.execute_analytical_command(
        arguments(
            command="build-dataset",
            dataset_directory=tmp_path,
            input_file=source if from_file else None,
        )
    )
    assert result == {"row_count": 1}
    assert calls == (["publish"] if from_file else ["export", "publish"])


@pytest.mark.parametrize("limit", [0, 101])
def test_attendance_batch_limits_checked_before_discovery(limit):
    with pytest.raises(ValueError, match="1 to 100"):
        collection.collect_attendance_batch(None, None, limit=limit)


def test_historical_roster_keeps_earliest_term_and_never_starts_before_2000():
    members = {}
    collection.index_attendance_members(members, [{"id": 1, "name": "first"}], 51)
    collection.index_attendance_members(members, [{"id": 1, "name": "later"}, {"id": 2}], 57)
    assert members["1"]["attendance_start_year"] == 2000
    assert members["1"]["name"] == "first"
    assert members["2"]["attendance_start_year"] == 2023


def test_attendance_profile_preparation_prefers_cache_without_repeated_download(monkeypatch):
    calls = []
    cached = {"2": "cached-two", "10": "cached-ten"}
    monkeypatch.setattr(collection, "cached_profile_artifact", lambda config, key: cached.get(key))
    acquisition = SimpleNamespace(
        configuration=None,
        json_document=lambda path, kind: calls.append(path) or ({}, "downloaded"),
    )
    result = collection.prepare_attendance_profiles(
        acquisition, {"1": {}, "10": {}, "2": {}}, {}, 3
    )
    assert list(result) == ["2", "10", "1"]
    assert calls == ["deputados/1"]


@pytest.mark.parametrize("receipt", [None, {}, {"result": {"failures": ["retry"]}}])
def test_failed_or_absent_attendance_receipt_remains_retryable(receipt):
    assert collection.attendance_recently_checked(receipt) is False


def test_attendance_receipt_expires_and_success_receipt_skips_recent_work():
    now = datetime.now(ZoneInfo("America/Belem"))
    assert collection.attendance_recently_checked(
        {"checked_at": (now - timedelta(hours=1)).isoformat()}
    )
    assert not collection.attendance_recently_checked(
        {"checked_at": (now - timedelta(days=2)).isoformat()}
    )


def test_attendance_discovery_requests_each_historical_legislature_once():
    calls = []

    def pages(query, kind):
        calls.append((query, kind))
        yield [{"id": len(calls)}], None

    result = collection.discover_attendance_members(SimpleNamespace(pages=pages))
    assert len(result) == 7
    assert len(calls) == 7
    assert calls[0][0] == "deputados?idLegislatura=51&itens=100"
    assert calls[-1][0] == "deputados?idLegislatura=57&itens=100"


@pytest.mark.parametrize("selected_person", [None, "canonical-person"])
def test_attendance_batch_persists_verified_results_and_preserves_failed_coverage(
    monkeypatch, tmp_path, selected_person
):
    state, saves = {}, []
    members = {"1": {}, "2": {}, "3": {}}
    monkeypatch.setattr(collection, "load_json", lambda _: state)
    monkeypatch.setattr(collection, "save_json", lambda path, payload: saves.append(dict(payload)))
    monkeypatch.setattr(collection, "discover_attendance_members", lambda _: members)
    monkeypatch.setattr(
        collection, "prepare_attendance_profiles", lambda *args, **kwargs: dict.fromkeys(members)
    )
    monkeypatch.setattr(
        collection,
        "resolve_voting_people",
        lambda *args: {
            "1": {"person_id": "canonical-person"},
            "3": {"person_id": "another-person"},
        },
    )
    monkeypatch.setattr(
        collection,
        "collect_attendance_history",
        lambda *args, **kwargs: {"months": 12, "failures": ["source-year-unavailable"]},
    )
    acquisition = SimpleNamespace(configuration=SimpleNamespace(storage_directory=tmp_path))
    result = collection.collect_attendance_batch(
        SimpleNamespace(connection=None), acquisition, person_id=selected_person
    )
    assert result["profiles_inspected"] == 3
    assert result["status"] == "partial"
    assert result["coverage"] == "camara_only_other_institutions_pending"
    assert len(result["people"]) == (2 if selected_person is None else 1)
    state = saves[-1]
    assert state["1"]["person_id"] == "canonical-person"
    if selected_person is None:
        assert state["2"]["status"] == "identity_not_in_scope"
    else:
        assert "2" not in state and "3" not in state


def test_published_worker_cli_passes_live_publisher_to_worker(monkeypatch):
    configuration = object()
    client, publisher = object(), object()
    monkeypatch.setattr(voting, "connect_database", lambda _: nullcontext("connection"))
    monkeypatch.setattr(voting, "load_storage_configuration", lambda _: configuration)
    monkeypatch.setattr(voting.httpx, "Client", lambda **kwargs: nullcontext(client))
    monkeypatch.setattr(
        voting,
        "SupabaseDatasetStorage",
        lambda config, transport: (
            publisher if (config is configuration and transport is client) else None
        ),
    )
    monkeypatch.setattr(
        voting,
        "run_voting_worker",
        lambda connection, args, storage: {"published": storage is publisher},
    )
    assert voting.execute_voting_command(arguments(command="voting-worker", local_only=False)) == {
        "published": True
    }


def test_failed_refresh_without_specific_error_metadata_uses_safe_retry_default(monkeypatch):
    failed = []
    monkeypatch.setattr(
        voting,
        "claim_voting_refresh",
        lambda *args: {
            "id": 4,
            "source": "camara",
            "starts_on": date(2026, 5, 1),
            "ends_on": date(2026, 5, 27),
        },
    )

    def unavailable(*args):
        raise RuntimeError("source unavailable")

    monkeypatch.setattr(voting, "run_requested_refresh", unavailable)
    monkeypatch.setattr(voting, "describe_error", lambda error: {})
    monkeypatch.setattr(voting, "fail_voting_refresh", lambda *args: failed.append(args))
    results = voting.process_voting_jobs(None, arguments(max_jobs=1), None, "worker")
    assert results == [{"source": "camara", "status": "failed", "code": "FAILED"}]
    assert failed[0][1:] == (4, "worker", "FAILED", 3600)


def test_build_strategy_selects_distinct_exporters_for_public_timeline():
    publisher, exporter, parser = analytical.dataset_build_strategy("build-voting-timeline")
    assert publisher.__name__ == "publish_person_voting_timeline"
    assert exporter is analytical.export_person_voting_timeline
    assert parser == "canonical-voting-timeline-v1"
    publisher, exporter, parser = analytical.dataset_build_strategy("build-dataset")
    assert publisher is analytical.publish_person_votes
    assert exporter is analytical.export_person_votes
    assert parser == "canonical-votes-v1"


def test_daemon_worker_sleeps_between_bounded_batches(monkeypatch):
    processed, slept = [], []
    monkeypatch.setattr(voting, "process_voting_jobs", lambda *args: processed.append(args) or [])

    def stop_after_first_poll(seconds):
        slept.append(seconds)
        raise KeyboardInterrupt

    monkeypatch.setattr(voting.time, "sleep", stop_after_first_poll)
    with pytest.raises(KeyboardInterrupt):
        voting.run_voting_worker(None, arguments(local_only=False, daemon=True), "publisher")
    assert len(processed) == 1
    assert slept == [5]
