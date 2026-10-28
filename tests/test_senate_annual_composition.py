"""Aggregate reports require a common explicit date and all 81 recorded seats."""

from copy import deepcopy

import pytest

from crawlers.senado.annual_composition import parse_final_senate_composition
from service.senate_history.report_compositions import merge_dated_report_composition

SOURCE = {"url": "https://www25.senado.leg.br/documents/report", "sha256": "a" * 64}
TEXT = '''B.4 - COMPOSIÇÃO FINAL DAS BANCADAS DOS PARTIDOS E DOS BLOCOS
PARTIDO TRABALHISTA BRASILEIRO - PTB
Em 22/12/2010: 6 integrantes
PARTIDO DEMOCRÁTICO TRABALHISTA - PDT
Em 22/12/2010: 6 integrantes
PARTIDO SOCIAL CRISTÃO - PSC
Em 22/12/2010: 1 integrante
PARTIDO VERDE - PV
Em 22/12/2010: 1 integrante
PARTIDO SOCIALISMO E LIBERDADE - PSOL
Em 22/12/2010: 1 integrante
BLOCO PARLAMENTAR DA MINORIA
Em 22/12/2010: 29 integrantes (DEM: 15 e PSDB: 14)
BLOCO PARLAMENTAR DE APOIO AO GOVERNO
Em 22/12/2010: 17 integrantes (PT: 8; PR: 4; PSB: 2; PRB: 2 e PCdoB: 1)
BLOCO PARLAMENTAR DA MAIORIA
Em 22/12/2010: 19 integrantes (PMDB: 18 e PP: 1)
Sem partido
Em 22/12/2010: 1 integrante
B.5 - SITUAÇÃO JURÍDICA DOS PARTIDOS POLÍTICOS'''


def test_final_composition_uses_dated_complete_counts_and_real_party_not_bloc():
    result = parse_final_senate_composition(TEXT, 2010, SOURCE)
    counts = {row["abbreviation"]: row["count"] for row in result["political_parties"]}
    assert result["reference_on"] == "2010-12-22" and result["total"] == 81
    assert counts["PSC"] == 1 and counts["PV"] == 1 and counts["PMDB"] == 18
    assert counts["DEM"] == 15 and counts["PSDB"] == 14
    assert not any("BLOCO" in key for key in counts)


def test_mixed_dates_in_final_table_are_rejected_instead_of_assuming_typo():
    with pytest.raises(ValueError, match="REFERENCE_DATES_DISAGREE"):
        parse_final_senate_composition(TEXT.replace("Em 22/12/2010: 6", "Em 02/02/2010: 6", 1),
                                      2010, SOURCE)


def test_missing_group_or_wrong_bloc_sum_cannot_be_called_complete():
    with pytest.raises(ValueError, match="TOTAL_NOT_VERIFIED"):
        malformed = TEXT.replace("6 integrantes", "5 integrantes", 1)
        parse_final_senate_composition(malformed, 2010, SOURCE)
    with pytest.raises(ValueError, match="BLOC_COMPONENT_SUM_MISMATCH"):
        parse_final_senate_composition(TEXT.replace("DEM: 15", "DEM: 16"), 2010, SOURCE)


def test_merge_preserves_previous_person_snapshot_and_elections_without_fabricated_people():
    composition = parse_final_senate_composition(TEXT, 2010, SOURCE)
    previous = {"year": 2010, "territory_code": "BR", "institution_code": "senado",
                "total": 79, "seat_count": 79, "reference_on": "2010-12-31",
                "observed_on": "2010-12-31", "observed_from": "2010-12-31",
                "coverage": "observed_partial",
                "members": [{"person_id": "senado:known"}], "political_parties": [],
                "election_observations": [{"source_event_id": "documented"}]}
    copy = deepcopy(previous)
    merged = merge_dated_report_composition(previous, composition)
    assert merged["reference_on"] == "2010-12-22" and merged["total"] == 81
    assert merged["coverage"] == "observed_complete" and merged["members"] == []
    assert merged["observed_on"] == merged["observed_from"] == "2010-12-22"
    assert merged["seat_count"] == 81
    assert merged["dated_exercise_snapshot"]["seat_count"] == 79
    assert merged["dated_exercise_snapshot"]["members"] == previous["members"]
    assert merged["election_observations"] == previous["election_observations"]
    assert previous == copy
    assert merge_dated_report_composition(merged, composition) == merged


def test_current_year_snapshot_cannot_be_replaced_by_historical_report():
    composition = parse_final_senate_composition(TEXT, 2010, SOURCE)
    with pytest.raises(ValueError, match="NOT_VALIDATED"):
        merge_dated_report_composition(None, {**composition, "year": 2026})
