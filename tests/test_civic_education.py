"""The guide remains usable without database access and preserves legal exceptions."""

from html.parser import HTMLParser
from pathlib import Path
from xml.etree import ElementTree

import pytest

from application.public_portal import dispatch_portal_request
from service.civic_education.laws import LAW_TYPES
from service.civic_education.office_decisions import OFFICE_DECISIONS
from service.civic_education.offices import OFFICES
from service.civic_education.page import render_civic_education
from service.public_profile_web.pages import render_person_profile


class GuideMarkup(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.ids, self.references, self.links, self.tags = set(), [], [], []
        self.in_header = False
        self.header_links, self.header_current = [], []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "header":
            self.in_header = True
        self.tags.append(tag)
        if values.get("id"):
            assert values["id"] not in self.ids
            self.ids.add(values["id"])
        if values.get("href"):
            if self.in_header:
                self.header_links.append(values["href"])
                if values.get("aria-current") == "page":
                    self.header_current.append(values["href"])
            self.links.append(values["href"])
            if values["href"].startswith("#"):
                self.references.append(values["href"][1:])

    def handle_endtag(self, tag):
        if tag == "header":
            self.in_header = False


@pytest.mark.parametrize("sphere", ["municipal", "estadual", "federal", "distrital", "todos"])
def test_every_sphere_renders_without_database_or_client_code(sphere):
    response = dispatch_portal_request(object(), "/como-funciona?esfera=" + sphere)
    assert response.status == 200
    document = GuideMarkup(response.body.decode())
    assert set(document.references) <= document.ids
    assert "script" not in document.tags
    assert "Não é uma escada de chefes" in response.body.decode()
    for office in OFFICES:
        assert ("cargo-" + office[0] in document.ids) == (sphere == "todos" or office[1] == sphere)


def test_all_normative_kinds_and_constitutional_exceptions_are_accessible():
    markup = render_civic_education("todos")
    for title, explanation, *_ in LAW_TYPES:
        assert isinstance(explanation, str)
        assert title in markup
    assert "O presidente não sanciona nem veta" in markup
    assert "Deputados federais e senadores aprovam a autorização" in markup
    assert "PPA, LDO e LOA" in markup
    assert "Quórum" in markup
    assert "ainda não foi testada" in markup
    assert "PMC3932674" in markup


@pytest.mark.parametrize(
    "query", ["esfera=invalid", "esfera=federal&esfera=municipal", "unknown=x"]
)
def test_invalid_or_ambiguous_filters_fail_before_data_access(query):
    response = dispatch_portal_request(object(), "/como-funciona?" + query)
    assert response.status == 400
    assert response.content_type.startswith("text/html")


def test_civic_stylesheet_served_without_credentials_or_database():
    response = dispatch_portal_request(object(), "/assets/civic-education.css")
    assert response.status == 200
    assert response.content_type.startswith("text/css")
    assert b"@media" in response.body


def test_circle_diagrams_have_distinct_meanings_and_accessible_descriptions():
    markup = render_civic_education()
    document = GuideMarkup(markup)
    assert document.tags.count("svg") == 3
    assert "office-reach-title" in document.ids
    assert "shared-title" in document.ids
    assert "proposal-title" in document.ids
    assert "Quem atua em cada esfera?" in markup
    assert "Onde fica sua rua?" not in markup
    assert "Cada círculo reúne cargos" in markup
    assert "Cooperação entre poderes" in markup
    assert "O prefeito não vota como vereador" in markup
    assets = Path(__file__).resolve().parents[1] / "src/service/civic_education/assets"
    for path in assets.glob("*.svg"):
        root = ElementTree.parse(path).getroot()
        assert root.attrib["role"] == "img"
        assert root.attrib["aria-labelledby"]


def test_every_office_explains_proposals_votes_and_people_affected():
    assert set(OFFICE_DECISIONS) == {office[0] for office in OFFICES}
    markup = render_civic_education("todos")
    assert markup.count("<dt>Pode apresentar propostas?</dt>") == len(OFFICES)
    assert markup.count("<dt>Vota e aprova leis?</dt>") == len(OFFICES)
    assert markup.count("<dt>Quem é atendido ou afetado?</dt>") == len(OFFICES)
    assert "Não vota como vereador na Câmara" in markup
    assert "Dos vereadores, que formam a Câmara Municipal" in markup
    assert "não apenas no estado pelo qual foi eleito" in markup
    assert "Representa um estado ou o DF, mas vota leis" in markup
    assert "Não são só para quem votou nele" in markup


def test_guide_is_in_global_header_not_the_persons_tabs():
    profile = {"person_id": "00000000-0000-0000-0000-000000000001", "display_name": "Pessoa"}
    document = GuideMarkup(render_person_profile(profile, {}, {"tab": "profile"}))
    assert document.header_links.count("/como-funciona") == 1
    assert document.links.count("/como-funciona") == 1
    assert document.header_current == ["/pessoas"]
    guide = GuideMarkup(render_civic_education())
    assert guide.header_current == ["/como-funciona"]


def test_ubs_example_separates_lawmaking_execution_and_oversight():
    markup = render_civic_education()
    assert "Juntos: mudar uma regra do SUS" in markup
    assert "No bairro: reformar uma UBS municipal" in markup
    assert "organizam e executam a reforma" in markup
    assert "votam o orçamento e fiscalizam a obra e os gastos" in markup
    assert "Nem todo reparo precisa de uma nova lei" in markup
