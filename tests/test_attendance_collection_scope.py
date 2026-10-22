"""Attendance batches prioritize known people and preserve explicit year scope."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from application.attendance import parse_attendance_years
from crawlers.camara.attendance import validate_attendance_years
from service.attendance import collection
from service.ingestion.contracts import IngestionError


def test_explicit_years_are_bounded_and_do_not_expand_to_entire_career():
    assert validate_attendance_years([2026, 2026], 2023, 2026) == [2026]
    assert validate_attendance_years([2020, 2026], 2023, 2026) == [2026]
    assert validate_attendance_years(None, 2023, 2026) == [2026, 2025, 2024, 2023]
    assert parse_attendance_years("all") is None
    for years in ([], [1999], [2027], [True]):
        with pytest.raises(IngestionError, match="INVALID_ATTENDANCE_YEARS"):
            validate_attendance_years(years, 2000, 2026)


def test_verified_profiles_take_precedence_over_low_source_ids(monkeypatch):
    artifact = object()
    monkeypatch.setattr(collection, "cached_profile_artifact", lambda *_: artifact)
    monkeypatch.setattr(
        collection, "resolve_voting_people", lambda *_: {"99": {"person_id": "verified"}}
    )
    acquisition = SimpleNamespace(configuration=None)
    assert collection.prepare_attendance_profiles(
        acquisition, {"1": {}, "99": {}}, {}, 1, connection="database"
    ) == {"99": artifact}


def test_person_filter_does_not_spend_profile_budget_on_other_people(monkeypatch):
    artifact = object()
    monkeypatch.setattr(collection, "cached_profile_artifact", lambda *_: artifact)
    monkeypatch.setattr(
        collection, "resolve_voting_people", lambda *_: {"99": {"person_id": "expected"}}
    )
    acquisition = Mock(configuration=None)
    result = collection.prepare_attendance_profiles(
        acquisition, {"1": {}, "99": {}}, {}, 1,
        connection="database", person_id="expected",
    )
    assert result == {"99": artifact}
    acquisition.json_document.assert_not_called()


def test_interrupted_batch_preserves_success_and_checkpoint(monkeypatch, tmp_path):
    monkeypatch.setattr(collection, "discover_attendance_members", lambda *_: {"1": {}, "2": {}})
    monkeypatch.setattr(
        collection, "prepare_attendance_profiles", lambda *_, **__: {"1": None, "2": None}
    )
    monkeypatch.setattr(collection, "resolve_voting_people", lambda *_: {
        "1": {"person_id": "first"}, "2": {"person_id": "second"},
    })
    monkeypatch.setattr(collection, "collect_attendance_history", Mock(side_effect=[
        {"years": [{"year": 2026}], "failures": []},
        IngestionError("HTTP_ERROR", {"status": 429}),
    ]))
    acquisition = SimpleNamespace(configuration=SimpleNamespace(storage_directory=tmp_path))
    result = collection.collect_attendance_batch(
        SimpleNamespace(connection=None), acquisition, years=[2026]
    )
    assert [person["person_id"] for person in result["people"]] == ["first"]
    assert result["failures"][0]["status"] == 429
    checkpoint = collection.load_json(tmp_path / "attendance/years-2026.json")
    assert "1" in checkpoint and "2" not in checkpoint
