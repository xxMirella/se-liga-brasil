"""A proposition label cannot substitute for the round or object actually voted."""

import pytest

from crawlers.camara.configuration import API_BASE
from crawlers.camara.voting_normalization import normalize_voting_event
from crawlers.camara.voting_staging import event_matter_fields
from service.public_profile_web.vote_groups import render_monthly_vote_cards


def event_row(**values):
    return {
        "id": "100-1",
        "uri": API_BASE + "votacoes/100-1",
        "data": "2024-05-15",
    } | values


@pytest.mark.parametrize(
    ("subject", "description", "expected"),
    [
        ("Votação da Emenda Aglutinativa nº 1.",
         "Aprovada, em primeiro turno, a Proposta de Emenda à Constituição.", 1),
        ("Votação em segundo turno.", "Aprovada a proposta.", 2),
        ("Votação em primeiro turno.", "Aprovada, em segundo turno, a proposta.", None),
        ("Votação de requerimento.", "Aprovado o Requerimento.", None),
        ("Dispensa de interstício entre o primeiro e o segundo turnos.",
         "Aprovado o Requerimento.", None),
        ("Votação de requerimento.",
         "Aprovado o requerimento para apreciação do segundo turno da PEC.", None),
        ("Comparação do primeiro turno com o segundo turno.", "Aprovado.", None),
    ],
)
def test_only_explicit_event_round_is_extracted(subject, description, expected):
    discovery = event_row()
    detail = event_row(descUltimaAberturaVotacao=subject, descricao=description)
    assert normalize_voting_event(discovery, detail)["round_number"] == expected


def test_related_matter_does_not_replace_the_official_voting_evidence_link():
    uri = API_BASE + "proposicoes/100"
    event = {"discovery": event_row(), "detail": {}}
    normalized = {"official_url": API_BASE + "votacoes/100-1"}
    matter = {"siglaTipo": "PEC", "numero": 1, "ano": 2024, "ementa": "Texto fictício."}
    assert event_matter_fields(event, normalized, {uri: matter}, uri)["official_url"] == (
        API_BASE + "votacoes/100-1"
    )


def test_monthly_card_exposes_day_and_each_evidenced_round_before_history_dialog():
    base = {
        "occurred_on": "2024-05-15", "date_precision": "day",
        "proposition": {"kind": "PEC", "number": "1", "year": 2024},
        "institution": {"code": "camara", "name": "Câmara dos Deputados"},
        "individual": {"choice": "yes", "participation_status": "voted"},
    }
    records = [base | {"round_number": value} for value in (None, 1, 2)]
    html = render_monthly_vote_cards("2024-05", records)
    card = html.split("<dialog", 1)[0]
    assert "2024-05-15 · 1º turno" in card
    assert "2024-05-15 · 2º turno" in card
    assert "Turno não informado" in card
