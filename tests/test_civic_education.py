"""The guide remains usable without database access and preserves legal exceptions."""

from html.parser import HTMLParser

import pytest

from application.public_portal import dispatch_portal_request
from service.civic_education.laws import LAW_NORMS
from service.civic_education.office_cards import OFFICE_CARDS
from service.civic_education.page import render_civic_education
from service.public_profile_web.pages import render_person_profile


class GuideMarkup(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.ids, self.references, self.links, self.tags = set(), [], [], []
        self.in_header = False
        self.executable_scripts = []
        self.header_links, self.header_current = [], []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        is_data = values.get("type") == "application/ld+json"
        is_site_file = str(values.get("src", "")).startswith("/assets/") and "defer" in values
        if tag == "script" and not is_data and not is_site_file:
            self.executable_scripts.append(values)
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
    assert document.executable_scripts == []  # only same-origin deferred files, never inline
    assert 'type="application/ld+json"' in response.body.decode()
    assert "Não é uma escada de chefes" in response.body.decode()
    body = response.body.decode()
    offices_step = body.split('id="passo-2"', 1)[1].split('id="passo-3"', 1)[0]
    for key, cards in OFFICE_CARDS.items():
        shown = sphere == "todos" or key == sphere
        # Exact tag text: "Governador e governadora" is a prefix of the DF card's name.
        assert all((f">{card[1]}<" in offices_step) == shown for card in cards)


def test_all_reference_norms_and_the_pec_exception_are_accessible():
    markup = render_civic_education("todos")
    for title, tag, *_ in LAW_NORMS:
        assert title in markup and tag in markup
    assert "O presidente não sanciona nem veta" in markup


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


def test_guide_is_in_global_header_not_the_persons_tabs():
    profile = {"person_id": "00000000-0000-0000-0000-000000000001", "display_name": "Pessoa"}
    document = GuideMarkup(render_person_profile(profile, {}, {"tab": "profile"}))
    assert document.header_links.count("/como-funciona") == 1
    assert document.links.count("/como-funciona") == 1
    assert document.header_current == ["/pessoas"]
    guide = GuideMarkup(render_civic_education())
    assert guide.header_current == ["/como-funciona"]


def test_offices_step_follows_the_reference_structure_without_inline_script():
    markup = render_civic_education("municipal")
    assert "Passo 2 de 4" in markup and "O que cada cargo pode fazer?" in markup
    assert "Antes de começar: UBS, UPA e hospital, e quem administra cada um" in markup
    assert markup.count("<summary>Exemplo na saúde</summary>") == 3
    assert 'href="?esfera=distrital#cargos"' in markup
    assert 'aria-current="true">Cidade</a>' in markup
    assert "A UBS municipal está com goteira. Quem organiza o conserto?" in markup
    assert "Fonte: <a " in markup and "Ver detalhes" not in markup
    assert markup.count("<dt>Pode</dt>") == 3 and "Suplente parlamentar" not in markup
    assert "<script>" not in markup


def test_guide_loads_its_enhancement_scripts_only_as_same_origin_files():
    markup = render_civic_education("municipal")

    for source in ("scroll-reveal.js", "civic-guide.js", "civic-review.js"):
        assert f'<script src="/assets/{source}" defer></script>' in markup


def test_static_export_strips_scripts_because_the_hosting_policy_forbids_them():
    from service.static_publication.build import prepare_static_document

    document = prepare_static_document(render_civic_education("municipal"), {}, "")

    assert b"<script src=" not in document
    assert b"ds-civic-stepper" in document
