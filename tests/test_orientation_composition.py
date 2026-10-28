"""Cards aggregate every party in its dated category without inventing session attendance."""

from service.political_dashboard.orientation_composition import orientation_composition
from service.political_dashboard.page import render_composition
from service.political_dashboard.semicircle import render_people_semicircle


def composition():
    return {
        "total": 30,
        "coverage": "observed_partial",
        "snapshot_on": "2022-12-31",
        "political_parties": [
            {"abbreviation": "PT", "count": 10},
            {"abbreviation": "PL", "count": 8},
            {"abbreviation": "PP", "count": 8},
            {"abbreviation": "Não informado", "count": 3},
            {"abbreviation": "S/Partido", "count": 1},
        ],
    }


def test_categories_sum_all_parties_not_just_largest_party():
    original = composition()
    result = orientation_composition(original, 2022)
    counts = {g["orientation_category"]: g["count"] for g in result["political_parties"]}
    assert counts == {"left": 10, "right": 16, "undetermined": 3, "unaffiliated": 1}
    assert sum(counts.values()) == result["total"] == 30
    assert result["coverage"] == "observed_partial"
    assert result["snapshot_on"] == "2022-12-31"
    assert original["political_parties"][0]["abbreviation"] == "PT"


def test_2026_does_not_inherit_2022_and_preserves_explicit_unaffiliated():
    result = orientation_composition(composition(), 2026)
    assert {g["orientation_category"]: g["count"] for g in result["political_parties"]} == {
        "undetermined": 29,
        "unaffiliated": 1,
    }


def test_unreported_remainder_is_not_silently_lost():
    result = orientation_composition(
        {"total": 5, "political_parties": [{"abbreviation": "PT", "count": 2}]}, 2022
    )
    assert {g["orientation_category"]: g["count"] for g in result["political_parties"]} == {
        "left": 2,
        "undetermined": 3,
    }


def test_chamber_bars_and_seat_colors_use_category_counts_and_percentages():
    html = render_composition(
        composition(),
        "Câmara dos Deputados",
        "Brasil",
        "https://www.camara.leg.br",
        view="political_orientation",
        year=2022,
        reference_on="2022-12-31",
    )
    assert html.count("<circle ") == 30
    assert "<strong>16<small>53,3%</small></strong>" in html
    assert "Direita · 16 integrantes" in html
    assert "panorama-vertical-bars" in html
    assert "referência: 2022-12-31" in html and "Não é contagem de presença em sessão" in html
    assert html.count('fill="#c79f53"') == 17  # 16 seat circles + one category bar.


def test_senate_legend_uses_same_colors_and_percentages():
    html = render_composition(
        composition(),
        "Senado Federal",
        "Brasil",
        "https://www25.senado.leg.br",
        view="political_orientation",
        year=2022,
    )
    assert "Integrantes por abordagem política" in html
    assert "<strong>16<small>53,3%</small></strong>" in html
    assert html.count("<circle ") == 30
    assert 'fill="#8c9990"' in html and 'fill="#aeb9aa"' in html


def test_2026_limit_is_visible_and_party_default_remains_unchanged():
    kwargs = dict(
        title="Senado Federal", eyebrow="Brasil", official_link="https://www25.senado.leg.br"
    )
    html = render_composition(composition(), **kwargs, view="political_orientation", year=2026)
    assert "Não há classificação documentada para este ano" in html
    assert "<span>Sem classificação</span><strong>29" in html
    default = render_composition(composition(), **kwargs)
    assert "<span>PT</span><strong>10</strong>" in default
    assert "panorama-orientation-composition-note" not in default


def test_partial_roll_is_labeled_documented_and_uses_only_available_people():
    html = render_composition(
        {
            "total": None,
            "members": [{"person_id": "source:1", "name": "Pessoa", "political_party": "PT"}],
        },
        "Câmara dos Deputados",
        "Brasil",
        "https://www.camara.leg.br",
        view="political_orientation",
        year=2022,
    )
    assert html.count("<circle ") == 1
    assert "não representa cadeiras simultâneas" in html
    assert ">documentados</text>" in html


def test_empty_semicircle_stays_empty():
    assert "<circle " not in render_people_semicircle(
        orientation_composition({"total": 0, "political_parties": []}, 2022)
    )


def test_unreconciled_affiliation_is_not_promoted_from_a_display_label():
    data = {
        "total": 3,
        "political_parties": [
            {"abbreviation": "PT", "political_party_code": "unreconciled", "count": 2},
            {"abbreviation": "S/Partido", "political_party_code": "unknown", "count": 1},
        ],
    }
    assert {
        g["orientation_category"]: g["count"]
        for g in orientation_composition(data, 2022)["political_parties"]
    } == {
        "undetermined": 2,
        "unaffiliated": 1,
    }


def test_controversial_category_remains_separate_and_ties_are_named(monkeypatch):
    from service.political_dashboard import orientation_composition as module

    categories = {"A": "left", "B": "right", "C": "controversial", "D": "center"}
    monkeypatch.setattr(
        module,
        "classify_political_orientation",
        lambda label, year: {"category": categories[label]},
    )
    data = {
        "total": 8,
        "political_parties": [
            {"abbreviation": name, "count": count}
            for name, count in [("A", 3), ("B", 3), ("C", 1), ("D", 1)]
        ],
    }
    result = module.orientation_composition(data, 2022)
    assert {g["orientation_category"]: g["count"] for g in result["political_parties"]} == {
        "left": 3,
        "right": 3,
        "controversial": 1,
        "center": 1,
    }
    html = module.render_largest_orientation_group(result["political_parties"])
    assert "Maiores grupos classificados" in html and "Direita · Esquerda" in html
