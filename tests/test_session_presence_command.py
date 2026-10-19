"""Daily frequency collection validates scope before touching networks or databases."""

from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace

import pytest

from application import session_presence


def arguments(tmp_path, start="2026-05-27", end=None):
    return SimpleNamespace(
        start_date=start, end_date=end, storage_directory=tmp_path, env_file=None
    )


@pytest.mark.parametrize(
    "start,end",
    [
        (None, None),
        ("1999-12-31", None),
        ("2026-05-28", "2026-05-27"),
        ("2026-01-01", "2026-02-01"),
        ("2999-01-01", None),
        ("invalid", None),
    ],
)
def test_invalid_scope_is_rejected_without_connecting(tmp_path, monkeypatch, start, end):
    def forbidden(*_):
        raise AssertionError("An invalid scope must not open a database connection")

    monkeypatch.setattr(session_presence, "connect_database", forbidden)
    with pytest.raises(ValueError):
        session_presence.execute_session_presence_command(arguments(tmp_path, start, end))


def test_day_range_publishes_explicit_frequency_without_claiming_vote_eligibility(
    tmp_path, monkeypatch
):
    collected, published = [], []
    monkeypatch.setattr(session_presence, "connect_database", lambda *_: nullcontext("database"))
    monkeypatch.setattr(session_presence.httpx, "Client", lambda **_: nullcontext("http"))
    monkeypatch.setattr(session_presence, "load_storage_configuration", lambda *_: "configuration")
    storage = SimpleNamespace(ensure_private_bucket=lambda: None)
    monkeypatch.setattr(session_presence, "SupabaseDatasetStorage", lambda *_: storage)
    monkeypatch.setattr(
        session_presence, "official_source_acquisition", lambda *_: nullcontext("source")
    )

    def collect(acquisition, connection, day):
        assert acquisition == "source" and connection == "database"
        collected.append(day)
        return [], {"unresolved_people": 513}

    def publish(directory, publisher, day, rows, coverage):
        assert publisher is storage and coverage["unresolved_people"] == 513
        published.append(day)
        return {"row_count": 0}

    monkeypatch.setattr(session_presence, "collect_daily_presence", collect)
    monkeypatch.setattr(session_presence, "publish_daily_presence", publish)
    result = session_presence.execute_session_presence_command(
        arguments(tmp_path, "2026-05-27", "2026-05-28")
    )
    assert collected == published == [date(2026, 5, 27), date(2026, 5, 28)]
    assert result["status"] == "partial"
    assert result["coverage"] == "plenary_sessions_not_vote_eligibility"


def test_default_storage_directory_and_single_day_scope(tmp_path, monkeypatch):
    monkeypatch.setattr(session_presence, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(session_presence, "connect_database", lambda *_: nullcontext(None))
    monkeypatch.setattr(session_presence.httpx, "Client", lambda **_: nullcontext(None))
    monkeypatch.setattr(session_presence, "load_storage_configuration", lambda *_: None)
    monkeypatch.setattr(
        session_presence,
        "SupabaseDatasetStorage",
        lambda *_: SimpleNamespace(ensure_private_bucket=lambda: None),
    )
    monkeypatch.setattr(
        session_presence, "official_source_acquisition", lambda *_: nullcontext(None)
    )
    monkeypatch.setattr(session_presence, "collect_daily_presence", lambda *_: ([], {}))
    directories = []
    monkeypatch.setattr(
        session_presence,
        "publish_daily_presence",
        lambda directory, *_: directories.append(directory) or {"row_count": 0},
    )
    args = arguments(tmp_path)
    args.storage_directory = None
    result = session_presence.execute_session_presence_command(args)
    assert len(result["days"]) == 1
    assert directories == [tmp_path / "data/enrichment/datasets"]
