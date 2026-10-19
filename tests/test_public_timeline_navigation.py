"""Timeline navigation resets stale filters and keeps an explicit historical scope."""

from datetime import date
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest

from application.public_portal import PublicPortalApplication, dispatch_portal_request
from service.public_profile_web.forms import render_vote_filters
from service.public_profile_web.pages import render_tabs
from service.public_profile_web.security import query_link

PERSON_ID = "00000000-0000-0000-0000-000000000001"
PERSON_PATH = f"/pessoas/{PERSON_ID}"


class NavigationMarkup(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.links = []
        self.inputs = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))
        if tag == "input":
            self.inputs.append(dict(attrs))


def portal():
    return PublicPortalApplication(None, None, today=lambda: date(2026, 10, 18))


def test_activity_tab_resets_period_office_exercise_and_cursor():
    stale = {
        "tab": "activity",
        "scope": "period",
        "start_date": "2026-01-01",
        "end_date": "2026-01-31",
        "office_kind": "senator",
        "exercise_id": "9",
        "cursor": "old-page",
        "limit": "1",
    }
    markup = NavigationMarkup(render_tabs(PERSON_PATH, stale, "activity"))
    activity = next(link for link in markup.links if link.get("aria-current") == "page")
    destination = urlsplit(activity["href"])
    assert destination.path == PERSON_PATH
    assert parse_qs(destination.query) == {"tab": ["activity"], "scope": ["history"]}
    assert all(link["href"] != "/como-funciona" for link in markup.links)


def test_manual_filters_choose_period_without_redundant_history_link():
    filters = portal().profile_filters({"tab": "activity"})
    markup = NavigationMarkup(render_vote_filters(PERSON_PATH, {"exercises": []}, filters))
    hidden = {item["name"]: item["value"] for item in markup.inputs if item["type"] == "hidden"}
    assert hidden == {"tab": "activity", "scope": "period"}
    date_controls = {item["name"]: item for item in markup.inputs if item["type"] == "date"}
    assert date_controls["start_date"]["value"] == ""
    assert date_controls["end_date"]["value"] == ""
    assert all("required" in item for item in date_controls.values())
    assert not markup.links


def test_default_activity_scope_is_history():
    assert portal().profile_filters({"tab": "activity"})["scope"] == "history"


@pytest.mark.parametrize(
    "dates",
    [
        {"start_date": "2026-10-01"},
        {"end_date": "2026-10-15"},
        {"start_date": "2026-10-01", "end_date": "2026-10-15"},
    ],
)
def test_explicit_dates_choose_period(dates):
    filters = portal().profile_filters({"tab": "activity", **dates})
    assert filters["scope"] == "period"
    assert all(filters[key] == value for key, value in dates.items())


def test_explicit_history_scope_survives_form_default_dates():
    filters = portal().profile_filters({"tab": "activity", "scope": "history"})
    destination = query_link(PERSON_PATH, filters | {"cursor": "next-page"})
    query = parse_qs(urlsplit(destination.replace("&amp;", "&")).query)
    assert query["scope"] == ["history"]
    assert query["cursor"] == ["next-page"]


@pytest.mark.parametrize("scope", ["all", "invalid", "HISTORY"])
def test_invalid_scope_returns_400_before_any_data_access(scope):
    response = dispatch_portal_request(portal(), f"{PERSON_PATH}?tab=activity&scope={scope}")
    assert response.status == 400
    assert response.content_type.startswith("text/html")
    assert b"INVALID_TIMELINE_SCOPE" not in response.body
