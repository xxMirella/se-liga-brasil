"""Public facts require dated evidence and preserve unavailable attendance."""

from contextlib import nullcontext
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from database.profile_media import ProfileMediaRepository
from service.activity_context.linking import ActivityContext, ActivityContextService
from service.attendance.monthly import consolidate_monthly_attendance
from service.ingestion.contracts import IngestionError


def context(**overrides):
    values = dict(
        source_id=1,
        activity_kind="proposal",
        external_key="proposal:1",
        person_id="person",
        source_record_id=1,
        observed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    return ActivityContext(**(values | overrides))


@pytest.mark.parametrize(
    "override,code",
    [
        ({"activity_kind": " "}, "INVALID_ACTIVITY_CONTEXT"),
        ({"external_key": " "}, "INVALID_ACTIVITY_CONTEXT"),
        ({"observed_at": datetime(2024, 1, 1)}, "INVALID_ACTIVITY_TIMESTAMP"),
        ({"occurred_at": datetime(2024, 1, 1)}, "INVALID_ACTIVITY_TIMESTAMP"),
    ],
)
def test_invalid_activity_never_reaches_repository(override, code):
    repository = SimpleNamespace(link_context=Mock())
    with pytest.raises(IngestionError, match=code):
        ActivityContextService(repository).link_activity(context(**override))
    repository.link_context.assert_not_called()


@pytest.mark.parametrize("occurred", [None, datetime(2024, 1, 1, tzinfo=UTC)])
def test_activity_unknown_date_is_preserved_without_inventing_one(occurred):
    repository = SimpleNamespace(link_context=Mock(return_value=3))
    value = context(occurred_at=occurred)
    assert ActivityContextService(repository).link_activity(value) == 3
    repository.link_context.assert_called_once_with(value)


def test_attendance_months_are_sorted_and_current_month_is_provisional():
    artifact = SimpleNamespace(
        resource=SimpleNamespace(url="https://www.camara.leg.br/presenca"),
        sha256="a" * 64,
        fetched_at="2024-02-29T12:00:00+00:00",
    )
    rows = consolidate_monthly_attendance(
        {
            date(2024, 2, 29): "present",
            date(2024, 1, 31): "excused_absence",
            date(2024, 1, 30): "present",
        },
        "person",
        artifact,
        date(2024, 2, 29),
    )
    assert [row["period"] for row in rows] == ["2024-01", "2024-02"]
    assert Decimal(rows[0]["percentage"]) == Decimal("50")
    assert rows[0]["excusedAbsences"] == 1
    assert rows[0]["partial"] is False and rows[1]["partial"] is True
    assert rows[1]["observedThrough"] == "2024-02-29"


def test_unknown_attendance_does_not_become_zero_percent():
    artifact = SimpleNamespace(
        resource=SimpleNamespace(url="https://www.camara.leg.br/presenca"),
        sha256="a" * 64,
        fetched_at="2024-01-01T12:00:00+00:00",
    )
    row = consolidate_monthly_attendance(
        {date(2024, 1, 1): "unknown"}, "person", artifact, date(2024, 2, 1)
    )[0]
    assert row["percentage"] is None and row["unknown"] == 1
    assert consolidate_monthly_attendance({}, "person", artifact, date(2024, 2, 1)) == []


def test_photo_repository_bounds_reads_and_uses_compare_and_swap():
    response = SimpleNamespace(fetchall=lambda: [], fetchone=lambda: {"updated": 1})
    connection = SimpleNamespace(
        execute=Mock(return_value=response), transaction=lambda: nullcontext()
    )
    repository = ProfileMediaRepository(connection)
    assert repository.fetch_linked_profiles(10) == []
    assert connection.execute.call_args.args[1] == (11,)
    assert (
        repository.save_official_photos(
            [
                {
                    "person_id": "person",
                    "source_record_id": 1,
                    "photo_url": "https://www.camara.leg.br/foto.jpg",
                    "previous_photo_url": None,
                    "private_extra": "must not be forwarded",
                }
            ]
        )
        == 1
    )
    payload = connection.execute.call_args.args[1][0].obj
    assert "private_extra" not in payload[0]
    assert "IS NOT DISTINCT FROM photo.previous_photo_url" in connection.execute.call_args.args[0]
    assert repository.fetch_person_photo_coverage() == {"updated": 1}


@pytest.mark.parametrize("apply", [False, True])
def test_photo_maintenance_command_defaults_to_dry_run(monkeypatch, tmp_path, capsys, apply):
    import service.profile_media.__main__ as command

    repository = SimpleNamespace(
        fetch_linked_profiles=lambda _: [],
        fetch_person_photo_coverage=lambda: {"total_people": 0},
    )
    monkeypatch.setattr(command, "connect_database", lambda _: nullcontext(object()))
    monkeypatch.setattr(command, "ProfileMediaRepository", lambda _: repository)
    backfill = Mock(return_value={"updated": 0})
    monkeypatch.setattr(command, "backfill_profile_photos", backfill)
    monkeypatch.setattr(command, "summarize_profiles", lambda _: {})
    argv = ["profile-media", "--env-file", str(tmp_path / "test.env")]
    monkeypatch.setattr("sys.argv", argv + (["--apply"] if apply else []))
    command.main()
    assert backfill.call_args.kwargs["apply"] is apply
    assert '"person_coverage"' in capsys.readouterr().out
