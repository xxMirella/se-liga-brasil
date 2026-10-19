"""Forged cursors and partial acquisitions cannot bypass public or ingestion scopes."""

import base64
import json
from contextlib import nullcontext
from dataclasses import replace
from datetime import date, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from service.ingestion.contracts import IngestionError
from service.public_profile.contracts import PublicProfileError, VoteQuery
from service.public_profile.history_pagination import (
    decode_history_cursor,
    encode_history_cursor,
    history_fingerprint,
)
from service.public_profile.storage_pagination import decode_storage_cursor, encode_storage_cursor
from service.voting_pipeline import consolidation, runtime


def query(**updates):
    return VoteQuery(str(uuid4()), date(2026, 5, 1), date(2026, 5, 31), **updates)


def mutate_cursor(token, updates):
    payload = json.loads(base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)))
    payload.update(updates)
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


@pytest.mark.parametrize(
    "updates",
    [
        {"v": 99},
        {"filters": "wrong"},
        {"snapshot": "../escape"},
        {"position": True},
        {"position": -1},
        {"position": 100001},
        {"date": "2026-04-30", "id": "1"},
        {"date": "2026-05-01", "id": None},
        {"date": None, "id": "1"},
        {"extra": "unexpected"},
    ],
)
def test_history_cursor_rejects_forged_position_filter_and_event_bounds(updates):
    filters = query()
    token = encode_history_cursor("a" * 64, history_fingerprint(filters), 0)
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        decode_history_cursor(replace(filters, cursor=mutate_cursor(token, updates)))


@pytest.mark.parametrize(
    "updates",
    [
        {"v": 99},
        {"filters": "wrong"},
        {"snapshot": "../escape"},
        {"date": "2026-04-30"},
        {"id": 1},
        {"id": "invalid"},
        {"extra": "unexpected"},
    ],
)
def test_daily_storage_cursor_rejects_forged_metadata(updates):
    filters = query()
    token = encode_storage_cursor(
        filters, "a" * 64, {"occurred_on": "2026-05-01", "voting_id": "1"}
    )
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        decode_storage_cursor(replace(filters, cursor=mutate_cursor(token, updates)))


@pytest.mark.parametrize("decoder", [decode_storage_cursor, decode_history_cursor])
@pytest.mark.parametrize("cursor", [123, "x" * 1025, "%%invalid%%"])
def test_cursor_decoders_bound_untrusted_input(decoder, cursor):
    with pytest.raises(PublicProfileError, match="INVALID_CURSOR"):
        decoder(query(cursor=cursor))


@pytest.mark.parametrize(
    "updates,code",
    [
        ({"start_on": datetime(2026, 5, 1)}, "INVALID_PERIOD"),
        ({"start_on": date(2026, 6, 1)}, "INVALID_PERIOD"),
        ({"limit": True}, "INVALID_PAGE_SIZE"),
        ({"office_kind": []}, "INVALID_OFFICE_KIND"),
        ({"exercise_id": True}, "INVALID_EXERCISE_ID"),
        ({"exercise_id": 2**63}, "INVALID_EXERCISE_ID"),
    ],
)
def test_public_query_does_not_accept_ambiguous_scalars(updates, code):
    filters = query()
    with pytest.raises(PublicProfileError, match=code):
        replace(filters, **updates)


@pytest.mark.parametrize(
    "record,code",
    [
        ({"institution_code": "camara", "date_precision": "day"}, "source/day precision"),
        ({"institution_code": "senado", "date_precision": "month"}, "source/day precision"),
        (
            {"institution_code": "senado", "date_precision": "day", "occurred_on": "2026-04-30"},
            "outside the requested interval",
        ),
    ],
)
def test_acquired_records_must_match_source_exact_day_and_period(record, code):
    with pytest.raises(ValueError, match=code):
        consolidation.validate_record_scope(record, "senado", date(2026, 5, 1), date(2026, 5, 31))


def test_retirement_scope_and_budget_checked_before_index_mutation():
    with pytest.raises(ValueError, match="Retirement budget exceeded"):
        consolidation.prepare_retirements(
            [{}] * 1001, "senado", date(2026, 5, 1), date(2026, 5, 31), None
        )
    with pytest.raises(ValueError, match="outside acquired interval"):
        consolidation.prepare_retirements(
            [{"occurred_on": "2026-04-30"}], "senado", date(2026, 5, 1), date(2026, 5, 31), None
        )


def test_unchanged_retirement_is_not_republished():
    index = SimpleNamespace(inspect_retirement=lambda *args: None)
    assert (
        consolidation.prepare_retirements(
            [{"occurred_on": "2026-05-01"}], "senado", date(2026, 5, 1), date(2026, 5, 31), index
        )
        == {}
    )


def test_conflicting_duplicates_do_not_reach_publication(tmp_path):
    path = tmp_path / "input"
    record = {
        "institution_code": "senado",
        "date_precision": "day",
        "occurred_on": "2026-05-01",
        "voting_id": "1",
    }
    path.write_text(json.dumps(record) + "\n" + json.dumps(record) + "\n")
    facts = iter(
        [
            (("person", "senado", "1", "digest-a", "observed"), None),
            (("person", "senado", "1", "digest-b", "observed"), None),
        ]
    )
    index = SimpleNamespace(inspect_record=lambda record: next(facts))
    with pytest.raises(ValueError, match="Conflicting duplicate"):
        consolidation.prepare_daily_changes(
            path, "senado", date(2026, 5, 1), date(2026, 5, 31), tmp_path, index
        )


def test_input_line_budget_is_checked_before_json_or_identity_index(tmp_path, monkeypatch):
    path = tmp_path / "input"
    path.write_text("too-large\n")
    monkeypatch.setattr(consolidation, "MAX_LINE_BYTES", 2)
    with pytest.raises(ValueError, match="record budget"):
        consolidation.prepare_daily_changes(
            path, "senado", date(2026, 5, 1), date(2026, 5, 31), tmp_path, None
        )


def test_database_lock_conflict_prevents_source_access():
    connection = SimpleNamespace(
        execute=lambda *args: SimpleNamespace(fetchone=lambda: {"acquired": False})
    )
    with (
        pytest.raises(IngestionError, match="ALREADY_RUNNING"),
        runtime.official_source_acquisition(
            connection, None, SimpleNamespace(code="senado"), (), None
        ),
    ):
        pytest.fail("Conflicting lock must prevent source entry")


@pytest.mark.parametrize("status,delay", [(429, 30), (503, 7200), (400, 30)])
def test_runtime_only_postpones_transient_or_blocked_sources(monkeypatch, status, delay):
    calls = []
    monkeypatch.setattr(
        runtime,
        "describe_error",
        lambda error: {"status": status, "retry_after_seconds": delay, "code": "SOURCE_FAILURE"},
    )
    monkeypatch.setattr(runtime, "postpone_source", lambda *args: calls.append(args))
    runtime.apply_collection_cooldown(None, "senado", RuntimeError())
    assert calls == (
        [] if status == 400 else [(None, "senado", max(3600, delay), "SOURCE_FAILURE", status)]
    )


def test_runtime_yields_shared_transport_and_unlocks_after_success(monkeypatch, tmp_path):
    calls = []
    connection = SimpleNamespace(
        execute=lambda sql, params: (
            calls.append(sql) or SimpleNamespace(fetchone=lambda: {"acquired": True})
        )
    )
    monkeypatch.setattr(runtime, "check_source_cooldown", lambda *args: None)
    monkeypatch.setattr(runtime, "local_run_lock", lambda path: nullcontext())
    monkeypatch.setattr(runtime.httpx, "Client", lambda **kwargs: nullcontext("client"))
    monkeypatch.setattr(runtime, "OfficialHttpClient", lambda config, client, hosts: "transport")
    config = SimpleNamespace(storage_directory=tmp_path, request_timeout_seconds=30)
    with runtime.official_source_acquisition(
        connection, config, SimpleNamespace(code="senado"), (), lambda config, transport: transport
    ) as acquisition:
        assert acquisition == "transport"
    assert "pg_try_advisory_lock" in calls[0]
    assert "pg_advisory_unlock" in calls[-1]


def test_invalid_public_person_id_has_stable_safe_error():
    with pytest.raises(PublicProfileError, match="INVALID_PERSON_ID"):
        VoteQuery("invalid-id", date(2026, 5, 1), date(2026, 5, 31))


def test_day_correction_emits_explicit_retirement_for_previous_day(tmp_path):
    record = {
        "institution_code": "senado",
        "date_precision": "day",
        "occurred_on": "2026-05-02",
        "voting_id": "1",
    }
    path = tmp_path / "input"
    path.write_text(json.dumps(record) + "\n" + json.dumps(record) + "\n")
    fact = ("canonical", "senado", "1", "digest", "2026-05-03T00:00:00Z")
    index = SimpleNamespace(inspect_record=lambda record: (fact, "2026-05-01"))
    files, facts, removals = consolidation.prepare_daily_changes(
        path, "senado", date(2026, 5, 1), date(2026, 5, 31), tmp_path, index
    )
    assert set(files) == {"2026-05-02"}
    assert facts == [fact]
    assert removals == {("2026-05-01", "1"): fact[4]}


def test_runtime_records_cooldown_and_unlocks_after_acquisition_failure(monkeypatch, tmp_path):
    effects = []
    connection = SimpleNamespace(
        execute=lambda sql, params: (
            effects.append("unlock" if "pg_advisory_unlock" in sql else "lock")
            or SimpleNamespace(fetchone=lambda: {"acquired": True})
        )
    )
    monkeypatch.setattr(runtime, "check_source_cooldown", lambda *args: None)
    monkeypatch.setattr(runtime, "local_run_lock", lambda path: nullcontext())
    monkeypatch.setattr(runtime.httpx, "Client", lambda **kwargs: nullcontext("client"))
    monkeypatch.setattr(runtime, "OfficialHttpClient", lambda *args: None)
    monkeypatch.setattr(
        runtime, "apply_collection_cooldown", lambda *args: effects.append("cooldown")
    )
    config = SimpleNamespace(storage_directory=tmp_path, request_timeout_seconds=30)
    with (
        pytest.raises(RuntimeError, match="source failed"),
        runtime.official_source_acquisition(
            connection, config, SimpleNamespace(code="senado"), (), lambda *args: "source"
        ),
    ):
        raise RuntimeError("source failed")
    assert effects == ["lock", "cooldown", "unlock"]
