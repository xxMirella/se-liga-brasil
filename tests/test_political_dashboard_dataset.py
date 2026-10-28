"""Annual aggregation never retroactively assigns present-day affiliations."""

from datetime import date

import pytest

from service.political_dashboard_dataset.aggregation import build_annual_partitions
from service.political_dashboard_dataset.executive import build_annual_executive_partitions
from service.political_dashboard_dataset.storage import encode_partition, store_partition


def observation(person="p1", institution="senado", observed_on="2026-03-01", **values):
    return {
        "person_id": person,
        "display_name": person,
        "institution_code": institution,
        "observed_on": date.fromisoformat(observed_on),
        "observation": {
            "observedOn": observed_on,
            "inExercise": True,
            "representedUf": "SP",
            "politicalPartyCode": "11",
            "politicalPartyAbbreviation": "AA",
            **values,
        },
    }


def brazil_partition(rows, year=2026):
    return next(
        partition
        for partition in build_annual_partitions(rows, year)
        if partition["territory_code"] == "BR"
    )


def test_year_is_grain_and_missing_year_is_not_backfilled():
    assert build_annual_partitions([observation()], 2025) == []
    assert brazil_partition([observation()])["year"] == 2026


def test_midyear_political_party_change_preserves_both_annual_participations():
    rows = [
        observation(),
        observation(
            observed_on="2026-08-01", politicalPartyCode="22", politicalPartyAbbreviation="BB"
        ),
    ]
    partition = brazil_partition(rows)
    assert partition["political_parties"][0]["abbreviation"] == "BB"
    assert (
        sum(item["distinct_people"] for item in partition["distinct_people_observed_during_year"])
        == 2
    )
    assert partition["total"] == 1


def test_different_observation_dates_do_not_claim_simultaneous_seats():
    partition = brazil_partition([observation(), observation("p2", observed_on="2026-04-01")])
    assert partition["snapshot_on"] is None
    assert partition["seat_count"] is None
    assert partition["coverage"] == "observed_partial"


def test_same_person_in_different_institutions_is_not_merged():
    partitions = build_annual_partitions([observation(), observation(institution="camara")], 2026)
    assert len(partitions) == 4
    assert {item["institution_code"] for item in partitions} == {"senado", "camara"}


def test_latest_explicit_non_exercise_excludes_current_observation_only():
    partition = brazil_partition(
        [observation(), observation(observed_on="2026-06-01", inExercise=False)]
    )
    assert partition["total"] == 0
    assert partition["distinct_people_observed_during_year"][0]["distinct_people"] == 1


def test_district_has_no_municipalities():
    with pytest.raises(ValueError, match="DISTRICT_HAS_NO_MUNICIPALITIES"):
        build_annual_partitions([observation(representedUf="DF", municipalityIbge="5300108")], 2026)


def test_unreported_affiliation_is_counted_without_fabrication():
    partition = brazil_partition(
        [observation(politicalPartyCode=None, politicalPartyAbbreviation=None)]
    )
    assert partition["political_parties"][0]["political_party_code"] == "unreported"
    assert partition["total"] == 1


def test_immutable_payload_is_deterministic_and_hard_bounded(tmp_path):
    partition = brazil_partition([observation()])
    first = store_partition(tmp_path, partition)
    assert first == store_partition(tmp_path, partition)
    assert (tmp_path / first["file"]).stat().st_size == first["bytes"]
    with pytest.raises(ValueError, match="PAYLOAD_BUDGET"):
        encode_partition({"oversized": "x" * 262144})


def executive(start, end=None, precision="day", name="A"):
    return {
        "territory_code": "BR",
        "institution_code": "presidency",
        "person_display_name": name,
        "exercise_start": start,
        "ends_before": end,
        "date_precision": precision,
        "source_url": "https://example.test/official",
    }


def test_executive_changes_in_year_preserved_without_assigning_unknown_party():
    records = [
        executive("2000-01-01", "2000-06-01"),
        {**executive("2000-06-01", name="B"), "observed_through": "2000-12-31"},
    ]
    partition = build_annual_executive_partitions(records, 2000, date(2026, 10, 22))[0]
    assert len(partition["segments"]) == 2
    assert partition["current"]["name"] == "B"
    assert partition["current"]["political_party_code"] is None


def test_annual_only_exercise_does_not_invent_day_snapshot():
    partition = build_annual_executive_partitions(
        [executive("1890", "1891", "year")], 1890, date(2026, 10, 22)
    )[0]
    assert partition["snapshot_on"] is None
    assert partition["current"] is None


def test_closed_open_exercise_ending_january_first_not_in_next_year():
    assert (
        build_annual_executive_partitions(
            [executive("2000-01-01", "2001-01-01")], 2001, date(2026, 10, 22)
        )
        == []
    )


def test_municipality_code_must_belong_to_selected_state():
    from service.political_dashboard.contracts import DashboardQuery
    from service.political_dashboard_dataset.query import validate_municipality_catalog
    from service.public_profile import PublicProfileError

    query = DashboardQuery("RJ", date(2026, 10, 22), level="municipal", municipality_ibge="3550308")
    with pytest.raises(PublicProfileError, match="INVALID_DASHBOARD_MUNICIPALITY"):
        validate_municipality_catalog(
            query,
            {"municipalities": [{"ibge_code": "3304557", "name": "Cidade Fictícia", "uf": "RJ"}]},
        )


def test_territorial_catalog_is_partitioned_by_uf_not_historically_backfilled():
    from service.political_dashboard_dataset.territories import build_territorial_catalogs

    catalog = {
        "states": [{"uf": "DF"}, {"uf": "SP"}],
        "municipalities": [{"ibge_code": "3550308", "name": "Cidade Fictícia", "uf": "SP"}],
        "observed_at": "2026-10-23T00:00:00Z",
        "temporal_scope": "current_inventory_only",
        "evidence": [],
    }
    partitions = build_territorial_catalogs(catalog)
    assert partitions[0]["municipalities"] == []
    assert partitions[1]["municipalities"][0]["uf"] == "SP"
    assert partitions[1]["temporal_scope"] == "current_inventory_only"


def test_historical_affiliation_is_limited_to_its_verified_year_interval():
    record = {
        **executive("1900", "1903", "year"),
        "political_party": "Partido Fictício",
        "political_party_code": "historical:test",
        "political_party_year_start": 1901,
        "political_party_year_end": 1901,
        "political_party_status": "verified_interval",
    }
    before = build_annual_executive_partitions([record], 1900, date(2026, 10, 23))[0]
    during = build_annual_executive_partitions([record], 1901, date(2026, 10, 23))[0]
    assert before["segments"][0]["political_party_code"] is None
    assert during["segments"][0]["political_party"] == "Partido Fictício"


def test_yearly_public_json_uses_existing_gzip_etag_and_revalidation_contract():
    from application.public_cache import prepare_public_response

    payload = b'{"year":2026,"data":"' + b"x" * 2000 + b'"}'
    status, compressed, headers = prepare_public_response(
        "/api/political-dashboard?year=2026", 200, payload, {"Accept-Encoding": "gzip"}
    )
    assert status == 200 and len(compressed) < len(payload)
    assert headers["Content-Encoding"] == "gzip"
    assert "s-maxage=300" in headers["Cache-Control"]
    assert (
        prepare_public_response(
            "/api/political-dashboard?year=2026",
            200,
            payload,
            {"Accept-Encoding": "gzip", "If-None-Match": headers["ETag"]},
        )[0]
        == 304
    )
    assert prepare_public_response("/api/political-dashboard", 503, payload, {})[2] == {
        "Cache-Control": "no-store"
    }


def test_legislative_source_with_only_year_never_invents_a_date_or_seat_snapshot():
    annual_row = {**observation(), "observed_on": None, "date_precision": "year", "year": 1900}
    partition = brazil_partition([annual_row], 1900)
    assert partition["date_precision"] == "year"
    assert partition["snapshot_on"] is None and partition["observed_on"] is None
    assert partition["seat_count"] is None
    assert partition["expected_seats"] is None  # Today's capacity is not projected into 1900.
    assert partition["distinct_people_observed_during_year"][0]["distinct_people"] == 1


def test_open_exercise_is_not_propagated_beyond_last_documented_observation():
    record = {**executive("2011-01-01"), "observed_through": "2012-09-21"}
    assert build_annual_executive_partitions([record], 2026, date(2026, 10, 23)) == []
    partition = build_annual_executive_partitions([record], 2012, date(2026, 10, 23))[0]
    assert partition["current"] is None
    assert partition["segments"][0]["observed_through"] == "2012-09-21"


def test_point_inauguration_without_current_evidence_does_not_create_full_year_occupancy():
    record = executive("2023-01-01")
    assert build_annual_executive_partitions([record], 2024, date(2026, 10, 23)) == []
    partition = build_annual_executive_partitions([record], 2023, date(2026, 10, 23))[0]
    assert partition["current"] is None


def test_selecting_old_year_keeps_navigation_to_later_documented_years():
    from service.political_dashboard.contracts import DashboardQuery
    from service.political_dashboard_dataset.query import annual_dashboard_payload

    selected = DashboardQuery("SP", date(1890, 12, 31))
    history = [{"year": 2026, "territory_code": "BR", "institution_code": "senado", "total": 81}]
    payload = annual_dashboard_payload([], history, selected, current_year=2026)
    assert payload["year"] == 1890
    assert payload["history"][-1]["year"] == 2026
    assert payload["history"][-1]["documented_records"] == 81
    assert payload["history"][0]["year"] == 1826


def test_state_timeline_keeps_visible_senate_separate_from_government_coverage():
    from service.political_dashboard.contracts import DashboardQuery
    from service.political_dashboard_dataset.query import annual_history

    query = DashboardQuery("AC", date(2000, 12, 31), level="state")
    rows = [{"year": 2000, "territory_code": "AC", "institution_code": "senado", "total": 3}]
    history = annual_history(rows, query, current_year=2026)
    selected = next(row for row in history if row["year"] == 2000)
    assert selected["documented_records"] == 3
    assert selected["senate_observations"] == 3
    assert selected["government_observations"] == 0


def test_district_government_is_visible_without_inventing_state_or_municipal_offices():
    from service.political_dashboard.contracts import DashboardQuery
    from service.political_dashboard_dataset.query import annual_dashboard_payload

    query = DashboardQuery("DF", date(2023, 12, 31), level="state")
    partition = {
        "payload": {
            "year": 2023,
            "territory_code": "DF",
            "institution_code": "district_government",
            "segments": [],
            "coverage": "observed_partial",
        }
    }
    payload = annual_dashboard_payload([partition], [], query, current_year=2026)
    assert payload["government"]["institution_code"] == "district_government"


def test_history_preserves_compact_institution_party_ties_without_members():
    from service.political_dashboard.contracts import DashboardQuery
    from service.political_dashboard_dataset.query import annual_history

    query = DashboardQuery("SP", date(2000, 12, 31), level="state")
    composition = {
        "institution_code": "senado",
        "territory_code": "SP",
        "political_parties": [{"abbreviation": "A", "count": 1}, {"abbreviation": "B", "count": 1}],
        "total": 2,
        "snapshot_on": "2000-12-31",
    }
    rows = [
        {
            "year": 2000,
            "territory_code": "SP",
            "institution_code": "senado",
            "total": 2,
            "composition": composition,
        }
    ]
    selected = next(row for row in annual_history(rows, query, 2026) if row["year"] == 2000)
    assert selected["institutions"] == [composition]
    assert selected["government_observations"] == 0


def test_national_dated_observations_preserve_rich_executive_intervals_idempotently():
    from service.political_dashboard_dataset.executive_observations import (
        merge_executive_observations,
    )

    rich = {
        "year": 2023,
        "current": {"name": "Titular", "political_party": None},
        "segments": [{"name": "Titular", "starts_on": "2023-01-01"}],
        "total": 1,
    }
    incoming = {
        "segments": [
            {"name": "Titular", "source_observed_on": "2023-02-01", "political_party": "ABC"}
        ]
    }
    merged = merge_executive_observations(rich, incoming)
    assert merged["current"] == rich["current"]
    assert merged["segments"] == rich["segments"]
    assert merged["total"] == 1
    assert merged["national_observations"] == incoming["segments"]
    assert merge_executive_observations(merged, incoming) == merged
    assert "national_observations" not in rich


def test_national_observation_republication_does_not_duplicate_native_points():
    from service.political_dashboard_dataset.executive_observations import (
        merge_executive_observations,
    )

    point = {"name": "Pessoa", "source_observed_on": "2023-01-01", "date_precision": "year"}
    existing = {"segments": [point], "current": None, "national_observations": [point]}
    incoming = {"segments": [point], "current": None}
    merged = merge_executive_observations(existing, incoming)
    assert merged["segments"] == [point]
    assert "national_observations" not in merged
    assert merge_executive_observations(merged, incoming) == merged
