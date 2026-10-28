from datetime import date

import pytest

from service.political_dashboard.contracts import DashboardQuery
from service.political_dashboard.timeline import timeline_year_url
from service.political_dashboard.view_filter import render_timeline_view_filter
from service.public_profile import PublicProfileError


def test_view_filter_preserves_municipality_and_year_without_visible_year_filter():
    data = {"uf": "SP", "level": "municipal", "municipality_ibge": "3550308",
            "year": 2018, "as_of": "2018-12-31", "view": "political_orientation"}
    form = render_timeline_view_filter(data)
    assert 'action="/panorama#panorama-results"' in form
    assert 'Visualizar composição e linha do tempo por' in form
    assert 'name="territory" value="SP"' in form
    assert 'name="municipality_ibge" value="3550308"' in form
    assert 'name="year" value="2018"' in form
    assert 'value="political_orientation" selected' in form
    assert 'view=political_orientation' in timeline_year_url(data, 2022)
    assert 'municipality_ibge=3550308' in timeline_year_url(data, 2022)


def test_view_defaults_to_party_and_invalid_values_are_rejected():
    today = date(2026, 10, 27)
    assert DashboardQuery.from_parameters({"territory": "BR"}, today).view == "political_party"
    assert DashboardQuery.from_parameters(
        {"territory": "BR", "view": "political_orientation"}, today
    ).view == "political_orientation"
    with pytest.raises(PublicProfileError, match="INVALID_DASHBOARD_VIEW"):
        DashboardQuery.from_parameters({"view": "unknown"}, today)
