"""Daily dataset cursors bind filters and an immutable cached generation snapshot."""

import base64
import json
import re
from datetime import date

from service.analytical_datasets.contracts import validate_voting_key
from service.public_profile.contracts import PublicProfileError
from service.public_profile.pagination import filter_fingerprint


def decode_storage_cursor(query):
    if query.cursor is None:
        return None
    try:
        if not isinstance(query.cursor, str) or len(query.cursor) > 1024:
            raise ValueError("Invalid cursor")
        payload = json.loads(
            base64.b64decode(
                query.cursor + "=" * (-len(query.cursor) % 4), altchars=b"-_", validate=True
            )
        )
        if set(payload) != {"v", "filters", "snapshot", "date", "id"}:
            raise ValueError("Invalid fields")
        if payload["v"] != 2 or payload["filters"] != filter_fingerprint(query):
            raise ValueError("Different filters")
        if not re.fullmatch(r"[a-f0-9]{64}", payload["snapshot"]):
            raise ValueError("Invalid snapshot")
        if not isinstance(payload["id"], str):
            raise ValueError("Invalid event")
        validate_voting_key(payload["id"], allow_event_keys=True)
        if not query.start_on <= date.fromisoformat(payload["date"]) <= query.end_on:
            raise ValueError("Invalid day")
        return payload
    except (ValueError, TypeError, KeyError) as error:
        raise PublicProfileError("INVALID_CURSOR") from error


def encode_storage_cursor(query, snapshot, row):
    payload = {
        "v": 2,
        "filters": filter_fingerprint(query),
        "snapshot": snapshot,
        "date": row["occurred_on"],
        "id": row["voting_id"],
    }
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
