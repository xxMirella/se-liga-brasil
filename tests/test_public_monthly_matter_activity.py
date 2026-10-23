"""Group evidenced actions by exact official matter, institution and action month."""

import pytest

from service.public_profile_web.activity import render_person_activity
from service.public_profile_web.vote_groups import proposition_group_key

PERSON = "00000000-0000-0000-0000-000000000001"


@pytest.mark.parametrize("person_id", [PERSON, "00000000-0000-0000-0000-000000000002"])
@pytest.mark.parametrize("institution", ["camara", "senado"])
def test_monthly_grouping_is_the_shared_default_for_any_person_and_institution(
    person_id, institution
):
    item = proposal(institution_code=institution, institution=institution)
    first = vote(institution={"code": institution, "name": institution})
    second = first | {"voting_id": institution + ":voting:42-2", "round_number": 2}
    profile = {"person_id": person_id, "display_name": "Pessoa pública fictícia",
               "propositions": {"items": [item]}}
    html = render_person_activity(profile, {"items": [first, second]})
    assert html.count('<article class="timeline-event') == 1
    assert html.count('<li class="voting-history-entry">') == 3
    assert "Autoria" in html and "Votação de emenda" in html
    assert "1º turno" in html and "2º turno" in html


def proposal(**values):
    return {
        "id": 42, "kind": "PEC", "number": "1", "year": 2024, "title": "PEC 1/2024",
        "official_key": "https://dadosabertos.camara.leg.br/api/v2/proposicoes/42",
        "official_url": "https://dadosabertos.camara.leg.br/api/v2/proposicoes/42",
        "institution_code": "camara", "institution": "Câmara dos Deputados",
        "occurred_on": "2024-05-01", "date_precision": "day", "roles": ["author"],
    } | values


def vote(**values):
    return {
        "voting_id": "camara:voting:42-1", "occurred_on": "2024-05-15",
        "date_precision": "day", "round_number": 1, "subject": "Votação de emenda",
        "proposition": {"kind": "PEC", "number": "1", "year": 2024, "title": "PEC 1/2024"},
        "institution": {"code": "camara", "name": "Câmara dos Deputados"},
        "individual": {"choice": "yes", "participation_status": "voted"},
        "official_url": "https://dadosabertos.camara.leg.br/api/v2/votacoes/42-1",
    } | values


def render(proposals, votes):
    profile = {"person_id": PERSON, "propositions": {"items": proposals}}
    return render_person_activity(profile, {"items": votes})


def test_one_monthly_matter_card_keeps_authorship_revision_and_distinct_votes():
    event = {"official_event_key": "https://www.camara.leg.br/evento/1",
             "occurred_at": "2024-05-10T12:00:00-03:00", "event_type": "revision",
             "description": "Revisão oficialmente documentada"}
    html = render([proposal(events=[event])], [vote(), vote(
        voting_id="camara:voting:42-2", round_number=2,
        official_url="https://dadosabertos.camara.leg.br/api/v2/votacoes/42-2")])
    assert html.count('<article class="timeline-event') == 1
    assert html.count('<li class="voting-history-entry">') == 4
    assert "Autoria" in html and "Revisão oficialmente documentada" in html
    assert "2024-05-01" in html and "2024-05-10" in html and "2024-05-15" in html
    assert "votacoes/42-1" in html and "evento/1" in html
    assert "não significa que cada ação foi realizada pela pessoa" in html


def test_months_and_institutions_never_collapse_into_one_card():
    records = [vote(), vote(occurred_on="2024-06-01"), vote(
        institution={"code": "senado", "name": "Senado Federal"})]
    html = render([proposal()], records)
    assert html.count('<article class="timeline-event') == 3


def test_only_explicit_same_institution_parent_groups_an_amendment_with_a_matter():
    parent = {"kind": "PEC", "number": "1", "year": 2024, "institution_code": "camara"}
    amendment = vote(proposition={"id": "amendment-1", "official_parent": parent})
    assert proposition_group_key(amendment) == proposition_group_key(vote())
    parent["institution_code"] = "senado"
    assert proposition_group_key(amendment) != proposition_group_key(vote())


def test_similar_titles_without_an_official_relationship_stay_separate():
    first = vote(proposition={"title": "Fim da escala 6x1"}, voting_id="1")
    second = vote(proposition={"title": "Fim da escala 6x1"}, voting_id="2")
    assert proposition_group_key(first) != proposition_group_key(second)
    assert render([], [first, second]).count('<article class="timeline-event') == 2


def test_empty_official_identifiers_never_create_a_shared_matter():
    missing = {"kind": "", "number": "", "year": 2024, "title": "Título coincidente"}
    assert proposition_group_key(vote(proposition=missing, voting_id="1")) != (
        proposition_group_key(vote(proposition=missing, voting_id="2")))


def test_identical_prl_numbers_with_distinct_principal_bills_remain_distinct_cards():
    first = proposal(id=101, kind="PRL", number="1", year=None, title="PRL 1",
                     official_parent={"institution_code": "camara", "kind": "PL",
                                      "number": "10", "year": 2024, "title": "PL 10/2024"})
    second = proposal(id=102, kind="PRL", number="1", year=None, title="PRL 1",
                      official_parent={"institution_code": "camara", "kind": "PL",
                                       "number": "20", "year": 2024, "title": "PL 20/2024"})
    html = render([first, second], [])
    assert html.count('<article class="timeline-event') == 2
    assert "PRL 1 — PL 10/2024" in html and "PRL 1 — PL 20/2024" in html


def test_prl_and_substitute_group_only_when_their_explicit_principal_bill_matches():
    parent = {"institution_code": "camara", "kind": "PL", "number": "10",
              "year": 2024, "title": "PL 10/2024"}
    first = proposal(id=101, kind="PRL", number="1", year=None, title="PRL 1",
                     official_parent=parent)
    second = proposal(id=102, kind="SBT", number="1", year=None, title="SBT 1",
                      official_parent=parent)
    html = render([first, second], [])
    assert html.count('<article class="timeline-event') == 1
    assert "PRL 1 — PL 10/2024" in html and "SBT 1 — PL 10/2024" in html


def test_unknown_principal_keeps_identical_prl_titles_separate_and_disambiguated():
    first = proposal(id=101, official_key="https://dadosabertos.camara.leg.br/api/v2/proposicoes/101",
                     kind="PRL", year=None, title="PRL 1", document_label="Documento Câmara 101")
    second = first | {"id": 102, "official_key":
                      "https://dadosabertos.camara.leg.br/api/v2/proposicoes/102",
                      "document_label": "Documento Câmara 102"}
    html = render([first, second], [])
    assert html.count('<article class="timeline-event') == 2
    assert "PRL 1 — Documento Câmara 101" in html
    assert "PRL 1 — Documento Câmara 102" in html


def test_event_limits_are_visible_without_creating_missing_actions():
    html = render([proposal(events_truncated=True)], [])
    assert "limite de 100" in html
    assert html.count('<li class="voting-history-entry">') == 1


def test_official_event_date_without_timestamp_remains_visible():
    event = {"occurred_on": "2024-05-10", "description": "Revisão oficial"}
    html = render([proposal(events=[event])], [])
    assert "2024-05-10" in html
    assert "Data completa não confirmada" not in html


def test_matter_history_uses_public_action_labels_instead_of_internal_event_codes():
    event = {"occurred_on": "2024-05-10", "event_type": "official_proceeding",
             "description": "Apresentação registrada na fonte"}
    html = render([proposal(events=[event])], [])
    assert "Tramitação da matéria · Tramitação oficial" in html
    assert "official_proceeding" not in html


def test_period_filter_applies_to_authorship_and_matter_events():
    profile = {"person_id": PERSON, "propositions": {"items": [proposal()]}}
    votes = {"items": [vote()], "period": {
        "starts_on": "2024-05-10", "ends_on_inclusive": "2024-05-20"}}
    html = render_person_activity(profile, votes, {"scope": "period"})
    assert html.count('<li class="voting-history-entry">') == 1
    assert "2024-05-01" not in html
    historical = render_person_activity(profile, votes, {"scope": "history"})
    assert historical.count('<li class="voting-history-entry">') == 2


def test_office_filter_never_attributes_unlinked_matter_events_to_that_office():
    profile = {"person_id": PERSON, "propositions": {"items": [proposal()]}}
    html = render_person_activity(profile, {"items": [vote()]}, {"office_kind": "senator"})
    assert html.count('<li class="voting-history-entry">') == 1
    assert "sem vínculo comprovado ao cargo filtrado" in html
