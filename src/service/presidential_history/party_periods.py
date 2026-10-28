"""Qualified party periods preserve changes within one presidential exercise."""

from copy import deepcopy
from datetime import date

from service.ingestion.contracts import IngestionError


def apply_presidential_party_periods(exercises, claims):
    """Join reviewed claims by provider identity and exercise start, never by name."""
    indexed = {}
    for claim in claims:
        indexed.setdefault((claim["person_id"], claim["exercise_starts_on"]), []).append(claim)
    exercise_keys = {(row["person_id"], row["starts_on"]) for row in exercises}
    if indexed.keys() - exercise_keys:
        raise IngestionError("PRESIDENTIAL_PARTY_EXERCISE_NOT_FOUND")
    enriched = deepcopy(exercises)
    for exercise in enriched:
        claims_for_exercise = indexed.get((exercise["person_id"], exercise["starts_on"]), [])
        if claims_for_exercise:
            periods = sorted(claims_for_exercise, key=lambda item: item["starts_on"])
            validate_presidential_party_periods(exercise, periods)
            exercise["political_party_periods"] = periods
    return enriched


def validate_presidential_party_periods(exercise, periods):
    previous_end = None
    exercise_end = exercise.get("ends_before")
    for period in periods:
        start, end = period["starts_on"], period["ends_before"]
        date.fromisoformat(start)
        date.fromisoformat(end)
        if start >= end or start < exercise["starts_on"]:
            raise IngestionError("PRESIDENTIAL_PARTY_PERIOD_OUTSIDE_EXERCISE")
        if exercise_end and end > exercise_end:
            raise IngestionError("PRESIDENTIAL_PARTY_PERIOD_OUTSIDE_EXERCISE")
        if previous_end and start < previous_end:
            raise IngestionError("PRESIDENTIAL_PARTY_PERIOD_OVERLAP")
        if not period.get("evidence") or not period["political_party_status"].startswith(
            "verified_"
        ):
            raise IngestionError("PRESIDENTIAL_PARTY_PERIOD_EVIDENCE_REQUIRED")
        previous_end = end
