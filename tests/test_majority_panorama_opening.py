import re

import pytest
from majority_panorama_fixtures import fictional_panorama

from service.majority_panorama.explainer import (
    VOTES_TO_PASS,
    build_chocolate_explanation,
    votes_in_favor,
)
from service.majority_panorama.opening_section import render_opening_section
from service.majority_panorama.state import PanoramaState


def test_default_example_is_rejected_with_40_of_100():
    result = build_chocolate_explanation("prop", "B")
    assert VOTES_TO_PASS == 51
    assert result.votes_in_favor == 40 and not result.approved
    assert result.vote_title == "40 a favor, 60 contra: rejeitada."
    assert "convencer 11 pessoas que gostam de chocolate" in result.vote_text
    assert result.vote_text.startswith("Precisa de 51, mais da metade.")
    assert result.seats_text == "Cada grupo tem cadeiras na mesma proporção que tem na população."
    assert result.unrepresented_text == ""
    assert len(result.seat_group_keys) == 100


def test_proposal_a_with_mirrored_seats_passes_at_exactly_60_and_blames_nobody():
    result = build_chocolate_explanation("prop", "A")
    assert result.votes_in_favor == 60 and result.approved
    assert result.vote_text.endswith("Os alérgicos votaram contra e perderam, mas com cadeiras "
                                     "podem propor ajustes e cobrar alternativas.")


def test_concentrated_majority_leaves_allergic_people_without_seat():
    result = build_chocolate_explanation("conc", "B")
    assert result.votes_in_favor == 15 and not result.approved
    assert result.seats_text == "Gostam de chocolate: 60% da população, 85% das cadeiras."
    assert result.unrepresented_text == (
        "As 15 pessoas que têm alergia não têm nenhuma cadeira. "
        "Ninguém leva a realidade delas para a votação."
    )
    approved_a = build_chocolate_explanation("conc", "A")
    assert approved_a.votes_in_favor == 85 and approved_a.approved
    assert approved_a.vote_text == "Precisa de 51, mais da metade."  # no allergic seats: no extra


def test_balanced_scenario_lets_small_groups_win_by_51():
    result = build_chocolate_explanation("equi", "B")
    assert result.votes_in_favor == 55 and result.approved
    assert result.vote_text.endswith("Grupos menores, somados, formaram maioria.")
    assert build_chocolate_explanation("equi", "A").vote_text.endswith(
        "precisaria do apoio de 6 representantes dos outros grupos."
    )


@pytest.mark.parametrize("scenario", ["prop", "conc", "equi"])
def test_every_scenario_has_100_seats(scenario):
    assert sum(build_chocolate_explanation(scenario, "A").seats_by_group) == 100
    assert votes_in_favor((60, 15, 25), "A") + votes_in_favor((60, 15, 25), "B") == 100


def test_opening_section_renders_texts_links_and_no_inline_style():
    html = render_opening_section(fictional_panorama(), PanoramaState(scenario="conc"))
    assert "<h1" in html and "Quem tem a maioria?" in html
    assert "desde 2015" in html
    assert "Entenda a regra · quem está representado?" in html
    assert html.count('<span class="ds-bloc--chocolate-likes">') == 85
    assert "15 a favor, 85 contra: rejeitada." in html
    assert "Sem representação." in html
    assert 'href="/panorama?scen=equi#entenda-a-regra"' in html
    assert html.count('aria-current="true"') == 2
    assert " style=" not in html and "<script" not in html
    legend = html.split("ds-legend", 1)[1].split("ds-rule-card", 1)[0]
    for label in ("Esquerda", "Centro", "Direita", "Extrema direita", "Sem filiação"):
        assert label in legend
    assert "Sem classificação" not in legend and "controversa" not in legend
    assert re.search(r'<col width="60.00%"><col width="15.00%"><col width="25.00%">', html)
