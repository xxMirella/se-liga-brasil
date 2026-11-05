"""Period section fragments: cards, seats card, verdict and reading section."""

import re

from period_fixtures import period_panorama

from service.majority_panorama.period_cards import majority_note, render_period_cards
from service.majority_panorama.period_section import render_period_section
from service.majority_panorama.period_selection import (
    format_percent,
    main_president,
    selected_legislature_index,
)
from service.majority_panorama.period_verdict import build_period_verdict
from service.majority_panorama.reading_section import render_reading_section
from service.majority_panorama.seat_groups import has_party_detail, political_party_shade
from service.majority_panorama.seats_card import render_seats_card
from service.majority_panorama.state import PanoramaState

PANORAMA = period_panorama()


def _legislature(leg_id):
    return next(item for item in PANORAMA.legislatures if item.legislature_id == leg_id)


def test_default_selection_is_latest_and_unknown_falls_back():
    assert selected_legislature_index(PANORAMA, PanoramaState()) == 2
    assert selected_legislature_index(PANORAMA, PanoramaState(legislature_id="1999")) == 2
    assert selected_legislature_index(PANORAMA, PanoramaState(legislature_id="2019")) == 1


def test_section_has_navigation_cards_and_seats():
    html = render_period_section(PANORAMA, PanoramaState())
    assert 'id="periodo"' in html and "2023–2026" in html
    assert 'href="/panorama?leg=2019#periodo"' in html
    assert 'aria-disabled="true" aria-label="Próximo período"' in html
    assert "Maior bloco: Direita · 200 de 513" in html
    assert html.count("<circle") >= 513
    assert " style=" not in html and "<script" not in html


def test_first_period_disables_previous_and_shows_honest_no_data():
    html = render_period_section(PANORAMA, PanoramaState(legislature_id="2015"))
    assert 'aria-disabled="true" aria-label="Período anterior"' in html
    assert "Não há composição documentada da Câmara nem do Senado" in html
    assert "Sem dados" in html and "<circle" not in html
    assert "Câmara · sem dados" in html


def test_house_cards_majority_notes():
    camara = _legislature("2023").camara
    assert majority_note(camara) == "Sem maioria sozinho: faltam 57 para 257."
    cards = render_period_cards(PANORAMA, PanoramaState())
    assert "Presidência" in cards and "Caio Fictício" in cards
    assert "sem partido · Sem filiação · 2023–2026" in cards


def test_verdict_cases():
    assert build_period_verdict(PANORAMA, _legislature("2023")).startswith(
        "Presidente com categoria “sem filiação”."
    )
    verdict = build_period_verdict(PANORAMA, _legislature("2019"))
    assert verdict.startswith("Presidente de direita. O maior bloco é")
    assert main_president(PANORAMA, _legislature("2019")).short_name == "Bia"


def test_seats_card_by_party_has_chips_links_and_pressed_state():
    state = PanoramaState(highlight="PCA")
    html = render_seats_card(PANORAMA, state)
    assert 'href="/panorama#cadeiras" aria-current="true"><svg' in html
    assert "Cor por partido" in html and "PCA <strong>120</strong>" in html
    assert "Câmara · 513" in html and "Senado · 81" in html
    assert "#e6e2d9" in html  # dimmed seats


def test_seats_card_mode_link_and_percent():
    html = render_seats_card(PANORAMA, PanoramaState())
    assert 'href="/panorama?mode=bloco#cadeiras"' in html
    assert format_percent(200, 513) == "39,0%"
    assert "<strong>200</strong> · 39,0%" in html


def test_without_party_detail_mode_is_disabled_and_note_shown():
    state = PanoramaState(legislature_id="2019")
    html = render_seats_card(PANORAMA, state)
    assert 'ds-seats-modes__option--disabled" aria-disabled="true">Cor por partido' in html
    assert 'mode=bloco#cadeiras" aria-current="true">Cor por bloco' in html
    assert "ds-seat-legend__party" not in html
    house = _legislature("2019").camara
    assert not has_party_detail(house)
    senate = render_seats_card(PANORAMA, PanoramaState(house="senado"))
    assert senate.count("<circle") >= 81


def test_unknown_highlight_does_not_dim_everything():
    html = render_seats_card(PANORAMA, PanoramaState(highlight="XXX"))
    assert "#e6e2d9" not in html


def test_shade_runs_dark_to_light_inside_the_bloc():
    assert political_party_shade("left", 0, 3) == "oklch(0.360 0.14 25)"
    assert political_party_shade("center", 2, 3) == "oklch(0.780 0.12 75)"
    assert political_party_shade("right", 0, 1) == "oklch(0.500 0.14 250)"
    assert political_party_shade("undetermined", 0, 2) == "#bdb8ad"


def test_reading_section_is_truthful_and_escaped():
    html = render_reading_section(PANORAMA)
    assert html.count("<details") == 3
    assert 'href="/comparacao-de-classificacoes"' in html
    assert "Fonte fictícia observada em 29/10/2026." in html
    assert "Cobertura fictícia parcial." in html
    assert "E antes de 2015?" in html
    assert not re.search(r"ilustrativ|protótipo|exemplo", html)
