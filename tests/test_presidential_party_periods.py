"""Party periods are source-qualified and never alter presidential exercise dates."""

from copy import deepcopy

import pytest

from crawlers.presidency.reviewed_party_periods import REVIEWED_PRESIDENTIAL_PARTY_PERIODS
from crawlers.presidency.reviewed_transcriptions import reviewed_party_transcriptions
from service.ingestion.contracts import IngestionError
from service.political_dashboard_dataset.executive import build_annual_executive_partitions
from service.presidential_history.party_periods import apply_presidential_party_periods


def exercised_president(identifier="199", starts_on="2019-01-01", ends_before="2023-01-01"):
    return {
        "person_id": "arquivo-nacional-president:" + identifier,
        "name": "Presidente da fonte",
        "starts_on": starts_on,
        "ends_before": ends_before,
        "territory_code": "BR",
        "institution_code": "presidency",
        "date_precision": "day",
    }


def reviewed_claims(identifier):
    claims = deepcopy(
        [
            row
            for row in REVIEWED_PRESIDENTIAL_PARTY_PERIODS
            if row["person_id"].endswith(":" + identifier)
        ]
    )
    for claim in claims:
        claim["evidence"] = [{"url": claim["source_url"], "locator": claim["locator"]}]
    return claims


def annual_partition(exercise, year):
    from datetime import date

    return build_annual_executive_partitions([exercise], year, date(2026, 10, 23))[0]


def test_bolsonaro_preserves_two_changes_and_unknown_november_boundary():
    original = exercised_president()
    enriched = apply_presidential_party_periods([original], reviewed_claims("199"))[0]
    assert "political_party_periods" not in original
    year_2019 = annual_partition(enriched, 2019)
    periods = year_2019["segments"][0]["political_party_periods"]
    assert [(row["political_party"], row["starts_on"], row["ends_before"]) for row in periods] == [
        ("PSL", "2019-01-01", "2019-11-01"),
        ("Sem partido", "2019-12-01", "2020-01-01"),
    ]
    assert year_2019["segments"][0]["starts_on"] == "2019-01-01"
    year_2021 = annual_partition(enriched, 2021)
    assert [
        row["political_party"] for row in year_2021["segments"][0]["political_party_periods"]
    ] == ["Sem partido", "PL"]
    assert annual_partition(enriched, 2020)["current"]["political_party"] == "Sem partido"
    assert annual_partition(enriched, 2022)["current"]["political_party"] == "PL"


def test_temer_historical_name_change_is_preserved_inside_2018():
    original = exercised_president("201", "2016-08-31", "2019-01-01")
    claims = [row for row in reviewed_claims("201") if row["exercise_starts_on"] == "2016-08-31"]
    enriched = apply_presidential_party_periods([original], claims)[0]
    assert annual_partition(enriched, 2017)["current"]["political_party"] == "PMDB"
    periods = annual_partition(enriched, 2018)["segments"][0]["political_party_periods"]
    assert [(row["political_party"], row["starts_on"]) for row in periods] == [
        ("PMDB", "2018-01-01"),
        ("MDB", "2018-05-15"),
    ]


def test_ai2_legal_extinction_does_not_attribute_castelo_party_or_entire_year():
    original = exercised_president("196", "1964-04-15", "1967-03-15")
    enriched = apply_presidential_party_periods([original], reviewed_claims("196"))[0]
    periods = annual_partition(enriched, 1965)["segments"][0]["political_party_periods"]
    assert [(row["political_party"], row["starts_on"], row["ends_before"]) for row in periods] == [
        ("Partidos extintos", "1965-10-27", "1965-11-22"),
    ]
    assert periods[0]["political_party_context"] == (
        "legal_party_extinction_not_personal_affiliation"
    )
    assert "political_party_periods" not in annual_partition(enriched, 1966)["current"]


def test_claim_cannot_attach_to_another_president_or_another_exercise():
    original = exercised_president("204", "2023-01-01", "2027-01-01")
    with pytest.raises(IngestionError, match="EXERCISE_NOT_FOUND"):
        apply_presidential_party_periods([original], reviewed_claims("199"))
    assert "political_party_periods" not in original


def test_overlapping_party_periods_are_rejected_before_publication():
    claims = reviewed_claims("199")
    claims[1]["starts_on"] = "2019-10-01"
    with pytest.raises(IngestionError, match="OVERLAP"):
        apply_presidential_party_periods([exercised_president()], claims)


def test_transcription_hash_never_claims_to_hash_original_official_document():
    reviewed = reviewed_party_transcriptions()["pmdb_mdb_name_change"]
    assert reviewed["sha256_scope"] == "reviewed_transcription"
    assert reviewed["original_document_sha256"] is None
    assert "sha256" not in reviewed
    assert len(reviewed["reviewed_transcription_sha256"]) == 64


def test_estado_novo_legal_prohibition_is_not_a_personal_affiliation():
    exercise = exercised_president("179", "1930-11-03", "1945-10-29")
    claims = [row for row in reviewed_claims("179") if row["exercise_starts_on"] == "1930-11-03"]
    enriched = apply_presidential_party_periods([exercise], claims)[0]
    assert annual_partition(enriched, 1930)["current"]["political_party_status"] == "unknown"
    current = annual_partition(enriched, 1938)["current"]
    assert current["political_party"] == "Partidos proibidos"
    assert current["political_party_context"] == "legal_party_prohibition_not_personal_affiliation"


@pytest.mark.parametrize("identifier,start,end,year", [
    ("212", "1889-11-15", "1891-11-23", 1889),
    ("213", "1891-11-23", "1894-11-15", 1892),
])
def test_first_republic_documented_non_affiliation_is_visible(identifier, start, end, year):
    exercise = exercised_president(identifier, start, end)
    enriched = apply_presidential_party_periods([exercise], reviewed_claims(identifier))[0]
    segment = annual_partition(enriched, year)["segments"][0]
    assert segment["political_party"] == "Sem partido"
    assert segment["political_party_status"] == "verified_government_classification"
    assert segment["political_party_context"] == "original_research_government_classification"
    assert segment["political_party_periods"][0]["evidence"][0]["url"].endswith(
        "2021_RodrigoLentz.pdf")


def test_party_prohibition_stops_at_documented_repeal_instead_of_covering_all_1945():
    exercise = exercised_president("179", "1930-11-03", "1945-10-29")
    claims = [row for row in reviewed_claims("179") if row["exercise_starts_on"] == "1930-11-03"]
    enriched = apply_presidential_party_periods([exercise], claims)[0]
    periods = annual_partition(enriched, 1945)["segments"][0]["political_party_periods"]
    assert periods[0]["starts_on"] == "1945-01-01"
    assert periods[0]["ends_before"] == "1945-05-28"
    legal = next(row for row in claims if row["political_party"] == "Partidos proibidos")
    assert len(legal["supporting_sources"][0]["locators"]) == 3


@pytest.mark.parametrize("year", range(1931, 1937))
def test_vargas_academic_annual_classification_preserves_precision_and_evidence(year):
    exercise = exercised_president("179", "1930-11-03", "1945-10-29")
    claims = [row for row in reviewed_claims("179") if row["exercise_starts_on"] == "1930-11-03"]
    enriched = apply_presidential_party_periods([exercise], claims)[0]
    current = annual_partition(enriched, year)["current"]
    assert current["political_party"] == "Sem partido"
    assert current["political_party_status"] == "verified_government_classification"
    period = current["political_party_periods"][0]
    assert period["date_precision"] == "year"
    assert period["starts_on"] == f"{year}-01-01"
    assert period["ends_before"] == f"{year+1}-01-01"
    assert period["evidence"][0]["url"].startswith("https://files.ufgd.edu.br/")
    assert "not_personal_affiliation_event_dates" in period["political_party_limitation"]


def test_academic_transcription_does_not_hash_publisher_maintenance_as_original_pdf():
    from crawlers.presidency.reviewed_transcriptions import VARGAS_UNESP_SOURCE_URL

    evidence = reviewed_party_transcriptions()[VARGAS_UNESP_SOURCE_URL]["evidence"]
    assert evidence["original_document_sha256"] is None
    assert evidence["source_type"] == "reviewed_academic_article_transcription"
    assert evidence["sha256_scope"] == "reviewed_transcription"
    assert "maintenance" in evidence["acquisition_limitation"]


def test_government_support_context_does_not_create_personal_party_affiliation(monkeypatch):
    from service.presidential_history import government_context

    monkeypatch.setattr(
        government_context, "acquire_claim_source",
        lambda *_: ({"url": "https://official.example/context"},
                    government_context.SUPPORT_LOCATOR),
    )
    exercise = exercised_president("196", "1964-04-15", "1967-03-15")
    enriched = government_context.enrich_documented_government_context(
        object(), [exercise], {},
    )[0]
    annual = annual_partition(enriched, 1966)
    assert annual["current"]["political_party_status"] == "unknown"
    assert annual["current"]["political_party"] == "Filiação histórica não verificada"
    context = annual["government_context_observations"][0]
    assert context["date"] == "1966-03-24"
    assert context["relationship"] == "government_support_organization_not_personal_affiliation"
    assert "filiação pessoal" in context["summary"]
    assert annual_partition(enriched, 1965)["government_context_observations"] == []
    assert "government_context_observations" not in exercise


def test_anachronistic_source_rows_are_not_silently_imported():
    assert all(row["political_party"] != "PL" for row in reviewed_claims("213"))
    assert all(row["political_party"] == "PRM" for row in reviewed_claims("206"))
    assert all(row["person_id"] != "arquivo-nacional-president:217"
               for row in REVIEWED_PRESIDENTIAL_PARTY_PERIODS)


def test_figueiredo_party_government_classification_keeps_annual_precision():
    exercise = exercised_president("193", "1979-03-15", "1985-03-15")
    enriched = apply_presidential_party_periods([exercise], reviewed_claims("193"))[0]
    first = annual_partition(enriched, 1979)["segments"][0]
    assert first["political_party"] == "ARENA"
    later = annual_partition(enriched, 1980)["current"]
    assert later["political_party"] == "PDS"
    assert later["political_party_periods"][0]["date_precision"] == "year"
    assert "not_personal_affiliation_event_dates" in later["political_party_limitation"]
    assert annual_partition(enriched, 1984)["current"]["political_party"] == "PDS"


def test_interim_capacity_requires_exact_reviewed_identity_and_source(monkeypatch):
    from service.presidential_history import exercise_capacity

    verified = {"url": "https://official.example/source", "locator": "interinamente"}
    monkeypatch.setattr(exercise_capacity, "acquire_reviewed_exercise_source",
                        lambda *_: (None, verified))
    mazzilli = exercised_president("184", "1964-04-02", "1964-04-15")
    mazzilli["exercise_capacity"] = "president"
    short_unrelated = exercised_president("999", "1964-04-02", "1964-04-15")
    short_unrelated["exercise_capacity"] = "president"
    rows = exercise_capacity.enrich_documented_exercise_capacity(
        object(), [mazzilli, short_unrelated],
    )
    assert rows[0]["exercise_capacity"] == "acting_president"
    assert rows[1]["exercise_capacity"] == "president"
    assert mazzilli["exercise_capacity"] == "president"
    segment = annual_partition(rows[0], 1964)["segments"][0]
    assert segment["exercise_capacity_evidence"] == [verified]
