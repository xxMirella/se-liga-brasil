"""Compose public voting pages without source acquisition or private provenance."""

import re

from service.public_profile.contracts import PublicProfileError
from service.public_profile.pagination import decode_vote_cursor, encode_vote_cursor


def serialize_exercise(row):
    return {
        "exercise_id": row["exercise_id"],
        "term_id": row["term_id"],
        "office_kind": row["office_kind"],
        "represented_uf": row.get("represented_uf"),
        "institution": {"code": row["institution_code"], "name": row["institution_name"]},
        "starts_on": row["starts_on"].isoformat(),
        "ends_before": row["ends_before"].isoformat() if row["ends_before"] else None,
        "capacity": row["capacity"],
    }


def serialize_vote(row):
    return {
        "voting_id": row["voting_id"],
        "occurred_on": row["held_on"].isoformat(),
        "occurred_at": row["held_at"].isoformat() if row["held_at"] else None,
        "date_precision": row["date_precision"],
        "month": row["held_on"].strftime("%Y-%m"),
        "institution": {"code": row["institution_code"], "name": row["institution_name"]},
        "proposition": {
            "id": row["proposition_id"],
            "kind": row["proposition_kind"],
            "number": row["proposition_number"],
            "year": row["proposition_year"],
            "title": row["proposition_title"],
        },
        "subject": row["subject"],
        "subject_kind": row["subject_kind"],
        "method": row["method"],
        "stage": row["stage"],
        "round_number": row["round_number"],
        "legislative_body_code": row["legislative_body_code"],
        "nominal_availability": row["nominal_availability"],
        "individual": {
            "participation_status": row["participation_status"],
            "choice": row["choice"],
        },
        "collective_result": row["collective_result"],
    }


def public_coverage_channel(partition_key):
    match = re.fullmatch(r"(?:(plenary|committee)/)?(\d{4}-\d{2})", partition_key)
    if match is None:
        return "unknown", None
    return match.group(1) or "unspecified", match.group(0)


def summarize_coverage(receipts, selected_exercises, truncated, restrict_institutions=False):
    institutions = {row["institution_code"] for row in selected_exercises}
    periods = []
    for row in receipts[:200]:
        if restrict_institutions and row["institution"] not in institutions:
            continue
        channel, partition_key = public_coverage_channel(row["partition_key"])
        verified = all(
            row[field]
            for field in (
                "identity_verified",
                "enumeration_complete",
                "source_period_complete",
                "artifact_verified",
                "scope_verified",
            )
        )
        state = "verified_for_interval" if verified else "partial"
        if row["acquisition_status"] == "unavailable":
            state = "unavailable"
        periods.append(
            {
                "institution": row["institution"],
                "source": row["source"],
                "domain": row["domain"],
                "channel": channel,
                "partition_key": partition_key,
                "starts_on": row["starts_on"].isoformat(),
                "ends_before": row["ends_before"].isoformat(),
                "checked_on": row["checked_on"].isoformat(),
                "state": state,
            }
        )
    return {
        "state": "documented_intervals" if periods else "unknown",
        "intervals": periods,
        "truncated": truncated,
        "absence_of_records_is_inactivity": False,
        "full_career_verified": False,
        "requested_period_state": "not_certified",
    }


def get_person_votes(repository, query):
    cursor = decode_vote_cursor(query)
    with repository.read_snapshot():
        person = repository.fetch_person(query.person_id)
        if person is None:
            raise PublicProfileError("PERSON_NOT_FOUND", 404)
        exercises = repository.fetch_exercises(query)
        if query.exercise_id is not None and not exercises:
            raise PublicProfileError("EXERCISE_NOT_FOUND_IN_PERIOD", 404)
        votes = repository.fetch_votes(query, cursor)
        receipts = repository.fetch_vote_coverage(query)
    visible = votes[: query.limit]
    next_cursor = None
    if len(votes) > query.limit:
        last = visible[-1]
        next_cursor = encode_vote_cursor(query, last["held_on"], last["voting_id"])
    has_office_filter = query.office_kind is not None or query.exercise_id is not None
    coverage_exercises = exercises if has_office_filter else []
    return {
        "person": {"person_id": person["person_id"], "display_name": person["display_name"]},
        "period": {
            "starts_on": query.start_on.isoformat(),
            "ends_on_inclusive": query.end_on.isoformat(),
        },
        "exercises": [serialize_exercise(row) for row in exercises[:100]],
        "exercises_truncated": len(exercises) > 100,
        "office_link_basis": "institution_and_evidenced_exercise_interval",
        "exercise_link_state": "evidenced" if exercises else "unconfirmed",
        "items": [serialize_vote(row) for row in visible],
        "next_cursor": next_cursor,
        "coverage": summarize_coverage(
            receipts, coverage_exercises, len(receipts) > 200, has_office_filter
        ),
        "empty_state": "no_linked_vote_records" if not visible else None,
    }
