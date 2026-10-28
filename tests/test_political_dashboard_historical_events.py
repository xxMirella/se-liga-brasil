"""Historical context must not manufacture political observations or invalid year links."""

import re
import xml.etree.ElementTree as ElementTree

from service.political_dashboard.historical_events import (
    HISTORICAL_EVENTS,
    event_coordinates,
    render_historical_event,
    render_historical_event_sources,
    render_historical_events,
)
from service.political_dashboard.timeline import render_timeline_bands


def test_historical_context_has_point_and_period_dates_with_country():
    assert HISTORICAL_EVENTS[0].start_year == HISTORICAL_EVENTS[0].end_year == 1888
    assert HISTORICAL_EVENTS[2].geography == "Alemanha"
    assert (HISTORICAL_EVENTS[2].start_year, HISTORICAL_EVENTS[2].end_year) == (1933, 1945)
    assert HISTORICAL_EVENTS[3].date_description.startswith("1964–1985")
    assert "anual" in HISTORICAL_EVENTS[3].date_description


def test_event_position_clips_to_visible_years_without_changing_dates():
    event = HISTORICAL_EVENTS[2]
    assert event_coordinates(event, 1940, 1950, 155, 10) == (160, 210)
    assert event_coordinates(event, 1950, 1960, 155, 10) is None
    assert (event.start_year, event.end_year) == (1933, 1945)


def test_event_labels_appear_above_periods_and_exact_dates_are_accessible():
    markup = render_historical_events(1888, 2026, 155, 7)
    assert 'y="51"' in markup
    assert 'V73' in markup
    assert "30 de janeiro de 1933 a 8 de maio de 1945" in markup
    assert 'marker-start' not in markup
    assert 'marker-end' not in markup
    assert "Alemanha" in markup


def test_sources_open_new_tabs_without_navigation_to_an_institutional_year():
    markup = render_historical_event_sources()
    assert markup.count('target="_blank" rel="noopener noreferrer"') == 5
    assert "https://encyclopedia.ushmm.org/content/en/article/third-reich" in markup
    assert "não representam datas exatas nem filiação partidária" in markup
    assert "year=" not in markup


def test_visual_axis_starts_in_1880_and_keeps_1888_historical_marker():
    data = {"level": "federal", "year": 2026, "as_of": "2026-10-23",
            "history": [{"year": 1889, "senate_observations": 1}, {"year": 2026}]}
    markup = render_timeline_bands(data)
    svg = re.search(r"<svg.*?</svg>", markup, re.S).group()
    ElementTree.fromstring(svg)
    assert ">1880</text>" in markup
    assert "year=1888" not in markup
    assert "year=1889" in markup
    assert '<marker' not in markup
    assert 'historical-arrow' not in markup
    assert "Abolição legal da escravidão" in markup
    assert "Ditadura militar" in markup
    assert "2026</text>" in markup
    assert data["history"][0]["year"] == 1889


def test_period_has_horizontal_line_and_exact_vertical_terminations():
    markup = render_historical_event(HISTORICAL_EVENTS[2], (200, 280), 100)
    assert 'd="M200.00 112H280.00M200.00 105V119M280.00 105V119"' in markup
    assert '<marker' not in markup


def test_presidential_origin_is_point_with_explicit_parliamentary_exception():
    event = HISTORICAL_EVENTS[1]
    assert event.start_year == event.end_year == 1889
    assert "15 de novembro de 1889" in event.date_description
    assert "1961–1963" in event.date_description
    assert "d0001.htm" in event.source_url
    markup = render_historical_event(event, (160, 160), 100)
    assert 'd="M160.00 105V119"' in markup
    sources = render_historical_event_sources()
    assert "sem afirmar continuidade" in sources
    assert "referendo-de-1963" in sources
