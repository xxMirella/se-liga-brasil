"""Timeline colours distinguish dated evidence from complete political composition."""

from service.political_dashboard.timeline import executive_cell, legislative_cell


def test_partial_chamber_cohort_never_looks_like_complete_historical_majority():
    cell = legislative_cell({
        "total": 61, "coverage": "observed_partial",
        "aggregation_basis": "verified_year_end_status_of_current_roster_cohort",
        "political_parties": [{"abbreviation": "PT", "count": 30}],
    })
    assert cell["state"] == "partial"
    assert cell["label"] == "PT"


def test_verified_current_roster_can_use_solid_colour():
    cell = legislative_cell({
        "total": 513, "coverage": "verified_current_roster",
        "political_parties": [{"abbreviation": "PL", "count": 90}],
    })
    assert cell["state"] == "known"


def test_dated_governor_observation_does_not_claim_continuous_affiliation():
    cell = executive_cell({
        "segments": [],
        "national_observations": [{
            "name": "Governadora", "political_party": "PSD",
            "political_party_status": "verified_official_dated_government_observation",
        }],
    })
    assert cell["state"] == "partial"
    assert cell["label"] == "PSD"


def test_equal_largest_groups_are_shown_as_tie():
    cell = legislative_cell({
        "total": 2, "coverage": "verified_current_roster",
        "political_parties": [
            {"abbreviation": "PL", "count": 1}, {"abbreviation": "PSD", "count": 1},
        ],
    })
    assert cell["state"] == "mixed"
    assert cell["label"] == "Empate: PL / PSD"


def test_annual_presidential_transition_is_not_hidden_by_year_end_party():
    cell = executive_cell({
        "current": {"political_party": "PL", "political_party_status": "verified_interval"},
        "segments": [{
            "political_party": "PL", "political_party_status": "verified_interval",
            "political_party_periods": [
                {"political_party": "Sem partido", "political_party_status": "verified_interval"},
                {"political_party": "PL", "political_party_status": "verified_interval"},
            ],
        }],
    })
    assert cell["state"] == "mixed"
    assert cell["label"] == "PL / Sem partido"
