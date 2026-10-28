"""Timeline colours distinguish dated evidence from complete political composition."""

from service.political_dashboard.timeline import executive_cell, legislative_cell


def test_partial_chamber_cohort_never_looks_like_complete_historical_majority():
    cell = legislative_cell({
        "total": 61, "coverage": "observed_partial",
        "aggregation_basis": "verified_year_end_status_of_current_roster_cohort",
        "political_parties": [{"abbreviation": "PT", "count": 30}],
    })
    assert cell["state"] == "partial"
    assert cell["label"] == "PT"


def test_verified_current_roster_can_use_solid_colour():
    cell = legislative_cell({
        "total": 513, "coverage": "verified_current_roster",
        "political_parties": [{"abbreviation": "PL", "count": 90}],
    })
    assert cell["state"] == "known"


def test_dated_governor_observation_does_not_claim_continuous_affiliation():
    cell = executive_cell({
        "segments": [],
        "national_observations": [{
            "name": "Governadora", "political_party": "PSD",
            "political_party_status": "verified_official_dated_government_observation",
        }],
    })
    assert cell["state"] == "partial"
    assert cell["label"] == "PSD"


def test_equal_largest_groups_are_shown_as_tie():
    cell = legislative_cell({
        "total": 2, "coverage": "verified_current_roster",
        "political_parties": [
            {"abbreviation": "PL", "count": 1}, {"abbreviation": "PSD", "count": 1},
        ],
    })
    assert cell["state"] == "mixed"
    assert cell["label"] == "Empate: PL / PSD"


def test_annual_presidential_transition_is_not_hidden_by_year_end_party():
    cell = executive_cell({
        "current": {"political_party": "PL", "political_party_status": "verified_interval"},
        "segments": [{
            "political_party": "PL", "political_party_status": "verified_interval",
            "political_party_periods": [
                {"political_party": "Sem partido", "political_party_status": "verified_interval"},
                {"political_party": "PL", "political_party_status": "verified_interval"},
            ],
        }],
    })
    assert cell["state"] == "mixed"
    assert cell["label"] == "PL / Sem partido"


def test_equal_party_years_share_one_solid_centered_block_with_annual_links():
    import xml.etree.ElementTree as ElementTree

    from service.political_dashboard.timeline import render_timeline_row

    cells = [{"label": "PSDB", "color": "#aaa24d", "state": state}
             for state in ("partial", "known", "partial")]
    markup = render_timeline_row(cells, {"level": "state", "uf": "SP"},
                                 [2000, 2001, 2002], 100, 20, 50)
    root = ElementTree.fromstring("<svg>" + markup + "</svg>")
    blocks = root.findall("./rect")
    assert len(blocks) == 1
    assert blocks[0].attrib["fill"] == "#aaa24d"
    assert float(blocks[0].attrib["width"]) == 57
    label = root.find("./text")
    assert label.text == "PSDB"
    assert label.attrib["x"] == "130.00"
    assert label.attrib["y"] == "66"
    assert label.attrib["text-anchor"] == "middle"
    assert label.attrib["dominant-baseline"] == "middle"
    assert len(root.findall("./a")) == 3
    assert "cobertura parcial" in root.findall("./a")[0].attrib["aria-label"]
    assert "cobertura parcial" not in root.findall("./a")[1].attrib["aria-label"]
    assert "pattern" not in markup and "url(" not in markup
    assert 'stroke="white"' not in markup


def test_party_transition_has_gap_without_overflowing_short_labels():
    import xml.etree.ElementTree as ElementTree

    from service.political_dashboard.timeline import render_timeline_row

    cells = [{"label": label, "color": color, "state": "partial"}
             for label, color in [("PSDB", "#aaa24d"), ("Republicanos", "#a7b5a1")]]
    markup = render_timeline_row(cells, {"level": "municipal", "uf": "SP",
                                        "municipality_ibge": "3550308"},
                                 [2025, 2026], 100, 20, 50)
    root = ElementTree.fromstring("<svg>" + markup + "</svg>")
    first, second = root.findall("./rect")
    assert float(first.attrib["x"]) + float(first.attrib["width"]) < float(second.attrib["x"])
    assert root.find("./text") is None
    assert second.find("title").text == "Republicanos"
    assert all("municipality_ibge=3550308" in link.attrib["href"] for link in root.findall("./a"))


def test_missing_years_have_distinct_solid_fill_without_fabricated_links():
    from service.political_dashboard.timeline import render_timeline_row

    cells = [{"label": "Sem dados", "color": "#89978e", "state": "missing"},
             {"label": "Partido não informado", "color": "#89978e", "state": "unknown"}]
    markup = render_timeline_row(cells, {"level": "federal"}, [1888, 1889], 100, 20, 50)
    assert 'fill="#edf2ee"' in markup
    assert 'fill="#89978e"' in markup
    assert "year=1888" not in markup
    assert "year=1889" in markup


def test_visual_timeline_clips_before_1880_without_changing_stored_history():
    import re
    from copy import deepcopy

    from service.political_dashboard.contracts import HISTORY_START
    from service.political_dashboard.timeline import render_timeline_bands

    history = [{"year": year, "institutions": [{
        "institution_code": "senado", "total": 1, "coverage": "verified_current_roster",
        "political_parties": [{"abbreviation": "PL", "count": 1}],
    }]} for year in [1826, 1879, 1880, 1945, 2026]]
    data = {"history": history, "level": "federal", "as_of": "2026-10-26", "year": 1945}
    original = deepcopy(data)
    markup = render_timeline_bands(data)
    linked_years = [int(year) for year in re.findall(r'year=(\d+)', markup)]
    assert min(linked_years) == 1880
    assert {1880, 1945, 2026} <= set(linked_years)
    assert ">1880</text>" in markup
    assert ">1826</text>" not in markup and ">1879</text>" not in markup
    assert data == original
    assert HISTORY_START.year == 1826


def test_only_pre_1880_history_does_not_reintroduce_older_axis():
    from service.political_dashboard.timeline import render_timeline_bands

    markup = render_timeline_bands({"history": [{"year": 1826}, {"year": 1879}]})
    assert "<svg" not in markup
    assert "Histórico ainda não disponível" in markup


def test_selected_older_year_does_not_create_marker_outside_visible_timeline():
    from service.political_dashboard.timeline import render_timeline_bands

    markup = render_timeline_bands({"history": [{"year": 1880}, {"year": 2026}],
                                    "level": "federal", "as_of": "1826-05-06", "year": 1826})
    assert 'stroke="#b89432"' not in markup
    assert ">1826</text>" not in markup
