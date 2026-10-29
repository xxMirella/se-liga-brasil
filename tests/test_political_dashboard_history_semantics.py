"""The reduced history draws the same timeline cells as the full annual composition."""

import pytest

from service.political_dashboard.presidential_explanations import presidential_year_explanation
from service.political_dashboard.timeline import timeline_cell
from service.political_dashboard_dataset.history import (
    expand_history_row,
    history_entry,
    reduce_history_row,
)

GOVERNMENT_RECORD = {
    "name": "Someone", "person_id": "p:1", "exercise_id": "p:1:2000-01-01",
    "starts_on": "2000-01-01", "ends_before": "2001-01-01", "source_url": "https://x.invalid/a",
    "observed_through": "2026-01-01", "political_party": "PSDB",
    "political_party_status": "verified_official_government_party_classification",
    "political_party_periods": [{
        "political_party": "PSDB", "political_party_status": "verified_x",
        "starts_on": "2000-01-01", "political_party_context": "context", "source_url": "u",
    }],
}


def stored_row(code, year, composition, kinds=None):
    return {"year": year, "institution_code": code, "territory_code": "SP",
            "office_kinds": kinds, "total": composition.get("total"), "composition": composition}


@pytest.mark.parametrize("view", ["political_party", "political_orientation"])
def test_state_government_cells_survive_reduction_without_names_or_sources(view):
    composition = {
        "institution_code": "state_government", "territory_code": "SP", "total": 1,
        "current": GOVERNMENT_RECORD, "segments": [GOVERNMENT_RECORD],
        "national_observations": [], "coverage": "observed_partial",
    }
    row = stored_row("state_government", 2000, composition)
    reduced = expand_history_row(reduce_history_row(row))["composition"]
    assert "name" not in reduced["segments"][0] and "source_url" not in reduced["current"]
    assert reduced["segments"][0]["political_party_periods"] == [
        {"political_party": "PSDB", "political_party_status": "verified_x"}
    ]
    before = timeline_cell({"year": 2000, "institutions": [composition]},
                           "state_government", "executive", view)
    after = timeline_cell({"year": 2000, "institutions": [reduced]},
                          "state_government", "executive", view)
    assert before == after


def presidency(segments):
    return {"institution_code": "presidency", "territory_code": "BR", "total": len(segments),
            "segments": segments, "current": segments[-1], "government_context_observations": []}


def test_presidential_year_with_a_transition_keeps_what_the_page_explains():
    first = {**GOVERNMENT_RECORD, "person_id": "p:1", "name": "A"}
    second = {**GOVERNMENT_RECORD, "person_id": "p:2", "name": "B", "exercise_id": "p:2:x"}
    composition = presidency([first, second])
    reduced = expand_history_row(reduce_history_row(stored_row("presidency", 2000, composition)))
    explanation = presidential_year_explanation({"year": 2000, "institutions": [composition]})
    after = presidential_year_explanation({"year": 2000, "institutions": [reduced["composition"]]})
    assert explanation and after and explanation["records"] != []
    assert [r["name"] for r in after["records"]] == ["A", "B"]


def test_ordinary_presidential_year_drops_detail_but_keeps_orientation_identity():
    composition = presidency([GOVERNMENT_RECORD])
    reduced = expand_history_row(reduce_history_row(stored_row("presidency", 2001, composition)))
    segment = reduced["composition"]["segments"][0]
    assert "name" not in segment and segment["exercise_id"] == "p:1:2000-01-01"
    for view in ("political_party", "political_orientation"):
        row = {"year": 2001, "institutions": [composition]}
        slim = {"year": 2001, "institutions": [reduced["composition"]]}
        assert timeline_cell(row, "presidency", "executive", view) == timeline_cell(
            slim, "presidency", "executive", view)


def test_history_entry_is_deterministic_for_unchanged_data():
    rows = [stored_row("senado", 2000, {"total": 81, "political_parties": []})]
    first, second = history_entry("SP", rows), history_entry("SP", rows)
    assert first["content_sha256"] == second["content_sha256"]
