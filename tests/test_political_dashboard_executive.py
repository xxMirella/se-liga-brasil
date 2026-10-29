"""Executive panel cards: party attribution and year precision stay evidence-bound."""

from datetime import date

from service.political_dashboard.aggregation import build_dashboard
from service.political_dashboard.contracts import DashboardQuery
from service.political_dashboard.page import render_dashboard

TODAY = date(2026, 10, 22)

def test_executive_year_precision_keeps_each_person_without_invented_days():
    data = build_dashboard([], DashboardQuery("SP", date(1891, 12, 31)))
    data["presidency"] = {
        "coverage": "observed_partial",
        "current": None,
        "segments": [
            {
                "name": "Pessoa histórica A",
                "person_id": "chronology:one",
                "political_party": "Filiação histórica não verificada",
                "year_start": 1889,
                "year_end": 1891,
                "date_precision": "year",
                "evidence": [{"url": "https://www.camara.leg.br/historia/"}],
            },
            {
                "name": "Pessoa histórica B",
                "person_id": None,
                "political_party": "Não verificada",
                "year_start": 1891,
                "year_end": 1894,
                "date_precision": "year",
            },
        ],
    }
    html = render_dashboard(data, TODAY)
    assert "Pessoa histórica A" in html and "Pessoa histórica B" in html
    assert "Filiação histórica não verificada" in html
    assert 'href="/pessoas/chronology' not in html
    assert "1889-01-01" not in html and "1891-01-01" not in html
    assert "Datas precisas" not in html
    from service.political_dashboard.page import (
        render_executive_period,
        render_executive_source,
    )

    first, second = data["presidency"]["segments"]
    assert render_executive_period(first) == (
        "1889–1891 · Datas precisas ainda não verificadas"
    )
    assert "1894-01-01" not in render_executive_period(second)
    assert "https://www.camara.leg.br/historia/" in render_executive_source(first)  # hardcode-ok: URL esperada da fixture oficial  # noqa: E501
    assert render_executive_source(second) == ""


def test_verified_historical_affiliation_has_its_own_official_evidence_link():
    data = build_dashboard([], DashboardQuery("SP", date(1923, 12, 31)))
    data["presidency"] = {
        "coverage": "observed_partial",
        "segments": [
            {
                "name": "Pessoa histórica",
                "person_id": None,
                "political_party": "Partido documentado",
                "year_start": 1922,
                "year_end": 1926,
                "date_precision": "year",
                "political_party_evidence": [{"url": "https://www.camara.leg.br/historia/partido"}],
            }
        ],
    }
    html = render_dashboard(data, TODAY)
    assert "Partido documentado" in html
    assert "filiação contínua" not in html
    from service.political_dashboard.page import render_executive_political_party_sources

    sources = render_executive_political_party_sources(data["presidency"]["segments"][0])
    assert 'aria-label="Fonte da filiação"' in sources
    assert "https://www.camara.leg.br/historia/partido" in sources  # hardcode-ok: URL esperada da fixture oficial  # noqa: E501
    assert 'target="_blank" rel="noopener noreferrer"' in sources


def test_qualified_presidential_party_is_not_labelled_continuous_affiliation():
    from service.political_dashboard.page import render_executive

    html = render_executive({"segments": [{
        "name": "Presidente", "political_party": "PT", "year_start": 2023, "year_end": 2026,
        "date_precision": "year",
        "political_party_status": "verified_official_presidential_term_party",
        "political_party_evidence": [{"url": "https://www.camara.leg.br/deputados/1"}],
    }]}, "Presidência", "Executivo")
    assert "<p>PT</p>" in html
    assert "filiação contínua" not in html
    assert "Filiação contínua" not in html
    from service.political_dashboard.page import (
        render_executive_political_party,
        render_executive_political_party_sources,
    )

    segment = {
        "political_party": "PT",
        "political_party_status": "verified_official_presidential_term_party",
        "political_party_evidence": [{"url": "https://www.camara.leg.br/deputados/1"}],  # hardcode-ok: URL de fixture da entrada do teste  # noqa: E501
    }
    party = render_executive_political_party(segment)
    assert "Partido informado para o mandato" in party
    assert 'class="panorama-executive-party">PT</strong>' in party
    assert "não comprova filiação contínua" in party
    assert "Fonte do partido informado para o mandato" in (
        render_executive_political_party_sources(segment)
    )


