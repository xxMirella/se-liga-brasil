"""Current SAPL data must exclude former members and future legislatures."""

import json
from datetime import date

import pytest

from crawlers.interlegis.roster import parse_current_roster, select_current_legislature
from service.ingestion.contracts import IngestionError


def test_selects_current_legislature_instead_of_future_election():
    payload = json.dumps(
        [
            {"id": 20, "data_inicio": "2023-02-01", "data_fim": "2027-01-31"},
            {"id": 21, "data_inicio": "2027-02-01", "data_fim": "2031-01-31"},
        ]
    )
    assert select_current_legislature(payload, date(2026, 10, 24)) == "20"


def test_inactive_titular_excluded_and_active_substitute_retained():
    payload = json.dumps(
        [
            {"id": 1, "nome_parlamentar": "Licensed", "ativo": False, "titular": "Sim"},
            {
                "id": 2,
                "nome_parlamentar": "Substitute",
                "ativo": True,
                "titular": "Não",
                "partido": "PT",
            },
        ]
    )
    members = parse_current_roster(payload)
    assert len(members) == 1
    assert members[0]["provider_subject_id"] == "2"


def test_paginated_incomplete_roster_rejected():
    with pytest.raises(IngestionError, match="PAGINATION_INCOMPLETE"):
        parse_current_roster(json.dumps({"next": "page2", "results": [{"id": 1}]}))


def test_ambiguous_current_legislatures_rejected():
    row = {"id": 20, "data_inicio": "2023-02-01", "data_fim": "2027-01-31"}
    with pytest.raises(IngestionError, match="LEGISLATURE_AMBIGUOUS"):
        select_current_legislature(json.dumps([row, row]), date(2026, 10, 24))
