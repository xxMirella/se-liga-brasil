"""Cached recursive Storage metadata discovery; never probe absent historical days."""

import json
import re
from datetime import date

from service.dataset_storage.read import MANIFEST_TTL_SECONDS, DatasetReadError, read_cache_json

CATALOG_PAGE_SIZE = 1000
MAX_CATALOG_PAGES = 100
CATALOG_MEMORY_TTL_SECONDS = 900  # in-process; the disk copy keeps the shorter manifest TTL
PARTITION_PATH = re.compile(
    r"legislative/(camara|senado)/person_voting_timeline/"
    r"year=(\d{4})/month=(\d{2})/day=(\d{2})/manifest\.json"
)


def parse_published_partition(name):
    match = PARTITION_PATH.fullmatch(name)
    if match is None:
        return None
    source, year, month, day = match.groups()
    try:
        occurred_on = date(int(year), int(month), int(day))
    except ValueError as error:
        raise DatasetReadError("DATASET_CATALOG_INVALID") from error
    return {"source": source, "occurred_on": occurred_on.isoformat()}


def list_catalog_page(reader, cursor):
    body = {"prefix": "legislative/", "limit": CATALOG_PAGE_SIZE, "with_delimiter": False}
    if cursor is not None:
        body["cursor"] = cursor
    response = reader.storage.request(
        "POST", "object/list-v2/" + reader.storage.configuration.bucket, json=body
    )
    if response.status_code >= 400:
        raise DatasetReadError("DATASET_CATALOG_UNAVAILABLE")
    if len(response.content) > 2 * 1024 * 1024:
        raise DatasetReadError("DATASET_CATALOG_PAGE_TOO_LARGE")
    try:
        payload = response.json()
        if not isinstance(payload["objects"], list) or type(payload["hasNext"]) is not bool:
            raise ValueError("Invalid catalog page")
        if len(payload["objects"]) > CATALOG_PAGE_SIZE:
            raise ValueError("Catalog page exceeded limit")
        return payload
    except (ValueError, KeyError, TypeError) as error:
        raise DatasetReadError("DATASET_CATALOG_INVALID") from error


def catalog_version(reader):
    """Cheap fingerprint of the in-memory catalog; None while it is not loaded (no I/O)."""
    memo = getattr(reader, "catalog_memo", None)
    if memo is None or memo[0] <= reader.clock():
        return None
    return memo[2]


def published_partitions(reader):
    """Process-wide memo over the disk/Storage catalog; failures are never memoized."""
    lock = getattr(reader, "catalog_lock", None)
    if lock is None:
        return load_published_partitions(reader)
    with lock:  # one lister at a time: concurrent cold requests share the result
        memo = reader.catalog_memo
        if memo is not None and memo[0] > reader.clock():
            return memo[1]
        partitions = load_published_partitions(reader)
        newest = partitions[0]["occurred_on"] if partitions else ""
        version = f"{len(partitions)}:{newest}"
        reader.catalog_memo = (reader.clock() + CATALOG_MEMORY_TTL_SECONDS, partitions, version)
        return partitions


def load_published_partitions(reader):
    path = reader.directory / "published-history.catalog.json"
    if path.exists():
        cached = read_cache_json(path)
        if reader.clock() - cached["checked_at"] < MANIFEST_TTL_SECONDS:
            return cached["partitions"]
    cursor, seen, partitions = None, set(), {}
    for _ in range(MAX_CATALOG_PAGES):
        payload = list_catalog_page(reader, cursor)
        index_catalog_objects(partitions, payload["objects"])
        if not payload["hasNext"]:
            ordered = [partitions[key] for key in sorted(partitions, reverse=True)]
            reader.save_bytes(
                path, json.dumps({"checked_at": reader.clock(), "partitions": ordered}).encode()
            )
            return ordered
        cursor = payload.get("nextCursor")
        if not isinstance(cursor, str) or not cursor or cursor in seen:
            raise DatasetReadError("DATASET_CATALOG_INVALID")
        seen.add(cursor)
    raise DatasetReadError("DATASET_CATALOG_BUDGET_EXCEEDED")


def index_catalog_objects(partitions, objects):
    for item in objects:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            raise DatasetReadError("DATASET_CATALOG_INVALID")
        partition = parse_published_partition(item["name"])
        if partition is not None:
            partitions[(partition["occurred_on"], partition["source"])] = partition
