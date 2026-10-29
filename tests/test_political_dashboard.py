"""Political composition never extrapolates observed affiliations into the past."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from application.public_portal import PublicPortalApplication, dispatch_portal_request
from service.political_dashboard.aggregation import build_composition, build_dashboard
from service.political_dashboard.contracts import STATE_NAMES, DashboardQuery
from service.political_dashboard.page import render_dashboard
from service.public_profile import PublicProfileError

TODAY = date(2026, 10, 22)
PERSON = "00000000-0000-0000-0000-000000000001"


def observation(day=TODAY, *, person_id=PERSON, political_party="ABC", active=True):
    return {
        "person_id": person_id,
        "display_name": "Pessoa <teste>",
        "observed_on": day,
        "institution_code": "senado",
        "observation": {
            "inExercise": active,
            "representedUf": "SP",
            "politicalPartyAbbreviation": political_party,
        },
    }


def test_national_state_catalog_and_historical_validation():
    assert len(STATE_NAMES) == 27
    for uf in STATE_NAMES:
        assert DashboardQuery.from_parameters({"uf": uf, "year": "2000"}, TODAY).uf == uf


@pytest.mark.parametrize(
    "parameters",
    [
        {"uf": "XX"},
        {"senate_uf": "XX"},
        {"date": "1826-05-05"},
        {"date": "2026-10-23"},
        {"date": "bad"},
        {"date": "2026-02-30"},
    ],
)
def test_invalid_filters_are_rejected(parameters):
    with pytest.raises(PublicProfileError):
        DashboardQuery.from_parameters(parameters, TODAY)


def test_latest_dated_observation_does_not_mix_current_and_old_party():
    rows = [observation(date(2020, 1, 1), political_party="ANT"), observation()]
    result = build_composition(rows, "senado")
    assert result["total"] == 1
    assert result["political_parties"] == [{"abbreviation": "ABC", "count": 1}]
    assert result["observed_on"] == "2026-10-22"
    assert build_composition(rows[:1], "senado")["political_parties"][0]["abbreviation"] == "ANT"


def test_inactive_holder_is_not_counted_with_active_substitute():
    rows = [observation(active=False), observation(person_id=PERSON[:-1] + "2")]
    assert build_composition(rows, "senado")["total"] == 1


def test_unknown_affiliation_is_retained_and_no_canonical_party_lookup_is_required():
    result = build_composition([observation(political_party=None)], "senado")
    assert result["total"] == 1
    assert result["political_parties"][0]["abbreviation"] == "Filiação não informada"
    assert build_composition([observation(political_party="PODE")], "senado")["total"] == 1


def test_uf_filter_and_empty_coverage_do_not_invent_government_or_assembly():
    assert build_composition([observation()], "senado", "RJ")["total"] == 0
    query = DashboardQuery("AC", TODAY)
    result = build_dashboard([], query)
    assert result["assembly"]["total"] == 0
    assert result["government"] == {"coverage": "not_available", "segments": []}
    assert result["history"][0]["year"] == 1826
    assert all(not year["senate_observations"] for year in result["history"])


def test_html_escapes_names_links_sources_and_uses_real_counts():
    data = build_dashboard([observation()], DashboardQuery("SP", TODAY))
    html = render_dashboard(data, TODAY)
    assert "Pessoa &lt;teste&gt;" in html
    assert 'target="_blank" rel="noopener noreferrer"' in html
    assert 'name="territory"' in html
    assert 'name="senate_uf"' not in html
    assert 'href="/fontes-dos-dados#presidencia"' in html
    assert "Prévia visual" not in html
    assert 'aria-current="page">Panorama político' in html
    assert "<script" not in html


@pytest.mark.parametrize("path", ["/panorama", "/api/political-dashboard"])
def test_public_routes_are_available(path):
    data = build_dashboard([], DashboardQuery("RJ", TODAY))
    app = SimpleNamespace(fetch_political_dashboard=lambda _: data, today=lambda: TODAY)
    response = dispatch_portal_request(app, path + "?uf=RJ&year=2026")
    assert response.status == 200
    if path.startswith("/api/"):
        assert json.loads(response.body)["uf"] == "RJ"
    else:
        assert b"Rio de Janeiro" in response.body


def test_route_rejects_duplicate_or_unknown_query_parameters_before_database():
    app = SimpleNamespace()
    for query in ["uf=SP&uf=RJ", "evil=1"]:
        response = dispatch_portal_request(app, "/panorama?" + query)
        assert response.status == 400


def test_public_request_uses_selected_preaggregated_partitions(monkeypatch):
    from test_request_optimizations import idle_connection_stub

    calls = []
    monkeypatch.setattr(
        "database.public_read_connections.open_public_read_connection",
        lambda _env: idle_connection_stub(),
    )
    monkeypatch.setattr(
        "database.political_dashboard_analytical.AnnualDashboardRepository.fetch_annual_snapshot",
        lambda _self, *args: calls.append(args) or {"partitions": [], "history": []},
    )
    monkeypatch.setattr(
        "database.political_dashboard_analytical.AnnualDashboardRepository.is_available",
        lambda _self: True,
    )
    monkeypatch.setattr(
        "database.political_dashboard_analytical.AnnualDashboardRepository.fetch_history",
        lambda _self, *_args: [],
    )
    app = PublicPortalApplication(None, None, today=lambda: TODAY)
    assert app.fetch_political_dashboard({"uf": "RJ"})["uf"] == "RJ"
    assert calls == [(2026, ["BR"], 2026)]
    with pytest.raises(PublicProfileError):
        app.fetch_political_dashboard({"uf": "XX"})
    assert len(calls) == 1


def test_stylesheet_route_is_local_and_white():
    response = dispatch_portal_request(None, "/assets/panorama.css")
    assert response.status == 200
    assert b"background:#fff" in response.body


@pytest.mark.parametrize("year", ["1825", "2027", "2026-01-01", "２026", "bad"])
def test_annual_filter_rejects_invalid_years(year):
    with pytest.raises(PublicProfileError):
        DashboardQuery.from_parameters({"year": year}, TODAY)


def test_closed_year_and_current_year_use_explicit_reference_dates():
    assert DashboardQuery.from_parameters({"year": "1889"}, TODAY).as_of == date(1889, 12, 31)
    assert DashboardQuery.from_parameters({"year": "2025"}, TODAY).as_of == date(2025, 12, 31)
    assert DashboardQuery.from_parameters({"year": "2026"}, TODAY).as_of == TODAY
    with pytest.raises(PublicProfileError):
        DashboardQuery.from_parameters({"year": "2026", "date": "2026-10-01"}, TODAY)


@pytest.mark.parametrize(
    "parameters",
    [
        {"level": "municipal", "uf": "DF"},
        {"municipality_ibge": "123"},
        {"municipality_ibge": "123456x"},
        {"level": "invalid"},
    ],
)
def test_territorial_filters_reject_unavailable_or_invalid_scope(parameters):
    with pytest.raises(PublicProfileError):
        DashboardQuery.from_parameters(parameters, TODAY)


def test_district_history_does_not_retroproject_brasilia():
    query = DashboardQuery.from_parameters({"year": "1900", "uf": "DF", "level": "state"}, TODAY)
    html = render_dashboard(build_dashboard([], query), TODAY)
    assert "tinha sede no Rio de Janeiro" in html
    assert '<select name="year"' not in html
    assert '<input type="number" name="year"' not in html
    assert 'name="date"' not in html


def test_annual_people_count_is_not_rendered_as_simultaneous_seats():
    data = build_dashboard([], DashboardQuery("SP", TODAY))
    composition = data["senate"]
    composition.update(
        total=None,
        members=[
            {
                "name": "Pessoa sem vínculo canônico",
                "person_id": "official:source-one",
                "political_party": "ABC",
                "uf": "SP",
                "observed_on": "2026-01-15",
            }
        ],
        distinct_people_observed_during_year=[{"abbreviation": "ABC", "distinct_people": 2}],
    )
    html = render_dashboard(data, TODAY)
    assert "Pessoas distintas registradas no ano, não cadeiras simultâneas" in html
    assert "Ver integrantes documentados" in html
    assert "Pessoa sem vínculo canônico" in html
    assert "2 pessoas em exercício" not in html


def test_historical_navigation_preserves_selected_territory():
    query = DashboardQuery("SP", TODAY, "RJ", "municipal", "3550308")
    data = build_dashboard([], query)
    data["municipalities"] = [{"ibge_code": "3550308", "name": "São Paulo"}]
    data["history"][-1]["mayoralty_observations"] = 1
    html = render_dashboard(data, TODAY)
    assert "São Paulo · SP" in html
    assert "municipality_ibge=3550308" in html
    assert "territory=SP" in html


def test_annual_route_does_not_accept_a_daily_reference():
    response = dispatch_portal_request(SimpleNamespace(), "/panorama?date=2026-01-01")
    assert response.status == 400


def test_timeline_links_to_documented_year_instead_of_empty_decade_end():
    from service.political_dashboard.timeline import render_timeline_bands

    years = [
        {"year": year, "presidency_observations": int(year == 1930),
         "senate_observations": 0, "assembly_observations": 0}
        for year in range(1930, 1940)
    ]
    html = render_timeline_bands({"history": years, "level": "federal", "uf": "SP",
                                  "year": 1930, "as_of": "1930-12-31"})
    assert "year=1930#panorama-results" in html
    assert "1930 · Partido não informado" in html
    assert "year=1939" not in html


def test_history_without_data_does_not_offer_empty_navigation():
    from service.political_dashboard.timeline import render_timeline_bands

    html = render_timeline_bands({"history": [{"year": 1940, "documented_records": 0,
        "senate_observations": 0, "assembly_observations": 0}],
        "level": "federal", "as_of": "1940-12-31"})
    assert 'href="/panorama?' not in html
    assert "Sem dados" in html


def test_official_source_host_exceptions_do_not_allow_similar_external_hosts():
    from service.public_profile_web.security import official_url

    for hostname in (
        "www.defensoria.rj.def.br", "agenciabrasil.ebc.com.br", "prefeitura.rio",
        "neamp.pucsp.br", "repositorio.unb.br", "psd.org.br",
        "files.ufgd.edu.br", "periodicos.fclar.unesp.br",
        "progressistas.org.br", "uniaobrasil.org.br", "albalegis.nopapercloud.com.br",
    ):
        assert official_url(f"https://{hostname}/noticia")
        assert official_url(f"https://{hostname}.example.com/noticia") is None
        assert official_url(f"https://{hostname}@example.com/noticia") is None
        assert official_url(f"http://{hostname}/noticia") is None


@pytest.mark.parametrize("uf", STATE_NAMES)
def test_geographic_navigation_selects_state_and_its_senators(uf):
    query = DashboardQuery.from_parameters({"territory": uf}, TODAY)
    assert query.uf == uf
    assert query.senate_uf == uf
    assert query.level == "state"
    assert query.as_of == TODAY


def test_municipality_navigation_keeps_parent_state():
    query = DashboardQuery.from_parameters(
        {"territory": "SP", "municipality_ibge": "3550308"}, TODAY,
    )
    assert query.level == "municipal"
    assert query.uf == "SP"
    assert query.municipality_ibge == "3550308"


def test_state_navigation_exposes_municipalities_without_year_filter():
    from service.political_dashboard.page import render_filters

    data = build_dashboard([], DashboardQuery("SP", TODAY, "SP", "state"))
    data["municipalities"] = [{"ibge_code": "3550308", "name": "São Paulo"}]
    html = render_filters(data, TODAY)
    assert 'name="year"' not in html
    assert 'name="level"' not in html
    assert 'name="territory"' in html
    assert 'name="municipality_ibge"' in html
    assert '<option value="3550308">São Paulo</option>' in html
    assert html.count("<form ") == 2
    assert "Municípios de São Paulo" in html


def test_district_navigation_does_not_offer_municipalities():
    from service.political_dashboard.page import render_filters

    data = build_dashboard([], DashboardQuery("DF", TODAY, "DF", "state"))
    assert 'name="municipality_ibge"' not in render_filters(data, TODAY)
