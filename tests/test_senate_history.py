"""Historical composition must never use current affiliation or unelected substitutes."""

import pytest

from crawlers.senado.historical_parsing import (
    annual_senate_observations,
    parse_affiliations,
    parse_exercises,
    parse_legislature_roster,
)
from service.political_dashboard.page import render_historical_roster
from service.senate_history.collection import (
    associate_verified_senators,
    build_senate_history_partitions,
)
from service.senate_history.rosters import attach_historical_rosters

EVIDENCE = {"url": "https://legis.senado.leg.br/dadosabertos/senador/1/filiacoes.json",
            "sha256": "a" * 64, "fetched_at": "2026-10-23T00:00:00+00:00"}


def source_person(exercises=None):
    mandate = {
        "CodigoMandato": "42", "UfParlamentar": "RJ", "DescricaoParticipacao": "Titular",
        "PrimeiraLegislaturaDoMandato": {"DataFim": "2003-01-31"},
    }
    if exercises is not None:
        mandate["Exercicios"] = {"Exercicio": exercises}
    return {"ListaParlamentarLegislatura": {"Parlamentares": {"Parlamentar": {
        "IdentificacaoParlamentar": {"CodigoParlamentar": "1", "NomeParlamentar": "Nome",
                                     "SiglaPartidoParlamentar": "ATUAL"},
        "Mandatos": {"Mandato": mandate},
    }}}}


def exercise():
    return parse_exercises(source_person({
        "CodigoExercicio": "10", "DataInicio": "1999-02-01", "DataFim": "2003-01-31",
    }), EVIDENCE)[0]


def affiliation(start, end=None, code="1", abbreviation="HIST"):
    return {"starts_on": start, "ends_on": end, "code": code,
            "abbreviation": abbreviation, "evidence": EVIDENCE}


def test_substitutes_without_exercise_are_not_occupants():
    assert parse_exercises(source_person(), EVIDENCE) == []


def test_current_affiliation_is_not_backfilled_to_historical_year():
    rows = annual_senate_observations([exercise()], {"1": [affiliation("2020-01-01")]}, 2000)
    assert rows[0]["observation"]["politicalPartyAbbreviation"] is None


def test_inclusive_source_end_and_party_change_use_exact_reference():
    affiliations = {"1": [affiliation("1999-01-01", "2000-12-31"),
                           affiliation("2001-01-01", code="2", abbreviation="NOVO")]}
    assert annual_senate_observations([exercise()], affiliations, 2000)[0][
        "observation"]["politicalPartyAbbreviation"] == "HIST"
    assert annual_senate_observations([exercise()], affiliations, 2001)[0][
        "observation"]["politicalPartyAbbreviation"] == "NOVO"
    assert annual_senate_observations([exercise()], affiliations, 2003) == []


def test_overlapping_distinct_affiliations_are_not_arbitrarily_chosen():
    rows = annual_senate_observations([exercise()], {"1": [
        affiliation("1999-01-01"), affiliation("2000-01-01", code="2")
    ]}, 2000)
    assert rows[0]["observation"]["politicalPartyCode"] is None


def test_affiliation_payload_cannot_be_associated_to_another_person():
    with pytest.raises(ValueError, match="PERSON_MISMATCH"):
        parse_affiliations({"FiliacaoParlamentar": {"Parlamentar": {"Codigo": "2"}}},
                           "1", EVIDENCE)


def test_annual_publication_preserves_evidence_and_source_identity():
    partitions = build_senate_history_partitions(
        [exercise()], {"1": [affiliation("1999-01-01")]}, 2000, 2000,
    )
    national = next(row for row in partitions if row["territory_code"] == "BR")
    assert national["total"] == 1
    assert national["reference_on"] == "2000-12-31"
    assert national["members"][0]["person_id"] == "senado:1"
    assert national["evidence"] == [EVIDENCE]
    assert national["political_parties"][0]["abbreviation"] == "HIST"


def test_missing_exercise_end_is_bounded_by_documented_mandate():
    rows = parse_exercises(source_person({
        "CodigoExercicio": "10", "DataInicio": "1999-02-01",
    }), EVIDENCE)
    assert rows[0]["ends_on"] == "2003-01-31"
    assert annual_senate_observations(rows, {}, 2003) == []


def test_old_legislature_roll_is_not_transformed_into_simultaneous_seats():
    payload = source_person()
    mandate = payload["ListaParlamentarLegislatura"]["Parlamentares"]["Parlamentar"][
        "Mandatos"]["Mandato"]
    mandate["PrimeiraLegislaturaDoMandato"] = {
        "NumeroLegislatura": "21", "DataInicio": "1890-11-15", "DataFim": "1891-02-24",
    }
    rosters = parse_legislature_roster(payload, 21, EVIDENCE)
    partitions = attach_historical_rosters([], rosters, 1889, 1891)
    national = next(row for row in partitions if row["territory_code"] == "BR")
    assert national["total"] is None
    assert national["political_parties"] == []
    assert national["historical_roster"][0]["name"] == "Nome"
    assert "ATUAL" not in str(partitions)
    html = render_historical_roster(national)
    assert "não confirma que todos exerceram simultaneamente" in html
    assert 'target="_blank"' in html


def test_verified_source_bridge_is_required_for_canonical_profile_link():
    partitions = build_senate_history_partitions([exercise()], {}, 2000, 2000)
    assert associate_verified_senators(partitions, {"2": "unrelated"}) == 0
    assert partitions[0]["members"][0]["person_id"] == "senado:1"
    assert associate_verified_senators(partitions, {"1": "canonical-verified"}) == 1
    assert partitions[0]["members"][0]["person_id"] == "canonical-verified"


def test_historical_roster_republication_does_not_inflate_observation_count():
    rosters = [{"source_person_id": "1", "name": "Nome", "uf": "RJ", "legislature": 21,
                "period_start": "1890-11-15", "period_end": "1891-02-24",
                "official_url": EVIDENCE["url"], "evidence": EVIDENCE}]
    partitions = attach_historical_rosters([], rosters, 1890, 1890)
    republished = attach_historical_rosters(partitions, rosters, 1890, 1890)
    assert all(row["source_observation_count"] == 1 for row in republished)


@pytest.mark.parametrize("code,current_name,historical_name", [
    ("33", "MDB", "PMDB"), ("41", "CIDADANIA", "PPS"), ("578", "AVANTE", "PTdoB"),
])
def test_mutable_source_party_names_do_not_rename_the_year_2000(
    code, current_name, historical_name,
):
    partitions = build_senate_history_partitions([exercise()], {"1": [
        affiliation("1999-01-01", code=code, abbreviation=current_name),
    ]}, 2000, 2000)
    assert partitions[0]["political_parties"][0]["abbreviation"] == historical_name
    assert any(row.get("source_kind") == "reviewed_official_table"
               for row in partitions[0]["evidence"])


def test_1965_mdb_is_not_confused_with_modern_party_of_same_name():
    from crawlers.senado.historical_party_names import historical_senate_political_party

    name, evidence = historical_senate_political_party(
        {"code": "240", "abbreviation": "MDB"}, "1969-12-31",
    )
    assert name == "MDB"
    assert evidence is None
