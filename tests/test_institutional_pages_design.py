"""The institutional and educational pages use the shared design system and the strict CSP."""

import re

import pytest

from service.civic_education.page import civic_stylesheet, render_civic_education
from service.data_sources.page import render_data_sources
from service.party_orientation_comparison.page import (
    comparison_stylesheet,
    render_party_comparison_page,
)
from service.project_information.page import render_project_information

PAGES = {
    "about": render_project_information,
    "sources": render_data_sources,
    "offices": lambda: render_civic_education("todos"),
    "comparison": render_party_comparison_page,
}
LEGACY_VARIABLES = re.compile(r"var\(--(green|border|ink|muted|accent|page|paper)\)")
HARDCODED_COLOR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\boklch\(")


@pytest.mark.parametrize("name", PAGES)
def test_page_has_hero_and_no_inline_style(name):
    document = PAGES[name]()
    assert document.count("<h1") == 1 and 'class="ds-container ds-hero"' in document
    assert "style=" not in document
    inline_scripts = re.search(r"<script(?![^>]*\bsrc=\"/assets/)", document)
    assert not inline_scripts


@pytest.mark.parametrize("name", ["about", "sources", "offices"])
def test_disclosures_use_the_shared_component(name):
    main = PAGES[name]().split("<main", 1)[1].split("</main>", 1)[0]
    assert main.count("<details") == main.count('<details class="ds-disclosure')


def test_page_stylesheets_use_only_shared_tokens():
    for stylesheet in (civic_stylesheet(), comparison_stylesheet()):
        assert not LEGACY_VARIABLES.search(stylesheet)
        assert not HARDCODED_COLOR.search(stylesheet)
        assert "system-ui" not in stylesheet


def test_education_anchors_are_preserved():
    document = render_civic_education("todos")
    for anchor in ("mapa", "cargos", "leis", "tipos", "pratique"):
        assert f'id="{anchor}"' in document


def test_sources_anchors_are_preserved():
    document = render_data_sources()
    for anchor in ("presidencia", "senado-2026", "senado-1992-1994"):
        assert f'id="{anchor}"' in document


