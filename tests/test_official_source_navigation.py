"""Official evidence opens separately while local navigation preserves its tab."""

from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest

from service.civic_education.page import render_civic_education
from service.project_information.page import render_project_information
from service.public_profile_web.asset_declarations import render_declaration_sources
from service.public_profile_web.cabinet_payroll import render_cabinet_month
from service.public_profile_web.office_scopes import render_scope_sources
from service.public_profile_web.pages import render_tabs
from service.public_profile_web.profile import render_attendance_history
from service.public_profile_web.propositions import render_authorship_card
from service.public_profile_web.vote_groups import render_activity_history_entry

SOURCE = "https://www.senado.leg.br/atividade?a=1&b=2"


class AnchorDocument(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.links = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.links.append(dict(attrs))


def rendered_evidence(component):
    if component == "attendance":
        return render_attendance_history([{"sourceUrl": SOURCE}])
    if component == "cabinet":
        return render_cabinet_month({
            "sourceUrl": SOURCE, "period": "2026-09", "roles": [],
            "total_amount": "10", "payment_entries": 1,
        })
    if component == "assets":
        return render_declaration_sources([{"official_url": SOURCE}])
    if component == "office_scope":
        return render_scope_sources([{"url": SOURCE, "title": "Documento"}])
    if component == "proposal":
        return render_authorship_card({"official_url": SOURCE})
    if component == "civic_education":
        return render_civic_education("todos")
    if component == "project_information":
        return render_project_information()
    return render_activity_history_entry({"official_url": SOURCE, "action_type": component})


@pytest.mark.parametrize("component", [
    "attendance", "cabinet", "assets", "office_scope", "proposal", "vote",
    "authorship", "procedure", "civic_education", "project_information",
])
def test_rendered_official_sources_open_new_tab_with_isolated_opener(component):
    document = AnchorDocument(rendered_evidence(component))
    external = [link for link in document.links if urlsplit(link["href"]).scheme == "https"]
    assert external, f"Evidence fixture must exercise a source link: {component}"
    for link in external:
        assert link.get("target") == "_blank", link["href"]
        assert {"noopener", "noreferrer"} <= set(link.get("rel", "").split()), link["href"]


def test_internal_profile_navigation_stays_in_current_tab():
    markup = render_tabs("/pessoas/pessoa", {}, "profile") + render_civic_education("todos")
    links = [link for link in AnchorDocument(markup).links if not urlsplit(link["href"]).scheme]
    assert links
    assert all(link.get("target") in {None, "_self"} for link in links)
