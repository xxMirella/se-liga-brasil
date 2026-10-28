from service.political_dashboard.composition_presentation import composition_presentation
from service.political_dashboard.page import render_composition_reference


def test_official_aggregate_explains_date_without_claiming_registered_profiles():
    composition = {
        "aggregation_basis": "verified_dated_official_senate_composition",
        "observed_on": "2001-12-17",
    }
    caption = render_composition_reference(composition, False)
    assert "2001-12-17" in caption
    assert "Distribuição agregada" in caption
    assert "relação nominal" in caption
    assert "perfis cadastrados" not in caption


def test_historical_legislature_rosters_remain_explicitly_partial():
    composition = {
        "total": 217,
        "aggregation_basis": "verified_year_end_status_of_historical_legislature_rosters",
    }
    presentation = composition_presentation(composition)
    assert "histórico parcial" in presentation["count_label"]
    assert "composição atual" not in presentation["count_label"]
    assert "Cobertura histórica parcial" in render_composition_reference(composition, False)
