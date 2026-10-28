"""Closed institutions must not be presented as unreported political parties."""

from service.senate_history.institutional_context import attach_senate_institutional_context
from service.senate_history.rosters import attach_historical_rosters


def test_closed_years_are_contextual_and_transition_years_are_not_claimed():
    partitions = attach_senate_institutional_context([])
    indexed = {row["year"]: row for row in partitions}
    assert set(indexed) == {*range(1931, 1935), *range(1938, 1946)}
    assert indexed[1945]["institutional_status"] == "suspended_whole_year"
    assert indexed[1938]["total"] is None
    assert indexed[1938]["political_parties"] == []
    assert indexed[1938]["institutional_status_evidence"]["url"].startswith("https://")


def test_imperial_roster_preserves_source_identity_without_inventing_affiliation():
    roster = {"source_person_id": "1363", "name": "Nome histórico", "uf": "RN",
              "legislature": 1, "period_start": "1826-05-06", "period_end": "1829-09-03"}
    partitions = attach_historical_rosters([], [roster], 1826, 1829)
    national = next(row for row in partitions if row["year"] == 1826
                    and row["territory_code"] == "BR")
    assert national["coverage"] == "legislature_roster_only"
    assert national["total"] is None
    assert national["political_parties"] == []
    assert national["historical_roster"][0]["source_person_id"] == "1363"


def test_suspension_applies_to_existing_state_without_inventing_other_territories():
    partitions = attach_senate_institutional_context([
        {"year": 1933, "territory_code": "SP", "historical_roster": [{"name": "Arquivo"}]},
        {"year": 1935, "territory_code": "SP"},
    ])
    indexed = {(row["year"], row["territory_code"]): row for row in partitions}
    assert indexed[1933, "SP"]["institutional_status"] == "suspended_whole_year"
    assert "institutional_status" not in indexed[1935, "SP"]
    assert (1933, "AC") not in indexed
    assert indexed[1933, "SP"]["historical_roster"] == [{"name": "Arquivo"}]
