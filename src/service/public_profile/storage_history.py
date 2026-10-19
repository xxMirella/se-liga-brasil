"""Complete available-date discovery with bounded lazy pages over public daily datasets."""

from datetime import date

from service.daily_voting_dataset.contracts import DailyVotingPartition
from service.dataset_storage.catalog import published_partitions
from service.dataset_storage.read import DatasetReadError
from service.public_profile.contracts import PublicProfileError, VoteQuery
from service.public_profile.history_pagination import (
    create_history_snapshot,
    decode_history_cursor,
    encode_history_cursor,
    history_fingerprint,
)
from service.public_profile.storage_query import query_snapshot
from service.public_profile.storage_votes import (
    fetch_profile_metadata,
    serialize_dataset_vote,
    serialize_exercise_context,
)
from service.public_profile.votes import serialize_exercise, summarize_coverage

DAYS_PER_BATCH = 4
MAX_BATCHES_PER_PAGE = 4


def take_history_batch(catalog, position):
    """Keep same-day sources together so equal dates cannot disappear across pages."""
    days, entries = set(), []
    while position < len(catalog):
        item = catalog[position]
        if len(days) >= DAYS_PER_BATCH and item["occurred_on"] not in days:
            break
        days.add(item["occurred_on"])
        entries.append(item)
        position += 1
    return entries, position


def load_history_batch(reader, entries):
    loaded = []
    for item in entries:
        partition = DailyVotingPartition(item["source"], date.fromisoformat(item["occurred_on"]))
        manifest = reader.current_manifest(partition)
        if manifest is None:
            raise DatasetReadError("DATASET_CATALOG_CHANGED", 410)
        loaded.append({"source": item["source"], "manifest": manifest})
    return loaded


def fetch_history_page(reader, query, snapshot, cursor):
    catalog = snapshot["catalog"]
    position = cursor["position"] if cursor else 0
    if position > len(catalog):
        raise PublicProfileError("INVALID_CURSOR")
    row_cursor = cursor if cursor and cursor["date"] is not None else None
    rows = []
    for _ in range(MAX_BATCHES_PER_PAGE):
        batch, position = take_history_batch(catalog, position)
        if not batch:
            break
        active = {"entries": load_history_batch(reader, batch)}
        rows.extend(query_snapshot(reader, active, query, row_cursor, snapshot["exercise_context"]))
        if len(rows) > query.limit:
            last = rows[query.limit - 1]
            resume = next(
                index
                for index, item in enumerate(catalog)
                if item["occurred_on"] == last["occurred_on"]
            )
            return rows[: query.limit], resume, last, position
        if position == len(catalog):
            return rows, None, None, position
        row_cursor = None
    return rows, position if position < len(catalog) else None, None, position


def get_person_storage_history(
    repository,
    reader,
    person_id,
    *,
    office_kind=None,
    exercise_id=None,
    cursor=None,
    limit=30,
    as_of=None,
):
    query = VoteQuery(
        person_id, date.min, as_of or date.today(), office_kind, exercise_id, cursor, limit
    )
    decoded = decode_history_cursor(query)
    person, exercises, receipts = fetch_profile_metadata(repository, query)
    try:
        with reader.lock:
            if decoded:
                token = decoded["snapshot"]
                snapshot = reader.load_snapshot(token, history_fingerprint(query))
            else:
                catalog = [
                    item
                    for item in published_partitions(reader)
                    if item["occurred_on"] <= query.end_on.isoformat()
                ]
                token, snapshot = create_history_snapshot(
                    reader, query, catalog, serialize_exercise_context(exercises)
                )
            rows, resume, last, inspected = fetch_history_page(reader, query, snapshot, decoded)
    except DatasetReadError as error:
        raise PublicProfileError(error.code, error.status_code) from error
    next_cursor = (
        encode_history_cursor(token, history_fingerprint(query), resume, last)
        if resume is not None
        else None
    )
    return serialize_history_page(
        person,
        exercises,
        receipts,
        query,
        rows,
        snapshot,
        next_cursor,
        inspected,
        resume is not None and last is None,
    )


def serialize_history_page(
    person, exercises, receipts, query, rows, snapshot, next_cursor, inspected, scan_budget_reached
):
    restrict = query.office_kind is not None or query.exercise_id is not None
    coverage = summarize_coverage(
        receipts, exercises if restrict else [], len(receipts) > 200, restrict
    )
    catalog = snapshot["catalog"]
    coverage["datasets"] = {
        "state": "partial" if catalog else "not_published",
        "published_partitions": len(catalog),
        "requested_partitions": len(catalog),
        "generation_pinned": False,
        "catalog_pinned": True,
        "history_range": "available_published_history",
        "inspected_through_partition": inspected,
        "scan_budget_reached": scan_budget_reached,
    }
    return {
        "person": {"person_id": person["person_id"], "display_name": person["display_name"]},
        "period": {
            "starts_on": catalog[-1]["occurred_on"] if catalog else None,
            "ends_on_inclusive": str(query.end_on),
        },
        "exercises": [serialize_exercise(row) for row in exercises[:100]],
        "exercises_truncated": len(exercises) > 100,
        "exercise_link_state": "evidenced" if exercises else "unconfirmed",
        "office_link_basis": "institution_and_evidenced_exercise_interval",
        "items": [serialize_dataset_vote(row) for row in rows],
        "next_cursor": next_cursor,
        "coverage": coverage,
        "empty_state": "no_linked_vote_records" if not rows else None,
    }
