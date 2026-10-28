"""Missing annual evidence cannot be promoted into historical institutional absence."""

from service.coverage_audit.annual import (
    annual_scope_coverage,
    evidence_status,
    partition_metrics,
)


def test_rosters_and_suspension_are_distinguished_from_complete_annual_caucuses():
    assert evidence_status({"coverage": "legislature_roster_only"}) == (
        "legislature_roster_not_annual_caucus"
    )
    assert evidence_status({"institutional_status": "suspended_whole_year"}) == (
        "institutionally_not_applicable"
    )


def test_current_municipality_catalog_does_not_generate_false_historical_occupancy():
    catalog = {"municipalities": [{"ibge_code": "1234567", "uf": "SP"}]}
    scopes, extra = annual_scope_coverage([], catalog, 1880, 1882)
    municipal = [row for row in scopes if row["territory_code"] == "1234567"]
    assert len(municipal) == 2 and not extra
    assert all(row["published_years"] == 0 for row in municipal)
    assert all(row["absent_year_ranges"] == [[1880, 1882]] for row in municipal)


def test_official_no_affiliation_is_not_counted_as_missing_political_party():
    metrics = partition_metrics(
        {
            "members": [{"person_id": "senado:5236", "political_party": "S/Partido"}],
            "segments": [],
            "total": 1,
        },
        set(),
    )
    assert metrics["records_without_political_party"] == 0
    assert metrics["canonical_profile_links"] == 0


def test_a_full_sized_historical_cohort_does_not_prove_complete_annual_composition():
    for basis in [
        "verified_year_end_status_of_current_roster_cohort",
        "verified_year_end_status_of_historical_legislature_rosters",
    ]:
        assert (
            evidence_status(
                {
                    "total": 513,
                    "named_records": 513,
                    "expected_seats": 513,
                    "coverage": "observed_complete",
                    "aggregation_basis": basis,
                }
            )
            == "partial_historical_legislature_cohort"
        )


def test_verified_current_roster_is_preserved_as_current_documented_composition():
    assert (
        evidence_status(
            {
                "total": 513,
                "coverage": "verified_current_roster",
                "aggregation_basis": "verified_current_roster_with_personal_identity",
            }
        )
        == "complete_at_documented_snapshot"
    )
