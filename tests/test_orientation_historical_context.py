from service.political_dashboard.orientation_historical_context import (
    documented_legislative_absence,
)
from service.political_dashboard.timeline import timeline_cell


def test_closed_congress_is_information_even_without_composition_payload():
    for year in range(1938, 1946):
        for code in ("camara", "senado"):
            cell = timeline_cell({"year": year}, code, "legislative", "political_orientation")
            assert cell["state"] == "suspended"
            assert "Parlamento não instalado" in cell["label"]
            assert cell["source_evidence"][0]["scope"] == "institutional_status"


def test_closure_does_not_replace_transition_years_or_other_institutions():
    assert documented_legislative_absence("camara", 1937) is None
    assert documented_legislative_absence("senado", 1946) is None
    assert documented_legislative_absence("presidency", 1940) is None
    assert documented_legislative_absence("state_assembly", 1940) is None
