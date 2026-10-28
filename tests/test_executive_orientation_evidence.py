"""Government discourse classifications must not become party-wide labels."""

import hashlib
from pathlib import Path

import pytest

from service.political_dashboard.executive_orientation_evidence import (
    classify_executive_orientation,
    get_executive_orientation_evidence_catalog,
)

EXECUTIVE_ID = "br-presidency-jair-bolsonaro-2019-2022"


@pytest.mark.parametrize("year", [2019, 2020, 2021, 2022])
def test_studied_government_period_is_explicitly_supported(year):
    result = classify_executive_orientation(EXECUTIVE_ID, year)
    assert result["category"] == "far_right"
    assert result["label"] == "Extrema direita"
    assert result["scope"] == "government_discourse"
    assert result["source_publication_year"] == 2025
    assert result["research_corpus_years"] == [2018, 2022]
    assert "political_party" not in result


@pytest.mark.parametrize("identity,year", [(EXECUTIVE_ID, 2018), (EXECUTIVE_ID, 2023),
                                          ("PL", 2020), ("Jair Bolsonaro", 2020)])
def test_evidence_does_not_leak_to_other_periods_or_name_matches(identity, year):
    assert classify_executive_orientation(identity, year)["category"] == "undetermined"


def test_excerpt_provenance_is_honest_and_reproducible():
    record = get_executive_orientation_evidence_catalog()["records"][0]
    root = Path(__file__).resolve().parents[1]
    archived = (root / record["archive_path"]).read_bytes()
    assert hashlib.sha256(archived).hexdigest() == record["sha256"]
    assert record["hash_scope"] == "reviewed_excerpt_utf8_not_original_document"
    assert len(record["literal_quote"].split()) <= 25
    record["category"] = "mutation"
    assert classify_executive_orientation(EXECUTIVE_ID, 2020)["category"] == "far_right"


def test_existing_exercise_identity_matches_without_name_inference():
    result = classify_executive_orientation("arquivo-nacional-president:199:2019-01-01", 2020)
    assert result["category"] == "far_right"


@pytest.mark.parametrize("year,coverage", [(1964, "partial"), (1965, "full"),
                                          (1984, "full"), (1985, "partial")])
def test_regime_preserves_transition_years(year, coverage):
    from service.political_dashboard.executive_orientation_evidence import (
        classify_regime_orientation,
    )
    result = classify_regime_orientation("senado-vcb:16005", year)
    assert result["category"] == "right"
    assert result["year_coverage"] == coverage
    assert result["scope"] == "political_regime"
    assert "political_party" not in result


def test_regime_does_not_extrapolate():
    from service.political_dashboard.executive_orientation_evidence import (
        classify_regime_orientation,
    )
    for year in (1963, 1986, 2020):
        assert classify_regime_orientation("senado-vcb:16005", year)["category"] == "undetermined"


@pytest.mark.parametrize("year", [2003, 2006, 2007, 2010])
def test_lula_first_two_terms_have_qualified_independent_evidence(year):
    result = classify_executive_orientation("arquivo-nacional-president:204:2003-01-01", year)
    assert result["category"] == "left"
    assert result["status"] == "literature_based_editorial_summary"
    assert result["coalition_note"]


def test_lula_third_term_does_not_borrow_first_term_or_future_coverage():
    identity = "arquivo-nacional-president:204:2023-01-01"
    result = classify_executive_orientation(identity, 2023)
    assert result["category"] == "left"
    assert result["research_corpus_years"] == [2023, 2023]
    assert classify_executive_orientation(identity, 2010)["category"] == "undetermined"
    assert classify_executive_orientation(identity, 2027)["category"] == "undetermined"


@pytest.mark.parametrize("year", [2024, 2025, 2026])
def test_lula_editorial_decision_is_distinct_from_academic_year(year):
    result = classify_executive_orientation("arquivo-nacional-president:204:2023-01-01", year)
    assert result["category"] == "left"
    assert result["evidence_kind"] == "editorial_government_classification"
    assert result["status"] == "editorial_mandate_summary"
    assert result["editorial_reference_date"] == "2026-10-27"
    assert result["source_scope"] == "first_six_months_2023"
    assert result["source_publication_year"] == 2023
    assert result["ui_qualifier"]


def test_executive_records_have_no_competing_identity_year():
    observed = set()
    for record in get_executive_orientation_evidence_catalog()["records"]:
        for year in record["valid_years"]:
            key = (record["exercise_id"], year)
            assert key not in observed
            observed.add(key)


def test_dilma_evidence_is_bounded_by_exercise_and_not_transferred_to_temer():
    identity = "arquivo-nacional-president:205:2011-01-01"
    result = classify_executive_orientation(identity, 2016)
    assert result["category"] == "left"
    assert result["status"] == "literature_based_editorial_summary"
    assert result["coverage_start"] == "2016-01-01"
    assert result["coverage_end_exclusive"] == "2016-05-12"
    assert classify_executive_orientation(identity, 2017)["category"] == "undetermined"
    temer = classify_executive_orientation("arquivo-nacional-president:201:2016-05-12", 2016)
    assert temer["category"] == "right"
    assert temer["coverage_start"] == "2016-05-12"
    assert temer["coverage_end_exclusive"] == "2016-08-31"


@pytest.mark.parametrize("year", [2016, 2017, 2018])
def test_temer_definitive_government_does_not_follow_the_party_survey(year):
    identity = "arquivo-nacional-president:201:2016-08-31"
    evidence = classify_executive_orientation(identity, year)
    assert evidence["category"] == "right"
    assert evidence["status"] == "literature_based_editorial_summary"
    assert evidence["coverage_start"] == ("2016-08-31" if year == 2016 else f"{year}-01-01")
    assert evidence["coverage_end_exclusive"] == f"{year + 1}-01-01"
    assert classify_executive_orientation(identity, 2019)["category"] == "undetermined"


def test_all_government_archives_match_the_recorded_hash():
    root = Path(__file__).resolve().parents[1]
    for record in get_executive_orientation_evidence_catalog()["records"]:
        assert hashlib.sha256((root / record["archive_path"]).read_bytes()).hexdigest() == record[
            "sha256"
        ]
