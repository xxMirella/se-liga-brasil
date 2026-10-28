"""Presidential periods preserve primary-source meaning and reject lifespan headings."""

from datetime import date
from types import SimpleNamespace

import pytest

from crawlers.presidency.archive_parsing import (
    discover_archive_biographies,
    parse_archive_exercises,
)
from crawlers.presidency.camara_mandates import parse_camara_presidential_mandates
from service.ingestion.contracts import IngestionError
from service.presidential_history.biographies import apply_biographical_observation
from service.presidential_history.contemporary_observations import (
    CURRENT_OFFICE_LOCATOR,
    CURRENT_PERSON_LOCATOR,
    enrich_current_presidential_observation,
)
from service.presidential_history.government_classification import classify_documented_government
from service.presidential_history.official_term_parties import (
    apply_official_presidential_term_party,
)
from service.presidential_history.reviewed_exercises import (
    TEMER_LOCATOR,
    TEMER_SOURCE_URL,
    split_temer_interim_exercise,
)


def artifact_for(article_id="123", path=None):
    return SimpleNamespace(
        resource=SimpleNamespace(url="https://presidentes.an.gov.br/index.php/"
                                 "biografias/" + article_id + "-pessoa-historica"),
        sha256="a" * 64, fetched_at="2026-10-23T00:00:00+00:00", path=path,
    )


def parse_exercises(html):
    return parse_archive_exercises(html.encode(), artifact_for(), observed_on=date(2026, 10, 23))


def test_multiple_terms_and_current_term_remain_separate():
    records = parse_exercises("<h1>Pessoa Histórica</h1><h4>1.1.2003 - 1.1.2011<br>1.1.2023</h4>")
    assert len(records) == 2 and records[0]["person_id"] == records[1]["person_id"]
    assert records[0]["ends_before"] == "2011-01-01"
    assert records[1]["ends_before"] is None
    assert records[1]["starts_on"] == "2023-01-01"
    assert records[1]["date_precision"] == "day"
    assert "year_end" not in records[1]


def test_biography_without_exercise_dates_is_not_an_office_holder():
    assert parse_exercises("<h1>Pessoa Eleita</h1><p>Foi eleita, mas não tomou posse.</p>") == []


def test_birth_and_death_heading_is_not_accepted_as_a_presidential_term():
    with pytest.raises(IngestionError, match="LIFESPAN_NOT_EXERCISE"):
        parse_exercises("<h1>Pessoa Histórica</h1><h4>20.9.1897 - 18.7.1967</h4>")


def test_duplicate_periods_and_invalid_dates_are_rejected():
    with pytest.raises(IngestionError, match="DUPLICATE_PERIOD"):
        parse_exercises("<h1>Pessoa Histórica</h1><h4>1.1.2003 - 1.1.2011<br>"
                        "1.1.2003 - 1.1.2011</h4>")
    with pytest.raises(IngestionError, match="DATE_OUT_OF_RANGE"):
        parse_exercises("<h1>Pessoa Histórica</h1><h4>1.1.2030</h4>")


def test_catalog_deduplicates_linked_official_biographies_and_rejects_foreign_links():
    suffix = "/index.php/biografias/123-pessoa-historica"
    html = (f'<a href="{suffix}">Pessoa Histórica</a>'
            f'<a href="{suffix}">Pessoa Histórica</a>'
            f'<a href="https://invasor.example{suffix}">Outra Pessoa</a>')
    pages = discover_archive_biographies(html.encode())
    assert len(pages) == 1 and pages[0][0].startswith("https://presidentes.an.gov.br/")
    with pytest.raises(ValueError):
        discover_archive_biographies(html.encode(), limit=0)


def test_interim_exercise_does_not_preserve_suspended_president_as_actively_serving(tmp_path):
    source = tmp_path / "official.html"
    source.write_text("<p>" + TEMER_LOCATOR + "</p>")
    artifact = artifact_for(path=source)
    acquisition = SimpleNamespace(acquire=lambda url: artifact)
    exercises = [
        {"person_id": "arquivo-nacional-president:201", "starts_on": "2016-08-31",
         "ends_before": "2019-01-01", "evidence": []},
        {"person_id": "arquivo-nacional-president:205", "starts_on": "2011-01-01",
         "ends_before": "2016-08-31", "evidence": []},
    ]
    correction = split_temer_interim_exercise(acquisition, exercises)
    assert correction["evidence"]["url"] == TEMER_SOURCE_URL
    assert exercises[1]["ends_before"] == "2016-05-12"
    assert exercises[1]["official_term_ends_before"] == "2016-08-31"
    assert exercises[2]["exercise_capacity"] == "acting_president"
    assert exercises[2]["ends_before"] == "2016-08-31"


def test_documented_party_intersects_day_precision_exercise_without_retroactive_affiliation():
    record = {"starts_on": "1961-09-07", "ends_before": "1964-03-31",
              "political_party_status": "unknown"}
    observation = {"kind": "party_leadership", "year_start": 1952, "year_end": 1964,
                   "political_party_code": "historical:BR:PTB:1945",
                   "political_party": "Partido Trabalhista Brasileiro",
                   "political_party_abbreviation": "PTB", "evidence": {"url": "fonte"}}
    apply_biographical_observation(record, observation)
    assert record["political_party_year_start"] == 1953
    assert record["political_party_year_end"] == 1963


def test_government_research_classification_is_qualified_and_not_extended_to_later_term():
    first = {"person_id": "arquivo-nacional-president:204", "starts_on": "2003-01-01",
             "ends_before": "2011-01-01", "political_party_status": "unknown"}
    current = {"person_id": "arquivo-nacional-president:204", "starts_on": "2023-01-01",
               "ends_before": None, "observed_through": "2026-10-23",
               "political_party_status": "unknown"}
    classification = ("arquivo-nacional-president:204", 2003, 2010, "PT",
                      "Partido dos Trabalhadores")
    evidence = {"url": "https://educapes.capes.gov.br/fixture", "sha256": "a" * 64}
    classify_documented_government(first, classification, evidence)
    classify_documented_government(current, classification, evidence)
    assert first["political_party_status"] == "verified_government_classification"
    assert first["political_party_context"] == "original_research_government_classification"
    assert first["political_party_year_end"] == 2010
    assert "not_affiliation_certificate" in first["political_party_limitation"]
    assert current["political_party_status"] == "unknown"


def test_official_presidential_party_uses_its_field_not_current_badge_or_vice_presidency():
    payload = (
        "<h1>PESSOA HISTÓRICA PL</h1><h2>Mandatos Externos:</h2><p>"
        "Vice-Presidente da República, Partido: PSB, Período: 2011 a 2016; "
        "Presidente da República, Partido: PT, Período: 2003 a 2011; "
        "Presidente da República, Partido: PT, Período: 2023.</p>"
        "<h2>Atividades Profissionais e Cargos Públicos:</h2>"
    ).encode()
    observations = parse_camara_presidential_mandates(payload, subject="PESSOA HISTÓRICA")
    assert len(observations) == 2
    assert {row["political_party_abbreviation"] for row in observations} == {"PT"}
    assert observations[1]["year_start"] == 2023 and observations[1]["year_end"] is None


def test_official_term_party_open_observation_is_limited_to_observed_current_term():
    record = {"starts_on": "2023-01-01", "ends_before": None,
              "observed_through": "2026-10-23", "political_party_status": "unknown"}
    observation = {"year_start": 2023, "year_end": None, "political_party_abbreviation": "PT"}
    accepted = apply_official_presidential_term_party(
        record, observation, {"url": "official"}, abbreviation="PT", name="Partido de Teste",
    )
    assert accepted is True
    assert record["political_party_year_start"] == 2023
    assert record["political_party_year_end"] == 2026
    assert record["political_party_status"] == "verified_official_presidential_term_party"
    old = {"starts_on": "2003-01-01", "ends_before": "2011-01-01",
           "political_party_status": "unknown"}
    assert apply_official_presidential_term_party(
        old, observation, {}, abbreviation="PT", name="Partido de Teste") is False
    assert old["political_party_status"] == "unknown"


def test_presidential_party_name_change_requires_review_instead_of_using_mutable_label():
    record = {"starts_on": "2016-08-31", "ends_before": "2019-01-01"}
    observation = {"year_start": 2016, "year_end": 2018,
                   "political_party_abbreviation": "MDB"}
    with pytest.raises(IngestionError, match="HISTORICAL_REVIEW"):
        apply_official_presidential_term_party(
            record, observation, {}, abbreviation="PMDB", name="Partido de Teste",
        )


def test_contemporary_party_observation_is_not_attached_to_previous_term(tmp_path):
    source = tmp_path / "contemporary.html"
    source.write_text("<p>" + CURRENT_PERSON_LOCATOR + "</p><p>" + CURRENT_OFFICE_LOCATOR + "</p>")
    artifact = artifact_for(path=source)
    acquisition = SimpleNamespace(acquire=lambda url: artifact)
    old = {"person_id": "arquivo-nacional-president:204", "starts_on": "2003-01-01"}
    current = {"person_id": "arquivo-nacional-president:204", "starts_on": "2023-01-01"}
    records, evidence = enrich_current_presidential_observation(acquisition, [old, current])
    assert evidence["observed_on"] == "2026-10-04"
    assert "political_party_observations" not in records[0]
    assert records[1]["political_party_observations"][0]["observed_on"] == "2026-10-04"
    assert "political_party_observations" not in current
