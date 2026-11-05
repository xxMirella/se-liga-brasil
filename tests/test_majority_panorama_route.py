"""The /panorama route accepts only the national view state and every link it renders is valid."""

import re
from html import unescape
from types import SimpleNamespace
from urllib.parse import parse_qsl, urlsplit

import pytest
from majority_panorama_fixtures import fictional_panorama

from application.public_portal import dispatch_portal_request
from service.majority_panorama.state import QUERY_PARAMETERS, parse_state


def application():
    return SimpleNamespace(fetch_majority_panorama=fictional_panorama)


def get(target):
    return dispatch_portal_request(application(), target)


@pytest.mark.parametrize("target", [
    "/panorama", "/panorama?leg=2019&house=senado&mode=bloco",
    "/panorama?leg=2019&house=senado&mode=bloco&hl=left&scen=conc&prop=A&view=bloco&bloc=left",
])
def test_valid_states_render_the_page(target):
    response = get(target)
    assert response.status == 200
    assert response.content_type.startswith("text/html")


@pytest.mark.parametrize("query", [
    "uf=SP", "year=2019", "level=federal", "territory=SP", "municipality_ibge=3550308",
    "senate_uf=SP", "view=political_orientation", "date=2026-01-01", "leg=2019&leg=2023",
    "house=x", "mode=y", "bloc=z", "leg=abc", "scen=x", "prop=C", "view=x",
])
def test_unknown_parameters_and_invalid_values_are_rejected(query):
    assert get("/panorama?" + query).status == 400


def test_page_has_no_inline_style_or_inline_script():
    for target in ("/panorama", "/panorama?leg=2019&house=senado&mode=bloco"):
        html = get(target).body.decode()
        assert "style=" not in html
        scripts = re.findall(r"<script[^>]*>", html)
        assert all(
            'type="application/ld+json"' in tag
            or 'src="/assets/panorama-enhance.js"' in tag
            or 'src="/assets/scroll-reveal.js"' in tag
            for tag in scripts
        )
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>(?!\s*</script>)", html.replace(
            '<script type="application/ld+json">', "<ld>"))
        assert not re.search(r"\son[a-z]+=", html)


def internal_links(html):
    hrefs = (unescape(match) for match in re.findall(r'href="([^"]*)"', html))
    return sorted({href for href in hrefs if href.startswith("/panorama")})


@pytest.mark.parametrize("target", [
    "/panorama", "/panorama?leg=2019", "/panorama?leg=2019&house=senado&mode=bloco",
    "/panorama?leg=2023&hl=left&view=bloco&bloc=right&scen=equi&prop=A",
])
def test_every_interaction_link_is_accepted_by_the_route(target):
    links = internal_links(get(target).body.decode())
    assert links, "the page must offer interactions as links"
    for link in links:
        parts = urlsplit(link)
        assert parts.path == "/panorama"
        parameters = dict(parse_qsl(parts.query, strict_parsing=bool(parts.query)))
        assert set(parameters) <= QUERY_PARAMETERS
        parse_state(parameters)
        assert get(parts.path + ("?" + parts.query if parts.query else "")).status == 200
