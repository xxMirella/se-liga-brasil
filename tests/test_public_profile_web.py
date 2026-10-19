"""Presentation tests use isolated fixtures, never database inserts."""

from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

import pytest

from service.public_profile_web import render_person_profile, render_search_page
from service.public_profile_web.security import official_url

PERSON_ID = str(UUID(int=1))


class Document(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.links = []
        self.tags = []
        self.inputs = {}
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        self.tags.append(tag)
        if tag == "a":
            self.links.append(attributes)
        if tag in {"input", "select"}:
            self.inputs[attributes.get("name")] = attributes


@pytest.fixture
def profile():
    return {
        "person_id": PERSON_ID,
        "display_name": "Pessoa de teste",
        "as_of": "2026-10-18",
        "age": {"value": 40, "status": "confirmed"},
        "political_party": {
            "abbreviation": "ABC",
            "name": "Partido de teste",
            "status": "observed",
            "observed_on": "2024-09-01",
            "evidence_kind": "electoral_declaration",
        },
        "current_offices": [],
        "payments": [],
    }


@pytest.fixture
def filters():
    return {"tab": "activity", "start_date": "2026-10-01", "end_date": "2026-10-18"}


def vote(**updates):
    record = {
        "occurred_on": "2026-10-14",
        "date_precision": "day",
        "proposition": {
            "title": "PEC 1/2026",
            "short_description": "Altera dispositivo constitucional.",
            "official_url": "https://www.senado.leg.br/atividade/materia/1",
        },
        "individual": {"choice": "yes", "participation_status": "voted"},
        "subject": "Primeiro turno",
        "round_number": 1,
        "collective_result": "unknown",
        "institution": {"name": "Senado Federal"},
    }
    return record | updates


def test_profile_activity_shows_month_and_distinct_vote_result(profile, filters):
    markup = render_person_profile(profile, {"items": [vote()]}, filters)
    assert "Outubro de 2026" in markup
    assert "Sim · a favor do objeto votado" in markup
    assert "Resultado coletivo" in markup
    assert "Aprovado" not in markup
    assert "Partido declarado na eleição" not in markup
    assert "Partido observado na fonte" not in markup
    assert "Filiação atual confirmada" not in markup
    assert "40 anos" in markup
    assert "Não representa remuneração zero" in markup
    assert "Resumo oficial ainda não disponível" not in markup
    document = Document(markup)
    assert "script" not in document.tags
    assert document.inputs["start_date"]["value"] == "2026-10-01"
    assert document.inputs["end_date"]["value"] == "2026-10-18"


def test_empty_activity_is_not_inactivity_and_no_fake_profile_values(profile, filters):
    markup = render_person_profile(profile | {"age": {}}, {"items": []}, filters)
    assert "Nenhum voto vinculado" in markup
    assert "inatividade" in markup
    assert "Foto não disponível" in markup
    assert "40 anos" not in markup
    assert "0 anos" not in markup
    assert "R$ 0" not in markup


def test_escaped_sources_cannot_create_script_or_foreign_link(profile, filters):
    malicious = '<script>alert("x")</script>'
    record = vote(proposition={"title": malicious, "official_url": "javascript:alert(1)"})
    markup = render_person_profile(
        profile | {"display_name": malicious, "photo": {"url": "https://tracker.example/x"}},
        {"items": [record]},
        filters,
    )
    assert "&lt;script&gt;" in markup
    assert "script" not in Document(markup).tags
    assert "javascript:" not in markup
    assert "tracker.example" not in markup


def test_pagination_keeps_filters_and_encodes_cursor(profile, filters):
    filters = filters | {"office_kind": "senator", "exercise_id": "7", "cursor": "old"}
    markup = render_person_profile(profile, {"items": [], "next_cursor": "new+/=x&y"}, filters)
    links = Document(markup).links
    next_link = next(link for link in links if "cursor=" in link.get("href", ""))
    parameters = parse_qs(urlsplit(next_link["href"]).query)
    assert parameters["cursor"] == ["new+/=x&y"]
    assert parameters["office_kind"] == ["senator"]
    assert parameters["exercise_id"] == ["7"]
    assert parameters["start_date"] == ["2026-10-01"]
    assert parameters["tab"] == ["activity"]
    tab_links = [link for link in links if link.get("aria-current") == "page"]
    assert "cursor" not in parse_qs(urlsplit(tab_links[0]["href"]).query)


def test_absence_is_not_no_and_undated_votes_have_own_group(profile, filters):
    record = vote(
        occurred_on="2026-01-01",
        date_precision="year",
        individual={"choice": "no", "participation_status": "absent"},
    )
    markup = render_person_profile(profile, {"items": [record]}, filters)
    assert "Ausência registrada" in markup
    assert "Não · contra" not in markup
    assert "Sem mês de votação confirmado" in markup
    assert "Janeiro de 2026" not in markup


def test_profile_overview_does_not_claim_missing_domains_available(profile):
    markup = render_person_profile(profile, {}, {"tab": "profile"})
    assert "Informações do perfil" in markup
    assert "Declarações de bens ainda não disponíveis neste perfil" in markup
    assert 'class="activity-controls"' not in markup


def test_multiple_payments_and_offices_are_not_summed(profile):
    profile["payments"] = [
        {"gross_amount": "100.00", "competence": "2026-09", "organization_code": "one"},
        {"gross_amount": "200.00", "competence": "2026-08", "organization_code": "two"},
    ]
    profile["current_offices"] = [
        {
            "office_kind": "senator",
            "institution": {"name": "Órgão A"},
            "tenure": {"years": 1, "months": 2},
        },
        {"office_kind": "other", "institution": {"name": "Órgão B"}, "tenure": {}},
    ]
    markup = render_person_profile(profile, {}, {})
    assert "R$ 100.00" in markup and "R$ 200.00" in markup
    assert "R$ 300" not in markup
    assert "2026-09" in markup and "2026-08" in markup
    assert "Órgão A" in markup and "Órgão B" in markup
    assert "1 anos e 2 meses" in markup


def test_private_fields_are_never_serialized(profile, filters):
    private = {
        "cpf": "DO_NOT_EXPOSE",
        "birth_date": "DO_NOT_EXPOSE",
        "storage_key": "DO_NOT_EXPOSE",
    }
    markup = render_person_profile(profile | private, {"items": [vote() | private]}, filters)
    assert "DO_NOT_EXPOSE" not in markup


def test_search_projects_only_public_identity_and_escapes_query():
    markup = render_search_page(
        '"><script>x</script>',
        {"items": [{"person_id": PERSON_ID, "display_name": "Pessoa <A>", "cpf": "PRIVATE"}]},
    )
    assert f'href="/pessoas/{PERSON_ID}"' in markup
    assert "Pessoa &lt;A&gt;" in markup
    assert "PRIVATE" not in markup
    assert "script" not in Document(markup).tags


def test_rendering_consumes_at_most_one_page(profile, filters):
    def bounded_votes():
        for _ in range(100):
            yield vote()
        raise AssertionError("Renderer consumed beyond its public page budget")

    markup = render_person_profile(profile, {"items": bounded_votes()}, filters)
    assert markup.count('class="event-body"') == 1
    assert markup.count('class="voting-history-entry"') == 100
    assert markup.count("Outubro de 2026") == 1


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://senado.leg.br.evil.example/x",
        "//senado.leg.br/x",
        "https://user:password@senado.leg.br/x",
        "https://senado.leg.br:444/x",
        "https://senado.leg.br/\nx",
        "https://senado.leg.br:invalid/x",
    ],
)
def test_official_url_rejects_unsafe_destinations(url):
    assert official_url(url) is None


def test_search_filter_mapping_is_preserved_in_next_page():
    filters = {
        "q": "Pessoa",
        "uf": "SP",
        "office_kind": "senator",
        "political_party": "ABC",
        "limit": "10",
    }
    markup = render_search_page(filters, {"items": [], "next_cursor": "next"})
    document = Document(markup)
    href = next(link["href"] for link in document.links if "cursor=" in link.get("href", ""))
    parameters = parse_qs(urlsplit(href).query)
    for key, value in filters.items():
        assert parameters[key] == [value]
    assert parameters["cursor"] == ["next"]
    assert document.inputs["political_party"]["value"] == "ABC"


def test_historical_office_observation_is_not_current_confirmation(profile):
    profile["public_office"] = {
        "has_current_public_office": True,
        "status": "historical_observation",
        "office_kind": "senator",
        "institution": {"name": "Senado Federal"},
        "observed_on": "2024-01-01",
    }
    markup = render_person_profile(profile, {}, {})
    assert "Senador(a)" in markup
    assert "Cargo observado em 2024-01-01; exercício atual não confirmado" in markup
    assert "Início individual não confirmado" in markup


def test_current_competence_not_marked_as_stale(profile):
    profile["payments"] = [
        {"gross_amount": "100.00", "competence": "2026-10", "freshness": "current_competence"}
    ]
    markup = render_person_profile(profile, {}, {})
    assert "R$ 100.00" in markup
    assert "Última publicação disponível; não confirma o mês atual" not in markup


def test_search_summary_does_not_infer_missing_office_from_reduced_dto():
    markup = render_search_page(
        "Pessoa", {"items": [{"person_id": PERSON_ID, "display_name": "Pessoa"}]}
    )
    assert "Cargo atual não confirmado" not in markup
    assert "Sem cargo público atual" not in markup
    assert "Consultar perfil" in markup


def test_storage_vote_description_and_link_use_event_contract(profile, filters):
    record = vote(
        proposition={"title": "PEC 1/2026"},
        short_description="Descrição curta do evento.",
        description_kind="official_excerpt",
        official_url="https://www.senado.leg.br/materia/1",
    )
    markup = render_person_profile(profile, {"items": [record]}, filters)
    assert "Descrição curta do evento." in markup
    assert "Trecho da ementa oficial" in markup
    assert 'href="https://www.senado.leg.br/materia/1"' in markup
