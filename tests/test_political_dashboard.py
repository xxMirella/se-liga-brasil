"""Political composition never extrapolates observed affiliations into the past."""

import json
from datetime import date
from types import SimpleNamespace

import pytest

from application.public_portal import PublicPortalApplication, dispatch_portal_request
from service.political_dashboard.aggregation import build_composition, build_dashboard
from service.political_dashboard.contracts import STATE_NAMES, DashboardQuery
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


def test_political_dashboard_api_remains_available_by_territory():
    data = build_dashboard([], DashboardQuery("RJ", TODAY))
    app = SimpleNamespace(fetch_political_dashboard=lambda _: data, today=lambda: TODAY)
    response = dispatch_portal_request(app, "/api/political-dashboard?uf=RJ&year=2026")
    assert response.status == 200
    assert json.loads(response.body)["uf"] == "RJ"


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


def test_annual_route_does_not_accept_a_daily_reference():
    response = dispatch_portal_request(SimpleNamespace(), "/panorama?date=2026-01-01")
    assert response.status == 400


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
