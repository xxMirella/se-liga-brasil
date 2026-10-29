"""The data sources page explains provenance without database access."""

import json
from html import escape
from html.parser import HTMLParser
from pathlib import Path

import pytest

from application.public_portal import dispatch_portal_request
from service.data_sources.page import render_data_sources, render_presidency_sources

EVIDENCE_PATH = (Path(__file__).parents[1] / "src" / "service" / "political_dashboard"
                 / "executive_orientation_evidence.json")
RECORDS = json.loads(EVIDENCE_PATH.read_text())["records"]


class SourcesMarkup(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.ids, self.links = set(), []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "a":
            self.links.append(values)


def record_sources(record):
    return [source for source in [record, *record.get("supporting_sources", [])]
            if source.get("source_title")]


@pytest.mark.parametrize("path", ["/fontes-dos-dados", "/fontes-dos-dados/"])
def test_route_serves_html_without_database(path):
    response = dispatch_portal_request(object(), path)
    assert response.status == 200
    assert response.content_type.startswith("text/html")
    assert "Fontes dos dados" in response.body.decode()


@pytest.mark.parametrize("query", ["unknown=x", "esfera=federal", "a=1&a=2"])
def test_unexpected_query_parameters_are_rejected(query):
    response = dispatch_portal_request(object(), "/fontes-dos-dados?" + query)
    assert response.status == 400


def test_rejected_query_renders_html_error_like_other_pages():
    response = dispatch_portal_request(object(), "/fontes-dos-dados?unknown=x")
    assert response.content_type.startswith("text/html")


def test_navigation_marks_only_sources_as_current():
    document = SourcesMarkup(render_data_sources())
    current = [link for link in document.links if link.get("aria-current") == "page"]
    assert [(link["href"], link.get("class")) for link in current] == [
        ("/fontes-dos-dados", "selected")
    ]


def test_anchors_for_presidency_and_senate_exist():
    document = SourcesMarkup(render_data_sources())
    assert {"presidencia", "senado-2026"} <= document.ids


def test_every_evidence_record_is_listed_with_its_external_sources():
    markup = render_presidency_sources()
    links = {link["href"]: link for link in SourcesMarkup(markup).links}
    for record in RECORDS:
        label = record.get("executive_name") or record.get("regime_name") or "Governo ou regime"
        assert escape(label) in markup
        for source in record_sources(record):
            assert escape(source["source_title"]) in markup, source["source_title"]
            assert escape(source["source_url"]) in links, source["source_url"]


def test_external_links_open_new_tab_with_isolated_opener():
    document = SourcesMarkup(render_data_sources())
    external = [link for link in document.links if link["href"].startswith("https://")]
    assert external
    for link in external:
        assert link.get("target") == "_blank", link["href"]
        assert {"noopener", "noreferrer"} <= set(link.get("rel", "").split()), link["href"]


def test_text_from_evidence_file_is_html_escaped(monkeypatch):
    hostile = {"records": [{
        "executive_name": "<script>alert(1)</script>",
        "classification_basis": "<b>base</b> & \"aspas\"",
        "source_title": "<img src=x onerror=alert(1)>",
        "source_url": "https://example.org/a?x=1&y=\"2\"",  # hardcode-ok: URL fictícia de fixture para testar o escape de HTML  # noqa: E501
        "source_publication_year": 2020,
    }]}
    original = Path.read_text
    monkeypatch.setattr(
        Path, "read_text",
        lambda self, *a, **k: json.dumps(hostile) if self.name == EVIDENCE_PATH.name
        else original(self, *a, **k),
    )
    markup = render_presidency_sources()
    for raw in ("<script>", "<img", "<b>base", 'href="https://example.org/a?x=1&y='):  # hardcode-ok: valor esperado da fixture fictícia  # noqa: E501
        assert raw not in markup
    assert "&lt;script&gt;" in markup
    assert "&lt;img" in markup


def test_mandatory_caveats_are_visible():
    markup = " ".join(render_data_sources().split())
    assert "síntese editorial" in markup
    assert "não uma pesquisa realizada em 2026" in markup
    assert "A classificação do governo é separada da filiação do presidente" in markup
    assert "Ausência de filiação informada não comprova desfiliação" in markup
