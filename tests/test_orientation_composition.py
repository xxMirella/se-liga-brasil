"""Cards aggregate every party in its dated category without inventing session attendance."""

from service.political_dashboard.orientation_composition import orientation_composition


def composition():
    return {
        "total": 30,
        "coverage": "observed_partial",
        "snapshot_on": "2022-12-31",
        "political_parties": [
            {"abbreviation": "PT", "count": 10},
            {"abbreviation": "PL", "count": 8},
            {"abbreviation": "PP", "count": 8},
            {"abbreviation": "Não informado", "count": 3},
            {"abbreviation": "S/Partido", "count": 1},
        ],
    }


def test_categories_sum_all_parties_not_just_largest_party():
    original = composition()
    result = orientation_composition(original, 2022)
    counts = {g["orientation_category"]: g["count"] for g in result["political_parties"]}
    assert counts == {"left": 10, "right": 16, "undetermined": 3, "unaffiliated": 1}
    assert sum(counts.values()) == result["total"] == 30
    assert result["coverage"] == "observed_partial"
    assert result["snapshot_on"] == "2022-12-31"
    assert original["political_parties"][0]["abbreviation"] == "PT"


def test_2026_does_not_inherit_2022_and_preserves_explicit_unaffiliated():
    result = orientation_composition(composition(), 2026)
    assert {g["orientation_category"]: g["count"] for g in result["political_parties"]} == {
        "undetermined": 29,
        "unaffiliated": 1,
    }


def test_unreported_remainder_is_not_silently_lost():
    result = orientation_composition(
        {"total": 5, "political_parties": [{"abbreviation": "PT", "count": 2}]}, 2022
    )
    assert {g["orientation_category"]: g["count"] for g in result["political_parties"]} == {
        "left": 2,
        "undetermined": 3,
    }


def test_unreconciled_affiliation_is_not_promoted_from_a_display_label():
    data = {
        "total": 3,
        "political_parties": [
            {"abbreviation": "PT", "political_party_code": "unreconciled", "count": 2},
            {"abbreviation": "S/Partido", "political_party_code": "unknown", "count": 1},
        ],
    }
    assert {
        g["orientation_category"]: g["count"]
        for g in orientation_composition(data, 2022)["political_parties"]
    } == {
        "undetermined": 2,
        "unaffiliated": 1,
    }


def test_controversial_category_remains_separate_and_ties_are_named(monkeypatch):
    from service.political_dashboard import orientation_composition as module

    categories = {"A": "left", "B": "right", "C": "controversial", "D": "center"}
    monkeypatch.setattr(
        module,
        "classify_political_orientation",
        lambda label, year: {"category": categories[label]},
    )
    data = {
        "total": 8,
        "political_parties": [
            {"abbreviation": name, "count": count}
            for name, count in [("A", 3), ("B", 3), ("C", 1), ("D", 1)]
        ],
    }
    result = module.orientation_composition(data, 2022)
    assert {g["orientation_category"]: g["count"] for g in result["political_parties"]} == {
        "left": 3,
        "right": 3,
        "controversial": 1,
        "center": 1,
    }
    assert result["total"] == 8
