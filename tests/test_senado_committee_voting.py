"""Fictional examples matching the committee JSON/XSD verified on 17 October 2026."""

import json
from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from crawlers.senado.committee_voting import (
    collect_committee_votings,
    committee_voting_rows,
    normalize_committee_individual_vote,
    normalize_committee_voting,
    resolve_committee_individuals,
)
from service.ingestion.contracts import IngestionError


def committee_row(**changes):
    return {
        "CodigoVotacao": "123",
        "SiglaCasaColegiado": "SF",
        "CodigoReuniao": "4",
        "CodigoColegiado": "34",
        "SiglaColegiado": "CCJ",
        "DataHoraInicioReuniao": "2025-12-17T09:13:00",
        "IdentificacaoMateria": "PL 1/2025",
        "DescricaoVotacao": "Objeto fictício",
        "CodigoParlamentarPresidente": "999",
        "NomeParlamentarPresidente": "Pessoa Presidente",
        "Votos": {
            "Voto": [
                {
                    "CodigoParlamentar": "1",
                    "NomeParlamentar": "Pessoa Fictícia",
                    "SiglaCasaParlamentar": "SF",
                    "QualidadeVoto": "S",
                    "VotoPresidente": "false",
                }
            ]
        },
        "TotalVotosSim": "1",
        "TotalVotosNao": "0",
        "TotalVotosAbstencao": "0",
    } | changes


def envelope(rows=None):
    body = {"Metadados": {"VersaoServico": "1"}}
    if rows is not None:
        body["Votacoes"] = {"Votacao": rows}
    return {"VotacoesComissao": body}


def test_no_records_published_is_not_proof_of_no_votes():
    rows, status = committee_voting_rows(envelope())
    assert rows == [] and status == "not_published_in_response"
    acquisition = SimpleNamespace(json_document=lambda *args: (envelope(), object()))
    records, _, coverage = collect_committee_votings(
        acquisition, "CCJ", date(2025, 12, 10), date(2025, 12, 10)
    )
    assert records == [] and coverage["coverage"] == "not_verified"


def test_different_objects_same_meeting_are_distinct_and_have_no_fabricated_voting_time():
    first = normalize_committee_voting(committee_row())
    second = normalize_committee_voting(committee_row(CodigoVotacao="124"))
    assert first["source_key"] == "committee:SF:34:123"
    assert second["source_key"] != first["source_key"]
    assert first["meeting_date"] == second["meeting_date"] == "2025-12-17"
    assert first["occurred_on"] is None and first["date_precision"] == "unknown"
    assert first["proposition_source_key"] is None and first["collective_result_code"] is None
    assert first["proposition_reference"] == {"kind": "PL", "number": "1", "year": 2025}
    assert first["nominal_votes"][0]["choice"] == "yes"
    assert first["totals"]["no"] == 0
    assert "CodigoParlamentar" not in json.dumps(first)
    assert "Pessoa Presidente" not in json.dumps(first)


def test_presiding_flag_does_not_invent_or_discard_a_choice():
    vote = normalize_committee_individual_vote({"QualidadeVoto": "N", "VotoPresidente": "true"})
    assert vote["choice"] == "no" and vote["is_presiding"] is True
    unknown = normalize_committee_individual_vote({"QualidadeVoto": "unverified"})
    assert unknown["choice"] is None and unknown["participation_status"] == "unknown"


def test_committee_names_and_dates_are_bounded_before_http():
    with pytest.raises(IngestionError, match="SCOPE"):
        collect_committee_votings(None, "../CCJ", date(2025, 12, 1), date(2025, 12, 1))
    with pytest.raises(IngestionError, match="SCOPE"):
        collect_committee_votings(None, "CCJ", date(2025, 12, 1), date(2026, 1, 1))


def test_collection_uses_compact_dates_and_checks_source_limits():
    requests = []

    def fetch(path, kind):
        requests.append(path)
        return envelope([committee_row(), committee_row(CodigoVotacao="124")]), object()

    acquisition = SimpleNamespace(json_document=fetch)
    with pytest.raises(IngestionError, match="RECORD_LIMIT"):
        collect_committee_votings(
            acquisition, "CCJ", date(2025, 12, 1), date(2025, 12, 31), maximum=1
        )
    assert requests == [
        "votacaoComissao/comissao/CCJ.json?dataInicio=20251201&dataFim=20251231&v=1"
    ]


def test_other_house_or_unresolved_people_are_never_assigned_senate_identity():
    person_id = str(uuid4())
    resolved, missing = resolve_committee_individuals(
        [committee_row()], {"1": (person_id, "a" * 64)}
    )
    assert len(resolved) == 1 and missing == 0
    assert resolved[0]["voting_key"] == "committee:SF:34:123"
    other_house = committee_row(
        Votos={"Voto": {"CodigoParlamentar": "1", "SiglaCasaParlamentar": "CD"}}
    )
    resolved, missing = resolve_committee_individuals([other_house], {"1": (person_id, "a" * 64)})
    assert resolved == [] and missing == 1


def test_schema_change_and_http_failure_propagate_without_coverage():
    with pytest.raises(IngestionError, match="VERSION_CHANGED"):
        committee_voting_rows({"VotacoesComissao": {"Metadados": {"VersaoServico": "2"}}})

    def fetch(*args):
        raise IngestionError("HTTP_ERROR", {"status": 429})

    with pytest.raises(IngestionError, match="HTTP_ERROR"):
        collect_committee_votings(
            SimpleNamespace(json_document=fetch), "CCJ", date(2025, 12, 1), date(2025, 12, 1)
        )
