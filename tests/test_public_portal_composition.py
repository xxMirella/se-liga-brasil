"""Transport and projection boundaries remain read-only and preserve explicit scopes."""

from contextlib import nullcontext
from datetime import date
from types import SimpleNamespace

import pytest

from application.public_portal import PublicPortalApplication, dispatch_portal_request
from service.public_profile import PublicProfileError

PERSON = "00000000-0000-0000-0000-000000000001"
TODAY = date(2026, 10, 19)


def application(monkeypatch):
    connection = SimpleNamespace(transaction=lambda: nullcontext(), execute=lambda *_: None)
    monkeypatch.setattr("database.operations.connect_database", lambda *_: nullcontext(connection))
    return PublicPortalApplication(None, "dataset-reader", today=lambda: TODAY), connection


def test_profile_composes_existing_projections_without_source_requests(monkeypatch):
    app, _ = application(monkeypatch)
    monkeypatch.setattr(
        "database.alerj_history.fetch_person_historical_activity",
        lambda *_: {"items": [], "coverage": "partial_official_synopsis"},
    )
    monkeypatch.setattr(
        "service.public_profile.people.get_public_person", lambda *_: {"person_id": PERSON}
    )
    monkeypatch.setattr(
        "service.public_profile.assets.get_public_assets", lambda *_: {"declarations": []}
    )
    monkeypatch.setattr(
        "database.attendance.fetch_person_attendance", lambda *_: {"percentage": "80.0"}
    )
    monkeypatch.setattr("database.attendance.fetch_person_attendance_history", lambda *_: [])
    monkeypatch.setattr("database.office_legal_scopes.fetch_public_office_scopes", lambda *_: [])
    monkeypatch.setattr(
        "database.cabinet_payroll.fetch_cabinet_payroll_history",
        lambda *_: {"months": [], "truncated": False},
    )
    pages = []
    monkeypatch.setattr(
        "database.public_propositions.fetch_person_propositions",
        lambda _c, _p, _d, page: pages.append(page) or {"items": []},
    )
    result = app.fetch_person(PERSON, proposal_page=2)
    assert result["attendance"]["percentage"] == "80.0"
    assert result["propositions"] == {"items": []}
    assert pages == [2]
    assert result["cabinet_payroll"]["latest"] is None


def test_missing_person_stops_before_other_projection_queries(monkeypatch):
    app, _ = application(monkeypatch)

    def missing(*_):
        raise PublicProfileError("PERSON_NOT_FOUND", 404)

    monkeypatch.setattr("service.public_profile.people.get_public_person", missing)
    with pytest.raises(PublicProfileError, match="PERSON_NOT_FOUND"):
        app.fetch_person(PERSON)


def test_search_preserves_typed_limit_and_filters(monkeypatch):
    app, _ = application(monkeypatch)
    captured = []
    monkeypatch.setattr(
        "service.public_profile.people.search_people",
        lambda _r, query, _d: captured.append(query) or {"items": []},
    )
    assert app.fetch_people({"q": "Pessoa", "uf": "SP", "limit": "12"}) == {"items": []}
    assert captured[0].limit == 12
    assert captured[0].uf == "SP"
    with pytest.raises(ValueError):
        app.fetch_people({"limit": "not-a-number"})


def test_history_request_passes_exercise_and_reader(monkeypatch):
    app, _ = application(monkeypatch)
    captured = []
    monkeypatch.setattr(
        "service.public_profile.storage_history.get_person_storage_history",
        lambda _r, reader, person, **kw: captured.append((reader, person, kw)) or {},
    )
    app.fetch_history(PERSON, {"exercise_id": "42", "limit": "8", "cursor": "page"})
    assert captured[0] == (
        "dataset-reader",
        PERSON,
        {
            "office_kind": None,
            "exercise_id": 42,
            "cursor": "page",
            "limit": 8,
            "as_of": TODAY,
        },
    )
    with pytest.raises(ValueError):
        app.fetch_history(PERSON, {"exercise_id": "invalid"})


def test_period_vote_scope_removes_only_the_scope_marker(monkeypatch):
    app, _ = application(monkeypatch)
    received = []
    monkeypatch.setattr(
        "service.public_profile.storage_votes.get_person_storage_votes",
        lambda _r, _d, query: received.append(query) or {"items": []},
    )
    app.fetch_votes(
        PERSON,
        {"scope": "period", "start_date": "2026-10-01", "end_date": "2026-10-19", "limit": "5"},
    )
    assert received[0].limit == 5
    assert received[0].person_id == PERSON
    with pytest.raises(PublicProfileError, match="INVALID_TIMELINE_SCOPE"):
        app.fetch_votes(PERSON, {"scope": "invalid"})


class ProfileApplication(PublicPortalApplication):
    def __init__(self):
        super().__init__(None, None, today=lambda: TODAY)
        self.pages = []
        self.votes = []

    def fetch_person(self, person_id, *, proposal_page=1):
        self.pages.append(proposal_page)
        return {"person_id": person_id, "propositions": {"items": []}}

    def fetch_votes(self, person_id, parameters):
        self.votes.append(parameters)
        return {"items": []}


@pytest.mark.parametrize("page", ["0", "1001", "bad", "-1"])
def test_bad_proposal_page_is_rejected_before_data_access(page):
    app = ProfileApplication()
    response = dispatch_portal_request(app, f"/pessoas/{PERSON}?proposal_page={page}")
    assert response.status == 400
    assert app.pages == []


def test_proposal_pagination_does_not_leak_into_vote_query():
    app = ProfileApplication()
    response = dispatch_portal_request(app, f"/pessoas/{PERSON}?tab=activity&proposal_page=2")
    assert response.status == 200
    assert app.pages == [2]
    assert "proposal_page" not in app.votes[0]


@pytest.mark.parametrize(
    "target",
    [
        f"/api/people/{PERSON}?proposal_page=2",
        f"/pessoas/{PERSON}/votes",
        "https://example.org/pessoas",
        "/pessoas#private",
        "/not-found",
        "/" + "a" * 4097,
    ],
)
def test_invalid_routes_never_turn_into_person_queries(target):
    app = ProfileApplication()
    assert dispatch_portal_request(app, target).status in {400, 404}
    assert app.pages == []
