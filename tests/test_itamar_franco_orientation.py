"""Itamar Franco's government is documented as contested, never inferred from party or FHC."""

import pytest

from service.political_dashboard.executive_orientation_evidence import (
    classify_executive_orientation,
    get_executive_orientation_evidence_catalog,
)
from service.political_dashboard.orientation_timeline import executive_orientation_cell

COLLOR = "arquivo-nacional-president:200:1990-03-15"
ITAMAR = "arquivo-nacional-president:203:1992-10-02"
FHC = "arquivo-nacional-president:197:1995-01-01"


def presidency(*identities):
    return {"institution_code": "presidency", "segments": [
        {"exercise_id": identity} for identity in identities]}


@pytest.mark.parametrize("year,start,end", [
    (1992, "1992-10-02", "1993-01-01"),
    (1993, "1993-01-01", "1994-01-01"),
    (1994, "1994-01-01", "1995-01-01"),
])
def test_each_itamar_year_is_controversial_and_clipped_to_exercise(year, start, end):
    result = classify_executive_orientation(ITAMAR, year)
    assert result["category"] == "controversial"
    assert result["label"] == "Classificação controversa"
    assert (result["coverage_start"], result["coverage_end_exclusive"]) == (start, end)
    assert "political_party" not in result


@pytest.mark.parametrize("year", [1991, 1995, 1996])
def test_itamar_evidence_does_not_leak_outside_exercise(year):
    assert classify_executive_orientation(ITAMAR, year)["category"] == "undetermined"


def test_itamar_is_not_forced_to_right_and_keeps_counterpoints():
    record = classify_executive_orientation(ITAMAR, 1993)
    assert record["category"] != "right"
    assert "centro-direita" not in record["source_terminology"]
    assert record["formal_mandate_end"] == "1994-12-31"
    kinds = " ".join(source["source_title"] for source in record["supporting_sources"])
    assert "neoliberalismo" in kinds and "Plano Real" in kinds
    assert "filiação" in " ".join(record["limitations"])


def test_1992_keeps_collor_right_then_itamar_controversial():
    cell = executive_orientation_cell(presidency(COLLOR, ITAMAR), 1992)
    assert cell["label"] == "Classificação controversa / Direita"
    assert [(row["executive_name"], row["coverage_start"], row["coverage_end_exclusive"])
            for row in cell["source_evidence"]] == [
        ("Fernando Collor", "1992-01-01", "1992-10-02"),
        ("Itamar Franco", "1992-10-02", "1993-01-01"),
    ]


@pytest.mark.parametrize("year", [1993, 1994])
def test_full_itamar_years_show_single_documented_classification(year):
    cell = executive_orientation_cell(presidency(ITAMAR), year)
    assert cell["label"] == "Classificação controversa"
    assert "Itamar Franco" in cell["detail"]
    assert "PRN" not in cell["label"] and "PMDB" not in cell["label"]


def test_1995_boundary_hands_over_to_fhc_without_itamar():
    institution = presidency(FHC)
    institution["segments"].insert(0, {
        "exercise_id": ITAMAR, "starts_on": "1992-10-02", "ends_before": "1995-01-01"})
    cell = executive_orientation_cell(institution, 1995)
    assert cell["label"] == "Direita"
    assert all(row["executive_name"] != "Itamar Franco" for row in cell["source_evidence"])
    assert classify_executive_orientation(FHC, 1994)["category"] == "undetermined"
    assert classify_executive_orientation(ITAMAR, 1995)["category"] == "undetermined"


def test_itamar_exercise_is_unique_in_catalog():
    records = [r for r in get_executive_orientation_evidence_catalog()["records"]
               if r["exercise_id"] == ITAMAR]
    assert len(records) == 1
