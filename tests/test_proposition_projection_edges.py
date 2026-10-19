from datetime import date
from types import SimpleNamespace

import pytest

from database.public_propositions import fetch_person_propositions
from service.public_profile_web.propositions import (
    render_authorship_card,
    render_person_propositions,
    render_proposition_pagination,
)

PERSON = "00000000-0000-0000-0000-000000000001"


@pytest.mark.parametrize("page", [0, 1001, True, "2"])
def test_invalid_proposal_pages_are_rejected_before_database_access(page):
    with pytest.raises(ValueError):
        fetch_person_propositions(None, PERSON, date(2026, 10, 19), page)


def test_public_authorship_projection_preserves_unknown_dates_and_limits_rows():
    row = {
        "id": 1,
        "title": "PEC 1/2025",
        "kind": "PEC",
        "introduced_on": None,
        "summary": "Resumo oficial",
        "official_key": "https://www.camara.leg.br/proposta",
        "institution": "Câmara",
        "roles": ["coauthor"],
        "cpf": "PRIVATE",
    }
    calls = []
    connection = SimpleNamespace(
        execute=lambda sql, params: (
            calls.append(params) or SimpleNamespace(fetchall=lambda: [row] * 101)
        )
    )
    result = fetch_person_propositions(connection, PERSON, date(2026, 10, 19), 2)
    assert result["truncated"] and len(result["items"]) == 100
    assert result["items"][0]["date_precision"] == "unknown"
    assert "PRIVATE" not in str(result) and calls[0][-1] == 100
    dated = row | {"introduced_on": date(2025, 2, 25)}
    connection.execute = lambda *_: SimpleNamespace(fetchall=lambda: [dated])
    assert (
        fetch_person_propositions(connection, PERSON, date(2026, 10, 19))["items"][0]["occurred_on"]
        == "2025-02-25"
    )


def test_authorship_history_handles_dated_and_undated_proposals_without_false_approval():
    items = [
        {
            "title": "PEC 1/2025",
            "occurred_on": "2025-02-25",
            "summary": "Resumo",
            "roles": ["author", "coauthor", "rapporteur"],
            "official_url": "https://www.camara.leg.br/proposta",
        },
        {
            "title": "Relatório sem data",
            "roles": ["unknown"],
            "official_url": "javascript:alert(1)",
        },
    ]
    html = render_person_propositions({"person_id": PERSON, "propositions": {"items": items}})
    assert "Fevereiro de 2025" in html and "Data de apresentação não informada" in html
    assert "Coautoria" in html and "Relatoria" in html and "Papel documentado" in html
    assert "javascript:" not in html and "não significa" in html
    assert render_person_propositions({}) == ""
    assert "Data não informada" in render_authorship_card({})


def test_proposal_pagination_keeps_all_pages_reachable():
    html = render_proposition_pagination({"person_id": PERSON}, {"page": 2, "truncated": True})
    assert "proposal_page=1" in html and "proposal_page=3" in html
