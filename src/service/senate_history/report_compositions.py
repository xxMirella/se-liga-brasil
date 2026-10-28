"""Keep aggregate source snapshots distinct from earlier person-level reconstructions."""

from copy import deepcopy

from service.political_dashboard_dataset.aggregation import build_annual_partition

DATED_REPORT_BASIS = "verified_dated_official_senate_composition"


def merge_dated_report_composition(existing, composition):
    year, reference = composition["year"], composition["reference_on"]
    if not 1995 <= year <= 2025 or sum(
        row["count"] for row in composition["political_parties"]
    ) != composition["total"] or composition["total"] != 81:
        raise ValueError("SENATE_REPORT_AGGREGATE_COMPOSITION_NOT_VALIDATED")
    partition = deepcopy(existing or build_annual_partition([], year, "BR", "senado"))
    if partition["year"] != year or partition["territory_code"] != "BR":
        raise ValueError("SENATE_REPORT_COMPOSITION_PARTITION_MISMATCH")
    if partition.get("aggregation_basis") != DATED_REPORT_BASIS:
        partition["dated_exercise_snapshot"] = {
            key: partition.get(key) for key in (
                "reference_on", "snapshot_on", "total", "coverage", "aggregation_basis",
                "members", "political_parties", "evidence", "seat_count",
                "observed_on", "observed_from", "source_observation_count",
                "distinct_people_observed_during_year",
            )
        }
    partition.update({
        "reference_on": reference, "snapshot_on": reference,
        "observed_on": reference, "observed_from": reference, "date_precision": "day",
        "seat_count": composition["total"], "distinct_people_observed_during_year": [],
        "total": composition["total"], "observed_people_count": composition["total"],
        "expected_seats": 81, "coverage": "observed_complete",
        "aggregation_basis": DATED_REPORT_BASIS, "office_kinds": ["senator"],
        "political_parties": composition["political_parties"], "members": [],
        "evidence": [composition["evidence"]],
        "source_observation_count": len(composition["political_parties"]),
        "official_composition_is_aggregate": True,
        "coverage_detail": "Composição das bancadas integralmente documentada na data indicada; "
                           "não comprova filiação contínua durante todo o ano.",
    })
    partition.pop("first_observation_on", None)
    partition.pop("last_observation_on", None)
    return partition


def attach_dated_report_compositions(partitions, compositions):
    indexed = {(row["year"], row["territory_code"]): row for row in partitions}
    for composition in compositions:
        key = composition["year"], "BR"
        indexed[key] = merge_dated_report_composition(indexed.get(key), composition)
    return [indexed[key] for key in sorted(indexed)]
