"""Public voting pages compose SQL identity metadata with daily Storage datasets."""

from service.dataset_storage.read import DatasetReadError
from service.public_profile.contracts import PublicProfileError
from service.public_profile.pagination import filter_fingerprint
from service.public_profile.storage_pagination import decode_storage_cursor, encode_storage_cursor
from service.public_profile.storage_query import daily_partitions, query_snapshot
from service.public_profile.votes import serialize_exercise, summarize_coverage

INSTITUTION_NAMES = {"camara": "Câmara dos Deputados", "senado": "Senado Federal"}


def serialize_dataset_vote(row):
    return {
        "voting_id": row["voting_id"],
        "occurred_on": row["occurred_on"],
        "occurred_at": None,
        "date_precision": row["date_precision"],
        "month": row["occurred_on"][:7],
        "institution": {
            "code": row["institution_code"],
            "name": INSTITUTION_NAMES[row["institution_code"]],
        },
        "proposition": {
            "id": None,
            "kind": row["matter_kind"],
            "number": row["matter_number"],
            "year": row["matter_year"],
            "title": row["matter_name"],
        },
        "subject": row["voting_subject"],
        "subject_kind": "unknown",
        "method": "unknown",
        "stage": "unknown",
        "round_number": row["round_number"],
        "legislative_body_code": None,
        "nominal_availability": "unknown",
        "individual": {
            "participation_status": row["participation_status"],
            "choice": row["vote_choice"],
        },
        "collective_result": "unknown",
        "short_description": row["short_description"],
        "description_kind": row["description_kind"],
        "description_state": row["description_state"],
        "official_url": row["official_url"],
        "official_url_state": row["official_url_state"],
    }


def fetch_profile_metadata(repository, query):
    with repository.read_snapshot():
        person = repository.fetch_person(query.person_id)
        if person is None:
            raise PublicProfileError("PERSON_NOT_FOUND", 404)
        exercises = repository.fetch_exercises(query)
        if query.exercise_id is not None and not exercises:
            raise PublicProfileError("EXERCISE_NOT_FOUND_IN_PERIOD", 404)
        receipts = repository.fetch_vote_coverage(query)
    return person, exercises, receipts


def fetch_dataset_page(reader, query, exercises):
    partitions = daily_partitions(query)
    cursor = decode_storage_cursor(query)
    fingerprint = filter_fingerprint(query)
    try:
        with reader.lock:
            if cursor:
                token = cursor["snapshot"]
                snapshot = reader.load_snapshot(token, fingerprint)
            else:
                token, snapshot = reader.create_snapshot(
                    partitions, fingerprint, serialize_exercise_context(exercises)
                )
            rows = query_snapshot(reader, snapshot, query, cursor, snapshot["exercise_context"])
    except DatasetReadError as error:
        raise PublicProfileError(error.code, error.status_code) from error
    return rows, token, snapshot


def get_person_storage_votes(repository, reader, query):
    daily_partitions(query)
    decode_storage_cursor(query)
    person, exercises, receipts = fetch_profile_metadata(repository, query)
    rows, token, snapshot = fetch_dataset_page(reader, query, exercises)
    visible = rows[: query.limit]
    next_cursor = (
        encode_storage_cursor(query, token, visible[-1]) if len(rows) > query.limit else None
    )
    restrict = query.office_kind is not None or query.exercise_id is not None
    coverage = summarize_coverage(
        receipts, exercises if restrict else [], len(receipts) > 200, restrict
    )
    coverage["datasets"] = {
        "state": "partial" if snapshot["entries"] else "not_published",
        "published_partitions": len(snapshot["entries"]),
        "requested_partitions": len(daily_partitions(query)),
        "generation_pinned": True,
    }
    return {
        "person": {"person_id": person["person_id"], "display_name": person["display_name"]},
        "period": {"starts_on": str(query.start_on), "ends_on_inclusive": str(query.end_on)},
        "exercises": [serialize_exercise(row) for row in exercises[:100]],
        "exercises_truncated": len(exercises) > 100,
        "exercise_link_state": "evidenced" if exercises else "unconfirmed",
        "office_link_basis": "institution_and_evidenced_exercise_interval",
        "items": [serialize_dataset_vote(row) for row in visible],
        "next_cursor": next_cursor,
        "coverage": coverage,
        "empty_state": "no_linked_vote_records" if not visible else None,
    }


def serialize_exercise_context(exercises):
    return [
        {
            "institution_code": row["institution_code"],
            "starts_on": str(row["starts_on"]),
            "ends_before": str(row["ends_before"]) if row["ends_before"] else None,
        }
        for row in exercises[:100]
    ]
