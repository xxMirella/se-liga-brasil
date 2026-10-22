"""Institutional content stays public, traceable and independent of private data."""

import gzip
import json
from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest

from application.public_cache import prepare_public_response
from application.public_portal import dispatch_portal_request
from service.project_information.page import render_project_information
from service.static_publication.build import build_civic_site


class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


@pytest.mark.parametrize("route", ["/", "/sobre", "/sobre/"])
def test_institutional_route_needs_no_database_or_application(route):
    response = dispatch_portal_request(object(), route)
    assert response.status == 200
    assert response.content_type == "text/html; charset=utf-8"
    document = response.body.decode()
    assert "Dados públicos para entender a política" in document
    assert 'href="/sobre"' in document
    assert "19 de outubro de 2026" in document
    assert "cobertura ainda é parcial" in document


@pytest.mark.parametrize("route", ["/", "/sobre", "/sobre/"])
@pytest.mark.parametrize("query", ["?q=a", "?token=private", "?q=a&q=b"])
def test_institutional_route_rejects_unexpected_parameters(route, query):
    response = dispatch_portal_request(object(), route + query)
    assert response.status == 400
    assert response.content_type.startswith("text/html")
    assert "private" not in response.body.decode()


def test_legal_content_preserves_reuse_and_privacy_limits():
    document = render_project_information()
    for explanation in (
        "não significa parceria", "Filiação partidária é dado sensível",
        "legítimo interesse não basta", "Não foi confirmada uma licença geral",
        "não cria uma exceção automática", "um aviso de privacidade completo",
        "Falta de voto registrado não prova ausência", "não é uma medida do patrimônio atual",
    ):
        assert explanation in document
    assert "<script" not in document
    assert 'aria-labelledby="sources"' in document


def test_external_links_use_verified_official_hosts_and_safe_targets():
    parser = LinkCollector()
    parser.feed(render_project_information())
    external = [link for link in parser.links if urlsplit(link["href"]).scheme]
    assert len(external) >= 12
    expected_hosts = {
        "dadosabertos.tse.jus.br", "dadosabertos.camara.leg.br",
        "www12.senado.leg.br", "www.al.sp.gov.br", "transparencia.alerj.rj.gov.br",
        "www.saopaulo.sp.leg.br", "www.planalto.gov.br",
        "www.gov.br",
    }
    assert {urlsplit(link["href"]).hostname for link in external} == expected_hosts
    for link in external:
        assert urlsplit(link["href"]).scheme == "https"
        assert link["target"] == "_blank"
        assert {"noopener", "noreferrer"} <= set(link["rel"].split())


def test_about_explains_independence_without_claiming_immunity_or_certification():
    document = render_project_information()
    assert "não\nrecomenda voto" in document
    assert "não são um julgamento de caráter" in document
    assert "Dados de visitantes também" in document
    assert "solicitações de exercício desses direitos são gratuitas" in document
    assert "não\nafasta a responsabilidade do projeto" in document
    assert "não representam certificação" in document
    assert "Nenhum texto desta página afasta responsabilidades" in document
    assert 'https://www.gov.br/anpd/' in document


def test_institutional_page_static_export_is_complete_and_fingerprinted(tmp_path):
    result = build_civic_site(tmp_path, backend_origin="https://api.example.org")
    path = tmp_path / "sobre/index.html"
    document = path.read_text()
    assert (tmp_path / "index.html").read_bytes() == path.read_bytes()
    assert result["files"] == 10
    assert 'href="/sobre/"' in document
    assert 'href="/como-funciona/"' in document
    assert 'action="https://api.example.org/pessoas"' in document
    assert gzip.decompress(path.with_name("index.html.gz").read_bytes()) == path.read_bytes()
    for stylesheet in tmp_path.glob("assets/*.css"):
        assert f'/assets/{stylesheet.name}' in document
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["files"]["sobre/index.html"]["bytes"] == len(path.read_bytes())


@pytest.mark.parametrize("route", ["/", "/sobre", "/sobre/"])
def test_institutional_cache_revalidates_and_never_caches_errors(route):
    body = render_project_information().encode()
    status, encoded, headers = prepare_public_response(
        route, 200, body, {"Accept-Encoding": "gzip"},
    )
    assert status == 200
    assert gzip.decompress(encoded) == body
    assert "public" in headers["Cache-Control"]
    status, empty, _ = prepare_public_response(
        route, 200, body, {"If-None-Match": headers["ETag"], "Accept-Encoding": "gzip"},
    )
    assert (status, empty) == (304, b"")
    assert prepare_public_response(route, 400, body, {})[2] == {"Cache-Control": "no-store"}


@pytest.mark.parametrize("active", ["about", "people", "guide"])
def test_header_exposes_about_and_only_selects_active_section(active):
    from service.public_profile_web.layout import render_layout

    document = render_layout("Página", "Conteúdo", active_section=active)
    header = document.split("</header>", 1)[0]
    parser = LinkCollector()
    parser.feed(header)
    selected = [link for link in parser.links if link.get("aria-current") == "page"]
    assert len(selected) == 1
    assert selected[0]["href"] == {
        "about": "/sobre", "people": "/pessoas", "guide": "/como-funciona",
    }[active]
    assert 'class="brand" href="/"' in header
    assert 'href="/sobre"' in header
    assert 'href="/sobre"' not in document.split("<footer>", 1)[1]


def test_search_parameters_still_reach_people_search():
    from types import SimpleNamespace

    parameters = []
    app = SimpleNamespace(fetch_people=lambda values: parameters.append(values) or {"items": []})
    response = dispatch_portal_request(app, "/api/people?q=Pessoa")
    assert response.status == 200
    assert parameters == [{"q": "Pessoa"}]
    response = dispatch_portal_request(app, "/pessoas?q=Pessoa")
    assert response.status == 200
    assert parameters == [{"q": "Pessoa"}]
    assert 'data-viewport-page' in response.body.decode()
    assert 'value="Pessoa"' in response.body.decode()
    response = dispatch_portal_request(app, "/pessoas?q=Pessoa&limit=3")
    assert response.status == 200
    assert parameters == [{"q": "Pessoa"}, {"q": "Pessoa", "limit": "3"}]


@pytest.mark.parametrize("route", ["/", "/sobre", "/sobre/"])
def test_institutional_header_selects_about_menu(route):
    document = dispatch_portal_request(object(), route).body.decode()
    parser = LinkCollector()
    parser.feed(document.split("</header>", 1)[0])
    selected = [link for link in parser.links if link.get("aria-current") == "page"]
    assert selected == [{"href": "/sobre", "class": "selected", "aria-current": "page"}]


def test_current_menu_has_semantic_visible_styles_in_static_export(tmp_path):
    from service.public_profile_web.layout import public_stylesheet

    stylesheet = public_stylesheet()
    assert '.profile-tabs a[aria-current="page"]' in stylesheet
    assert "border-bottom:3px solid var(--green)" in stylesheet
    assert 'background:var(--accent)' in stylesheet
    build_civic_site(tmp_path)
    for relative in ("index.html", "sobre/index.html"):
        parser = LinkCollector()
        parser.feed((tmp_path / relative).read_text().split("</header>", 1)[0])
        selected = [link for link in parser.links if link.get("aria-current") == "page"]
        assert selected == [{"href": "/sobre/", "class": "selected", "aria-current": "page"}]
