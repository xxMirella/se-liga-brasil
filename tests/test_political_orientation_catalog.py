"""Dated ideology estimates must not relabel historical parties or missing affiliation."""

import pytest

from service.political_dashboard.political_orientation_catalog import (
    classify_orientation_observations,
    classify_political_orientation,
    orientation_index,
    score_category,
)


def test_survey_years_have_original_scores_and_reproducible_source_information():
    result = classify_political_orientation("PT", 2018)
    assert result["category"] == "left" and result["reference_year"] == 2018
    assert result["score"] == pytest.approx(2.97420635)
    assert result["respondents"] == 504
    assert result["source_url"] == "https://doi.org/10.7910/DVN/MFIXKW"
    assert classify_political_orientation("PL", 2022)["category"] == "right"
    assert len(orientation_index()) == 67


@pytest.mark.parametrize("year", [1880, 1945, 2017, 2019, 2021, 2023, 2026])
def test_no_backfill_or_forward_fill_of_modern_survey_years(year):
    result = classify_political_orientation("PSD", year)
    assert result["category"] == "undetermined"
    assert result["status"] == "no_dated_classification"
    assert result["reference_year"] is None


@pytest.mark.parametrize("label", ["S/Partido", "Sem Partido", "sem filiação partidária"])
def test_explicit_non_affiliation_never_becomes_center(label):
    result = classify_political_orientation(label, 2016)
    assert result["category"] == "unaffiliated" and result["score"] is None


@pytest.mark.parametrize("label", [None, "", "Filiação não informada", "Partidos proibidos"])
def test_absence_of_a_party_is_not_treated_as_verified_non_affiliation(label):
    assert classify_political_orientation(label, 2018)["category"] == "undetermined"


def test_renames_and_mergers_do_not_inherit_classification_without_dated_mapping():
    assert classify_political_orientation("PR", 2018)["status"] == "classified"
    assert classify_political_orientation("PL", 2018)["status"] == "no_dated_classification"
    assert classify_political_orientation("UNIÃO", 2022)["status"] == "classified"
    assert classify_political_orientation("DEM", 2022)["status"] == "no_dated_classification"


@pytest.mark.parametrize(("score", "expected"), [
    (0, "left"), (4.49, "left"), (4.5, "center"), (5.5, "center"), (5.51, "right"), (10, "right"),
])
def test_product_thresholds_are_explicit_at_boundaries(score, expected):
    assert score_category(score) == expected


@pytest.mark.parametrize("score", [-1, 11, float("nan"), float("inf"), True])
def test_invalid_source_scale_is_rejected(score):
    with pytest.raises(ValueError, match="OUTSIDE_SCALE"):
        score_category(score)


def test_incompatible_dated_source_results_are_preserved_as_controversial():
    result = classify_orientation_observations([
        {"score": 3.0, "source_url": "https://example.org/a"},
        {"score": 8.0, "source_url": "https://example.org/b"},
    ])
    assert result["category"] == "controversial"
    assert result["status"] == "conflicting_sources"
    assert len(result["sources"]) == 2
