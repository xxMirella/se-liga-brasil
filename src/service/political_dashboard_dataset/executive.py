"""Annual executive exercise records retain changes and precision without invented dates."""

from collections import defaultdict
from datetime import date

from service.political_dashboard_dataset.aggregation import SCHEMA_VERSION
from service.political_dashboard_dataset.executive_party_periods import (
    annual_executive_party_periods,
    party_at_annual_reference,
)


def interval_overlaps_year(exercise, year):
    start = str(exercise.get("exercise_start") or exercise.get("starts_on") or "")
    if exercise.get("date_precision") == "day" and start:
        return dated_interval_overlaps_year(exercise, start, year)
    return annual_interval_overlaps_year(exercise, start, year)


def dated_interval_overlaps_year(exercise, start, year):
    end = exercise.get("ends_before")
    if end:
        return start <= f"{year}-12-31" and end > f"{year}-01-01"
    observed_through = exercise.get("observed_through") or start
    return int(start[:4]) <= year <= int(observed_through[:4])


def annual_interval_overlaps_year(exercise, start, year):
    start_year = exercise.get("year_start") or (int(start[:4]) if start else None)
    if start_year is None:
        raise ValueError("EXECUTIVE_EXERCISE_START_REQUIRED")
    end_year = exercise.get("year_end")
    if end_year is None:
        ends_before = exercise.get("ends_before")
        if ends_before and str(ends_before) <= f"{year}-01-01":
            return False
        end_year = int(str(ends_before or exercise.get("observed_through") or start_year)[:4])
    return start_year <= year <= end_year


def executive_segment(exercise, year):
    return {
        "exercise_id": exercise.get("exercise_id"),
        "source_observed_on": exercise.get("source_observed_on"),
        "observation_kind": exercise.get("observation_kind"),
        "name": exercise.get("person_display_name") or exercise.get("name"),
        "person_id": exercise.get("person_id"),
        "exercise_capacity": exercise.get("exercise_capacity"),
        "exercise_capacity_evidence": exercise.get("exercise_capacity_evidence", []),
        "government_context_observations": [
            row for row in exercise.get("government_context_observations", [])
            if row["year"] == year
        ],
        "official_term_ends_before": exercise.get("official_term_ends_before"),
        "original_source_name": exercise.get("original_source_name"),
        "display_name_evidence": exercise.get("display_name_evidence", []),
        **historical_political_party(exercise, year),
        "starts_on": exercise.get("exercise_start") or exercise.get("starts_on"),
        "ends_before": exercise.get("ends_before"),
        "observed_through": exercise.get("observed_through")
        or (
            None
            if exercise.get("ends_before")
            else (exercise.get("exercise_start") or exercise.get("starts_on"))
        ),
        "date_precision": exercise.get("date_precision", "year"),
        "year_start": exercise.get("year_start"),
        "year_end": exercise.get("year_end"),
        "official_url": exercise.get("source_url"),
        "evidence": exercise.get("evidence", []),
    }


def build_annual_executive_partitions(exercises, year, as_of):
    grouped = defaultdict(list)
    for exercise in exercises:
        validate_executive_territory(exercise)
        if interval_overlaps_year(exercise, year):
            key = exercise["territory_code"], exercise["institution_code"]
            grouped[key].append(executive_segment(exercise, year))
    return [
        executive_partition(territory, institution, segments, year, as_of)
        for (territory, institution), segments in sorted(grouped.items())
    ]


def executive_partition(territory, institution, segments, year, as_of):
    reference = min(date(year, 12, 31), as_of)
    active = [
        segment
        for segment in segments
        if segment["date_precision"] == "day"
        and str(segment["starts_on"]) <= str(reference)
        and (not segment["ends_before"] or str(segment["ends_before"]) > str(reference))
        and (
            segment["ends_before"]
            or not segment["observed_through"]
            or str(segment["observed_through"]) >= str(reference)
        )
    ]
    current = active[0] if len(active) == 1 else None
    return {
        "schema_version": SCHEMA_VERSION,
        "year": year,
        "territory_code": territory,
        "institution_code": institution,
        "coverage": "observed_partial",
        "aggregation_basis": "documented_exercises_overlapping_year",
        "snapshot_on": str(reference) if current else None,
        "date_precision": "day" if current else "year",
        "total": len(active) or None,
        "current": current,
        "segments": segments,
        "government_context_observations": [
            observation for segment in segments
            for observation in segment.get("government_context_observations", [])
        ],
        "political_parties": [],
        "members": [],
        "distinct_people_observed_during_year": [],
    }


def historical_political_party(exercise, year):
    periods = annual_executive_party_periods(exercise, year)
    if periods:
        return party_at_annual_reference(periods)
    start = exercise.get("political_party_year_start", 1889)
    end = exercise.get("political_party_year_end", 9999)
    status = exercise.get("political_party_status") or "unknown"
    verified = start <= year <= end and status.startswith("verified_")
    return {
        "political_party": (
            exercise.get("political_party_abbreviation") or exercise.get("political_party")
        )
        if verified
        else "Filiação histórica não verificada",
        "political_party_code": exercise.get("political_party_code") if verified else None,
        "political_party_status": exercise.get("political_party_status") if verified else "unknown",
        "political_party_evidence": exercise.get("political_party_evidence", [])
        if verified
        else [],
        "political_party_observations": exercise.get("political_party_observations", []),
        "political_party_context": exercise.get("political_party_context"),
        "political_party_limitation": exercise.get("political_party_limitation"),
    }


def documented_exercise_year_bounds(evidence):
    starts, ends = [], []
    for exercise in evidence["exercises"]:
        start = exercise.get("year_start") or int(
            str(exercise.get("exercise_start") or exercise.get("starts_on"))[:4]
        )
        end = exercise.get("year_end") or int(
            str(exercise.get("ends_before") or exercise.get("observed_through") or start)[:4]
        )
        starts.append(start)
        ends.append(end)
    return evidence.get("year_start", min(starts)), evidence.get("year_end", max(ends))


def validate_executive_territory(exercise):
    institution = exercise["institution_code"]
    territory = exercise["territory_code"]
    if (institution == "state_government" and territory == "DF") or (
        institution == "district_government" and territory != "DF"
    ):
        raise ValueError("EXECUTIVE_TERRITORY_INSTITUTION_MISMATCH")
