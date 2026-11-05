from majority_panorama_fixtures import fictional_panorama

from service.majority_panorama.contracts import MajorityPanorama
from service.majority_panorama.state import PanoramaState
from service.majority_panorama.timeline_blocs import bloc_summary_text
from service.majority_panorama.timeline_section import render_timeline_section
from web_components import design_system_stylesheet
from web_components.column_chart import percent_height_classes


def test_period_view_lists_newest_first_and_marks_missing_data():
    html = render_timeline_section(fictional_panorama(), PanoramaState())
    assert "Quem governou e quem teve maioria, de 2015 a hoje" in html
    assert html.index("2023–2026") < html.index("2019–2022") < html.index("2015–2018")
    assert html.count("sem dados") == 2  # tag + line of the legislature without data
    assert html.count("dados do Se Liga") == 2
    assert 'href="/panorama?leg=2019#periodo"' in html
    assert html.count('aria-current="true"') == 2  # view toggle + selected legislature
    assert "<strong>Gama</strong> PXX · Esquerda" in html
    assert "metade das cadeiras" in html
    assert 'class="ds-bloc--unaffiliated"' in html  # neutral group present in the data


def test_period_bars_have_percentages_and_half_marker():
    html = render_timeline_section(fictional_panorama(), PanoramaState())
    assert "ds-stacked-bar--half" in html
    assert '<col width="60.00%">' in html and ">60%</td>" in html
    assert "Câmara 2023–2026: Esquerda 60, Centro 10, Direita 20, Extrema direita 10 de 100" in html


def test_selecting_a_legislature_uses_the_state():
    html = render_timeline_section(fictional_panorama(), PanoramaState(legislature_id="2019"))
    rows = html.split('<li><a class="ds-timeline-row"')[1:]
    current = [row for row in rows if "aria-current" in row.split("</a>")[0]]
    assert len(current) == 1 and "2019–2022" in current[0]


def test_bloc_view_has_picker_summary_charts_and_chips():
    state = PanoramaState(timeline_view="bloco", timeline_bloc="left")
    html = render_timeline_section(fictional_panorama(), state)
    assert "Esquerda: maior presença na Câmara em 2023–2026 (60%)." in html
    assert "Já teve maioria sozinha em pelo menos uma Casa." in html
    assert "Esquerda no Senado" in html and "Esquerda na Câmara dos Deputados" in html
    assert "ds-pct-tens-6 ds-pct-ones-0" in html
    assert "Presidentes · em destaque os de esquerda" in html
    assert html.count("ds-president-chip--highlight") == 1
    assert 'aria-label="2015–2018: sem dados"' in html
    assert 'href="/panorama?view=bloco&amp;bloc=center#linha-do-tempo"' in html or (
        'bloc=center#linha-do-tempo' in html
    )
    assert "metade" in html and " style=" not in html and "<script" not in html


def test_bloc_summary_when_bloc_never_has_majority_or_data():
    panorama = fictional_panorama()
    assert "Nunca passou da metade sozinha" in bloc_summary_text(panorama, "far_right")
    empty = MajorityPanorama((), (), panorama.generated_on)
    assert "ainda não há dados" in bloc_summary_text(empty, "left")
    assert "Quem governou" in render_timeline_section(empty, PanoramaState())


def test_percent_height_classes_split_tens_and_ones():
    assert percent_height_classes(37.4) == "ds-pct-tens-3 ds-pct-ones-7"
    assert percent_height_classes(100) == "ds-pct-tens-10 ds-pct-ones-0"
    assert percent_height_classes(-3) == "ds-pct-tens-0 ds-pct-ones-0"


def test_stylesheet_includes_timeline_parts_and_no_external_resources():
    stylesheet = design_system_stylesheet()
    assert ".ds-column-chart" in stylesheet and ".ds-timeline-row" in stylesheet
    assert "ds-pct-tens-10" in stylesheet
    assert "http" not in stylesheet.split(".ds-bloc-scope--left", 1)[1]


def test_bloc_chart_marks_unclassified_houses_instead_of_showing_zero_percent():
    from service.majority_panorama.timeline_blocs import is_classified
    from tests.majority_panorama_fixtures import house

    assert is_classified(house("camara", 10, left=4, right=6))
    assert not is_classified(house("camara", 10, undetermined=10))
    assert not is_classified(None)
