"""Election evidence is visible without becoming Senate seat or affiliation claims."""

from service.political_dashboard.page import render_composition
from service.political_dashboard.senate_election_observations import (
    render_senate_election_observations,
)
from service.political_dashboard.timeline import legislative_cell, timeline_cell
from service.senate_history.institutional_context import attach_senate_institutional_context

OFFICIAL_SOURCE = "https://www12.senado.leg.br/noticias/infomaterias/2026/06/"


def election(year=1986):
    name, political_party = ("Getúlio Vargas", "PTB") if year == 1945 else (
        "Fernando Henrique Cardoso", "PMDB"
    )
    return {"name": name, "election_year": year,
            "territory_code": "SP", "political_party_literal": political_party,
            "political_party_interpretation": "single_label",
            "evidence": {"url": OFFICIAL_SOURCE + "todas-as-eleicoes-para-o-senado-em-sao-paulo"}}


def composition(year):
    return {"year": year, "territory_code": "BR", "institution_code": "senado",
            "total": None, "members": [], "political_parties": [],
            "election_observations": [election(year)]}


def test_1945_renders_suspension_and_separate_election_details():
    partition = next(row for row in attach_senate_institutional_context([composition(1945)])
                     if row["year"] == 1945)
    html = render_composition(partition, "Senado Federal", "Poder legislativo", OFFICIAL_SOURCE)
    assert "Senado sem funcionamento neste ano" in html
    assert "Partidos registrados na eleição deste ano" in html
    assert "Eleição de 1945" in html
    assert "Ser eleito não comprova posse, exercício ou filiação durante todo o ano" in html
    assert "Maior bancada documentada" not in html
    assert "panorama-semicircle" not in html
    assert timeline_cell({"year": 1945, "institutions": [partition]}, "senado", "legislative")[
        "state"
    ] == "suspended"


def test_1986_election_label_is_not_an_annual_composition_or_timeline_majority():
    partition = composition(1986)
    html = render_composition(partition, "Senado Federal", "Poder legislativo", OFFICIAL_SOURCE)
    assert "Fernando Henrique Cardoso" in html and "PMDB" in html
    assert "Esses registros não são usados para calcular a maior bancada" in html
    assert "Maior bancada documentada" not in html
    assert "Composição ainda não documentada" in html
    assert legislative_cell(partition)["state"] == "unknown"
    assert legislative_cell(partition)["label"] != "PMDB"
    assert partition["political_parties"] == [] and partition["total"] is None


def test_electoral_source_links_open_a_new_tab_and_untrusted_source_is_suppressed():
    partition = composition(1986)
    html = render_senate_election_observations(partition)
    assert 'target="_blank" rel="noopener noreferrer"' in html
    partition["election_observations"][0]["evidence"]["url"] = "javascript:alert(1)"
    partition["election_observations"][0]["name"] = "<script>nome</script>"
    html = render_senate_election_observations(partition)
    assert "javascript:" not in html and "<script>" not in html
    assert "&lt;script&gt;nome&lt;/script&gt;" in html
