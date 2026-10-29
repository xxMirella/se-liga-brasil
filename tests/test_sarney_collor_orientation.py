"""Government interpretations must respect exercise dates and historical disagreements."""

from service.political_dashboard.executive_orientation_evidence import (
    classify_executive_orientation,
)
from service.political_dashboard.orientation_timeline import executive_orientation_cell

SARNEY = "arquivo-nacional-president:198:1985-03-15"
COLLOR = "arquivo-nacional-president:200:1990-03-15"
ITAMAR = "arquivo-nacional-president:203:1992-10-02"


def presidency(*identities):
    return {"institution_code": "presidency", "segments": [
        {"exercise_id": identity} for identity in identities]}


def test_collor_exercise_starts_at_possession_and_ends_before_itamar():
    assert classify_executive_orientation(COLLOR, 1989)["category"] == "undetermined"
    initial = classify_executive_orientation(COLLOR, 1990)
    final = classify_executive_orientation(COLLOR, 1992)
    assert initial["category"] == final["category"] == "right"
    assert initial["coverage_start"] == "1990-03-15"
    assert final["coverage_end_exclusive"] == "1992-10-02"
    assert final["formal_mandate_end"] == "1992-12-29"
    assert classify_executive_orientation(COLLOR, 1993)["category"] == "undetermined"


def test_sarney_preserves_early_disagreement_and_later_right_synthesis():
    for year in (1985, 1986):
        assert classify_executive_orientation(SARNEY, year)["category"] == "controversial"
    for year in (1987, 1988, 1989, 1990):
        result = classify_executive_orientation(SARNEY, year)
        assert result["category"] == "right"
        assert result["orientation_change_date_precision"] == "year"
    assert classify_executive_orientation(SARNEY, 1984)["category"] == "undetermined"
    assert classify_executive_orientation(SARNEY, 1991)["category"] == "undetermined"
    assert classify_executive_orientation(SARNEY, 1990)["coverage_end_exclusive"] == "1990-03-15"


def test_military_regime_does_not_hide_sarney_civil_government_in_1985():
    cell = executive_orientation_cell(presidency(SARNEY), 1985)
    assert "transição de regime e governo" in cell["label"]
    assert "Classificação controversa" in cell["label"]
    assert "José Sarney" in cell["detail"]
    assert "1985-03-15" in cell["detail"]
    assert cell["source_evidence"][0]["coverage_end_exclusive"] == "1985-03-15"
    assert cell["source_evidence"][1]["coverage_start"] == "1985-03-15"


def test_1990_keeps_both_governments_and_1992_keeps_itamar_distinct():
    cell = executive_orientation_cell(presidency(SARNEY, COLLOR), 1990)
    assert "José Sarney" in cell["detail"] and "Fernando Collor" in cell["detail"]
    assert {r["coverage_end_exclusive"] for r in cell["source_evidence"]} == {
        "1990-03-15", "1991-01-01"}
    cell = executive_orientation_cell(presidency(COLLOR, ITAMAR), 1992)
    assert any(r["executive_name"] == "Fernando Collor"
               and r["coverage_end_exclusive"] == "1992-10-02"
               for r in cell["source_evidence"])
    assert "PRN" not in cell["label"]
