"""Historical rolls keep the current diagram while preserving their different evidential meaning."""

import re
from xml.etree import ElementTree

from service.political_dashboard.composition_charts import render_party_bars
from service.political_dashboard.composition_presentation import composition_presentation
from service.political_dashboard.page import render_composition
from service.political_dashboard.political_palette import UNKNOWN_COLOR, political_party_color
from service.political_dashboard.semicircle import render_people_semicircle


def historical_roll(count):
    return {
        "total": None,
        "members": [],
        "political_parties": [],
        "historical_roster": [
            dict(
                source_person_id=str(index),
                name=f"Pessoa{index}",
                legislature=24,
                period_start="1897-01-01",
                period_end="1899-12-31",
                uf="SP",
                official_url="https://www25.senado.leg.br/source",
            )
            for index in range(count)
        ],
    }


def test_historical_190_integrants_get_diagram_and_names_without_claiming_81_seats():
    original = historical_roll(190)
    html = render_composition(original, "Senado Federal", "Brasil", "https://www.senado.leg.br")
    assert html.count("<circle ") == 190
    assert "<strong>190</strong>" in html
    assert "integrantes documentados no período" in html
    assert "Ver integrantes documentados" in html
    assert "Pessoa189" in html
    assert "não representa cadeiras simultâneas" in html
    assert "pessoas em exercício na composição observada" not in html
    assert original["total"] is None
    assert original["members"] == []


def test_people_repeated_across_legislatures_are_counted_once_without_current_affiliation():
    original = historical_roll(1)
    repeated = dict(original["historical_roster"][0], legislature=25, political_party="PL")
    original["historical_roster"].append(repeated)
    view = composition_presentation(original)
    assert view["total"] == 1
    assert view["members"][0]["period_description"] == "Legislaturas: 24, 25"
    assert view["members"][0]["political_party"] == "Filiação histórica não verificada"
    assert "PL" not in str(view["political_parties"])


def test_exact_snapshot_remains_snapshot_even_with_extra_legislature_records():
    original = historical_roll(190)
    original.update(
        total=81,
        members=[{"name": "Pessoa", "political_party": "PSD", "uf": "SP"}],
        political_parties=[{"abbreviation": "PSD", "count": 81}],
    )
    view = composition_presentation(original)
    assert view["total"] == 81
    assert view["presentation_basis"] == "snapshot"
    assert "em exercício" in view["count_label"]


def test_513_member_chamber_and_190_person_roll_fit_same_svg_bounds():
    for total in (1, 3, 81, 190, 513):
        view = {"total": total, "political_parties": [{"abbreviation": "PSD", "count": total}]}
        svg = ElementTree.fromstring(render_people_semicircle(view))
        circles = svg.findall("circle")
        assert len(circles) == total
        assert all(0 <= float(circle.attrib["cx"]) <= 360 for circle in circles)
        assert all(0 <= float(circle.attrib["cy"]) <= 190 for circle in circles)
        assert {circle.attrib["fill"] for circle in circles} == {"#236049"}


def test_empty_recortes_keep_chart_shape_without_invented_seat_markers():
    svg = render_people_semicircle({"total": 0, "political_parties": []})
    assert "panorama-semicircle-empty" in svg
    assert "<path " in svg and "<circle " not in svg
    assert "Composição ainda não documentada" in svg


def test_party_palette_is_fixed_by_name_not_rank_and_matches_mock():
    assert political_party_color("PSD") == "#236049"
    assert political_party_color("PL") == "#56866c"
    assert political_party_color("MDB") == political_party_color("PMDB") == "#aaa24d"
    assert political_party_color("União") == political_party_color("UNIÃO BRASIL") == "#678798"
    assert political_party_color("Filiação histórica não verificada") == UNKNOWN_COLOR
    assert political_party_color("PRP") == political_party_color("PRP")
    html = render_party_bars(
        {
            "total": 5,
            "political_parties": [
                {"abbreviation": "PL", "count": 2},
                {"abbreviation": "PSD", "count": 3},
            ],
        }
    )
    assert re.findall(r'fill="(#[0-9a-f]+)"', html) == ["#236049", "#56866c"]
    assert "style=" not in html


def test_historical_and_current_senate_share_four_rows_without_fixed_81_markers():
    from service.political_dashboard.semicircle import indicator_positions

    for total in (70, 81, 190):
        positions, _ = indicator_positions(total)
        radii = {round(((x - 180) ** 2 + (y - 174) ** 2) ** 0.5) for _, x, y in positions}
        assert len(radii) == 4
        assert len(positions) == total


def test_partial_current_cohort_history_keeps_its_limit_visible_in_coverage_notes():
    html = render_composition({
        "total": 61, "members": [], "political_parties": [{"abbreviation": "PT", "count": 61}],
        "coverage": "observed_partial",
        "aggregation_basis": "verified_year_end_status_of_current_roster_cohort",
    }, "Câmara dos Deputados", "Brasil", "https://www.camara.leg.br")
    assert "faltam antigos parlamentares" in html
    assert "Exercício em 31/12" in html
    assert "panorama-panel-chamber" in html
    assert "panorama-vertical-bars" in html
    assert html.count('<circle ') == 61
    assert 'href="https://www.camara.leg.br" target="_blank"' in html


def test_composition_source_links_to_archived_official_roster_when_available():
    url = "https://www.al.sp.gov.br/repositorio/deputados.xml"
    html = render_composition({
        "total": 94, "members": [], "political_parties": [],
        "evidence": [{"url": url}],
    }, "Assembleia de São Paulo", "Estado", "https://www.al.sp.gov.br")
    assert f'href="{url}" target="_blank"' in html


def test_state_party_observation_is_visible_without_claiming_continuous_affiliation():
    from service.political_dashboard.page import render_executive

    html = render_executive({
        "segments": [{"name": "Governadora", "political_party": "Não verificado"}],
        "national_observations": [{
            "name": "Governadora", "political_party": "PSD",
            "political_party_status": "verified_official_dated_government_observation",
            "source_observed_on": "2026-10-04",
            "official_url": "https://www.gov.br/noticia",
        }],
    }, "Governo", "Estado")
    primary_card = html.split("<details>")[0]
    assert 'class="panorama-executive-party">PSD</strong>' in primary_card
    assert "Observação oficial: 2026-10-04" in primary_card
    assert "não comprova filiação durante todo o mandato" in primary_card
