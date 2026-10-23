"""Plan shared monthly voting jobs only inside independently verified exercises."""

from datetime import date, timedelta

from normalization.periods import month_intervals

HISTORICAL_FLOOR = date(2000, 1, 1)


def historical_voting_partitions(exercises, source, start, end):
    if source not in {"senado", "camara"} or start < HISTORICAL_FLOOR or start > end:
        raise ValueError("Invalid historical voting scope")
    months = set()
    for exercise in exercises:
        if exercise["institution"] != source or exercise["starts_on"] is None:
            continue
        lower = max(start, exercise["starts_on"])
        upper = min(end + timedelta(days=1), exercise["ends_before"] or end + timedelta(days=1))
        if lower < upper:
            months.update(month_intervals(lower, upper))
    # The source resource is shared by all people; daily votes retain their real dates.
    return sorted((lower, upper - timedelta(days=1)) for lower, upper in months)


def enqueue_historical_voting(connection, person_id, source, start, end, requested_on, maximum):
    from database.career_coverage import fetch_career_coverage_inputs
    from database.voting_backfill import enqueue_missing_voting_partitions
    from database.voting_refresh import apply_voting_refresh_schema

    if not person_id or not 1 <= maximum <= 100 or end > requested_on:
        raise ValueError("Person, closed/present dates and bounded job budget are required")
    inputs = fetch_career_coverage_inputs(connection, [person_id])
    partitions = historical_voting_partitions(inputs["exercises"], source, start, end)
    apply_voting_refresh_schema(connection)
    queued = enqueue_missing_voting_partitions(
        connection, source, partitions, requested_on, maximum
    )
    return {
        "source": source,
        "person_id": person_id,
        "verified_exercise_partitions": len(partitions),
        "enqueued": queued,
        "coverage": "planned_verified_exercises_not_collected_history",
        "unverified_institutions": "not_enqueued",
    }
