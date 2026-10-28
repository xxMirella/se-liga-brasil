"""Legislative chart lengths preserve ratios without claiming a political majority."""

import re

from service.political_dashboard.composition_charts import render_party_bars


def chart(groups):
    return render_party_bars(
        {
            "total": sum(count for _, count in groups),
            "political_parties": [{"abbreviation": name, "count": count} for name, count in groups],
        }
    )


def test_largest_group_has_full_scale_and_half_as_many_has_half_width():
    html = chart([("MENOR", 32), ("MAIOR", 64)])
    assert re.findall(r'<rect width="([0-9.]+)"', html) == ["100.00", "50.00"]
    assert "style=" not in html
    assert html.index("<span>MAIOR</span>") < html.index("<span>MENOR</span>")
    assert "<strong>64<small>66,7%</small></strong>" in html
    assert "<strong>32<small>33,3%</small></strong>" in html
    assert "Maior bancada não significa maioria absoluta" in html


def test_unknown_affiliation_is_a_separate_category_not_the_largest_party():
    html = chart([("Filiação não informada", 50), ("ABC", 20), ("S/Partido", 1)])
    assert "Maior bancada documentada:</strong> ABC · 20 pessoas." in html
    assert "Maior bancada documentada:</strong> Filiação" not in html
    assert 'class="panorama-unaffiliated"' in html
    assert re.findall(r'<rect width="([0-9.]+)"', html) == ["100.00", "40.00", "2.00"]


def test_empty_and_zero_counts_do_not_divide_by_zero():
    assert chart([]) == ""
    assert chart([("ABC", 0)]) == ""
    assert (
        render_party_bars(
            {"total": None, "political_parties": [{"abbreviation": "ABC", "count": 3}]}
        )
        == ""
    )


def test_tied_largest_parties_are_both_named_without_arbitrary_winner():
    html = chart([("DEF", 3), ("ABC", 3)])
    assert "Maiores bancadas documentadas:</strong> ABC · DEF" in html
    assert re.findall(r'<rect width="([0-9.]+)"', html) == ["100.00", "100.00"]


def test_unaffiliated_only_cannot_be_called_a_party_majority():
    html = chart([("S/Partido", 2)])
    assert "Maior bancada documentada" not in html
    assert "Maioria absoluta" not in html


def test_source_labels_are_escaped_in_bars_and_largest_group():
    html = chart([("<script>alert(1)</script>", 1)])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


def test_chart_uses_svg_widths_compatible_with_the_portals_strict_style_policy():
    from datetime import date
    from types import SimpleNamespace
    from wsgiref.util import setup_testing_defaults

    from application.vercel import PublicPortalWSGI
    from service.political_dashboard.aggregation import build_dashboard
    from service.political_dashboard.contracts import DashboardQuery

    today = date(2026, 10, 23)
    payload = build_dashboard([], DashboardQuery("SP", today))
    payload["federal_chamber"].update(
        total=96,
        political_parties=[
            {"abbreviation": "ABC", "count": 64},
            {"abbreviation": "DEF", "count": 32},
        ],
    )
    portal = SimpleNamespace(fetch_political_dashboard=lambda _: payload, today=lambda: today)
    application = PublicPortalWSGI(portal)
    environ, captured = {}, {}
    setup_testing_defaults(environ)
    environ["PATH_INFO"] = "/panorama"
    body = b"".join(application(environ, lambda status, headers: captured.update(headers)))
    assert "style-src 'self'" in captured["Content-Security-Policy"]
    assert b'height="100.00"' in body and b'height="50.00"' in body
    assert b"panorama-vertical-bars" in body
    assert b"style=" not in body


def test_compact_legend_preserves_sorted_counts_and_stable_colors_without_bars():
    html = render_party_bars(
        {
            "total": 3,
            "political_parties": [
                {"abbreviation": "PL", "count": 1},
                {"abbreviation": "PSD", "count": 2},
            ],
        },
        compact=True,
    )
    assert 'class="panorama-party-legend"' in html
    assert html.index("<span>PSD</span>") < html.index("<span>PL</span>")
    assert "<strong>2</strong>" in html and "<strong>1</strong>" in html
    assert 'fill="#236049"' in html and 'fill="#56866c"' in html
    assert "panorama-track" not in html and "style=" not in html


def test_chamber_vertical_bars_keep_counts_ratios_percentages_and_all_parties():
    html = render_party_bars(
        {
            "total": 100,
            "political_parties": [
                {"abbreviation": "PL", "count": 60},
                {"abbreviation": "PT", "count": 30},
                {"abbreviation": "Não informado", "count": 10},
            ],
        },
        vertical=True,
    )
    assert re.findall(r'height="([0-9.]+)" rx=', html) == ["100.00", "50.00", "16.67"]
    assert "<strong>60<small>60,0%</small></strong>" in html
    assert 'panorama-vertical-label">Não informado' in html
    assert 'class="panorama-unaffiliated"' in html
    assert "Altura proporcional" in html
    assert "style=" not in html


def test_chamber_and_senate_use_same_diagram_without_changing_assembly_bars():
    from service.political_dashboard.page import render_composition

    composition = {"total": 513, "political_parties": [{"abbreviation": "PL", "count": 513}]}
    chamber = render_composition(
        composition, "Câmara dos Deputados", "Federal", "https://www.camara.leg.br"
    )
    assert chamber.count("<circle ") == 513
    assert "panorama-panel-chamber" in chamber and "panorama-vertical-bars" in chamber
    assembly = render_composition(
        composition, "Assembleia Legislativa", "Estadual", "https://www.al.sp.gov.br"
    )
    assert "<circle " not in assembly and 'class="panorama-bars"' in assembly


def test_partial_chamber_roll_remains_documented_people_not_simultaneous_seats():
    from service.political_dashboard.page import render_composition

    composition = {
        "total": None,
        "members": [{"name": "Pessoa", "person_id": "source:1"}],
        "political_parties": [],
    }
    html = render_composition(
        composition, "Câmara dos Deputados", "Federal", "https://www.camara.leg.br"
    )
    assert html.count("<circle ") == 1
    assert "não representa cadeiras simultâneas" in html
    assert ">documentados</text>" in html
