"""Remaining mandate uses documented exclusive dates for every office kind."""
from datetime import date

import pytest

from service.public_profile.term_duration import remaining_term
from service.public_profile_web.profile import render_remaining_term


@pytest.mark.parametrize("office_kind", ["senator", "governor", "councillor", "state_deputy"])
def test_documented_term_boundary_for_all_offices(office_kind):
    duration = remaining_term(date(2027, 2, 1), date(2026, 10, 22))
    assert duration["years"] == 0
    assert duration["months"] == 3
    assert duration["days"] == 10
    assert duration["total_days"] == 102
    assert duration["last_day"] == "2027-01-31"
    markup = render_remaining_term({"office_kind": office_kind, "remaining_term": duration})
    assert "3 meses e 10 dias" in markup
    assert "2027-01-31" in markup


def test_unknown_end_never_infers_four_or_eight_years():
    assert remaining_term(None, date(2026, 10, 22))["status"] == "unknown"
    assert "Término não informado" in render_remaining_term({"office_kind": "senator"})


def test_substitute_does_not_claim_exercise_until_mandate_end():
    markup = render_remaining_term({
        "capacity": "substitute",
        "remaining_term": remaining_term(date(2031, 2, 1), date(2026, 10, 22)),
    })
    assert "exercício de suplência pode terminar antes" in markup


@pytest.mark.parametrize("boundary", [date(2026, 10, 22), date(2025, 1, 1)])
def test_ended_term_never_has_negative_duration(boundary):
    duration = remaining_term(boundary, date(2026, 10, 22))
    assert (duration["years"], duration["months"], duration["days"]) == (0, 0, 0)


def test_calendar_month_ends_and_leap_year():
    duration = remaining_term(date(2024, 2, 29), date(2024, 1, 31))
    assert (duration["months"], duration["days"]) == (1, 0)
    assert duration["total_days"] == 29
